import os
import re
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def markdown_to_docx(md_path, docx_path):
    if not os.path.exists(md_path):
        print(f"Error: {md_path} not found.")
        return

    doc = Document()
    
    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)

    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_table = False
    table_data = []

    for line in lines:
        stripped = line.strip()

        # Handle Horizontal Rules as Page Breaks
        if stripped == '---':
            doc.add_page_break()
            continue

        # Handle Tables
        if stripped.startswith('|') and '|' in stripped:
            if not in_table:
                in_table = True
                table_data = []
            
            # Skip separator lines like |---|---|
            if re.match(r'^\|[\s:-|]*\|$', stripped):
                continue
            
            cells = [c.strip() for c in stripped.split('|') if c.strip() or (stripped.startswith('|') and stripped.endswith('|'))]
            # Precise split checking for leading/trailing pipes
            row_content = [c.strip() for c in stripped.strip('|').split('|')]
            table_data.append(row_content)
            continue
        else:
            if in_table:
                # Flush table to document
                if table_data:
                    num_rows = len(table_data)
                    num_cols = len(table_data[0])
                    table = doc.add_table(rows=num_rows, cols=num_cols)
                    table.style = 'Table Grid'
                    for i, row in enumerate(table_data):
                        for j, val in enumerate(row):
                            if j < num_cols: # Safety break
                                table.cell(i, j).text = val
                in_table = False
                table_data = []

        # Handle Headings
        if stripped.startswith('# '):
            h = doc.add_heading(stripped[2:], level=0)
            h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif stripped.startswith('## '):
            # If it's a CHAPTER, maybe start on new page
            if 'CHAPTER' in stripped.upper():
                doc.add_page_break()
            doc.add_heading(stripped[3:], level=1)
        elif stripped.startswith('### '):
            doc.add_heading(stripped[4:], level=2)
        elif stripped.startswith('#### '):
            doc.add_heading(stripped[5:], level=3)
        
        # Handle Empty Lines
        elif not stripped:
            continue
            
        # Handle Paragraphs and Bold/Italic
        else:
            p = doc.add_paragraph()
            
            # Simple conversion for **bold** and *italic*
            # This is a basic regex-based parser
            parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', line)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    run = p.add_run(part[2:-2])
                    run.bold = True
                elif part.startswith('*') and part.endswith('*'):
                    run = p.add_run(part[1:-1])
                    run.italic = True
                else:
                    # Handle Figure placeholders specially
                    if stripped.startswith('[Insert Figure'):
                        run = p.add_run(part.strip())
                        run.bold = True
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    else:
                        p.add_run(part)

    # Final flush for table at end of file
    if in_table and table_data:
        num_rows = len(table_data)
        num_cols = len(table_data[0]) if table_data else 0
        if num_cols > 0:
            table = doc.add_table(rows=num_rows, cols=num_cols)
            table.style = 'Table Grid'
            for i, row in enumerate(table_data):
                for j, val in enumerate(row):
                    if j < num_cols:
                        table.cell(i, j).text = val

    doc.save(docx_path)
    print(f"Successfully saved to {docx_path}")

if __name__ == "__main__":
    md_file = r"c:\Users\bhuva\OneDrive\Desktop\Facial_Intent_System\Project_Report.md"
    word_file = r"c:\Users\bhuva\OneDrive\Desktop\Facial_Intent_System\Facial_Intent_System_Report.docx"
    markdown_to_docx(md_file, word_file)
