#!/usr/bin/env bash
# End-to-end pilot pipeline runner:
# 1. Runs the 6-task hermetic smoke test (one per question type).
# 2. Runs the 20-task pilot generation and evaluation with configured model (or Oracle if no key).
set -e

echo "======================================================================"
echo "Step 1: Running smoke test (6 tasks, one per type, verified + oracle)"
echo "======================================================================"
python scripts/smoke_test.py

echo ""
echo "======================================================================"
echo "Step 2: Running 20-task pilot build and evaluation"
echo "======================================================================"
python -m sanket.cli pilot "$@"

echo ""
echo "======================================================================"
echo "Pilot pipeline completed successfully."
echo "======================================================================"
