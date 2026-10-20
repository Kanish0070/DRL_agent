import zipfile
import xml.etree.ElementTree as ET

def get_slide_text(pptx_path, slide_number):
    try:
        with zipfile.ZipFile(pptx_path, 'r') as z:
            # Slide XML files are typically named slide1.xml, slide2.xml, etc.
            slide_path = f'ppt/slides/slide{slide_number}.xml'
            
            if slide_path not in z.namelist():
                return f"Slide {slide_number} not found."
            
            xml_content = z.read(slide_path)
            root = ET.fromstring(xml_content)
            
            # The namespace map for PPTX
            namespaces = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
            
            # Find all text elements
            texts = []
            for node in root.findall('.//a:t', namespaces):
                if node.text:
                    texts.append(node.text)
                    
            return " ".join(texts)
    except Exception as e:
        return str(e)

print("Slide 9 Text:")
print(get_slide_text('Review-2_Draft_v10.pptx', 9))
