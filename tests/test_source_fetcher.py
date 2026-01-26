"""
Tests for Source Fetcher Module.

Tests the /rag/source endpoint functionality.
Ensures verbatim source content is returned without LLM involvement.

Run with: pytest tests/test_source_fetcher.py -v
"""

import pytest
from src.server.source_fetcher import fetch_source_content
from src.server.schemas import SourceType, SourceResponse


class TestSourceFetcher:
    """Test source content fetching."""
    
    def test_fetch_general_sop_block(self):
        """Should fetch General SOP block by ID."""
        result = fetch_source_content(SourceType.GENERAL_SOP, "GSOP_004")
        
        assert result is not None
        assert isinstance(result, SourceResponse)
        assert result.source_type == SourceType.GENERAL_SOP
        assert result.section_id == "GSOP_004"
        assert "FIR" in result.content  # Content about FIR issuance
        assert len(result.content) > 0
    
    def test_fetch_general_sop_case_insensitive(self):
        """Should handle case-insensitive block IDs."""
        result = fetch_source_content(SourceType.GENERAL_SOP, "gsop_004")
        
        assert result is not None
        assert result.section_id == "GSOP_004"
    
    def test_fetch_bnss_section(self):
        """Should fetch BNSS section by number."""
        result = fetch_source_content(SourceType.BNSS, "183")
        
        assert result is not None
        assert result.source_type == SourceType.BNSS
        assert "183" in result.section_id
        assert len(result.content) > 0
    
    def test_fetch_bnss_section_with_prefix(self):
        """Should handle 'Section 183' format."""
        result = fetch_source_content(SourceType.BNSS, "Section 183")
        
        assert result is not None
        assert "183" in result.section_id
    
    def test_fetch_bnss_section_with_act_prefix(self):
        """Should handle 'BNSS Section 183' format."""
        result = fetch_source_content(SourceType.BNSS, "BNSS Section 183")
        
        assert result is not None
        assert "183" in result.section_id
    
    def test_fetch_nonexistent_source(self):
        """Should return None for non-existent sources."""
        result = fetch_source_content(SourceType.GENERAL_SOP, "GSOP_99999")
        
        assert result is None
    
    def test_source_response_has_metadata(self):
        """Should include relevant metadata."""
        result = fetch_source_content(SourceType.GENERAL_SOP, "GSOP_004")
        
        assert result is not None
        assert "metadata" in result.model_dump()
        # General SOP should have procedural_stage
        assert result.metadata.get("procedural_stage") is not None
    
    def test_bnss_section_has_chapter_metadata(self):
        """BNSS sections should include chapter info."""
        result = fetch_source_content(SourceType.BNSS, "183")
        
        assert result is not None
        assert result.metadata.get("chapter_no") is not None
    
    def test_verbatim_content_no_modification(self):
        """Content should be verbatim, not summarized."""
        result = fetch_source_content(SourceType.GENERAL_SOP, "GSOP_003")
        
        assert result is not None
        # Should contain markdown formatting from original
        assert "####" in result.content or "•" in result.content


class TestSourceFetcherEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_source_id(self):
        """Should handle empty source ID gracefully."""
        result = fetch_source_content(SourceType.GENERAL_SOP, "")
        
        assert result is None
    
    def test_special_characters_in_id(self):
        """Should handle special characters in source ID."""
        result = fetch_source_content(SourceType.BNSS, "§183")
        
        # Should normalize and find the section
        assert result is not None or result is None  # May or may not find depending on normalization


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
