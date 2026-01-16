"""
SOP (Standard Operating Procedure) Parser for Procedural Documents.
Extracts structured procedural blocks instead of hierarchical chapters/sections.
"""

import re
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class ProceduralStage(Enum):
    """Stages in a legal procedure (shared taxonomy)."""
    PRE_FIR = "pre_fir"
    FIR = "fir"
    INVESTIGATION = "investigation"
    MEDICAL_EXAMINATION = "medical_examination"
    STATEMENT_RECORDING = "statement_recording"
    EVIDENCE_COLLECTION = "evidence_collection"
    ARREST = "arrest"
    CHARGE_SHEET = "charge_sheet"
    TRIAL = "trial"
    APPEAL = "appeal"
    COMPENSATION = "compensation"
    VICTIM_RIGHTS = "victim_rights"
    POLICE_DUTIES = "police_duties"
    GENERAL = "general"


class Stakeholder(Enum):
    """Who the procedure applies to."""
    VICTIM = "victim"
    POLICE = "police"
    MAGISTRATE = "magistrate"
    DOCTOR = "doctor"
    IO = "investigating_officer"  # Investigating Officer
    WITNESS = "witness"
    ACCUSED = "accused"
    COURT = "court"
    GENERAL = "general"


class ActionType(Enum):
    """Type of procedural action."""
    DUTY = "duty"  # Something that must be done
    RIGHT = "right"  # Something the victim can demand
    TIMELINE = "timeline"  # Time limits
    PROCEDURE = "procedure"  # How to do something
    ESCALATION = "escalation"  # What to do if procedure fails
    GUIDELINE = "guideline"  # Recommended practice


@dataclass
class ProceduralBlock:
    """A single procedural block from the SOP."""
    block_id: str
    title: str
    text: str
    procedural_stage: ProceduralStage = ProceduralStage.GENERAL
    stakeholders: list[Stakeholder] = field(default_factory=list)
    action_type: ActionType = ActionType.PROCEDURE
    case_type: str = "rape"  # Type of case this applies to
    time_limit: Optional[str] = None  # e.g., "24 hours", "immediately"
    bnss_sections: list[str] = field(default_factory=list)  # Referenced BNSS sections
    bns_sections: list[str] = field(default_factory=list)  # Referenced BNS sections
    page: int = 0
    priority: int = 1  # Higher = more important for retrieval
    embedding: Optional[list[float]] = None
    
    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "title": self.title,
            "text": self.text,
            "procedural_stage": self.procedural_stage.value,
            "stakeholders": [s.value for s in self.stakeholders],
            "action_type": self.action_type.value,
            "case_type": self.case_type,
            "time_limit": self.time_limit,
            "bnss_sections": self.bnss_sections,
            "bns_sections": self.bns_sections,
            "page": self.page,
            "priority": self.priority
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProceduralBlock":
        return cls(
            block_id=data["block_id"],
            title=data["title"],
            text=data["text"],
            procedural_stage=ProceduralStage(data.get("procedural_stage", "general")),
            stakeholders=[Stakeholder(s) for s in data.get("stakeholders", [])],
            action_type=ActionType(data.get("action_type", "procedure")),
            case_type=data.get("case_type", "rape"),
            time_limit=data.get("time_limit"),
            bnss_sections=data.get("bnss_sections", []),
            bns_sections=data.get("bns_sections", []),
            page=data.get("page", 0),
            priority=data.get("priority", 1)
        )
    
    def get_citation(self) -> str:
        """Generate citation for this block."""
        return f"SOP (MHA/BPR&D) - {self.title}"


@dataclass
class SOPDocument:
    """Complete SOP document."""
    doc_id: str = "SOP_RAPE_MHA"
    doc_type: str = "SOP"
    title: str = "Standard Operating Procedure for Investigation and Prosecution of Rape against Women"
    short_name: str = "SOP-Rape"
    source: str = "MHA/BPR&D"
    blocks: list[ProceduralBlock] = field(default_factory=list)
    total_pages: int = 0
    case_types: list[str] = field(default_factory=lambda: ["rape", "sexual_assault", "pocso"])
    embedding: Optional[list[float]] = None
    
    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "title": self.title,
            "short_name": self.short_name,
            "source": self.source,
            "blocks": [b.to_dict() for b in self.blocks],
            "total_pages": self.total_pages,
            "case_types": self.case_types
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SOPDocument":
        return cls(
            doc_id=data["doc_id"],
            doc_type=data.get("doc_type", "SOP"),
            title=data["title"],
            short_name=data["short_name"],
            source=data.get("source", "MHA/BPR&D"),
            blocks=[ProceduralBlock.from_dict(b) for b in data.get("blocks", [])],
            total_pages=data.get("total_pages", 0),
            case_types=data.get("case_types", ["rape"])
        )


class SOPParser:
    """Parser for MHA/BPR&D SOP documents."""
    
    # Stage keywords for classification
    STAGE_KEYWORDS = {
        ProceduralStage.FIR: ["fir", "first information report", "lodging", "complaint registration"],
        ProceduralStage.INVESTIGATION: ["investigation", "investigating officer", "i.o.", "io"],
        ProceduralStage.MEDICAL_EXAMINATION: ["medical examination", "medical officer", "forensic", "rape kit", "164(a)", "184"],
        ProceduralStage.STATEMENT_RECORDING: ["statement", "164", "183", "161", "180", "recording"],
        ProceduralStage.EVIDENCE_COLLECTION: ["evidence", "scene of crime", "collection", "forensic", "dna"],
        ProceduralStage.ARREST: ["arrest", "custody", "remand", "accused"],
        ProceduralStage.CHARGE_SHEET: ["charge sheet", "173", "193", "final report"],
        ProceduralStage.TRIAL: ["trial", "court", "prosecution", "sessions"],
        ProceduralStage.VICTIM_RIGHTS: ["victim", "survivor", "rights", "entitlement", "compensation"],
        ProceduralStage.POLICE_DUTIES: ["duty", "police", "shall", "must", "obligation"],
    }
    
    # Stakeholder keywords
    STAKEHOLDER_KEYWORDS = {
        Stakeholder.VICTIM: ["victim", "survivor", "woman", "girl", "complainant"],
        Stakeholder.POLICE: ["police", "sho", "station house officer"],
        Stakeholder.IO: ["investigating officer", "i.o.", "io", "investigation team"],
        Stakeholder.MAGISTRATE: ["magistrate", "judicial", "metropolitan"],
        Stakeholder.DOCTOR: ["doctor", "medical officer", "medical practitioner", "lady doctor"],
        Stakeholder.WITNESS: ["witness"],
        Stakeholder.COURT: ["court", "sessions", "judge"],
    }
    
    # Time limit patterns
    TIME_PATTERNS = [
        (r'within\s+(\d+)\s+hours?', lambda m: f"{m.group(1)} hours"),
        (r'(\d+)\s+hours?', lambda m: f"{m.group(1)} hours"),
        (r'immediately', lambda m: "immediately"),
        (r'promptly', lambda m: "promptly"),
        (r'at\s+once', lambda m: "immediately"),
        (r'forthwith', lambda m: "immediately"),
        (r'as\s+soon\s+as\s+possible', lambda m: "as soon as possible"),
        (r'within\s+(\d+)\s+days?', lambda m: f"{m.group(1)} days"),
    ]
    
    # Section reference patterns
    BNSS_SECTION_PATTERN = re.compile(r'section\s+(\d+)\s+of\s+BNSS|section[\s-]?(\d+).*?BNSS|BNSS.*?section\s+(\d+)', re.IGNORECASE)
    BNS_SECTION_PATTERN = re.compile(r'section\s+(\d+)\s+of\s+BNS|section[\s-]?(\d+).*?BNS|BNS.*?section\s+(\d+)|sections?\s+(\d+(?:,\s*\d+)*)\s+of\s+BNS', re.IGNORECASE)
    
    # Block separator pattern (numbered items in the SOP)
    BLOCK_PATTERN = re.compile(
        r'^(\d{2})\n\s*(.+?)(?=^\d{2}\n|\Z)',
        re.MULTILINE | re.DOTALL
    )
    
    def __init__(self):
        self.current_doc: Optional[SOPDocument] = None
    
    def parse(self, pdf_path: Path) -> SOPDocument:
        """Parse SOP PDF into structured procedural blocks."""
        doc = fitz.open(pdf_path)
        self.current_doc = SOPDocument(total_pages=len(doc))
        
        # Extract all text with page numbers
        full_text = ""
        page_texts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            page_texts.append({"page": page_num + 1, "text": text})
            full_text += f"\n{text}"
        
        doc.close()
        
        # Parse blocks from the structured SOP
        blocks = self._extract_blocks(full_text, page_texts)
        self.current_doc.blocks = blocks
        
        return self.current_doc
    
    def _extract_blocks(self, full_text: str, page_texts: list[dict]) -> list[ProceduralBlock]:
        """Extract procedural blocks from SOP text."""
        blocks = []
        
        # The SOP has numbered sections like "01 FIR", "02 Victim shelter", etc.
        # Split by these numbered patterns
        
        # Pattern to match numbered items (01, 02, ... up to 30+)
        section_pattern = re.compile(
            r'(?:^|\n)(\d{2})\s*\n\s*(.+?)(?=\n\d{2}\s*\n|\nAdditional\s+Provisions|\Z)',
            re.DOTALL
        )
        
        matches = list(section_pattern.finditer(full_text))
        
        if not matches:
            # Fallback: try to extract by looking for common headers
            blocks = self._extract_blocks_fallback(full_text, page_texts)
            return blocks
        
        for idx, match in enumerate(matches):
            block_num = match.group(1)
            block_text = match.group(2).strip()
            
            # Extract title (first line or until first bullet point)
            lines = block_text.split('\n')
            title_line = lines[0].strip() if lines else f"Block {block_num}"
            
            # Clean up title
            title = self._clean_title(title_line)
            
            # Find page number
            page = self._find_page_for_text(block_text[:100], page_texts)
            
            # Create block
            block = ProceduralBlock(
                block_id=f"SOP_BLOCK_{block_num}",
                title=title,
                text=block_text,
                page=page
            )
            
            # Classify the block
            self._classify_block(block)
            
            blocks.append(block)
        
        # Also extract additional provisions section if present
        additional_match = re.search(
            r'Additional\s+Provisions.*?(?=\Z)',
            full_text, re.DOTALL | re.IGNORECASE
        )
        if additional_match:
            additional_text = additional_match.group(0)
            block = ProceduralBlock(
                block_id="SOP_BLOCK_ADDITIONAL",
                title="Additional Provisions",
                text=additional_text,
                page=self._find_page_for_text(additional_text[:100], page_texts),
                procedural_stage=ProceduralStage.GENERAL
            )
            self._classify_block(block)
            blocks.append(block)
        
        return blocks
    
    def _extract_blocks_fallback(self, full_text: str, page_texts: list[dict]) -> list[ProceduralBlock]:
        """Fallback extraction using header patterns."""
        blocks = []
        
        # Common SOP headers
        headers = [
            ("FIR", ProceduralStage.FIR),
            ("Victim shelter", ProceduralStage.VICTIM_RIGHTS),
            ("Investigation", ProceduralStage.INVESTIGATION),
            ("Recording of statement", ProceduralStage.STATEMENT_RECORDING),
            ("Statement of victim", ProceduralStage.STATEMENT_RECORDING),
            ("Medical examination", ProceduralStage.MEDICAL_EXAMINATION),
            ("Collection of evidence", ProceduralStage.EVIDENCE_COLLECTION),
            ("Arrest", ProceduralStage.ARREST),
            ("Charge sheet", ProceduralStage.CHARGE_SHEET),
            ("Trial", ProceduralStage.TRIAL),
        ]
        
        for idx, (header, stage) in enumerate(headers):
            pattern = re.compile(
                rf'{header}.*?(?=(?:{"|".join(h for h, _ in headers[idx+1:])})|Additional\s+Provisions|\Z)',
                re.DOTALL | re.IGNORECASE
            )
            match = pattern.search(full_text)
            if match:
                block_text = match.group(0).strip()
                block = ProceduralBlock(
                    block_id=f"SOP_BLOCK_{idx+1:02d}",
                    title=header,
                    text=block_text,
                    page=self._find_page_for_text(block_text[:100], page_texts),
                    procedural_stage=stage
                )
                self._classify_block(block)
                blocks.append(block)
        
        return blocks
    
    def _clean_title(self, title: str) -> str:
        """Clean and normalize title text."""
        # Remove extra whitespace
        title = ' '.join(title.split())
        # Remove common prefixes
        title = re.sub(r'^(compliance of |recording of |collection of )', '', title, flags=re.IGNORECASE)
        # Capitalize properly
        if title:
            title = title[0].upper() + title[1:]
        return title[:100]  # Limit length
    
    def _find_page_for_text(self, text: str, page_texts: list[dict]) -> int:
        """Find which page contains the given text."""
        search_text = text[:50].lower()
        for pt in page_texts:
            if search_text in pt["text"].lower():
                return pt["page"]
        return 1
    
    def _classify_block(self, block: ProceduralBlock) -> None:
        """Classify a block's stage, stakeholders, action type, and extract metadata."""
        text_lower = block.text.lower()
        title_lower = block.title.lower()
        combined = title_lower + " " + text_lower
        
        # Classify procedural stage
        stage_scores = {}
        for stage, keywords in self.STAGE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > 0:
                stage_scores[stage] = score
        
        if stage_scores:
            block.procedural_stage = max(stage_scores, key=stage_scores.get)  # type: ignore
        
        # Override with title-based classification
        if "fir" in title_lower:
            block.procedural_stage = ProceduralStage.FIR
        elif "medical" in title_lower:
            block.procedural_stage = ProceduralStage.MEDICAL_EXAMINATION
        elif "investigation" in title_lower:
            block.procedural_stage = ProceduralStage.INVESTIGATION
        elif "statement" in title_lower:
            block.procedural_stage = ProceduralStage.STATEMENT_RECORDING
        elif "evidence" in title_lower or "scene of crime" in title_lower:
            block.procedural_stage = ProceduralStage.EVIDENCE_COLLECTION
        elif "arrest" in title_lower:
            block.procedural_stage = ProceduralStage.ARREST
        elif "charge" in title_lower:
            block.procedural_stage = ProceduralStage.CHARGE_SHEET
        elif "trial" in title_lower:
            block.procedural_stage = ProceduralStage.TRIAL
        elif "victim" in title_lower or "shelter" in title_lower:
            block.procedural_stage = ProceduralStage.VICTIM_RIGHTS
        
        # Identify stakeholders
        stakeholders = []
        for stakeholder, keywords in self.STAKEHOLDER_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                stakeholders.append(stakeholder)
        block.stakeholders = stakeholders if stakeholders else [Stakeholder.GENERAL]
        
        # Determine action type
        if any(word in combined for word in ["must", "shall", "duty", "obligation", "mandatory"]):
            block.action_type = ActionType.DUTY
        elif any(word in combined for word in ["right", "entitled", "can demand", "victim's right"]):
            block.action_type = ActionType.RIGHT
        elif any(word in combined for word in ["hours", "days", "time limit", "within"]):
            block.action_type = ActionType.TIMELINE
        elif any(word in combined for word in ["if", "failure", "refuse", "escalat"]):
            block.action_type = ActionType.ESCALATION
        else:
            block.action_type = ActionType.PROCEDURE
        
        # Extract time limits
        for pattern, formatter in self.TIME_PATTERNS:
            match = re.search(pattern, combined)
            if match:
                block.time_limit = formatter(match)
                break
        
        # Extract section references
        block.bnss_sections = self._extract_sections(block.text, self.BNSS_SECTION_PATTERN)
        block.bns_sections = self._extract_sections(block.text, self.BNS_SECTION_PATTERN)
        
        # Set priority based on importance
        # Higher priority for victim-centric, duty-based, time-sensitive blocks
        priority = 1
        if Stakeholder.VICTIM in block.stakeholders:
            priority += 2
        if block.action_type == ActionType.DUTY:
            priority += 1
        if block.action_type == ActionType.RIGHT:
            priority += 2
        if block.time_limit:
            priority += 1
        if block.procedural_stage in [ProceduralStage.FIR, ProceduralStage.MEDICAL_EXAMINATION, ProceduralStage.VICTIM_RIGHTS]:
            priority += 1
        block.priority = priority
    
    def _extract_sections(self, text: str, pattern: re.Pattern) -> list[str]:
        """Extract section numbers from text using given pattern."""
        sections = []
        for match in pattern.finditer(text):
            for group in match.groups():
                if group:
                    # Handle comma-separated sections
                    for sec in group.split(','):
                        sec = sec.strip()
                        if sec.isdigit():
                            sections.append(sec)
        return list(set(sections))


def parse_sop(pdf_path: Path) -> SOPDocument:
    """Parse SOP PDF and return structured document."""
    parser = SOPParser()
    return parser.parse(pdf_path)
