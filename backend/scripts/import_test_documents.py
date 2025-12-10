#!/usr/bin/env python3
"""
Import test documents into ChromaDB and FalkorDB.

This script:
1. Parses PDF documents using LlamaParse
2. Analyzes them for risk factors using Gemini
3. Stores document chunks in ChromaDB (vector store)
4. Stores contract graph in FalkorDB (graph store)
5. Provides query functionality

Usage:
    # First, start FalkorDB:
    docker run -p 6381:6379 -p 3001:3000 -it --rm falkordb/falkordb

    # Set up environment variables in .env file or export them:
    export GOOGLE_API_KEY=your-gemini-api-key
    export LLAMA_CLOUD_API_KEY=your-llamaparse-key

    # Run the script:
    python scripts/import_test_documents.py --import
    python scripts/import_test_documents.py --query "What are the payment terms?"
    python scripts/import_test_documents.py --list
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional, Dict, Any, List

# Try to load from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / '.env')
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass


def check_environment():
    """Check that required environment variables are set."""
    missing = []
    if not os.getenv("GOOGLE_API_KEY"):
        missing.append("GOOGLE_API_KEY")
    if not os.getenv("LLAMA_CLOUD_API_KEY"):
        missing.append("LLAMA_CLOUD_API_KEY")

    if missing:
        print("ERROR: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nSet them via export or create a .env file:")
        print("  export GOOGLE_API_KEY=your-key")
        print("  export LLAMA_CLOUD_API_KEY=your-key")
        sys.exit(1)


# FalkorDB configuration (use port 6381 to avoid conflict with local Redis)
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6381"))

# Test documents directory
TEST_DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "test"

# ChromaDB directory
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db_test"


class SimplePDFParser:
    """Simple PDF parser using LlamaParse directly."""

    def __init__(self, api_key: str):
        # Import here to avoid module conflicts
        os.environ["LLAMA_CLOUD_API_KEY"] = api_key

    async def parse_document(self, file_path: Path) -> Dict[str, Any]:
        """Parse a PDF document using LlamaParse API directly."""
        import httpx

        api_key = os.getenv("LLAMA_CLOUD_API_KEY")

        # Upload file to LlamaParse
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Upload the file
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/pdf")}
                headers = {"Authorization": f"Bearer {api_key}"}

                response = await client.post(
                    "https://api.cloud.llamaindex.ai/api/parsing/upload",
                    files=files,
                    headers=headers,
                    data={"parsing_instruction": "Extract all text from this legal contract."}
                )

                if response.status_code != 200:
                    raise Exception(f"Upload failed: {response.text}")

                job_id = response.json()["id"]
                print(f"    Parse job started: {job_id}")

            # Poll for completion
            for _ in range(60):  # Max 5 minutes
                await asyncio.sleep(5)

                status_response = await client.get(
                    f"https://api.cloud.llamaindex.ai/api/parsing/job/{job_id}",
                    headers=headers
                )

                status = status_response.json()
                if status["status"] == "SUCCESS":
                    break
                elif status["status"] == "ERROR":
                    raise Exception(f"Parse failed: {status}")

                print(f"    Parsing... ({status['status']})")

            # Get results
            result_response = await client.get(
                f"https://api.cloud.llamaindex.ai/api/parsing/job/{job_id}/result/markdown",
                headers=headers
            )

            if result_response.status_code != 200:
                raise Exception(f"Failed to get results: {result_response.text}")

            parsed_text = result_response.json().get("markdown", "")

            return {
                "parsed_text": parsed_text,
                "filename": file_path.name,
                "page_count": parsed_text.count("\n---\n") + 1
            }


class SimpleVectorStore:
    """Simple ChromaDB vector store."""

    def __init__(self, persist_dir: str):
        import chromadb
        from chromadb.config import Settings

        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="test_contracts",
            metadata={"hnsw:space": "cosine"}
        )

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into chunks."""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap
            if start >= len(text) - overlap:
                break
        return chunks

    async def store_document(self, contract_id: str, text: str, metadata: Dict) -> int:
        """Store document chunks with embeddings."""
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

        chunks = self._chunk_text(text)
        if not chunks:
            return 0

        # Generate embeddings
        embeddings = []
        for i in range(0, len(chunks), 50):
            batch = chunks[i:i+50]
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=batch,
                task_type="retrieval_document"
            )
            embeddings.extend(result['embedding'])

        # Store in ChromaDB
        ids = [f"{contract_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"contract_id": contract_id, "chunk_index": i, **metadata} for i in range(len(chunks))]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )

        return len(chunks)

    async def search(self, query: str, contract_id: Optional[str] = None, n_results: int = 5) -> List[Dict]:
        """Semantic search."""
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

        # Generate query embedding
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=query,
            task_type="retrieval_query"
        )

        where_filter = {"contract_id": contract_id} if contract_id else None

        results = self.collection.query(
            query_embeddings=[result['embedding']],
            n_results=n_results,
            where=where_filter
        )

        formatted = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                formatted.append({
                    "id": results['ids'][0][i],
                    "text": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if 'distances' in results else None
                })

        return formatted

    def get_stats(self) -> Dict:
        """Get collection statistics."""
        return {
            "collection": "test_contracts",
            "total_chunks": self.collection.count()
        }


class SimpleGraphStore:
    """Simple FalkorDB graph store."""

    def __init__(self, host: str, port: int):
        from falkordb import FalkorDB

        self.db = FalkorDB(host=host, port=port)
        self.graph = self.db.select_graph("contracts")

        # Create indexes
        indexes = [
            "CREATE INDEX FOR (c:Contract) ON (c.contract_id)",
            "CREATE INDEX FOR (c:Contract) ON (c.risk_level)",
        ]
        for idx in indexes:
            try:
                self.graph.query(idx)
            except:
                pass

    async def store_contract(
        self,
        contract_id: str,
        filename: str,
        risk_score: float,
        risk_level: str,
        companies: List[Dict],
        risk_factors: List[Dict],
        key_terms: Dict
    ):
        """Store contract in graph database."""

        # Create contract node
        self.graph.query(
            """
            MERGE (c:Contract {contract_id: $contract_id})
            SET c.filename = $filename,
                c.upload_date = $upload_date,
                c.risk_score = $risk_score,
                c.risk_level = $risk_level,
                c.payment_amount = $payment_amount,
                c.liability_cap = $liability_cap
            """,
            {
                'contract_id': contract_id,
                'filename': filename,
                'upload_date': datetime.now(timezone.utc).isoformat(),
                'risk_score': risk_score,
                'risk_level': risk_level,
                'payment_amount': key_terms.get('payment_amount'),
                'liability_cap': key_terms.get('liability_cap')
            }
        )

        # Create company nodes
        for company in companies:
            self.graph.query(
                """
                MERGE (co:Company {name: $name})
                SET co.role = $role
                WITH co
                MATCH (c:Contract {contract_id: $contract_id})
                MERGE (co)-[r:PARTY_TO]->(c)
                """,
                {
                    'name': company['name'],
                    'role': company['role'],
                    'contract_id': contract_id
                }
            )

        # Create risk factor nodes
        for i, risk in enumerate(risk_factors):
            self.graph.query(
                """
                CREATE (r:RiskFactor {risk_id: $risk_id})
                SET r.concern = $concern,
                    r.risk_level = $risk_level,
                    r.section = $section,
                    r.recommendation = $recommendation
                WITH r
                MATCH (c:Contract {contract_id: $contract_id})
                MERGE (c)-[rel:HAS_RISK]->(r)
                """,
                {
                    'risk_id': f"{contract_id}_risk_{i}",
                    'concern': risk['concern'],
                    'risk_level': risk['risk_level'],
                    'section': risk.get('section'),
                    'recommendation': risk.get('recommendation'),
                    'contract_id': contract_id
                }
            )

    def list_contracts(self) -> List[Dict]:
        """List all contracts."""
        result = self.graph.query(
            "MATCH (c:Contract) RETURN c.contract_id, c.filename, c.risk_level, c.risk_score ORDER BY c.upload_date DESC"
        )
        return [
            {"contract_id": r[0], "filename": r[1], "risk_level": r[2], "risk_score": r[3]}
            for r in result.result_set
        ]

    def get_stats(self) -> Dict:
        """Get graph statistics."""
        contracts = self.graph.query("MATCH (c:Contract) RETURN count(c)").result_set[0][0]
        risks = self.graph.query("MATCH (r:RiskFactor) RETURN count(r)").result_set[0][0]
        return {"contracts": contracts, "risk_factors": risks}

    def close(self):
        """Close connection."""
        self.db.connection.close()


class DocumentImporter:
    """Import and manage test documents."""

    def __init__(self):
        print("Initializing services...")
        self.parser = SimplePDFParser(os.getenv("LLAMA_CLOUD_API_KEY"))
        self.vector_store = SimpleVectorStore(str(CHROMA_DIR))
        self.graph_store = SimpleGraphStore(FALKORDB_HOST, FALKORDB_PORT)

        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.genai = genai

        print(f"  Vector store: {CHROMA_DIR}")
        print(f"  Graph store: {FALKORDB_HOST}:{FALKORDB_PORT}")

    async def analyze_risks(self, text: str) -> Dict[str, Any]:
        """Analyze contract for risks using Gemini."""
        print("  Analyzing risks with Gemini...")

        prompt = f"""Analyze this legal contract and identify key risk factors.

CONTRACT TEXT (first 12000 chars):
{text[:12000]}

Provide your analysis in this EXACT format:
RISK_SCORE: [number 1-10]
RISK_LEVEL: [low/medium/high]

RISK_FACTORS:
1. CONCERN: [description]
   LEVEL: [low/medium/high]
   SECTION: [section name]
   RECOMMENDATION: [advice]

KEY_TERMS:
- Payment amount: [amount or not specified]
- Liability cap: [amount or unlimited]

COMPANIES:
- [Company name]: [role]
"""

        # Try multiple models in case of quota issues
        models_to_try = ['gemini-2.0-flash-lite', 'gemini-2.5-flash', 'gemini-2.0-flash']
        last_error = None

        for model_name in models_to_try:
            try:
                model = self.genai.GenerativeModel(model_name)
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt
                )
                print(f"    (used model: {model_name})")
                return self._parse_analysis(response.text)
            except Exception as e:
                last_error = e
                if "429" in str(e) or "quota" in str(e).lower():
                    print(f"    Quota exceeded for {model_name}, trying next...")
                    continue
                raise

        raise last_error

    def _parse_analysis(self, text: str) -> Dict:
        """Parse risk analysis response."""
        analysis = {
            "risk_score": 5.0,
            "risk_level": "medium",
            "risk_factors": [],
            "key_terms": {},
            "companies": []
        }

        lines = text.split('\n')
        current_risk = None

        for line in lines:
            line = line.strip()

            if line.startswith("RISK_SCORE:"):
                try:
                    score = float(line.split(":")[1].strip().split()[0])
                    analysis["risk_score"] = min(10, max(1, score))
                except:
                    pass

            elif line.startswith("RISK_LEVEL:"):
                level = line.split(":")[1].strip().lower().split()[0]
                if level in ["low", "medium", "high"]:
                    analysis["risk_level"] = level

            elif line.startswith("CONCERN:") or (line.startswith("1.") and "CONCERN:" in line):
                if current_risk:
                    analysis["risk_factors"].append(current_risk)
                concern = line.split("CONCERN:")[-1].strip() if "CONCERN:" in line else line[2:].strip()
                current_risk = {
                    "concern": concern,
                    "risk_level": "medium",
                    "section": None,
                    "recommendation": None
                }

            elif current_risk and line.startswith("LEVEL:"):
                level = line.split(":")[1].strip().lower().split()[0]
                if level in ["low", "medium", "high"]:
                    current_risk["risk_level"] = level

            elif current_risk and line.startswith("SECTION:"):
                current_risk["section"] = line.split(":", 1)[1].strip()

            elif current_risk and line.startswith("RECOMMENDATION:"):
                current_risk["recommendation"] = line.split(":", 1)[1].strip()

            elif line.startswith("- Payment amount:"):
                analysis["key_terms"]["payment_amount"] = line.split(":", 1)[1].strip()

            elif line.startswith("- Liability cap:"):
                analysis["key_terms"]["liability_cap"] = line.split(":", 1)[1].strip()

            elif line.startswith("- ") and ":" in line and "COMPANIES" not in line:
                try:
                    parts = line[2:].split(":")
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        role = parts[1].strip().lower()
                        if name and len(name) < 100:
                            analysis["companies"].append({"name": name, "role": role})
                except:
                    pass

        if current_risk:
            analysis["risk_factors"].append(current_risk)

        return analysis

    async def import_document(self, pdf_path: Path) -> str:
        """Import a single document."""
        contract_id = f"contract_{uuid4().hex[:8]}"

        print(f"\n{'='*60}")
        print(f"Importing: {pdf_path.name}")
        print(f"Contract ID: {contract_id}")
        print(f"{'='*60}")

        # Parse PDF
        print("  Parsing PDF...")
        parsed = await self.parser.parse_document(pdf_path)
        print(f"    Text length: {len(parsed['parsed_text'])} chars")

        # Analyze risks
        analysis = await self.analyze_risks(parsed["parsed_text"])
        print(f"    Risk score: {analysis['risk_score']}")
        print(f"    Risk level: {analysis['risk_level']}")
        print(f"    Risk factors: {len(analysis['risk_factors'])}")
        print(f"    Companies: {len(analysis['companies'])}")

        # Store in vector DB
        print("  Storing in ChromaDB...")
        chunks = await self.vector_store.store_document(
            contract_id=contract_id,
            text=parsed["parsed_text"],
            metadata={"filename": pdf_path.name}
        )
        print(f"    Stored {chunks} chunks")

        # Store in graph DB
        print("  Storing in FalkorDB...")
        await self.graph_store.store_contract(
            contract_id=contract_id,
            filename=pdf_path.name,
            risk_score=analysis["risk_score"],
            risk_level=analysis["risk_level"],
            companies=analysis["companies"],
            risk_factors=analysis["risk_factors"],
            key_terms=analysis["key_terms"]
        )

        print(f"\n✓ Import complete: {contract_id}")
        return contract_id

    async def import_all(self) -> List[str]:
        """Import all PDFs from test directory."""
        pdf_files = list(TEST_DOCS_DIR.glob("*.pdf"))

        if not pdf_files:
            print(f"No PDF files found in {TEST_DOCS_DIR}")
            return []

        print(f"Found {len(pdf_files)} PDF files")

        contract_ids = []
        for pdf_path in pdf_files:
            try:
                cid = await self.import_document(pdf_path)
                contract_ids.append(cid)
            except Exception as e:
                print(f"ERROR importing {pdf_path.name}: {e}")
                import traceback
                traceback.print_exc()

        self.show_stats()
        return contract_ids

    async def query(self, query: str, contract_id: Optional[str] = None):
        """Query documents."""
        print(f"\nQuery: {query}")
        if contract_id:
            print(f"Contract: {contract_id}")
        print("-" * 40)

        results = await self.vector_store.search(query, contract_id, n_results=5)

        if not results:
            print("No relevant sections found.")
            return

        context = "\n\n".join([f"[{i+1}]: {r['text']}" for i, r in enumerate(results)])

        prompt = f"""Based on the contract excerpts below, answer the question.

EXCERPTS:
{context}

QUESTION: {query}

Answer based only on the information above. If not found, say so."""

        # Try multiple models
        models_to_try = ['gemini-2.0-flash-lite', 'gemini-2.5-flash', 'gemini-2.0-flash']
        for model_name in models_to_try:
            try:
                model = self.genai.GenerativeModel(model_name)
                response = await asyncio.to_thread(model.generate_content, prompt)
                print(f"\nAnswer: {response.text}")
                print(f"\n(Model: {model_name})")
                print(f"Sources: {[r['metadata'].get('contract_id') for r in results]}")
                return
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    continue
                raise
        print("All models quota exceeded. Please wait and try again.")

    def list_contracts(self):
        """List all contracts."""
        print("\nContracts in FalkorDB:")
        print("-" * 40)

        contracts = self.graph_store.list_contracts()
        if not contracts:
            print("No contracts found.")
            return

        for c in contracts:
            print(f"  ID: {c['contract_id']}")
            print(f"    File: {c['filename']}")
            print(f"    Risk: {c['risk_level']} (score: {c['risk_score']})")
            print()

    def show_stats(self):
        """Show database statistics."""
        print(f"\n{'='*60}")
        print("Database Statistics")
        print(f"{'='*60}")

        vs = self.vector_store.get_stats()
        print(f"\nChromaDB: {vs['total_chunks']} chunks")

        gs = self.graph_store.get_stats()
        print(f"FalkorDB: {gs['contracts']} contracts, {gs['risk_factors']} risk factors")

    def close(self):
        self.graph_store.close()


async def main():
    parser = argparse.ArgumentParser(description="Import and query test documents")
    parser.add_argument("--import", "-i", action="store_true", dest="do_import", help="Import PDFs")
    parser.add_argument("--query", "-q", type=str, help="Query documents")
    parser.add_argument("--contract", "-c", type=str, help="Specific contract ID")
    parser.add_argument("--list", "-l", action="store_true", help="List contracts")
    parser.add_argument("--stats", "-s", action="store_true", help="Show stats")

    args = parser.parse_args()

    check_environment()

    importer = DocumentImporter()

    try:
        if args.do_import:
            await importer.import_all()
        elif args.query:
            await importer.query(args.query, args.contract)
        elif args.list:
            importer.list_contracts()
        elif args.stats:
            importer.show_stats()
        else:
            parser.print_help()
    finally:
        importer.close()


if __name__ == "__main__":
    asyncio.run(main())
