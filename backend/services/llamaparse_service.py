"""
LlamaParse Service - Legal document parsing using LlamaParse v0.6.88.

This service extracts structured data from legal PDFs including sections,
tables, metadata, and preserves legal document formatting.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from llama_parse import LlamaParse


logger = logging.getLogger(__name__)


class LegalDocumentParser:
    """
    Parses legal documents (PDFs) into structured markdown with metadata extraction.

    Uses LlamaParse configured specifically for legal document structures.
    """

    # Common legal contract types
    CONTRACT_TYPES = [
        "Non-Disclosure Agreement",
        "NDA",
        "Employment Agreement",
        "Service Agreement",
        "Lease Agreement",
        "Purchase Agreement",
        "License Agreement",
        "Partnership Agreement",
        "Master Service Agreement",
        "MSA",
        "Statement of Work",
        "SOW",
        "Terms of Service",
        "Privacy Policy",
    ]

    def __init__(self, api_key: str):
        """
        Initialize the legal document parser.

        Args:
            api_key: LlamaParse API key
        """
        self.parser = LlamaParse(
            api_key=api_key,
            result_type="markdown",  # Get markdown output
            parsing_instruction=self._get_legal_parsing_instruction(),
            num_workers=4,  # Parallel processing
            verbose=True,
            language="en",
        )
        logger.info("LegalDocumentParser initialized with LlamaParse v0.6.88")

    def _get_legal_parsing_instruction(self) -> str:
        """
        Get specialized parsing instructions for legal documents.

        Returns:
            Parsing instruction string optimized for legal documents
        """
        return """
        This is a legal contract or agreement document. Please:
        1. Preserve all section numbering (e.g., 1.1, 2.3.4)
        2. Maintain table structures with all data intact
        3. Identify and mark key sections like:
           - Definitions
           - Parties
           - Terms and Conditions
           - Payment Terms
           - Termination Clauses
           - Governing Law
           - Signatures
        4. Preserve dates, monetary amounts, and percentages exactly
        5. Keep paragraph formatting and indentation
        6. Extract all footnotes and references
        7. Maintain the hierarchical structure of the document
        """

    async def parse_document(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """
        Parse a legal document PDF into structured data.

        Args:
            file_bytes: PDF file as bytes
            filename: Original filename

        Returns:
            Dictionary containing:
                - parsed_text: Full markdown text
                - sections: List of extracted sections with numbering
                - tables: List of extracted tables
                - metadata: Document metadata (dates, parties, type, etc.)

        Raises:
            Exception: If parsing fails
        """
        try:
            logger.info(f"Starting parse of document: {filename}")

            # Parse document using LlamaParse
            # Note: LlamaParse v0.6.88 doesn't have async support in all methods,
            # so we handle this synchronously but can be called from async context
            documents = self.parser.load_data(file_bytes)

            if not documents:
                raise ValueError("No content extracted from document")

            # Combine all document pages into single text
            parsed_text = "\n\n".join(doc.text for doc in documents)

            logger.info(f"Parsed {len(documents)} pages, {len(parsed_text)} characters")

            # Extract structured elements
            sections = self._extract_sections(parsed_text)
            tables = self._extract_tables(parsed_text)
            metadata = self._extract_metadata(parsed_text, filename)

            return {
                "parsed_text": parsed_text,
                "sections": sections,
                "tables": tables,
                "metadata": metadata,
                "page_count": len(documents),
            }

        except Exception as e:
            logger.error(f"Failed to parse document {filename}: {e}")
            raise

    def _extract_sections(self, text: str) -> List[Dict[str, str]]:
        """
        Extract numbered legal sections from the document.

        Args:
            text: Parsed markdown text

        Returns:
            List of sections with number, title, and content
        """
        sections = []

        # Pattern for legal section numbering (e.g., "1.", "1.1", "1.1.1", etc.)
        # Matches lines starting with numbers and dots
        section_pattern = r'^((?:\d+\.)+\d*)\s+(.+?)$'

        lines = text.split('\n')
        current_section = None
        current_content = []

        for i, line in enumerate(lines):
            match = re.match(section_pattern, line.strip())

            if match:
                # Save previous section if exists
                if current_section:
                    sections.append({
                        "section_number": current_section["number"],
                        "title": current_section["title"],
                        "content": '\n'.join(current_content).strip(),
                        "level": current_section["level"],
                    })
                    current_content = []

                # Start new section
                section_number = match.group(1)
                section_title = match.group(2).strip()
                level = section_number.count('.')

                current_section = {
                    "number": section_number,
                    "title": section_title,
                    "level": level,
                }

            elif current_section:
                # Add line to current section content
                if line.strip():
                    current_content.append(line)

        # Add final section
        if current_section:
            sections.append({
                "section_number": current_section["number"],
                "title": current_section["title"],
                "content": '\n'.join(current_content).strip(),
                "level": current_section["level"],
            })

        logger.debug(f"Extracted {len(sections)} numbered sections")
        return sections

    def _extract_tables(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract markdown tables from the document.

        Args:
            text: Parsed markdown text

        Returns:
            List of tables with headers, rows, and metadata
        """
        tables = []

        # Split text into lines
        lines = text.split('\n')

        i = 0
        table_number = 1

        while i < len(lines):
            line = lines[i].strip()

            # Check if line looks like a table header (contains pipes |)
            if '|' in line and line.startswith('|'):
                # Found potential table
                table_lines = [line]
                i += 1

                # Collect table lines
                while i < len(lines):
                    next_line = lines[i].strip()
                    if '|' in next_line and next_line.startswith('|'):
                        table_lines.append(next_line)
                        i += 1
                    else:
                        break

                if len(table_lines) >= 2:  # At least header and separator
                    # Parse table
                    table_data = self._parse_markdown_table(table_lines)
                    if table_data:
                        tables.append({
                            "table_number": table_number,
                            "headers": table_data["headers"],
                            "rows": table_data["rows"],
                            "markdown": '\n'.join(table_lines),
                            "caption": None,  # Could be enhanced to detect captions
                        })
                        table_number += 1

            i += 1

        logger.debug(f"Extracted {len(tables)} tables")
        return tables

    def _parse_markdown_table(self, table_lines: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parse markdown table lines into headers and rows.

        Args:
            table_lines: Lines containing the markdown table

        Returns:
            Dictionary with headers and rows, or None if invalid
        """
        if len(table_lines) < 2:
            return None

        try:
            # Parse headers (first line)
            header_line = table_lines[0].strip('|').strip()
            headers = [h.strip() for h in header_line.split('|')]

            # Skip separator line (second line)
            # Parse data rows (remaining lines)
            rows = []
            for line in table_lines[2:]:
                row_line = line.strip('|').strip()
                if row_line:
                    cells = [c.strip() for c in row_line.split('|')]
                    rows.append(cells)

            return {
                "headers": headers,
                "rows": rows,
            }

        except Exception as e:
            logger.warning(f"Failed to parse markdown table: {e}")
            return None

    def _extract_metadata(self, text: str, filename: str) -> Dict[str, Any]:
        """
        Extract metadata from the legal document.

        Args:
            text: Parsed markdown text
            filename: Original filename

        Returns:
            Dictionary with contract metadata
        """
        metadata = {
            "filename": filename,
            "extracted_at": datetime.utcnow().isoformat(),
            "contract_type": None,
            "parties": [],
            "dates": [],
            "jurisdiction": None,
        }

        # Detect contract type
        text_upper = text.upper()
        for contract_type in self.CONTRACT_TYPES:
            if contract_type.upper() in text_upper[:1000]:  # Check first 1000 chars
                metadata["contract_type"] = contract_type
                break

        # Extract parties (common patterns in legal documents)
        # Look for "BETWEEN ... AND ..." pattern
        between_pattern = r'BETWEEN\s+(.+?)\s+(?:AND|&)\s+(.+?)(?:\n|,|\.)'
        between_matches = re.findall(between_pattern, text, re.IGNORECASE)
        for match in between_matches[:2]:  # Take first 2 matches
            metadata["parties"].extend([m.strip() for m in match])

        # Look for "Party A/B" or "Seller/Buyer" patterns
        party_patterns = [
            r'(?:Party A|First Party|Seller)(?:\s*[:\-]\s*|\s+)([A-Z][A-Za-z\s,\.]+?)(?:\n|,|\(|;)',
            r'(?:Party B|Second Party|Buyer)(?:\s*[:\-]\s*|\s+)([A-Z][A-Za-z\s,\.]+?)(?:\n|,|\(|;)',
        ]
        for pattern in party_patterns:
            matches = re.findall(pattern, text)
            for match in matches[:1]:  # Take first match per pattern
                party = match.strip()
                if len(party) > 3 and party not in metadata["parties"]:
                    metadata["parties"].append(party)

        # Extract dates (various formats)
        date_patterns = [
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',
            r'\b\d{4}-\d{2}-\d{2}\b',
            r'\b(?:Effective Date|Commencement Date|Execution Date)(?:\s*[:\-]\s*|\s+)([A-Za-z0-9\s,]+)',
        ]
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                date_str = match if isinstance(match, str) else match[0]
                date_str = date_str.strip()
                if date_str and date_str not in metadata["dates"]:
                    metadata["dates"].append(date_str)

        # Extract governing law/jurisdiction
        jurisdiction_pattern = r'(?:governed by|governing law|jurisdiction)(?:\s+of)?(?:\s*[:\-]\s*|\s+)(?:the\s+)?([A-Z][A-Za-z\s]+?)(?:\n|,|\.|\;)'
        jurisdiction_matches = re.findall(jurisdiction_pattern, text, re.IGNORECASE)
        if jurisdiction_matches:
            metadata["jurisdiction"] = jurisdiction_matches[0].strip()

        # Clean up parties list (remove duplicates, empty strings)
        metadata["parties"] = [
            p for p in list(set(metadata["parties"]))
            if p and len(p) > 3 and len(p) < 100
        ]

        # Limit dates to first 5
        metadata["dates"] = metadata["dates"][:5]

        logger.debug(
            f"Extracted metadata: type={metadata['contract_type']}, "
            f"parties={len(metadata['parties'])}, dates={len(metadata['dates'])}"
        )

        return metadata

    def extract_specific_clause(
        self,
        text: str,
        clause_type: str,
    ) -> Optional[str]:
        """
        Extract a specific type of clause from the document.

        Args:
            text: Parsed document text
            clause_type: Type of clause to extract (e.g., 'termination', 'payment')

        Returns:
            Extracted clause text or None if not found
        """
        # Define patterns for common legal clauses
        clause_patterns = {
            "termination": [
                r'(?:Termination|Cancellation)(?:\s+Clause)?(?:.*?)(?=\n\d+\.|$)',
            ],
            "payment": [
                r'(?:Payment Terms|Compensation|Fees)(?:.*?)(?=\n\d+\.|$)',
            ],
            "confidentiality": [
                r'(?:Confidentiality|Non-Disclosure)(?:.*?)(?=\n\d+\.|$)',
            ],
            "liability": [
                r'(?:Limitation of Liability|Indemnification)(?:.*?)(?=\n\d+\.|$)',
            ],
        }

        patterns = clause_patterns.get(clause_type.lower(), [])

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(0).strip()

        return None

    def validate_document_structure(self, parsed_data: Dict[str, Any]) -> Dict[str, bool]:
        """
        Validate that the document has expected legal structure.

        Args:
            parsed_data: Parsed document data

        Returns:
            Dictionary with validation results
        """
        validation = {
            "has_sections": len(parsed_data.get("sections", [])) > 0,
            "has_metadata": bool(parsed_data.get("metadata", {})),
            "has_parties": len(parsed_data.get("metadata", {}).get("parties", [])) > 0,
            "has_dates": len(parsed_data.get("metadata", {}).get("dates", [])) > 0,
            "has_text": len(parsed_data.get("parsed_text", "")) > 100,
        }

        validation["is_valid"] = all(validation.values())

        return validation
