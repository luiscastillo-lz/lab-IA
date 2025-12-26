# 🤖 RAG - Asistente Virtual de Laboratorio de Control de Calidad

Sistema RAG (Retrieval-Augmented Generation) completo con Langchain y Google Gemini 2.5 Flash para consultar instructivos y procedimientos de laboratorio.

## 📋 Características

### 🔍 Pipeline de Ingestión Robusto
- **Múltiples Parsers de PDF**: pdfplumber, PDFMiner, Tabula, PyMuPDF + pytesseract OCR
- **Extracción Inteligente**: Texto, tablas complejas, imágenes con OCR
- **Limpieza Automática**: Remoción de headers/footers repetidos
- **Normalización de Unidades**: °C, psi, MPa, mm, etc.
- **Extracción de Metadatos**: Códigos LL-CI-I-##, normas ASTM/EN, revisiones
- **Chunking Semántico**: División por secciones (Inicio, Requisitos, Procedimiento, etc.)
- **Logging de Errores**: Continúa procesando si un PDF falla
- **Compatible con Python 3.11.9**

### 💬 Chatbot Interactivo
- **UI Moderna con Gradio**: Paleta azul profesional (#2563eb)
- **Parámetros LLM Configurables**: Temperatura, tokens, modelo seleccionable
- **Memoria Conversacional**: Mantiene contexto de últimas 5 interacciones
- **Prompt Especializado**: Chain of Thought + restricciones de fuentes
- **Visualización de Fuentes**: Muestra documentos y normas consultadas
- **Botón Copiar Respuesta**: Integrado en cada mensaje del bot
- **Sistema de Feedback**: Botones 👍/👎 para evaluar respuestas
- **Exportar a PDF**: Descarga conversación completa

### 🎯 Características del Prompt
```
✓ Chain of Thought (análisis paso a paso)
✓ Restricción estricta a información del contexto
✓ Respuesta estructurada en 3 párrafos:
  1. Respuesta directa
  2. Detalles técnicos
  3. Recomendación práctica
✓ Estilo profesional en español formal
✓ Referencias técnicas (ASTM, códigos de procedimiento)
```

## 🛠️ Requisitos del Sistema

### Software Requerido

1. **Python 3.9+**
   - Descargar: https://www.python.org/downloads/

2. **Tesseract OCR** (para pytesseract)
   - **Windows**: Descargar instalador desde https://github.com/UB-Mannheim/tesseract/wiki
   - Instalar en: `C:\Program Files\Tesseract-OCR` (ubicación por defecto configurada)
   - **Linux**: `sudo apt-get install tesseract-ocr`
   - **Mac**: `brew install tesseract`

3. **Java Runtime Environment (JRE)** (para tabula-py)
   - Descargar: https://www.java.com/download/
   - Verificar instalación: `java -version`

**Nota**: Python 3.11.9 es la versión recomendada y probada.

## 📦 Instalación

### 1. Clonar o Descargar el Proyecto

```bash
cd "c:\Users\luis.castillo\OneDrive - Lazarus & Lazarus\IA\Rag Control de Calidad"
```

### 2. Crear Entorno Virtual (Recomendado)

```powershell
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Si hay error de permisos, ejecutar primero:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3. Instalar Dependencias

```powershell
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno

1. Copiar el archivo de ejemplo:
   ```powershell
   Copy-Item .env.example .env
   ```

2. Editar `.env` y configurar tu API key de Google:
   ```
   GOOGLE_API_KEY=tu_api_key_aqui
   ```

   **Obtener API Key:**
   - Ir a: https://ai.google.dev/
   - Crear proyecto en Google AI Studio
   - Generar API key
   - **Importante**: Esta API key es diferente a Google Cloud API keys

### 5. Preparar PDFs

Asegúrate de que tus PDFs estén en la carpeta `raw/`:

```
raw/
├── LLCCI01 ...pdf
├── LLCCI02 ...pdf
└── ... (41 PDFs total)
```

## 🚀 Uso

### Paso 1: Procesar PDFs (Ingestión)

Ejecutar el pipeline de ingestión para procesar los 41 PDFs:

```powershell
python ingest.py
```

**Qué hace este script:**
- Extrae texto, tablas e imágenes de cada PDF
- Aplica OCR a imágenes cuando es necesario
- Limpia y normaliza el contenido
- Extrae metadatos (códigos, normas, revisiones)
- Crea chunks semánticos por sección
- Genera embeddings con Google Gemini
- Almacena en ChromaDB (`./chroma_db/`)

**Tiempo estimado**: 5-10 minutos para 41 PDFs

**Logs generados:**
- `logs/ingestion.log` - Log completo del proceso
- `logs/failed_pdfs.json` - PDFs que fallaron (si alguno)

### Paso 2: Iniciar Chatbot

```powershell
python app.py
```

**Interfaz web se abrirá en:**
```
http://127.0.0.1:7860
```

## 📖 Guía de Uso del Chatbot

### Panel de Configuración (Izquierda)

1. **⚙️ Configuración del Modelo**
   - **Temperatura** (0-1): Controla creatividad
     - 0.0 = Respuestas precisas y deterministas
     - 0.3 = Equilibrio (recomendado)
     - 1.0 = Más creativo (no recomendado para datos técnicos)
   - **Max Tokens**: Longitud máxima de respuesta (1024 recomendado)
   - **Modelo**: Seleccionar entre:
     - `gemini-2.0-flash-exp` (más rápido, recomendado)
     - `gemini-1.5-flash` (alternativa)
     - `gemini-1.5-pro` (más potente pero lento)

2. **📊 Acciones**
   - **Exportar Chat a PDF**: Descarga conversación completa
   - **Reiniciar Conversación**: Limpia historial y memoria

### Panel de Chat (Derecha)

1. **Hacer Preguntas**
   - Escribir pregunta en el campo de texto
   - Presionar Enter o click en "✈️ Enviar"

2. **Respuestas del Bot**
   - Incluyen 3 párrafos estructurados
   - Botón copiar integrado en cada mensaje
   - Sección "📚 Fuentes consultadas" al final

3. **Feedback**
   - 👍 Útil: Marca respuesta como útil
   - 👎 No útil: Marca respuesta como no útil
   - Feedback se guarda en `logs/feedback.json`

### Ejemplos de Preguntas

```
✓ ¿Cuál es el procedimiento para medir el pH del cemento?
✓ ¿Qué norma ASTM se usa para resistencia a compresión del concreto?
✓ ¿Cómo se prepara una muestra de mortero según ASTM C305?
✓ ¿Cuál es el equipo necesario para el ensayo de fluidez?
✓ ¿Qué temperatura debe tener el agua para la prueba de fraguado?
✓ Explica el procedimiento de tamizado de agregados
```

## 📁 Estructura del Proyecto

```
Rag Control de Calidad/
│
├── raw/                          # PDFs originales (41 archivos)
│   ├── LLCCI01 ...pdf
│   └── ...
│
├── chroma_db/                    # Base de datos vectorial (generada)
│   └── [archivos de ChromaDB]
│
├── logs/                         # Logs del sistema
│   ├── ingestion.log            # Log de procesamiento de PDFs
│   ├── failed_pdfs.json         # PDFs que fallaron
│   └── feedback.json            # Feedback de usuarios
│
├── exports/                      # PDFs exportados de conversaciones
│   └── chat_export_*.pdf
│
├── ingest.py                    # Pipeline de ingestión
├── app.py                       # Chatbot con UI
├── requirements.txt             # Dependencias Python
├── .env.example                 # Template de configuración
├── .env                         # Configuración (crear manualmente)
└── README.md                    # Esta documentación
```

## 🔧 Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE DE INGESTIÓN                        │
└─────────────────────────────────────────────────────────────────┘
                              │
    ┌─────────────────────────┴─────────────────────────┐
    │                                                     │
┌───▼────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐  ┌─────┐
│  PDF   │→ │PDFPlumber│→ │PDFMiner │→ │  Tabula  │→ │ OCR │
│  41    │  │  (texto) │  │(fallback│  │ (tablas) │  │(img)│
└────────┘  └──────────┘  └─────────┘  └──────────┘  └─────┘
                              │
                    ┌─────────▼──────────┐
                    │   LIMPIEZA Y       │
                    │   NORMALIZACIÓN    │
                    │ - Headers/Footers  │
                    │ - Unidades         │
                    │ - Metadatos        │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  CHUNKING          │
                    │  SEMÁNTICO         │
                    │ - Por secciones    │
                    │ - 512-1024 tokens  │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  EMBEDDINGS        │
                    │  Google Gemini     │
                    │  embedding-001     │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │    CHROMADB        │
                    │  Vector Store      │
                    └────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      CHATBOT (RETRIEVAL)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
    ┌───────▼────────┐              ┌──────────▼─────────┐
    │   PREGUNTA     │              │  MEMORIA (k=5)     │
    │   USUARIO      │              │  Últimas 5         │
    └───────┬────────┘              │  interacciones     │
            │                        └────────────────────┘
            │                                   │
    ┌───────▼───────────────────────────────────▼────────┐
    │           RETRIEVAL (ChromaDB)                     │
    │           Top-K=5 documentos similares             │
    └───────┬────────────────────────────────────────────┘
            │
    ┌───────▼────────┐
    │  CONTEXTO +    │
    │  PROMPT CoT    │
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │  GEMINI 2.5    │
    │  FLASH         │
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │  RESPUESTA     │
    │  3 párrafos +  │
    │  Fuentes       │
    └────────────────┘
```

## 🐛 Troubleshooting

### Error: "GOOGLE_API_KEY no configurada"

**Solución:**
1. Crear archivo `.env` desde `.env.example`
2. Agregar tu API key de Google AI Studio
3. Reiniciar la aplicación

### Error: "Tesseract not found"

**Solución:**
1. Instalar Tesseract desde https://github.com/UB-Mannheim/tesseract/wiki
2. Verificar que esté en `C:\Program Files\Tesseract-OCR`
3. Si está en otra ubicación, editar `ingest.py` línea 36:
   ```python
   pytesseract.pytesseract.tesseract_cmd = r'C:\ruta\a\tu\tesseract.exe'
   ```

### Error: "Java not found" (tabula-py)

**Solución:**
1. Instalar Java JRE desde https://www.java.com/download/
2. Verificar instalación: `java -version`
3. Reiniciar terminal

### Error: "No se encontró la base de datos ChromaDB"

**Solución:**
1. Ejecutar primero: `python ingest.py`
2. Esperar a que termine el procesamiento
3. Verificar que exista la carpeta `chroma_db/`
4. Luego ejecutar: `python app.py`

### PDFs no se procesan correctamente

**Solución:**
1. Revisar `logs/ingestion.log` para detalles
2. Revisar `logs/failed_pdfs.json` para PDFs específicos que fallaron
3. Verificar que los PDFs no estén corruptos o protegidos con contraseña
4. Asegurarse de que Tesseract, Java y Ghostscript estén instalados

### Respuestas del chatbot son genéricas o incorrectas

**Posibles causas:**
1. **Temperatura muy alta**: Reducir a 0.2-0.3
2. **Ingestión incompleta**: Re-ejecutar `ingest.py`
3. **Pregunta muy vaga**: Ser más específico (mencionar norma, procedimiento, equipo)
4. **Información no existe**: El bot responderá "No tengo información" correctamente

## 📊 Logs y Monitoreo

### Archivos de Log

1. **logs/ingestion.log**
   - Proceso completo de ingestión
   - Éxitos y errores por PDF
   - Estadísticas de chunks generados

2. **logs/failed_pdfs.json**
   - PDFs que fallaron durante procesamiento
   - Detalles del error
   - Timestamp

3. **logs/feedback.json**
   - Feedback de usuarios (👍/👎)
   - Pregunta y respuesta asociada
   - Timestamp

### Monitorear el Sistema

```powershell
# Ver últimos logs de ingestión
Get-Content logs/ingestion.log -Tail 50

# Ver PDFs que fallaron
Get-Content logs/failed_pdfs.json

# Ver feedback de usuarios
Get-Content logs/feedback.json | ConvertFrom-Json | Format-Table
```

## 🔄 Re-procesamiento

Si agregas nuevos PDFs o quieres re-procesar:

```powershell
# 1. Eliminar base de datos anterior
Remove-Item -Recurse -Force chroma_db

# 2. Limpiar logs (opcional)
Remove-Item logs/*.log
Remove-Item logs/failed_pdfs.json

# 3. Re-ejecutar ingestión
python ingest.py

# 4. Reiniciar chatbot
python app.py
```

## 🎨 Personalización

### Modificar Prompt del Sistema

Editar en `app.py` línea 40-73:

```python
SYSTEM_PROMPT = """
Tu prompt personalizado aqui...
"""
```

### Cambiar Paleta de Colores

Editar CSS en `app.py` función `create_ui()`:

```python
custom_css = """
.header-container {
    background: linear-gradient(135deg, #TU_COLOR 0%, #TU_COLOR_2 100%);
}
"""
```

### Ajustar Chunk Size

Editar en `ingest.py` función `semantic_chunking()` línea 271:

```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,  # Modificar aquí
    chunk_overlap=200,  # Y aquí
)
```

## 📈 Mejoras Futuras

- [ ] Dashboard de análisis de feedback
- [ ] Búsqueda por filtros (norma, código, fecha)
- [ ] Modo multi-idioma (inglés/español)
- [ ] Integración con bases de datos SQL para metadatos
- [ ] API REST para integración con otros sistemas
- [ ] Autenticación de usuarios
- [ ] Sistema de caché para respuestas frecuentes

## 📄 Licencia

Este proyecto es de uso interno para el Laboratorio de Control de Calidad.

## 🤝 Soporte

Para problemas o dudas:
1. Revisar la sección **Troubleshooting**
2. Consultar los logs en `logs/`
3. Contactar al equipo de desarrollo

---

**Desarrollado con ❤️ para el Laboratorio de Control de Calidad**

*Última actualización: Diciembre 2025*
