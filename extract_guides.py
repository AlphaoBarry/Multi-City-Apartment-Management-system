import zipfile
import re
import xml.etree.ElementTree as ET

try:
    with zipfile.ZipFile('PAMS_FrontDesk_Merge_Guide.docx') as docx:
        tree = ET.fromstring(docx.read('word/document.xml'))
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        texts = [node.text for node in tree.findall('.//w:t', namespaces) if node.text]
        with open('PAMS_FrontDesk_Merge_Guide_extracted.txt', 'w', encoding='utf-8') as f:
            f.write("".join(texts))
    print("Extracted DOCX to PAMS_FrontDesk_Merge_Guide_extracted.txt")
except Exception as e:
    print("DOCX extract failed:", e)

try:
    import zipfile
    print("For PDF we might just need to use strings or read it raw.")
except Exception as e:
    pass
