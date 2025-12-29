# 📊 GUÍA DE BASE DE DATOS Y NUEVAS FUNCIONALIDADES - LAB-AI

## 🎯 Resumen de Mejoras Implementadas

### 1. **Ingesta Limpia con Flag `--reset`**
Ahora puedes hacer una ingesta completamente limpia borrando todos los documentos anteriores:

```powershell
# Ingesta limpia (borra todo y vuelve a procesar)
python ingest.py --reset

# Se te pedirá confirmar escribiendo 'SI'
```

**Uso normal:**
```powershell
# Ingestar todos los PDFs en raw/
python ingest.py

# Modo prueba con archivos específicos
python ingest.py --test --files "LLCCI05*.pdf,LLCCI13*.pdf"

# Ingesta limpia en modo prueba
python ingest.py --test --files "*.pdf" --reset
```

---

## 📍 Ubicación de la Base de Datos

### **Conexión PostgreSQL**
- **Host:** localhost
- **Puerto:** 5432
- **Base de datos:** labia_db
- **Usuario:** postgres
- **Contraseña:** admin171419860

### **Conectar desde terminal:**
```powershell
psql -h localhost -p 5432 -U postgres -d labia_db
```

### **Conectar con herramientas gráficas:**
- **pgAdmin:** https://www.pgadmin.org/
- **DBeaver:** https://dbeaver.io/
- **TablePlus:** https://tableplus.com/

---

## 🗄️ Tablas de la Base de Datos

### **1. Vectorización de Documentos**

#### `langchain_pg_collection`
Contiene las colecciones de vectores.

```sql
SELECT * FROM langchain_pg_collection;
```

#### `langchain_pg_embedding`
Almacena los documentos vectorizados (chunks + embeddings).

```sql
-- Ver total de documentos
SELECT COUNT(*) 
FROM langchain_pg_embedding e
INNER JOIN langchain_pg_collection c ON e.collection_id = c.uuid
WHERE c.name = 'labia_embeddings';

-- Ver algunos documentos
SELECT 
    e.document AS contenido,
    e.cmetadata->>'codigo_documento' AS codigo,
    e.cmetadata->>'seccion' AS seccion
FROM langchain_pg_embedding e
INNER JOIN langchain_pg_collection c ON e.collection_id = c.uuid
WHERE c.name = 'labia_embeddings'
LIMIT 10;
```

**Campos importantes:**
- `document`: Contenido del chunk
- `cmetadata`: Metadatos (código, normas ASTM, sección, etc.)
- `embedding`: Vector de embeddings (768 dimensiones)

---

### **2. Registro de Preguntas y Respuestas**

#### `chat_logs`
Almacena todas las interacciones del chat.

```sql
-- Ver últimas conversaciones
SELECT 
    id,
    session_id,
    timestamp,
    user_query AS pregunta,
    bot_response AS respuesta,
    tokens_in,
    tokens_out,
    cost_usd,
    latency,
    vote
FROM chat_logs
ORDER BY timestamp DESC
LIMIT 10;
```

**Campos importantes:**
- `user_query`: Pregunta del usuario
- `bot_response`: Respuesta del asistente
- `context_docs`: Documentos usados como contexto (JSONB)
- `tokens_in` / `tokens_out`: Tokens consumidos
- `cost_usd`: Costo en dólares (Google Gemini)
- `latency`: Tiempo de respuesta en segundos
- `vote`: Voto del usuario ('up' o 'down')

---

### **3. Votos (Thumbs Up / Thumbs Down)**

Los votos se almacenan en el campo `vote` de `chat_logs`.

```sql
-- Ver todos los votos
SELECT 
    id,
    user_query,
    vote,
    timestamp
FROM chat_logs
WHERE vote IS NOT NULL
ORDER BY timestamp DESC;

-- Estadísticas de votos
SELECT 
    vote,
    COUNT(*) AS cantidad
FROM chat_logs
WHERE vote IS NOT NULL
GROUP BY vote;

-- Satisfacción (%)
SELECT 
    ROUND(
        COUNT(CASE WHEN vote = 'up' THEN 1 END)::DECIMAL / 
        NULLIF(COUNT(*), 0) * 100, 
        2
    ) AS satisfaccion_porcentaje
FROM chat_logs
WHERE vote IS NOT NULL;
```

---

### **4. Feedback Negativo**

#### `negative_feedbacks`
Almacena comentarios de usuarios cuando votan negativamente.

```sql
-- Ver feedbacks negativos
SELECT 
    f.id,
    f.timestamp,
    f.comment AS comentario,
    l.user_query AS pregunta,
    l.bot_response AS respuesta
FROM negative_feedbacks f
LEFT JOIN chat_logs l ON f.chat_log_id = l.id
ORDER BY f.timestamp DESC;
```

**Campos importantes:**
- `chat_log_id`: ID del chat asociado
- `comment`: Comentario del usuario sobre qué salió mal
- `source`: Fuente del feedback (Web, API, etc.)
- `response`: Respuesta que generó el feedback

---

### **5. Historial Conversacional**

#### `chat_session_state`
Mantiene el historial de las últimas 5 interacciones por sesión.

```sql
-- Ver sesiones activas
SELECT 
    session_id,
    conversation_history,
    last_interaction
FROM chat_session_state
ORDER BY last_interaction DESC;

-- Ver historial completo de una sesión
SELECT 
    session_id,
    jsonb_pretty(conversation_history) AS historial
FROM chat_session_state
WHERE session_id = 'TU_SESSION_ID';
```

**Campos importantes:**
- `session_id`: ID único de la sesión
- `conversation_history`: Array JSONB con últimas 5 interacciones
- `last_interaction`: Timestamp de última actividad

---

## 🔧 Nuevas Funcionalidades del Frontend

### **Botones de Feedback Mejorados**

#### **Thumbs Up (Útil)**
- Marca la respuesta como útil
- Se guarda en `chat_logs.vote = 'up'`
- Botones se deshabilitan después de votar

#### **Thumbs Down (No útil)**
- Marca la respuesta como no útil
- **NUEVO:** Abre un modal preguntando "¿Qué salió mal?"
- El usuario puede describir el problema
- Se guarda en `negative_feedbacks` con el comentario

#### **Copiar**
- Copia la respuesta al portapapeles
- Muestra confirmación visual

---

## 📊 Consultas Útiles

### **Dashboard de Métricas**

```sql
SELECT 
    (SELECT COUNT(*) FROM langchain_pg_embedding e
     INNER JOIN langchain_pg_collection c ON e.collection_id = c.uuid
     WHERE c.name = 'labia_embeddings') AS total_documentos,
    
    (SELECT COUNT(*) FROM chat_logs) AS total_consultas,
    
    (SELECT SUM(tokens_in) + SUM(tokens_out) FROM chat_logs) AS total_tokens,
    
    (SELECT ROUND(SUM(cost_usd)::NUMERIC, 4) FROM chat_logs) AS costo_total_usd,
    
    (SELECT ROUND(AVG(latency)::NUMERIC, 2) FROM chat_logs) AS latencia_promedio_seg,
    
    (SELECT COUNT(*) FROM chat_logs WHERE vote = 'up') AS votos_positivos,
    
    (SELECT COUNT(*) FROM chat_logs WHERE vote = 'down') AS votos_negativos,
    
    (SELECT COUNT(*) FROM negative_feedbacks) AS feedbacks_negativos;
```

### **Consultas más Frecuentes**

```sql
SELECT 
    user_query,
    COUNT(*) AS veces_preguntada
FROM chat_logs
WHERE user_query IS NOT NULL
GROUP BY user_query
ORDER BY veces_preguntada DESC
LIMIT 20;
```

### **Respuestas con Votos Negativos (Para Mejorar)**

```sql
SELECT 
    l.user_query AS pregunta,
    l.bot_response AS respuesta,
    f.comment AS problema_reportado
FROM chat_logs l
LEFT JOIN negative_feedbacks f ON l.id = f.chat_log_id
WHERE l.vote = 'down'
ORDER BY l.timestamp DESC;
```

---

## 🧹 Mantenimiento

### **Limpiar Base de Datos Antes de Ingesta**

**Opción 1: Usar el flag --reset (Recomendado)**
```powershell
python ingest.py --reset
```

**Opción 2: Desde PostgreSQL**
```sql
-- Borrar todos los embeddings
DELETE FROM langchain_pg_embedding 
WHERE collection_id = (
    SELECT uuid FROM langchain_pg_collection 
    WHERE name = 'labia_embeddings'
);
```

### **Limpiar Datos Antiguos**

```sql
-- Borrar sesiones inactivas (>30 días)
DELETE FROM chat_session_state
WHERE last_interaction < NOW() - INTERVAL '30 days';

-- Borrar logs antiguos (>90 días)
DELETE FROM chat_logs
WHERE timestamp < NOW() - INTERVAL '90 days';
```

---

## 🎨 Estilos del Modal de Feedback

El modal de feedback negativo tiene estilos personalizados en `style.css`:

- Fondo oscuro semitransparente
- Animación de entrada suave
- Campo de texto con enfoque visual
- Botones Cancel y Submit
- Mensaje de agradecimiento temporal

---

## 📝 Archivo de Consultas SQL

Revisa el archivo `consultas_db.sql` para un conjunto completo de consultas útiles organizadas por categoría.

---

## ✅ Checklist de Verificación

- [x] ¿La base de datos PostgreSQL está corriendo? → `docker ps` o `psql`
- [x] ¿Puedes conectarte? → `psql -h localhost -U postgres -d labia_db`
- [x] ¿Los PDFs están en `raw/`? → `ls raw/`
- [x] ¿El server Flask está corriendo? → `python app.py`
- [x] ¿Los botones de feedback funcionan? → Probar en navegador
- [x] ¿El modal aparece al votar negativo? → Probar thumbs down

---

## 🚀 Flujo de Trabajo Completo

### **1. Ingesta Limpia**
```powershell
# Borrar todo y reingestar
python ingest.py --reset
# Confirmar con 'SI'
```

### **2. Iniciar Servidor**
```powershell
python app.py
```

### **3. Probar en Navegador**
- Ir a http://localhost:8010
- Hacer preguntas
- Votar respuestas (thumbs up/down)
- Si votas down, llenar el modal de feedback

### **4. Revisar Métricas en BD**
```sql
psql -h localhost -U postgres -d labia_db

-- Dashboard
SELECT * FROM ... (ver consultas_db.sql)
```

---

## 📞 Soporte

Si algo no funciona:

1. Verificar logs del servidor: `python app.py` (buscar errores)
2. Verificar PostgreSQL: `docker logs labia_postgres`
3. Verificar red del navegador: F12 → Network → ver respuestas de API
4. Revisar consultas SQL en `consultas_db.sql`

---

**Última actualización:** 27 de diciembre de 2025
