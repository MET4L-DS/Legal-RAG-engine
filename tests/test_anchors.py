"""
Tests for Timeline Anchor System.

These tests lock down the anchor definitions and ensure:
1. Each case type has its required anchors
2. Anchors are correctly marked (is_anchor=True, audience=victim/police)
3. Missing anchors trigger system_notice for Tier-1 crimes
4. No regressions in anchor completeness

Run with: pytest tests/test_anchors.py -v
"""

import pytest
from src.server.adapter import (
    TIMELINE_ANCHORS,
    TIER1_CASE_TYPES,
    extract_timeline_with_anchors,
    _normalize_case_type,
)
from src.server.schemas import TierType, TimelineItem


# ============================================================================
# ANCHOR DEFINITION TESTS (lock down expected anchors)
# ============================================================================

class TestAnchorDefinitions:
    """Test that anchor definitions are complete and correct."""
    
    def test_sexual_assault_has_required_anchors(self):
        """Sexual assault MUST have all 4 critical anchors."""
        required_stages = {
            "fir_registration",
            "medical_examination", 
            "statement_recording",
            "victim_protection",
        }
        
        anchors = TIMELINE_ANCHORS.get("sexual_assault", [])
        actual_stages = {a["stage"] for a in anchors}
        
        assert required_stages.issubset(actual_stages), (
            f"Missing anchors for sexual_assault: {required_stages - actual_stages}"
        )
    
    def test_rape_has_required_anchors(self):
        """Rape MUST have all 4 critical anchors."""
        required_stages = {
            "fir_registration",
            "medical_examination",
            "statement_recording", 
            "victim_protection",
        }
        
        anchors = TIMELINE_ANCHORS.get("rape", [])
        actual_stages = {a["stage"] for a in anchors}
        
        assert required_stages.issubset(actual_stages), (
            f"Missing anchors for rape: {required_stages - actual_stages}"
        )
    
    def test_pocso_has_required_anchors(self):
        """POCSO MUST have all 4 critical anchors (same as rape)."""
        required_stages = {
            "fir_registration",
            "medical_examination",
            "statement_recording",
            "victim_protection",
        }
        
        anchors = TIMELINE_ANCHORS.get("pocso", [])
        actual_stages = {a["stage"] for a in anchors}
        
        assert required_stages.issubset(actual_stages), (
            f"Missing anchors for pocso: {required_stages - actual_stages}"
        )
    
    def test_robbery_has_required_anchors(self):
        """Robbery MUST have FIR and investigation anchors."""
        required_stages = {
            "fir_registration",
            "investigation_commencement",
        }
        
        anchors = TIMELINE_ANCHORS.get("robbery", [])
        actual_stages = {a["stage"] for a in anchors}
        
        assert required_stages.issubset(actual_stages), (
            f"Missing anchors for robbery: {required_stages - actual_stages}"
        )
    
    def test_theft_has_required_anchors(self):
        """Theft MUST have FIR and investigation anchors."""
        required_stages = {
            "fir_registration",
            "investigation_commencement",
        }
        
        anchors = TIMELINE_ANCHORS.get("theft", [])
        actual_stages = {a["stage"] for a in anchors}
        
        assert required_stages.issubset(actual_stages), (
            f"Missing anchors for theft: {required_stages - actual_stages}"
        )
    
    def test_all_tier1_case_types_have_anchors(self):
        """All Tier-1 case types MUST have anchor definitions."""
        for case_type in TIER1_CASE_TYPES:
            normalized = _normalize_case_type(case_type)
            anchors = TIMELINE_ANCHORS.get(normalized, [])
            assert len(anchors) > 0, f"Tier-1 case type '{case_type}' has no anchors defined"
    
    def test_general_fallback_exists(self):
        """General fallback anchor MUST exist."""
        assert "general" in TIMELINE_ANCHORS
        assert len(TIMELINE_ANCHORS["general"]) > 0


# ============================================================================
# ANCHOR FIELD TESTS (verify is_anchor, audience, etc.)
# ============================================================================

class TestAnchorFields:
    """Test that anchors have correct field values."""
    
    def test_all_anchors_have_audience(self):
        """Every anchor MUST have an audience field."""
        for case_type, anchors in TIMELINE_ANCHORS.items():
            for anchor in anchors:
                assert "audience" in anchor, (
                    f"Anchor '{anchor['stage']}' in '{case_type}' missing audience"
                )
                assert anchor["audience"] in ("victim", "police", "court"), (
                    f"Invalid audience '{anchor['audience']}' for '{anchor['stage']}'"
                )
    
    def test_fir_registration_is_always_victim_audience(self):
        """FIR registration should always be audience=victim."""
        for case_type, anchors in TIMELINE_ANCHORS.items():
            for anchor in anchors:
                if anchor["stage"] == "fir_registration":
                    assert anchor["audience"] == "victim", (
                        f"FIR registration in '{case_type}' should be victim audience"
                    )
    
    def test_all_anchors_have_deadline(self):
        """Every anchor MUST have a deadline."""
        for case_type, anchors in TIMELINE_ANCHORS.items():
            for anchor in anchors:
                assert anchor.get("deadline"), (
                    f"Anchor '{anchor['stage']}' in '{case_type}' missing deadline"
                )


# ============================================================================
# EXTRACTION TESTS (verify extract_timeline_with_anchors behavior)
# ============================================================================

class TestAnchorExtraction:
    """Test the 2-pass anchor extraction system."""
    
    def test_rape_extraction_returns_all_anchors(self):
        """Extracting timeline for rape should return all 4 anchors."""
        mock_rag = {
            "case_type": "rape",
            "retrieval": {"sop_blocks": [], "general_sop_blocks": []},
        }
        
        timeline, notice = extract_timeline_with_anchors(
            mock_rag, "rape", TierType.TIER1
        )
        
        # Should have at least 4 anchors
        anchor_items = [t for t in timeline if t.is_anchor]
        assert len(anchor_items) >= 4, f"Expected 4+ anchors, got {len(anchor_items)}"
        
        # All anchors should be marked correctly
        anchor_stages = {t.stage for t in anchor_items}
        required = {"fir_registration", "medical_examination", "statement_recording", "victim_protection"}
        assert required.issubset(anchor_stages), f"Missing anchors: {required - anchor_stages}"
    
    def test_robbery_extraction_returns_anchors(self):
        """Extracting timeline for robbery should return 2 anchors."""
        mock_rag = {
            "case_type": "robbery",
            "retrieval": {"sop_blocks": [], "general_sop_blocks": []},
        }
        
        timeline, notice = extract_timeline_with_anchors(
            mock_rag, "robbery", TierType.TIER3
        )
        
        anchor_items = [t for t in timeline if t.is_anchor]
        assert len(anchor_items) >= 2, f"Expected 2+ anchors, got {len(anchor_items)}"
        
        anchor_stages = {t.stage for t in anchor_items}
        required = {"fir_registration", "investigation_commencement"}
        assert required.issubset(anchor_stages), f"Missing anchors: {required - anchor_stages}"
    
    def test_anchors_sorted_before_secondary(self):
        """Anchors should appear before secondary timelines."""
        mock_rag = {
            "case_type": "robbery",
            "retrieval": {
                "sop_blocks": [],
                "general_sop_blocks": [{
                    "text": "Property attachment under Section 107",
                    "metadata": {
                        "stage": "property_attachment",
                        "time_limit": "14 days",
                        "title": "Property Attachment"
                    }
                }]
            },
        }
        
        timeline, _ = extract_timeline_with_anchors(
            mock_rag, "robbery", TierType.TIER3
        )
        
        # Find first non-anchor
        first_non_anchor_idx = None
        for i, item in enumerate(timeline):
            if not item.is_anchor:
                first_non_anchor_idx = i
                break
        
        if first_non_anchor_idx is not None:
            # All items before first non-anchor should be anchors
            for i in range(first_non_anchor_idx):
                assert timeline[i].is_anchor, (
                    f"Non-anchor at position {i} before secondary starts at {first_non_anchor_idx}"
                )
    
    def test_victim_anchors_have_correct_audience(self):
        """Victim-critical anchors should have audience=victim."""
        mock_rag = {
            "case_type": "rape",
            "retrieval": {"sop_blocks": [], "general_sop_blocks": []},
        }
        
        timeline, _ = extract_timeline_with_anchors(
            mock_rag, "rape", TierType.TIER1
        )
        
        # FIR and medical exam should be victim audience
        for item in timeline:
            if item.stage in ("fir_registration", "medical_examination"):
                assert item.audience == "victim", (
                    f"{item.stage} should have audience=victim"
                )


# ============================================================================
# SYSTEM NOTICE TESTS (verify failure detection)
# ============================================================================

class TestAnchorFailures:
    """Test system notice generation for anchor failures."""
    
    def test_no_notice_when_anchors_present(self):
        """No system notice when all anchors resolved."""
        mock_rag = {
            "case_type": "robbery",
            "retrieval": {
                "sop_blocks": [],
                "general_sop_blocks": [{
                    "text": "FIR registration immediately",
                    "metadata": {"stage": "fir_registration"}
                }, {
                    "text": "Investigation commencement",
                    "metadata": {"stage": "investigation_commencement"}
                }]
            },
        }
        
        _, notice = extract_timeline_with_anchors(
            mock_rag, "robbery", TierType.TIER3
        )
        
        # Tier-3 doesn't require strict notice
        # But even for Tier-1, if blocks match, no notice
        assert notice is None or notice.type != "ANCHOR_MISSING"
    
    def test_unknown_case_type_uses_general_fallback(self):
        """Unknown case types should use general fallback anchors."""
        mock_rag = {
            "case_type": "unknown_crime_xyz",
            "retrieval": {"sop_blocks": [], "general_sop_blocks": []},
        }
        
        timeline, _ = extract_timeline_with_anchors(
            mock_rag, "unknown_crime_xyz", TierType.STANDARD
        )
        
        # Should still have at least FIR anchor from general
        anchor_stages = {t.stage for t in timeline if t.is_anchor}
        assert "fir_registration" in anchor_stages


# ============================================================================
# REGRESSION TESTS (prevent known issues from recurring)
# ============================================================================

class TestNoRegressions:
    """Tests to prevent known issues from recurring."""
    
    def test_robbery_timeline_not_dominated_by_property_attachment(self):
        """
        Regression test: Property attachment should NOT be first in robbery timeline.
        
        Previously, robbery queries would show "Section 107 attachment - 14 days"
        as the first/only timeline, which was misleading for victims.
        """
        mock_rag = {
            "case_type": "robbery",
            "retrieval": {
                "sop_blocks": [],
                "general_sop_blocks": [{
                    "text": "Property attachment procedure under Section 107",
                    "metadata": {
                        "stage": "property_attachment", 
                        "time_limit": "14 days",
                        "title": "SOP on Sec 107 Attachment"
                    }
                }]
            },
        }
        
        timeline, _ = extract_timeline_with_anchors(
            mock_rag, "robbery", TierType.TIER3
        )
        
        assert len(timeline) > 0, "Timeline should not be empty"
        
        # First item should be FIR, not property attachment
        assert timeline[0].stage == "fir_registration", (
            f"First timeline item should be FIR, not {timeline[0].stage}"
        )
        assert timeline[0].is_anchor, "First item should be an anchor"
        assert timeline[0].audience == "victim", "First item should be victim audience"
    
    def test_sexual_assault_has_all_critical_stages(self):
        """
        Regression test: Sexual assault must show all 4 critical stages,
        not just medical examination and rehabilitation.
        """
        mock_rag = {
            "case_type": "sexual_assault",
            "retrieval": {
                "sop_blocks": [{
                    "text": "Medical examination within 24 hours",
                    "metadata": {"stage": "medical_examination", "time_limit": "24 hours"}
                }, {
                    "text": "Rehabilitation support",
                    "metadata": {"stage": "rehabilitation"}
                }],
                "general_sop_blocks": []
            },
        }
        
        timeline, _ = extract_timeline_with_anchors(
            mock_rag, "sexual_assault", TierType.TIER1
        )
        
        anchor_stages = {t.stage for t in timeline if t.is_anchor}
        
        # Must have all 4 critical stages, not just what was retrieved
        required = {"fir_registration", "medical_examination", "statement_recording", "victim_protection"}
        assert required.issubset(anchor_stages), (
            f"Sexual assault missing critical stages: {required - anchor_stages}"
        )


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
