from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import ebooklib
from ebooklib import epub
from weasyprint import HTML, CSS
from bs4 import BeautifulSoup
import io
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

ALLOWED_EXTENSIONS = {'epub'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_epub_content(epub_path):
    """Extract text and structure from EPUB file"""
    book = epub.read_epub(epub_path)
    
    # Get metadata
    title = book.get_metadata('DC', 'title')
    title = title[0][0] if title else 'Untitled'
    
    author = book.get_metadata('DC', 'creator')
    author = author[0][0] if author else 'Unknown Author'
    
    # Extract all text content
    content_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: 'Georgia', 'Times New Roman', serif;
                line-height: 1.6;
                color: #333;
                font-size: 12pt;
            }}
            h1 {{
                font-size: 24pt;
                margin-top: 0;
                margin-bottom: 0.5em;
                color: #2c3e50;
                page-break-before: always;
            }}
            h1:first-of-type {{
                page-break-before: avoid;
            }}
            h2 {{
                font-size: 18pt;
                margin-top: 1em;
                margin-bottom: 0.5em;
                color: #34495e;
            }}
            h3 {{
                font-size: 14pt;
                margin-top: 0.8em;
                margin-bottom: 0.4em;
                color: #34495e;
            }}
            p {{
                margin: 0.5em 0;
                text-align: justify;
            }}
            .title-page {{
                text-align: center;
                margin-top: 5cm;
            }}
            .book-title {{
                font-size: 28pt;
                font-weight: bold;
                margin-bottom: 1em;
            }}
            .book-author {{
                font-size: 18pt;
                font-style: italic;
                color: #7f8c8d;
            }}
            img {{
                max-width: 100%;
                height: auto;
            }}
        </style>
    </head>
    <body>
        <div class="title-page">
            <div class="book-title">{title}</div>
            <div class="book-author">{author}</div>
        </div>
    """
    
    # Process all document items
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            # Remove script and style tags
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            content_html += str(soup)
    
    content_html += "</body></html>"
    
    return content_html

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
            html_content = extract_epub_content(temp_epub.name)
            
            # Convert to PDF
            pdf_buffer = io.BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)
            
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
        'endpoints': {
            '/convert': 'POST - Convert EPUB to PDF',
            '/health': 'GET - Health check'
        }
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)