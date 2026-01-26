"""
Sentence-Level Citation Attribution Module.

This module provides sentence-level mapping of answer text to source citations.
It enables the frontend to show inline citation dots and link sentences to sources.

Key Features:
- Deterministic sentence splitting (no LLM needed)
- LLM-based citation alignment (constrained task, low hallucination risk)
- Fallback to heuristic matching when LLM unavailable

The flow:
1. Split answer into sentences with IDs (S1, S2, S3...)
2. Ask LLM to map each sentence to citations (constrained mapping task)
3. Return mapping in a structured format

This is an ADDITIVE feature - the existing citation system remains unchanged.
"""

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def split_into_sentences(text: str) -> list[dict[str, str]]:
    """
    Split text into sentences with IDs.
    
    This is deterministic - no LLM needed.
    
    Args:
        text: The answer text to split
        
    Returns:
        List of {"sid": "S1", "text": "sentence text"}
    """
    if not text:
        return []
    
    # Handle markdown headers - keep them as single "sentences"
    # Split on sentence-ending punctuation, but be smart about abbreviations
    
    # First, protect common abbreviations
    protected = text
    abbreviations = [
        (r'e\.g\.', 'E_G_'),
        (r'i\.e\.', 'I_E_'),
        (r'etc\.', 'ETC_'),
        (r'vs\.', 'VS_'),
        (r'v\.', 'V_'),
        (r'u/s', 'U_S'),
        (r'u/S', 'U_S'),
        (r'U/s', 'U_S'),
        (r'sec\.', 'SEC_'),
        (r'Sec\.', 'SEC_'),
        (r'Sr\.', 'SR_'),
        (r'Jr\.', 'JR_'),
        (r'Dr\.', 'DR_'),
        (r'Mr\.', 'MR_'),
        (r'Mrs\.', 'MRS_'),
        (r'Ms\.', 'MS_'),
        (r'No\.', 'NO_'),
        (r'Rs\.', 'RS_'),
        (r'St\.', 'ST_'),
    ]
    
    for pattern, replacement in abbreviations:
        protected = re.sub(pattern, replacement, protected, flags=re.IGNORECASE)
    
    # Split on sentence-ending punctuation followed by space and capital or newline
    # Also split on bullet points (• or -)
    sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z•\-\d#])|(?<=\n)(?=##?\s)|(?<=\n)(?=•\s)|(?<=\n)(?=-\s)'
    
    raw_sentences = re.split(sentence_pattern, protected)
    
    # Restore abbreviations and clean up
    sentences = []
    for i, sent in enumerate(raw_sentences, 1):
        # Restore abbreviations
        restored = sent
        for pattern, replacement in abbreviations:
            original = pattern.replace(r'\.', '.').replace(r'/', '/')
            restored = restored.replace(replacement, original)
        
        # Clean whitespace
        restored = restored.strip()
        
        # Skip empty or very short sentences
        if len(restored) < 5:
            continue
        
        # Handle markdown headers - they're important context
        if restored.startswith('#'):
            # Skip section headers from sentence attribution
            # They're structural, not content that needs citation
            continue
        
        sentences.append({
            "sid": f"S{len(sentences) + 1}",
            "text": restored
        })
    
    logger.debug(f"[SENTENCE] Split answer into {len(sentences)} sentences")
    return sentences


def build_citation_key(source_type: str, source_id: str) -> str:
    """Build a citation key in format 'source_type:source_id'."""
    return f"{source_type}:{source_id}"


def parse_citation_key(key: str) -> tuple[str, str]:
    """Parse a citation key into (source_type, source_id)."""
    if ':' not in key:
        return ("unknown", key)
    parts = key.split(':', 1)
    return (parts[0], parts[1])


def get_available_citations(structured_citations: list[dict]) -> list[str]:
    """Get list of available citation keys from structured citations."""
    keys = []
    for cit in structured_citations:
        source_type = cit.get("source_type", "")
        source_id = cit.get("source_id", "")
        if source_type and source_id:
            keys.append(build_citation_key(source_type, source_id))
    return keys


def create_attribution_prompt(
    sentences: list[dict[str, str]],
    available_citations: list[str],
    answer_text: str
) -> str:
    """
    Create the prompt for LLM citation alignment.
    
    This is a CONSTRAINED task - the LLM can only map to provided citations.
    """
    sentences_text = "\n".join([f"{s['sid']}: {s['text']}" for s in sentences])
    citations_text = "\n".join([f"- {c}" for c in available_citations])
    
    prompt = f"""Your task is to map each sentence in the answer to the legal sources that support it.

AVAILABLE SOURCES (use ONLY these, do not invent):
{citations_text}

ANSWER SENTENCES:
{sentences_text}

INSTRUCTIONS:
1. For each sentence ID, list which sources from above support the information in that sentence
2. Use EXACT source keys from the list above (e.g., "general_sop:GSOP_004", "bnss:183")
3. A sentence may map to zero, one, or multiple sources
4. If a sentence is a general statement not requiring citation (like "Here are the steps"), map it to []
5. DO NOT invent sources - only use sources from the AVAILABLE SOURCES list

OUTPUT FORMAT (strict JSON):
{{
  "S1": ["source_type:source_id"],
  "S2": ["source_type:source_id", "another:source"],
  "S3": []
}}

Only output the JSON, nothing else."""

    return prompt


def compute_sentence_attribution(
    answer: str,
    structured_citations: list[dict],
    llm_client=None,
) -> Optional[dict]:
    """
    Compute sentence-level citation attribution.
    
    Args:
        answer: The LLM-generated answer text
        structured_citations: List of structured citation dicts
        llm_client: Optional LLM client for attribution (Google GenAI)
        
    Returns:
        Dict with "sentences" and "mapping", or None if attribution fails
    """
    if not answer:
        return None
    
    # Step A: Split into sentences (deterministic)
    sentences = split_into_sentences(answer)
    if not sentences:
        logger.warning("[SENTENCE] No sentences extracted from answer")
        return None
    
    # Get available citation keys
    available_citations = get_available_citations(structured_citations)
    if not available_citations:
        logger.warning("[SENTENCE] No citations available for mapping")
        return {
            "sentences": sentences,
            "mapping": {s["sid"]: [] for s in sentences}
        }
    
    # Step B: Get citation mapping from LLM (or fallback to heuristic)
    mapping = {}
    
    if llm_client:
        # Use LLM for attribution
        mapping = _llm_attribution(sentences, available_citations, answer, llm_client)
    
    if not mapping:
        # Fallback: heuristic matching
        mapping = _heuristic_attribution(sentences, structured_citations)
    
    logger.info(f"[SENTENCE] Attribution complete: {len(sentences)} sentences, {sum(len(v) for v in mapping.values())} mappings")
    
    return {
        "sentences": sentences,
        "mapping": mapping
    }


def _llm_attribution(
    sentences: list[dict],
    available_citations: list[str],
    answer: str,
    llm_client
) -> dict[str, list[str]]:
    """Use LLM for citation attribution."""
    import time
    
    prompt = create_attribution_prompt(sentences, available_citations, answer)
    
    # Use a fast model for this constrained task
    models_to_try = [
        "gemini-2.5-flash-lite",
        "gemma-3-12b-it",
    ]
    
    for model in models_to_try:
        try:
            logger.debug(f"[SENTENCE] Attempting attribution with model: {model}")
            from google.genai import types
            
            response = llm_client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,  # Deterministic
                    max_output_tokens=500,
                )
            )
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Clean up response (remove markdown code blocks if present)
            if response_text.startswith("```"):
                response_text = re.sub(r'^```json?\n?', '', response_text)
                response_text = re.sub(r'\n?```$', '', response_text)
            
            mapping = json.loads(response_text)
            
            # Validate mapping - ensure all keys are valid sentence IDs
            valid_sids = {s["sid"] for s in sentences}
            valid_citations = set(available_citations)
            
            cleaned_mapping = {}
            for sid, cits in mapping.items():
                if sid not in valid_sids:
                    continue
                # Filter to only valid citations
                valid_cits = [c for c in cits if c in valid_citations]
                cleaned_mapping[sid] = valid_cits
            
            # Ensure all sentences have an entry (even if empty)
            for s in sentences:
                if s["sid"] not in cleaned_mapping:
                    cleaned_mapping[s["sid"]] = []
            
            logger.info(f"[SENTENCE] LLM attribution success with {model}")
            return cleaned_mapping
            
        except json.JSONDecodeError as e:
            logger.warning(f"[SENTENCE] Failed to parse LLM response as JSON: {e}")
            continue
        except Exception as e:
            error_str = str(e)
            logger.warning(f"[SENTENCE] LLM attribution failed ({model}): {error_str[:100]}")
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                time.sleep(2)
            continue
    
    logger.warning("[SENTENCE] All LLM attribution attempts failed, using heuristic")
    return {}


def _heuristic_attribution(
    sentences: list[dict],
    structured_citations: list[dict]
) -> dict[str, list[str]]:
    """
    Fallback heuristic for citation attribution.
    
    Matches sentences to citations based on keyword overlap.
    Less accurate than LLM but works without API calls.
    """
    mapping = {s["sid"]: [] for s in sentences}
    
    for cit in structured_citations:
        source_type = cit.get("source_type", "")
        source_id = cit.get("source_id", "")
        display = cit.get("display", "").lower()
        snippet = (cit.get("context_snippet") or "").lower()
        
        if not source_type or not source_id:
            continue
        
        citation_key = build_citation_key(source_type, source_id)
        
        # Extract keywords from citation
        keywords = set()
        
        # From display
        words = re.findall(r'\b[a-z]{3,}\b', display)
        keywords.update(words)
        
        # From snippet
        words = re.findall(r'\b[a-z]{4,}\b', snippet)
        keywords.update(words)
        
        # Add source-specific keywords
        if source_type == "bnss":
            keywords.add("bnss")
            keywords.add("section")
            keywords.add(source_id.lower())
        elif source_type == "bns":
            keywords.add("bns")
            keywords.add("section")
            keywords.add(source_id.lower())
        elif source_type == "general_sop":
            keywords.add("sop")
            keywords.add("procedure")
            keywords.add("fir")
        elif source_type == "sop":
            keywords.add("sop")
            keywords.add("procedure")
        
        # Remove common words
        stop_words = {"the", "and", "for", "with", "that", "this", "from", "shall", "must", "may"}
        keywords -= stop_words
        
        # Match sentences
        for sent in sentences:
            sent_lower = sent["text"].lower()
            sent_words = set(re.findall(r'\b[a-z]{3,}\b', sent_lower))
            
            # Check overlap
            overlap = keywords & sent_words
            
            # Require significant overlap
            if len(overlap) >= 2 or (len(keywords) > 0 and len(overlap) / len(keywords) > 0.3):
                if citation_key not in mapping[sent["sid"]]:
                    mapping[sent["sid"]].append(citation_key)
    
    logger.debug(f"[SENTENCE] Heuristic attribution: {sum(len(v) for v in mapping.values())} mappings")
    return mapping
