import os

filepath = "tools/run_sensitivity_sweep.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('[sys.executable,', '["uv", "run", "python",')

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
