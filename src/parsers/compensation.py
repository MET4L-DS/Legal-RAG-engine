"""
Compensation Scheme Parser for NALSA Victim Compensation Scheme (2018).

Tier-2 Document: Conditional depth layer for compensation-related questions.

This parser extracts policy-driven blocks for victim relief and rehabilitation queries.
It produces CompensationBlock objects with compensation types, eligibility criteria,
application procedures, and amounts.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


# =============================================================================
# ENUMS: CompensationType, ApplicationStage, Authority, CrimeCovered
# =============================================================================


class CompensationType(Enum):
    """Types of compensation available."""
    INTERIM = "interim"  # Immediate relief before trial
    FINAL = "final"  # After conviction/acquittal
    MEDICAL = "medical"  # Medical expenses
    REHABILITATION = "rehabilitation"  # Long-term rehabilitation
    LEGAL_AID = "legal_aid"  # Legal assistance
    GENERAL = "general"


class ApplicationStage(Enum):
    """When compensation can be applied for."""
    POST_FIR = "post_fir"  # After FIR is registered
    DURING_TRIAL = "during_trial"  # During trial proceedings
    POST_TRIAL = "post_trial"  # After trial completion
    POST_CONVICTION = "post_conviction"  # After conviction
    ANYTIME = "anytime"  # Can be applied at any stage


class Authority(Enum):
    """Authority to approach for compensation."""
    DLSA = "dlsa"  # District Legal Services Authority
    SLSA = "slsa"  # State Legal Services Authority
    NALSA = "nalsa"  # National Legal Services Authority
    COURT = "court"  # Presiding Court
    DCW = "dcw"  # District/State Commission for Women
    GENERAL = "general"


class CrimeCovered(Enum):
    """Types of crimes covered under the scheme."""
    RAPE = "rape"
    GANG_RAPE = "gang_rape"
    SEXUAL_ASSAULT = "sexual_assault"
    ACID_ATTACK = "acid_attack"
    TRAFFICKING = "trafficking"
    MURDER = "murder"  # For dependents
    DOMESTIC_VIOLENCE = "domestic_violence"
    CHILD_ABUSE = "child_abuse"
    OTHER = "other"


@dataclass
class CompensationBlock:
    """A single policy-driven block from the NALSA Compensation Scheme."""
    block_id: str
    title: str
    text: str
    compensation_type: CompensationType = CompensationType.GENERAL
    application_stage: ApplicationStage = ApplicationStage.ANYTIME
    authority: Authority = Authority.DLSA
    crimes_covered: list[CrimeCovered] = field(default_factory=list)
    eligibility_criteria: list[str] = field(default_factory=list)
    amount_range: Optional[str] = None  # e.g., "Rs. 3,00,000 to Rs. 10,00,000"
    requires_conviction: bool = False
    time_limit: Optional[str] = None
    documents_required: list[str] = field(default_factory=list)
    bnss_sections: list[str] = field(default_factory=list)  # e.g., §396
    page: int = 0
    priority: int = 1
    embedding: Optional[list[float]] = None
    
    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "title": self.title,
            "text": self.text,
            "compensation_type": self.compensation_type.value,
            "application_stage": self.application_stage.value,
            "authority": self.authority.value,
            "crimes_covered": [c.value for c in self.crimes_covered],
            "eligibility_criteria": self.eligibility_criteria,
            "amount_range": self.amount_range,
            "requires_conviction": self.requires_conviction,
            "time_limit": self.time_limit,
            "documents_required": self.documents_required,
            "bnss_sections": self.bnss_sections,
            "page": self.page,
            "priority": self.priority
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CompensationBlock":
        return cls(
            block_id=data["block_id"],
            title=data["title"],
            text=data["text"],
            compensation_type=CompensationType(data.get("compensation_type", "general")),
            application_stage=ApplicationStage(data.get("application_stage", "anytime")),
            authority=Authority(data.get("authority", "dlsa")),
            crimes_covered=[CrimeCovered(c) for c in data.get("crimes_covered", [])],
            eligibility_criteria=data.get("eligibility_criteria", []),
            amount_range=data.get("amount_range"),
            requires_conviction=data.get("requires_conviction", False),
            time_limit=data.get("time_limit"),
            documents_required=data.get("documents_required", []),
            bnss_sections=data.get("bnss_sections", []),
            page=data.get("page", 0),
            priority=data.get("priority", 1)
        )
    
    def get_citation(self) -> str:
        """Generate citation for this block."""
        return f"NALSA Compensation Scheme (2018) - {self.title}"


@dataclass
class CompensationSchemeDocument:
    """Complete NALSA Compensation Scheme document."""
    doc_id: str = "NALSA_COMPENSATION_2018"
    doc_type: str = "COMPENSATION_SCHEME"
    title: str = "NALSA Compensation Scheme for Women Victims/Survivors of Sexual Assault/Other Crimes"
    short_name: str = "NALSA Scheme"
    source: str = "NALSA 2018"
    blocks: list[CompensationBlock] = field(default_factory=list)
    total_pages: int = 0
    crimes_covered: list[str] = field(default_factory=lambda: ["rape", "sexual_assault", "acid_attack"])
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
            "crimes_covered": self.crimes_covered
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CompensationSchemeDocument":
        return cls(
            doc_id=data["doc_id"],
            doc_type=data.get("doc_type", "COMPENSATION_SCHEME"),
            title=data["title"],
            short_name=data.get("short_name", "NALSA Scheme"),
            source=data.get("source", "NALSA 2018"),
            blocks=[CompensationBlock.from_dict(b) for b in data.get("blocks", [])],
            total_pages=data.get("total_pages", 0),
            crimes_covered=data.get("crimes_covered", ["rape", "sexual_assault"])
        )


class CompensationSchemeParser:
    """Parser for NALSA Victim Compensation Scheme (2018)."""
    
    # Crime keywords for classification
    CRIME_KEYWORDS = {
        CrimeCovered.RAPE: ["rape", "sexual intercourse without consent"],
        CrimeCovered.GANG_RAPE: ["gang rape", "gang-rape", "multiple perpetrators"],
        CrimeCovered.SEXUAL_ASSAULT: ["sexual assault", "molestation", "outraging modesty", "sexual harassment"],
        CrimeCovered.ACID_ATTACK: ["acid attack", "acid", "corrosive substance"],
        CrimeCovered.TRAFFICKING: ["trafficking", "trafficked", "prostitution"],
        CrimeCovered.MURDER: ["murder", "death", "homicide", "killed"],
        CrimeCovered.DOMESTIC_VIOLENCE: ["domestic violence", "cruelty", "dowry"],
        CrimeCovered.CHILD_ABUSE: ["child", "minor", "pocso", "juvenile"],
    }
    
    # Compensation type keywords
    COMPENSATION_TYPE_KEYWORDS = {
        CompensationType.INTERIM: ["interim", "immediate", "emergency", "first stage", "initial"],
        CompensationType.FINAL: ["final", "second stage", "ultimate", "remaining"],
        CompensationType.MEDICAL: ["medical", "treatment", "hospital", "healthcare"],
        CompensationType.REHABILITATION: ["rehabilitation", "livelihood", "vocational", "skill", "employment"],
        CompensationType.LEGAL_AID: ["legal aid", "legal assistance", "lawyer", "advocate"],
    }
    
    # Authority keywords
    AUTHORITY_KEYWORDS = {
        Authority.DLSA: ["district legal services", "dlsa", "district authority"],
        Authority.SLSA: ["state legal services", "slsa", "state authority"],
        Authority.NALSA: ["national legal services", "nalsa"],
        Authority.COURT: ["court", "magistrate", "sessions", "trial court"],
        Authority.DCW: ["women commission", "dcw", "ncw", "state commission"],
    }
    
    # Amount patterns
    AMOUNT_PATTERNS = [
        r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:to|-)?\s*(?:Rs\.?\s*)?([\d,]+(?:\.\d+)?)?',
        r'rupees?\s*([\d,]+)',
        r'([\d,]+)\s*(?:lakh|lac)',
    ]
    
    def __init__(self):
        self.current_doc: Optional[CompensationSchemeDocument] = None
    
    def parse(self, pdf_path: Path) -> CompensationSchemeDocument:
        """Parse NALSA Compensation Scheme PDF into structured blocks."""
        doc = fitz.open(pdf_path)
        self.current_doc = CompensationSchemeDocument(total_pages=len(doc))
        
        # Extract all text with page numbers
        full_text = ""
        page_texts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            page_texts.append({"page": page_num + 1, "text": text})
            full_text += f"\n{text}"
        
        doc.close()
        
        # Parse blocks from the scheme
        blocks = self._extract_blocks(full_text, page_texts)
        self.current_doc.blocks = blocks
        
        return self.current_doc
    
    def _extract_blocks(self, full_text: str, page_texts: list[dict]) -> list[CompensationBlock]:
        """Extract policy-driven compensation blocks from scheme text."""
        blocks = []
        
        # Strategy 1: Extract by numbered clauses (common in legal schemes)
        clause_pattern = re.compile(
            r'(\d+\.)\s*(.+?)(?=\n\d+\.|$)',
            re.DOTALL
        )
        
        # Strategy 2: Extract by topic areas
        blocks = self._extract_by_topics(full_text, page_texts)
        
        if not blocks:
            # Fallback: extract by paragraphs with compensation keywords
            blocks = self._extract_by_paragraphs(full_text, page_texts)
        
        return blocks
    
    def _extract_by_topics(self, full_text: str, page_texts: list[dict]) -> list[CompensationBlock]:
        """Extract blocks by looking for specific compensation topics."""
        blocks = []
        block_idx = 0
        
        # Define topic patterns with their associated metadata
        topic_patterns = [
            {
                "pattern": r"(?:eligibility|who\s+can\s+(?:apply|claim)).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Eligibility for Compensation",
                "comp_type": CompensationType.GENERAL,
            },
            {
                "pattern": r"interim\s+(?:compensation|relief).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Interim Compensation",
                "comp_type": CompensationType.INTERIM,
                "stage": ApplicationStage.POST_FIR,
            },
            {
                "pattern": r"final\s+(?:compensation|relief).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Final Compensation",
                "comp_type": CompensationType.FINAL,
                "stage": ApplicationStage.POST_TRIAL,
            },
            {
                "pattern": r"(?:rape|sexual\s+(?:assault|offence)).*?(?:compensation|amount|relief).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Compensation for Rape/Sexual Assault",
                "comp_type": CompensationType.GENERAL,
                "crimes": [CrimeCovered.RAPE, CrimeCovered.SEXUAL_ASSAULT],
            },
            {
                "pattern": r"acid\s+attack.*?(?:compensation|amount|relief).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Compensation for Acid Attack Victims",
                "comp_type": CompensationType.GENERAL,
                "crimes": [CrimeCovered.ACID_ATTACK],
            },
            {
                "pattern": r"(?:medical|treatment).*?(?:expense|cost|reimbursement).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Medical Expenses Reimbursement",
                "comp_type": CompensationType.MEDICAL,
            },
            {
                "pattern": r"rehabilitation.*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Rehabilitation Support",
                "comp_type": CompensationType.REHABILITATION,
            },
            {
                "pattern": r"(?:application|procedure|how\s+to\s+apply).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Application Procedure",
                "comp_type": CompensationType.GENERAL,
            },
            {
                "pattern": r"(?:document|proof|evidence)\s+(?:required|needed).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Documents Required",
                "comp_type": CompensationType.GENERAL,
            },
            {
                "pattern": r"(?:amount|quantum|scale).*?compensation.*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Compensation Amounts",
                "comp_type": CompensationType.GENERAL,
            },
            {
                "pattern": r"(?:time\s+limit|limitation|period).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Time Limits for Application",
                "comp_type": CompensationType.GENERAL,
            },
            {
                "pattern": r"(?:legal\s+(?:aid|assistance)|free\s+legal).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Free Legal Aid",
                "comp_type": CompensationType.LEGAL_AID,
            },
            {
                "pattern": r"(?:conviction|without\s+conviction|irrespective\s+of).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Compensation Without Conviction",
                "comp_type": CompensationType.GENERAL,
            },
            {
                "pattern": r"(?:dlsa|slsa|legal\s+services\s+authority).*?(?=\n[A-Z]{2,}|\n\d+\.|\Z)",
                "title": "Role of Legal Services Authority",
                "comp_type": CompensationType.GENERAL,
            },
        ]
        
        for topic in topic_patterns:
            matches = re.finditer(topic["pattern"], full_text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                text = match.group(0).strip()
                if len(text) < 30:  # Skip very short matches
                    continue
                
                block_idx += 1
                block = CompensationBlock(
                    block_id=f"COMPENSATION_BLOCK_{block_idx:03d}",
                    title=topic["title"],
                    text=text[:2000],  # Limit text length
                    compensation_type=topic.get("comp_type", CompensationType.GENERAL),
                    application_stage=topic.get("stage", ApplicationStage.ANYTIME),
                    crimes_covered=topic.get("crimes", []),
                    page=self._find_page_for_text(text[:100], page_texts)
                )
                
                # Classify further
                self._classify_block(block)
                blocks.append(block)
        
        return blocks
    
    def _extract_by_paragraphs(self, full_text: str, page_texts: list[dict]) -> list[CompensationBlock]:
        """Fallback: Extract blocks by splitting into meaningful paragraphs."""
        blocks = []
        
        # Split by double newlines or numbered clauses
        paragraphs = re.split(r'\n{2,}|\n(?=\d+\.)', full_text)
        
        block_idx = 0
        for para in paragraphs:
            para = para.strip()
            if len(para) < 50:  # Skip very short paragraphs
                continue
            
            # Check if paragraph is compensation-related
            para_lower = para.lower()
            if not any(kw in para_lower for kw in ["compensation", "victim", "relief", "amount", "rupees", "rs", "scheme", "eligible"]):
                continue
            
            block_idx += 1
            title = self._extract_title(para)
            
            block = CompensationBlock(
                block_id=f"COMPENSATION_BLOCK_{block_idx:03d}",
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
        
        # Remove leading numbers
        first_line = re.sub(r'^\d+\.\s*', '', first_line)
        
        # If first line is short enough, use it as title
        if len(first_line) < 80 and len(first_line) > 5:
            return first_line[:60]
        
        # Otherwise, look for keywords to generate title
        text_lower = text.lower()
        if "interim" in text_lower:
            return "Interim Compensation"
        elif "final" in text_lower:
            return "Final Compensation"
        elif "eligible" in text_lower:
            return "Eligibility Criteria"
        elif "amount" in text_lower or "quantum" in text_lower:
            return "Compensation Amount"
        elif "application" in text_lower or "procedure" in text_lower:
            return "Application Procedure"
        
        return "Compensation Provision"
    
    def _find_page_for_text(self, text: str, page_texts: list[dict]) -> int:
        """Find which page contains the given text."""
        search_text = text[:50].lower()
        for pt in page_texts:
            if search_text in pt["text"].lower():
                return pt["page"]
        return 1
    
    def _classify_block(self, block: CompensationBlock) -> None:
        """Classify a block's compensation type, authority, crimes covered, etc."""
        text_lower = block.text.lower()
        title_lower = block.title.lower()
        combined = title_lower + " " + text_lower
        
        # Classify compensation type
        if block.compensation_type == CompensationType.GENERAL:
            for comp_type, keywords in self.COMPENSATION_TYPE_KEYWORDS.items():
                if any(kw in combined for kw in keywords):
                    block.compensation_type = comp_type
                    break
        
        # Classify crimes covered
        if not block.crimes_covered:
            for crime, keywords in self.CRIME_KEYWORDS.items():
                if any(kw in combined for kw in keywords):
                    block.crimes_covered.append(crime)
            if not block.crimes_covered:
                block.crimes_covered = [CrimeCovered.OTHER]
        
        # Classify authority
        for authority, keywords in self.AUTHORITY_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                block.authority = authority
                break
        
        # Detect application stage
        if "fir" in combined or "before trial" in combined or "first stage" in combined:
            block.application_stage = ApplicationStage.POST_FIR
        elif "during trial" in combined:
            block.application_stage = ApplicationStage.DURING_TRIAL
        elif "after trial" in combined or "post trial" in combined or "second stage" in combined:
            block.application_stage = ApplicationStage.POST_TRIAL
        elif "conviction" in combined:
            block.application_stage = ApplicationStage.POST_CONVICTION
        
        # Detect if conviction is required
        if "without conviction" in combined or "irrespective of conviction" in combined or "not necessary" in combined:
            block.requires_conviction = False
        elif "after conviction" in combined or "upon conviction" in combined:
            block.requires_conviction = True
        
        # Extract amounts
        for pattern in self.AMOUNT_PATTERNS:
            match = re.search(pattern, block.text, re.IGNORECASE)
            if match:
                groups = [g for g in match.groups() if g]
                if len(groups) >= 2:
                    block.amount_range = f"Rs. {groups[0]} to Rs. {groups[1]}"
                elif groups:
                    block.amount_range = f"Rs. {groups[0]}"
                break
        
        # Extract time limits
        time_patterns = [
            r'within\s+(\d+)\s+(?:days?|months?|years?)',
            r'(\d+)\s+(?:days?|months?|years?)\s+(?:from|of)',
        ]
        for pattern in time_patterns:
            match = re.search(pattern, combined)
            if match:
                block.time_limit = match.group(0)
                break
        
        # Extract document requirements
        doc_keywords = ["fir copy", "medical report", "identity proof", "photograph", 
                        "bank account", "address proof", "death certificate", "disability certificate"]
        for doc_kw in doc_keywords:
            if doc_kw in combined:
                block.documents_required.append(doc_kw.title())
        
        # Extract BNSS section references (§396 is key for compensation)
        bnss_pattern = re.compile(r'section\s+(\d+)\s+of\s+(?:BNSS|Cr\.?P\.?C\.?)|§\s*(\d+)', re.IGNORECASE)
        for match in bnss_pattern.finditer(block.text):
            sec = match.group(1) or match.group(2)
            if sec and sec not in block.bnss_sections:
                block.bnss_sections.append(sec)
        
        # Set priority based on importance
        priority = 1
        if block.compensation_type == CompensationType.INTERIM:
            priority += 2  # Interim compensation is most urgent for victims
        if CrimeCovered.RAPE in block.crimes_covered or CrimeCovered.SEXUAL_ASSAULT in block.crimes_covered:
            priority += 1  # Our primary use case
        if not block.requires_conviction:
            priority += 1  # Important - victims can get help without waiting for conviction
        if block.amount_range:
            priority += 1  # Contains concrete amount info
        if block.documents_required:
            priority += 1  # Actionable information
        block.priority = priority
        
        # Add eligibility criteria if detected
        eligibility_patterns = [
            r'victim\s+(?:of|who)',
            r'any\s+(?:woman|person)',
            r'survivor\s+of',
        ]
        for pattern in eligibility_patterns:
            if re.search(pattern, combined):
                block.eligibility_criteria.append("Victim/survivor of specified crime")
                break


def parse_compensation_scheme(pdf_path: Path) -> CompensationSchemeDocument:
    """Parse NALSA Compensation Scheme PDF and return structured document."""
    parser = CompensationSchemeParser()
    return parser.parse(pdf_path)
