"""
Pipeline de Ingestión de PDFs para RAG de Control de Calidad
Procesamiento robusto con múltiples parsers, chunking semántico y ChromaDB
"""

import os
import re
import logging
import io
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

# PDF Parsers
import pdfplumber
import fitz  # PyMuPDF
import pytesseract
import tabula
from PIL import Image
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTFigure

# Data Processing
import pandas as pd
from pint import UnitRegistry

# Langchain
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

# Utilities
from dotenv import load_dotenv

# ==================== CONFIGURACIÓN ====================
load_dotenv()

# Configurar Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ingestion.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Crear directorio de logs si no existe
Path("logs").mkdir(exist_ok=True)

# Directorios
RAW_DIR = Path("raw")
CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

# Unidades
ureg = UnitRegistry()

# ==================== PATRONES DE LIMPIEZA ====================
HEADER_FOOTER_PATTERNS = [
    r"DOCUMENTO CONTROLADO",
    r"LAZARUS.*?LABORATORIOS",
    r"LL-C[I]{1,2}-[I]{1,2}-\d+.*?Pág(?:ina)?\s+\d+\s+de\s+\d+",
    r"Edición\s+\d+.*?Fecha:.*?\d{2}/\d{2}/\d{4}",
]

# Patrones de metadatos
METADATA_PATTERNS = {
    'codigo': r'(LL-C[I]{1,2}-[I]{1,2}-\d+)',
    'norma_astm': r'(ASTM\s+[A-Z]\d+(?:/[A-Z]\d+)?(?:\s*-\s*\d+)?)',
    'norma_en': r'(EN\s+\d+(?:-\d+)?)',
    'revision': r'(?:Edición|Revisión|Rev\.?)\s+(\d+)',
    'fecha': r'Fecha:\s*(\d{2}/\d{2}/\d{4})',
}

# Secciones semánticas
SECTION_MARKERS = {
    'inicio': r'^\s*(?:INICIO|OBJETIVO|PROPÓSITO|ALCANCE)\s*$',
    'requisitos': r'^\s*(?:REQUISITOS|MATERIALES|EQUIPOS|REACTIVOS)\s*$',
    'procedimiento': r'^\s*(?:PROCEDIMIENTO|MÉTODO|PASOS)\s*$',
    'calculos': r'^\s*(?:CÁLCULOS|FÓRMULAS|EXPRESIÓN DE RESULTADOS)\s*$',
    'referencias': r'^\s*(?:REFERENCIAS|NORMATIVIDAD)\s*$',
}

# ==================== NORMALIZACIÓN DE UNIDADES ====================
UNIT_NORMALIZATION = {
    r'(?<!\w)mm(?!\w)': 'milímetros',
    r'(?<!\w)cm(?!\w)': 'centímetros',
    r'(?<!\w)in(?!\w)': 'pulgadas',
    r'(?<!\w)psi(?!\w)': 'PSI',
    r'(?<!\w)MPa(?!\w)': 'megapascales',
    r'(?<!\w)Pa(?!\w)': 'pascales',
    r'°C': 'grados Celsius',
    r'°F': 'grados Fahrenheit',
    r'(?<!\w)kg(?!\w)': 'kilogramos',
    r'(?<!\w)g(?!\w)': 'gramos',
    r'(?<!\w)lb(?!\w)': 'libras',
}


# ==================== FUNCIONES DE EXTRACCIÓN ====================

def extract_with_pdfplumber(pdf_path: Path) -> Dict[str, Any]:
    """Extrae texto y tablas usando pdfplumber (método principal)"""
    try:
        text_content = []
        tables_content = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extraer texto
                page_text = page.extract_text()
                if page_text:
                    text_content.append({
                        'page': page_num,
                        'text': page_text
                    })
                
                # Extraer tablas
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if table:
                        df = pd.DataFrame(table[1:], columns=table[0])
                        tables_content.append({
                            'page': page_num,
                            'table_num': table_idx + 1,
                            'data': df.to_string()
                        })
        
        return {
            'success': True,
            'text': text_content,
            'tables': tables_content,
            'parser': 'pdfplumber'
        }
    except Exception as e:
        logger.warning(f"pdfplumber falló para {pdf_path.name}: {str(e)}")
        return {'success': False, 'error': str(e)}


def extract_with_pdfminer(pdf_path: Path) -> Dict[str, Any]:
    """Extrae texto estructurado usando pdfminer.six (alternativa a camelot)"""
    try:
        text_content = []
        
        for page_num, page_layout in enumerate(extract_pages(str(pdf_path)), 1):
            page_text = ""
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    page_text += element.get_text()
            
            if page_text.strip():
                text_content.append({
                    'page': page_num,
                    'text': page_text
                })
        
        return {
            'success': True,
            'text': text_content,
            'parser': 'pdfminer'
        }
    except Exception as e:
        logger.warning(f"PDFMiner falló para {pdf_path.name}: {str(e)}")
        return {'success': False, 'error': str(e)}


def extract_with_tabula(pdf_path: Path) -> Dict[str, Any]:
    """Extrae tablas usando tabula-py"""
    try:
        tables_content = []
        
        # Leer todas las tablas
        tables = tabula.read_pdf(str(pdf_path), pages='all', multiple_tables=True)
        
        for idx, df in enumerate(tables):
            if not df.empty:
                tables_content.append({
                    'table_num': idx + 1,
                    'data': df.to_string()
                })
        
        return {
            'success': True,
            'tables': tables_content,
            'parser': 'tabula'
        }
    except Exception as e:
        logger.warning(f"Tabula falló para {pdf_path.name}: {str(e)}")
        return {'success': False, 'error': str(e)}


def extract_images_and_ocr(pdf_path: Path) -> Dict[str, Any]:
    """Extrae imágenes y aplica OCR con PyMuPDF + pytesseract"""
    try:
        ocr_content = []
        
        doc = fitz.open(pdf_path)
        
        # Limitar a primeras 3 páginas para OCR (optimización)
        max_pages_ocr = min(3, len(doc))
        
        for page_num in range(1, max_pages_ocr + 1):
            page = doc[page_num - 1]
            # Extraer imágenes de la página
            image_list = page.get_images()
            
            # Limitar a primeras 2 imágenes por página
            for img_idx, img in enumerate(image_list[:2]):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Convertir a PIL Image
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    # Solo OCR en imágenes grandes (probablemente contienen texto)
                    if image.width > 100 and image.height > 100:
                        # Aplicar OCR con timeout implícito
                        ocr_text = pytesseract.image_to_string(image, lang='spa', timeout=5)
                        
                        if ocr_text.strip():
                            ocr_content.append({
                                'page': page_num,
                                'image_num': img_idx + 1,
                                'text': ocr_text
                            })
                except Exception as e:
                    logger.debug(f"Error OCR en imagen {img_idx} página {page_num}: {str(e)}")
                    continue
        
        doc.close()
        
        return {
            'success': True,
            'ocr': ocr_content,
            'parser': 'PyMuPDF+OCR'
        }
    except Exception as e:
        logger.warning(f"OCR falló para {pdf_path.name}: {str(e)}")
        return {'success': False, 'error': str(e)}


# ==================== LIMPIEZA Y NORMALIZACIÓN ====================

def clean_text(text: str) -> str:
    """Limpia headers, footers y normaliza el texto"""
    # Remover headers/footers
    for pattern in HEADER_FOOTER_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Normalizar espacios en blanco
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Normalizar unidades (mantener símbolos pero agregar contexto)
    for pattern, replacement in UNIT_NORMALIZATION.items():
        text = re.sub(pattern, f'{replacement}', text)
    
    return text.strip()


def extract_metadata(text: str, filename: str) -> Dict[str, Any]:
    """Extrae metadatos del documento"""
    metadata: Dict[str, Any] = {
        "filename": filename,
        "codigo": None,
        # ChromaDB NO acepta listas/dicts/None en metadata. Guardamos normas como string.
        "normas": None,
        "revision": None,
        "fecha": None,
    }
    
    # Extraer código del documento
    codigo_match = re.search(METADATA_PATTERNS['codigo'], text)
    if codigo_match:
        metadata['codigo'] = codigo_match.group(1)
    
    # Extraer normas ASTM / EN
    normas: List[str] = []
    normas.extend(re.findall(METADATA_PATTERNS["norma_astm"], text))
    normas.extend(re.findall(METADATA_PATTERNS["norma_en"], text))
    normas = [n.strip() for n in normas if n and n.strip()]
    if normas:
        metadata["normas"] = ", ".join(sorted(set(normas)))
    
    # Extraer revisión
    rev_match = re.search(METADATA_PATTERNS['revision'], text)
    if rev_match:
        metadata['revision'] = rev_match.group(1)
    
    # Extraer fecha
    fecha_match = re.search(METADATA_PATTERNS['fecha'], text)
    if fecha_match:
        metadata['fecha'] = fecha_match.group(1)

    # Normalizar a tipos simples (str/int/float/bool) y remover None
    normalized: Dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            normalized[key] = value
        else:
            normalized[key] = str(value)

    return normalized


def detect_section(text: str) -> Optional[str]:
    """Detecta el tipo de sección basado en marcadores"""
    for section_type, pattern in SECTION_MARKERS.items():
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return section_type
    return None


# ==================== CHUNKING SEMÁNTICO ====================

def semantic_chunking(content: List[Dict], metadata: Dict, chunk_size: int = 800, chunk_overlap: int = 200) -> List[Document]:
    """Divide el contenido en chunks semánticos por sección"""
    documents = []
    
    # Combinar todo el texto por página
    full_text = ""
    for page_content in content:
        page_num = page_content.get('page', 0)
        text = page_content.get('text', '')
        full_text += f"\n\n=== Página {page_num} ===\n\n{text}"
    
    # Detectar secciones
    lines = full_text.split('\n')
    current_section = 'general'
    section_texts = {'general': []}
    
    for line in lines:
        detected_section = detect_section(line)
        if detected_section:
            current_section = detected_section
            if current_section not in section_texts:
                section_texts[current_section] = []
        
        section_texts[current_section].append(line)
    
    # Crear chunks por sección
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    for section_type, section_lines in section_texts.items():
        section_text = '\n'.join(section_lines)
        
        if section_text.strip():
            chunks = text_splitter.split_text(section_text)
            
            for idx, chunk in enumerate(chunks):
                doc_metadata = metadata.copy()
                doc_metadata.update({
                    'section_type': section_type,
                    'chunk_index': idx,
                    'total_chunks': len(chunks)
                })
                
                documents.append(Document(
                    page_content=chunk,
                    metadata=doc_metadata
                ))
    
    return documents


# ==================== PROCESAMIENTO PRINCIPAL ====================

def process_single_pdf(pdf_path: Path) -> List[Document]:
    """Procesa un solo PDF con múltiples parsers y fallbacks"""
    logger.info(f"Procesando: {pdf_path.name}")
    
    try:
        # 1. Extraer con pdfplumber (principal)
        result_plumber = extract_with_pdfplumber(pdf_path)
        
        if not result_plumber['success']:
            # Fallback a pdfminer si pdfplumber falla
            logger.warning(f"pdfplumber falló, intentando con pdfminer...")
            result_pdfminer = extract_with_pdfminer(pdf_path)
            if not result_pdfminer['success']:
                logger.error(f"Fallo crítico en {pdf_path.name}: no se pudo extraer texto base")
                return []
            result_plumber = result_pdfminer
        
        # 2. Extraer tablas con Tabula
        result_tabula = extract_with_tabula(pdf_path)
        
        # 3. OCR de imágenes
        result_ocr = extract_images_and_ocr(pdf_path)
        
        # Combinar todo el contenido
        all_text_content = result_plumber['text'].copy()
        
        # Agregar tablas de Tabula
        if result_tabula['success'] and result_tabula['tables']:
            for table in result_tabula['tables']:
                all_text_content.append({
                    'page': 0,
                    'text': f"\n[TABLA]\n{table['data']}\n"
                })
        
        # Agregar OCR
        if result_ocr['success']:
            for ocr_item in result_ocr['ocr']:
                all_text_content.append({
                    'page': ocr_item['page'],
                    'text': f"\n[OCR - Imagen]\n{ocr_item['text']}\n"
                })
        
        # Combinar y limpiar texto
        combined_text = "\n".join([item['text'] for item in all_text_content])
        cleaned_text = clean_text(combined_text)
        
        # Extraer metadatos
        metadata = extract_metadata(cleaned_text, pdf_path.name)
        
        # Crear chunks semánticos
        documents = semantic_chunking(all_text_content, metadata)
        
        logger.info(f"✓ {pdf_path.name}: {len(documents)} chunks generados")
        return documents
        
    except Exception as e:
        logger.error(f"✗ Error procesando {pdf_path.name}: {str(e)}", exc_info=True)
        
        # Guardar error detallado
        error_log = {
            'filename': pdf_path.name,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }
        
        with open('logs/failed_pdfs.json', 'a', encoding='utf-8') as f:
            f.write(json.dumps(error_log, ensure_ascii=False) + '\n')
        
        return []


def process_all_pdfs() -> List[Document]:
    """Procesa todos los PDFs en el directorio raw/"""
    all_documents = []
    
    pdf_files = list(RAW_DIR.glob("*.pdf"))
    total_files = len(pdf_files)
    
    logger.info(f"Encontrados {total_files} archivos PDF en {RAW_DIR}")
    
    for idx, pdf_path in enumerate(pdf_files, 1):
        logger.info(f"[{idx}/{total_files}] Procesando {pdf_path.name}")
        
        docs = process_single_pdf(pdf_path)
        all_documents.extend(docs)
    
    logger.info(f"\nResumen: {len(all_documents)} chunks totales de {total_files} PDFs")
    return all_documents


# ==================== EMBEDDINGS Y VECTORSTORE ====================

def create_vectorstore(documents: List[Document]):
    """Crea embeddings y almacena en ChromaDB"""
    logger.info("Generando embeddings con Google Gemini...")
    
    # Verificar API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your_google_api_key_here":
        raise ValueError("GOOGLE_API_KEY no configurada en .env")
    
    # Crear embeddings
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=api_key
    )
    
    # Crear ChromaDB
    logger.info(f"Almacenando en ChromaDB: {CHROMA_DIR}")
    
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name="laboratorio_qa"
    )
    
    logger.info(f"✓ Vectorstore creado con {len(documents)} documentos")
    return vectorstore


# ==================== MAIN ====================

def main():
    """Función principal de ingestión"""
    logger.info("=" * 80)
    logger.info("INICIANDO PIPELINE DE INGESTIÓN - RAG Control de Calidad")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    # 1. Procesar PDFs
    documents = process_all_pdfs()
    
    if not documents:
        logger.error("No se generaron documentos. Revisa los logs de errores.")
        return
    
    # 2. Crear vectorstore
    vectorstore = create_vectorstore(documents)
    
    # 3. Resumen final
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("=" * 80)
    logger.info("INGESTIÓN COMPLETADA")
    logger.info(f"Tiempo total: {duration:.2f} segundos")
    logger.info(f"Documentos procesados: {len(documents)}")
    logger.info(f"ChromaDB ubicación: {CHROMA_DIR}")
    logger.info("=" * 80)


if __name__ == "__main__":
    import io  # Necesario para OCR
    main()
