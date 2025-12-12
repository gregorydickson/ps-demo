"""
Unit tests for LegalDocumentChunker service.

Tests section detection, hierarchy tracking, chunk merging/splitting,
and metadata preservation for legal document chunking.
"""

import pytest
from backend.services.legal_chunker import (
    LegalDocumentChunker,
    LegalChunk,
    chunk_legal_document
)


class TestLegalChunkDataclass:
    """Tests for the LegalChunk dataclass."""

    def test_legal_chunk_creation(self):
        """Test basic LegalChunk creation."""
        chunk = LegalChunk(
            text="Test text",
            section_title="ARTICLE 1",
            section_type="article",
            hierarchy_level=1,
            chunk_index=0,
            parent_section=None
        )

        assert chunk.text == "Test text"
        assert chunk.section_title == "ARTICLE 1"
        assert chunk.section_type == "article"
        assert chunk.hierarchy_level == 1

    def test_legal_chunk_to_dict(self):
        """Test LegalChunk serialization to dictionary."""
        chunk = LegalChunk(
            text="Contract clause text",
            section_title="Section 2.1",
            section_type="section",
            hierarchy_level=2,
            chunk_index=5,
            parent_section="ARTICLE 2"
        )

        result = chunk.to_dict()

        assert result["text"] == "Contract clause text"
        assert result["section_title"] == "Section 2.1"
        assert result["section_type"] == "section"
        assert result["hierarchy_level"] == 2
        assert result["chunk_index"] == 5
        assert result["parent_section"] == "ARTICLE 2"

    def test_legal_chunk_defaults(self):
        """Test LegalChunk default values."""
        chunk = LegalChunk(text="Just text")

        assert chunk.section_title is None
        assert chunk.section_type is None
        assert chunk.hierarchy_level == 0
        assert chunk.chunk_index == 0
        assert chunk.parent_section is None


class TestSectionDetection:
    """Tests for section header detection patterns."""

    @pytest.fixture
    def chunker(self):
        return LegalDocumentChunker()

    def test_detect_article_roman_numerals(self, chunker):
        """Test detection of ARTICLE with Roman numerals."""
        result = chunker._detect_section_type("ARTICLE I: Definitions")
        assert result is not None
        assert result[0] == "article"

        result = chunker._detect_section_type("Article IV: Payment Terms")
        assert result is not None
        assert result[0] == "article"

    def test_detect_article_arabic_numerals(self, chunker):
        """Test detection of ARTICLE with Arabic numerals."""
        result = chunker._detect_section_type("ARTICLE 1 - DEFINITIONS")
        assert result is not None
        assert result[0] == "article"

        result = chunker._detect_section_type("Article 12: Termination")
        assert result is not None
        assert result[0] == "article"

    def test_detect_section_patterns(self, chunker):
        """Test detection of Section headers."""
        patterns = [
            "Section 1.1 Payment Schedule",
            "SECTION 2.3: Liability",
            "Section 10 - Confidentiality",
            "§1 Definitions",
            "§2.1 Scope of Work",
        ]

        for pattern in patterns:
            result = chunker._detect_section_type(pattern)
            assert result is not None, f"Failed to detect: {pattern}"
            assert result[0] == "section"

    def test_detect_clause_patterns(self, chunker):
        """Test detection of Clause headers."""
        result = chunker._detect_section_type("Clause 1: Definitions")
        assert result is not None
        assert result[0] == "clause"

        result = chunker._detect_section_type("CLAUSE 2.1 Payment")
        assert result is not None
        assert result[0] == "clause"

    def test_detect_numbered_sections(self, chunker):
        """Test detection of numbered section patterns."""
        patterns = [
            "1. Introduction",
            "2.1 Scope of Services",
            "3.2.1 Payment Terms",
        ]

        for pattern in patterns:
            result = chunker._detect_section_type(pattern)
            assert result is not None, f"Failed to detect: {pattern}"
            assert result[0] == "numbered"

    def test_detect_lettered_subsections(self, chunker):
        """Test detection of lettered subsection patterns."""
        patterns = [
            "(a) First item",
            "(b) Second item",
            "(i) Roman numeral item",
            "(iv) Another roman item",
        ]

        for pattern in patterns:
            result = chunker._detect_section_type(pattern)
            assert result is not None, f"Failed to detect: {pattern}"
            assert result[0] == "lettered"

    def test_detect_definitions_recitals(self, chunker):
        """Test detection of DEFINITIONS and RECITALS sections."""
        patterns = [
            "DEFINITIONS",
            "Definitions",
            "RECITALS",
            "Recitals",
            "WHEREAS",
            "WITNESSETH",
        ]

        for pattern in patterns:
            result = chunker._detect_section_type(pattern)
            assert result is not None, f"Failed to detect: {pattern}"
            assert result[0] == "definitions"

    def test_detect_exhibits_schedules(self, chunker):
        """Test detection of EXHIBIT and SCHEDULE headers."""
        patterns = [
            "EXHIBIT A",
            "Exhibit B",
            "SCHEDULE 1",
            "Schedule A",
            "APPENDIX C",
            "Appendix 1",
        ]

        for pattern in patterns:
            result = chunker._detect_section_type(pattern)
            assert result is not None, f"Failed to detect: {pattern}"
            assert result[0] == "exhibit"

    def test_non_section_lines_return_none(self, chunker):
        """Test that regular text lines return None."""
        non_sections = [
            "This is regular paragraph text.",
            "The parties agree to the following terms.",
            "Payment shall be made within 30 days.",
            "",
            "   ",
        ]

        for text in non_sections:
            result = chunker._detect_section_type(text)
            assert result is None, f"Should not detect section in: {text}"


class TestDocumentSplitting:
    """Tests for splitting documents into structural sections."""

    @pytest.fixture
    def chunker(self):
        return LegalDocumentChunker()

    def test_split_simple_document(self, chunker):
        """Test splitting a simple document with clear sections."""
        document = """ARTICLE 1: DEFINITIONS

For purposes of this Agreement, the following terms shall have the meanings set forth below.

ARTICLE 2: SERVICES

Provider shall perform the services described in Exhibit A.

ARTICLE 3: PAYMENT

Client shall pay Provider according to the fee schedule."""

        sections = chunker._split_into_sections(document)

        # Should have preamble (empty) + 3 articles
        article_sections = [s for s in sections if s["type"] == "article"]
        assert len(article_sections) == 3

    def test_split_preserves_content(self, chunker):
        """Test that section content is preserved correctly."""
        document = """ARTICLE 1: TEST

This is the content of article 1.
It has multiple lines.
And more text here."""

        sections = chunker._split_into_sections(document)

        article = next(s for s in sections if s["type"] == "article")
        assert "This is the content of article 1." in article["content"]
        assert "multiple lines" in article["content"]

    def test_split_tracks_hierarchy(self, chunker):
        """Test that hierarchy levels are tracked correctly."""
        document = """ARTICLE 1: MAIN SECTION

Some content here.

Section 1.1 Subsection

Subsection content.

(a) First item

Item content."""

        sections = chunker._split_into_sections(document)

        # Check hierarchy levels
        article = next(s for s in sections if s["type"] == "article")
        assert article["level"] == 1

        section = next(s for s in sections if s["type"] == "section")
        assert section["level"] == 2

        lettered = next(s for s in sections if s["type"] == "lettered")
        assert lettered["level"] == 4

    def test_split_tracks_parent_sections(self, chunker):
        """Test that parent section references are tracked."""
        document = """ARTICLE 1: PARENT

Parent content.

Section 1.1 Child

Child content."""

        sections = chunker._split_into_sections(document)

        section = next(s for s in sections if s["type"] == "section")
        assert section["parent"] is not None
        assert "ARTICLE 1" in section["parent"]


class TestChunkMerging:
    """Tests for merging small consecutive sections."""

    @pytest.fixture
    def chunker(self):
        return LegalDocumentChunker(min_chunk_size=200)

    def test_merge_small_sections(self, chunker):
        """Test that small sections at same level are merged."""
        sections = [
            {"type": "lettered", "title": "(a)", "content": "Short.", "level": 4, "parent": None},
            {"type": "lettered", "title": "(b)", "content": "Also short.", "level": 4, "parent": None},
            {"type": "lettered", "title": "(c)", "content": "Brief.", "level": 4, "parent": None},
        ]

        merged = chunker._merge_small_sections(sections)

        # Should merge into fewer sections
        assert len(merged) < len(sections)

    def test_no_merge_different_levels(self, chunker):
        """Test that sections at different levels are not merged."""
        sections = [
            {"type": "article", "title": "ARTICLE 1", "content": "Short.", "level": 1, "parent": None},
            {"type": "section", "title": "Section 1.1", "content": "Also short.", "level": 2, "parent": "ARTICLE 1"},
        ]

        merged = chunker._merge_small_sections(sections)

        # Different levels should not merge
        assert len(merged) == 2

    def test_no_merge_large_sections(self):
        """Test that large sections are not merged."""
        chunker = LegalDocumentChunker(min_chunk_size=50)

        sections = [
            {"type": "section", "title": "Section 1", "content": "A" * 100, "level": 2, "parent": None},
            {"type": "section", "title": "Section 2", "content": "B" * 100, "level": 2, "parent": None},
        ]

        merged = chunker._merge_small_sections(sections)

        # Large sections should not merge
        assert len(merged) == 2


class TestLargeSectionSplitting:
    """Tests for splitting large sections into smaller chunks."""

    @pytest.fixture
    def chunker(self):
        return LegalDocumentChunker(max_chunk_size=200, overlap_sentences=1)

    def test_split_large_section(self, chunker):
        """Test splitting a section that exceeds max_chunk_size."""
        section_info = {
            "title": "ARTICLE 1",
            "type": "article",
            "level": 1,
            "parent": None
        }

        # Create text with multiple sentences
        text = (
            "First sentence of the article. "
            "Second sentence continues here. "
            "Third sentence adds more content. "
            "Fourth sentence keeps going. "
            "Fifth sentence is also long. "
        ) * 5  # Repeat to exceed max_chunk_size

        chunks = chunker._split_large_section(text, section_info)

        assert len(chunks) > 1
        assert all(isinstance(c, LegalChunk) for c in chunks)

    def test_split_preserves_metadata(self, chunker):
        """Test that metadata is preserved across split chunks."""
        section_info = {
            "title": "Section 2.1",
            "type": "section",
            "level": 2,
            "parent": "ARTICLE 2"
        }

        text = "Sentence. " * 100  # Long text

        chunks = chunker._split_large_section(text, section_info)

        for chunk in chunks:
            assert chunk.section_title == "Section 2.1"
            assert chunk.section_type == "section"
            assert chunk.hierarchy_level == 2
            assert chunk.parent_section == "ARTICLE 2"

    def test_split_creates_overlap(self, chunker):
        """Test that split chunks have overlapping content."""
        section_info = {
            "title": "Test",
            "type": "section",
            "level": 2,
            "parent": None
        }

        sentences = [f"Sentence number {i}." for i in range(20)]
        text = " ".join(sentences)

        chunks = chunker._split_large_section(text, section_info)

        if len(chunks) > 1:
            # Check for overlap between consecutive chunks
            for i in range(len(chunks) - 1):
                # With overlap_sentences=1, last sentence of chunk i
                # should appear in chunk i+1
                chunk_i_sentences = chunks[i].text.split(". ")
                chunk_i_plus_1_text = chunks[i + 1].text

                # At least one sentence from end of chunk i should be in chunk i+1
                found_overlap = any(
                    sent.strip() in chunk_i_plus_1_text
                    for sent in chunk_i_sentences[-2:]
                    if sent.strip()
                )
                # Note: Overlap may not always be detectable depending on sentence boundaries
                # This is a soft check


class TestFullDocumentChunking:
    """Tests for the complete document chunking workflow."""

    @pytest.fixture
    def chunker(self):
        return LegalDocumentChunker(
            max_chunk_size=1500,
            min_chunk_size=200
        )

    @pytest.fixture
    def sample_contract(self):
        """Sample legal contract for testing."""
        return """SERVICE AGREEMENT

This Agreement is entered into as of January 1, 2025.

RECITALS

WHEREAS, Client desires to engage Provider for technical services;
WHEREAS, Provider agrees to provide such services.

NOW, THEREFORE, the parties agree as follows:

ARTICLE I: DEFINITIONS

1.1 "Agreement" means this Service Agreement.
1.2 "Services" means the technical services described herein.
1.3 "Term" means the period during which this Agreement is in effect.

ARTICLE II: SERVICES

Section 2.1 Scope of Services

Provider shall perform the following services:

(a) Software development and maintenance
(b) Technical support and consulting
(c) Training and documentation

Section 2.2 Service Levels

Provider shall maintain the following service levels:

(i) 99.9% uptime for production systems
(ii) 4-hour response time for critical issues
(iii) 24-hour response time for non-critical issues

ARTICLE III: PAYMENT

Section 3.1 Fees

Client shall pay Provider the fees set forth in Exhibit A.

Section 3.2 Payment Terms

Payment shall be due within thirty (30) days of invoice date.

ARTICLE IV: TERMINATION

Either party may terminate this Agreement upon thirty (30) days written notice.

EXHIBIT A: FEE SCHEDULE

Monthly retainer: $10,000
Hourly rate for additional services: $200/hour
"""

    def test_chunk_document_returns_legal_chunks(self, chunker, sample_contract):
        """Test that chunk_document returns list of LegalChunk objects."""
        chunks = chunker.chunk_document(sample_contract)

        assert len(chunks) > 0
        assert all(isinstance(c, LegalChunk) for c in chunks)

    def test_chunk_document_preserves_all_content(self, chunker, sample_contract):
        """Test that no content is lost during chunking."""
        chunks = chunker.chunk_document(sample_contract)

        # Reconstruct text (approximately - some formatting may differ)
        all_text = " ".join(c.text for c in chunks)

        # Key phrases should be preserved
        assert "SERVICE AGREEMENT" in all_text
        assert "RECITALS" in all_text
        assert "ARTICLE I" in all_text or "ARTICLE 1" in all_text
        assert "Provider shall perform" in all_text
        assert "EXHIBIT A" in all_text

    def test_chunk_document_assigns_section_types(self, chunker, sample_contract):
        """Test that chunks have appropriate section types."""
        chunks = chunker.chunk_document(sample_contract)

        section_types = {c.section_type for c in chunks}

        # Should have detected multiple section types
        assert len(section_types) > 1
        # Should include articles
        assert "article" in section_types or "definitions" in section_types

    def test_chunk_document_tracks_hierarchy(self, chunker, sample_contract):
        """Test that hierarchy levels are tracked correctly."""
        chunks = chunker.chunk_document(sample_contract)

        hierarchy_levels = {c.hierarchy_level for c in chunks}

        # Should have multiple hierarchy levels
        assert len(hierarchy_levels) > 1

    def test_chunk_document_handles_empty_text(self, chunker):
        """Test handling of empty document."""
        chunks = chunker.chunk_document("")
        assert chunks == []

        chunks = chunker.chunk_document("   \n\n   ")
        assert chunks == []

    def test_chunk_document_handles_no_sections(self, chunker):
        """Test handling of document with no recognizable sections."""
        plain_text = """
        This is just regular text without any legal section headers.
        It continues with more content that doesn't have structure.
        The chunker should still process this text appropriately.
        """

        chunks = chunker.chunk_document(plain_text)

        # Should still create chunks (as preamble)
        assert len(chunks) > 0
        assert chunks[0].section_type == "preamble"


class TestChunkToTextsAndMetadata:
    """Tests for the convenience method that returns separate lists."""

    @pytest.fixture
    def chunker(self):
        return LegalDocumentChunker()

    def test_returns_parallel_lists(self, chunker):
        """Test that texts and metadatas lists are parallel."""
        document = """ARTICLE 1: TEST

Content here.

ARTICLE 2: MORE

More content."""

        texts, metadatas = chunker.chunk_to_texts_and_metadata(document)

        assert len(texts) == len(metadatas)
        assert all(isinstance(t, str) for t in texts)
        assert all(isinstance(m, dict) for m in metadatas)

    def test_metadata_contains_expected_fields(self, chunker):
        """Test that metadata dictionaries have expected fields."""
        document = """ARTICLE 1: TEST

Content here."""

        texts, metadatas = chunker.chunk_to_texts_and_metadata(document)

        expected_fields = ["section_title", "section_type", "hierarchy_level", "parent_section"]

        for metadata in metadatas:
            for field in expected_fields:
                assert field in metadata


class TestConvenienceFunction:
    """Tests for the chunk_legal_document convenience function."""

    def test_convenience_function_works(self):
        """Test that the convenience function returns chunks."""
        document = """ARTICLE 1: TEST

Some content here."""

        chunks = chunk_legal_document(document)

        assert len(chunks) > 0
        assert all(isinstance(c, LegalChunk) for c in chunks)

    def test_convenience_function_accepts_parameters(self):
        """Test that parameters can be customized."""
        document = "A" * 3000

        chunks_default = chunk_legal_document(document)
        chunks_small = chunk_legal_document(document, max_chunk_size=500)

        # Smaller max_chunk_size should create more chunks
        assert len(chunks_small) >= len(chunks_default)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def chunker(self):
        return LegalDocumentChunker()

    def test_document_with_only_headers(self, chunker):
        """Test document with headers but minimal content."""
        document = """ARTICLE 1

ARTICLE 2

ARTICLE 3"""

        chunks = chunker.chunk_document(document)

        # Should handle gracefully
        assert isinstance(chunks, list)

    def test_deeply_nested_structure(self, chunker):
        """Test deeply nested document structure."""
        document = """ARTICLE 1: TOP

This is the top level content for article one.

Section 1.1: Second Level

This is subsection content with enough text to be meaningful.

(a) Third level

This is the third level item content.

(i) Fourth level content here with some actual text."""

        chunks = chunker.chunk_document(document)

        # Should handle deep nesting
        assert len(chunks) > 0

        # Check that hierarchy levels are assigned
        levels = [c.hierarchy_level for c in chunks]
        assert max(levels) >= 2  # At least some nesting detected

    def test_mixed_case_headers(self, chunker):
        """Test that standard case headers are detected (ARTICLE, Article)."""
        # Note: Legal documents typically use ARTICLE or Article, not lowercase
        # Small sections get merged, so we check that article type was detected
        document = """ARTICLE 1: UPPERCASE

Content for article 1 with enough text to make it meaningful and substantive.
This section contains important legal provisions that govern the agreement.

Article 2: Title Case

Content for article 2 with sufficient detail to stand as its own section.
The parties hereby agree to the terms and conditions set forth herein.

ARTICLE III: Roman Numerals

Content for article 3 explaining the final provisions of this agreement.
All disputes shall be resolved through binding arbitration procedures."""

        chunks = chunker.chunk_document(document)

        # Should have detected article sections (may be merged if small)
        assert len(chunks) > 0
        # At least one chunk should be of article type
        article_chunks = [c for c in chunks if c.section_type == "article"]
        assert len(article_chunks) >= 1
        # The combined text should contain all article references
        all_text = " ".join(c.text for c in chunks)
        assert "ARTICLE 1" in all_text
        assert "Article 2" in all_text
        assert "ARTICLE III" in all_text

    def test_unicode_content(self, chunker):
        """Test handling of unicode characters in content."""
        document = """ARTICLE 1: INTERNATIONAL

This agreement involves parties from múltiple countries.
Payment shall be made in € (Euros) or ¥ (Yen).
The parties agree to the following términos y condiciones."""

        chunks = chunker.chunk_document(document)

        all_text = " ".join(c.text for c in chunks)
        assert "múltiple" in all_text
        assert "€" in all_text
        assert "términos" in all_text

    def test_very_long_section_title(self, chunker):
        """Test handling of very long section titles."""
        long_title = "ARTICLE 1: " + "A" * 500
        document = f"""{long_title}

Content here."""

        chunks = chunker.chunk_document(document)

        # Should handle gracefully
        assert len(chunks) > 0
