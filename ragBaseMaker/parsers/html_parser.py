"""
HTML document parser using BeautifulSoup.
"""

from pathlib import Path
from typing import List, Dict, Any
import re

from ragBaseMaker.parsers.base_parser import BaseParser, ParsedDocument


class HTMLParser(BaseParser):
    """Parser for HTML documents."""
    
    SUPPORTED_EXTENSIONS = ['.html', '.htm', '.xhtml']
    
    def __init__(
        self,
        encoding: str = 'utf-8',
        remove_scripts: bool = True,
        remove_styles: bool = True,
    ):
        super().__init__(encoding)
        self.remove_scripts = remove_scripts
        self.remove_styles = remove_styles
    
    def parse(self, file_path: str | Path) -> ParsedDocument:
        """
        Parse an HTML document.
        
        Args:
            file_path: Path to HTML file
            
        Returns:
            ParsedDocument with extracted text and metadata
        """
        from bs4 import BeautifulSoup
        
        path = self._validate_file(file_path)
        
        # Read file
        with open(path, 'r', encoding=self.encoding, errors='replace') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        if self.remove_scripts:
            for script in soup.find_all('script'):
                script.decompose()
        
        if self.remove_styles:
            for style in soup.find_all('style'):
                style.decompose()
        
        # Remove comments
        from bs4 import Comment
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        sections: List[Dict[str, Any]] = []
        metadata: Dict[str, Any] = {}
        
        # Extract metadata from head
        head = soup.find('head')
        if head:
            # Title
            title_tag = head.find('title')
            if title_tag:
                metadata['title'] = title_tag.get_text().strip()
            
            # Meta tags
            for meta in head.find_all('meta'):
                name = meta.get('name', meta.get('property', ''))
                content = meta.get('content', '')
                if name and content:
                    metadata[f'meta_{name}'] = content
        
        # Extract main content
        body = soup.find('body') or soup
        
        # Extract headings and their content
        current_section = {'heading': None, 'level': 0, 'content': []}
        
        for element in body.descendants:
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # Save previous section
                if current_section['heading'] or current_section['content']:
                    sections.append({
                        'type': 'section',
                        'level': current_section['level'],
                        'heading': current_section['heading'],
                        'content': ' '.join(current_section['content']),
                    })
                
                level = int(element.name[1])
                current_section = {
                    'heading': element.get_text().strip(),
                    'level': level,
                    'content': [],
                }
            elif element.name == 'p':
                text = element.get_text().strip()
                if text:
                    current_section['content'].append(text)
        
        # Save last section
        if current_section['heading'] or current_section['content']:
            sections.append({
                'type': 'section',
                'level': current_section['level'],
                'heading': current_section['heading'],
                'content': ' '.join(current_section['content']),
            })
        
        # Extract all text
        content = soup.get_text(separator='\n', strip=True)
        content = self._clean_text(content)
        
        # Extract tables
        for table_idx, table in enumerate(soup.find_all('table'), 1):
            table_data: List[List[str]] = []
            for row in table.find_all('tr'):
                row_data = [
                    cell.get_text().strip()
                    for cell in row.find_all(['td', 'th'])
                ]
                if row_data:
                    table_data.append(row_data)
            
            if table_data:
                sections.append({
                    'type': 'table',
                    'table_number': table_idx,
                    'data': table_data,
                })
        
        # Extract links
        links = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text().strip()
            if href and text:
                links.append({'text': text, 'href': href})
        
        if links:
            metadata['links'] = links[:50]  # Limit to 50 links
        
        return ParsedDocument(
            content=content,
            source_path=str(path.absolute()),
            file_type='html',
            metadata=metadata,
            title=metadata.get('title') or path.stem,
            sections=sections,
        )

