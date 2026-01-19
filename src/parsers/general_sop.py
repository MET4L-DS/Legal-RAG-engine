"""
General SOP Parser for Tier-3 - Citizen-Centric Procedural Guidance.

Tier-3 Document: General procedural guidance for all crime types.

This parser processes the General SOP.md document into atomic procedural blocks
for answering general crime-related procedural questions.

Unlike Tier-1 (rape-specific SOP), Tier-3 provides:
- General procedural guidance for all crimes (robbery, theft, assault, murder, etc.)
- Citizen-centric steps (not victim-trauma focused)
- Police accountability information
- Escalation paths when police don't act

Source: BPR&D General Standard Operating Procedures
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np


# =============================================================================
# ENUMS: SOPGroup, ProceduralStage, ActionType, Stakeholder
# =============================================================================


class SOPGroup(Enum):
    """Groups of SOP topics for categorization."""
    FIR = "fir"
    ZERO_FIR = "zero_fir"
    COMPLAINT = "complaint"
    NON_COGNIZABLE = "non_cognizable"
    PRELIMINARY_ENQUIRY = "preliminary_enquiry"
    WITNESS_EXAMINATION = "witness_examination"
    MEDICAL_EXAMINATION = "medical_examination"
    SEARCH_SEIZURE = "search_seizure"
    DIGITAL_EVIDENCE = "digital_evidence"
    MAGISTRATE_COMPLAINT = "magistrate_complaint"
    PUBLIC_SERVANT = "public_servant"
    VIDEOGRAPHY = "videography"
    GENERAL = "general"


class ProceduralStage(Enum):
    """Procedural stages - reusing existing stages from Tier-1."""
    PRE_FIR = "pre_fir"
    FIR = "fir"
    STATEMENT_RECORDING = "statement_recording"
    MEDICAL_EXAMINATION = "medical_examination"
    EVIDENCE_COLLECTION = "evidence_collection"
    INVESTIGATION = "investigation"
    ARREST = "arrest"
    BAIL = "bail"
    CHARGE_SHEET = "charge_sheet"
    SUMMONS = "summons"
    TRIAL = "trial"
    APPEAL = "appeal"
    COMPENSATION = "compensation"
    VICTIM_RIGHTS = "victim_rights"
    POLICE_DUTIES = "police_duties"
    DIGITAL_EVIDENCE = "digital_evidence"


class ActionType(Enum):
    """Type of action described in the SOP block."""
    PROCEDURE = "procedure"
    DUTY = "duty"
    RIGHT = "right"
    TIMELINE = "timeline"
    ESCALATION = "escalation"
    GUIDELINE = "guideline"
    TECHNICAL = "technical"


class Stakeholder(Enum):
    """Who the SOP block applies to."""
    CITIZEN = "citizen"
    VICTIM = "victim"
    POLICE = "police"
    IO = "io"  # Investigating Officer
    SHO = "sho"  # Station House Officer
    MAGISTRATE = "magistrate"
    DOCTOR = "doctor"
    FORENSIC = "forensic"
    ALL = "all"


@dataclass
class GeneralSOPBlock:
    """A single procedural block from the General SOP document."""
    block_id: str
    doc_id: str
    title: str
    text: str
    sop_group: SOPGroup
    procedural_stage: ProceduralStage
    stakeholders: list[Stakeholder]
    applies_to: list[str]  # Crime types: robbery, theft, assault, murder, all, etc.
    action_type: ActionType
    priority: int  # 1-5, lower is higher priority
    legal_references: list[str] = field(default_factory=list)
    time_limit: Optional[str] = None
    page: int = 0
    embedding: Optional[np.ndarray] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "block_id": self.block_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "text": self.text,
            "sop_group": self.sop_group.value,
            "procedural_stage": self.procedural_stage.value,
            "stakeholders": [s.value for s in self.stakeholders],
            "applies_to": self.applies_to,
            "action_type": self.action_type.value,
            "priority": self.priority,
            "legal_references": self.legal_references,
            "time_limit": self.time_limit,
            "page": self.page
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "GeneralSOPBlock":
        """Create from dictionary."""
        return cls(
            block_id=data["block_id"],
            doc_id=data["doc_id"],
            title=data["title"],
            text=data["text"],
            sop_group=SOPGroup(data["sop_group"]),
            procedural_stage=ProceduralStage(data["procedural_stage"]),
            stakeholders=[Stakeholder(s) for s in data["stakeholders"]],
            applies_to=data["applies_to"],
            action_type=ActionType(data["action_type"]),
            priority=data["priority"],
            legal_references=data.get("legal_references", []),
            time_limit=data.get("time_limit"),
            page=data.get("page", 0)
        )


@dataclass
class GeneralSOPDocument:
    """Complete General SOP document with all blocks."""
    doc_id: str
    title: str
    short_name: str
    source: str
    blocks: list[GeneralSOPBlock]
    total_pages: int = 0
    doc_type: str = "GENERAL_SOP"
    embedding: Optional[np.ndarray] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "title": self.title,
            "short_name": self.short_name,
            "source": self.source,
            "total_pages": self.total_pages,
            "blocks": [b.to_dict() for b in self.blocks]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "GeneralSOPDocument":
        """Create from dictionary."""
        return cls(
            doc_id=data["doc_id"],
            title=data["title"],
            short_name=data["short_name"],
            source=data["source"],
            total_pages=data.get("total_pages", 0),
            blocks=[GeneralSOPBlock.from_dict(b) for b in data["blocks"]]
        )


class GeneralSOPParser:
    """Parser for General SOP markdown document."""
    
    # Mapping from SOP titles to groups and stages
    SOP_MAPPINGS = {
        "types of petition": (SOPGroup.COMPLAINT, ProceduralStage.PRE_FIR),
        "receipt of complaint": (SOPGroup.COMPLAINT, ProceduralStage.PRE_FIR),
        "non-cognizable": (SOPGroup.NON_COGNIZABLE, ProceduralStage.PRE_FIR),
        "section 174 bnss": (SOPGroup.NON_COGNIZABLE, ProceduralStage.PRE_FIR),
        "cognizable cases": (SOPGroup.FIR, ProceduralStage.FIR),
        "electronic communication": (SOPGroup.FIR, ProceduralStage.FIR),
        "section 173": (SOPGroup.FIR, ProceduralStage.FIR),
        "registration of fir": (SOPGroup.FIR, ProceduralStage.FIR),
        "zero fir": (SOPGroup.ZERO_FIR, ProceduralStage.FIR),
        "section 173(4)": (SOPGroup.MAGISTRATE_COMPLAINT, ProceduralStage.PRE_FIR),
        "complaint to magistrate": (SOPGroup.MAGISTRATE_COMPLAINT, ProceduralStage.PRE_FIR),
        "complaint against a public servant": (SOPGroup.PUBLIC_SERVANT, ProceduralStage.INVESTIGATION),
        "examination of witnesses": (SOPGroup.WITNESS_EXAMINATION, ProceduralStage.STATEMENT_RECORDING),
        "section 180 bnss": (SOPGroup.WITNESS_EXAMINATION, ProceduralStage.STATEMENT_RECORDING),
        "161 crpc": (SOPGroup.WITNESS_EXAMINATION, ProceduralStage.STATEMENT_RECORDING),
        "section 184 bnss": (SOPGroup.MEDICAL_EXAMINATION, ProceduralStage.MEDICAL_EXAMINATION),
        "medical examination": (SOPGroup.MEDICAL_EXAMINATION, ProceduralStage.MEDICAL_EXAMINATION),
        "search and seizure": (SOPGroup.SEARCH_SEIZURE, ProceduralStage.EVIDENCE_COLLECTION),
        "videography": (SOPGroup.VIDEOGRAPHY, ProceduralStage.EVIDENCE_COLLECTION),
        "digital evidence": (SOPGroup.DIGITAL_EVIDENCE, ProceduralStage.DIGITAL_EVIDENCE),
        "crime scene": (SOPGroup.SEARCH_SEIZURE, ProceduralStage.EVIDENCE_COLLECTION),
        "flowchart": (SOPGroup.GENERAL, ProceduralStage.INVESTIGATION),
        "evidence preservation": (SOPGroup.DIGITAL_EVIDENCE, ProceduralStage.EVIDENCE_COLLECTION),
        "preliminary enquiry": (SOPGroup.PRELIMINARY_ENQUIRY, ProceduralStage.PRE_FIR),
    }
    
    # Time limit patterns
    TIME_PATTERNS = [
        (r"within\s+(\d+)\s*(hours?|days?)", lambda m: f"{m.group(1)} {m.group(2)}"),
        (r"(\d+)\s*(hours?|days?)", lambda m: f"{m.group(1)} {m.group(2)}"),
        (r"immediately", lambda m: "immediately"),
        (r"promptly", lambda m: "promptly"),
        (r"without delay", lambda m: "without delay"),
        (r"forthwith", lambda m: "forthwith"),
        (r"(fort night|fortnight|15 days)", lambda m: "15 days"),
        (r"14 days", lambda m: "14 days"),
        (r"7 days", lambda m: "7 days"),
        (r"24 hours", lambda m: "24 hours"),
        (r"3 days", lambda m: "3 days"),
    ]
    
    # Legal reference patterns
    LEGAL_REF_PATTERNS = [
        r"[Ss]ec(?:tion)?\.?\s*(\d+(?:\([^)]+\))?)\s*(?:of\s+)?(?:BNSS|BNS|BSA|Cr\.?P\.?C\.?)",
        r"BNSS\s+[Ss]ec(?:tion)?\.?\s*(\d+)",
        r"BNS\s+[Ss]ec(?:tion)?\.?\s*(\d+)",
        r"BSA\s+[Ss]ec(?:tion)?\.?\s*(\d+)",
        r"[Ss]ection\s+(\d+)\s+(?:of\s+)?BNSS",
        r"[Ss]ection\s+(\d+)\s+(?:of\s+)?BNS",
        r"[Uu]/[Ss]ec\.?\s*(\d+)",
    ]
    
    def __init__(self):
        self.blocks: list[GeneralSOPBlock] = []
        self.block_counter = 0
    
    def parse(self, filepath: Path) -> GeneralSOPDocument:
        """Parse a General SOP markdown file."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        self.blocks = []
        self.block_counter = 0
        
        # Split by major sections (## headers)
        sections = re.split(r'\n## \*\*', content)
        
        for section in sections[1:]:  # Skip content before first ##
            self._parse_section(section)
        
        return GeneralSOPDocument(
            doc_id="GENERAL_SOP_BPRD",
            title="BPR&D General Standard Operating Procedures",
            short_name="General SOP",
            source="BPR&D General SOP",
            blocks=self.blocks,
            total_pages=len(sections)
        )
    
    def _parse_section(self, section_text: str) -> None:
        """Parse a single section into one or more blocks."""
        # Extract title
        title_match = re.match(r'([^*]+)\*\*', section_text)
        if not title_match:
            return
        
        section_title = title_match.group(1).strip()
        section_body = section_text[title_match.end():].strip()
        
        # Determine SOP group and stage from title
        sop_group, stage = self._classify_section(section_title)
        
        # Extract subsections (### headers)
        subsections = re.split(r'\n### ', section_body)
        
        if len(subsections) > 1:
            # Parse main section intro as one block
            main_intro = subsections[0].strip()
            if main_intro and len(main_intro) > 50:
                self._create_block(
                    title=section_title,
                    text=self._clean_text(main_intro),
                    sop_group=sop_group,
                    stage=stage
                )
            
            # Parse each subsection as a block
            for subsection in subsections[1:]:
                sub_title_match = re.match(r'([^\n]+)', subsection)
                if sub_title_match:
                    sub_title = sub_title_match.group(1).strip()
                    sub_body = subsection[sub_title_match.end():].strip()
                    
                    # Determine stage from subsection title if more specific
                    sub_group, sub_stage = self._classify_section(sub_title)
                    if sub_group != SOPGroup.GENERAL:
                        sop_group = sub_group
                        stage = sub_stage
                    
                    if sub_body and len(sub_body) > 30:
                        self._create_block(
                            title=f"{section_title} - {sub_title}",
                            text=self._clean_text(sub_body),
                            sop_group=sop_group,
                            stage=stage
                        )
        else:
            # No subsections - create block from entire section
            # Split long sections into multiple blocks by numbered items or bullet groups
            text_blocks = self._split_into_chunks(section_body)
            
            for i, text in enumerate(text_blocks):
                block_title = section_title if len(text_blocks) == 1 else f"{section_title} (Part {i+1})"
                self._create_block(
                    title=block_title,
                    text=self._clean_text(text),
                    sop_group=sop_group,
                    stage=stage
                )
    
    def _classify_section(self, title: str) -> tuple[SOPGroup, ProceduralStage]:
        """Classify section by title into SOP group and procedural stage."""
        title_lower = title.lower()
        
        for keyword, (group, stage) in self.SOP_MAPPINGS.items():
            if keyword in title_lower:
                return group, stage
        
        return SOPGroup.GENERAL, ProceduralStage.INVESTIGATION
    
    def _create_block(
        self,
        title: str,
        text: str,
        sop_group: SOPGroup,
        stage: ProceduralStage
    ) -> None:
        """Create a GeneralSOPBlock and add to list."""
        if not text or len(text.strip()) < 30:
            return
        
        self.block_counter += 1
        
        # Determine stakeholders from content
        stakeholders = self._detect_stakeholders(text, title)
        
        # Determine action type
        action_type = self._detect_action_type(text, title)
        
        # Extract time limits
        time_limit = self._extract_time_limit(text)
        
        # Extract legal references
        legal_refs = self._extract_legal_references(text)
        
        # Determine applicable crime types
        applies_to = self._detect_applicable_crimes(text, title, sop_group)
        
        # Set priority based on group
        priority = self._calculate_priority(sop_group, action_type)
        
        block = GeneralSOPBlock(
            block_id=f"GSOP_{self.block_counter:03d}",
            doc_id="GENERAL_SOP_BPRD",
            title=title,
            text=text,
            sop_group=sop_group,
            procedural_stage=stage,
            stakeholders=stakeholders,
            applies_to=applies_to,
            action_type=action_type,
            priority=priority,
            legal_references=legal_refs,
            time_limit=time_limit
        )
        
        self.blocks.append(block)
    
    def _detect_stakeholders(self, text: str, title: str) -> list[Stakeholder]:
        """Detect who the SOP block applies to."""
        combined = (text + " " + title).lower()
        stakeholders = []
        
        patterns = {
            Stakeholder.CITIZEN: ["citizen", "informant", "complainant", "person", "individual"],
            Stakeholder.VICTIM: ["victim", "survivor"],
            Stakeholder.POLICE: ["police officer", "police", "officer in charge"],
            Stakeholder.IO: ["investigating officer", "i.o.", "io "],
            Stakeholder.SHO: ["sho", "station house officer"],
            Stakeholder.MAGISTRATE: ["magistrate", "court", "judicial"],
            Stakeholder.DOCTOR: ["medical practitioner", "doctor", "medical officer"],
            Stakeholder.FORENSIC: ["forensic", "expert", "evidence specialist"],
        }
        
        for stakeholder, keywords in patterns.items():
            if any(kw in combined for kw in keywords):
                stakeholders.append(stakeholder)
        
        if not stakeholders:
            stakeholders = [Stakeholder.ALL]
        
        return stakeholders
    
    def _detect_action_type(self, text: str, title: str) -> ActionType:
        """Detect the type of action described."""
        combined = (text + " " + title).lower()
        
        if any(word in combined for word in ["must", "shall", "mandatory", "obligation", "bound to"]):
            return ActionType.DUTY
        elif any(word in combined for word in ["may", "entitled", "right", "can"]):
            return ActionType.RIGHT
        elif any(word in combined for word in ["within", "hours", "days", "time limit", "timeline"]):
            return ActionType.TIMELINE
        elif any(word in combined for word in ["if not", "refuse", "failure", "complain", "approach"]):
            return ActionType.ESCALATION
        elif any(word in combined for word in ["technical", "forensic", "hash", "digital", "recording"]):
            return ActionType.TECHNICAL
        else:
            return ActionType.PROCEDURE
    
    def _extract_time_limit(self, text: str) -> Optional[str]:
        """Extract time limit from text."""
        text_lower = text.lower()
        
        for pattern, extractor in self.TIME_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                return extractor(match)
        
        return None
    
    def _extract_legal_references(self, text: str) -> list[str]:
        """Extract legal section references from text."""
        refs = []
        
        for pattern in self.LEGAL_REF_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            refs.extend(matches)
        
        # Deduplicate while preserving order
        seen = set()
        unique_refs = []
        for ref in refs:
            if ref not in seen:
                seen.add(ref)
                unique_refs.append(ref)
        
        return unique_refs[:5]  # Limit to 5 references
    
    def _detect_applicable_crimes(
        self,
        text: str,
        title: str,
        sop_group: SOPGroup
    ) -> list[str]:
        """Detect which crime types this SOP applies to."""
        combined = (text + " " + title).lower()
        
        # Check for specific crime mentions
        crime_keywords = {
            "robbery": ["robbery", "robbed", "loot"],
            "theft": ["theft", "stolen", "steal"],
            "assault": ["assault", "hurt", "grievous"],
            "murder": ["murder", "homicide", "death", "killed"],
            "cybercrime": ["cyber", "digital", "online", "electronic", "computer"],
            "cheating": ["cheating", "fraud", "deceive"],
            "kidnapping": ["kidnap", "abduct"],
            "rape": ["rape", "sexual assault"],  # Note: will be filtered if Tier-1 applies
        }
        
        applicable = []
        for crime, keywords in crime_keywords.items():
            if any(kw in combined for kw in keywords):
                applicable.append(crime)
        
        # If no specific crimes detected, it's general
        if not applicable:
            applicable = ["all"]
        
        return applicable
    
    def _calculate_priority(self, sop_group: SOPGroup, action_type: ActionType) -> int:
        """Calculate priority (1-5, lower is higher priority)."""
        # FIR-related procedures are highest priority for general queries
        group_priority = {
            SOPGroup.FIR: 1,
            SOPGroup.ZERO_FIR: 1,
            SOPGroup.COMPLAINT: 2,
            SOPGroup.MAGISTRATE_COMPLAINT: 2,
            SOPGroup.NON_COGNIZABLE: 3,
            SOPGroup.PRELIMINARY_ENQUIRY: 3,
            SOPGroup.WITNESS_EXAMINATION: 3,
            SOPGroup.SEARCH_SEIZURE: 4,
            SOPGroup.DIGITAL_EVIDENCE: 4,
            SOPGroup.VIDEOGRAPHY: 4,
            SOPGroup.MEDICAL_EXAMINATION: 3,
            SOPGroup.PUBLIC_SERVANT: 4,
            SOPGroup.GENERAL: 5,
        }
        
        base_priority = group_priority.get(sop_group, 5)
        
        # Adjust based on action type
        if action_type == ActionType.DUTY:
            base_priority = max(1, base_priority - 1)
        elif action_type == ActionType.ESCALATION:
            base_priority = max(1, base_priority - 1)
        
        return base_priority
    
    def _split_into_chunks(self, text: str, max_chunk_size: int = 1500) -> list[str]:
        """Split long text into manageable chunks."""
        if len(text) <= max_chunk_size:
            return [text]
        
        # Try to split by numbered items
        numbered_pattern = r'\n\d+\.\s+'
        parts = re.split(numbered_pattern, text)
        
        if len(parts) > 1:
            chunks = []
            current_chunk = ""
            
            for part in parts:
                if len(current_chunk) + len(part) > max_chunk_size and current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = part
                else:
                    current_chunk += "\n" + part
            
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            
            return chunks if chunks else [text]
        
        # Split by paragraphs
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        # Remove markdown formatting artifacts
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)  # Italic
        text = re.sub(r'_([^_]+)_', r'\1', text)  # Underscore
        
        # Clean up bullet points
        text = re.sub(r'^[\s]*[-•]\s*', '• ', text, flags=re.MULTILINE)
        
        return text.strip()


def parse_general_sop(filepath: Path) -> GeneralSOPDocument:
    """Parse a General SOP markdown file.
    
    Args:
        filepath: Path to the General SOP.md file
        
    Returns:
        GeneralSOPDocument with parsed blocks
    """
    parser = GeneralSOPParser()
    return parser.parse(filepath)
