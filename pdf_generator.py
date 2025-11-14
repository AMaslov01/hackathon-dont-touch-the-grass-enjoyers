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
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

logger = logging.getLogger(__name__)


# Register CID fonts for Unicode (including Cyrillic) support
try:
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))  # Japanese font that supports wide Unicode
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    _FONTS_AVAILABLE = True
    logger.info("CID Unicode fonts registered")
except Exception as e:
    logger.warning(f"Could not register CID fonts: {e}")
    _FONTS_AVAILABLE = False


def clean_text_for_pdf(text: str) -> str:
    """
    Clean text for PDF generation - remove emojis and unsupported characters
    Keep Cyrillic, Latin, numbers, and basic punctuation
    """
    import re
    
    # Remove emojis and special Unicode characters
    # Keep: Cyrillic (0400-04FF), Latin (0000-007F, 0080-00FF), 
    # numbers, basic punctuation, newlines
    cleaned = re.sub(r'[^\u0000-\u007F\u0080-\u00FF\u0400-\u04FF\s\-–—.,!?:;()"\'\[\]{}@#$%^&*+=<>|~/\\\n]', '', text)
    
    # Don't replace newlines, but clean up multiple spaces on same line
    lines = cleaned.split('\n')
    lines = [re.sub(r'[ \t]+', ' ', line) for line in lines]
    cleaned = '\n'.join(lines)
    
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
        # Choose font based on availability - HeiseiMin-W3 supports Cyrillic
        font_normal = 'HeiseiMin-W3' if _FONTS_AVAILABLE else 'Helvetica'
        font_bold = 'HeiseiKakuGo-W5' if _FONTS_AVAILABLE else 'Helvetica-Bold'
        font_italic = 'HeiseiMin-W3' if _FONTS_AVAILABLE else 'Helvetica-Oblique'
        
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
        # Title - remove emoji for compatibility
        self.story.append(Paragraph("Финансовый План", self.styles['CustomTitle']))
        
        # Metadata
        date_str = datetime.now().strftime("%d.%m.%Y")
        if user_name:
            meta = f"Подготовлено для: {user_name}<br/>Дата: {date_str}"
        else:
            meta = f"Дата: {date_str}"
        
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
        # Section title (already cleaned, just format)
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
            
            # Apply text formatting (bold, italic)
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
        header = [cell.strip() for cell in lines[0].split('|') if cell.strip()]
        if not header:
            return None
        
        # Skip separator line
        data = [header]
        
        # Parse data rows
        for line in lines[2:]:  # Skip header and separator
            if '|' in line:
                row = [cell.strip() for cell in line.split('|') if cell.strip()]
                if row:
                    data.append(row)
        
        if len(data) <= 1:
            return None
        
        # Create table
        col_widths = [18*cm / len(header)] * len(header)
        table = Table(data, colWidths=col_widths)
        
        # Choose fonts - HeiseiKakuGo-W5 for bold (actually it's a different weight)
        font_bold = 'HeiseiKakuGo-W5' if _FONTS_AVAILABLE else 'Helvetica-Bold'
        font_normal = 'HeiseiMin-W3' if _FONTS_AVAILABLE else 'Helvetica'
        
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
        
        footer_text = (
            "<i>Этот финансовый план был создан автоматически на основе предоставленной вами информации. "
            "Рекомендуется проконсультироваться с профессиональным финансовым консультантом "
            "перед принятием серьезных финансовых решений.</i>"
        )
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
            
            # Add business info section (without emoji)
            self.story.append(Paragraph("Информация о бизнесе", self.styles['CustomHeading1']))
            self.story.append(Spacer(1, 6))
            
            if business_info.get('business_type'):
                text = f"<b>Тип бизнеса:</b> {business_info['business_type']}"
                self.story.append(Paragraph(text, self.styles['CustomBody']))
            
            if business_info.get('financial_situation'):
                situation = business_info['financial_situation']
                if len(situation) > 200:
                    situation = situation[:200] + '...'
                text = f"<b>Финансовая ситуация:</b> {situation}"
                self.story.append(Paragraph(text, self.styles['CustomBody']))
            
            if business_info.get('goals'):
                goals = business_info['goals']
                if len(goals) > 200:
                    goals = goals[:200] + '...'
                text = f"<b>Цели:</b> {goals}"
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

