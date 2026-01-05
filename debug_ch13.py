"""Debug Chapter XIII - before dedup"""
from src.pdf_parser import LegalPDFParser
import fitz
import re

# First let's see what raw chapters we find
pdf_path = "documents/Bharatiya Nagarik Suraksha Sanhita (BNSS).pdf"
doc = fitz.open(pdf_path)
full_text = "\n".join([doc[i].get_text() for i in range(len(doc))])

# Find all Chapter XIII matches
pattern = re.compile(r'^CHAPTER\s*(XIII)\s*[-–—]?\s*(.+?)$', re.IGNORECASE | re.MULTILINE)
matches = list(pattern.finditer(full_text))

print(f"Found {len(matches)} matches for Chapter XIII:")
for m in matches:
    pos = m.start()
    # Find approximate page
    char_count = 0
    page_num = 0
    for i in range(len(doc)):
        page_text = doc[i].get_text()
        char_count += len(page_text) + 1  # +1 for newline
        if char_count > pos:
            page_num = i + 1
            break
    print(f"  Page ~{page_num}: {m.group(0)[:80]}")
    # Show sections following
    following = full_text[m.end():m.end()+500]
    sections = re.findall(r'(\d{1,3})\.\s+', following[:200])
    print(f"    First sections: {sections[:5]}")
