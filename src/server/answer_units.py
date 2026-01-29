"""
Span-Based Attribution System for Legal RAG.

This module implements Option B from UPDATES.md - verbatim-safe citation mapping.

Core Principle:
> Only text that is directly grounded in source spans may be highlighted.
> Synthesized guidance may list supporting sources but must not highlight text.

Key Components:
1. SourceSpan - Exact character offsets into source documents
2. AnswerUnit - A sentence/bullet marked as "verbatim" or "derived"
3. Span Resolution - Deterministic matching of quotes to sources (no LLM)

The flow:
1. LLM generates answer units with kind=verbatim/derived
2. Verbatim units include a `quote` field (exact text from source)
3. Span resolver finds the quote in retrieved chunks and attaches offsets
4. Frontend can only highlight verbatim units with resolved spans
"""

import logging
import re
from typing import Literal, Optional
from dataclasses import dataclass, field
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class SourceSpan:
    """
    Exact location of quoted text within a source document.
    
    These offsets refer to the FULL document text, not the chunk.
    This enables precise highlighting in the frontend.
    """
    doc_id: str           # e.g., "GENERAL_SOP_BPRD", "BNSS_2023"
    section_id: str       # e.g., "GSOP_057", "183"
    start_char: int       # Absolute char offset (0-indexed)
    end_char: int         # Exclusive end offset
    quote: str            # Exact text slice (for verification)
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "doc_id": self.doc_id,
            "section_id": self.section_id,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "quote": self.quote
        }


@dataclass  
class AnswerUnit:
    """
    A single unit of the answer (sentence or bullet point).
    
    Each unit is classified as:
    - "verbatim": Directly supported by a specific passage (can be highlighted)
    - "derived": Guidance, summary, or best-practice (NO highlighting allowed)
    
    This classification is made by the LLM during answer generation.
    """
    id: str                                      # e.g., "S1", "S2"
    text: str                                    # The sentence text
    kind: Literal["verbatim", "derived"]         # CRITICAL: determines highlightability
    source_spans: list[SourceSpan] = field(default_factory=list)  # Resolved after generation
    quote: Optional[str] = None                  # LLM-provided quote (for verbatim units)
    supporting_sources: list[str] = field(default_factory=list)   # Source IDs (for derived units)
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "id": self.id,
            "text": self.text,
            "kind": self.kind,
            "source_spans": [s.to_dict() for s in self.source_spans],
            "quote": self.quote,
            "supporting_sources": self.supporting_sources
        }
    
    @property
    def is_clickable(self) -> bool:
        """Whether this unit can be clicked to view source (verbatim with resolved span)."""
        return self.kind == "verbatim" and len(self.source_spans) > 0


# ============================================================================
# CHUNK WITH OFFSETS (for retrieval layer integration)
# ============================================================================

@dataclass
class ChunkWithOffsets:
    """
    A retrieved chunk with character offset information.
    
    This is used during span resolution to find where quotes appear
    in the original document.
    """
    doc_id: str
    section_id: str
    text: str
    start_char: int      # Offset of this chunk within the full document
    end_char: int        # End offset within full document
    
    # Additional metadata (optional)
    title: Optional[str] = None
    metadata: dict = field(default_factory=dict)


# ============================================================================
# LLM PROMPT FOR ANSWER UNIT GENERATION
# ============================================================================

ANSWER_UNIT_SYSTEM_PROMPT = """You are a legal assistant specializing in Indian law.
Your task is to provide COMPREHENSIVE, HELPFUL answers using the provided legal materials.

ANSWER QUALITY REQUIREMENTS:
1. Give DETAILED, THOROUGH answers - not just brief summaries
2. Include STEP-BY-STEP GUIDANCE when relevant (what victim can do immediately)
3. Explain POLICE DUTIES (what police MUST do, with deadlines if available)
4. Include LEGAL RIGHTS and relevant section references
5. If materials don't cover the question well, provide general legal guidance

SENTENCE CLASSIFICATION (for citation accuracy):
After writing each sentence, classify it as:
- VERBATIM: You can quote EXACT TEXT from the materials (copy-paste, no changes)
- DERIVED: You synthesized guidance, summarized, or the exact text isn't available

CRITICAL RULES FOR VERBATIM:
- The "quote" field MUST be a DIRECT COPY from the legal materials (10-50 words)
- Do NOT paraphrase or modify the quote
- Do NOT invent quotes - if you can't find exact text, mark as DERIVED
- Most sentences will be DERIVED - only use VERBATIM when you have exact source text

CRITICAL RULES FOR SUPPORTING_SOURCES:
- Use ONLY the section IDs (e.g., "GSOP_004", "183", "Section 173 BNSS")
- Do NOT include full titles or descriptions
- Look for patterns like "GSOP_XXX", "Section XXX", "BNS XXX", "BNSS XXX"

OUTPUT FORMAT (strict JSON):
{
  "answer_units": [
    {
      "id": "S1",
      "text": "A detailed sentence with useful information for the victim.",
      "kind": "verbatim",
      "quote": "exact text copied from the legal materials word for word"
    },
    {
      "id": "S2", 
      "text": "Synthesized guidance or explanation sentence.",
      "kind": "derived",
      "supporting_sources": ["GSOP_004", "Section 173"]
    }
  ]
}

REMEMBER: The user may be distressed. Provide HELPFUL, ACTIONABLE guidance first."""


def get_answer_unit_prompt(context: str, question: str, tier_prompt: str = "") -> str:
    """
    Build the full prompt for answer unit generation.
    
    Args:
        context: Retrieved context text
        question: User's question
        tier_prompt: Additional tier-specific instructions
        
    Returns:
        Complete prompt for LLM
    """
    base_prompt = ANSWER_UNIT_SYSTEM_PROMPT
    
    if tier_prompt:
        base_prompt = f"{base_prompt}\n\nADDITIONAL CONTEXT:\n{tier_prompt}"
    
    return f"""{base_prompt}

LEGAL MATERIALS:
{context}

QUESTION: {question}

Generate your response as JSON with answer_units:"""


# ============================================================================
# SPAN RESOLUTION (Deterministic - No LLM)
# ============================================================================

def resolve_span(
    quote: str,
    chunks: list[ChunkWithOffsets],
    fuzzy_threshold: float = 0.85
) -> Optional[SourceSpan]:
    """
    Find the exact location of a quote within retrieved chunks.
    
    This is a DETERMINISTIC operation - no LLM involved.
    
    Args:
        quote: The exact text to find
        chunks: List of retrieved chunks with offset information
        fuzzy_threshold: Minimum similarity ratio for fuzzy matching
        
    Returns:
        SourceSpan if found, None otherwise
    """
    if not quote or not chunks:
        return None
    
    # Normalize quote for matching
    quote_normalized = _normalize_text(quote)
    
    for chunk in chunks:
        chunk_text = chunk.text
        chunk_normalized = _normalize_text(chunk_text)
        
        # Strategy 1: Exact match
        idx = chunk_text.find(quote)
        if idx != -1:
            logger.debug(f"[SPAN] Exact match found in {chunk.section_id}")
            return SourceSpan(
                doc_id=chunk.doc_id,
                section_id=chunk.section_id,
                start_char=chunk.start_char + idx,
                end_char=chunk.start_char + idx + len(quote),
                quote=quote
            )
        
        # Strategy 2: Normalized match (whitespace-insensitive)
        idx_norm = chunk_normalized.find(quote_normalized)
        if idx_norm != -1:
            # Find actual position in original text
            actual_idx = _find_actual_position(chunk_text, quote_normalized, idx_norm)
            if actual_idx is not None:
                logger.debug(f"[SPAN] Normalized match found in {chunk.section_id}")
                return SourceSpan(
                    doc_id=chunk.doc_id,
                    section_id=chunk.section_id,
                    start_char=chunk.start_char + actual_idx,
                    end_char=chunk.start_char + actual_idx + len(quote),
                    quote=quote
                )
        
        # Strategy 3: Fuzzy match (for minor variations)
        match_result = _fuzzy_find(quote, chunk_text, fuzzy_threshold)
        if match_result:
            start_idx, end_idx, matched_text = match_result
            logger.debug(f"[SPAN] Fuzzy match ({fuzzy_threshold:.0%}) found in {chunk.section_id}")
            return SourceSpan(
                doc_id=chunk.doc_id,
                section_id=chunk.section_id,
                start_char=chunk.start_char + start_idx,
                end_char=chunk.start_char + end_idx,
                quote=matched_text  # Use actual matched text
            )
    
    logger.warning(f"[SPAN] Quote not found: '{quote[:50]}...'")
    return None


def resolve_all_spans(
    answer_units: list[AnswerUnit],
    chunks: list[ChunkWithOffsets]
) -> list[AnswerUnit]:
    """
    Resolve spans for all verbatim answer units.
    
    Units that fail resolution are downgraded to "derived" with a warning.
    
    Args:
        answer_units: List of answer units from LLM
        chunks: Retrieved chunks with offset information
        
    Returns:
        Answer units with resolved spans (or downgraded to derived)
    """
    resolved_count = 0
    downgraded_count = 0
    
    for unit in answer_units:
        if unit.kind == "verbatim" and unit.quote:
            span = resolve_span(unit.quote, chunks)
            
            if span:
                unit.source_spans.append(span)
                resolved_count += 1
            else:
                # Downgrade to derived - can't verify the quote
                logger.warning(f"[SPAN] Downgrading {unit.id} to derived: quote not found")
                unit.kind = "derived"
                unit.supporting_sources = [c.section_id for c in chunks[:3]]  # Fallback sources
                downgraded_count += 1
    
    logger.info(f"[SPAN] Resolution complete: {resolved_count} resolved, {downgraded_count} downgraded")
    return answer_units


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _normalize_text(text: str) -> str:
    """Normalize text for matching (collapse whitespace, lowercase)."""
    # Collapse multiple spaces/newlines to single space
    normalized = re.sub(r'\s+', ' ', text)
    # Lowercase for case-insensitive matching
    normalized = normalized.lower().strip()
    return normalized


def _find_actual_position(original: str, normalized_target: str, norm_idx: int) -> Optional[int]:
    """
    Find the actual character position in original text given a position in normalized text.
    
    This handles whitespace differences between original and normalized.
    """
    # Build a mapping from normalized positions to original positions
    original_idx = 0
    normalized_idx = 0
    
    while original_idx < len(original) and normalized_idx < len(normalized_target):
        # Skip extra whitespace in original
        while original_idx < len(original) and original[original_idx].isspace():
            if normalized_idx < len(_normalize_text(original[:original_idx+1])):
                break
            original_idx += 1
        
        if normalized_idx == norm_idx:
            return original_idx
        
        original_idx += 1
        normalized_idx += 1
    
    return None


def _fuzzy_find(
    needle: str,
    haystack: str,
    threshold: float = 0.85
) -> Optional[tuple[int, int, str]]:
    """
    Find approximate match of needle in haystack.
    
    Returns (start_idx, end_idx, matched_text) or None.
    """
    needle_len = len(needle)
    
    if needle_len > len(haystack):
        return None
    
    # Sliding window search
    best_ratio = 0.0
    best_match = None
    
    # Allow some flexibility in window size (±20%)
    min_window = max(10, int(needle_len * 0.8))
    max_window = min(len(haystack), int(needle_len * 1.2))
    
    for window_size in range(min_window, max_window + 1):
        for i in range(len(haystack) - window_size + 1):
            window = haystack[i:i + window_size]
            ratio = SequenceMatcher(None, needle.lower(), window.lower()).ratio()
            
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = (i, i + window_size, window)
    
    if best_ratio >= threshold:
        return best_match
    
    return None


# ============================================================================
# SUPPORTING SOURCES CLEANUP
# ============================================================================

def _extract_section_id(source_str: str) -> str:
    """
    Extract clean section ID from a potentially messy source string.
    
    Examples:
    - "General SOP (BPR&D) - SOP ON RECEIPT OF COMPLAINT..." -> "GSOP_004" (if found)
    - "GSOP_004" -> "GSOP_004"
    - "Section 173 BNSS" -> "Section 173"
    - "BNS Section 351" -> "351"
    """
    # Pattern: GSOP_XXX
    gsop_match = re.search(r'GSOP_\d+', source_str)
    if gsop_match:
        return gsop_match.group(0)
    
    # Pattern: Section XXX (BNSS/BNS/BSA)
    section_match = re.search(r'[Ss]ection\s*(\d+)', source_str)
    if section_match:
        return section_match.group(1)
    
    # Pattern: BNSS XXX, BNS XXX, BSA XXX
    law_match = re.search(r'(BNSS|BNS|BSA)\s*[_-]?\s*(\d+)', source_str, re.IGNORECASE)
    if law_match:
        return law_match.group(2)
    
    # Pattern: just a number (section ID)
    num_match = re.search(r'^(\d+)$', source_str.strip())
    if num_match:
        return num_match.group(1)
    
    # If nothing matches and it's already short, keep it
    if len(source_str) < 30:
        return source_str
    
    # Truncate long strings
    return source_str[:25] + "..."


def _clean_supporting_sources(sources: list) -> list[str]:
    """
    Clean up supporting_sources list to contain only section IDs.
    
    The LLM sometimes returns full display strings instead of IDs.
    """
    if not sources:
        return []
    
    cleaned = []
    seen = set()
    
    for source in sources:
        if not isinstance(source, str):
            continue
        
        extracted = _extract_section_id(source)
        if extracted and extracted not in seen:
            cleaned.append(extracted)
            seen.add(extracted)
    
    return cleaned


# ============================================================================
# PARSE LLM RESPONSE
# ============================================================================

def _extract_json_from_response(response_text: str) -> str:
    """
    Extract JSON from LLM response, handling various formats.
    
    Handles:
    - Plain JSON
    - Markdown code blocks (```json ... ```)
    - JSON embedded in text
    - Truncated responses
    """
    text = response_text.strip()
    
    # Strategy 1: Check if it's already valid JSON
    if text.startswith('{'):
        return text
    
    # Strategy 2: Extract from markdown code block
    # Match ```json or ``` followed by JSON
    code_block_match = re.search(r'```(?:json)?\s*\n?(\{[\s\S]*?\})\s*\n?```', text)
    if code_block_match:
        return code_block_match.group(1)
    
    # Strategy 3: Find JSON object that starts with { and contains "answer_units"
    # This handles cases where code block closing is missing or malformed
    json_start = text.find('{"answer_units"')
    if json_start == -1:
        json_start = text.find('{\n  "answer_units"')
    if json_start == -1:
        json_start = text.find('{')
    
    if json_start != -1:
        # Find matching closing brace
        brace_count = 0
        json_end = -1
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text[json_start:], start=json_start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    break
        
        if json_end != -1:
            return text[json_start:json_end]
        else:
            # JSON might be truncated, try to find last complete unit
            logger.warning("[PARSE] JSON appears truncated, attempting recovery")
            # Find up to the last complete answer_unit
            partial = text[json_start:]
            # Try adding closing brackets
            for suffix in ['}]}', ']}', '}']:
                try:
                    import json
                    json.loads(partial + suffix)
                    return partial + suffix
                except:
                    continue
    
    # Strategy 4: Remove markdown code block markers more aggressively
    cleaned = text
    cleaned = re.sub(r'^```json?\s*\n?', '', cleaned)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    cleaned = re.sub(r'\n?```[\s\S]*$', '', cleaned)  # Remove ``` and anything after
    
    return cleaned.strip()


def parse_answer_units_response(response_text: str) -> list[AnswerUnit]:
    """
    Parse LLM response into AnswerUnit objects.
    
    Handles JSON extraction and validation with robust error recovery.
    """
    import json
    
    # Extract JSON from response (handles markdown, truncation, etc.)
    cleaned = _extract_json_from_response(response_text)
    
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"[PARSE] Failed to parse LLM response as JSON: {e}")
        logger.debug(f"[PARSE] Cleaned text (first 200 chars): {cleaned[:200]}")
        # Fallback: return empty list to trigger legacy answer generation
        # Don't return raw JSON as a "sentence" - that's wrong
        return []
    
    # Extract answer_units
    units_data = data.get("answer_units", [])
    
    if not units_data:
        logger.warning("[PARSE] No answer_units in response")
        return []
    
    units = []
    for item in units_data:
        try:
            # Clean up supporting_sources
            raw_sources = item.get("supporting_sources", [])
            clean_sources = _clean_supporting_sources(raw_sources)
            
            unit = AnswerUnit(
                id=item.get("id", f"S{len(units)+1}"),
                text=item.get("text", ""),
                kind=item.get("kind", "derived"),
                quote=item.get("quote"),
                supporting_sources=clean_sources
            )
            
            # Validate kind
            if unit.kind not in ("verbatim", "derived"):
                logger.warning(f"[PARSE] Invalid kind '{unit.kind}', defaulting to derived")
                unit.kind = "derived"
            
            # Verbatim must have quote
            if unit.kind == "verbatim" and not unit.quote:
                logger.warning(f"[PARSE] Verbatim unit {unit.id} has no quote, downgrading to derived")
                unit.kind = "derived"
            
            units.append(unit)
            
        except Exception as e:
            logger.warning(f"[PARSE] Failed to parse unit: {e}")
            continue
    
    logger.info(f"[PARSE] Parsed {len(units)} answer units ({sum(1 for u in units if u.kind == 'verbatim')} verbatim)")
    return units


# ============================================================================
# CONVERT CHUNKS FROM RETRIEVAL RESULT
# ============================================================================

def chunks_from_retrieval_result(retrieval_result: dict, min_score: float = 0.0) -> list[ChunkWithOffsets]:
    """
    Convert retrieval results to ChunkWithOffsets for span resolution.
    
    Args:
        retrieval_result: The raw RAG result dictionary
        min_score: Minimum relevance score to include a chunk for span resolution
    """
    chunks = []
    
    # Helper to add chunk from search result
    def add_chunk(result: dict, source_prefix: str = ""):
        doc_id = result.get("metadata", {}).get("doc_id", "") or source_prefix
        section_id = result.get("metadata", {}).get("block_id", "") or result.get("citation", "")
        text = result.get("text", "")
        
        if not text:
            return
        
        # For now, we don't have actual document offsets
        # Use 0 as start_char - this means highlights will be relative to chunk
        # TODO: Update retrieval layer to track absolute offsets
        chunks.append(ChunkWithOffsets(
            doc_id=doc_id,
            section_id=section_id,
            text=text,
            start_char=0,  # Placeholder - needs retrieval layer update
            end_char=len(text),
            title=result.get("metadata", {}).get("title", ""),
            metadata=result.get("metadata", {})
        ))
    
    # Process all result types
    for key in ["sop_blocks", "general_sop_blocks", "evidence_blocks", 
                "compensation_blocks", "sections", "subsections"]:
        results = retrieval_result.get("retrieval", {}).get(key, [])
        for r in results:
            if r.get("score", 0.0) >= min_score:
                add_chunk(r, key.replace("_blocks", "").upper())
    
    logger.debug(f"[CHUNK] Converted {len(chunks)} chunks from retrieval result")
    return chunks
