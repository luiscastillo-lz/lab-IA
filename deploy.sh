#!/bin/bash

# ================================================================================================
# DEPLOYMENT SCRIPT - LAB-IA
# Script para deployment en servidor con Docker
# ================================================================================================

set -e  # Detener en caso de error

echo "================================================================================================"
echo "🚀 DEPLOYMENT LAB-IA - Asistente Virtual de Laboratorio"
echo "================================================================================================"

# ==================== 1. VERIFICAR DEPENDENCIAS ====================
echo ""
echo "📋 Verificando dependencias..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker no está instalado. Instalar con:"
    echo "   curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose no está instalado. Instalar con:"
    echo "   sudo apt-get install docker-compose-plugin"
    exit 1
fi

echo "✅ Docker instalado: $(docker --version)"
echo "✅ Docker Compose instalado: $(docker-compose --version)"

# ==================== 2. VERIFICAR ARCHIVO .env ====================
echo ""
echo "📄 Verificando configuración..."

if [ ! -f ".env" ]; then
    echo "⚠️  Archivo .env no encontrado. Creando desde .env.example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANTE: Editar .env y configurar:"
    echo "   - GOOGLE_API_KEY (requerido)"
    echo "   - POSTGRES_PASSWORD (recomendado cambiar)"
    echo ""
    read -p "Presiona Enter cuando hayas configurado .env..."
fi

# Verificar que la API key esté configurada
if grep -q "tu_api_key_aqui" .env; then
    echo "❌ ERROR: Debes configurar GOOGLE_API_KEY en .env"
    exit 1
fi

echo "✅ Archivo .env configurado"

# ==================== 3. CREAR CARPETA RAW ====================
echo ""
echo "📁 Verificando carpeta de PDFs..."

if [ ! -d "raw" ]; then
    echo "⚠️  Carpeta 'raw/' no encontrada. Creándola..."
    mkdir -p raw
    echo ""
    echo "⚠️  IMPORTANTE: Copiar los 44 PDFs de instructivos a la carpeta raw/"
    echo ""
    read -p "Presiona Enter cuando hayas copiado los PDFs..."
fi

PDF_COUNT=$(ls -1 raw/*.pdf 2>/dev/null | wc -l)
echo "✅ PDFs encontrados: $PDF_COUNT"

if [ "$PDF_COUNT" -eq 0 ]; then
    echo "⚠️  No se encontraron PDFs en raw/. La ingesta fallará."
fi

# ==================== 4. DETENER CONTENEDORES ANTERIORES ====================
echo ""
echo "🛑 Deteniendo contenedores anteriores (si existen)..."
docker-compose down 2>/dev/null || true

# ==================== 5. CONSTRUIR IMÁGENES ====================
echo ""
echo "🔨 Construyendo imágenes Docker..."
docker-compose build --no-cache

# ==================== 6. LEVANTAR SERVICIOS ====================
echo ""
echo "🚀 Levantando servicios..."
docker-compose up -d

# ==================== 7. ESPERAR A QUE POSTGRESQL ESTÉ LISTO ====================
echo ""
echo "⏳ Esperando a que PostgreSQL esté listo..."
sleep 10

# Verificar health check
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U postgres -d labia_db > /dev/null 2>&1; then
        echo "✅ PostgreSQL está listo"
        break
    fi
    echo "   Esperando... ($i/30)"
    sleep 2
done

# ==================== 8. VERIFICAR SERVICIOS ====================
echo ""
echo "📊 Estado de servicios:"
docker-compose ps

# ==================== 9. INGESTAR PDFs (OPCIONAL) ====================
echo ""
read -p "¿Deseas ingestar los PDFs ahora? (s/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[SsYy]$ ]]; then
    echo ""
    echo "📚 Iniciando ingesta de PDFs..."
    echo "   (Esto tomará varios minutos para ~44 PDFs)"
    docker-compose exec app python ingest.py --reset
    echo "✅ Ingesta completada"
fi

# ==================== 10. MOSTRAR LOGS ====================
echo ""
echo "================================================================================================"
echo "✅ DEPLOYMENT COMPLETADO"
echo "================================================================================================"
echo ""
echo "🌐 Aplicación disponible en: http://localhost:8010"
echo "🗄️  PostgreSQL en: localhost:5432"
echo ""
echo "📋 Comandos útiles:"
echo "   - Ver logs:        docker-compose logs -f app"
echo "   - Reiniciar:       docker-compose restart"
echo "   - Detener:         docker-compose down"
echo "   - Re-ingestar:     docker-compose exec app python ingest.py --reset"
echo ""
echo "🔍 Verificar salud de servicios:"
echo "   curl http://localhost:8010/"
echo ""

# Mostrar logs en tiempo real
read -p "¿Deseas ver los logs en tiempo real? (s/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[SsYy]$ ]]; then
    docker-compose logs -f app
fi
