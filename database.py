"""
================================================================================================
DATABASE.PY - RAG LABIA
Gestión de Base de Datos PostgreSQL para LabIa - Asistente Virtual de Laboratorio
================================================================================================

Funcionalidades:
- Inicialización de PostgreSQL + pgvector
- Gestión de historial conversacional (últimas 5 interacciones)
- Logging de interacciones (tokens, latency, costos)
- Sistema de votos y feedback
- Métricas del sistema

Base de datos: labia_db
Colección embeddings: labia_embeddings
LLM: Google Gemini 2.5 Flash

Autor: Sistema LabIa
Fecha: 27 de diciembre de 2025
================================================================================================
"""

from datetime import datetime
import psycopg2
from psycopg2.extras import Json
import os
from dotenv import load_dotenv

load_dotenv()

# ================================================================================================
# CONEXIÓN A POSTGRESQL
# ================================================================================================

def get_pg_connection():
    """Conexión a PostgreSQL con configuración para LabIa."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "labia_db"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "")
    )

# ================================================================================================
# INICIALIZACIÓN
# ================================================================================================

def init_pgvector():
    """Inicializa extensión pgvector en PostgreSQL."""
    try:
        con = get_pg_connection()
        con.autocommit = True
        cursor = con.cursor()
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("✅ pgvector extension creada exitosamente")
        cursor.close()
        con.close()
    except Exception as e:
        print(f"❌ Error inicializando pgvector: {e}")
        print(f"   Verifica que PostgreSQL esté corriendo y que tengas permisos")


def init_db():
    """
    Inicializa todas las tablas necesarias para LabIa.
    
    Tablas:
    - chat_logs: Registro de todas las interacciones (con tokens y costos)
    - chat_session_state: Estado de sesiones (historial conversacional JSONB)
    - negative_feedbacks: Feedbacks negativos de usuarios
    """
    print("\n" + "=" * 80)
    print("🔧 INICIALIZANDO BASE DE DATOS - RAG LABIA")
    print("=" * 80)
    
    init_pgvector()
    
    conn = get_pg_connection()
    conn.autocommit = True
    c = conn.cursor()
    
    # Tabla principal de logs
    c.execute('''CREATE TABLE IF NOT EXISTS chat_logs (
                 id SERIAL PRIMARY KEY,
                 user_id TEXT DEFAULT NULL,
                 session_id TEXT DEFAULT NULL,
                 timestamp TIMESTAMP DEFAULT NOW(),
                 user_query TEXT DEFAULT NULL,
                 bot_response TEXT DEFAULT NULL,
                 context_docs JSONB DEFAULT NULL,
                 tokens_in INTEGER DEFAULT 0,
                 tokens_out INTEGER DEFAULT 0,
                 latency REAL DEFAULT 0,
                 cost_usd DECIMAL(10,6) DEFAULT 0,
                 vote TEXT DEFAULT NULL
                 )''')
    print("✅ Tabla chat_logs creada")

    # Estado por sesión con historial conversacional en JSONB
    c.execute('''CREATE TABLE IF NOT EXISTS chat_session_state (
                 session_id TEXT PRIMARY KEY,
                 user_id TEXT DEFAULT NULL,
                 conversation_history JSONB DEFAULT '[]'::jsonb,
                 last_interaction TIMESTAMP DEFAULT NOW(),
                 created_at TIMESTAMP DEFAULT NOW()
                 )''')
    print("✅ Tabla chat_session_state creada (con conversation_history JSONB)")

    # Índices útiles
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_session_time ON chat_logs(session_id, timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_session_state_last_interaction ON chat_session_state(last_interaction)")
        print("✅ Índices creados")
    except Exception as e:
        print(f"⚠️  Índices ya existen: {e}")
    
    # Tabla de feedbacks negativos
    c.execute('''CREATE TABLE IF NOT EXISTS negative_feedbacks (
                 id SERIAL PRIMARY KEY,
                 chat_log_id INTEGER,
                 timestamp TIMESTAMP DEFAULT NOW(),
                 comment TEXT,
                 source TEXT DEFAULT 'Desconocido',
                 response TEXT DEFAULT '',
                 FOREIGN KEY (chat_log_id) REFERENCES chat_logs(id)
                 )''')
    print("✅ Tabla negative_feedbacks creada")
    
    conn.commit()
    conn.close()
    print("=" * 80)
    print("✅ BASE DE DATOS INICIALIZADA CORRECTAMENTE\n")

# ================================================================================================
# LOGGING DE INTERACCIONES
# ================================================================================================

def log_interaction(tokens_in=0, tokens_out=0, latency=0.0, user_query=None, bot_response=None, 
                   session_id=None, user_id=None, context_docs=None):
    """
    Registra una interacción completa del chat con cálculo de costos Google Gemini.
    
    Pricing Google Gemini 2.5 Flash:
    - Input: $0.00001875 / 1K tokens
    - Output: $0.000075 / 1K tokens
    
    Args:
        tokens_in: Tokens de entrada (pregunta + contexto)
        tokens_out: Tokens de salida (respuesta)
        latency: Tiempo de respuesta en segundos
        user_query: Pregunta del usuario
        bot_response: Respuesta del chatbot
        session_id: ID único de la sesión
        user_id: ID del usuario
        context_docs: Documentos de contexto recuperados (para análisis)
    
    Returns:
        log_id: ID del registro creado
    """
    conn = get_pg_connection()
    cursor = conn.cursor()
    timestamp = datetime.now()
    
    # Calcular costo (Google Gemini 2.5 Flash pricing)
    cost_usd = (tokens_in * 0.00001875 / 1000) + (tokens_out * 0.000075 / 1000)
    
    # Convertir context_docs a JSON si es un dict/list
    if isinstance(context_docs, (dict, list)):
        context_docs_json = Json(context_docs)
    else:
        context_docs_json = context_docs
    
    cursor.execute(
        """INSERT INTO chat_logs
                 (user_id, session_id, timestamp, user_query, bot_response, context_docs,
                  tokens_in, tokens_out, latency, cost_usd, vote)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (user_id, session_id, timestamp, user_query, bot_response, context_docs_json,
         tokens_in, tokens_out, latency, cost_usd, None),
    )
    log_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return log_id

# ================================================================================================
# HISTORIAL CONVERSACIONAL
# ================================================================================================

def get_recent_history(session_id: str, limit: int = 5):
    """
    Devuelve las últimas N interacciones (user_query, bot_response) para una sesión.
    
    IMPORTANTE: Para LabIa mantenemos historial de las últimas 5 interacciones.
    
    Args:
        session_id: ID de la sesión
        limit: Número de interacciones a recuperar (default: 5)
    
    Returns:
        Lista de tuplas [(user_query, bot_response), ...]
    """
    if not session_id:
        return []

    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT user_query, bot_response
           FROM chat_logs
           WHERE session_id = %s
             AND user_query IS NOT NULL
             AND bot_response IS NOT NULL
           ORDER BY id DESC
           LIMIT %s""",
        (session_id, limit)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    rows.reverse()  # Orden cronológico (más antiguo → más reciente)
    return [(u, b) for (u, b) in rows]

# ================================================================================================
# GESTIÓN DE SESIONES
# ================================================================================================

def upsert_session_state(session_id: str, user_id: str = None):
    """
    Crea o actualiza el timestamp de una sesión.
    
    Args:
        session_id: ID de la sesión
        user_id: ID del usuario (opcional)
    """
    if not session_id:
        return
    conn = get_pg_connection()
    cursor = conn.cursor()
    now = datetime.now()
    cursor.execute(
        """INSERT INTO chat_session_state (session_id, user_id, last_interaction, created_at)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT(session_id) DO UPDATE SET
             user_id = COALESCE(EXCLUDED.user_id, chat_session_state.user_id),
             last_interaction = EXCLUDED.last_interaction""",
        (session_id, user_id, now, now)
    )
    conn.commit()
    cursor.close()
    conn.close()


def clear_session(session_id: str):
    """
    Borra todo el historial y estado de una sesión.
    Útil para "Nueva Conversación".
    
    Args:
        session_id: ID de la sesión a limpiar
    """
    if not session_id:
        return
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_logs WHERE session_id = %s", (session_id,))
    cursor.execute("DELETE FROM chat_session_state WHERE session_id = %s", (session_id,))
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ Sesión {session_id} limpiada")

# ================================================================================================
# VOTOS Y FEEDBACK
# ================================================================================================

def update_vote(log_id, vote_type):
    """
    Actualiza el voto de un registro.
    
    Args:
        log_id: ID del registro de chat
        vote_type: 'up' o 'down'
    """
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE chat_logs SET vote = %s WHERE id = %s", (vote_type, log_id))
    conn.commit()
    cursor.close()
    conn.close()


def save_negative_feedback(chat_log_id, comment, source='Desconocido', response=''):
    """
    Guarda feedback negativo de un usuario.
    
    Args:
        chat_log_id: ID del registro de chat
        comment: Comentario del usuario
        source: Fuente del feedback
        response: Respuesta que generó el feedback
    """
    conn = get_pg_connection()
    cursor = conn.cursor()
    timestamp = datetime.now()
    cursor.execute(
        """INSERT INTO negative_feedbacks (chat_log_id, timestamp, comment, source, response)
           VALUES (%s, %s, %s, %s, %s)""",
        (chat_log_id, timestamp, comment, source, response)
    )
    conn.commit()
    cursor.close()
    conn.close()

# ================================================================================================
# MÉTRICAS
# ================================================================================================

def get_metrics():
    """
    Obtiene métricas generales del chatbot LabIa.
    
    Incluye cálculo de costos con pricing de Google Gemini 2.5 Flash.
    
    Returns:
        Dict con métricas: chats, latency, tokens, costos, satisfacción
    """
    conn = get_pg_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*), AVG(latency), SUM(tokens_in), SUM(tokens_out), SUM(cost_usd) FROM chat_logs")
    total_chats, avg_latency, total_in, total_out, total_cost = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE vote = 'up'")
    pos_votes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE vote = 'down'")
    neg_votes = cursor.fetchone()[0]
    
    total_votes = pos_votes + neg_votes
    satisfaction = (pos_votes / total_votes * 100) if total_votes > 0 else 0
    
    total_in = int(total_in or 0)
    total_out = int(total_out or 0)
    total_cost = float(total_cost or 0)
    
    cursor.close()
    conn.close()
    
    return {
        "total_chats": total_chats or 0,
        "avg_latency": round(float(avg_latency) if avg_latency else 0, 2),
        "tokens_in": total_in,
        "tokens_out": total_out,
        "total_tokens": total_in + total_out,
        "cost_usd": round(total_cost, 4),
        "pos_votes": pos_votes or 0,
        "neg_votes": neg_votes or 0,
        "satisfaction": round(satisfaction, 1)
    }

# ================================================================================================
# MAIN (Para testing)
# ================================================================================================

if __name__ == "__main__":
    init_db()
