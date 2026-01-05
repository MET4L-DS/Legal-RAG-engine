import re
import fitz

TOC_INDICATORS = [
    "ARRANGEMENT OF CLAUSES",
    "TABLE OF CONTENTS",
    "STATEMENT OF OBJECTS AND REASONS",
    "MEMORANDUM REGARDING DELEGATED LEGISLATION",
    "FINANCIAL MEMORANDUM",
    "AS INTRODUCED IN LOK SABHA",
    "AS PASSED BY"
]

LAW_START_PATTERNS = [
    r'BE\s+it\s+enacted\s+by\s+Parliament',
    r'An\s+Act\s+to',
    r'1\.\s*\(1\)\s*This\s+Act',
    r'Short\s+title.*extent.*commencement',
]

law_patterns = [re.compile(p, re.IGNORECASE) for p in LAW_START_PATTERNS]

doc = fitz.open('documents/Bharatiya Nagarik Suraksha Sanhita (BNSS).pdf')

for i in range(20):
    text = doc[i].get_text()
    text_normalized = ' '.join(text.upper().split())
    
    is_toc = any(indicator in text_normalized for indicator in TOC_INDICATORS)
    has_law_start = any(p.search(text) for p in law_patterns)
    
    print(f"Page {i+1}: is_toc={is_toc}, has_law_start={has_law_start}")
    
    if is_toc:
        print(f"  -> Skipping (TOC)")
    elif has_law_start:
        print(f"  -> START HERE (law start marker found)")
        break
