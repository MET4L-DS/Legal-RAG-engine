"""Test BNSS parsing after fix"""
from src.pdf_parser import LegalPDFParser

parser = LegalPDFParser()
doc = parser.parse_pdf("documents/Bharatiya Nagarik Suraksha Sanhita (BNSS).pdf")

print(f"Chapters: {len(doc.chapters)}")
print(f"Chapter numbers: {[c.chapter_no for c in doc.chapters]}")

# Find Section 184
found_184 = False
for ch in doc.chapters:
    for s in ch.sections:
        if s.section_no == "184":
            found_184 = True
            print(f"\n=== Section 184 ===")
            print(f"Chapter: {ch.chapter_no} - {ch.chapter_title}")
            print(f"Title: {s.section_title}")
            print(f"Full text ({len(s.full_text)} chars):")
            print(s.full_text[:500])
            print("\n... (truncated)")

if not found_184:
    print("\n!!! Section 184 NOT FOUND !!!")

# Count total sections and sample some
total_sections = sum(len(ch.sections) for ch in doc.chapters)
print(f"\nTotal sections: {total_sections}")

# Check a few section numbers to verify completeness
test_sections = ["1", "52", "63", "64", "183", "184", "530", "531"]
found = []
for sec_no in test_sections:
    for ch in doc.chapters:
        for s in ch.sections:
            if s.section_no == sec_no:
                found.append((sec_no, len(s.full_text)))
                break
print(f"\nTest sections found: {found}")
