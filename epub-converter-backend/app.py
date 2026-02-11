from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import ebooklib
from ebooklib import epub
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from bs4 import BeautifulSoup
import io
import os
import tempfile
from werkzeug.utils import secure_filename
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Increase max content length to 50MB
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {'epub'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_html_text(html_content):
    """Extract clean text from HTML - optimized version"""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
    except:
        soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style tags
    for script in soup(["script", "style", "meta", "link"]):
        script.decompose()
    
    # Get text and clean it
    text = soup.get_text(separator=' ', strip=True)
    
    # Clean up excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()

def extract_epub_content(epub_path):
    """Extract text and metadata from EPUB file - optimized"""
    logger.info(f"Starting EPUB extraction from {epub_path}")
    
    try:
        book = epub.read_epub(epub_path)
    except Exception as e:
        logger.error(f"Failed to read EPUB: {e}")
        raise Exception(f"Invalid EPUB file: {str(e)}")
    
    # Get metadata
    title = book.get_metadata('DC', 'title')
    title = title[0][0] if title else 'Untitled'
    
    author = book.get_metadata('DC', 'creator')
    author = author[0][0] if author else 'Unknown Author'
    
    logger.info(f"Book: {title} by {author}")
    
    # Extract all text content with progress logging
    chapters = []
    items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    
    logger.info(f"Processing {len(items)} document items")
    
    for idx, item in enumerate(items):
        try:
            content = item.get_content().decode('utf-8', errors='ignore')
            text = clean_html_text(content)
            
            # Only include if has substantial content (more than 50 chars)
            if len(text) > 50:
                # Limit chapter size to prevent memory issues
                if len(text) > 100000:  # 100k chars max per chapter
                    text = text[:100000] + "..."
                
                chapters.append({'text': text})
                logger.info(f"Processed chapter {idx + 1}/{len(items)}: {len(text)} chars")
        except Exception as e:
            logger.warning(f"Skipping problematic chapter {idx + 1}: {e}")
            continue
    
    logger.info(f"Successfully extracted {len(chapters)} chapters")
    
    return {
        'title': title,
        'author': author,
        'chapters': chapters
    }

def create_pdf(book_data):
    """Create PDF from book data using ReportLab - optimized"""
    logger.info("Starting PDF creation")
    
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor='#2c3e50',
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    author_style = ParagraphStyle(
        'CustomAuthor',
        parent=styles['Normal'],
        fontSize=16,
        textColor='#7f8c8d',
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique'
    )
    
    chapter_style = ParagraphStyle(
        'CustomChapter',
        parent=styles['Heading2'],
        fontSize=14,
        textColor='#34495e',
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        textColor='#333333',
        alignment=TA_JUSTIFY,
        spaceAfter=10,
        leading=14,
        fontName='Times-Roman'
    )
    
    # Add title page
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph(book_data['title'], title_style))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph(f"by {book_data['author']}", author_style))
    elements.append(PageBreak())
    
    logger.info(f"Processing {len(book_data['chapters'])} chapters for PDF")
    
    # Add chapters with progress logging
    for idx, chapter in enumerate(book_data['chapters'], 1):
        # Add chapter number if multiple chapters
        if len(book_data['chapters']) > 1:
            elements.append(Paragraph(f"Chapter {idx}", chapter_style))
            elements.append(Spacer(1, 0.2*inch))
        
        # Split text into paragraphs
        text = chapter['text']
        
        # Split by double newlines or after every ~1000 chars to avoid huge paragraphs
        paragraphs = []
        current_para = ""
        
        for line in text.split('\n'):
            if line.strip():
                current_para += line + " "
                # Break into smaller chunks if too long
                if len(current_para) > 1000:
                    paragraphs.append(current_para.strip())
                    current_para = ""
            else:
                if current_para:
                    paragraphs.append(current_para.strip())
                    current_para = ""
        
        if current_para:
            paragraphs.append(current_para.strip())
        
        # Add paragraphs to PDF
        for para in paragraphs[:500]:  # Limit to 500 paragraphs per chapter
            if para:
                # Escape special characters
                para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                # Limit paragraph length
                if len(para) > 2000:
                    para = para[:2000] + "..."
                
                try:
                    elements.append(Paragraph(para, body_style))
                except Exception as e:
                    logger.warning(f"Skipping problematic paragraph: {e}")
                    continue
        
        # Page break between chapters
        if len(book_data['chapters']) > 1 and idx < len(book_data['chapters']):
            elements.append(PageBreak())
        
        logger.info(f"Added chapter {idx}/{len(book_data['chapters'])} to PDF")
    
    # Build PDF
    logger.info("Building final PDF document")
    doc.build(elements)
    buffer.seek(0)
    
    logger.info("PDF creation complete")
    return buffer

@app.route('/convert', methods=['POST'])
def convert_epub_to_pdf():
    """Convert EPUB file to PDF"""
    temp_epub_path = None
    
    try:
        logger.info("Received conversion request")
        
        # Check if file is present
        if 'file' not in request.files:
            logger.warning("No file in request")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            logger.warning("Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            logger.warning(f"Invalid file type: {file.filename}")
            return jsonify({'error': 'Invalid file type. Only EPUB files are allowed'}), 400
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        logger.info(f"Processing file: {filename}")
        
        temp_epub = tempfile.NamedTemporaryFile(delete=False, suffix='.epub')
        temp_epub_path = temp_epub.name
        file.save(temp_epub_path)
        temp_epub.close()
        
        logger.info(f"Saved to temp file: {temp_epub_path}")
        
        # Extract EPUB content
        book_data = extract_epub_content(temp_epub_path)
        
        # Create PDF
        pdf_buffer = create_pdf(book_data)
        
        # Clean up temporary EPUB file
        if temp_epub_path and os.path.exists(temp_epub_path):
            os.unlink(temp_epub_path)
            logger.info("Cleaned up temp file")
        
        # Send PDF file
        pdf_filename = filename.rsplit('.', 1)[0] + '.pdf'
        logger.info(f"Sending PDF: {pdf_filename}")
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=pdf_filename
        )
            
    except Exception as e:
        logger.error(f"Conversion error: {str(e)}", exc_info=True)
        
        # Clean up on error
        if temp_epub_path and os.path.exists(temp_epub_path):
            try:
                os.unlink(temp_epub_path)
            except:
                pass
        
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'EPUB to PDF Converter'}), 200

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'service': 'EPUB to PDF Converter API',
        'version': '2.1',
        'endpoints': {
            '/convert': 'POST - Convert EPUB to PDF (send file as multipart/form-data)',
            '/health': 'GET - Health check'
        }
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)