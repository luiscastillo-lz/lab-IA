# 🚀 GUÍA DE DEPLOYMENT - LAB-IA

## Despliegue en servidor con Docker

Esta guía describe el proceso completo para desplegar Lab-Ai en un servidor usando Docker y GitHub.

---

## 📋 **Pre-requisitos en el servidor**

### 1. **Sistema operativo**
- Ubuntu 20.04 LTS o superior
- Debian 11 o superior
- CentOS 8 / Rocky Linux 8 o superior

### 2. **Software necesario**
```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo apt install docker-compose-plugin -y

# Instalar Git
sudo apt install git -y

# Verificar instalaciones
docker --version
docker-compose --version
git --version
```

### 3. **Recursos mínimos**
- **RAM**: 2GB (recomendado 4GB)
- **Almacenamiento**: 10GB libres
- **Puertos**: 8010 (app), 5433 (PostgreSQL externo)

---

## 🔧 **Proceso de deployment**

### **PASO 1: Clonar repositorio**

```bash
# Crear directorio de aplicaciones
mkdir -p ~/apps
cd ~/apps

# Clonar repositorio
git clone https://github.com/luiscastillo-lz/lab-IA.git
cd lab-IA
```

### **PASO 2: Crear carpeta de PDFs**

```bash
# Crear carpeta raw
mkdir -p raw

# Subir los 44 PDFs al servidor
# Opción A: Usar SCP desde tu máquina local
# scp -r /ruta/local/raw/*.pdf usuario@servidor:~/apps/lab-IA/raw/

# Opción B: Usar SFTP o WinSCP (Windows)

# Verificar que los PDFs estén copiados
ls -lh raw/
```

### **PASO 3: Configurar variables de entorno**

```bash
# Copiar template
cp .env.example .env

# Editar con tu API key
nano .env
```

**Configuración mínima necesaria en `.env`:**
```env
# REQUERIDO: Tu API key de Google Gemini
GOOGLE_API_KEY=AIzaSy...tu_key_real_aqui

# RECOMENDADO: Cambiar password de PostgreSQL
POSTGRES_PASSWORD=tu_password_seguro_aqui

# Opcional: Ajustar otros parámetros
LLM_MAX_TOKENS=4096
DEBUG=False
```

**Guardar y salir** (Ctrl+X, luego Y, luego Enter en nano)

### **PASO 4: Construir y levantar servicios**

```bash
# Opción A: Usar el script automatizado (RECOMENDADO)
chmod +x deploy.sh
./deploy.sh

# Opción B: Manual
docker-compose build --no-cache
docker-compose up -d
```

### **PASO 5: Verificar servicios**

```bash
# Ver estado de contenedores
docker-compose ps

# Deberías ver:
# labia_app       running   0.0.0.0:8010->8010/tcp
# labia_postgres  running   5432/tcp
```

### **PASO 6: Ingestar PDFs (primera vez)**

```bash
# Ejecutar ingesta
docker-compose exec app python ingest.py --reset

# Esto tomará 2-5 minutos para 44 PDFs
# Deberías ver:
# ✅ Total PDFs procesados: 44
# 📝 Total chunks creados: ~438
# 📋 Total tablas procesadas: ~170
```

### **PASO 7: Verificar aplicación**

```bash
# Verificar que responde
curl http://localhost:8010/

# Debería retornar HTML de la página principal
```

### **PASO 8: Acceder desde navegador**

**Servidor de producción:** `http://192.168.8.27:8010`

Si el servidor tiene IP pública o acceso local: `http://<IP_SERVIDOR>:8010`

Si usas túnel SSH (desarrollo): 
```bash
# Desde tu máquina local
ssh -L 8010:localhost:8010 usuario@servidor
# Luego acceder a: http://localhost:8010
```

---

## 📊 **Comandos de mantenimiento**

### **Ver logs**
```bash
# Logs de la aplicación
docker-compose logs -f app

# Logs de PostgreSQL
docker-compose logs -f postgres

# Últimas 100 líneas
docker-compose logs --tail=100 app
```

### **Reiniciar servicios**
```bash
# Reiniciar todo
docker-compose restart

# Reiniciar solo la app
docker-compose restart app
```

### **Actualizar código desde GitHub**
```bash
# Detener servicios
docker-compose down

# Actualizar código
git pull origin main

# Reconstruir y levantar
docker-compose up --build -d

# Re-ingestar si hay cambios en PDFs
docker-compose exec app python ingest.py --reset
```

### **Backup de base de datos**
```bash
# Crear backup
docker-compose exec postgres pg_dump -U postgres labia_db > backup_$(date +%Y%m%d).sql

# Restaurar backup
docker-compose exec -T postgres psql -U postgres labia_db < backup_20250129.sql
```

### **Ver consumo de recursos**
```bash
# Estadísticas de contenedores
docker stats
```

### **Limpiar datos (⚠️ CUIDADO)**
```bash
# Detener y eliminar volúmenes (borra base de datos)
docker-compose down -v

# Eliminar imágenes no usadas
docker system prune -a
```

---

## 🔒 **Seguridad (Producción)**

### **1. Configurar firewall**
```bash
# Permitir solo puertos necesarios
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8010/tcp  # Lab-Ai
sudo ufw enable
sudo ufw status
```

### **2. Usar HTTPS con Nginx reverse proxy**
```bash
# Instalar Nginx
sudo apt install nginx certbot python3-certbot-nginx -y

# Configurar proxy reverso
sudo nano /etc/nginx/sites-available/labia
```

**Contenido de `/etc/nginx/sites-available/labia`:**
```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    location / {
        proxy_pass http://localhost:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Activar sitio
sudo ln -s /etc/nginx/sites-available/labia /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Obtener certificado SSL
sudo certbot --nginx -d tu-dominio.com
```

### **3. Limitar exposición de PostgreSQL**
```bash
# Editar docker-compose.yml para NO exponer puerto 5433
# Cambiar:
#   ports:
#     - "5433:5432"
# Por:
#   expose:
#     - "5432"
```

---

## 🐛 **Troubleshooting**

### **Error: "Cannot connect to PostgreSQL"**
```bash
# Verificar que PostgreSQL esté saludable
docker-compose exec postgres pg_isready -U postgres

# Si no responde, reiniciar
docker-compose restart postgres
sleep 10
docker-compose restart app
```

### **Error: "No such file or directory: raw/"**
```bash
# Crear carpeta y copiar PDFs
mkdir -p raw
# Luego copiar los PDFs al directorio
```

### **Error: "API key not found"**
```bash
# Verificar que .env tenga la API key
grep GOOGLE_API_KEY .env

# Si está vacía, editarla
nano .env
# Guardar y reiniciar
docker-compose restart app
```

### **La app no responde en puerto 8010**
```bash
# Verificar que el puerto esté escuchando
netstat -tulpn | grep 8010

# Verificar logs
docker-compose logs --tail=50 app

# Verificar firewall
sudo ufw status
```

---

## 📈 **Monitoreo**

### **Health checks**
```bash
# Verificar salud de contenedores
docker-compose ps

# Verificar endpoint de la app
curl -f http://localhost:8010/ || echo "App no responde"

# Verificar PostgreSQL
docker-compose exec postgres pg_isready -U postgres -d labia_db
```

### **Automatizar con cron**
```bash
# Editar crontab
crontab -e

# Agregar verificación cada 5 minutos
*/5 * * * * cd ~/apps/lab-IA && docker-compose ps | grep -q "running" || docker-compose up -d
```

---

## 🔄 **Actualización de versión**

```bash
# 1. Hacer backup
docker-compose exec postgres pg_dump -U postgres labia_db > backup_pre_update.sql

# 2. Detener servicios
docker-compose down

# 3. Actualizar código
git pull origin main

# 4. Reconstruir imágenes
docker-compose build --no-cache

# 5. Levantar servicios
docker-compose up -d

# 6. Verificar
docker-compose logs -f app
```

---

## 📞 **Soporte**

Si encuentras problemas:

1. Revisar logs: `docker-compose logs -f app`
2. Verificar configuración: `cat .env`
3. Verificar conectividad: `docker-compose ps`
4. Consultar documentación: [README.md](README.md)

---

**Desarrollado por**: Luis Castillo - Lazarus & Lazarus  
**Repositorio**: https://github.com/luiscastillo-lz/lab-IA
