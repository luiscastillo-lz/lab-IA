# Lab-Ai: Asistente Virtual de Laboratorio de Control de Calidad

<div align="center">
  <img src="static/labai.png" alt="Lab-Ai Logo" width="200"/>
  
  **Asistente inteligente con RAG para consultas de instructivos de laboratorio**
  
  [![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/downloads/)
  [![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
  [![Google Gemini](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-orange.svg)](https://ai.google.dev/)
  [![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016-blue.svg)](https://www.postgresql.org/)
</div>

---

## 📋 Descripción

**Lab-Ai** es un asistente virtual basado en Retrieval-Augmented Generation (RAG) diseñado para responder consultas sobre procedimientos de laboratorio, normas ASTM, y control de calidad en construcción.

### Características principales:
- ✅ **RAG con Google Gemini 2.5 Flash**: Respuestas precisas basadas en documentación
- ✅ **Procesamiento multi-PDF**: 44 instructivos de laboratorio vectorizados
- ✅ **PostgreSQL + pgvector**: Almacenamiento de embeddings y búsqueda semántica
- ✅ **Feedback del usuario**: Sistema de votos (thumbs up/down) y comentarios
- ✅ **Historial conversacional**: Mantiene contexto entre preguntas
- ✅ **Interfaz minimalista**: Chat intuitivo con respuestas estructuradas

---

## 🏗️ Arquitectura

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Usuario       │◄────►│   Flask App      │◄────►│  PostgreSQL     │
│   (Navegador)   │      │   (puerto 8010)  │      │  + pgvector     │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                               │
                               ▼
                         ┌──────────────────┐
                         │  Google Gemini   │
                         │  2.5 Flash API   │
                         └──────────────────┘
```

**Componentes:**
- **Frontend**: HTML + JavaScript + CSS (servido por Flask)
- **Backend**: Flask + LangChain
- **Base de datos**: PostgreSQL 16 con extensión pgvector
- **LLM**: Google Gemini 2.5 Flash
- **Embeddings**: Google Embedding Model 001

---

## 🚀 Deployment con Docker

### **Requisitos previos**
- Docker 20.10+
- Docker Compose 2.0+
- 2GB RAM mínimo
- Google Gemini API Key ([obtener aquí](https://aistudio.google.com/app/apikey))

### **Pasos de instalación**

#### 1. Clonar el repositorio
```bash
git clone https://github.com/luiscastillo-lz/lab-IA.git
cd lab-IA
```

#### 2. Crear carpeta de PDFs
```bash
mkdir raw
# Copiar los 44 PDFs de instructivos a la carpeta raw/
```

#### 3. Configurar variables de entorno
```bash
cp .env.example .env
nano .env  # o usar tu editor favorito
```

**Editar `.env` con tus credenciales:**
```env
GOOGLE_API_KEY=tu_api_key_de_gemini_aqui
POSTGRES_PASSWORD=tu_password_seguro
```

#### 4. Construir y levantar contenedores
```bash
docker-compose up --build -d
```

#### 5. Verificar que los servicios estén corriendo
```bash
docker-compose ps
```

Deberías ver:
```
NAME                COMMAND                  SERVICE     STATUS      PORTS
labia_app           "python app.py"          app         running     0.0.0.0:8010->8010/tcp
labia_postgres      "docker-entrypoint.s…"   postgres    running     0.0.0.0:5432->5432/tcp
```

#### 6. Ingestar los PDFs (primera vez)
```bash
docker-compose exec app python ingest.py --reset
```

Esto procesará los 44 PDFs y creará ~438 chunks vectorizados.

#### 7. Acceder a la aplicación
```
http://localhost:8010
```

---

## 🛠️ Comandos útiles

### **Ver logs de la aplicación**
```bash
docker-compose logs -f app
```

### **Reiniciar servicios**
```bash
docker-compose restart
```

### **Detener servicios**
```bash
docker-compose down
```

### **Borrar volúmenes (⚠️ CUIDADO: elimina datos)**
```bash
docker-compose down -v
```

### **Acceder a la base de datos**
```bash
docker-compose exec postgres psql -U postgres -d labia_db
```

### **Re-ingestar documentos**
```bash
docker-compose exec app python ingest.py --reset
```

---

## 📊 Base de datos

### **Tablas principales**
- `langchain_pg_embedding`: Vectores de documentos
- `langchain_pg_collection`: Colecciones de embeddings
- `chat_logs`: Registro de conversaciones
- `negative_feedbacks`: Comentarios de usuarios
- `chat_session_state`: Historial conversacional

### **Consultas útiles**
Ver archivo [consultas_db.sql](consultas_db.sql) o [README_DB.md](README_DB.md) para queries completas.

**Ejemplos:**
```sql
-- Ver total de documentos vectorizados
SELECT COUNT(*) FROM langchain_pg_embedding;

-- Ver últimas consultas
SELECT user_query, bot_response, timestamp 
FROM chat_logs 
ORDER BY timestamp DESC 
LIMIT 10;

-- Ver satisfacción del usuario
SELECT 
    COUNT(CASE WHEN vote = 'up' THEN 1 END) AS positivos,
    COUNT(CASE WHEN vote = 'down' THEN 1 END) AS negativos
FROM chat_logs;
```

---

## 🔧 Configuración avanzada

### **Variables de entorno disponibles**

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `GOOGLE_API_KEY` | API Key de Google Gemini | *Requerido* |
| `LLM_MODEL` | Modelo de LLM | `gemini-2.5-flash` |
| `LLM_TEMPERATURE` | Creatividad del modelo (0-1) | `0.8` |
| `LLM_MAX_TOKENS` | Tokens máximos de respuesta | `4096` |
| `CHUNK_SIZE` | Tamaño de chunks para RAG | `1024` |
| `CHUNK_OVERLAP` | Solapamiento entre chunks | `150` |
| `RETRIEVAL_K` | Documentos a recuperar | `5` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | `admin171419860` |
| `DEBUG` | Modo debug de Flask | `False` |

---

## 📁 Estructura del proyecto

```
lab-IA/
├── app.py                  # Aplicación Flask principal
├── database.py             # Conexión y esquemas de PostgreSQL
├── ingest.py               # Pipeline de ingesta de PDFs
├── requirements.txt        # Dependencias Python
├── Dockerfile              # Imagen Docker de la app
├── docker-compose.yml      # Orquestación de servicios
├── .env.example            # Template de variables de entorno
├── .gitignore              # Archivos excluidos de Git
├── README.md               # Este archivo
├── README_DB.md            # Documentación de base de datos
├── consultas_db.sql        # Queries SQL útiles
├── static/                 # Frontend (HTML, CSS, JS)
│   ├── index.html
│   ├── script.js
│   ├── style.css
│   └── labai.png
└── raw/                    # PDFs de instructivos (44 archivos)
```

---

## 🧪 Testing

### **Probar endpoints**

**Health check:**
```bash
curl http://localhost:8010/
```

**Enviar pregunta:**
```bash
curl -X POST http://localhost:8010/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "¿Cómo se mide la gravedad específica?",
    "session_id": "test-001"
  }'
```

**Votar respuesta:**
```bash
curl -X POST http://localhost:8010/vote \
  -H "Content-Type: application/json" \
  -d '{
    "log_id": 1,
    "vote": "up"
  }'
```

---

## 🐛 Troubleshooting

### **La app no inicia**
```bash
# Ver logs detallados
docker-compose logs -f app

# Verificar que PostgreSQL esté saludable
docker-compose ps postgres
```

### **Error de conexión a PostgreSQL**
```bash
# Verificar que la contraseña en .env coincida
# Reiniciar servicios
docker-compose down
docker-compose up -d
```

### **Respuestas del LLM muy cortas**
- Verificar que `LLM_MAX_TOKENS` en `.env` sea >= 4096

### **No encuentra documentos**
```bash
# Re-ingestar PDFs
docker-compose exec app python ingest.py --reset
```

---

## 📝 Licencia

Proyecto privado - Lazarus & Lazarus  
© 2025 Luis Castillo

---

## 👥 Contacto

**Desarrollador**: Luis Castillo  
**Organización**: Lazarus & Lazarus  
**Repositorio**: [https://github.com/luiscastillo-lz/lab-IA](https://github.com/luiscastillo-lz/lab-IA)

---

## 🚀 Roadmap

- [ ] Autenticación de usuarios
- [ ] Exportar conversaciones a PDF
- [ ] Dashboard de métricas
- [ ] Soporte multiidioma
- [ ] Integración con Slack/Teams
- [ ] API REST documentada con Swagger

---

<div align="center">
  <strong>Hecho con ❤️ para mejorar la eficiencia en el laboratorio</strong>
</div>
