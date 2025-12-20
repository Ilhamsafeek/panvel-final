# =====================================================
# FILE: app/utils/document_parser.py
# Enhanced Document Parser with Better Formatting
# pip install pdfplumber python-docx PyPDF2
# =====================================================

import logging
import re
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class DocumentParser:
    """Extract formatted text from uploaded documents with layout preservation"""
    
    @staticmethod
    def extract_text(file_path: str) -> str:
        """Extract text based on file extension"""
        ext = Path(file_path).suffix.lower()
        
        logger.info(f"📄 Extracting content from: {file_path} (type: {ext})")
        
        if ext == '.pdf':
            return DocumentParser.extract_text_from_pdf(file_path)
        elif ext in ['.docx']:
            return DocumentParser.extract_text_from_docx(file_path)
        elif ext == '.doc':
            return DocumentParser.extract_text_from_doc(file_path)
        elif ext == '.txt':
            return DocumentParser.extract_text_from_txt(file_path)
        else:
            return f"<p>Unsupported file type: {ext}</p>"
    
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Extract text from PDF with formatting preservation"""
        
        # Try pdfplumber first (best formatting)
        try:
            result = DocumentParser._extract_with_pdfplumber(file_path)
            if result and len(result.strip()) > 100:
                logger.info(f"✅ pdfplumber extracted {len(result)} characters")
                return result
        except ImportError:
            logger.warning("⚠️ pdfplumber not installed, falling back to PyPDF2")
        except Exception as e:
            logger.warning(f"⚠️ pdfplumber failed: {e}")
        
        # Fallback to PyPDF2
        try:
            result = DocumentParser._extract_with_pypdf2(file_path)
            if result:
                logger.info(f"✅ PyPDF2 extracted {len(result)} characters")
                return result
        except Exception as e:
            logger.error(f"❌ PyPDF2 failed: {e}")
        
        return "<p>Unable to extract text from this PDF.</p>"
    
    @staticmethod
    def _extract_with_pdfplumber(file_path: str) -> str:
        """Extract using pdfplumber with full formatting preservation"""
        import pdfplumber
        
        all_content = []
        
        with pdfplumber.open(file_path) as pdf:
            num_pages = len(pdf.pages)
            logger.info(f"📄 PDF has {num_pages} pages")
            
            for page_num, page in enumerate(pdf.pages, 1):
                page_content = []
                
                # Get page dimensions for layout analysis
                page_width = page.width
                page_height = page.height
                
                # ===== EXTRACT TABLES FIRST =====
                tables = page.extract_tables({
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "intersection_tolerance": 5
                })
                
                table_bboxes = []
                if tables:
                    # Get table bounding boxes to exclude from text extraction
                    for table in page.find_tables():
                        table_bboxes.append(table.bbox)
                    
                    # Convert tables to HTML
                    for table_data in tables:
                        if table_data and len(table_data) > 0:
                            table_html = DocumentParser._table_to_styled_html(table_data)
                            page_content.append(table_html)
                
                # ===== EXTRACT TEXT WITH LAYOUT =====
                # Extract words with positioning
                words = page.extract_words(
                    keep_blank_chars=True,
                    x_tolerance=3,
                    y_tolerance=3,
                    extra_attrs=['fontname', 'size']
                )
                
                if words:
                    # Filter out words that are inside tables
                    filtered_words = []
                    for word in words:
                        in_table = False
                        for bbox in table_bboxes:
                            if (word['x0'] >= bbox[0] and word['x1'] <= bbox[2] and
                                word['top'] >= bbox[1] and word['bottom'] <= bbox[3]):
                                in_table = True
                                break
                        if not in_table:
                            filtered_words.append(word)
                    
                    # Group words into lines based on Y position
                    lines = DocumentParser._group_words_into_lines(filtered_words)
                    
                    # Detect columns
                    is_multi_column = DocumentParser._detect_columns(filtered_words, page_width)
                    
                    # Format lines with styling
                    formatted_text = DocumentParser._format_lines_with_style(
                        lines, page_width, is_multi_column
                    )
                    page_content.append(formatted_text)
                
                # Wrap page content (clean, no shadows or page numbers)
                if page_content:
                    all_content.append(''.join(page_content))
        
        return '\n'.join(all_content)
    
    @staticmethod
    def _group_words_into_lines(words: List[dict]) -> List[List[dict]]:
        """Group words into lines based on Y position"""
        if not words:
            return []
        
        # Sort by Y position (top), then X position
        sorted_words = sorted(words, key=lambda w: (round(w['top'], 1), w['x0']))
        
        lines = []
        current_line = [sorted_words[0]]
        current_y = sorted_words[0]['top']
        
        for word in sorted_words[1:]:
            # If Y position is close enough, same line (tolerance based on font size)
            y_tolerance = word.get('size', 12) * 0.5
            if abs(word['top'] - current_y) <= y_tolerance:
                current_line.append(word)
            else:
                # Sort current line by X position and save
                current_line.sort(key=lambda w: w['x0'])
                lines.append(current_line)
                current_line = [word]
                current_y = word['top']
        
        # Don't forget the last line
        if current_line:
            current_line.sort(key=lambda w: w['x0'])
            lines.append(current_line)
        
        return lines
    
    @staticmethod
    def _detect_columns(words: List[dict], page_width: float) -> bool:
        """Detect if page has multiple columns"""
        if not words or len(words) < 20:
            return False
        
        # Get X positions of word starts
        x_positions = [w['x0'] for w in words]
        
        # Check if there's a significant gap in the middle
        mid_point = page_width / 2
        left_count = sum(1 for x in x_positions if x < mid_point - 50)
        right_count = sum(1 for x in x_positions if x > mid_point + 50)
        
        # If both sides have significant content, likely multi-column
        total = len(x_positions)
        if left_count > total * 0.3 and right_count > total * 0.3:
            return True
        
        return False
    
    @staticmethod
    def _format_lines_with_style(lines: List[List[dict]], page_width: float, 
                                  is_multi_column: bool) -> str:
        """Format lines with proper HTML styling based on font analysis"""
        if not lines:
            return ""
        
        formatted_parts = []
        
        # Analyze font sizes to determine hierarchy
        all_sizes = []
        for line in lines:
            for word in line:
                size = word.get('size', 12)
                if size:
                    all_sizes.append(size)
        
        if all_sizes:
            avg_size = sum(all_sizes) / len(all_sizes)
            max_size = max(all_sizes)
        else:
            avg_size = 12
            max_size = 12
        
        for line in lines:
            if not line:
                continue
            
            # Get line text
            line_text = ' '.join(w['text'] for w in line)
            line_text = line_text.strip()
            
            if not line_text:
                continue
            
            # Escape HTML
            line_text = line_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Analyze line properties
            line_x = line[0]['x0']
            avg_font_size = sum(w.get('size', 12) for w in line) / len(line)
            font_name = line[0].get('fontname', '').lower()
            
            # Determine if bold (font name contains 'bold' or 'heavy')
            is_bold = 'bold' in font_name or 'heavy' in font_name or 'black' in font_name
            
            # Determine style based on analysis
            style = DocumentParser._determine_line_style(
                line_text, avg_font_size, avg_size, max_size, 
                is_bold, line_x, page_width
            )
            
            formatted_parts.append(f'<{style["tag"]} style="{style["css"]}">{line_text}</{style["tag"]}>')
        
        return '\n'.join(formatted_parts)
    
    @staticmethod
    def _determine_line_style(text: str, font_size: float, avg_size: float, 
                               max_size: float, is_bold: bool, 
                               x_pos: float, page_width: float) -> dict:
        """Determine HTML tag and CSS style for a line"""
        
        # Check for main title (largest font, near top)
        if font_size >= max_size * 0.9 and font_size > avg_size * 1.3:
            return {
                "tag": "h1",
                "css": "font-size: 24px; font-weight: bold; color: #1a365d; "
                       "margin: 25px 0 15px 0; padding-bottom: 10px; "
                       "border-bottom: 2px solid #2762cb;"
            }
        
        # Check for section headers (larger than average, bold, or all caps)
        if (font_size > avg_size * 1.15 or is_bold or text.isupper()) and len(text) < 100:
            # Numbered section (1. INTRODUCTION, 2.1 Scope)
            if re.match(r'^[\d]+\.[\d]*\.?\s+', text):
                return {
                    "tag": "h3",
                    "css": "font-size: 16px; font-weight: bold; color: #2d3748; "
                           "margin: 20px 0 10px 0;"
                }
            
            # ARTICLE, SECTION, CHAPTER headers
            if re.match(r'^(ARTICLE|SECTION|CHAPTER|PART|SCHEDULE|EXHIBIT)\s+', text, re.I):
                return {
                    "tag": "h2",
                    "css": "font-size: 18px; font-weight: bold; color: #1a5f7a; "
                           "margin: 30px 0 15px 0; padding: 10px 0; "
                           "border-bottom: 1px solid #1a5f7a;"
                }
            
            # All caps header
            if text.isupper() and len(text.split()) < 10:
                return {
                    "tag": "h3",
                    "css": "font-size: 15px; font-weight: bold; color: #2762cb; "
                           "margin: 20px 0 10px 0; text-transform: uppercase; "
                           "letter-spacing: 0.5px;"
                }
            
            # Bold subheading
            if is_bold:
                return {
                    "tag": "h4",
                    "css": "font-size: 14px; font-weight: bold; color: #333; "
                           "margin: 15px 0 8px 0;"
                }
        
        # Check for list items
        indent = ""
        if x_pos > 70:  # Indented text
            indent_level = min(int((x_pos - 50) / 20), 4)
            indent = f"margin-left: {indent_level * 25}px; "
        
        # Numbered list (1., 2., etc.)
        if re.match(r'^[\d]+[\.\)]\s+', text):
            return {
                "tag": "p",
                "css": f"{indent}margin-bottom: 8px; padding-left: 10px; "
                       "border-left: 3px solid #e2e8f0;"
            }
        
        # Lettered list (a., b., etc.)
        if re.match(r'^[a-z][\.\)]\s+', text, re.I):
            return {
                "tag": "p",
                "css": f"margin-left: {max(int(x_pos/3), 30)}px; margin-bottom: 6px;"
            }
        
        # Roman numeral list
        if re.match(r'^[\(]?[ivxIVX]+[\.\)]\s+', text):
            return {
                "tag": "p",
                "css": f"margin-left: {max(int(x_pos/3), 45)}px; margin-bottom: 6px;"
            }
        
        # Bullet points
        if re.match(r'^[•\-\*\►\➢]\s*', text):
            clean_text = re.sub(r'^[•\-\*\►\➢]\s*', '• ', text)
            return {
                "tag": "p",
                "css": f"{indent}margin-bottom: 6px; padding-left: 15px;"
            }
        
        # Definition line (Term: Definition)
        if ':' in text and 5 < text.index(':') < 40:
            return {
                "tag": "p",
                "css": f"{indent}margin-bottom: 10px; line-height: 1.6;"
            }
        
        # Regular paragraph
        return {
            "tag": "p",
            "css": f"{indent}margin-bottom: 12px; line-height: 1.7; "
                   "text-align: justify; color: #333;"
        }
    
    @staticmethod
    def _table_to_styled_html(table_data: List[List]) -> str:
        """Convert table data to styled HTML"""
        if not table_data:
            return ""
        
        html = '''
        <table style="
            width: 100%; 
            border-collapse: collapse; 
            margin: 20px 0; 
            font-size: 13px;
            border: 1px solid #d1d5db;
        ">
        '''
        
        for i, row in enumerate(table_data):
            if not row:
                continue
            
            html += '<tr>'
            for j, cell in enumerate(row):
                tag = 'th' if i == 0 else 'td'
                cell_text = str(cell) if cell else ''
                cell_text = cell_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                if i == 0:  # Header row
                    style = '''
                        padding: 12px 10px;
                        background: #f8fafc;
                        border: 1px solid #d1d5db;
                        font-weight: 600;
                        color: #1e293b;
                        text-align: left;
                    '''
                else:
                    bg = '#fff' if i % 2 == 1 else '#f9fafb'
                    style = f'''
                        padding: 10px;
                        background: {bg};
                        border: 1px solid #e5e7eb;
                        color: #374151;
                    '''
                
                html += f'<{tag} style="{style}">{cell_text}</{tag}>'
            html += '</tr>'
        
        html += '</table>'
        return html
    
    @staticmethod
    def _extract_with_pypdf2(file_path: str) -> str:
        """Fallback extraction using PyPDF2"""
        import PyPDF2
        
        text_content = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            logger.info(f"📄 PDF has {num_pages} pages (PyPDF2 fallback)")
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                text = page.extract_text()
                if text:
                    formatted = DocumentParser._format_basic_text(text)
                    text_content.append(formatted)
        
        return '\n'.join(text_content)
    
    @staticmethod
    def _format_basic_text(text: str) -> str:
        """Basic text formatting for PyPDF2 fallback"""
        lines = text.split('\n')
        formatted = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Headers
            if line.isupper() and len(line) < 80 and len(line.split()) < 10:
                formatted.append(f'<h3 style="font-weight: bold; color: #2762cb; margin: 15px 0 8px 0;">{line}</h3>')
            elif re.match(r'^[\d]+\.', line) and len(line) < 80:
                formatted.append(f'<h4 style="font-weight: bold; margin: 12px 0 6px 0;">{line}</h4>')
            elif re.match(r'^[•\-\*]\s*', line):
                formatted.append(f'<p style="margin-left: 20px; margin-bottom: 6px;">{line}</p>')
            else:
                formatted.append(f'<p style="margin-bottom: 10px; line-height: 1.6;">{line}</p>')
        
        return '\n'.join(formatted)
    
    # ===== DOCX EXTRACTION =====
    
    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """Extract text from DOCX with formatting"""
        try:
            import docx
            from docx.oxml.text.paragraph import CT_P
            from docx.oxml.table import CT_Tbl
            from docx.table import Table
            from docx.text.paragraph import Paragraph
            from docx.shared import Pt
            
            doc = docx.Document(file_path)
            html_parts = []
            
            for element in doc.element.body:
                if isinstance(element, CT_P):
                    paragraph = Paragraph(element, doc)
                    html = DocumentParser._docx_para_to_html(paragraph)
                    if html:
                        html_parts.append(html)
                elif isinstance(element, CT_Tbl):
                    table = Table(element, doc)
                    html = DocumentParser._docx_table_to_html(table)
                    if html:
                        html_parts.append(html)
            
            result = '\n'.join(html_parts)
            logger.info(f"✅ DOCX extracted {len(result)} characters")
            return result
            
        except Exception as e:
            logger.error(f"❌ DOCX extraction error: {e}")
            return f"<p>Error extracting DOCX: {str(e)}</p>"
    
    @staticmethod
    def _docx_para_to_html(paragraph) -> str:
        """Convert DOCX paragraph to styled HTML"""
        text = paragraph.text.strip()
        if not text:
            return ""
        
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        style_name = paragraph.style.name if paragraph.style else ""
        
        # Headings
        if style_name.startswith('Heading'):
            try:
                level = int(style_name.replace('Heading ', '').strip())
                level = min(level, 6)
            except:
                level = 3
            
            colors = {1: '#1a365d', 2: '#1a5f7a', 3: '#2762cb', 4: '#333'}
            sizes = {1: '22px', 2: '18px', 3: '16px', 4: '14px'}
            
            return f'''<h{level} style="
                font-size: {sizes.get(level, '14px')}; 
                font-weight: bold; 
                color: {colors.get(level, '#333')}; 
                margin: 20px 0 10px 0;
            ">{text}</h{level}>'''
        
        # Lists
        if 'List' in style_name:
            return f'<p style="margin-left: 25px; margin-bottom: 8px;">• {text}</p>'
        
        # Check for inline formatting
        formatted_text = text
        for run in paragraph.runs:
            run_text = run.text
            if run.bold and run_text:
                run_text_escaped = run_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                formatted_text = formatted_text.replace(
                    run_text_escaped, 
                    f'<strong>{run_text_escaped}</strong>'
                )
            if run.italic and run_text:
                run_text_escaped = run_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                formatted_text = formatted_text.replace(
                    run_text_escaped,
                    f'<em>{run_text_escaped}</em>'
                )
        
        return f'<p style="margin-bottom: 12px; line-height: 1.7; text-align: justify;">{formatted_text}</p>'
    
    @staticmethod
    def _docx_table_to_html(table) -> str:
        """Convert DOCX table to styled HTML"""
        rows_html = []
        
        for i, row in enumerate(table.rows):
            cells_html = []
            for cell in row.cells:
                tag = 'th' if i == 0 else 'td'
                cell_text = ' '.join(p.text.strip() for p in cell.paragraphs if p.text.strip())
                cell_text = cell_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                style = 'padding: 10px; border: 1px solid #d1d5db;'
                if i == 0:
                    style += ' background: #f8fafc; font-weight: 600;'
                
                cells_html.append(f'<{tag} style="{style}">{cell_text}</{tag}>')
            
            rows_html.append(f'<tr>{"".join(cells_html)}</tr>')
        
        return f'''
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0; border: 1px solid #d1d5db;">
            {"".join(rows_html)}
        </table>
        '''
    
    # ===== TXT & DOC =====
    
    @staticmethod
    def extract_text_from_txt(file_path: str) -> str:
        """Extract from plain text files"""
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                
                content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                paragraphs = content.split('\n\n')
                
                html_parts = []
                for para in paragraphs:
                    if para.strip():
                        lines = para.split('\n')
                        formatted = '<br>'.join(line for line in lines if line.strip())
                        html_parts.append(f'<p style="margin-bottom: 12px; line-height: 1.6;">{formatted}</p>')
                
                return '\n'.join(html_parts)
            except UnicodeDecodeError:
                continue
        
        return "<p>Unable to read text file.</p>"
    
    @staticmethod
    def extract_text_from_doc(file_path: str) -> str:
        """Extract from legacy .doc files"""
        return "<p>Legacy .doc format detected. Please convert to .docx for better results.</p>"