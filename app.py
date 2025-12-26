"""
Chatbot RAG - API Flask para Asistente Virtual de Laboratorio
Backend API con Google Gemini 2.0 Flash + ChromaDB
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict
from collections import deque

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Langchain
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

# PDF Export
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# ==================== CONFIGURACIÓN ====================
load_dotenv()

# Verificar API key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY or GOOGLE_API_KEY == "your_google_api_key_here":
    raise ValueError("ERROR: GOOGLE_API_KEY no configurada. Copia .env.example a .env y configura tu API key.")

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
FEEDBACK_FILE = "logs/feedback.json"

# Crear directorios necesarios
Path("logs").mkdir(exist_ok=True)
Path("exports").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)

# ==================== PROMPT DEL SISTEMA ====================

SYSTEM_PROMPT = """Eres un asistente virtual del laboratorio.

INSTRUCCIONES CRÍTICAS:

1. RAZONA internamente paso a paso (no lo muestres):
   - Identifica exactamente la pregunta.
   - Usa solo información del contexto.
   - Redacta la mejor respuesta.

2. RESTRINGE tu respuesta:
   - SOLO usa información del contexto proporcionado
   - Si no tienes la información, responde: "No tengo información sobre eso en los documentos del laboratorio."
   - NUNCA inventes especificaciones técnicas, normas o procedimientos

3. ESTRUCTURA tu respuesta en máximo 3 párrafos:
   - Párrafo 1: Respuesta directa a la pregunta
   - Párrafo 2: Detalles técnicos relevantes (especificaciones, normas, pasos)
   - Párrafo 3: Recomendación práctica o consideración importante

4. ESTILO:
   - Profesional pero amigable
   - Máximo 3 párrafos
   - Español formal

CONTEXTO:
{context}

HISTORIAL DE CONVERSACIÓN:
{chat_history}

PREGUNTA DEL USUARIO:
{question}

RESPUESTA:"""

# ==================== CLASE LabAssistant ====================

class LabAssistant:
    """Asistente de laboratorio con parámetros fijos"""
    
    # Parámetros fijos del modelo (hardcodeados)
    TEMPERATURE = 0.5
    MAX_TOKENS = 800    
    MODEL = "gemini-2.5-flash"
    
    def __init__(self):
        """Inicializa el asistente con parámetros fijos"""
        # Cargar vectorstore
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=GOOGLE_API_KEY
        )
        
        self.vectorstore = Chroma(
            persist_directory=CHROMA_DIR,
            embedding_function=self.embeddings,
            collection_name="laboratorio_qa"
        )
        
        # Configurar LLM
        self.llm = ChatGoogleGenerativeAI(
            model=self.MODEL,
            temperature=self.TEMPERATURE,
            max_output_tokens=self.MAX_TOKENS,
            google_api_key=GOOGLE_API_KEY
        )

        # Memoria conversacional (últimas 5 interacciones)
        self._history: deque[Tuple[str, str]] = deque(maxlen=5)
    
    def chat(self, question: str) -> Tuple[str, List[Dict]]:
        """Procesa pregunta y retorna respuesta + fuentes"""
        try:
            source_docs = self.vectorstore.similarity_search(question, k=5)

            context_blocks: List[str] = []
            for doc in source_docs:
                meta = doc.metadata or {}
                filename = meta.get("filename", "Desconocido")
                section = meta.get("section_type", "general")
                context_blocks.append(f"[Fuente: {filename} | Sección: {section}]\n{doc.page_content}")
            context = "\n\n".join(context_blocks)

            chat_history_text = "\n".join([f"Usuario: {q}\nAsistente: {a}" for q, a in self._history])
            prompt = SYSTEM_PROMPT.format(context=context, chat_history=chat_history_text, question=question)

            llm_result = self.llm.invoke(prompt)
            answer = getattr(llm_result, "content", None) or str(llm_result)
            
            # Formatear fuentes
            sources = []
            seen_sources = set()
            
            for doc in source_docs:
                metadata = doc.metadata
                source_id = f"{metadata.get('filename', 'Desconocido')}_{metadata.get('page', 0)}"
                
                if source_id not in seen_sources:
                    sources.append({
                        'filename': metadata.get('filename', 'Desconocido'),
                        'codigo': metadata.get('codigo', 'N/A'),
                        'normas': metadata.get('normas', 'N/A') or 'N/A',
                        'section': metadata.get('section_type', 'general')
                    })
                    seen_sources.add(source_id)

            # Actualizar memoria
            self._history.append((question, answer))

            return answer, sources
            
        except Exception as e:
            return f"Error al procesar la pregunta: {str(e)}", []
    
    def reset_memory(self):
        """Reinicia la memoria conversacional"""
        self._history.clear()


# ==================== FLASK APP ====================

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Estado global
assistant = None
chat_history = []

def get_assistant():
    """Obtiene o inicializa el asistente"""
    global assistant
    if assistant is None:
        assistant = LabAssistant()
    return assistant


# ==================== ENDPOINTS ====================

@app.route('/')
def index():
    """Sirve la página principal"""
    return send_from_directory('static', 'index.html')


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Endpoint para chat"""
    global chat_history
    
    try:
        data = request.json
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Mensaje vacío'}), 400
        
        # Procesar pregunta
        assistant = get_assistant()
        answer, sources = assistant.chat(message)
        
        # Guardar en historial
        chat_entry = {
            'timestamp': datetime.now().isoformat(),
            'question': message,
            'answer': answer,
            'sources': sources
        }
        chat_history.append(chat_entry)
        
        return jsonify({
            'answer': answer,
            'sources': sources,
            'timestamp': chat_entry['timestamp']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/feedback', methods=['POST'])
def api_feedback():
    """Endpoint para guardar feedback"""
    try:
        data = request.json
        message = data.get('message', '')
        feedback_type = data.get('type', 'neutral')
        
        feedback_data = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'feedback': feedback_type
        }
        
        with open(FEEDBACK_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(feedback_data, ensure_ascii=False) + '\n')
        
        return jsonify({'status': 'success', 'message': f'Feedback guardado: {feedback_type}'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export', methods=['GET'])
def api_export():
    """Endpoint para exportar chat a PDF"""
    global chat_history
    
    try:
        if not chat_history:
            return jsonify({'error': 'No hay conversación para exportar'}), 400
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_export_{timestamp}.pdf"
        filepath = f"exports/{filename}"
        
        # Crear PDF
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30
        )
        story.append(Paragraph("Conversación - Asistente Virtual de Laboratorio", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Estilos para pregunta y respuesta
        question_style = ParagraphStyle(
            'Question',
            parent=styles['Normal'],
            fontSize=11,
            leftIndent=20,
            spaceAfter=10
        )
        
        answer_style = ParagraphStyle(
            'Answer',
            parent=styles['Normal'],
            fontSize=10,
            leftIndent=20,
            spaceAfter=20
        )
        
        # Agregar conversaciones
        for idx, entry in enumerate(chat_history, 1):
            time_str = datetime.fromisoformat(entry['timestamp']).strftime("%d/%m/%Y %H:%M:%S")
            story.append(Paragraph(f"<b>Interacción {idx}</b> - {time_str}", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            story.append(Paragraph(f"<b>Pregunta:</b> {entry['question']}", question_style))
            story.append(Paragraph(f"<b>Respuesta:</b> {entry['answer']}", answer_style))
            
            if entry['sources']:
                sources_text = "<b>Fuentes:</b><br/>"
                for src in entry['sources']:
                    sources_text += f"• {src['codigo']} - {src['filename']}<br/>"
                story.append(Paragraph(sources_text, answer_style))
            
            story.append(Spacer(1, 0.3*inch))
        
        doc.build(story)
        
        return jsonify({
            'status': 'success',
            'filename': filename,
            'download_url': f'/exports/{filename}'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/exports/<filename>')
def download_export(filename):
    """Descarga de archivos exportados"""
    return send_from_directory('exports', filename, as_attachment=True)


@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Endpoint para reiniciar conversación"""
    global chat_history, assistant
    
    try:
        if assistant:
            assistant.reset_memory()
        
        chat_history = []
        
        return jsonify({'status': 'success', 'message': 'Conversación reiniciada'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== MAIN ====================

def main():
    """Función principal para lanzar la aplicación"""
    
    # Verificar que existe el vectorstore
    if not Path(CHROMA_DIR).exists():
        print("=" * 80)
        print("ERROR: No se encontró la base de datos vectorial ChromaDB")
        print(f"Ubicación esperada: {CHROMA_DIR}")
        print("\nPrimero ejecuta: python ingest.py")
        print("=" * 80)
        return
    
    print("=" * 80)
    print("🚀 INICIANDO ASISTENTE VIRTUAL DE LABORATORIO - FLASK API")
    print("=" * 80)
    print(f"ChromaDB: {CHROMA_DIR}")
    print(f"Google API Key: {'✓ Configurada' if GOOGLE_API_KEY else '✗ NO configurada'}")
    print(f"Modelo: {LabAssistant.MODEL}")
    print(f"Temperatura: {LabAssistant.TEMPERATURE}")
    print(f"Max Tokens: {LabAssistant.MAX_TOKENS}")
    print("=" * 80)
    print("\n🌐 Servidor Flask iniciado en: http://127.0.0.1:5000")
    print("\nEndpoints disponibles:")
    print("  GET  /                - Interfaz web")
    print("  POST /api/chat        - Enviar mensaje")
    print("  POST /api/feedback    - Guardar feedback")
    print("  GET  /api/export      - Exportar a PDF")
    print("  POST /api/reset       - Reiniciar conversación")
    print("  GET  /exports/<file>  - Descargar PDF")
    print("=" * 80)
    
    app.run(host='127.0.0.1', port=5000, debug=True)


if __name__ == "__main__":
    main()
