import zipfile
import xml.etree.ElementTree as ET
try:
    with zipfile.ZipFile('temp_guide.docx') as docx:
        tree = ET.fromstring(docx.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        texts = [n.text for n in tree.findall('.//w:t', ns) if n.text]
        with open('merged_guide.txt', 'w', encoding='utf-8') as f:
            f.write(''.join(texts))
    print("DOCX successfully extracted")
except Exception as e:
    print("DOCX extraction error:", e)

try:
    import PyPDF2
    with open('pams merge guide-pdf.pdf', 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        texts = [page.extract_text() for page in reader.pages]
        with open('pdf_guide.txt', 'w', encoding='utf-8') as f2:
            f2.write('\n'.join(texts))
    print("PDF successfully extracted")
except Exception as e:
    print("PDF extraction error:", e)
