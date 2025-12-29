-- ================================================================================================
-- CONSULTAS BASE DE DATOS - LAB-AI
-- Script para consultar las diferentes tablas del sistema
-- ================================================================================================

-- CONEXIÓN A LA BASE DE DATOS:
-- psql -h localhost -p 5432 -U postgres -d labia_db
-- Password: admin171419860

-- ================================================================================================
-- 1. VECTORIZACIÓN - Embeddings de documentos
-- ================================================================================================

-- Ver todas las colecciones de vectores
SELECT * FROM langchain_pg_collection;

-- Contar documentos vectorizados en la colección 'labia_embeddings'
SELECT COUNT(*) AS total_documentos
FROM langchain_pg_embedding e
INNER JOIN langchain_pg_collection c ON e.collection_id = c.uuid
WHERE c.name = 'labia_embeddings';

-- Ver algunos documentos vectorizados (con metadata)
SELECT 
    e.id,
    e.document AS contenido,
    e.cmetadata AS metadatos,
    c.name AS coleccion
FROM langchain_pg_embedding e
INNER JOIN langchain_pg_collection c ON e.collection_id = c.uuid
WHERE c.name = 'labia_embeddings'
LIMIT 10;

-- Ver documentos por código de instructivo
SELECT 
    e.document,
    e.cmetadata->>'codigo_documento' AS codigo,
    e.cmetadata->>'seccion' AS seccion,
    e.cmetadata->>'tipo_contenido' AS tipo
FROM langchain_pg_embedding e
INNER JOIN langchain_pg_collection c ON e.collection_id = c.uuid
WHERE c.name = 'labia_embeddings'
  AND e.cmetadata->>'codigo_documento' LIKE 'LLCCI%'
LIMIT 20;

-- ================================================================================================
-- 2. REGISTRO DE PREGUNTAS Y RESPUESTAS - Chat Logs
-- ================================================================================================

-- Ver últimas 10 conversaciones
SELECT 
    id,
    session_id,
    timestamp,
    user_query AS pregunta,
    bot_response AS respuesta,
    tokens_in,
    tokens_out,
    cost_usd AS costo,
    latency AS latencia_seg,
    vote AS voto
FROM chat_logs
ORDER BY timestamp DESC
LIMIT 10;

-- Estadísticas de uso
SELECT 
    COUNT(*) AS total_consultas,
    SUM(tokens_in) AS total_tokens_entrada,
    SUM(tokens_out) AS total_tokens_salida,
    SUM(cost_usd) AS costo_total_usd,
    AVG(latency) AS latencia_promedio_seg,
    COUNT(CASE WHEN vote = 'up' THEN 1 END) AS votos_positivos,
    COUNT(CASE WHEN vote = 'down' THEN 1 END) AS votos_negativos
FROM chat_logs;

-- Consultas más frecuentes (palabras clave)
SELECT 
    user_query,
    COUNT(*) AS veces_preguntada
FROM chat_logs
WHERE user_query IS NOT NULL
GROUP BY user_query
ORDER BY veces_preguntada DESC
LIMIT 20;

-- Consultas por sesión
SELECT 
    session_id,
    COUNT(*) AS numero_preguntas,
    MIN(timestamp) AS inicio_sesion,
    MAX(timestamp) AS fin_sesion
FROM chat_logs
GROUP BY session_id
ORDER BY numero_preguntas DESC
LIMIT 10;

-- ================================================================================================
-- 3. VOTOS - Thumbs Up y Thumbs Down
-- ================================================================================================

-- Ver todos los votos
SELECT 
    id,
    session_id,
    timestamp,
    user_query AS pregunta,
    vote AS voto
FROM chat_logs
WHERE vote IS NOT NULL
ORDER BY timestamp DESC;

-- Conteo de votos por tipo
SELECT 
    vote AS tipo_voto,
    COUNT(*) AS cantidad
FROM chat_logs
WHERE vote IS NOT NULL
GROUP BY vote;

-- Satisfacción general (%)
SELECT 
    ROUND(
        (COUNT(CASE WHEN vote = 'up' THEN 1 END)::DECIMAL / 
        NULLIF(COUNT(CASE WHEN vote IN ('up', 'down') THEN 1 END), 0) * 100), 
        2
    ) AS satisfaccion_porcentaje
FROM chat_logs;

-- Respuestas con votos negativos (para revisar)
SELECT 
    id,
    timestamp,
    user_query AS pregunta,
    bot_response AS respuesta,
    vote
FROM chat_logs
WHERE vote = 'down'
ORDER BY timestamp DESC;

-- ================================================================================================
-- 4. FEEDBACK NEGATIVO - Comentarios de usuarios
-- ================================================================================================

-- Ver todos los feedbacks negativos
SELECT 
    f.id,
    f.timestamp,
    f.comment AS comentario,
    f.source AS fuente,
    l.user_query AS pregunta_original,
    l.bot_response AS respuesta_original
FROM negative_feedbacks f
LEFT JOIN chat_logs l ON f.chat_log_id = l.id
ORDER BY f.timestamp DESC;

-- Contar feedbacks por tipo de problema (si se categorizan)
SELECT 
    comment,
    COUNT(*) AS veces_reportado
FROM negative_feedbacks
GROUP BY comment
ORDER BY veces_reportado DESC;

-- ================================================================================================
-- 5. HISTORIAL CONVERSACIONAL - Estado de sesiones
-- ================================================================================================

-- Ver todas las sesiones activas
SELECT 
    session_id,
    user_id,
    conversation_history,
    last_interaction,
    created_at
FROM chat_session_state
ORDER BY last_interaction DESC;

-- Ver historial de una sesión específica
SELECT 
    session_id,
    conversation_history,
    jsonb_array_length(conversation_history) AS num_interacciones
FROM chat_session_state
WHERE session_id = 'TU_SESSION_ID_AQUI';

-- Sesiones más activas
SELECT 
    session_id,
    jsonb_array_length(conversation_history) AS num_interacciones,
    last_interaction
FROM chat_session_state
ORDER BY num_interacciones DESC
LIMIT 10;

-- ================================================================================================
-- 6. MÉTRICAS GENERALES DEL SISTEMA
-- ================================================================================================

-- Dashboard completo
SELECT 
    -- Documentos
    (SELECT COUNT(*) FROM langchain_pg_embedding e
     INNER JOIN langchain_pg_collection c ON e.collection_id = c.uuid
     WHERE c.name = 'labia_embeddings') AS total_documentos,
    
    -- Chats
    (SELECT COUNT(*) FROM chat_logs) AS total_consultas,
    
    -- Tokens
    (SELECT SUM(tokens_in) + SUM(tokens_out) FROM chat_logs) AS total_tokens,
    
    -- Costo
    (SELECT ROUND(SUM(cost_usd)::NUMERIC, 4) FROM chat_logs) AS costo_total_usd,
    
    -- Latencia promedio
    (SELECT ROUND(AVG(latency)::NUMERIC, 2) FROM chat_logs) AS latencia_promedio_seg,
    
    -- Votos positivos
    (SELECT COUNT(*) FROM chat_logs WHERE vote = 'up') AS votos_positivos,
    
    -- Votos negativos
    (SELECT COUNT(*) FROM chat_logs WHERE vote = 'down') AS votos_negativos,
    
    -- Feedbacks negativos
    (SELECT COUNT(*) FROM negative_feedbacks) AS feedbacks_negativos,
    
    -- Sesiones activas
    (SELECT COUNT(*) FROM chat_session_state) AS sesiones_totales;

-- ================================================================================================
-- 7. MANTENIMIENTO - Limpiar datos antiguos
-- ================================================================================================

-- Ver sesiones antiguas (más de 7 días sin actividad)
SELECT 
    session_id,
    last_interaction,
    NOW() - last_interaction AS tiempo_inactivo
FROM chat_session_state
WHERE last_interaction < NOW() - INTERVAL '7 days'
ORDER BY last_interaction;

-- BORRAR sesiones antiguas (CUIDADO: esto elimina datos permanentemente)
-- DELETE FROM chat_session_state
-- WHERE last_interaction < NOW() - INTERVAL '30 days';

-- BORRAR logs antiguos (más de 90 días)
-- DELETE FROM chat_logs
-- WHERE timestamp < NOW() - INTERVAL '90 days';

-- ================================================================================================
-- 8. BÚSQUEDAS AVANZADAS
-- ================================================================================================

-- Buscar en metadata de documentos
SELECT 
    e.document,
    e.cmetadata->>'codigo_documento' AS codigo,
    e.cmetadata->>'normas_astm' AS normas_astm
FROM langchain_pg_embedding e
INNER JOIN langchain_pg_collection c ON e.collection_id = c.uuid
WHERE c.name = 'labia_embeddings'
  AND e.cmetadata->>'normas_astm' LIKE '%C109%';

-- Consultas que mencionan términos específicos
SELECT 
    user_query,
    bot_response,
    timestamp
FROM chat_logs
WHERE user_query ILIKE '%ph%' OR user_query ILIKE '%cemento%'
ORDER BY timestamp DESC
LIMIT 10;

-- ================================================================================================
-- FIN DEL SCRIPT
-- ================================================================================================
