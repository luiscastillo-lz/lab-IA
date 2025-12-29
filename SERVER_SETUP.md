# 🚀 GUÍA RÁPIDA - DEPLOYMENT EN SERVIDOR 192.168.8.27

## Comandos para ejecutar en el servidor Linux

### 1️⃣ Clonar repositorio
```bash
cd ~
git clone https://github.com/luiscastillo-lz/lab-IA.git
cd lab-IA
```

### 2️⃣ Crear carpeta raw y copiar PDFs
```bash
mkdir -p raw
```

**Desde tu PC Windows**, copiar los 44 PDFs al servidor:
```powershell
# Ejecutar en tu PC (PowerShell)
scp -r "C:\Users\luis.castillo\OneDrive - Lazarus & Lazarus\IA\Rag LabAi\raw\*.pdf" usuario@192.168.8.27:~/lab-IA/raw/
```

### 3️⃣ Configurar variables de entorno
```bash
cp .env.example .env
nano .env
```

**Editar estas líneas:**
```env
GOOGLE_API_KEY=AIzaSyDQl_TIzom8AvezgjWV5GjtJuskNatpe_Q
POSTGRES_PASSWORD=TU_PASSWORD_SEGURO_AQUI
```

Guardar: `Ctrl+X`, luego `Y`, luego `Enter`

### 4️⃣ Ejecutar deployment automático
```bash
chmod +x deploy.sh
./deploy.sh
```

El script preguntará si deseas ejecutar la ingesta. **Responde: yes**

### 5️⃣ Verificar servicios
```bash
docker-compose ps
```

Deberías ver:
```
NAME             STATUS         PORTS
labia_app        Up (healthy)   0.0.0.0:8010->8010/tcp
labia_postgres   Up (healthy)   0.0.0.0:5433->5432/tcp
```

### 6️⃣ Acceder a la aplicación

**Desde cualquier PC en la red:**
```
http://192.168.8.27:8010
```

---

## 🔍 Comandos útiles

### Ver logs en tiempo real
```bash
docker-compose logs -f app
```

### Reiniciar servicios
```bash
docker-compose restart
```

### Detener servicios
```bash
docker-compose down
```

### Actualizar código desde GitHub
```bash
git pull origin main
docker-compose up --build -d
```

### Re-ingestar PDFs (si se agregan nuevos)
```bash
docker-compose exec app python ingest.py --reset
```

### Acceder a PostgreSQL
```bash
docker-compose exec postgres psql -U postgres -d labia_db
```

Queries útiles:
```sql
-- Ver cantidad de chunks
SELECT COUNT(*) FROM langchain_pg_embedding;

-- Ver últimas consultas
SELECT query, response, created_at 
FROM chat_logs 
ORDER BY created_at DESC 
LIMIT 10;
```

---

## ⚠️ Troubleshooting

### Error: Puerto 5432 en uso
Ya está resuelto, usamos **5433** para PostgreSQL.

### Error: No module named 'flask_cors'
Ya está en requirements.txt, reconstruir:
```bash
docker-compose up --build -d
```

### La app no responde
```bash
# Verificar logs
docker-compose logs --tail=100 app

# Reiniciar
docker-compose restart app
```

### Firewall bloqueando puerto 8010
```bash
sudo ufw allow 8010/tcp
sudo ufw reload
```

---

## 📊 Validación final

**1. Verificar healthchecks:**
```bash
docker-compose ps
# Ambos deben mostrar "healthy"
```

**2. Verificar ingesta:**
```bash
docker-compose exec postgres psql -U postgres -d labia_db -c "SELECT COUNT(*) FROM langchain_pg_embedding;"
# Debe retornar: ~438 chunks
```

**3. Probar API:**
```bash
curl -X POST http://localhost:8010/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Cómo se calibra el pH metro?", "session_id": "test-001"}'
```

**4. Probar desde navegador:**
Abrir: `http://192.168.8.27:8010`

---

## 🎯 Configuración actual

- **Servidor**: 192.168.8.27
- **Puerto app**: 8010
- **Puerto PostgreSQL**: 5433 (externo), 5432 (interno contenedor)
- **Base de datos**: labia_db
- **PDFs**: 44 instructivos en carpeta `raw/`
- **Chunks esperados**: ~438
- **LLM**: Google Gemini 2.5 Flash
- **Max tokens**: 4096

---

✅ **Deployment completado exitosamente**
