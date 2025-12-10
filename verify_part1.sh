#!/bin/bash

echo "================================================"
echo "Part 1 Implementation Verification"
echo "================================================"
echo ""

echo "Checking file structure..."
echo ""

files=(
    "backend/models/schemas.py"
    "backend/services/gemini_router.py"
    "backend/services/cost_tracker.py"
    "backend/services/llamaparse_service.py"
    "backend/test_part1.py"
    "backend/README_PART1.md"
    "docs/PART1-IMPLEMENTATION-SUMMARY.md"
)

all_exist=true
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file (MISSING)"
        all_exist=false
    fi
done

echo ""
if [ "$all_exist" = true ]; then
    echo "✅ All required files present"
else
    echo "❌ Some files are missing"
    exit 1
fi

echo ""
echo "Running integration tests..."
echo ""

cd backend
python3 test_part1.py

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "================================================"
    echo "✅ Part 1 Implementation Verified Successfully!"
    echo "================================================"
else
    echo "================================================"
    echo "❌ Verification failed"
    echo "================================================"
fi

exit $exit_code
