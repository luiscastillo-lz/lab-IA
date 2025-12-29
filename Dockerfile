FROM python:3.11-slim

# Metadata
LABEL maintainer="Luis Castillo - Lazarus & Lazarus"
LABEL description="Lab-Ai: Asistente Virtual de Laboratorio de Control de Calidad"
LABEL version="1.0.0"

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    default-jre \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements primero (mejor uso de cache de Docker)
COPY requirements.txt .

# Instalar dependencias Python con bypass SSL para redes corporativas
RUN pip install --no-cache-dir --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org && \
    pip install --no-cache-dir -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org

# Copiar código de la aplicación
COPY app.py .
COPY database.py .
COPY ingest.py .
COPY static/ ./static/
COPY templates/ ./templates/

# Crear carpetas necesarias
RUN mkdir -p raw logs

# Exponer puerto 8010 (configurado en .env)
EXPOSE 8010

# Variables de entorno por defecto
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV PORT=8010

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8010', timeout=5)" || exit 1

# Comando para ejecutar la aplicación
CMD ["python", "app.py"]
