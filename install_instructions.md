# Installation Instructions — Compliance Classifier Prototype

This guide explains how to set up and run the **Compliance Classifier** project locally.

---

## 1. Clone the repository

```bash
git clone git@github.com:vectorworx/compliance-classifier-prototype.git
cd compliance-classifier-prototype
```

## 2. Create a Python virtual environment

```bash
python -m venv .venv
```

## 3. Activate the virtual environment

**Windows (Git Bash / PowerShell)**

```bash
source .venv/Scripts/activate
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

## 4. Upgrade pip

```bash
python -m pip install --upgrade pip
```

## 5. Install dependencies

```bash
pip install -r requirements.txt
```

## 6. Run the classifier

**GDPR mode**

```bash
python cc_mvp.py --regime GDPR
```

**SOC 2 mode**

```bash
python cc_mvp.py --regime SOC2
```

## 7. Deactivate the virtual environment

```bash
deactivate
```

---

## Notes

- All commits in this repository are **GPG signed** for authenticity.
- Dependencies are pinned in `requirements.txt` for reproducibility.
- Tested on **Python 3.11+** (recommended) and **pip 25+**.

## Commit this file

```bash
git add install_instructions.md
git commit -S -m "docs: add full installation guide (#ccenv)"
git push origin main
```
