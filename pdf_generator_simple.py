"""
Simplified PDF Generator using WeasyPrint
Much simpler alternative to custom ReportLab implementation
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

try:
    from weasyprint import HTML, CSS
    import markdown
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logging.warning("WeasyPrint not installed. Install: pip install weasyprint markdown")

logger = logging.getLogger(__name__)


def remove_emojis(text: str) -> str:
    """
    Remove emojis from text for better PDF compatibility
    WeasyPrint doesn't handle emojis well, so we remove them
    """
    if not text:
        return text
    
    import re
    
    # Remove emojis using regex
    # This pattern matches most common emoji ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U00002600-\U000026FF"  # Miscellaneous Symbols
        "]+",
        flags=re.UNICODE
    )
    
    return emoji_pattern.sub('', text)


# CSS стили для красивого PDF
PDF_CSS = """
@page {
    size: A4;
    margin: 2cm;
}

body {
    font-family: 'DejaVu Sans', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
}

h1 {
    color: #1a472a;
    font-size: 24pt;
    text-align: center;
    margin-bottom: 20pt;
}

h2 {
    color: #2e7d32;
    font-size: 16pt;
    margin-top: 20pt;
    margin-bottom: 10pt;
}

h3 {
    color: #388e3c;
    font-size: 14pt;
    margin-top: 15pt;
    margin-bottom: 8pt;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 15pt 0;
}

th {
    background-color: #2e7d32;
    color: white;
    padding: 10pt;
    text-align: left;
}

td {
    padding: 8pt;
    border: 1pt solid #ccc;
}

tr:nth-child(even) {
    background-color: #f5f5f5;
}

ul, ol {
    margin: 10pt 0;
    padding-left: 25pt;
}

li {
    margin: 5pt 0;
}

.metadata {
    text-align: center;
    color: #666;
    margin-bottom: 20pt;
}

.footer {
    text-align: center;
    color: #999;
    font-size: 9pt;
    margin-top: 30pt;
    font-style: italic;
}
"""


class SimpleFinancialPlanPDF:
    """Simplified PDF generator using WeasyPrint"""
    
    def generate(self, ai_response: str, business_info: Dict, 
                 user_name: str = None, output_path: str = None) -> str:
        """
        Generate PDF from AI response (Markdown)
        
        Args:
            ai_response: AI-generated financial plan in Markdown
            business_info: Business information dictionary
            user_name: Optional user name
            output_path: Optional custom output path
            
        Returns:
            Path to generated PDF file
        """
        if not WEASYPRINT_AVAILABLE:
            raise ImportError("WeasyPrint not installed. Run: pip install weasyprint markdown")
        
        try:
            # Setup output path
            if not output_path:
                output_dir = Path(__file__).parent / "temp_pdfs"
                output_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = output_dir / f"financial_plan_{timestamp}.pdf"
            
            # Remove emojis from AI response for better PDF compatibility
            ai_response_clean = remove_emojis(ai_response)
            
            # Build HTML document
            html_content = self._build_html(ai_response_clean, business_info, user_name)
            
            # Generate PDF
            HTML(string=html_content).write_pdf(
                str(output_path),
                stylesheets=[CSS(string=PDF_CSS)]
            )
            
            logger.info(f"PDF generated successfully: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error generating PDF: {e}", exc_info=True)
            raise
    
    def _build_html(self, ai_response: str, business_info: Dict, user_name: str) -> str:
        """Build HTML document from Markdown"""
        
        # Header section
        date_str = datetime.now().strftime("%d.%m.%Y")
        header = f"""
        <h1>Финансовый План</h1>
        <div class="metadata">
            Дата: {date_str}
        </div>
        """
        
        # Business info section (clean emojis from user input)
        business_type = remove_emojis(business_info.get('business_type', 'Не указан'))
        business_section = f"""
        <h2>Информация о бизнесе</h2>
        <ul>
            <li><strong>Тип бизнеса:</strong> {business_type}</li>
        """
        
        if business_info.get('financial_situation'):
            situation = remove_emojis(business_info['financial_situation'][:200])
            business_section += f"<li><strong>Финансовая ситуация:</strong> {situation}</li>"
        
        if business_info.get('goals'):
            goals = remove_emojis(business_info['goals'][:200])
            business_section += f"<li><strong>Цели:</strong> {goals}</li>"
        
        business_section += "</ul>"
        
        # Convert AI response (Markdown) to HTML
        ai_html = markdown.markdown(
            ai_response,
            extensions=['tables', 'extra', 'nl2br']
        )
        
        # Footer
        footer = """
        <div class="footer">
            AI-generated. For reference only.
        </div>
        """
        
        # Combine all parts
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Финансовый План</title>
        </head>
        <body>
            {header}
            {business_section}
            <hr style="margin: 20pt 0; border: 1pt solid #2e7d32;">
            {ai_html}
            {footer}
        </body>
        </html>
        """
        
        return full_html
    
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


class SimpleChatHistoryPDF:
    """Simplified chat history PDF generator"""
    
    def generate(self, chat_history: list, user_name: str = None, 
                 output_path: str = None) -> str:
        """
        Generate PDF from chat history
        
        Args:
            chat_history: List of dicts with 'prompt', 'response', 'created_at'
            user_name: Optional user name
            output_path: Optional custom output path
            
        Returns:
            Path to generated PDF file
        """
        if not WEASYPRINT_AVAILABLE:
            raise ImportError("WeasyPrint not installed. Run: pip install weasyprint markdown")
        
        try:
            # Setup output path
            if not output_path:
                output_dir = Path(__file__).parent / "temp_pdfs"
                output_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = output_dir / f"chat_history_{timestamp}.pdf"
            
            # Build HTML document
            html_content = self._build_html(chat_history, user_name)
            
            # Custom CSS for chat
            chat_css = PDF_CSS + """
            .message {
                margin: 15pt 0;
                padding: 10pt;
                border-radius: 5pt;
            }
            
            .user-message {
                background-color: #e3f2fd;
                border-left: 4pt solid #1565c0;
            }
            
            .bot-message {
                background-color: #f5f5f5;
                border-left: 4pt solid #2e7d32;
            }
            
            .timestamp {
                color: #999;
                font-size: 9pt;
                margin-bottom: 5pt;
            }
            
            .label {
                font-weight: bold;
                color: #1565c0;
            }
            """
            
            # Generate PDF
            HTML(string=html_content).write_pdf(
                str(output_path),
                stylesheets=[CSS(string=chat_css)]
            )
            
            logger.info(f"Chat history PDF generated: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error generating chat PDF: {e}", exc_info=True)
            raise
    
    def _build_html(self, chat_history: list, user_name: str) -> str:
        """Build HTML document from chat history"""
        
        # Header
        date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        user_info = f"Пользователь: {user_name}" if user_name else ""
        header = f"""
        <h1>История общения с ботом</h1>
        <div class="metadata">
            {user_info}<br>
            {date_str}
        </div>
        <hr>
        """
        
        # Messages
        messages_html = ""
        for entry in reversed(chat_history):  # Oldest first
            timestamp = entry.get('created_at', datetime.now())
            if isinstance(timestamp, str):
                time_str = timestamp
            else:
                time_str = timestamp.strftime("%d.%m.%Y %H:%M")
            
            prompt = remove_emojis(entry.get('prompt', '')[:1000])
            response = remove_emojis(entry.get('response', '')[:3000])
            
            messages_html += f"""
            <div class="message user-message">
                <div class="timestamp">[{time_str}]</div>
                <div><span class="label">Пользователь:</span> {prompt}</div>
            </div>
            
            <div class="message bot-message">
                <div><span class="label">Бот:</span> {response}</div>
            </div>
            """
        
        # Footer
        footer = f"""
        <div class="footer">
            Конец истории. Всего сообщений: {len(chat_history)}
        </div>
        """
        
        # Combine
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>История чата</title>
        </head>
        <body>
            {header}
            {messages_html}
            {footer}
        </body>
        </html>
        """
        
        return full_html


# Export instances (same interface as original)
pdf_generator = SimpleFinancialPlanPDF()
chat_history_pdf = SimpleChatHistoryPDF()
