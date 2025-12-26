# Script helper para ejecutar el RAG del laboratorio
# Activa el venv y configura Java automáticamente

Write-Host "🚀 Iniciando RAG de Control de Calidad..." -ForegroundColor Cyan
Write-Host ""

# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Configurar Java para tabula-py
$env:PATH = "C:\Program Files\Java\jre1.8.0_471\bin;$env:PATH"

# Verificar configuración
Write-Host "✓ Python:" (python --version) -ForegroundColor Green
Write-Host "✓ Java:" (java -version 2>&1 | Select-Object -First 1) -ForegroundColor Green
Write-Host ""

# Mostrar opciones
Write-Host "Opciones disponibles:" -ForegroundColor Yellow
Write-Host "1. Ejecutar ingestión (python ingest.py)"
Write-Host "2. Iniciar chatbot (python app.py)"
Write-Host "3. Salir"
Write-Host ""

$opcion = Read-Host "Selecciona una opción (1-3)"

switch ($opcion) {
    "1" {
        Write-Host ""
        Write-Host "📄 Procesando PDFs..." -ForegroundColor Cyan
        python ingest.py
    }
    "2" {
        Write-Host ""
        Write-Host "💬 Iniciando chatbot..." -ForegroundColor Cyan
        Write-Host "El chatbot se abrirá en: http://127.0.0.1:7860" -ForegroundColor Green
        Write-Host ""
        python app.py
    }
    "3" {
        Write-Host "Saliendo..." -ForegroundColor Gray
        exit
    }
    default {
        Write-Host "Opción inválida" -ForegroundColor Red
    }
}
