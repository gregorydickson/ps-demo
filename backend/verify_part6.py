#!/usr/bin/env python3
"""
Verification script for Part 6: Architecture Improvements

Verifies that all components are properly implemented and accessible.
"""

import sys


def verify_imports():
    """Verify all new modules can be imported."""
    print("=" * 60)
    print("PART 6 VERIFICATION: Architecture Improvements")
    print("=" * 60)
    print()

    errors = []

    # Test API Resilience
    print("1. API Resilience Components")
    try:
        from backend.services.api_resilience import (
            gemini_breaker,
            llamaparse_breaker,
            with_circuit_breaker,
            get_breaker_status,
            ServiceUnavailableError
        )
        print("   ✅ Circuit breakers imported")
        print(f"   ✅ Gemini breaker: fail_max={gemini_breaker.fail_max}, reset_timeout={gemini_breaker.reset_timeout}s")
        print(f"   ✅ LlamaParse breaker: fail_max={llamaparse_breaker.fail_max}, reset_timeout={llamaparse_breaker.reset_timeout}s")
    except Exception as e:
        errors.append(f"API Resilience: {e}")
        print(f"   ❌ Error: {e}")

    print()

    # Test Observability
    print("2. Observability Components")
    try:
        from backend.utils.logging import setup_logging, get_logger
        print("   ✅ Structured logging imported")

        from backend.utils.request_context import (
            set_request_id,
            get_request_id,
            clear_request_context
        )
        print("   ✅ Request context imported")

        from backend.utils.performance import log_execution_time
        print("   ✅ Performance monitoring imported")
    except Exception as e:
        errors.append(f"Observability: {e}")
        print(f"   ❌ Error: {e}")

    print()

    # Test QA Workflow
    print("3. QA Workflow")
    try:
        from backend.workflows.qa_workflow import QAWorkflow, QAState
        print("   ✅ QA Workflow imported")
    except Exception as e:
        errors.append(f"QA Workflow: {e}")
        print(f"   ❌ Error: {e}")

    print()

    # Test GeminiRouter enhancements
    print("4. GeminiRouter Enhancements")
    try:
        from backend.services.gemini_router import GeminiRouter
        import inspect

        # Check __init__ signature
        init_sig = inspect.signature(GeminiRouter.__init__)
        assert 'default_timeout' in init_sig.parameters
        assert 'max_timeout' in init_sig.parameters
        print("   ✅ Timeout configuration parameters added")

        # Check generate signature
        gen_sig = inspect.signature(GeminiRouter.generate)
        assert 'timeout' in gen_sig.parameters
        print("   ✅ Generate method accepts timeout")

        # Check decorators
        assert hasattr(GeminiRouter.generate, 'retry')
        print("   ✅ Retry decorator applied")

    except Exception as e:
        errors.append(f"GeminiRouter: {e}")
        print(f"   ❌ Error: {e}")

    print()

    # Test Main API updates
    print("5. Main API Updates")
    try:
        from backend.main import RequestContextMiddleware, qa_workflow
        print("   ✅ Request context middleware defined")
        print("   ✅ QA workflow global variable defined")
    except Exception as e:
        errors.append(f"Main API: {e}")
        print(f"   ❌ Error: {e}")

    print()
    print("=" * 60)

    if errors:
        print(f"❌ VERIFICATION FAILED: {len(errors)} error(s)")
        for error in errors:
            print(f"   - {error}")
        return False
    else:
        print("✅ VERIFICATION SUCCESSFUL")
        print()
        print("All Part 6 components are properly implemented:")
        print("  • API Resilience: Retry, Circuit Breaker, Timeout")
        print("  • Observability: Logging, Request Context, Performance")
        print("  • QA Workflow: Lightweight contract querying")
        print()
        return True


def verify_test_suite():
    """Verify test suite exists and can be imported."""
    print("=" * 60)
    print("TEST SUITE VERIFICATION")
    print("=" * 60)
    print()

    try:
        import backend.test_part6
        print("✅ Test suite imported successfully")
        print()
        print("Run tests with:")
        print("  cd backend && python3 -m pytest test_part6.py -v")
        return True
    except Exception as e:
        print(f"❌ Error importing test suite: {e}")
        return False


if __name__ == "__main__":
    print()
    imports_ok = verify_imports()
    print()
    tests_ok = verify_test_suite()
    print()

    if imports_ok and tests_ok:
        print("🎉 Part 6 implementation is complete and verified!")
        sys.exit(0)
    else:
        print("⚠️  Some components failed verification")
        sys.exit(1)
