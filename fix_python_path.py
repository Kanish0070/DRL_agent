import os

filepath = "tools/run_sensitivity_sweep.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('["uv", "run", "python",', '["D:\\\\dev_env\\\\Final_year\\\\DRL_agent\\\\.venv\\\\Scripts\\\\python.exe",')

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
