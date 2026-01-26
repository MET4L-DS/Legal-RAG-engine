"""
Source Fetcher Module.

Fetches verbatim source content from parsed documents.
NO LLM involvement - returns exact text as parsed.

Supports:
- General SOP blocks (GSOP_001, etc.)
- Rape SOP blocks
- BNSS/BNS/BSA sections
- Evidence Manual blocks
- Compensation Scheme blocks

Highlight Support:
- Accepts optional highlight_snippet parameter
- Computes character offsets for frontend highlighting
- Enables auto-scroll to referenced text
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .schemas import SourceResponse, SourceType, HighlightRange
from .config import get_settings


logger = logging.getLogger(__name__)

# Cache for loaded documents (loaded once on first access)
_document_cache: dict[str, dict] = {}


def _get_parsed_dir() -> Path:
    """Get the parsed data directory."""
    settings = get_settings()
    return Path(settings.index_dir).parent / "parsed"


def _load_document(filename: str) -> Optional[dict]:
    """Load and cache a parsed document."""
    if filename in _document_cache:
        logger.debug(f"[SOURCE] Cache hit for document: {filename}")
        return _document_cache[filename]
    
    parsed_dir = _get_parsed_dir()
    filepath = parsed_dir / filename
    
    if not filepath.exists():
        logger.warning(f"[SOURCE] Document not found: {filepath}")
        return None
    
    try:
        logger.debug(f"[SOURCE] Loading document from disk: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            doc = json.load(f)
            _document_cache[filename] = doc
            logger.info(f"[SOURCE] Document cached: {filename} (doc_id={doc.get('doc_id', 'N/A')})")
            return doc
    except Exception as e:
        logger.error(f"[SOURCE] Failed to load document {filename}: {e}")
        return None


def _normalize_section_id(source_id: str) -> str:
    """
    Normalize section ID for matching.
    
    Handles variations like:
    - "Section 183" → "183"
    - "BNSS Section 183" → "183"
    - "s. 183" → "183"
    - "§183" → "183"
    """
    # Remove common prefixes
    normalized = source_id.lower().strip()
    normalized = re.sub(r'^(bnss|bns|bsa)\s*', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'^(section|sec\.?|s\.?|§)\s*', '', normalized, flags=re.IGNORECASE)
    normalized = normalized.strip()
    
    if normalized != source_id:
        logger.debug(f"[SOURCE] Normalized section ID: '{source_id}' → '{normalized}'")
    
    return normalized


def _compute_highlights(content: str, snippet: str) -> list[HighlightRange]:
    """
    Compute highlight ranges by finding snippet in content.
    
    Uses fuzzy matching strategies:
    1. Exact match (fastest)
    2. Normalized whitespace match
    3. Prefix match (for truncated snippets ending with "...")
    4. Sentence-level match (for partial matches)
    
    Returns list of HighlightRange objects.
    """
    if not snippet or not content:
        return []
    
    highlights = []
    
    # Remove trailing "..." from truncated snippets
    clean_snippet = snippet.rstrip(".")
    if clean_snippet.endswith(".."):
        clean_snippet = clean_snippet[:-2].rstrip()
    
    # Strategy 1: Exact match
    idx = content.find(clean_snippet)
    if idx >= 0:
        logger.debug(f"[HIGHLIGHT] Exact match at offset {idx}")
        highlights.append(HighlightRange(
            start=idx,
            end=idx + len(clean_snippet),
            reason="Referenced in response"
        ))
        return highlights
    
    # Strategy 2: Normalized whitespace match
    # Collapse multiple whitespace to single space
    normalized_content = re.sub(r'\s+', ' ', content)
    normalized_snippet = re.sub(r'\s+', ' ', clean_snippet)
    
    idx = normalized_content.find(normalized_snippet)
    if idx >= 0:
        # Map back to original content position (approximate)
        # Find the actual start by searching for first N chars
        first_words = normalized_snippet[:50]
        original_pattern = re.sub(r' ', r'\\s+', re.escape(first_words))
        match = re.search(original_pattern, content)
        if match:
            logger.debug(f"[HIGHLIGHT] Whitespace-normalized match at offset {match.start()}")
            # Estimate end position based on snippet length
            estimated_end = min(match.start() + len(clean_snippet) + 50, len(content))
            highlights.append(HighlightRange(
                start=match.start(),
                end=estimated_end,
                reason="Referenced in response"
            ))
            return highlights
    
    # Strategy 3: Prefix match for truncated snippets
    # Try matching just the first sentence or first N characters
    if len(clean_snippet) > 100:
        prefix = clean_snippet[:100]
        idx = content.find(prefix)
        if idx >= 0:
            logger.debug(f"[HIGHLIGHT] Prefix match at offset {idx}")
            # Extend to a reasonable length (original snippet length or sentence end)
            end_idx = idx + len(clean_snippet)
            # Find sentence boundary
            sentence_end = content.find('. ', end_idx)
            if sentence_end > 0 and sentence_end - idx < len(clean_snippet) * 1.5:
                end_idx = sentence_end + 1
            highlights.append(HighlightRange(
                start=idx,
                end=min(end_idx, len(content)),
                reason="Referenced in response"
            ))
            return highlights
    
    # Strategy 4: First sentence match
    # Extract first sentence from snippet and find it
    first_sentence_match = re.match(r'^([^.!?]+[.!?])', clean_snippet)
    if first_sentence_match:
        first_sentence = first_sentence_match.group(1).strip()
        if len(first_sentence) > 20:  # Only if substantial
            idx = content.find(first_sentence)
            if idx >= 0:
                logger.debug(f"[HIGHLIGHT] First sentence match at offset {idx}")
                highlights.append(HighlightRange(
                    start=idx,
                    end=idx + len(first_sentence),
                    reason="Referenced in response"
                ))
                return highlights
    
    logger.debug(f"[HIGHLIGHT] No match found for snippet: {clean_snippet[:50]}...")
    return highlights




def _fetch_sop_block(doc: dict, block_id: str) -> Optional[SourceResponse]:
    """Fetch a block from SOP-style documents."""
    blocks = doc.get("blocks", [])
    logger.debug(f"[SOURCE] Searching SOP blocks for: {block_id} (total blocks: {len(blocks)})")
    
    # Normalize block_id for comparison
    block_id_upper = block_id.upper()
    
    for block in blocks:
        if block.get("block_id", "").upper() == block_id_upper:
            logger.info(f"[SOURCE] Found SOP block: {block_id} → '{block.get('title', '')[:50]}...'")
            return SourceResponse(
                source_type=SourceType.GENERAL_SOP if "GSOP" in block_id_upper else SourceType.SOP,
                doc_id=doc.get("doc_id", ""),
                title=block.get("title", ""),
                section_id=block.get("block_id", ""),
                content=block.get("text", ""),
                legal_references=block.get("legal_references", []),
                metadata={
                    "procedural_stage": block.get("procedural_stage"),
                    "stakeholders": block.get("stakeholders", []),
                    "action_type": block.get("action_type"),
                    "time_limit": block.get("time_limit"),
                    "sop_group": block.get("sop_group"),
                    "priority": block.get("priority"),
                }
            )
    
    logger.warning(f"[SOURCE] SOP block not found: {block_id}")
    return None


def _fetch_legal_section(doc: dict, section_no: str, source_type: SourceType) -> Optional[SourceResponse]:
    """Fetch a section from legal act documents (BNSS/BNS/BSA)."""
    chapters = doc.get("chapters", [])
    total_sections = sum(len(ch.get("sections", [])) for ch in chapters)
    logger.debug(f"[SOURCE] Searching {source_type.value} for section: {section_no} (chapters: {len(chapters)}, sections: {total_sections})")
    
    # Normalize section number
    section_normalized = _normalize_section_id(section_no)
    
    for chapter in chapters:
        for section in chapter.get("sections", []):
            if section.get("section_no") == section_normalized:
                logger.info(f"[SOURCE] Found {source_type.value} Section {section_normalized}: '{section.get('section_title', '')[:50]}...'")
                return SourceResponse(
                    source_type=source_type,
                    doc_id=doc.get("doc_id", ""),
                    title=section.get("section_title", ""),
                    section_id=f"Section {section.get('section_no')}",
                    content=section.get("full_text", ""),
                    legal_references=[],
                    metadata={
                        "chapter_no": chapter.get("chapter_no"),
                        "chapter_title": chapter.get("chapter_title"),
                        "page_start": section.get("page_start"),
                        "page_end": section.get("page_end"),
                    }
                )
    
    logger.warning(f"[SOURCE] Legal section not found: {source_type.value} Section {section_no} (normalized: {section_normalized})")
    return None


def _fetch_evidence_block(doc: dict, block_id: str) -> Optional[SourceResponse]:
    """Fetch a block from Evidence Manual."""
    blocks = doc.get("blocks", [])
    block_id_upper = block_id.upper()
    logger.debug(f"[SOURCE] Searching Evidence Manual for: {block_id} (total blocks: {len(blocks)})")
    
    for block in blocks:
        if block.get("block_id", "").upper() == block_id_upper:
            logger.info(f"[SOURCE] Found Evidence block: {block_id} → '{block.get('title', '')[:50]}...'")
            return SourceResponse(
                source_type=SourceType.EVIDENCE,
                doc_id=doc.get("doc_id", ""),
                title=block.get("title", ""),
                section_id=block.get("block_id", ""),
                content=block.get("text", ""),
                legal_references=block.get("legal_references", []),
                metadata={
                    "evidence_category": block.get("evidence_category"),
                    "evidence_type": block.get("evidence_type"),
                    "failure_impact": block.get("failure_impact"),
                    "chain_of_custody": block.get("chain_of_custody"),
                }
            )
    
    logger.warning(f"[SOURCE] Evidence block not found: {block_id}")
    return None


def _fetch_compensation_block(doc: dict, block_id: str) -> Optional[SourceResponse]:
    """Fetch a block from Compensation Scheme."""
    blocks = doc.get("blocks", [])
    block_id_upper = block_id.upper()
    logger.debug(f"[SOURCE] Searching Compensation Scheme for: {block_id} (total blocks: {len(blocks)})")
    
    for block in blocks:
        if block.get("block_id", "").upper() == block_id_upper:
            logger.info(f"[SOURCE] Found Compensation block: {block_id} → '{block.get('title', '')[:50]}...'")
            return SourceResponse(
                source_type=SourceType.COMPENSATION,
                doc_id=doc.get("doc_id", ""),
                title=block.get("title", ""),
                section_id=block.get("block_id", ""),
                content=block.get("text", ""),
                legal_references=block.get("legal_references", []),
                metadata={
                    "compensation_type": block.get("compensation_type"),
                    "eligibility": block.get("eligibility"),
                    "amount_info": block.get("amount_info"),
                    "conviction_not_required": block.get("conviction_not_required"),
                }
            )
    
    logger.warning(f"[SOURCE] Compensation block not found: {block_id}")
    return None


# Document file mappings
DOCUMENT_FILES = {
    SourceType.GENERAL_SOP: "GENERAL_SOP_BPRD.json",
    SourceType.SOP: "SOP_RAPE_MHA.json",
    SourceType.BNSS: "BNSS_2023.json",
    SourceType.BNS: "BNS_2023.json",
    SourceType.BSA: "BSA_2023.json",
    SourceType.EVIDENCE: "CRIME_SCENE_MANUAL.json",
    SourceType.COMPENSATION: "NALSA_COMPENSATION_2018.json",
}


def fetch_source_content(
    source_type: SourceType,
    source_id: str,
    highlight_snippet: Optional[str] = None,
) -> Optional[SourceResponse]:
    """
    Fetch verbatim source content with optional highlighting.
    
    Args:
        source_type: Type of source (general_sop, sop, bnss, bns, bsa, evidence, compensation)
        source_id: Source identifier (block_id or section number)
        highlight_snippet: Optional snippet to highlight (from citation's context_snippet)
        
    Returns:
        SourceResponse with verbatim content and highlights, or None if not found
    """
    logger.info(f"[SOURCE] Fetch request: type={source_type.value}, id='{source_id}', highlight={'yes' if highlight_snippet else 'no'}")
    
    # Load the appropriate document
    filename = DOCUMENT_FILES.get(source_type)
    if not filename:
        logger.error(f"[SOURCE] Unknown source type: {source_type}")
        return None
    
    doc = _load_document(filename)
    if not doc:
        logger.error(f"[SOURCE] Failed to load document for {source_type.value}")
        return None
    
    # Fetch based on source type
    result = None
    if source_type == SourceType.GENERAL_SOP:
        result = _fetch_sop_block(doc, source_id)
    
    elif source_type == SourceType.SOP:
        result = _fetch_sop_block(doc, source_id)
    
    elif source_type in (SourceType.BNSS, SourceType.BNS, SourceType.BSA):
        result = _fetch_legal_section(doc, source_id, source_type)
    
    elif source_type == SourceType.EVIDENCE:
        result = _fetch_evidence_block(doc, source_id)
    
    elif source_type == SourceType.COMPENSATION:
        result = _fetch_compensation_block(doc, source_id)
    
    if result:
        logger.info(f"[SOURCE] ✓ Fetch success: {source_type.value}/{source_id} → {len(result.content)} chars")
        
        # Compute highlights if snippet provided
        if highlight_snippet:
            highlights = _compute_highlights(result.content, highlight_snippet)
            result.highlights = highlights
            logger.info(f"[SOURCE] Computed {len(highlights)} highlight(s) for snippet")
    else:
        logger.warning(f"[SOURCE] ✗ Fetch failed: {source_type.value}/{source_id} not found")
    
    return result
