# 🚀 INSTRUCCIONES FINALES - SERVIDOR 192.168.8.27

## ✅ Cambios aplicados en el código:

1. ✅ **docker-compose.yml**: Eliminada versión obsoleta
2. ✅ **script.js**: Auto-detección de URL del servidor
3. ✅ **app.py + ingest.py**: Bypass SSL para red corporativa
4. ✅ **Dockerfile**: Bypass SSL en pip install
5. ✅ **POSTGRES_HOST**: Configurado a `postgres` (nombre servicio Docker)
6. ✅ **Puerto PostgreSQL**: Cambiado a 5433

---

## 📋 COMANDOS PARA EL SERVIDOR LINUX

Copia y pega estos comandos **EN ORDEN**:

### 1️⃣ Ir al proyecto

```bash
cd ~/lab-ai/lab-IA
```

### 2️⃣ Actualizar código desde GitHub

```bash
git pull origin main
```

### 3️⃣ Verificar que el .env esté configurado

```bash
cat .env
```

**Debe contener:**
```env
GOOGLE_API_KEY=AIzaSyDQl_TIzom8AvezgjWV5GjtJuskNatpe_Q
POSTGRES_HOST=postgres
POSTGRES_PORT=5433
```

**Si no existe, créalo:**
```bash
cp .env.example .env
nano .env
# Pegar el GOOGLE_API_KEY correcto
# Guardar: Ctrl+X, luego Y, luego Enter
```

### 4️⃣ Detener contenedores viejos (si existen)

```bash
docker compose down
```

### 5️⃣ Construir las imágenes Docker

```bash
docker compose build
```

⏱️ **Esto tomará 2-4 minutos** (instalando dependencias con bypass SSL)

### 6️⃣ Levantar los servicios

```bash
docker compose up -d
```

### 7️⃣ Verificar que estén corriendo

```bash
docker compose ps
```

**Debes ver:**
```
NAME             STATUS         PORTS
labia_postgres   Up (healthy)   0.0.0.0:5433->5432/tcp
labia_app        Up (healthy)   0.0.0.0:8010->8010/tcp
```

**Si ves "Restarting" o errores:**
```bash
docker compose logs -f app
```

### 8️⃣ VECTORIZAR LA BASE DE DATOS (CRÍTICO)

⚠️ **ESTE PASO ES OBLIGATORIO - Sin esto el chatbot NO funcionará**

```bash
docker compose exec app python ingest.py --reset
```

**Cuando pregunte:** `¿Deseas eliminar la colección...?`
**Escribe:** `SI` (en mayúsculas)

⏱️ **Espera 2-5 minutos** mientras procesa los 44 PDFs

**Debes ver al final:**
```
✅ INGESTA COMPLETADA
📊 Total PDFs procesados: 44
📝 Total chunks creados: ~438
📋 Total tablas procesadas: ~170
```

### 9️⃣ Verificar chunks en la base de datos

```bash
docker compose exec postgres psql -U postgres -d labia_db -c "SELECT COUNT(*) FROM langchain_pg_embedding;"
```

**Debe retornar:**
```
 count 
-------
   438
(1 row)
```

### 🔟 Verificar logs de la aplicación

```bash
docker compose logs --tail=50 app
```

**Debes ver:**
```
🤖 LABIA - ASISTENTE VIRTUAL DE LABORATORIO
🌐 Servidor corriendo en: http://localhost:8010
```

---

## 🌐 ACCESO AL CHATBOT

### Desde cualquier navegador en la red:

```
http://192.168.8.27:8010
```

### Prueba con esta pregunta:

```
¿Cómo se calibra el pH metro?
```

**Debe responder** con procedimientos detallados de los instructivos.

---

## 🔧 SOLUCIÓN DE PROBLEMAS

### Error: "Container labia_app is unhealthy"

```bash
docker compose logs app
```

Busca errores de SSL o conexión a PostgreSQL.

### Error: "Failed to fetch" en el navegador

1. Verifica que la app esté corriendo:
   ```bash
   docker compose ps
   ```

2. Verifica que el puerto 8010 esté abierto:
   ```bash
   netstat -tulpn | grep 8010
   ```

3. Verifica firewall:
   ```bash
   sudo ufw allow 8010/tcp
   sudo ufw reload
   ```

### Error: "ModuleNotFoundError: No module named 'httpx'"

NO uses `python3 ingest.py` directamente.  
Siempre usa: `docker compose exec app python ingest.py --reset`

### La app responde pero dice "No encontré información"

Significa que NO corriste el paso 8 (vectorización).  
Ejecuta:
```bash
docker compose exec app python ingest.py --reset
```

### Reiniciar todo desde cero

```bash
docker compose down -v  # ⚠️ Borra la base de datos
docker compose build --no-cache
docker compose up -d
docker compose exec app python ingest.py --reset
```

---

## 📊 COMANDOS ÚTILES

### Ver logs en tiempo real
```bash
docker compose logs -f app
```

### Reiniciar servicios
```bash
docker compose restart
```

### Detener todo
```bash
docker compose down
```

### Ver uso de recursos
```bash
docker stats
```

### Acceder a PostgreSQL
```bash
docker compose exec postgres psql -U postgres -d labia_db
```

Queries útiles:
```sql
-- Ver chunks
SELECT COUNT(*) FROM langchain_pg_embedding;

-- Ver últimas consultas
SELECT query, response, created_at 
FROM chat_logs 
ORDER BY created_at DESC 
LIMIT 5;

-- Ver tablas
\dt
```

---

## ✅ CHECKLIST FINAL

- [ ] Código actualizado con `git pull`
- [ ] `.env` configurado con API key correcta
- [ ] Contenedores construidos con `docker compose build`
- [ ] Servicios corriendo con `docker compose up -d`
- [ ] Ambos contenedores "healthy" en `docker compose ps`
- [ ] Base de datos vectorizada con `ingest.py --reset`
- [ ] 438 chunks verificados en PostgreSQL
- [ ] App accesible en `http://192.168.8.27:8010`
- [ ] Chatbot responde correctamente a preguntas

---

## 🎯 ESTADO FINAL ESPERADO

```bash
docker compose ps
```

```
NAME             IMAGE              COMMAND              STATUS         PORTS
labia_postgres   pgvector/...       docker-entry...      Up (healthy)   0.0.0.0:5433->5432/tcp
labia_app        lab-ia-app         python app.py        Up (healthy)   0.0.0.0:8010->8010/tcp
```

```bash
docker compose exec postgres psql -U postgres -d labia_db -c "SELECT COUNT(*) FROM langchain_pg_embedding;"
```

```
 count 
-------
   438
```

```
Navegador: http://192.168.8.27:8010
Pregunta: ¿Cómo se calibra el pH metro?
Respuesta: [Procedimiento detallado del instructivo LLCCI13]
```

---

**🚀 ¡DEPLOYMENT COMPLETADO!**

Si tienes problemas, revisa los logs:
```bash
docker compose logs -f app
```
