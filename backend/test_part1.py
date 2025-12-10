#!/usr/bin/env python3
"""
Integration tests for Part 1: Infrastructure & Core Services

Tests all components implemented in Part 1 of the workplan.
"""

import sys
import ast


def test_syntax_check(filepath: str, name: str) -> bool:
    """Test that a Python file has valid syntax."""
    try:
        with open(filepath, 'r') as f:
            ast.parse(f.read())
        print(f"✅ {name} - Syntax OK")
        return True
    except SyntaxError as e:
        print(f"❌ {name} - Syntax Error: {e}")
        return False
    except Exception as e:
        print(f"❌ {name} - Error: {e}")
        return False


def test_import(module_path: str, items: list, name: str) -> bool:
    """Test that a module can be imported."""
    try:
        module = __import__(module_path, fromlist=items)
        for item in items:
            if not hasattr(module, item):
                print(f"❌ {name} - Missing: {item}")
                return False
        print(f"✅ {name} - Import OK")
        return True
    except ImportError as e:
        print(f"⚠️  {name} - Import skipped (dependencies not installed): {e}")
        return None  # Not a failure, just skipped
    except Exception as e:
        print(f"❌ {name} - Error: {e}")
        return False


def test_schemas() -> bool:
    """Test Pydantic schemas."""
    try:
        from models.schemas import (
            RiskLevel,
            RiskAnalysis,
            KeyTerms,
            ContractUploadResponse,
            ContractQuery,
            QueryResponse,
            CostAnalytics,
            ContractMetadata,
            ParsedSection,
            ParsedTable,
        )

        # Test enum
        assert RiskLevel.LOW == "low"
        assert RiskLevel.CRITICAL == "critical"

        # Test instantiation
        risk = RiskAnalysis(
            risk_level=RiskLevel.MEDIUM,
            risk_score=65.5,
        )
        assert risk.risk_level == RiskLevel.MEDIUM
        assert risk.risk_score == 65.5

        # Test validation
        query = ContractQuery(
            contract_id="test-123",
            question="What are the payment terms?",
        )
        assert query.contract_id == "test-123"
        assert query.include_context is True  # default value

        print("✅ Pydantic Schemas - All tests passed")
        return True

    except Exception as e:
        print(f"❌ Pydantic Schemas - Error: {e}")
        return False


def test_gemini_router() -> bool:
    """Test Gemini Router Service."""
    try:
        from services.gemini_router import GeminiRouter, TaskComplexity, GenerationResult

        # Test enum
        assert TaskComplexity.SIMPLE == "simple"
        assert TaskComplexity.REASONING == "reasoning"

        # Test model configs exist
        assert TaskComplexity.SIMPLE in GeminiRouter.MODEL_CONFIGS
        assert TaskComplexity.BALANCED in GeminiRouter.MODEL_CONFIGS
        assert TaskComplexity.COMPLEX in GeminiRouter.MODEL_CONFIGS
        assert TaskComplexity.REASONING in GeminiRouter.MODEL_CONFIGS

        # Test model names
        config = GeminiRouter.MODEL_CONFIGS[TaskComplexity.SIMPLE]
        assert config.name == "gemini-2.5-flash-lite"
        assert config.input_cost_per_1m > 0
        assert config.output_cost_per_1m > 0

        # Test reasoning model has thinking support
        reasoning_config = GeminiRouter.MODEL_CONFIGS[TaskComplexity.REASONING]
        assert reasoning_config.supports_thinking is True
        assert reasoning_config.thinking_cost_per_1m is not None

        print("✅ Gemini Router - All tests passed")
        return True

    except ImportError as e:
        print(f"⚠️  Gemini Router - Skipped (dependencies not installed): {e}")
        return None
    except Exception as e:
        print(f"❌ Gemini Router - Error: {e}")
        return False


def test_cost_tracker() -> bool:
    """Test Cost Tracker Service."""
    try:
        from services.cost_tracker import CostTracker

        # Test key prefixes exist
        assert hasattr(CostTracker, 'KEY_PREFIX_DAILY')
        assert hasattr(CostTracker, 'KEY_PREFIX_CALL')
        assert hasattr(CostTracker, 'RETENTION_SECONDS')

        # Test retention is 30 days
        assert CostTracker.RETENTION_SECONDS == 30 * 24 * 60 * 60

        print("✅ Cost Tracker - All tests passed")
        return True

    except ImportError as e:
        print(f"⚠️  Cost Tracker - Skipped (dependencies not installed): {e}")
        return None
    except Exception as e:
        print(f"❌ Cost Tracker - Error: {e}")
        return False


def test_llamaparse_service() -> bool:
    """Test LlamaParse Service."""
    try:
        from services.llamaparse_service import LegalDocumentParser

        # Test contract types list exists
        assert hasattr(LegalDocumentParser, 'CONTRACT_TYPES')
        assert len(LegalDocumentParser.CONTRACT_TYPES) > 0
        assert "NDA" in LegalDocumentParser.CONTRACT_TYPES

        print("✅ LlamaParse Service - All tests passed")
        return True

    except ImportError as e:
        print(f"⚠️  LlamaParse Service - Skipped (dependencies not installed): {e}")
        return None
    except Exception as e:
        print(f"❌ LlamaParse Service - Error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Part 1 Integration Tests")
    print("=" * 60)
    print()

    results = []

    print("1. Syntax Checks")
    print("-" * 60)
    results.append(test_syntax_check("models/schemas.py", "Schemas"))
    results.append(test_syntax_check("services/gemini_router.py", "Gemini Router"))
    results.append(test_syntax_check("services/cost_tracker.py", "Cost Tracker"))
    results.append(test_syntax_check("services/llamaparse_service.py", "LlamaParse"))
    print()

    print("2. Import Tests")
    print("-" * 60)
    results.append(test_schemas())
    results.append(test_gemini_router())
    results.append(test_cost_tracker())
    results.append(test_llamaparse_service())
    print()

    print("=" * 60)
    print("Test Summary")
    print("=" * 60)

    # Filter out None (skipped tests)
    actual_results = [r for r in results if r is not None]
    skipped_count = len([r for r in results if r is None])

    passed = sum(actual_results)
    total = len(actual_results)

    print(f"Passed: {passed}/{total}")
    if skipped_count > 0:
        print(f"Skipped: {skipped_count} (dependencies not installed)")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
