import os
import sys

filepath = "tools/run_sensitivity_sweep.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('["python", "-m", "eval.run"', '[sys.executable, "-m", "eval.run"')
content = "import sys\n" + content

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated run_sensitivity_sweep.py to use sys.executable")
