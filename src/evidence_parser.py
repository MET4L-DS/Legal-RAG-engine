"""
Evidence Manual Parser for Crime Scene Investigation Manual (DFS/GoI).
Extracts operational evidence blocks for forensic/evidence handling queries.

Tier-2 Document: Conditional depth layer for evidence-related questions.
"""

import re
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class EvidenceType(Enum):
    """Types of evidence covered in the manual."""
    BIOLOGICAL = "biological"  # DNA, blood, semen, saliva, hair
    PHYSICAL = "physical"  # Weapons, clothing, fibers
    DIGITAL = "digital"  # Mobile, computer, CCTV
    DOCUMENTARY = "documentary"  # Documents, records
    TRACE = "trace"  # Fingerprints, footprints, tool marks
    CHEMICAL = "chemical"  # Toxicology, drugs, poison
    BALLISTIC = "ballistic"  # Firearms, ammunition
    GENERAL = "general"


class InvestigativeAction(Enum):
    """Types of investigative actions in evidence handling."""
    SCENE_PROTECTION = "scene_protection"  # Securing the crime scene
    EVIDENCE_COLLECTION = "evidence_collection"  # Collecting evidence
    EVIDENCE_PRESERVATION = "evidence_preservation"  # Preserving evidence
    EVIDENCE_PACKAGING = "evidence_packaging"  # Packaging for transport
    CHAIN_OF_CUSTODY = "chain_of_custody"  # Maintaining chain
    FORENSIC_ANALYSIS = "forensic_analysis"  # Lab analysis
    DOCUMENTATION = "documentation"  # Recording, photography
    WITNESS_EVIDENCE = "witness_evidence"  # Witness statements
    GENERAL = "general"


class FailureImpact(Enum):
    """Potential impact of procedural failure."""
    CONTAMINATION = "contamination"  # Evidence contaminated
    CASE_WEAKENING = "case_weakening"  # Case becomes weaker
    INADMISSIBILITY = "inadmissibility"  # Evidence inadmissible
    ACQUITTAL_RISK = "acquittal_risk"  # Risk of acquittal
    PROCEDURAL_VIOLATION = "procedural_violation"  # Violation of law
    NONE = "none"


@dataclass
class EvidenceBlock:
    """A single operational evidence block from the Crime Scene Manual."""
    block_id: str
    title: str
    text: str
    evidence_types: list[EvidenceType] = field(default_factory=list)
    investigative_action: InvestigativeAction = InvestigativeAction.GENERAL
    stakeholders: list[str] = field(default_factory=lambda: ["police", "io"])
    failure_impact: FailureImpact = FailureImpact.NONE
    linked_stage: str = "evidence_collection"  # Links to ProceduralStage
    case_types: list[str] = field(default_factory=lambda: ["all"])  # Which cases this applies to
    page: int = 0
    priority: int = 1
    bnss_sections: list[str] = field(default_factory=list)
    embedding: Optional[list[float]] = None
    
    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "title": self.title,
            "text": self.text,
            "evidence_types": [e.value for e in self.evidence_types],
            "investigative_action": self.investigative_action.value,
            "stakeholders": self.stakeholders,
            "failure_impact": self.failure_impact.value,
            "linked_stage": self.linked_stage,
            "case_types": self.case_types,
            "page": self.page,
            "priority": self.priority,
            "bnss_sections": self.bnss_sections
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceBlock":
        return cls(
            block_id=data["block_id"],
            title=data["title"],
            text=data["text"],
            evidence_types=[EvidenceType(e) for e in data.get("evidence_types", [])],
            investigative_action=InvestigativeAction(data.get("investigative_action", "general")),
            stakeholders=data.get("stakeholders", ["police", "io"]),
            failure_impact=FailureImpact(data.get("failure_impact", "none")),
            linked_stage=data.get("linked_stage", "evidence_collection"),
            case_types=data.get("case_types", ["all"]),
            page=data.get("page", 0),
            priority=data.get("priority", 1),
            bnss_sections=data.get("bnss_sections", [])
        )
    
    def get_citation(self) -> str:
        """Generate citation for this block."""
        return f"Crime Scene Manual (DFS) - {self.title}"


@dataclass
class EvidenceManualDocument:
    """Complete Crime Scene Investigation Manual document."""
    doc_id: str = "CRIME_SCENE_MANUAL"
    doc_type: str = "EVIDENCE_MANUAL"
    title: str = "Crime Scene Investigation Manual"
    short_name: str = "CSI Manual"
    source: str = "DFS/GoI"
    blocks: list[EvidenceBlock] = field(default_factory=list)
    total_pages: int = 0
    embedding: Optional[list[float]] = None
    
    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "title": self.title,
            "short_name": self.short_name,
            "source": self.source,
            "blocks": [b.to_dict() for b in self.blocks],
            "total_pages": self.total_pages
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceManualDocument":
        return cls(
            doc_id=data["doc_id"],
            doc_type=data.get("doc_type", "EVIDENCE_MANUAL"),
            title=data["title"],
            short_name=data.get("short_name", "CSI Manual"),
            source=data.get("source", "DFS/GoI"),
            blocks=[EvidenceBlock.from_dict(b) for b in data.get("blocks", [])],
            total_pages=data.get("total_pages", 0)
        )


class EvidenceManualParser:
    """Parser for Crime Scene Investigation Manual (DFS/GoI)."""
    
    # Evidence type keywords
    EVIDENCE_TYPE_KEYWORDS = {
        EvidenceType.BIOLOGICAL: ["blood", "semen", "saliva", "hair", "dna", "biological", "body fluid", "swab", "nail"],
        EvidenceType.PHYSICAL: ["weapon", "clothing", "fiber", "physical", "object", "tool", "instrument"],
        EvidenceType.DIGITAL: ["digital", "mobile", "computer", "cctv", "electronic", "phone", "data"],
        EvidenceType.DOCUMENTARY: ["document", "record", "paper", "writing", "letter"],
        EvidenceType.TRACE: ["fingerprint", "footprint", "impression", "tool mark", "trace"],
        EvidenceType.CHEMICAL: ["chemical", "poison", "drug", "toxicology", "narcotic"],
        EvidenceType.BALLISTIC: ["firearm", "bullet", "cartridge", "ammunition", "ballistic", "gun"],
    }
    
    # Action type keywords
    ACTION_KEYWORDS = {
        InvestigativeAction.SCENE_PROTECTION: ["protect", "secure", "cordon", "seal", "barrier", "preserve scene", "first officer"],
        InvestigativeAction.EVIDENCE_COLLECTION: ["collect", "gather", "retrieve", "pick", "sample", "swab"],
        InvestigativeAction.EVIDENCE_PRESERVATION: ["preserve", "store", "maintain", "refrigerat", "dry", "container"],
        InvestigativeAction.EVIDENCE_PACKAGING: ["pack", "seal", "label", "bag", "envelope", "container", "transport"],
        InvestigativeAction.CHAIN_OF_CUSTODY: ["chain of custody", "handover", "transfer", "custody", "receipt"],
        InvestigativeAction.FORENSIC_ANALYSIS: ["analys", "laborator", "forensic", "test", "examin", "fsl"],
        InvestigativeAction.DOCUMENTATION: ["document", "photograph", "video", "record", "sketch", "note", "log"],
        InvestigativeAction.WITNESS_EVIDENCE: ["witness", "statement", "testimony", "interview"],
    }
    
    # Failure impact keywords
    FAILURE_KEYWORDS = {
        FailureImpact.CONTAMINATION: ["contaminat", "pollut", "mix", "cross-contaminat"],
        FailureImpact.CASE_WEAKENING: ["weaken", "compromise", "damage", "affect case"],
        FailureImpact.INADMISSIBILITY: ["inadmissib", "rejected", "not admissible", "thrown out"],
        FailureImpact.ACQUITTAL_RISK: ["acquit", "benefit of doubt", "fail to prove"],
        FailureImpact.PROCEDURAL_VIOLATION: ["violat", "breach", "illegal", "improper"],
    }
    
    # Section headers that indicate chapter/topic boundaries
    SECTION_HEADERS = [
        ("crime scene", InvestigativeAction.SCENE_PROTECTION),
        ("securing", InvestigativeAction.SCENE_PROTECTION),
        ("collection", InvestigativeAction.EVIDENCE_COLLECTION),
        ("preservation", InvestigativeAction.EVIDENCE_PRESERVATION),
        ("packaging", InvestigativeAction.EVIDENCE_PACKAGING),
        ("chain of custody", InvestigativeAction.CHAIN_OF_CUSTODY),
        ("forensic", InvestigativeAction.FORENSIC_ANALYSIS),
        ("laboratory", InvestigativeAction.FORENSIC_ANALYSIS),
        ("documentation", InvestigativeAction.DOCUMENTATION),
        ("photography", InvestigativeAction.DOCUMENTATION),
        ("biological evidence", InvestigativeAction.EVIDENCE_COLLECTION),
        ("sexual assault", InvestigativeAction.EVIDENCE_COLLECTION),
        ("rape", InvestigativeAction.EVIDENCE_COLLECTION),
        ("fingerprint", InvestigativeAction.EVIDENCE_COLLECTION),
        ("digital evidence", InvestigativeAction.EVIDENCE_COLLECTION),
    ]
    
    def __init__(self):
        self.current_doc: Optional[EvidenceManualDocument] = None
    
    def parse(self, pdf_path: Path) -> EvidenceManualDocument:
        """Parse Crime Scene Manual PDF into structured evidence blocks."""
        doc = fitz.open(pdf_path)
        self.current_doc = EvidenceManualDocument(total_pages=len(doc))
        
        # Extract all text with page numbers
        full_text = ""
        page_texts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            page_texts.append({"page": page_num + 1, "text": text})
            full_text += f"\n{text}"
        
        doc.close()
        
        # Parse blocks from the manual
        blocks = self._extract_blocks(full_text, page_texts)
        self.current_doc.blocks = blocks
        
        return self.current_doc
    
    def _extract_blocks(self, full_text: str, page_texts: list[dict]) -> list[EvidenceBlock]:
        """Extract operational evidence blocks from manual text."""
        blocks = []
        
        # Strategy 1: Look for numbered chapter/section patterns
        # Many forensic manuals use patterns like "Chapter 1", "1.0", "1.1", etc.
        chapter_pattern = re.compile(
            r'(?:chapter\s+(\d+)|(\d+)\.0)\s*[:\-]?\s*(.+?)(?=chapter\s+\d+|\d+\.0|\Z)',
            re.IGNORECASE | re.DOTALL
        )
        
        # Strategy 2: Look for section headers
        section_pattern = re.compile(
            r'\n([A-Z][A-Z\s]{5,50})\n',  # All caps headers
            re.MULTILINE
        )
        
        # Strategy 3: Extract by topic areas (most reliable for varied formats)
        blocks = self._extract_by_topics(full_text, page_texts)
        
        if not blocks:
            # Fallback: chunk by paragraphs
            blocks = self._extract_by_paragraphs(full_text, page_texts)
        
        return blocks
    
    def _extract_by_topics(self, full_text: str, page_texts: list[dict]) -> list[EvidenceBlock]:
        """Extract blocks by looking for specific forensic topics."""
        blocks = []
        block_idx = 0
        
        # Define topic patterns with their associated metadata
        topic_patterns = [
            {
                "pattern": r"(?:crime\s+scene|scene\s+of\s+(?:crime|offence)).*?(?=\n[A-Z]{2,}|\Z)",
                "title": "Securing the Crime Scene",
                "action": InvestigativeAction.SCENE_PROTECTION,
                "failure": FailureImpact.CONTAMINATION,
            },
            {
                "pattern": r"first\s+(?:responder|officer|responding).*?(?=\n[A-Z]{2,}|\Z)",
                "title": "First Responder Duties",
                "action": InvestigativeAction.SCENE_PROTECTION,
                "failure": FailureImpact.CONTAMINATION,
            },
            {
                "pattern": r"(?:biological\s+evidence|blood|semen|dna).*?(?:collect|preserv|packag).*?(?=\n[A-Z]{2,}|\Z)",
                "title": "Biological Evidence Collection",
                "action": InvestigativeAction.EVIDENCE_COLLECTION,
                "failure": FailureImpact.CONTAMINATION,
                "evidence_types": [EvidenceType.BIOLOGICAL],
            },
            {
                "pattern": r"(?:sexual\s+(?:assault|offence)|rape).*?(?:evidence|examination|collection).*?(?=\n[A-Z]{2,}|\Z)",
                "title": "Sexual Assault Evidence Collection",
                "action": InvestigativeAction.EVIDENCE_COLLECTION,
                "failure": FailureImpact.CASE_WEAKENING,
                "case_types": ["rape", "sexual_assault"],
                "evidence_types": [EvidenceType.BIOLOGICAL, EvidenceType.PHYSICAL],
            },
            {
                "pattern": r"chain\s+of\s+custody.*?(?=\n[A-Z]{2,}|\Z)",
                "title": "Chain of Custody",
                "action": InvestigativeAction.CHAIN_OF_CUSTODY,
                "failure": FailureImpact.INADMISSIBILITY,
            },
            {
                "pattern": r"(?:fingerprint|latent\s+print).*?(?=\n[A-Z]{2,}|\Z)",
                "title": "Fingerprint Evidence Collection",
                "action": InvestigativeAction.EVIDENCE_COLLECTION,
                "failure": FailureImpact.CASE_WEAKENING,
                "evidence_types": [EvidenceType.TRACE],
            },
            {
                "pattern": r"(?:digital|electronic|mobile|computer).*?evidence.*?(?=\n[A-Z]{2,}|\Z)",
                "title": "Digital Evidence Handling",
                "action": InvestigativeAction.EVIDENCE_COLLECTION,
                "failure": FailureImpact.INADMISSIBILITY,
                "evidence_types": [EvidenceType.DIGITAL],
            },
            {
                "pattern": r"photograph.*?(?:scene|evidence).*?(?=\n[A-Z]{2,}|\Z)",
                "title": "Crime Scene Photography",
                "action": InvestigativeAction.DOCUMENTATION,
                "failure": FailureImpact.CASE_WEAKENING,
            },
            {
                "pattern": r"packag.*?(?:evidence|material).*?(?=\n[A-Z]{2,}|\Z)",
                "title": "Evidence Packaging",
                "action": InvestigativeAction.EVIDENCE_PACKAGING,
                "failure": FailureImpact.CONTAMINATION,
            },
            {
                "pattern": r"preserv.*?(?:evidence|biological).*?(?=\n[A-Z]{2,}|\Z)",
                "title": "Evidence Preservation",
                "action": InvestigativeAction.EVIDENCE_PRESERVATION,
                "failure": FailureImpact.CONTAMINATION,
            },
            {
                "pattern": r"(?:forensic|fsl|laboratory).*?(?:analysis|examination).*?(?=\n[A-Z]{2,}|\Z)",
                "title": "Forensic Laboratory Analysis",
                "action": InvestigativeAction.FORENSIC_ANALYSIS,
                "failure": FailureImpact.CASE_WEAKENING,
            },
        ]
        
        for topic in topic_patterns:
            matches = re.finditer(topic["pattern"], full_text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                text = match.group(0).strip()
                if len(text) < 50:  # Skip very short matches
                    continue
                
                block_idx += 1
                block = EvidenceBlock(
                    block_id=f"EVIDENCE_BLOCK_{block_idx:03d}",
                    title=topic["title"],
                    text=text[:2000],  # Limit text length
                    investigative_action=topic["action"],
                    failure_impact=topic.get("failure", FailureImpact.NONE),
                    evidence_types=topic.get("evidence_types", []),
                    case_types=topic.get("case_types", ["all"]),
                    page=self._find_page_for_text(text[:100], page_texts)
                )
                
                # Classify further
                self._classify_block(block)
                blocks.append(block)
        
        return blocks
    
    def _extract_by_paragraphs(self, full_text: str, page_texts: list[dict]) -> list[EvidenceBlock]:
        """Fallback: Extract blocks by splitting into meaningful paragraphs."""
        blocks = []
        
        # Split by double newlines or section markers
        paragraphs = re.split(r'\n{2,}', full_text)
        
        block_idx = 0
        for para in paragraphs:
            para = para.strip()
            if len(para) < 100:  # Skip very short paragraphs
                continue
            
            # Check if paragraph is evidence-related
            para_lower = para.lower()
            if not any(kw in para_lower for kw in ["evidence", "scene", "collect", "forensic", "preserve", "sample"]):
                continue
            
            block_idx += 1
            title = self._extract_title(para)
            
            block = EvidenceBlock(
                block_id=f"EVIDENCE_BLOCK_{block_idx:03d}",
                title=title,
                text=para[:2000],
                page=self._find_page_for_text(para[:100], page_texts)
            )
            
            self._classify_block(block)
            blocks.append(block)
        
        return blocks
    
    def _extract_title(self, text: str) -> str:
        """Extract a title from the first line or generate one."""
        lines = text.split('\n')
        first_line = lines[0].strip()
        
        # If first line is short enough, use it as title
        if len(first_line) < 100 and len(first_line) > 5:
            return first_line[:80]
        
        # Otherwise, look for keywords to generate title
        text_lower = text.lower()
        for kw, _ in self.SECTION_HEADERS:
            if kw in text_lower:
                return kw.title()
        
        return "Evidence Procedure"
    
    def _find_page_for_text(self, text: str, page_texts: list[dict]) -> int:
        """Find which page contains the given text."""
        search_text = text[:50].lower()
        for pt in page_texts:
            if search_text in pt["text"].lower():
                return pt["page"]
        return 1
    
    def _classify_block(self, block: EvidenceBlock) -> None:
        """Classify a block's evidence types, action type, and failure impact."""
        text_lower = block.text.lower()
        title_lower = block.title.lower()
        combined = title_lower + " " + text_lower
        
        # Classify evidence types
        if not block.evidence_types:
            for evidence_type, keywords in self.EVIDENCE_TYPE_KEYWORDS.items():
                if any(kw in combined for kw in keywords):
                    block.evidence_types.append(evidence_type)
            if not block.evidence_types:
                block.evidence_types = [EvidenceType.GENERAL]
        
        # Classify investigative action
        if block.investigative_action == InvestigativeAction.GENERAL:
            action_scores = {}
            for action, keywords in self.ACTION_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in combined)
                if score > 0:
                    action_scores[action] = score
            if action_scores:
                block.investigative_action = max(action_scores, key=action_scores.get)  # type: ignore
        
        # Classify failure impact
        if block.failure_impact == FailureImpact.NONE:
            for failure, keywords in self.FAILURE_KEYWORDS.items():
                if any(kw in combined for kw in keywords):
                    block.failure_impact = failure
                    break
            # Default failure impact based on action
            if block.failure_impact == FailureImpact.NONE:
                if block.investigative_action in [InvestigativeAction.SCENE_PROTECTION, 
                                                   InvestigativeAction.EVIDENCE_PRESERVATION]:
                    block.failure_impact = FailureImpact.CONTAMINATION
                elif block.investigative_action == InvestigativeAction.CHAIN_OF_CUSTODY:
                    block.failure_impact = FailureImpact.INADMISSIBILITY
                else:
                    block.failure_impact = FailureImpact.CASE_WEAKENING
        
        # Detect case types if applicable
        if "all" in block.case_types:
            if any(word in combined for word in ["rape", "sexual", "assault"]):
                block.case_types = ["rape", "sexual_assault"]
            elif "murder" in combined or "homicide" in combined:
                block.case_types = ["murder", "homicide"]
        
        # Detect linked procedural stage
        if "medical" in combined or "examination" in combined:
            block.linked_stage = "medical_examination"
        elif "arrest" in combined:
            block.linked_stage = "arrest"
        elif "investigation" in combined or "io" in combined:
            block.linked_stage = "investigation"
        else:
            block.linked_stage = "evidence_collection"
        
        # Set priority based on importance
        priority = 1
        if EvidenceType.BIOLOGICAL in block.evidence_types:
            priority += 2  # Biological evidence is critical in sexual assault cases
        if block.investigative_action == InvestigativeAction.SCENE_PROTECTION:
            priority += 1  # First response is critical
        if block.failure_impact in [FailureImpact.INADMISSIBILITY, FailureImpact.ACQUITTAL_RISK]:
            priority += 2  # High impact failures
        if "rape" in block.case_types or "sexual_assault" in block.case_types:
            priority += 1  # Priority for our target use case
        block.priority = priority
        
        # Extract BNSS section references
        bnss_pattern = re.compile(r'section\s+(\d+)\s+of\s+(?:BNSS|Cr\.?P\.?C\.?)', re.IGNORECASE)
        block.bnss_sections = list(set(m.group(1) for m in bnss_pattern.finditer(block.text)))


def parse_evidence_manual(pdf_path: Path) -> EvidenceManualDocument:
    """Parse Crime Scene Manual PDF and return structured document."""
    parser = EvidenceManualParser()
    return parser.parse(pdf_path)
