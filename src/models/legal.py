"""
Core legal document data models.

This module defines the hierarchical structure for legal documents:
- LegalDocument: Complete legal document (Act/Law)
- Chapter: Chapter within a document
- Section: Section within a chapter
- Subsection: Subsection/clause within a section
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SubsectionType(Enum):
    """Classification of subsection content types."""
    PUNISHMENT = "punishment"
    DEFINITION = "definition"
    EXPLANATION = "explanation"
    PROVISION = "provision"
    EXCEPTION = "exception"
    ILLUSTRATION = "illustration"
    GENERAL = "general"


@dataclass
class Subsection:
    """Represents a subsection/clause within a section."""
    subsection_no: str
    text: str
    type: SubsectionType = SubsectionType.GENERAL
    page: int = 0
    embedding: Optional[list[float]] = None
    
    def to_dict(self) -> dict:
        return {
            "subsection_no": self.subsection_no,
            "text": self.text,
            "type": self.type.value,
            "page": self.page
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Subsection":
        return cls(
            subsection_no=data["subsection_no"],
            text=data["text"],
            type=SubsectionType(data.get("type", "general")),
            page=data.get("page", 0)
        )


@dataclass
class Section:
    """Represents a section within a chapter."""
    section_no: str
    section_title: str
    subsections: list[Subsection] = field(default_factory=list)
    full_text: str = ""
    page_start: int = 0
    page_end: int = 0
    embedding: Optional[list[float]] = None
    
    def to_dict(self) -> dict:
        return {
            "section_no": self.section_no,
            "section_title": self.section_title,
            "subsections": [s.to_dict() for s in self.subsections],
            "full_text": self.full_text,
            "page_start": self.page_start,
            "page_end": self.page_end
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Section":
        return cls(
            section_no=data["section_no"],
            section_title=data["section_title"],
            subsections=[Subsection.from_dict(s) for s in data.get("subsections", [])],
            full_text=data.get("full_text", ""),
            page_start=data.get("page_start", 0),
            page_end=data.get("page_end", 0)
        )


@dataclass
class Chapter:
    """Represents a chapter within a document."""
    chapter_no: str
    chapter_title: str
    sections: list[Section] = field(default_factory=list)
    summary: str = ""
    page_start: int = 0
    page_end: int = 0
    embedding: Optional[list[float]] = None
    
    def to_dict(self) -> dict:
        return {
            "chapter_no": self.chapter_no,
            "chapter_title": self.chapter_title,
            "sections": [s.to_dict() for s in self.sections],
            "summary": self.summary,
            "page_start": self.page_start,
            "page_end": self.page_end
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Chapter":
        return cls(
            chapter_no=data["chapter_no"],
            chapter_title=data["chapter_title"],
            sections=[Section.from_dict(s) for s in data.get("sections", [])],
            summary=data.get("summary", ""),
            page_start=data.get("page_start", 0),
            page_end=data.get("page_end", 0)
        )


@dataclass
class LegalDocument:
    """Represents a complete legal document (Act/Law)."""
    doc_id: str
    title: str
    short_name: str
    chapters: list[Chapter] = field(default_factory=list)
    summary: str = ""
    version: str = "2023"
    effective_date: str = ""
    status: str = "active"
    total_pages: int = 0
    embedding: Optional[list[float]] = None
    
    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "short_name": self.short_name,
            "chapters": [c.to_dict() for c in self.chapters],
            "summary": self.summary,
            "version": self.version,
            "effective_date": self.effective_date,
            "status": self.status,
            "total_pages": self.total_pages
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "LegalDocument":
        return cls(
            doc_id=data["doc_id"],
            title=data["title"],
            short_name=data["short_name"],
            chapters=[Chapter.from_dict(c) for c in data.get("chapters", [])],
            summary=data.get("summary", ""),
            version=data.get("version", "2023"),
            effective_date=data.get("effective_date", ""),
            status=data.get("status", "active"),
            total_pages=data.get("total_pages", 0)
        )
