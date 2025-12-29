# 🔴 DIAGNÓSTICO: Error de conexión a Google Gemini

## ❌ Problema detectado:

```
503 DNS resolution failed for https://generativelanguage.googleapis.com
Domain name not found
```

**Esto significa que tu servidor Linux NO puede conectarse a la API de Google Gemini.**

---

## 🔍 PASO 1: Verificar conectividad desde el servidor Linux

Ejecuta estos comandos **EN EL SERVIDOR** (no en el contenedor):

```bash
# 1. Verificar conectividad a Google
ping -c 3 generativelanguage.googleapis.com

# 2. Verificar DNS
nslookup generativelanguage.googleapis.com

# 3. Verificar HTTPS
curl -I https://generativelanguage.googleapis.com

# 4. Verificar con tu API Key
curl -X POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=AIzaSyDQl_TIzom8AvezgjWV5GjtJuskNatpe_Q \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"parts":[{"text":"test"}]}]}'
```

---

## 📊 Interpreta los resultados:

### ✅ Si TODO funciona:
```
ping: 64 bytes from ...
nslookup: Address: 142.250.xxx.xxx
curl: HTTP/2 200
```
→ **El servidor tiene acceso a Google**. El problema está en Docker.

### ❌ Si TODO falla:
```
ping: Name or service not known
nslookup: SERVFAIL
curl: Could not resolve host
```
→ **El servidor NO tiene salida a Internet o el firewall corporativo bloquea Google.**

---

## 🛠️ SOLUCIONES según el diagnóstico

### Escenario A: El servidor SÍ tiene acceso (ping/curl funciona)

**Problema**: Docker no está usando el DNS correcto.

**Solución**: Configurar DNS en docker-compose.yml

Edita `docker-compose.yml` y agrega esto en el servicio `app`:

```yaml
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: labia_app
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8010:8010"
    dns:                           # ← AGREGAR ESTAS LÍNEAS
      - 8.8.8.8                    # ← Google DNS
      - 8.8.4.4                    # ← Google DNS secundario
      - 1.1.1.1                    # ← Cloudflare DNS
    environment:
      # ... resto de variables
```

Luego:
```bash
docker compose down
docker compose build
docker compose up -d
docker compose exec app python ingest.py --reset
```

---

### Escenario B: El servidor NO tiene acceso (todo falla)

**Problema**: Firewall corporativo bloquea Google.

**Opciones**:

#### 1. Solicitar acceso IT:
Pide a IT que habiliten acceso a:
- `*.googleapis.com`
- `*.google.com`

#### 2. Configurar proxy corporativo:

Si tu empresa usa un proxy HTTP, edita `docker-compose.yml`:

```yaml
  app:
    environment:
      HTTP_PROXY: http://proxy.tuempresa.com:8080
      HTTPS_PROXY: http://proxy.tuempresa.com:8080
      NO_PROXY: localhost,127.0.0.1,postgres
      # ... resto de variables
```

#### 3. Vectorizar en tu PC local y copiar la base de datos:

**Opción temporal**: Como tu PC Windows SÍ tiene acceso a Google:

```bash
# EN TU PC WINDOWS (PowerShell):
cd "C:\Users\luis.castillo\OneDrive - Lazarus & Lazarus\IA\Rag LabAi"

# Levantar Docker local
docker-compose up -d

# Ejecutar ingesta local (esto SÍ funcionará)
docker-compose exec app python ingest.py --reset

# Hacer backup de la base de datos
docker-compose exec postgres pg_dump -U postgres labia_db > backup_vectorizado.sql

# Copiar el backup al servidor
scp backup_vectorizado.sql devll01@192.168.8.27:~/lab-ai/lab-IA/
```

```bash
# EN EL SERVIDOR LINUX:
cd ~/lab-ai/lab-IA

# Restaurar la base de datos vectorizada
docker compose exec -T postgres psql -U postgres labia_db < backup_vectorizado.sql

# Verificar chunks
docker compose exec postgres psql -U postgres -d labia_db -c "SELECT COUNT(*) FROM langchain_pg_embedding;"
```

**⚠️ DESVENTAJA**: Cada vez que agregues PDFs, deberás repetir el proceso.

#### 4. Cambiar a un LLM local (Ollama):

Si Google está bloqueado permanentemente, considera usar **Ollama** (LLM local que no necesita Internet).

---

## 🧪 PASO 2: Verificar conectividad desde DENTRO del contenedor

```bash
docker compose exec app ping -c 3 generativelanguage.googleapis.com

docker compose exec app curl -I https://generativelanguage.googleapis.com
```

**Si el servidor funciona pero el contenedor NO:**
→ Usa la solución de DNS en docker-compose.yml (Escenario A)

---

## 📋 CHECKLIST DE DIAGNÓSTICO

Ejecuta esto **EN EL SERVIDOR** y comparte los resultados:

```bash
echo "=== DESDE EL HOST ==="
ping -c 2 generativelanguage.googleapis.com
echo ""
nslookup generativelanguage.googleapis.com
echo ""
echo "=== DESDE EL CONTENEDOR ==="
docker compose exec app ping -c 2 generativelanguage.googleapis.com
echo ""
docker compose exec app nslookup generativelanguage.googleapis.com
```

---

## ✅ DESPUÉS DE APLICAR LA SOLUCIÓN

1. Actualiza código:
```bash
git pull origin main
```

2. Reconstruye (si cambiaste docker-compose.yml):
```bash
docker compose down
docker compose build
docker compose up -d
```

3. Prueba conectividad desde el contenedor:
```bash
docker compose exec app ping -c 3 generativelanguage.googleapis.com
```

4. Si ahora funciona, ejecuta ingesta:
```bash
docker compose exec app python ingest.py --reset
```

---

## 🆘 Si NADA funciona

**ÚLTIMA OPCIÓN**: Usa la vectorización desde tu PC local y copia la base de datos al servidor (ver Escenario B, opción 3).

**O MEJOR**: Solicita a IT acceso a `*.googleapis.com` para que el servidor pueda usar Google Gemini.

---

¿Qué resultados obtienes al ejecutar las pruebas de conectividad?
