"""
================================================================================================
INGEST.PY - RAG LABIA
Pipeline de Ingesta Avanzada para Instructivos de Laboratorio de Control de Calidad
================================================================================================

Características:
- Extracción multi-librería (pdfplumber → PyMuPDF → pytesseract fallback)
- Limpieza de headers/footers repetidos ("DOCUMENTO CONTROLADO")
- Segmentación semántica por secciones (INICIO, PROCEDIMIENTO, TABLA, FIGURA)
- Normalización dual de unidades (original + SI) con pint
- Extracción de metadatos (código LL-CI-I-xx, normas ASTM, revisión, fecha)
- Chunking controlado 1024 tokens / overlap 150
- Embeddings Google Gemini + PostgreSQL+pgvector

Autor: Sistema LabIa
Fecha: 27 de diciembre de 2025
================================================================================================
"""

import os
import re
import glob
import logging
import ssl
import httpx
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv

# PDF Processing Libraries
import pdfplumber
import fitz  # PyMuPDF
try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️ OCR no disponible (pytesseract/Pillow/pdf2image). Solo se usarán extractores nativos.")

# Data Processing
import pandas as pd
import pint

# LangChain
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.documents import Document

# Database
import database

# Load environment variables
load_dotenv()

# ================================================================================================
# BYPASS SSL PARA REDES CORPORATIVAS
# ================================================================================================

# Deshabilitar warnings de SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Cliente HTTP con SSL deshabilitado
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ================================================================================================
# CONFIGURACIÓN
# ================================================================================================

RAW_DIRECTORY = "./raw"
COLLECTION_NAME = "labia_embeddings"

# Chunking Configuration (Opción B: 1024 tokens / 150 overlap)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1024"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

# PostgreSQL Connection
PG_CONNECTION_STRING = f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', '')}@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'labia_db')}"

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Unit Registry para normalización
ureg = pint.UnitRegistry()

# ================================================================================================
# DICCIONARIO DE NORMALIZACIÓN DE UNIDADES
# ================================================================================================

UNIT_PATTERNS = {
    # Temperatura
    r'(\d+\.?\d*)\s*°C': ('degC', 'kelvin'),
    r'(\d+\.?\d*)\s*°F': ('degF', 'degC'),
    
    # Presión
    r'(\d+\.?\d*)\s*psi': ('psi', 'kilopascal'),
    r'(\d+\.?\d*)\s*MPa': ('megapascal', 'megapascal'),
    r'(\d+\.?\d*)\s*kPa': ('kilopascal', 'kilopascal'),
    r'(\d+\.?\d*)\s*Pa': ('pascal', 'kilopascal'),
    
    # Longitud
    r'(\d+\.?\d*)\s*mm': ('millimeter', 'millimeter'),
    r'(\d+\.?\d*)\s*cm': ('centimeter', 'millimeter'),
    r'(\d+\.?\d*)\s*m(?!m)': ('meter', 'meter'),
    r'(\d+\.?\d*)\s*in': ('inch', 'millimeter'),
    r'(\d+\.?\d*)\s*"': ('inch', 'millimeter'),
    r'(\d+\.?\d*)\s*ft': ('foot', 'meter'),
    
    # Masa
    r'(\d+\.?\d*)\s*kg': ('kilogram', 'kilogram'),
    r'(\d+\.?\d*)\s*g(?!r)': ('gram', 'kilogram'),
    r'(\d+\.?\d*)\s*lb': ('pound', 'kilogram'),
    
    # Volumen
    r'(\d+\.?\d*)\s*L': ('liter', 'liter'),
    r'(\d+\.?\d*)\s*mL': ('milliliter', 'liter'),
    r'(\d+\.?\d*)\s*gal': ('gallon', 'liter'),
}

# ================================================================================================
# CLASE: PDFExtractor - Extracción Multi-Librería
# ================================================================================================

class PDFExtractor:
    """
    Extrae texto, tablas y metadatos de PDFs técnicos usando múltiples librerías:
    1. pdfplumber (PRIORIDAD 1: tablas estructuradas)
    2. PyMuPDF/fitz (PRIORIDAD 2: texto nativo)
    3. pytesseract (FALLBACK: OCR para imágenes/diagramas)
    """
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.filename = os.path.basename(pdf_path)
        
    def extract_with_pdfplumber(self) -> Tuple[str, List[pd.DataFrame]]:
        """Extrae texto y tablas con pdfplumber (mejor para tablas)."""
        try:
            full_text = []
            tables = []
            
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extraer texto
                    text = page.extract_text()
                    if text:
                        full_text.append(f"\n--- Página {page_num} ---\n{text}")
                    
                    # Extraer tablas
                    page_tables = page.extract_tables()
                    if page_tables:
                        for table_idx, table in enumerate(page_tables):
                            if table:
                                df = pd.DataFrame(table[1:], columns=table[0] if table[0] else None)
                                df['_page'] = page_num
                                df['_table_idx'] = table_idx
                                tables.append(df)
            
            return "\n".join(full_text), tables
        except Exception as e:
            logger.warning(f"pdfplumber falló en {self.filename}: {e}")
            return "", []
    
    def extract_with_pymupdf(self) -> str:
        """Extrae texto con PyMuPDF/fitz (mejor para texto nativo)."""
        try:
            doc = fitz.open(self.pdf_path)
            full_text = []
            
            for page_num, page in enumerate(doc, 1):
                text = page.get_text()
                if text.strip():
                    full_text.append(f"\n--- Página {page_num} ---\n{text}")
            
            doc.close()
            return "\n".join(full_text)
        except Exception as e:
            logger.warning(f"PyMuPDF falló en {self.filename}: {e}")
            return ""
    
    def extract_with_ocr(self) -> str:
        """Extrae texto con OCR (fallback para PDFs escaneados/imágenes)."""
        if not OCR_AVAILABLE:
            logger.warning("OCR no disponible. Instala pytesseract, Pillow y pdf2image.")
            return ""
        
        try:
            logger.info(f"Aplicando OCR a {self.filename}...")
            images = convert_from_path(self.pdf_path)
            full_text = []
            
            for page_num, image in enumerate(images, 1):
                text = pytesseract.image_to_string(image, lang='spa')
                if text.strip():
                    full_text.append(f"\n--- Página {page_num} (OCR) ---\n{text}")
            
            return "\n".join(full_text)
        except Exception as e:
            logger.error(f"OCR falló en {self.filename}: {e}")
            return ""
    
    def extract_all(self) -> Tuple[str, List[pd.DataFrame]]:
        """
        Estrategia de extracción con fallback:
        1. Intentar pdfplumber (mejor para tablas)
        2. Si falla o texto insuficiente, intentar PyMuPDF
        3. Si ambos fallan, intentar OCR (solo si OCR_AVAILABLE=True)
        """
        logger.info(f"📄 Procesando: {self.filename}")
        
        # Intento 1: pdfplumber
        text, tables = self.extract_with_pdfplumber()
        
        # Intento 2: PyMuPDF si pdfplumber no extrajo suficiente texto
        if len(text) < 100:
            logger.info(f"  ↳ pdfplumber extrajo poco texto, probando PyMuPDF...")
            pymupdf_text = self.extract_with_pymupdf()
            if len(pymupdf_text) > len(text):
                text = pymupdf_text
        
        # Intento 3: OCR solo si aún no hay texto suficiente
        if len(text) < 100 and OCR_AVAILABLE:
            logger.info(f"  ↳ Texto insuficiente, aplicando OCR...")
            ocr_text = self.extract_with_ocr()
            if len(ocr_text) > len(text):
                text = ocr_text
        
        logger.info(f"  ✓ Extraído: {len(text)} caracteres, {len(tables)} tablas")
        return text, tables

# ================================================================================================
# FUNCIONES: Limpieza y Normalización
# ================================================================================================

def clean_headers_footers(text: str) -> str:
    """
    Elimina headers/footers repetidos que contaminan chunks:
    - "DOCUMENTO CONTROLADO"
    - Logos
    - Pies de página con números
    """
    patterns_to_remove = [
        r'DOCUMENTO CONTROLADO',
        r'LAZARUS.*?(?=\n)',
        r'Página \d+ de \d+',
        r'^\d+\s*$',  # Números de página solitarios
        r'_{3,}',  # Líneas de guiones bajos
        r'-{3,}',  # Líneas de guiones
    ]
    
    for pattern in patterns_to_remove:
        text = re.sub(pattern, '', text, flags=re.MULTILINE | re.IGNORECASE)
    
    # Limpiar espacios múltiples
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'  +', ' ', text)
    
    return text.strip()

def normalize_units(text: str) -> Dict[str, any]:
    """
    Normaliza unidades encontradas en el texto (Opción B: Dual).
    Retorna diccionario con valores originales y normalizados.
    """
    normalized_units = []
    
    for pattern, (from_unit, to_unit) in UNIT_PATTERNS.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            value_str = match.group(1)
            original = match.group(0)
            
            try:
                value = float(value_str)
                quantity = value * ureg(from_unit)
                converted = quantity.to(to_unit)
                
                normalized_units.append({
                    'original': original,
                    'value_original': value,
                    'unit_original': from_unit,
                    'value_normalized': f"{converted.magnitude:.2f}",
                    'unit_normalized': to_unit
                })
            except Exception as e:
                logger.debug(f"Error normalizando '{original}': {e}")
    
    return normalized_units

# ================================================================================================
# FUNCIONES: Extracción de Metadatos
# ================================================================================================

def extract_metadata(text: str, filename: str) -> Dict[str, any]:
    """
    Extrae metadatos específicos de instructivos de laboratorio:
    - Código de documento (LL-CI-I-05, LL-CII-20, etc.)
    - Normas ASTM (C109, C1090, C143, etc.)
    - Revisión (rev01, rev02, edición)
    - Fecha
    - Variables técnicas (pH, Pa, Ps, G, T, V)
    """
    metadata = {
        'source': filename,
        'codigo_documento': None,
        'normas_astm': [],
        'revision': None,
        'fecha': None,
        'variables_tecnicas': [],
        'tipo_documento': 'instructivo_laboratorio'
    }
    
    # Código de documento: LL-CI-I-05, LLCCI05, LL-CII-20, etc.
    codigo_match = re.search(r'(LL[-\s]?C(?:I{1,2})[-\s]?I?[-\s]?\d{2,3})', text, re.IGNORECASE)
    if codigo_match:
        metadata['codigo_documento'] = codigo_match.group(1).replace(' ', '').upper()
    
    # Normas ASTM: ASTM C109, ASTM C1090, C143, etc.
    astm_matches = re.findall(r'ASTM\s+([A-Z]\d{2,4}(?:-\d{2})?)', text, re.IGNORECASE)
    if astm_matches:
        metadata['normas_astm'] = list(set(astm_matches))
    
    # Revisión: rev01, rev02, edición 01, etc.
    revision_match = re.search(r'(?:rev|revisión|edición)\s*(\d{1,2})', text, re.IGNORECASE)
    if revision_match:
        metadata['revision'] = f"rev{revision_match.group(1).zfill(2)}"
    
    # Fecha: 01/12/2023, 2023-12-01, etc.
    fecha_match = re.search(r'(?:fecha|date)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
    if fecha_match:
        metadata['fecha'] = fecha_match.group(1)
    
    # Variables técnicas comunes en laboratorio
    variables_patterns = [
        r'\bpH\b', r'\bPa\b', r'\bPs\b', r'\bG\b', r'\bT\b', r'\bV\b',
        r'gravedad específica', r'revenimiento', r'resistencia',
        r'contenido de aire', r'viscosidad', r'densidad'
    ]
    for pattern in variables_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            metadata['variables_tecnicas'].append(pattern.replace(r'\b', ''))
    
    return metadata
    # Variables técnicas comunes en laboratorio
    variables_patterns = [
        r'\bpH\b', r'\bPa\b', r'\bPs\b', r'\bG\b', r'\bT\b', r'\bV\b',
        r'gravedad específica', r'revenimiento', r'resistencia',
        r'contenido de aire', r'viscosidad', r'densidad'
    ]
    for pattern in variables_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            metadata['variables_tecnicas'].append(pattern.replace(r'\b', ''))
    
    return metadata

# ================================================================================================
# FUNCIONES: Segmentación Semántica
# ================================================================================================

def segment_by_sections(text: str) -> List[Dict[str, str]]:
    """
    Divide el texto por secciones semánticas típicas de instructivos:
    - INICIO, OBJETIVO, ALCANCE
    - REQUISITOS, MATERIALES, EQUIPOS
    - PROCEDIMIENTO (con pasos numerados)
    - CÁLCULOS, FÓRMULAS
    - PRECAUCIONES, SEGURIDAD
    - REFERENCIAS
    """
    sections = []
    
    # Patrones de secciones comunes
    section_patterns = {
        'OBJETIVO': r'(?:OBJETIVO|PROPÓSITO)',
        'ALCANCE': r'ALCANCE',
        'REQUISITOS': r'(?:REQUISITOS|REQUERIMIENTOS)',
        'MATERIALES': r'(?:MATERIALES|REACTIVOS)',
        'EQUIPOS': r'(?:EQUIPOS|APARATOS|INSTRUMENTOS)',
        'PROCEDIMIENTO': r'PROCEDIMIENTO',
        'CÁLCULOS': r'(?:CÁLCULOS|FÓRMULAS|EXPRESIÓN)',
        'RESULTADOS': r'(?:RESULTADOS|INFORME)',
        'PRECAUCIONES': r'(?:PRECAUCIONES|SEGURIDAD|ADVERTENCIAS)',
        'REFERENCIAS': r'(?:REFERENCIAS|NORMAS)',
    }
    
    # Dividir por secciones
    current_section = 'INICIO'
    current_text = []
    
    for line in text.split('\n'):
        matched_section = None
        for section_name, pattern in section_patterns.items():
            if re.search(f'^\\s*{pattern}', line, re.IGNORECASE):
                # Guardar sección anterior
                if current_text:
                    sections.append({
                        'seccion': current_section,
                        'contenido': '\n'.join(current_text)
                    })
                current_section = section_name
                current_text = [line]
                matched_section = True
                break
        
        if not matched_section:
            current_text.append(line)
    
    # Guardar última sección
    if current_text:
        sections.append({
            'seccion': current_section,
            'contenido': '\n'.join(current_text)
        })
    
    return sections

# ================================================================================================
# FUNCIONES: Procesamiento de Tablas
# ================================================================================================

def process_tables(tables: List[pd.DataFrame]) -> List[Dict[str, any]]:
    """
    Convierte tablas a formato textual estructurado.
    Las tablas se guardan como chunks únicos (no se dividen).
    """
    processed_tables = []
    
    for idx, df in enumerate(tables):
        try:
            # Validar que la tabla tenga datos
            if df.empty:
                logger.warning(f"      ⚠️  Tabla {idx} vacía - SKIP")
                continue
            
            # Convertir tabla a texto markdown
            table_text = df.to_markdown(index=False)
            
            # Validar que el texto generado tenga contenido
            if not table_text or not table_text.strip():
                logger.warning(f"      ⚠️  Tabla {idx} sin contenido de texto - SKIP")
                continue
            
            # Extraer metadatos de la tabla de forma segura
            page_num = None
            if '_page' in df.columns:
                try:
                    # Usar iloc para acceso seguro al primer elemento
                    page_series = df['_page']
                    if len(page_series) > 0:
                        page_num = page_series.iloc[0]
                except Exception:
                    pass  # Si falla, page_num queda como None
            
            processed_tables.append({
                'contenido': table_text,
                'tipo_contenido': 'tabla',
                'tabla_idx': idx,
                'page': page_num,
                'columnas': list(df.columns),
                'filas': len(df)
            })
            
        except Exception as e:
            logger.warning(f"      ⚠️  Error procesando tabla {idx}: {e} - SKIP")
            continue
    
    return processed_tables

# ================================================================================================
# FUNCIÓN PRINCIPAL: Ingestar PDFs
# ================================================================================================

def reset_vectorstore():
    """
    Borra toda la colección de embeddings para empezar de cero.
    
    ADVERTENCIA: Esto eliminará todos los documentos vectorizados.
    """
    logger.warning("⚠️  LIMPIANDO COLECCIÓN DE EMBEDDINGS...")
    try:
        conn = database.get_pg_connection()
        cursor = conn.cursor()
        
        # Eliminar todos los embeddings de la colección
        cursor.execute(
            """DELETE FROM langchain_pg_embedding 
               WHERE collection_id = (
                   SELECT uuid FROM langchain_pg_collection WHERE name = %s
               )""",
            (COLLECTION_NAME,)
        )
        deleted_count = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Eliminados {deleted_count} documentos de la colección '{COLLECTION_NAME}'")
        logger.info("🔄 La colección está lista para una ingesta limpia")
    except Exception as e:
        logger.error(f"❌ Error limpiando colección: {e}")


def ingest_pdfs(test_mode: bool = False, test_files: Optional[List[str]] = None, reset: bool = False):
    """
    Pipeline completo de ingesta:
    1. Extraer texto y tablas (multi-librería)
    2. Limpiar headers/footers
    3. Segmentar por secciones
    4. Extraer metadatos
    5. Normalizar unidades (dual)
    6. Chunking controlado (1024/150)
    7. Generar embeddings
    8. Almacenar en PostgreSQL+pgvector
    
    Args:
        test_mode: Si True, procesa solo archivos de test
        test_files: Lista de patrones de archivos para modo test
        reset: Si True, borra toda la colección antes de ingestar
    """
    logger.info("=" * 80)
    logger.info("🚀 INICIANDO INGESTA - RAG LABIA")
    logger.info("=" * 80)
    
    # Inicializar base de datos
    database.init_db()
    
    # Limpiar colección si se solicita
    if reset:
        reset_vectorstore()
    
    # Obtener lista de PDFs
    pdf_files = []
    if test_mode and test_files:
        for pattern in test_files:
            pdf_files.extend(glob.glob(os.path.join(RAW_DIRECTORY, pattern)))
    else:
        pdf_files = glob.glob(os.path.join(RAW_DIRECTORY, "*.pdf"))
    
    if not pdf_files:
        logger.error(f"❌ No se encontraron PDFs en {RAW_DIRECTORY}")
        return
    
    logger.info(f"📁 Encontrados: {len(pdf_files)} archivos PDF")
    if test_mode:
        logger.info(f"🧪 MODO PRUEBA: Procesando {len(pdf_files)} archivos")
    
    # Inicializar embeddings
    logger.info("🔗 Conectando a Google Gemini...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        transport="rest",  # Usar REST en vez de gRPC
        client_options={"api_endpoint": "https://generativelanguage.googleapis.com"}
    )
    
    # Inicializar vectorstore
    vectorstore = PGVector(
        connection=PG_CONNECTION_STRING,
        collection_name=COLLECTION_NAME,
        embeddings=embeddings
    )
    
    # Procesar cada PDF
    total_chunks = 0
    total_tables = 0
    
    for pdf_idx, pdf_path in enumerate(pdf_files, 1):
        logger.info(f"\n{'=' * 80}")
        logger.info(f"📄 [{pdf_idx}/{len(pdf_files)}] {os.path.basename(pdf_path)}")
        logger.info(f"{'=' * 80}")
        
        try:
            # 1. Extracción
            extractor = PDFExtractor(pdf_path)
            text, tables = extractor.extract_all()
            
            if len(text) < 50:
                logger.warning(f"  ⚠️ Texto insuficiente extraído, saltando...")
                continue
            
            # 2. Limpieza
            text = clean_headers_footers(text)
            
            # 3. Extracción de metadatos
            metadata = extract_metadata(text, os.path.basename(pdf_path))
            logger.info(f"  📋 Metadatos: {metadata['codigo_documento']} | ASTM: {metadata['normas_astm']}")
            
            # 4. Normalización de unidades (dual)
            normalized_units = normalize_units(text)
            if normalized_units:
                logger.info(f"  🔢 Unidades normalizadas: {len(normalized_units)}")
                metadata['unidades_normalizadas'] = normalized_units
            
            # 5. Segmentación por secciones
            sections = segment_by_sections(text)
            logger.info(f"  📑 Secciones detectadas: {[s['seccion'] for s in sections]}")
            
            # 6. Chunking controlado
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""],
                keep_separator=True
            )
            
            documents = []
            
            # Procesar secciones como chunks
            logger.info(f"  🔹 Iniciando chunking de {len(sections)} secciones...")
            for section_idx, section in enumerate(sections):
                # Validar que la sección tenga contenido
                if not section or 'contenido' not in section:
                    logger.warning(f"     ⚠️  Sección {section_idx} sin estructura válida - SKIP")
                    continue
                
                contenido = section.get('contenido', '').strip()
                seccion_nombre = section.get('seccion', 'DESCONOCIDA')
                
                if not contenido:
                    logger.warning(f"     ⚠️  Sección '{seccion_nombre}' vacía - SKIP")
                    continue
                
                logger.info(f"     📄 Sección '{seccion_nombre}': {len(contenido)} caracteres")
                
                try:
                    section_chunks = text_splitter.split_text(contenido)
                except Exception as chunk_error:
                    logger.error(f"     ❌ Error en split_text para '{seccion_nombre}': {chunk_error}")
                    continue
                
                # Validar que se generaron chunks
                if not section_chunks:
                    logger.warning(f"        ⚠️  No se generaron chunks para '{seccion_nombre}'")
                    continue
                
                logger.info(f"        ✓ Generados {len(section_chunks)} chunks")
                    
                for chunk_idx, chunk in enumerate(section_chunks):
                    # Validar que el chunk tenga contenido
                    if not chunk or not chunk.strip():
                        logger.warning(f"           ⚠️  Chunk {chunk_idx} vacío - SKIP")
                        continue
                        
                    doc_metadata = {
                        **metadata,
                        'seccion': seccion_nombre,
                        'chunk_idx': chunk_idx,
                        'tipo_contenido': 'texto'
                    }
                    # Limpiar metadatos complejos para pgvector
                    doc_metadata = {k: v for k, v in doc_metadata.items() 
                                  if isinstance(v, (str, int, float, bool)) or v is None}
                    
                    documents.append(Document(
                        page_content=chunk,
                        metadata=doc_metadata
                    ))
            
            # 7. Procesar tablas (como chunks únicos)
            logger.info(f"  🔹 Procesando {len(tables)} tablas...")
            try:
                processed_tables = process_tables(tables)
                for table_data in processed_tables:
                    if not table_data or 'contenido' not in table_data:
                        logger.warning(f"     ⚠️  Tabla sin contenido - SKIP")
                        continue
                    
                    table_metadata = {
                        **metadata,
                        'tipo_contenido': 'tabla',
                        'tabla_idx': table_data['tabla_idx'],
                        'page': table_data.get('page')
                    }
                    table_metadata = {k: v for k, v in table_metadata.items() 
                                    if isinstance(v, (str, int, float, bool)) or v is None}
                    
                    documents.append(Document(
                        page_content=table_data['contenido'],
                        metadata=table_metadata
                    ))
                
                total_tables += len(processed_tables)
                logger.info(f"     ✓ {len(processed_tables)} tablas procesadas")
                
            except Exception as table_error:
                logger.error(f"  ❌ Error procesando tablas: {table_error}")
                import traceback
                logger.error(traceback.format_exc())
            
            # 8. Generar embeddings y almacenar
            if documents:
                logger.info(f"  💾 Generando embeddings para {len(documents)} chunks...")
                vectorstore.add_documents(documents)
                total_chunks += len(documents)
                logger.info(f"  ✅ Almacenados {len(documents)} chunks ({len(processed_tables)} tablas)")
            
        except Exception as e:
            import traceback
            logger.error(f"  ❌ Error procesando {os.path.basename(pdf_path)}: {e}")
            logger.error(f"  📍 Traceback completo:")
            logger.error(traceback.format_exc())
            continue
    
    # Resumen final
    logger.info("\n" + "=" * 80)
    logger.info("✅ INGESTA COMPLETADA")
    logger.info("=" * 80)
    logger.info(f"📊 Total PDFs procesados: {len(pdf_files)}")
    logger.info(f"📝 Total chunks creados: {total_chunks}")
    logger.info(f"📋 Total tablas procesadas: {total_tables}")
    logger.info(f"🗄️ Colección: {COLLECTION_NAME}")
    logger.info(f"🔗 PostgreSQL: {os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'labia_db')}")
    logger.info("=" * 80)

# ================================================================================================
# MAIN
# ================================================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingesta de PDFs para RAG LabIa")
    parser.add_argument("--test", action="store_true", help="Modo prueba (procesar solo archivos de test)")
    parser.add_argument("--files", type=str, help="Patrones de archivos para modo prueba (separados por coma)")
    parser.add_argument("--reset", action="store_true", help="Borrar toda la colección antes de ingestar (ingesta limpia)")
    
    args = parser.parse_args()
    
    test_files = None
    if args.files:
        test_files = [f.strip() for f in args.files.split(',')]
    
    # Advertencia si se usa --reset
    if args.reset:
        print("\n" + "="*80)
        print("⚠️  ADVERTENCIA: Se borrarán TODOS los documentos vectorizados")
        print("="*80)
        response = input("¿Estás seguro de continuar? (escriba 'SI' para confirmar): ")
        if response.strip().upper() != 'SI':
            print("❌ Operación cancelada")
            exit(0)
    
    ingest_pdfs(test_mode=args.test, test_files=test_files, reset=args.reset)
