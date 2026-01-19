"""
Document parsers for the Legal RAG system.

This package contains parsers organized by tier:
- pdf: Core legal document parser (BNS, BNSS, BSA)
- sop: Tier-1 SOP parser for sexual offence cases
- evidence: Tier-2 evidence manual parser
- compensation: Tier-2 compensation scheme parser
- general_sop: Tier-3 general SOP parser for all crimes
"""

# PDF Parser (Core)
from .pdf import LegalPDFParser, parse_all_documents

# Tier-1: Sexual Offence SOP
from .sop import (
    SOPDocument,
    ProceduralBlock,
    ProceduralStage,
    Stakeholder,
    ActionType,
    SOPParser,
    parse_sop,
)

# Tier-2: Evidence Manual
from .evidence import (
    EvidenceManualDocument,
    EvidenceBlock,
    EvidenceType,
    InvestigativeAction,
    FailureImpact,
    EvidenceManualParser,
    parse_evidence_manual,
)

# Tier-2: Compensation Scheme
from .compensation import (
    CompensationSchemeDocument,
    CompensationBlock,
    CompensationType,
    ApplicationStage,
    Authority,
    CrimeCovered,
    CompensationSchemeParser,
    parse_compensation_scheme,
)

# Tier-3: General SOP
from .general_sop import (
    GeneralSOPDocument,
    GeneralSOPBlock,
    SOPGroup,
    GeneralSOPParser,
    parse_general_sop,
)

__all__ = [
    # PDF Parser
    "LegalPDFParser",
    "parse_all_documents",
    # Tier-1
    "SOPDocument",
    "ProceduralBlock",
    "ProceduralStage",
    "Stakeholder",
    "ActionType",
    "SOPParser",
    "parse_sop",
    # Tier-2 Evidence
    "EvidenceManualDocument",
    "EvidenceBlock",
    "EvidenceType",
    "InvestigativeAction",
    "FailureImpact",
    "EvidenceManualParser",
    "parse_evidence_manual",
    # Tier-2 Compensation
    "CompensationSchemeDocument",
    "CompensationBlock",
    "CompensationType",
    "ApplicationStage",
    "Authority",
    "CrimeCovered",
    "CompensationSchemeParser",
    "parse_compensation_scheme",
    # Tier-3
    "GeneralSOPDocument",
    "GeneralSOPBlock",
    "SOPGroup",
    "GeneralSOPParser",
    "parse_general_sop",
]
