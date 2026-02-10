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

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

ALLOWED_EXTENSIONS = {'epub'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_html_text(html_content):
    """Extract clean text from HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style tags
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Get text and clean it
    text = soup.get_text()
    
    # Clean up whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    
    return text

def extract_epub_content(epub_path):
    """Extract text and metadata from EPUB file"""
    book = epub.read_epub(epub_path)
    
    # Get metadata
    title = book.get_metadata('DC', 'title')
    title = title[0][0] if title else 'Untitled'
    
    author = book.get_metadata('DC', 'creator')
    author = author[0][0] if author else 'Unknown Author'
    
    # Extract all text content
    chapters = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            content = item.get_content().decode('utf-8', errors='ignore')
            
            # Check if this is a chapter (has substantial content)
            text = clean_html_text(content)
            if len(text) > 100:  # Only include if has substantial content
                chapters.append({
                    'text': text,
                    'raw_html': content
                })
    
    return {
        'title': title,
        'author': author,
        'chapters': chapters
    }

def create_pdf(book_data):
    """Create PDF from book data using ReportLab"""
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
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
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
        fontSize=16,
        textColor='#34495e',
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        textColor='#333333',
        alignment=TA_JUSTIFY,
        spaceAfter=12,
        leading=16,
        fontName='Times-Roman'
    )
    
    # Add title page
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph(book_data['title'], title_style))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph(f"by {book_data['author']}", author_style))
    elements.append(PageBreak())
    
    # Add chapters
    for idx, chapter in enumerate(book_data['chapters'], 1):
        # Add chapter number if multiple chapters
        if len(book_data['chapters']) > 1:
            elements.append(Paragraph(f"Chapter {idx}", chapter_style))
            elements.append(Spacer(1, 0.2*inch))
        
        # Split text into paragraphs
        text = chapter['text']
        paragraphs = text.split('\n\n')
        
        for para in paragraphs:
            para = para.strip()
            if para:
                # Escape special characters for ReportLab
                para = para.replace('&', '&amp;')
                para = para.replace('<', '&lt;')
                para = para.replace('>', '&gt;')
                
                # Add paragraph
                elements.append(Paragraph(para, body_style))
                elements.append(Spacer(1, 0.1*inch))
        
        # Page break between chapters if more than one
        if len(book_data['chapters']) > 1 and idx < len(book_data['chapters']):
            elements.append(PageBreak())
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer

@app.route('/convert', methods=['POST'])
def convert_epub_to_pdf():
    """Convert EPUB file to PDF"""
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only EPUB files are allowed'}), 400
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_epub = tempfile.NamedTemporaryFile(delete=False, suffix='.epub')
        file.save(temp_epub.name)
        temp_epub.close()
        
        try:
            # Extract EPUB content
            book_data = extract_epub_content(temp_epub.name)
            
            # Create PDF
            pdf_buffer = create_pdf(book_data)
            
            # Clean up temporary EPUB file
            os.unlink(temp_epub.name)
            
            # Send PDF file
            pdf_filename = filename.rsplit('.', 1)[0] + '.pdf'
            return send_file(
                pdf_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=pdf_filename
            )
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_epub.name):
                os.unlink(temp_epub.name)
            raise e
            
    except Exception as e:
        print(f"Error during conversion: {str(e)}")
        import traceback
        traceback.print_exc()
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
        'version': '2.0',
        'endpoints': {
            '/convert': 'POST - Convert EPUB to PDF (send file as multipart/form-data)',
            '/health': 'GET - Health check'
        }
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)