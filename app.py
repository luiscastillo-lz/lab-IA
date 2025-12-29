"""
================================================================================================
APP.PY - RAG LABIA
Aplicación Flask para Asistente Virtual de Laboratorio de Control de Calidad
================================================================================================

Características:
- Google Gemini 2.5 Flash como LLM
- Configuración explícita de temperatura, max_tokens, modelo
- Prompt Chain of Thought especializado para laboratorio
- Historial conversacional (últimas 5 interacciones)
- Retrieval con similarity_search (k=5-10)
- Logging completo con tokens y costos
- Endpoints: /chat, /vote, /feedback, /metrics, /vectorize

Base de datos: labia_db
Colección: labia_embeddings
Puerto: 8000

Autor: Sistema LabIa
Fecha: 27 de diciembre de 2025
================================================================================================
"""

# Configuración gRPC ANTES de cualquier import (CRÍTICO)
import grpc_config

import os
import time
import uuid
import ssl
import httpx
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# LangChain con Google Gemini
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

# Database y otros módulos
import database
import ingest

# ================================================================================================
# CONFIGURACIÓN
# ================================================================================================

load_dotenv()

# ================================================================================================
# BYPASS SSL PARA REDES CORPORATIVAS
# ================================================================================================

# Cliente HTTP con SSL deshabilitado para bypass de certificados corporativos
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

httpx_client = httpx.Client(verify=False, timeout=60.0)

# Deshabilitar warnings de SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)  # Habilitar CORS para todas las rutas

# Inicializar Base de Datos
database.init_db()

# ================================================================================================
# CONFIGURACIÓN EXPLÍCITA DEL LLM
# ================================================================================================

LLM_CONFIG = {
    "model": os.getenv("LLM_MODEL", "gemini-2.5-flash-latest"),  # Modelo configurable
    "temperature": float(os.getenv("LLM_TEMPERATURE", "0.6")),   # 0-1 (Configurableexplícitamente)
    "max_output_tokens": int(os.getenv("LLM_MAX_TOKENS", "1000")),  # Configurable
    "top_p": 0.95,
    "top_k": 40
}

print("\n" + "=" * 80)
print("🤖 CONFIGURACIÓN LLM - GOOGLE GEMINI")
print("=" * 80)
print(f"Modelo: {LLM_CONFIG['model']}")
print(f"Temperatura: {LLM_CONFIG['temperature']}")
print(f"Max Tokens: {LLM_CONFIG['max_output_tokens']}")
print("=" * 80 + "\n")

# ================================================================================================
# CONSTANTES
# ================================================================================================

COLLECTION_NAME = "labia_embeddings"
RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", "5"))  # Número de documentos a recuperar

# PostgreSQL Connection String
PG_CONNECTION_STRING = f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', '')}@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'labia_db')}"

# ================================================================================================
# INICIALIZACIÓN DE EMBEDDINGS Y VECTORSTORE
# ================================================================================================

print("🔗 Conectando a Google Gemini Embeddings...")
# Cliente httpx customizado para bypass SSL y DNS
httpx_client_embeddings = httpx.Client(
    verify=False,
    timeout=120.0,
    follow_redirects=True
)

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    transport="rest",  # Forzar REST (no gRPC)
    client_options={"api_endpoint": "https://generativelanguage.googleapis.com"},
    client=httpx_client_embeddings  # Bypass SSL y DNS issues
)

print(f"🗄️  Conectando a PostgreSQL+pgvector (colección: {COLLECTION_NAME})...")
vectorstore = PGVector(
    connection=PG_CONNECTION_STRING,
    collection_name=COLLECTION_NAME,
    embeddings=embeddings
)

# ================================================================================================
# INICIALIZACIÓN DEL LLM (GOOGLE GEMINI)
# ================================================================================================

print("🚀 Inicializando Google Gemini 2.5 Flash...")
llm = ChatGoogleGenerativeAI(
    model=LLM_CONFIG["model"],
    temperature=LLM_CONFIG["temperature"],
    max_output_tokens=LLM_CONFIG["max_output_tokens"],
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    transport="rest",  # Usar REST en vez de gRPC
    client_options={"api_endpoint": "https://generativelanguage.googleapis.com"}
)

# ================================================================================================
# SYSTEM PROMPT ESPECIALIZADO PARA LABORATORIO
# ================================================================================================

SYSTEM_PROMPT = """Eres un asistente virtual experto en procedimientos del laboratorio.
Tu tarea es ayudar a técnicos y laboratoristas con preguntas sobre los instructivos y documentacion internos proporcionados.
INSTRUCCIONES CRÍTICAS:

1. ANALIZA paso a paso (Chain of Thought):
   - ¿Cuál es exactamente la pregunta?
   - ¿Qué información relevante hay en el contexto?
   - ¿Cuál es la mejor respuesta?
   -- Si la pregunta es general o ambigua, busca el procedimiento o sección más relevante, aunque no coincida exactamente con las palabras usadas.
- Si la pregunta no usa los mismos términos que el instructivo, busca sinónimos o frases relacionadas.


2. RESTRINGE tu respuesta:
   - SOLO usa información del contexto proporcionado
   - Si no tienes la información, responde: "No tengo información sobre esto en los instructivos disponibles."
   - NUNCA inventes especificaciones técnicas, normas o procedimientos

3. ESTRUCTURA tu respuesta:
   - Párrafo 1: Respuesta directa a la pregunta
   - Párrafo 2: Detalles técnicos (procedimiento, normas ASTM, equipos)
   - Párrafo 3: Recomendación o precaución (si aplica)

4. ESTILO:
   - Profesional pero amigable
   - Máximo 3 párrafos
   - Incluye referencias técnicas (normas ASTM, códigos de instructivo)
   - Español formal

5. EJEMPLOS:

   Pregunta: "¿Cómo medir el pH del cemento?"
   
   Respuesta: "El pH del cemento se mide según el instructivo LL-CI-I-02, que sigue la norma ASTM C1293. 
   Se prepara una solución acuosa al 10% de cemento en agua destilada, se agita durante 5 minutos y se 
   deja reposar 10 minutos antes de medir con un pH-metro calibrado.
   
   El procedimiento requiere un pH-metro con precisión de ±0.1, agua destilada y una balanza analítica. 
   La temperatura de medición debe estar entre 20-25°C para asegurar resultados precisos.
   
   Es importante calibrar el pH-metro antes de cada serie de mediciones y verificar que la muestra 
   esté homogénea para obtener lecturas representativas."

CONTEXTO DE INSTRUCTIVOS DISPONIBLES:
{context}

HISTORIAL DE CONVERSACIÓN:
{chat_history}

PREGUNTA DEL TÉCNICO:
{question}
"""

# ================================================================================================
# FUNCIONES AUXILIARES
# ================================================================================================

def calculate_tokens_gemini(text: str) -> int:
    """
    Estima tokens para Google Gemini.
    Aproximación: ~1 token ≈ 4 caracteres para texto en español.
    
    Para cálculo exacto, usar la API de Gemini (futura mejora).
    """
    return len(text) // 4


def format_chat_history(history_tuples: list) -> str:
    """
    Formatea el historial de chat para incluir en el prompt.
    
    Args:
        history_tuples: Lista de tuplas [(user_query, bot_response), ...]
    
    Returns:
        String formateado con el historial
    """
    if not history_tuples:
        return "No hay historial previo."
    
    formatted = []
    for idx, (user_q, bot_r) in enumerate(history_tuples, 1):
        formatted.append(f"Interacción {idx}:")
        formatted.append(f"  Usuario: {user_q}")
        formatted.append(f"  Asistente: {bot_r}")
    
    return "\n".join(formatted)

# ================================================================================================
# RUTAS (ENDPOINTS)
# ================================================================================================

@app.route('/')
def index():
    """Sirve la interfaz principal del chat."""
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    """
    Endpoint principal para interacciones de chat.
    
    Request Body:
        {
            "message": "Pregunta del usuario",
            "session_id": "UUID de la sesión (opcional)"
        }
    
    Response:
        {
            "response": "Respuesta del asistente",
            "sources": ["documento1.pdf", "documento2.pdf"],
            "log_id": 123,
            "latency": 1.23,
            "session_id": "uuid"
        }
    """
    data = request.json
    user_query = data.get('message', '')
    session_id = data.get('session_id')

    if not user_query:
        return jsonify({'error': 'Message is required'}), 400

    # Generar session_id si no existe
    if not session_id:
        session_id = str(uuid.uuid4())

    start_time = time.time()

    # 1. Actualizar estado de sesión
    database.upsert_session_state(session_id)

    # 2. Recuperar historial de conversación (últimas 5 interacciones)
    history_tuples = database.get_recent_history(session_id, limit=5)
    formatted_history = format_chat_history(history_tuples)

    # 3. Retrieval (RAG) - Búsqueda semántica
    try:
        docs = vectorstore.similarity_search(user_query, k=RETRIEVAL_K)
    except Exception as e:
        print(f"❌ Error en vectorstore: {e}")
        docs = []

    # Construir contexto
    context_text = "\n\n".join([
        f"[{d.metadata.get('codigo_documento', 'DOC')}] {d.page_content}" 
        for d in docs
    ])
    
    # Extraer fuentes únicas
    sources = list(set([
        d.metadata.get('source', 'Desconocido') 
        for d in docs
    ]))

    # 4. Generar respuesta con LLM
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{question}")
    ])

    chain = prompt_template | llm

    try:
        response_message = chain.invoke({
            "context": context_text,
            "chat_history": formatted_history,
            "question": user_query
        })
        bot_response = response_message.content
    except Exception as e:
        print(f"❌ Error en LLM: {e}")
        bot_response = "Lo siento, ha ocurrido un error al procesar tu solicitud. Por favor, intenta de nuevo."

    latency = time.time() - start_time

    # 5. Calcular tokens (estimación)
    # Construir el prompt completo aproximado
    full_prompt_text = f"""Eres un asistente virtual del laboratorio de control de calidad.
    
CONTEXTO: {context_text}
HISTORIAL: {formatted_history}
PREGUNTA: {user_query}"""
    
    tokens_in = calculate_tokens_gemini(full_prompt_text)
    tokens_out = calculate_tokens_gemini(bot_response)

    # 6. Logging en base de datos
    context_docs_json = [
        {
            "source": d.metadata.get('source'),
            "codigo": d.metadata.get('codigo_documento'),
            "seccion": d.metadata.get('seccion')
        }
        for d in docs[:3]  # Solo primeros 3 para JSON
    ]

    log_id = database.log_interaction(
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency=latency,
        user_query=user_query,
        bot_response=bot_response,
        session_id=session_id,
        context_docs=context_docs_json
    )

    return jsonify({
        "response": bot_response,
        "sources": sources,
        "log_id": log_id,
        "latency": round(latency, 2),
        "session_id": session_id,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": round((tokens_in * 0.00001875 / 1000) + (tokens_out * 0.000075 / 1000), 6)
    })


@app.route('/vote', methods=['POST'])
def vote():
    """
    Registra un voto (thumbs up/down) en una respuesta.
    
    Request Body:
        {
            "log_id": 123,
            "vote": "up" | "down"
        }
    """
    data = request.json
    log_id = data.get('log_id')
    vote_type = data.get('vote')
    
    if log_id and vote_type in ['up', 'down']:
        database.update_vote(log_id, vote_type)
        return jsonify({"status": "success"})
    
    return jsonify({"error": "Invalid request"}), 400


@app.route('/feedback', methods=['POST'])
def feedback():
    """
    Guarda feedback negativo detallado.
    
    Request Body:
        {
            "log_id": 123,
            "comment": "Comentario del usuario",
            "source": "Página web",
            "response": "Respuesta que generó el feedback"
        }
    """
    data = request.json
    database.save_negative_feedback(
        chat_log_id=data.get('log_id'),
        comment=data.get('comment'),
        source=data.get('source', 'Web'),
        response=data.get('response', '')
    )
    return jsonify({"status": "success"})


@app.route('/metrics', methods=['GET'])
def get_metrics():
    """
    Retorna métricas del sistema.
    
    Response:
        {
            "total_chats": 100,
            "avg_latency": 1.23,
            "tokens_in": 50000,
            "tokens_out": 30000,
            "cost": "$0.0042",
            "pos_votes": 80,
            "neg_votes": 5,
            "satisfaction": 94.1,
            "doc_count": 245
        }
    """
    stats = database.get_metrics()
    
    # Obtener conteo de documentos en vectorstore
    try:
        conn = database.get_pg_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %s)",
            (COLLECTION_NAME,)
        )
        doc_count = cursor.fetchone()[0] or 0
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error obteniendo conteo de documentos: {e}")
        doc_count = 0

    return jsonify({
        "total_chats": stats["total_chats"],
        "avg_latency": stats["avg_latency"],
        "tokens_in": stats["tokens_in"],
        "tokens_out": stats["tokens_out"],
        "cost": f"${stats['cost_usd']}",
        "pos_votes": stats["pos_votes"],
        "neg_votes": stats["neg_votes"],
        "satisfaction": stats["satisfaction"],
        "doc_count": doc_count
    })


@app.route('/vectorize', methods=['POST'])
def trigger_vectorization():
    """
    Dispara manualmente el proceso de ingesta de documentos.
    
    Útil para re-procesar PDFs después de agregar nuevos archivos a /raw.
    
    Response:
        {
            "message": "Documentos re-ingestados correctamente."
        }
    """
    try:
        print("\n🔄 Disparando proceso de ingesta manual...")
        ingest.ingest_pdfs()
        
        # Refrescar vectorstore
        global vectorstore
        vectorstore = PGVector(
            connection=PG_CONNECTION_STRING,
            collection_name=COLLECTION_NAME,
            embeddings=embeddings
        )
        
        return jsonify({"message": "Documentos re-ingestados correctamente."})
    except Exception as e:
        print(f"❌ Error en vectorización: {e}")
        return jsonify({"error": f"Falló la vectorización: {str(e)}"}), 500


@app.route('/clear_session', methods=['POST'])
def clear_session():
    """
    Limpia el historial de una sesión (Nueva Conversación).
    
    Request Body:
        {
            "session_id": "uuid"
        }
    """
    data = request.json
    session_id = data.get('session_id')
    
    if session_id:
        database.clear_session(session_id)
        return jsonify({"status": "success", "message": "Sesión limpiada"})
    
    return jsonify({"error": "session_id required"}), 400

# ================================================================================================
# MAIN
# ================================================================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8010))
    
    print("\n" + "=" * 80)
    print("🧪 LABIA - ASISTENTE VIRTUAL DE LABORATORIO")
    print("=" * 80)
    print(f"🌐 Servidor corriendo en: http://localhost:{port}")
    print(f"🗄️  Base de datos: {os.getenv('POSTGRES_DB', 'labia_db')}")
    print(f"📚 Colección: {COLLECTION_NAME}")
    print(f"🤖 Modelo: {LLM_CONFIG['model']}")
    print("=" * 80 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)
