"""
Search result models for retrieval pipeline.

This module defines data models for search and retrieval results.
"""

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """Represents a search result with score and metadata."""
    doc_id: str
    chapter_no: str
    section_no: str
    subsection_no: str
    text: str
    score: float
    level: str  # document, chapter, section, subsection
    metadata: dict = field(default_factory=dict)
    
    def get_citation(self) -> str:
        """Generate a citation string."""
        parts = [self.doc_id]
        if self.chapter_no:
            parts.append(f"Chapter {self.chapter_no}")
        if self.section_no:
            parts.append(f"Section {self.section_no}")
        if self.subsection_no:
            parts.append(f"({self.subsection_no})")
        return " - ".join(parts)
