import os
import pdfplumber
import docx
import logging

logger = logging.getLogger(__name__)

def extract_text_from_file(file_path: str) -> str:
    """
    Extracts text from PDF or DOCX files.
    """
    ext = file_path.split('.')[-1].lower()
    text = ""
    
    try:
        if ext == 'pdf':
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        elif ext == 'docx':
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif ext == 'odt':
            import zipfile
            from xml.etree import ElementTree as ET
            with zipfile.ZipFile(file_path) as z:
                with z.open('content.xml') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    ns = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
                    for elem in root.iter():
                        if elem.text:
                            text += elem.text + " "
        else:
            logger.warning(f"Unsupported file extension: {ext}")
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {e}")
        
    return text.strip()
