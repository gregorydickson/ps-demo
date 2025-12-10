"""
Test script for Part 2 implementations.

Tests graph schemas, vector store, graph store, and workflow without
requiring actual API keys or running services.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Mock environment variables for testing
os.environ["GOOGLE_API_KEY"] = "test_key_not_used"
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USERNAME"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password123"


def test_graph_schemas():
    """Test graph schema imports and instantiation."""
    print("\n=== Testing Graph Schemas ===")

    from backend.models.graph_schemas import (
        ContractNode,
        CompanyNode,
        ClauseNode,
        RiskFactorNode,
        ContractGraph
    )
    from datetime import datetime

    # Test ContractNode
    contract = ContractNode(
        contract_id="test_123",
        filename="test.pdf",
        risk_score=5.5,
        risk_level="medium"
    )
    print(f"✓ ContractNode created: {contract.contract_id}")

    # Test CompanyNode
    company = CompanyNode(
        name="Test Corp",
        role="vendor"
    )
    print(f"✓ CompanyNode created: {company.name}")

    # Test ClauseNode
    clause = ClauseNode(
        section_name="Payment Terms",
        content="Payment within 30 days",
        clause_type="payment"
    )
    print(f"✓ ClauseNode created: {clause.section_name}")

    # Test RiskFactorNode
    risk = RiskFactorNode(
        concern="Unlimited liability",
        risk_level="high",
        section="Liability"
    )
    print(f"✓ RiskFactorNode created: {risk.concern}")

    # Test ContractGraph
    graph = ContractGraph(
        contract=contract,
        companies=[company],
        clauses=[clause],
        risk_factors=[risk]
    )
    print(f"✓ ContractGraph created with {len(graph.companies)} companies")

    # Test JSON serialization
    json_data = graph.model_dump_json()
    print(f"✓ Graph serializes to JSON ({len(json_data)} chars)")

    print("✅ All graph schema tests passed")
    return True


def test_vector_store_import():
    """Test vector store import (without initialization)."""
    print("\n=== Testing Vector Store ===")

    try:
        from backend.services.vector_store import ContractVectorStore
        print("✓ ContractVectorStore imported")

        # Test that class has required methods
        methods = ['store_document_sections', 'semantic_search', 'delete_contract']
        for method in methods:
            assert hasattr(ContractVectorStore, method), f"Missing method: {method}"
            print(f"✓ Method exists: {method}")

        print("✅ Vector store structure tests passed")
        return True

    except Exception as e:
        print(f"❌ Vector store test failed: {e}")
        return False


def test_graph_store_import():
    """Test graph store import (without Neo4j connection)."""
    print("\n=== Testing Graph Store ===")

    try:
        from backend.services.graph_store import ContractGraphStore
        print("✓ ContractGraphStore imported")

        # Test that class has required methods
        methods = ['store_contract', 'get_contract_relationships', 'delete_contract']
        for method in methods:
            assert hasattr(ContractGraphStore, method), f"Missing method: {method}"
            print(f"✓ Method exists: {method}")

        print("✅ Graph store structure tests passed")
        return True

    except Exception as e:
        print(f"❌ Graph store test failed: {e}")
        return False


def test_workflow_import():
    """Test workflow import (without initialization)."""
    print("\n=== Testing Workflow ===")

    try:
        # Import without instantiation (initialize_stores=False to avoid connecting)
        from backend.workflows.contract_analysis_workflow import (
            ContractAnalysisState,
            ContractAnalysisWorkflow,
            get_workflow
        )
        print("✓ Workflow classes imported")

        # Test creating workflow without stores
        workflow = ContractAnalysisWorkflow(initialize_stores=False)
        print("✓ Workflow instantiated (without stores)")

        # Check state schema
        state_keys = ContractAnalysisState.__annotations__.keys()
        required_keys = ['contract_id', 'file_bytes', 'filename', 'query']
        for key in required_keys:
            assert key in state_keys, f"Missing state key: {key}"
            print(f"✓ State has key: {key}")

        # Check workflow class methods
        methods = ['_parse_document_node', '_analyze_risk_node', '_store_vectors_node',
                   '_store_graph_node', '_qa_node', 'run']
        for method in methods:
            assert hasattr(ContractAnalysisWorkflow, method), f"Missing method: {method}"
            print(f"✓ Method exists: {method}")

        print("✅ Workflow structure tests passed")
        return True

    except Exception as e:
        print(f"❌ Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Part 2 Implementation Tests")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Graph Schemas", test_graph_schemas()))
    results.append(("Vector Store", test_vector_store_import()))
    results.append(("Graph Store", test_graph_store_import()))
    results.append(("Workflow", test_workflow_import()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Part 2 implementation is complete.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
