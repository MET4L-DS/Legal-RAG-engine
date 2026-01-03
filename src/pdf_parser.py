"""
PDF Parser for Legal Documents.
Extracts structured hierarchical data from Indian legal PDFs.
"""

import re
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional
from tqdm import tqdm

from .models import (
    LegalDocument, Chapter, Section, Subsection, SubsectionType
)


class LegalPDFParser:
    """Parser for Indian legal documents (BNS, BNSS, BSA)."""
    
    # Patterns for Indian legal documents
    # Chapter pattern: handles both "CHAPTER I" and "CHAPTERI" (no space)
    CHAPTER_PATTERN = re.compile(
        r'^CHAPTER\s*([IVXLCDM]+|[0-9]+)\s*[-–—]?\s*(.+?)$',
        re.IGNORECASE | re.MULTILINE
    )
    
    # Section pattern: matches "103. Text..." or "103 Text..." at start of line or after newline
    # More flexible to handle PDF text extraction quirks
    SECTION_PATTERN = re.compile(
        r'(?:^|\n)\s*(\d{1,3})\.\s+([A-Z\(].+?)(?=\n\s*\d{1,3}\.|\n\s*CHAPTER|\Z)',
        re.MULTILINE | re.DOTALL
    )
    
    SUBSECTION_PATTERN = re.compile(
        r'^\s*\((\d+|[a-z]|[ivxlcdm]+)\)\s*(.+)',
        re.IGNORECASE | re.MULTILINE
    )
    
    EXPLANATION_PATTERN = re.compile(
        r'^Explanation\.?[-–—]?\s*(.+)',
        re.IGNORECASE | re.MULTILINE
    )
    
    ILLUSTRATION_PATTERN = re.compile(
        r'^Illustration\.?[-–—]?\s*(.+)',
        re.IGNORECASE | re.MULTILINE
    )
    
    EXCEPTION_PATTERN = re.compile(
        r'^Exception\.?[-–—]?\s*(.+)',
        re.IGNORECASE | re.MULTILINE
    )
    
    def __init__(self):
        self.current_doc: Optional[LegalDocument] = None
    
    def parse_pdf(self, pdf_path: str | Path) -> LegalDocument:
        """Parse a legal PDF into structured format."""
        pdf_path = Path(pdf_path)
        
        # Determine document type from filename
        doc_info = self._identify_document(pdf_path.name)
        
        # Extract text from PDF
        doc = fitz.open(str(pdf_path))
        pages_text = []
        
        print(f"Extracting text from {pdf_path.name}...")
        for page_num in tqdm(range(len(doc)), desc="Reading pages"):
            page = doc[page_num]
            text = page.get_text("text")
            pages_text.append({
                "page_num": page_num + 1,
                "text": text
            })
        
        doc.close()
        
        # Create document
        legal_doc = LegalDocument(
            doc_id=doc_info["doc_id"],
            title=doc_info["title"],
            short_name=doc_info["short_name"],
            total_pages=len(pages_text),
            version=doc_info.get("version", "2023"),
            effective_date=doc_info.get("effective_date", "2023-07-01")
        )
        
        # Parse structure
        full_text = "\n".join([p["text"] for p in pages_text])
        legal_doc = self._parse_structure(legal_doc, full_text, pages_text)
        
        return legal_doc
    
    def _identify_document(self, filename: str) -> dict:
        """Identify document type from filename."""
        filename_lower = filename.lower()
        
        # Check BNSS first (before BNS) since BNSS contains "bns"
        if "bnss" in filename_lower or "nagarik suraksha" in filename_lower:
            return {
                "doc_id": "BNSS_2023",
                "title": "Bharatiya Nagarik Suraksha Sanhita",
                "short_name": "BNSS",
                "version": "2023",
                "effective_date": "2023-07-01"
            }
        elif "bns" in filename_lower or "nyaya sanhita" in filename_lower:
            return {
                "doc_id": "BNS_2023",
                "title": "The Bharatiya Nyaya Sanhita",
                "short_name": "BNS",
                "version": "2023",
                "effective_date": "2023-07-01"
            }
        elif "bsa" in filename_lower or "sakshya" in filename_lower:
            return {
                "doc_id": "BSA_2023",
                "title": "Bharatiya Sakshya Adhiniyam",
                "short_name": "BSA",
                "version": "2023",
                "effective_date": "2023-07-01"
            }
        else:
            # Generic handling
            name = filename.replace(".pdf", "").replace("_", " ")
            doc_id = name.upper().replace(" ", "_")
            return {
                "doc_id": doc_id,
                "title": name,
                "short_name": "".join([w[0] for w in name.split()]).upper(),
                "version": "2023",
                "effective_date": ""
            }
    
    def _parse_structure(
        self, 
        legal_doc: LegalDocument, 
        full_text: str,
        pages_text: list[dict]
    ) -> LegalDocument:
        """Parse the hierarchical structure of the document."""
        
        # Find all chapters
        chapter_matches = list(self.CHAPTER_PATTERN.finditer(full_text))
        
        print(f"Found {len(chapter_matches)} chapters")
        
        for i, match in enumerate(tqdm(chapter_matches, desc="Parsing chapters")):
            chapter_no = match.group(1).strip()
            chapter_title = match.group(2).strip()
            
            # Get chapter text (until next chapter or end)
            start_pos = match.end()
            end_pos = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(full_text)
            chapter_text = full_text[start_pos:end_pos]
            
            # Find page numbers for chapter
            page_start = self._find_page_for_position(match.start(), pages_text, full_text)
            page_end = self._find_page_for_position(end_pos, pages_text, full_text)
            
            chapter = Chapter(
                chapter_no=chapter_no,
                chapter_title=chapter_title,
                page_start=page_start,
                page_end=page_end
            )
            
            # Parse sections within chapter
            chapter.sections = self._parse_sections(chapter_text, pages_text, full_text, match.start())
            
            # Generate chapter summary from sections
            if chapter.sections:
                section_titles = [f"Section {s.section_no}: {s.section_title}" 
                                 for s in chapter.sections[:10]]  # First 10 sections
                chapter.summary = f"Chapter {chapter_no} - {chapter_title}. Contains: " + "; ".join(section_titles)
            
            legal_doc.chapters.append(chapter)
        
        # Generate document summary
        if legal_doc.chapters:
            chapter_summaries = [f"Chapter {c.chapter_no}: {c.chapter_title}" 
                               for c in legal_doc.chapters]
            legal_doc.summary = f"{legal_doc.title}. Contains {len(legal_doc.chapters)} chapters: " + "; ".join(chapter_summaries[:10])
        
        return legal_doc
    
    def _parse_sections(
        self, 
        chapter_text: str, 
        pages_text: list[dict],
        full_text: str,
        chapter_offset: int
    ) -> list[Section]:
        """Parse sections within a chapter."""
        sections = []
        
        # Find all sections using the pattern that captures full section text
        section_matches = list(self.SECTION_PATTERN.finditer(chapter_text))
        
        for match in section_matches:
            section_no = match.group(1).strip()
            section_text_full = match.group(2).strip()
            
            # Extract title from the first sentence/line
            # Section title is typically the first line or until first period
            title_match = re.match(r'^([^\n.]+?)(?:\.|—|\n)', section_text_full)
            if title_match:
                section_title = title_match.group(1).strip()
            else:
                section_title = section_text_full[:100].strip()
            
            # Clean up section title
            section_title = re.sub(r'\s+', ' ', section_title).strip()
            if len(section_title) > 200:
                section_title = section_title[:200] + "..."
            
            # Use the captured text as section text
            section_text = section_text_full
            
            # Find page numbers
            global_start = chapter_offset + match.start()
            global_end = chapter_offset + match.end()
            page_start = self._find_page_for_position(global_start, pages_text, full_text)
            page_end = self._find_page_for_position(global_end, pages_text, full_text)
            
            section = Section(
                section_no=section_no,
                section_title=section_title,
                full_text=section_text,
                page_start=page_start,
                page_end=page_end
            )
            
            # Parse subsections
            section.subsections = self._parse_subsections(section_text, page_start)
            
            # If no subsections found, create one from full text
            if not section.subsections and section_text:
                subsection_type = self._classify_text_type(section_text)
                section.subsections.append(Subsection(
                    subsection_no="main",
                    text=section_text[:2000],  # Limit text length
                    type=subsection_type,
                    page=page_start
                ))
            
            sections.append(section)
        
        return sections
    
    def _parse_subsections(self, section_text: str, page_start: int) -> list[Subsection]:
        """Parse subsections within a section."""
        subsections = []
        
        # Find numbered subsections like (1), (2), (a), (b)
        subsection_matches = list(self.SUBSECTION_PATTERN.finditer(section_text))
        
        for i, match in enumerate(subsection_matches):
            subsection_no = match.group(1).strip()
            
            # Get text until next subsection
            start_pos = match.start()
            end_pos = subsection_matches[i + 1].start() if i + 1 < len(subsection_matches) else len(section_text)
            subsection_text = section_text[start_pos:end_pos].strip()
            
            # Classify type
            subsection_type = self._classify_text_type(subsection_text)
            
            subsections.append(Subsection(
                subsection_no=subsection_no,
                text=subsection_text[:2000],  # Limit text length
                type=subsection_type,
                page=page_start
            ))
        
        # Also find Explanations and Illustrations
        for pattern, sub_type in [
            (self.EXPLANATION_PATTERN, SubsectionType.EXPLANATION),
            (self.ILLUSTRATION_PATTERN, SubsectionType.ILLUSTRATION),
            (self.EXCEPTION_PATTERN, SubsectionType.EXCEPTION)
        ]:
            for match in pattern.finditer(section_text):
                text = match.group(0).strip()
                if text and len(text) > 20:  # Minimum text length
                    subsections.append(Subsection(
                        subsection_no=sub_type.value,
                        text=text[:2000],
                        type=sub_type,
                        page=page_start
                    ))
        
        return subsections
    
    def _classify_text_type(self, text: str) -> SubsectionType:
        """Classify the type of legal text."""
        text_lower = text.lower()
        
        # Check for punishment indicators
        punishment_keywords = [
            "punish", "imprison", "fine", "rigorous", "simple imprisonment",
            "life imprisonment", "death", "years", "months", "shall be liable"
        ]
        if any(kw in text_lower for kw in punishment_keywords):
            return SubsectionType.PUNISHMENT
        
        # Check for definitions
        if "means" in text_lower or "includes" in text_lower or "defined" in text_lower:
            return SubsectionType.DEFINITION
        
        # Check for explanations
        if text_lower.startswith("explanation"):
            return SubsectionType.EXPLANATION
        
        # Check for illustrations
        if text_lower.startswith("illustration"):
            return SubsectionType.ILLUSTRATION
        
        # Check for exceptions
        if "exception" in text_lower or "except" in text_lower:
            return SubsectionType.EXCEPTION
        
        return SubsectionType.PROVISION
    
    def _find_page_for_position(
        self, 
        position: int, 
        pages_text: list[dict],
        full_text: str
    ) -> int:
        """Find which page a text position belongs to."""
        current_pos = 0
        for page_info in pages_text:
            page_len = len(page_info["text"]) + 1  # +1 for newline
            if current_pos + page_len > position:
                return page_info["page_num"]
            current_pos += page_len
        return pages_text[-1]["page_num"] if pages_text else 1


def parse_all_documents(documents_dir: str | Path) -> list[LegalDocument]:
    """Parse all PDF documents in a directory."""
    documents_dir = Path(documents_dir)
    parser = LegalPDFParser()
    documents = []
    
    pdf_files = list(documents_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files")
    
    for pdf_path in pdf_files:
        print(f"\n{'='*60}")
        print(f"Parsing: {pdf_path.name}")
        print(f"{'='*60}")
        
        try:
            doc = parser.parse_pdf(pdf_path)
            documents.append(doc)
            
            # Print summary
            total_sections = sum(len(c.sections) for c in doc.chapters)
            total_subsections = sum(
                len(s.subsections) 
                for c in doc.chapters 
                for s in c.sections
            )
            print(f"✓ {doc.short_name}: {len(doc.chapters)} chapters, "
                  f"{total_sections} sections, {total_subsections} subsections")
            
        except Exception as e:
            print(f"✗ Error parsing {pdf_path.name}: {e}")
    
    return documents
