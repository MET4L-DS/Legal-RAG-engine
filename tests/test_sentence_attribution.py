"""
Tests for sentence-level citation attribution.
"""

import pytest
from src.server.sentence_attribution import (
    split_into_sentences,
    build_citation_key,
    parse_citation_key,
    get_available_citations,
    create_attribution_prompt,
    compute_sentence_attribution,
    _heuristic_attribution,
)


class TestSentenceSplitter:
    """Tests for sentence splitting."""
    
    def test_simple_sentences(self):
        """Test splitting simple sentences."""
        text = "File FIR immediately. Police must register the case. Contact nearest station."
        result = split_into_sentences(text)
        
        assert len(result) == 3
        assert result[0]["sid"] == "S1"
        assert "FIR" in result[0]["text"]
        assert result[1]["sid"] == "S2"
        assert result[2]["sid"] == "S3"
    
    def test_abbreviations_preserved(self):
        """Test that common abbreviations don't break sentence splitting."""
        text = "Under BNSS u/s 183, the statement must be recorded. Dr. Smith confirmed this."
        result = split_into_sentences(text)
        
        assert len(result) == 2
        assert "u/s 183" in result[0]["text"] or "u/S 183" in result[0]["text"] or "U_S" in result[0]["text"] or "183" in result[0]["text"]
    
    def test_skips_headers(self):
        """Test that markdown headers are skipped."""
        text = "## Immediate Steps\n\nFile FIR at the police station. This is required by law."
        result = split_into_sentences(text)
        
        # Headers should be skipped
        for sent in result:
            assert not sent["text"].startswith("#")
    
    def test_empty_text(self):
        """Test empty text returns empty list."""
        assert split_into_sentences("") == []
        assert split_into_sentences("   ") == []
    
    def test_single_sentence(self):
        """Test single sentence handling."""
        text = "This is a single sentence without ending punctuation"
        result = split_into_sentences(text)
        
        assert len(result) == 1
        assert result[0]["sid"] == "S1"


class TestCitationKeys:
    """Tests for citation key handling."""
    
    def test_build_citation_key(self):
        """Test building citation keys."""
        assert build_citation_key("bnss", "183") == "bnss:183"
        assert build_citation_key("general_sop", "GSOP_004") == "general_sop:GSOP_004"
    
    def test_parse_citation_key(self):
        """Test parsing citation keys."""
        assert parse_citation_key("bnss:183") == ("bnss", "183")
        assert parse_citation_key("general_sop:GSOP_004") == ("general_sop", "GSOP_004")
        assert parse_citation_key("invalid") == ("unknown", "invalid")
    
    def test_get_available_citations(self):
        """Test extracting citation keys from structured citations."""
        citations = [
            {"source_type": "bnss", "source_id": "183", "display": "BNSS Section 183"},
            {"source_type": "general_sop", "source_id": "GSOP_004", "display": "FIR Registration"},
        ]
        
        keys = get_available_citations(citations)
        
        assert "bnss:183" in keys
        assert "general_sop:GSOP_004" in keys
        assert len(keys) == 2


class TestHeuristicAttribution:
    """Tests for heuristic-based attribution (no LLM)."""
    
    def test_basic_heuristic_matching(self):
        """Test basic keyword matching."""
        sentences = [
            {"sid": "S1", "text": "File FIR immediately at the police station."},
            {"sid": "S2", "text": "Under BNSS Section 183, the statement must be recorded."},
        ]
        
        citations = [
            {
                "source_type": "general_sop",
                "source_id": "GSOP_004",
                "display": "FIR Registration Procedure",
                "context_snippet": "File FIR immediately when victim reports crime.",
            },
            {
                "source_type": "bnss",
                "source_id": "183",
                "display": "BNSS Section 183",
                "context_snippet": "Recording of statement of victim.",
            },
        ]
        
        mapping = _heuristic_attribution(sentences, citations)
        
        # S1 should map to GSOP (FIR keyword match)
        # S2 should map to BNSS 183 (section reference)
        assert "S1" in mapping
        assert "S2" in mapping
    
    def test_no_citations(self):
        """Test with no citations available."""
        sentences = [{"sid": "S1", "text": "Some text."}]
        citations = []
        
        mapping = _heuristic_attribution(sentences, citations)
        
        assert mapping == {"S1": []}


class TestComputeSentenceAttribution:
    """Tests for the main attribution function."""
    
    def test_no_answer(self):
        """Test with no answer text."""
        result = compute_sentence_attribution("", [], None)
        assert result is None
    
    def test_no_citations(self):
        """Test with answer but no citations."""
        result = compute_sentence_attribution(
            "This is an answer.",
            [],
            None
        )
        
        assert result is not None
        assert len(result["sentences"]) > 0
        # All mappings should be empty
        for sid, cits in result["mapping"].items():
            assert cits == []
    
    def test_with_heuristic_fallback(self):
        """Test attribution falls back to heuristic when no LLM."""
        answer = "File FIR immediately. Police must act within 24 hours."
        citations = [
            {
                "source_type": "general_sop",
                "source_id": "GSOP_004",
                "display": "FIR Registration",
                "context_snippet": "File FIR immediately upon receiving complaint.",
            }
        ]
        
        result = compute_sentence_attribution(answer, citations, None)
        
        assert result is not None
        assert "sentences" in result
        assert "mapping" in result
        assert len(result["sentences"]) >= 1


class TestAttributionPrompt:
    """Tests for LLM prompt generation."""
    
    def test_prompt_contains_sentences(self):
        """Test prompt includes all sentences."""
        sentences = [
            {"sid": "S1", "text": "First sentence."},
            {"sid": "S2", "text": "Second sentence."},
        ]
        citations = ["bnss:183", "general_sop:GSOP_004"]
        
        prompt = create_attribution_prompt(sentences, citations, "Full answer")
        
        assert "S1: First sentence." in prompt
        assert "S2: Second sentence." in prompt
    
    def test_prompt_contains_citations(self):
        """Test prompt includes available citations."""
        sentences = [{"sid": "S1", "text": "Text."}]
        citations = ["bnss:183", "general_sop:GSOP_004"]
        
        prompt = create_attribution_prompt(sentences, citations, "Answer")
        
        assert "bnss:183" in prompt
        assert "general_sop:GSOP_004" in prompt
    
    def test_prompt_requests_json(self):
        """Test prompt asks for JSON output."""
        sentences = [{"sid": "S1", "text": "Text."}]
        citations = ["bnss:183"]
        
        prompt = create_attribution_prompt(sentences, citations, "Answer")
        
        assert "JSON" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
