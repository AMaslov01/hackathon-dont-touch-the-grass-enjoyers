"""
PDF Generator for Financial Plans using ReportLab
"""
import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

logger = logging.getLogger(__name__)


def download_dejavu_fonts():
    """
    Download DejaVu fonts if not found in system
    Returns the directory where fonts are stored
    """
    try:
        import urllib.request
        import zipfile
        import io
        
        fonts_dir = Path(__file__).parent / "fonts"
        fonts_dir.mkdir(exist_ok=True)
        
        # Check if fonts already downloaded
        required_fonts = [
            'DejaVuSans.ttf',
            'DejaVuSans-Bold.ttf',
            'DejaVuSans-Oblique.ttf',
            'DejaVuSans-BoldOblique.ttf'
        ]
        
        all_exist = all((fonts_dir / font).exists() for font in required_fonts)
        if all_exist:
            logger.info("DejaVu fonts already downloaded")
            return str(fonts_dir)
        
        logger.info("Downloading DejaVu fonts...")
        url = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"
        
        # Download and extract
        response = urllib.request.urlopen(url, timeout=30)
        zip_data = io.BytesIO(response.read())
        
        with zipfile.ZipFile(zip_data) as zip_file:
            for font in required_fonts:
                # Find font in zip (it's in ttf/ subdirectory)
                zip_path = f"dejavu-fonts-ttf-2.37/ttf/{font}"
                try:
                    zip_file.extract(zip_path, fonts_dir)
                    # Move from subdirectory to fonts_dir
                    extracted_path = fonts_dir / "dejavu-fonts-ttf-2.37" / "ttf" / font
                    target_path = fonts_dir / font
                    if extracted_path.exists():
                        extracted_path.rename(target_path)
                    logger.info(f"Downloaded {font}")
                except KeyError:
                    logger.warning(f"Font {font} not found in archive")
        
        # Cleanup extracted directory
        extracted_dir = fonts_dir / "dejavu-fonts-ttf-2.37"
        if extracted_dir.exists():
            import shutil
            shutil.rmtree(extracted_dir)
        
        logger.info("DejaVu fonts downloaded successfully")
        return str(fonts_dir)
        
    except Exception as e:
        logger.warning(f"Could not download DejaVu fonts: {e}")
        return None


def register_fonts():
    """
    Register fonts with Cyrillic support
    Try to use DejaVuSans (best for Cyrillic), fallback to system fonts
    """
    global _FONTS_AVAILABLE, _FONT_NORMAL, _FONT_BOLD, _FONT_ITALIC, _FONT_BOLD_ITALIC
    
    try:
        # Try to find DejaVu fonts in system or download them
        dejavu_locations = [
            # Local fonts directory (downloaded)
            str(Path(__file__).parent / "fonts"),
            # Common Linux locations
            '/usr/share/fonts/truetype/dejavu',
            # macOS locations
            '/System/Library/Fonts/Supplemental',
            '/Library/Fonts',
            # Windows locations
            'C:/Windows/Fonts',
        ]
        
        # Try to download fonts if not found
        downloaded_dir = download_dejavu_fonts()
        if downloaded_dir and downloaded_dir not in dejavu_locations:
            dejavu_locations.insert(0, downloaded_dir)
        
        dejavu_files = {
            'normal': 'DejaVuSans.ttf',
            'bold': 'DejaVuSans-Bold.ttf',
            'italic': 'DejaVuSans-Oblique.ttf',
            'bolditalic': 'DejaVuSans-BoldOblique.ttf'
        }
        
        fonts_found = {}
        
        # Search for fonts in all locations
        for location in dejavu_locations:
            if not os.path.exists(location):
                continue
            
            for style, filename in dejavu_files.items():
                if style in fonts_found:
                    continue  # Already found
                
                font_path = os.path.join(location, filename)
                if os.path.exists(font_path):
                    try:
                        font_name = f'DejaVuSans-{style.capitalize()}'
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                        fonts_found[style] = font_name
                        logger.info(f"Registered {font_name} from {font_path}")
                    except Exception as e:
                        logger.warning(f"Could not register {font_path}: {e}")
        
        # Check if we have at least normal and bold
        if 'normal' in fonts_found and 'bold' in fonts_found:
            # Register font family
            try:
                registerFontFamily('DejaVuSans',
                                 normal=fonts_found.get('normal', 'DejaVuSans-Normal'),
                                 bold=fonts_found.get('bold', 'DejaVuSans-Bold'),
                                 italic=fonts_found.get('italic', 'DejaVuSans-Normal'),
                                 boldItalic=fonts_found.get('bolditalic', 'DejaVuSans-Bold'))
            except:
                pass
            
            _FONT_NORMAL = fonts_found.get('normal', 'DejaVuSans-Normal')
            _FONT_BOLD = fonts_found.get('bold', 'DejaVuSans-Bold')
            _FONT_ITALIC = fonts_found.get('italic', _FONT_NORMAL)
            _FONT_BOLD_ITALIC = fonts_found.get('bolditalic', _FONT_BOLD)
            _FONTS_AVAILABLE = True
            logger.info("DejaVuSans fonts successfully registered")
            return True
        
        # Try Arial Unicode (macOS fallback)
        arial_unicode_paths = [
            '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
            '/Library/Fonts/Arial Unicode.ttf'
        ]
        
        for arial_path in arial_unicode_paths:
            if os.path.exists(arial_path):
                pdfmetrics.registerFont(TTFont('ArialUnicode', arial_path))
                _FONT_NORMAL = 'ArialUnicode'
                _FONT_BOLD = 'ArialUnicode'
                _FONT_ITALIC = 'ArialUnicode'
                _FONT_BOLD_ITALIC = 'ArialUnicode'
                _FONTS_AVAILABLE = True
                logger.info("Arial Unicode font registered")
                return True
        
        raise Exception("No suitable Unicode fonts found")
        
    except Exception as e:
        logger.warning(f"Could not register Unicode fonts: {e}")
        logger.warning("Falling back to Helvetica (Cyrillic may not display correctly)")
        _FONT_NORMAL = 'Helvetica'
        _FONT_BOLD = 'Helvetica-Bold'
        _FONT_ITALIC = 'Helvetica-Oblique'
        _FONT_BOLD_ITALIC = 'Helvetica-BoldOblique'
        _FONTS_AVAILABLE = False
        return False


# Global font variables
_FONTS_AVAILABLE = False
_FONT_NORMAL = 'Helvetica'
_FONT_BOLD = 'Helvetica-Bold'
_FONT_ITALIC = 'Helvetica-Oblique'
_FONT_BOLD_ITALIC = 'Helvetica-BoldOblique'

# Try to register fonts on import
register_fonts()


def clean_text_for_pdf(text: str) -> str:
    """
    Clean text for PDF generation - remove emojis and unsupported characters
    Keep Cyrillic, Latin, numbers, and basic punctuation
    """
    import re
    
    # First, remove BOM and other invisible characters
    # Remove BOM (Byte Order Mark)
    text = text.replace('\ufeff', '')
    # Remove zero-width spaces and joiners
    text = text.replace('\u200b', '')  # Zero-width space
    text = text.replace('\u200c', '')  # Zero-width non-joiner
    text = text.replace('\u200d', '')  # Zero-width joiner
    text = text.replace('\ufff9', '')  # Interlinear annotation anchor
    text = text.replace('\ufffa', '')  # Interlinear annotation separator
    text = text.replace('\ufffb', '')  # Interlinear annotation terminator
    
    # Remove control characters (except newlines and tabs)
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    # Remove emojis and special Unicode characters
    # Keep: Cyrillic (0400-04FF), Latin (0000-007F, 0080-00FF), 
    # Extended Latin (0100-017F), numbers, basic punctuation, newlines
    # Currency symbols: Euro (20AC), Ruble (20BD), Dollar, etc.
    # Common special chars: dashes (2013-2015), quotes (2018-201D), bullet (2022)
    cleaned = re.sub(
        r'[^\u0000-\u007F\u0080-\u00FF\u0100-\u017F\u0400-\u04FF'
        r'\u2013-\u2015\u2018-\u201D\u2020-\u2022\u20AC\u20BD'
        r'\s\-.,!?:;()"\'\[\]{}@#№$%^&*+=<>|~/\\\n]', 
        '', text)
    
    # Clean up whitespace - normalize spaces but keep single spaces between words
    lines = cleaned.split('\n')
    lines = [' '.join(line.split()) for line in lines]  # This properly normalizes spaces
    cleaned = '\n'.join(lines)
    
    # Final strip to remove leading/trailing whitespace
    return cleaned.strip()


def format_text_for_pdf(text: str) -> str:
    """
    Convert markdown-like formatting to ReportLab HTML tags
    Handles: **bold**, *italic*, __bold__, _italic_
    """
    import re
    
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    
    # Italic: *text* or _text_ (but not in URLs or after numbers)
    text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<i>\1</i>', text)
    
    return text


class FinancialPlanPDF:
    """Generate professional financial plan PDFs"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        self.story = []
        
    def _setup_styles(self):
        """Setup custom styles for the document"""
        # Use registered fonts (DejaVuSans or fallback to Helvetica)
        font_normal = _FONT_NORMAL
        font_bold = _FONT_BOLD
        font_italic = _FONT_ITALIC
        
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a472a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName=font_bold
        ))
        
        # Heading 1
        self.styles.add(ParagraphStyle(
            name='CustomHeading1',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#2e7d32'),
            spaceAfter=12,
            spaceBefore=12,
            fontName=font_bold
        ))
        
        # Heading 2
        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#388e3c'),
            spaceAfter=10,
            spaceBefore=10,
            fontName=font_bold
        ))
        
        # Body text
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['BodyText'],
            fontSize=11,
            leading=16,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
            fontName=font_normal
        ))
        
        # Bullet points
        self.styles.add(ParagraphStyle(
            name='CustomBullet',
            parent=self.styles['BodyText'],
            fontSize=10,
            leading=14,
            leftIndent=20,
            spaceAfter=6,
            fontName=font_normal
        ))
    
    def _add_header(self, user_name: str = None):
        """Add document header"""
        # Title - clean text to avoid special characters
        title = clean_text_for_pdf("Финансовый План")
        self.story.append(Paragraph(title, self.styles['CustomTitle']))
        
        # Metadata
        date_str = datetime.now().strftime("%d.%m.%Y")
        meta = f"{date_str}"
        
        # Note: meta contains HTML tags (<br/>), don't clean it
        self.story.append(Paragraph(meta, self.styles['Normal']))
        self.story.append(Spacer(1, 20))
        
        # Separator line
        line_table = Table([['']], colWidths=[18*cm])
        line_table.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#2e7d32')),
        ]))
        self.story.append(line_table)
        self.story.append(Spacer(1, 20))
    
    def _parse_ai_response(self, ai_response: str) -> Dict:
        """Parse AI response into structured sections"""
        sections = {}
        current_section = None
        current_content = []
        
        lines = ai_response.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a section header
            if line.startswith('#'):
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                
                # Start new section
                current_section = line.lstrip('#').strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def _add_section(self, title: str, content: str, level: int = 1):
        """Add a section to the document"""
        # Section title - clean and format
        title = clean_text_for_pdf(title)
        title = format_text_for_pdf(title)
        style_name = f'CustomHeading{level}' if level <= 2 else 'CustomBody'
        self.story.append(Paragraph(title, self.styles[style_name]))
        self.story.append(Spacer(1, 6))
        
        # Process content
        paragraphs = content.split('\n')
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Clean and apply text formatting (bold, italic)
            para = clean_text_for_pdf(para)
            para = format_text_for_pdf(para)
            
            # Detect indentation level for nested lists
            indent_level = 0
            original_para = para
            while para.startswith('  '):
                indent_level += 1
                para = para[2:]
            para = para.strip()
            
            # Check if it's a bullet point
            if para.startswith(('-', '•', '*')):
                para = '• ' + para.lstrip('-•* ')
                # Create indented style if needed
                if indent_level > 0:
                    style = ParagraphStyle(
                        name=f'IndentedBullet{indent_level}',
                        parent=self.styles['CustomBullet'],
                        leftIndent=20 + (indent_level * 15)
                    )
                    self.story.append(Paragraph(para, style))
                else:
                    self.story.append(Paragraph(para, self.styles['CustomBullet']))
            elif para.startswith(tuple(str(i) + '.' for i in range(1, 10))):
                # Numbered list
                if indent_level > 0:
                    style = ParagraphStyle(
                        name=f'IndentedNumbered{indent_level}',
                        parent=self.styles['CustomBullet'],
                        leftIndent=20 + (indent_level * 15)
                    )
                    self.story.append(Paragraph(para, style))
                else:
                    self.story.append(Paragraph(para, self.styles['CustomBullet']))
            else:
                # Regular paragraph
                self.story.append(Paragraph(para, self.styles['CustomBody']))
        
        self.story.append(Spacer(1, 12))
    
    def _parse_table(self, table_text: str) -> Optional[Table]:
        """Parse markdown-style table from text"""
        lines = [line.strip() for line in table_text.split('\n') if line.strip()]
        if len(lines) < 2:
            return None
        
        # Parse header
        header = [clean_text_for_pdf(cell.strip()) for cell in lines[0].split('|') if cell.strip()]
        if not header:
            return None
        
        # Skip separator line
        data = [header]
        
        # Parse data rows
        for line in lines[2:]:  # Skip header and separator
            if '|' in line:
                row = [clean_text_for_pdf(cell.strip()) for cell in line.split('|') if cell.strip()]
                if row:
                    data.append(row)
        
        if len(data) <= 1:
            return None
        
        # Create table
        col_widths = [18*cm / len(header)] * len(header)
        table = Table(data, colWidths=col_widths)
        
        # Use registered fonts
        font_bold = _FONT_BOLD
        font_normal = _FONT_NORMAL
        
        # Style table
        table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e7d32')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Body style
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), font_normal),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            
            # Padding
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        return table
    
    def _add_footer(self):
        """Add document footer"""
        self.story.append(Spacer(1, 20))
        
        # Clean the text content but preserve HTML tags
        footer_content = clean_text_for_pdf(
            'AI-generated. For reference only.'
        )
        footer_text = f"<i>{footer_content}</i>"
        self.story.append(Paragraph(footer_text, self.styles['Normal']))
    
    def generate(self, 
                 ai_response: str, 
                 business_info: Dict,
                 user_name: str = None,
                 output_path: str = None) -> str:
        """
        Generate PDF from AI response
        
        Args:
            ai_response: Structured AI response with financial plan
            business_info: Business information dictionary
            user_name: Optional user name for personalization
            output_path: Optional custom output path
            
        Returns:
            Path to generated PDF file
        """
        try:
            # Clean text from emojis and unsupported characters
            ai_response = clean_text_for_pdf(ai_response)
            if user_name:
                user_name = clean_text_for_pdf(user_name)
            
            # Clean business info
            cleaned_business_info = {}
            for key, value in business_info.items():
                if isinstance(value, str):
                    cleaned_business_info[key] = clean_text_for_pdf(value)
                else:
                    cleaned_business_info[key] = value
            business_info = cleaned_business_info
            
            # Setup output path
            if not output_path:
                output_dir = Path(__file__).parent / "temp_pdfs"
                output_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = output_dir / f"financial_plan_{timestamp}.pdf"
            
            # Create document
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )
            
            # Build story
            self.story = []
            self._add_header(user_name)
            
            # Add business info section - clean all text
            heading = clean_text_for_pdf("Информация о бизнесе")
            self.story.append(Paragraph(heading, self.styles['CustomHeading1']))
            self.story.append(Spacer(1, 6))
            
            if business_info.get('business_type'):
                label = clean_text_for_pdf("Тип бизнеса:")
                text = f"<b>{label}</b> {business_info['business_type']}"
                self.story.append(Paragraph(text, self.styles['CustomBody']))
            
            if business_info.get('financial_situation'):
                situation = business_info['financial_situation']
                if len(situation) > 200:
                    situation = situation[:200] + '...'
                label = clean_text_for_pdf("Финансовая ситуация:")
                text = f"<b>{label}</b> {situation}"
                self.story.append(Paragraph(text, self.styles['CustomBody']))
            
            if business_info.get('goals'):
                goals = business_info['goals']
                if len(goals) > 200:
                    goals = goals[:200] + '...'
                label = clean_text_for_pdf("Цели:")
                text = f"<b>{label}</b> {goals}"
                self.story.append(Paragraph(text, self.styles['CustomBody']))
            
            self.story.append(Spacer(1, 20))
            
            # Parse and add AI response sections
            sections = self._parse_ai_response(ai_response)
            
            for section_title, section_content in sections.items():
                # Check if section contains a table
                if '|' in section_content and section_content.count('|') > 3:
                    # Add section title
                    self.story.append(Paragraph(section_title, self.styles['CustomHeading1']))
                    self.story.append(Spacer(1, 6))
                    
                    # Try to parse table
                    table = self._parse_table(section_content)
                    if table:
                        self.story.append(table)
                        self.story.append(Spacer(1, 12))
                    else:
                        # If table parsing failed, add as regular text
                        self._add_section(section_title, section_content, level=1)
                else:
                    # Regular section
                    self._add_section(section_title, section_content, level=1)
            
            # If no sections were parsed, add the whole response
            if not sections:
                self._add_section("Финансовый план", ai_response, level=1)
            
            # Add footer
            self._add_footer()
            
            # Build PDF
            doc.build(self.story)
            
            logger.info(f"PDF generated successfully: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error generating PDF: {e}", exc_info=True)
            raise
    
    def cleanup_old_pdfs(self, max_age_hours: int = 24):
        """Clean up old temporary PDF files"""
        try:
            temp_dir = Path(__file__).parent / "temp_pdfs"
            if not temp_dir.exists():
                return
            
            now = datetime.now()
            for pdf_file in temp_dir.glob("financial_plan_*.pdf"):
                file_age = now - datetime.fromtimestamp(pdf_file.stat().st_mtime)
                if file_age.total_seconds() > max_age_hours * 3600:
                    pdf_file.unlink()
                    logger.info(f"Deleted old PDF: {pdf_file}")
        except Exception as e:
            logger.warning(f"Error cleaning up old PDFs: {e}")


# Global PDF generator instance
pdf_generator = FinancialPlanPDF()
