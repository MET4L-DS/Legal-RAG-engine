"""Test the new chapter pattern."""
import fitz
import re

# Test the new pattern - CHAPTER must be uppercase, chapter number can be roman or numeric
CHAPTER_PATTERN = re.compile(
    r'^CHAPTER\s+([IVXLCDM]+|[0-9]+)\s*[-–—]?\s*\n([A-Z][A-Z\s,]+)',
    re.MULTILINE
)

# Load PDF
doc = fitz.open('documents/Bharatiya Nagarik Suraksha Sanhita (BNSS).pdf')

# Test on page 82 (0-indexed: 81) where real Chapter XIV is
text = doc[81].get_text()
matches = list(CHAPTER_PATTERN.finditer(text))
print('Matches on page 82:')
for m in matches:
    title = m.group(2).strip()[:50]
    print(f'  Chapter {m.group(1)}: "{title}"')

# Also test on problematic text (mid-sentence reference)
test_text = '''under the provisions of
Chapter XIV:
Provided that considering'''
matches2 = list(CHAPTER_PATTERN.finditer(test_text))
print(f'\nMatches in problematic text: {len(matches2)} (should be 0)')
for m in matches2:
    print(f'  Matched: "{m.group(0)}"')
    print(f'  Title: "{m.group(2)}"')

# Test on TOC page 6
text_toc = doc[5].get_text()  # Page 6 is index 5
matches_toc = list(CHAPTER_PATTERN.finditer(text_toc))
print(f'\nMatches on TOC page 6:')
for m in matches_toc:
    title = m.group(2).strip()[:50]
    print(f'  Chapter {m.group(1)}: "{title}"')

doc.close()
