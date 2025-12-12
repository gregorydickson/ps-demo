"""
Section-aware chunking for legal contracts.

Preserves document structure by chunking on legal section boundaries
(Articles, Sections, Clauses) rather than arbitrary character positions.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LegalChunk:
    """A chunk of legal document with structural metadata."""
    text: str
    section_title: Optional[str] = None
    section_type: Optional[str] = None  # article, section, clause, paragraph
    hierarchy_level: int = 0  # 0=top, 1=article, 2=section, 3=clause
    chunk_index: int = 0
    parent_section: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "section_title": self.section_title,
            "section_type": self.section_type,
            "hierarchy_level": self.hierarchy_level,
            "chunk_index": self.chunk_index,
            "parent_section": self.parent_section,
        }


class LegalDocumentChunker:
    """
    Section-aware chunker for legal documents.

    Recognizes common legal document patterns:
    - Articles (ARTICLE I, Article 1, etc.)
    - Sections (Section 1.1, SECTION 2, §1, etc.)
    - Clauses (Clause 1, (a), (i), etc.)
    - Definitions, Recitals, Exhibits
    """

    # Regex patterns for legal document sections
    PATTERNS = {
        "article": re.compile(
            r'^(?:ARTICLE|Article)\s+(?:[IVXLC]+|\d+)[.\s:]*(.*)$',
            re.MULTILINE
        ),
        "section": re.compile(
            r'^(?:SECTION|Section|§)\s*[\d.]+[.\s:]*(.*)$',
            re.MULTILINE
        ),
        "clause": re.compile(
            r'^(?:Clause|CLAUSE)\s+[\d.]+[.\s:]*(.*)$',
            re.MULTILINE
        ),
        "numbered": re.compile(
            r'^(\d+(?:\.\d+)*)[.\s:]+(.*)$',
            re.MULTILINE
        ),
        "lettered": re.compile(
            r'^\s*\(([a-z]|[ivx]+)\)\s+(.*)$',
            re.MULTILINE | re.IGNORECASE
        ),
        "definitions": re.compile(
            r'^(?:DEFINITIONS|Definitions|RECITALS|Recitals|WHEREAS|WITNESSETH)',
            re.MULTILINE
        ),
        "exhibit": re.compile(
            r'^(?:EXHIBIT|Exhibit|SCHEDULE|Schedule|APPENDIX|Appendix)\s+[A-Z\d]+',
            re.MULTILINE
        ),
    }

    # Hierarchy levels for section types
    HIERARCHY = {
        "article": 1,
        "section": 2,
        "clause": 3,
        "numbered": 2,
        "lettered": 4,
        "definitions": 1,
        "exhibit": 1,
    }

    def __init__(
        self,
        max_chunk_size: int = 1500,
        min_chunk_size: int = 200,
        overlap_sentences: int = 1
    ):
        """
        Initialize the legal document chunker.

        Args:
            max_chunk_size: Maximum characters per chunk (sections larger than this are split)
            min_chunk_size: Minimum characters per chunk (small sections are merged)
            overlap_sentences: Number of sentences to overlap between split chunks
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_sentences = overlap_sentences

    def _detect_section_type(self, line: str) -> Optional[Tuple[str, str]]:
        """
        Detect if a line is a section header.

        Returns:
            Tuple of (section_type, section_title) or None
        """
        line = line.strip()

        for section_type, pattern in self.PATTERNS.items():
            match = pattern.match(line)
            if match:
                # Extract title from match groups if available
                title = match.group(1).strip() if match.lastindex else line
                return (section_type, title or line)

        return None

    def _split_into_sections(self, text: str) -> List[Dict[str, Any]]:
        """
        Split document into structural sections.

        Returns:
            List of section dictionaries with type, title, content, and level
        """
        lines = text.split('\n')
        sections = []
        current_section = {
            "type": "preamble",
            "title": "Preamble",
            "content": [],
            "level": 0,
            "parent": None
        }
        parent_stack = []  # Track hierarchy for parent references

        for line in lines:
            detection = self._detect_section_type(line)

            if detection:
                section_type, title = detection
                level = self.HIERARCHY.get(section_type, 2)

                # Save previous section if it has content
                if current_section["content"]:
                    current_section["content"] = '\n'.join(current_section["content"])
                    sections.append(current_section)

                # Update parent stack based on hierarchy
                while parent_stack and parent_stack[-1]["level"] >= level:
                    parent_stack.pop()

                parent = parent_stack[-1]["title"] if parent_stack else None

                # Start new section
                current_section = {
                    "type": section_type,
                    "title": f"{line.strip()}",
                    "content": [],
                    "level": level,
                    "parent": parent
                }

                # Add to parent stack for hierarchy tracking
                parent_stack.append({"title": current_section["title"], "level": level})
            else:
                current_section["content"].append(line)

        # Don't forget the last section
        if current_section["content"]:
            current_section["content"] = '\n'.join(current_section["content"])
            sections.append(current_section)

        return sections

    def _split_large_section(self, text: str, section_info: Dict[str, Any]) -> List[LegalChunk]:
        """
        Split a large section into smaller chunks while preserving context.

        Uses sentence boundaries and adds overlap for continuity.
        """
        chunks = []

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)

        current_chunk = []
        current_length = 0
        chunk_index = 0

        for i, sentence in enumerate(sentences):
            sentence_len = len(sentence)

            if current_length + sentence_len > self.max_chunk_size and current_chunk:
                # Create chunk from accumulated sentences
                chunk_text = ' '.join(current_chunk)
                chunks.append(LegalChunk(
                    text=chunk_text,
                    section_title=section_info["title"],
                    section_type=section_info["type"],
                    hierarchy_level=section_info["level"],
                    chunk_index=chunk_index,
                    parent_section=section_info["parent"]
                ))
                chunk_index += 1

                # Keep overlap sentences for context continuity
                overlap_start = max(0, len(current_chunk) - self.overlap_sentences)
                current_chunk = current_chunk[overlap_start:]
                current_length = sum(len(s) for s in current_chunk)

            current_chunk.append(sentence)
            current_length += sentence_len

        # Add remaining content
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(LegalChunk(
                text=chunk_text,
                section_title=section_info["title"],
                section_type=section_info["type"],
                hierarchy_level=section_info["level"],
                chunk_index=chunk_index,
                parent_section=section_info["parent"]
            ))

        return chunks

    def _merge_small_sections(
        self,
        sections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge consecutive small sections at the same hierarchy level.
        """
        if not sections:
            return sections

        merged = []
        buffer = None

        for section in sections:
            content_len = len(section.get("content", ""))

            if content_len < self.min_chunk_size:
                if buffer is None:
                    buffer = section.copy()
                elif buffer["level"] == section["level"]:
                    # Merge with buffer
                    buffer["content"] += f"\n\n{section['title']}\n{section['content']}"
                    buffer["title"] += f" + {section['title']}"
                else:
                    # Different level, flush buffer and start new
                    merged.append(buffer)
                    buffer = section.copy()
            else:
                # Flush buffer if exists
                if buffer:
                    merged.append(buffer)
                    buffer = None
                merged.append(section)

        # Don't forget remaining buffer
        if buffer:
            merged.append(buffer)

        return merged

    def chunk_document(self, text: str) -> List[LegalChunk]:
        """
        Chunk a legal document with section awareness.

        Args:
            text: Full document text

        Returns:
            List of LegalChunk objects with structural metadata
        """
        if not text or not text.strip():
            return []

        # Step 1: Split into structural sections
        sections = self._split_into_sections(text)
        logger.debug(f"Detected {len(sections)} sections")

        # Step 2: Merge small consecutive sections
        sections = self._merge_small_sections(sections)
        logger.debug(f"After merging: {len(sections)} sections")

        # Step 3: Process each section
        all_chunks = []
        global_index = 0

        for section in sections:
            content = section.get("content", "").strip()

            if not content:
                continue

            content_with_title = f"{section['title']}\n\n{content}"

            if len(content_with_title) <= self.max_chunk_size:
                # Section fits in one chunk
                all_chunks.append(LegalChunk(
                    text=content_with_title,
                    section_title=section["title"],
                    section_type=section["type"],
                    hierarchy_level=section["level"],
                    chunk_index=global_index,
                    parent_section=section["parent"]
                ))
                global_index += 1
            else:
                # Split large section
                sub_chunks = self._split_large_section(content_with_title, section)
                for chunk in sub_chunks:
                    chunk.chunk_index = global_index
                    all_chunks.append(chunk)
                    global_index += 1

        logger.info(
            f"Chunked document into {len(all_chunks)} chunks "
            f"(from {len(sections)} sections)"
        )

        return all_chunks

    def chunk_to_texts_and_metadata(
        self,
        text: str
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Convenience method returning separate lists for ChromaDB storage.

        Returns:
            Tuple of (texts, metadatas) ready for vector store
        """
        chunks = self.chunk_document(text)

        texts = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "section_title": chunk.section_title,
                "section_type": chunk.section_type,
                "hierarchy_level": chunk.hierarchy_level,
                "parent_section": chunk.parent_section,
            }
            for chunk in chunks
        ]

        return texts, metadatas


# Convenience function for quick usage
def chunk_legal_document(
    text: str,
    max_chunk_size: int = 1500,
    min_chunk_size: int = 200
) -> List[LegalChunk]:
    """
    Chunk a legal document with section awareness.

    Args:
        text: Full document text
        max_chunk_size: Maximum characters per chunk
        min_chunk_size: Minimum characters per chunk

    Returns:
        List of LegalChunk objects
    """
    chunker = LegalDocumentChunker(
        max_chunk_size=max_chunk_size,
        min_chunk_size=min_chunk_size
    )
    return chunker.chunk_document(text)
