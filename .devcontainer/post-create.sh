#!/usr/bin/env bash
set -e

# Create venv
python -m venv .venv
source .venv/bin/activate

# Install deps (from lock if present; else minimal set)
if [ -f requirements.txt ]; then
  pip install --upgrade pip
  pip install -r requirements.txt
else
  pip install --upgrade pip
  pip install pdfplumber python-docx PyYAML pandas pytest streamlit
fi

# Ensure data dirs exist
mkdir -p data/docs data/outputs

# Print helpful next steps
echo ""
echo "✅ Devcontainer ready."
echo "Next:"
echo "  1) python demo.py"
echo "  2) streamlit run dashboard.py  # (Codespaces will expose port 8501)"
