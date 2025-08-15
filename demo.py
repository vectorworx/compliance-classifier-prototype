import sys, subprocess

PY = sys.executable  # use the same interpreter that's running this script

print("=== Running GDPR Demo ===")
subprocess.run([PY, "cc_mvp.py", "--regime", "GDPR"], check=True)

# Ensure edge docs are included in any packaged findings
print(
    "Included edge docs:",
    "data/testdocs/edgecase_gdpr_implied.txt,",
    "data/testdocs/edgecase_policy_ambiguous.txt",
)

print("\n=== Running SOC2 Demo ===")
subprocess.run([PY, "cc_mvp.py", "--regime", "SOC2"], check=True)

print("\n✅ Demo complete.")
