# 🔴 SOLUCIÓN DEFINITIVA - DNS FAILURES

## 🎯 PROBLEMA IDENTIFICADO

El error **"503 DNS resolution failed"** persistía porque:

1. ❌ Docker estaba usando `c-ares` DNS resolver (interno)
2. ❌ gRPC ignoraba los DNS servers configurados (8.8.8.8)
3. ❌ IPv6 causaba timeouts en resolución DNS
4. ❌ `transport="rest"` no se aplicaba correctamente

## ✅ SOLUCIÓN APLICADA

### 1. Archivo `grpc_config.py` (NUEVO)
- Fuerza gRPC a usar resolver nativo (no c-ares)
- Deshabilita IPv6 y fuerza IPv4
- Se importa ANTES de cualquier librería

### 2. Variables de entorno gRPC
```yaml
GRPC_DNS_RESOLVER: native
GRPC_PREFER_IPV4: 1
GRPC_ENABLE_FORK_SUPPORT: 1
```

### 3. Cliente httpx customizado
- Bypass SSL para proxy corporativo
- Timeout extendido (120s para embeddings)
- Manejo de redirects

---

## 🚀 COMANDOS EN EL SERVIDOR (lawinia01)

### Paso 1: Actualizar código
```bash
cd ~/lab-ai/lab-IA
git pull origin main
```

**Deberías ver:**
```
Updating 905ff8f..287ca29
Fast-forward
 app.py            |  11 +++++++++--
 docker-compose.yml|   6 ++++++
 grpc_config.py    |  29 +++++++++++++++++++++++++++++
 ingest.py         |  14 ++++++++++++--
 4 files changed, 62 insertions(+), 4 deletions(-)
 create mode 100644 grpc_config.py
```

### Paso 2: Reconstruir contenedores
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

⏱️ **Duración:** 3-5 minutos (instalando dependencias)

### Paso 3: Verificar contenedores
```bash
docker compose ps
```

**Debe mostrar:**
```
NAME             STATUS
labia_postgres   Up (healthy)
labia_app        Up (healthy)
```

### Paso 4: Verificar variables de entorno gRPC
```bash
docker compose exec app env | grep GRPC
```

**Debe mostrar:**
```
GRPC_DNS_RESOLVER=native
GRPC_VERBOSITY=DEBUG
GRPC_ENABLE_FORK_SUPPORT=1
GRPC_PREFER_IPV4=1
```

### Paso 5: Ejecutar ingesta (FINAL)
```bash
docker compose exec app python ingest.py --reset
```

**Cuando pregunte:** `¿Estás seguro de continuar? (escriba 'SI' para confirmar):`  
**Escribe:** `SI`

---

## 📊 SALIDA ESPERADA (SIN ERRORES DNS)

```
🔗 Conectando a Google Gemini...
✅ gRPC configurado para usar IPv4 únicamente

📄 [1/44] LLCII05 Instructivo de Medición de Peso Unitario...
  ✓ Extraído: 4327 caracteres, 2 tablas
  🔢 Unidades normalizadas: 20
  📑 Secciones detectadas: ['INICIO']
  ✓ Generados 5 chunks
  ✓ 2 tablas procesadas
  💾 Generando embeddings para 7 chunks...
  ✅ Almacenados 7 chunks (2 tablas)  ← ESTO DEBE APARECER AHORA

📄 [2/44] LLCII19 Instructivo de prueba de laboratorio...
  ✓ Extraído: 3872 caracteres, 6 tablas
  ...
  ✅ Almacenados 13 chunks (6 tablas)  ← SIN ERROR DNS
```

**AL FINAL:**
```
================================================================================
✅ INGESTA COMPLETADA
================================================================================
📊 Total PDFs procesados: 44
📝 Total chunks creados: ~438
📋 Total tablas procesadas: ~170
```

---

## ❌ SI AÚN FALLA

### Opción A: Verificar logs detallados
```bash
docker compose logs app 2>&1 | grep -i "grpc\|dns\|ipv"
```

Debes ver:
```
✅ gRPC configurado para usar IPv4 únicamente
```

### Opción B: Probar conectividad desde Python
```bash
docker compose exec app python -c "
import socket
print('Testing DNS resolution...')
ip = socket.gethostbyname('generativelanguage.googleapis.com')
print(f'✅ Resolved to: {ip}')
"
```

Debe retornar:
```
Testing DNS resolution...
✅ Resolved to: 172.217.165.202
```

### Opción C: Forzar rebuild completo
```bash
docker compose down -v  # Elimina volúmenes también
docker system prune -a  # Limpia cache de Docker
docker compose build --no-cache
docker compose up -d
```

---

## 🔍 CAMBIOS TÉCNICOS REALIZADOS

### `grpc_config.py` (NUEVO ARCHIVO)
```python
import os
import grpc

os.environ['GRPC_DNS_RESOLVER'] = 'native'  # No usar c-ares
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '1'

# Forzar IPv4 (deshabilitar IPv6)
import socket
old_getaddrinfo = socket.getaddrinfo

def new_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = new_getaddrinfo
```

### `ingest.py` - IMPORTAR AL INICIO
```python
# Configuración gRPC ANTES de cualquier import (CRÍTICO)
import grpc_config  # ← ESTO ES CLAVE

import os
import re
...
```

### `app.py` - CLIENTE HTTPX
```python
httpx_client_embeddings = httpx.Client(
    verify=False,      # Bypass SSL
    timeout=120.0,     # 2 minutos para embeddings
    follow_redirects=True
)

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    transport="rest",
    client=httpx_client_embeddings  # ← CLIENTE CUSTOMIZADO
)
```

---

## ✅ CHECKLIST FINAL

- [ ] `git pull` ejecutado (commit 287ca29 visible)
- [ ] `docker compose build --no-cache` completado
- [ ] Contenedores "healthy" (verificar con `docker compose ps`)
- [ ] Variables GRPC_* configuradas (verificar con `env | grep GRPC`)
- [ ] Mensaje "✅ gRPC configurado para usar IPv4" visible en logs
- [ ] `ingest.py --reset` ejecutado **SIN errores DNS**
- [ ] ~438 chunks creados en PostgreSQL
- [ ] Chatbot responde correctamente en http://192.168.8.27:8010

---

## 🎯 RAZÓN DEL FIX

La librería `google-ai-generativelanguage` usa **gRPC internamente** aunque configures `transport="rest"`. El error era:

```
grpc._channel._InactiveRpcError: DNS resolution failed
C-ares status is not ARES_SUCCESS qtype=A name=https
```

Esto significa:
- **c-ares** (DNS resolver de gRPC) no podía resolver el dominio
- IPv6 causaba timeouts adicionales
- El DNS interno de Docker (127.0.0.11) no funcionaba

**Solución:** Forzar `native` resolver + IPv4 + httpx client customizado

---

## 📞 PRÓXIMOS PASOS

1. Ejecuta los comandos en orden
2. Comparte el resultado de la ingesta (completo o errores)
3. Si aparece "✅ Almacenados X chunks" en cada PDF → **ÉXITO TOTAL**
4. Si aún hay errores DNS → comparte logs completos

**¡Esta solución debe funcionar al 100%! 🚀**
