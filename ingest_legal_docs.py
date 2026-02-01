import os
import re
import json
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

@dataclass
class Chunk:
    text: str
    metadata: Dict
    canonical_header: str

@dataclass
class ParserContext:
    law: Optional[str] = None
    law_name: Optional[str] = None
    year: Optional[int] = None
    doc_type: Optional[str] = None
    part: Optional[str] = None
    chapter: Optional[str] = None
    chapter_title: Optional[str] = None
    section: Optional[str] = None
    section_title: Optional[str] = None
    clause: Optional[str] = None
    clause_title: Optional[str] = None
    sub_section: Optional[str] = None
    step: Optional[str] = None
    mode: str = "normal"  # normal | illustration | explanation | table | sop
    source_file: Optional[str] = None

class StatefulParser:
    def __init__(self):
        self.context = ParserContext()
        self.chunks: List[Chunk] = []
        self.current_buffer: List[str] = []

    def flush_buffer(self):
        if not self.current_buffer:
            return

        text_content = "\n".join(self.current_buffer).strip()
        if not text_content:
            self.current_buffer = []
            return

        # Special case: skip page number markers or generic index entries
        if re.match(r"^\|?\s*\d+\s*\|\s*Page\s*\|?$", text_content, re.I):
            self.current_buffer = []
            return

        # Construct Canonical Header
        header_parts = []
        
        # Law Line
        if self.context.law_name:
            year_suffix = f", {self.context.year}" if self.context.year else ""
            header_parts.append(f"{self.context.law_name}{year_suffix}")
        
        if self.context.part:
            header_parts.append(self.context.part)

        # Chapter Line
        if self.context.chapter:
            ch_title = f" – {self.context.chapter_title}" if self.context.chapter_title else ""
            header_parts.append(f"{self.context.chapter}{ch_title}")
        
        # Section/Clause Line
        if self.context.section:
            sec_title = f" – {self.context.section_title}" if self.context.section_title else ""
            header_parts.append(f"Section {self.context.section}{sec_title}")
        elif self.context.clause:
            cl_title = f" – {self.context.clause_title}" if self.context.clause_title else ""
            header_parts.append(f"Clause {self.context.clause}{cl_title}")
        
        # Detail Line
        detail_line = []
        if self.context.sub_section:
            detail_line.append(f"Sub-section ({self.context.sub_section})")
        
        if self.context.mode == "illustration":
            detail_line.append("Illustration")
        elif self.context.mode == "explanation":
            detail_line.append("Explanation")
        elif self.context.mode in ["sop", "step"]:
            if self.context.step:
                detail_line.append(self.context.step)
        
        if detail_line:
            header_parts.append(" / ".join(detail_line))

        canonical_header = "\n".join(header_parts)
        full_text = f"{canonical_header}\n\n{text_content}"

        # Create Metadata
        meta = asdict(self.context)
        meta["unit_type"] = self.determine_unit_type()

        self.chunks.append(Chunk(text=full_text, metadata=meta, canonical_header=canonical_header))
        self.current_buffer = []

    def determine_unit_type(self):
        if self.context.mode == "illustration": return "illustration"
        if self.context.mode == "explanation": return "explanation"
        if self.context.mode == "table": return "table_row"
        if self.context.step: return "step"
        if self.context.sub_section: return "sub_section"
        if self.context.section: return "section"
        if self.context.clause: return "clause"
        return "general"

    def parse_line(self, line: str):
        stripped = line.strip()
        
        # Flush on separator
        if stripped == "---":
            self.flush_buffer()
            return

        # Skip PDF artifacts like "## 1 | Page"
        if re.match(r"^##\s+\d+\s+\|\s+Page", stripped, re.I):
            self.flush_buffer()
            return

        # Context updates
        
        # PART: # PART II or ## PART-II
        part_match = re.match(r"^(?:#|##)\s+(PART\s?[-–\s]?\s?[IVXLC]+.*)", stripped, re.I)
        if part_match:
            self.flush_buffer()
            self.context.part = part_match.group(1).strip()
            return

        # CHAPTER: # CHAPTER III or ## CHAPTER III
        chapter_match = re.match(r"^(?:#|##)\s+(CHAPTER\s+[IVXLC]+.*)", stripped, re.I)
        if chapter_match:
            self.flush_buffer()
            self.context.chapter = chapter_match.group(1).strip()
            self.context.chapter_title = None
            self.context.section = None
            self.context.sub_section = None
            self.context.mode = "normal"
            return

        # SECTION (BNS/BNSS/BSA): ## Section 14 — Title
        section_match = re.match(r"^##\s+Section\s+(\d+[A-Z]*)\s*[—\-]\s*(.*)", stripped, re.I)
        if section_match:
            self.flush_buffer()
            self.context.section = section_match.group(1).strip()
            self.context.section_title = section_match.group(2).strip()
            self.context.sub_section = None
            self.context.clause = None
            self.context.step = None
            self.context.mode = "normal"
            return

        # NALSA Clause: ## 2. DEFINITIONS or ## 1. SHORT TITLE...
        nalsa_clause_match = re.match(r"^##\s+(\d+)\.\s*(.*)", stripped)
        if nalsa_clause_match and self.context.law == "NALSA":
            self.flush_buffer()
            self.context.clause = nalsa_clause_match.group(1).strip()
            self.context.clause_title = nalsa_clause_match.group(2).strip()
            self.context.section = None
            self.context.sub_section = None
            self.context.mode = "normal"
            return

        # SOP Topic: ## **SOP ON ...**
        sop_topic_match = re.match(r"^##\s+\*\*(SOP\s+ON\s+.*)\*\*", stripped, re.I)
        if sop_topic_match:
            self.flush_buffer()
            self.context.chapter_title = sop_topic_match.group(1).strip()
            self.context.mode = "sop"
            return

        # Chapter Title: ## GENERAL EXCEPTIONS (when chapter is already set)
        # ONLY if not already matched as section/clause/sop
        if self.context.chapter and not section_match and not nalsa_clause_match and not sop_topic_match:
            if re.match(r"^##\s+[^0-9]+", stripped):
                title_match = re.match(r"^##\s+(.*)", stripped)
                if title_match:
                    self.context.chapter_title = title_match.group(1).strip()
                    return

        # SOP Step (Rape): **01. FIR - Suggested...** or **22. Witness Protection**
        sop_step_rape_match = re.match(r"^\*\*(\d+)\.\s*(.*?)(?:\s*[—\-]\s*Suggested.*?)?\*\*", stripped)
        if sop_step_rape_match:
            self.flush_buffer()
            self.context.step = f"Step {sop_step_rape_match.group(1)}"
            self.context.section_title = sop_step_rape_match.group(2).strip()
            self.context.mode = "step"
            return

        # General SOP Step: **Step 1:**
        gen_sop_step_match = re.match(r"^\*\*(Step\s+\d+):\*\*", stripped)
        if gen_sop_step_match:
            self.flush_buffer()
            self.context.step = gen_sop_step_match.group(1)
            self.context.mode = "step"
            return

        # Sub-section: **(1)** or (1) (usually at start of line)
        sub_sec_match = re.match(r"^(?:\*\*|\s)*\((\d+[a-z]?)\)(?:\*\*|\s)*", stripped)
        if sub_sec_match:
            self.flush_buffer()
            self.context.sub_section = sub_sec_match.group(1)
            self.context.mode = "normal" # Sub-sections reset illustration/explanation mode usually
            # We don't return here because the text usually follows on same or next line
        
        # Modes
        if re.search(r"Illustration(s)?(\.|:)?", stripped, re.I) and len(stripped) < 30:
            self.flush_buffer()
            self.context.mode = "illustration"
            return
        
        if re.search(r"Explanation(s)?(\s?\d+)?(\.|—)?", stripped, re.I) and "Explanation" in stripped:
            # Check if it's a standalone line or the start of a line
            if stripped.startswith("**Explanation") or stripped.startswith("*Explanation") or "Explanation.—" in stripped:
                self.flush_buffer()
                self.context.mode = "explanation"
        
        # Table Row
        if stripped.startswith("|") and not re.match(r"^[\|\-\s]+$", stripped) and not "Particulars" in stripped:
            if not self.context.mode == "table":
                self.flush_buffer()
                self.context.mode = "table"
            self.current_buffer.append(stripped)
            self.flush_buffer()
            return

        # Normal text
        if stripped:
            self.current_buffer.append(line)

    def parse_file(self, file_path: str, context_overrides: Dict):
        print(f"Processing: {file_path}")
        # Reset context but keep overrides
        self.context = ParserContext(source_file=os.path.basename(file_path))
        for k, v in context_overrides.items():
            setattr(self.context, k, v)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                self.parse_line(line)
        
        self.flush_buffer()

def main():
    parser = StatefulParser()
    docs_dir = r"c:\Met4l.DSCode\Python\Embedding-Test-Py\documents"
    
    # Process BNS (Split)
    bns_dir = os.path.join(docs_dir, "BNS")
    if os.path.exists(bns_dir):
        files = sorted(os.listdir(bns_dir))
        for f in files:
            if f.endswith(".md"):
                parser.parse_file(os.path.join(bns_dir, f), {"law": "BNS", "law_name": "Bharatiya Nyaya Sanhita", "year": 2023, "doc_type": "primary_legislation"})

    # Process BNSS (Split)
    bnss_dir = os.path.join(docs_dir, "BNSS")
    if os.path.exists(bnss_dir):
        files = sorted(os.listdir(bnss_dir))
        for f in files:
            if f.endswith(".md"):
                parser.parse_file(os.path.join(bnss_dir, f), {"law": "BNSS", "law_name": "Bharatiya Nagarik Suraksha Sanhita", "year": 2023, "doc_type": "primary_legislation"})

    # Process BSA (Split)
    bsa_dir = os.path.join(docs_dir, "BSA")
    if os.path.exists(bsa_dir):
        files = sorted(os.listdir(bsa_dir))
        for f in files:
            if f.endswith(".md"):
                parser.parse_file(os.path.join(bsa_dir, f), {"law": "BSA", "law_name": "Bharatiya Sakshya Adhiniyam", "year": 2023, "doc_type": "primary_legislation"})

    # Process NALSA (Complete)
    nalsa_file = os.path.join(docs_dir, "NALSA_Compensation_Scheme_2018.md")
    if os.path.exists(nalsa_file):
        parser.parse_file(nalsa_file, {"law": "NALSA", "law_name": "NALSA Compensation Scheme", "year": 2018, "doc_type": "compensation_scheme"})
    
    # Process NALSA Tables (Special)
    nalsa_table = os.path.join(docs_dir, "nalsa_table.md")
    if os.path.exists(nalsa_table):
        parser.parse_file(nalsa_table, {"law": "NALSA", "law_name": "NALSA Compensation Scheme", "year": 2018, "doc_type": "compensation_scheme", "chapter_title": "Schedule – Women Victims of Crimes"})

    # Process SOPs
    gen_sop = os.path.join(docs_dir, "General SOP.md")
    if os.path.exists(gen_sop):
        parser.parse_file(gen_sop, {"law": "SOP", "law_name": "General SOP", "doc_type": "sop"})
    
    rape_sop = os.path.join(docs_dir, "sop_rape_against_women.md")
    if os.path.exists(rape_sop):
        parser.parse_file(rape_sop, {"law": "SOP", "law_name": "SOP on Rape Against Women", "doc_type": "sop"})

    # Dry Run Output
    with open("debug_chunks.txt", "w", encoding="utf-8") as f:
        for i, chunk in enumerate(parser.chunks):
            f.write(f"--- CHUNK {i+1} ---\n")
            # Filter None values from metadata for cleaner log
            meta_clean = {k: v for k, v in chunk.metadata.items() if v is not None}
            f.write(f"METADATA: {json.dumps(meta_clean)}\n")
            f.write(f"CONTENT:\n{chunk.text}\n\n")

    # Save to JSON for embedding stage
    chunks_data = [asdict(c) for c in parser.chunks]
    with open("legal_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks_data, f, indent=2)

    # Final summary
    stats = {}
    for c in parser.chunks:
        law = c.metadata.get("law", "Unknown")
        stats[law] = stats.get(law, 0) + 1
    
    print(f"\nParsing complete. Total chunks: {len(parser.chunks)}")
    for law, count in stats.items():
        print(f" - {law}: {count} chunks")
    print(f"Chunks saved to legal_chunks.json and debug_chunks.txt")

if __name__ == "__main__":
    main()
