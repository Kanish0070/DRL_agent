import os
import re

filepath = "task.md"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace ? DONE with ? TODO for T5.6, T5.7, T5.8, P6
def replace_status(match):
    line = match.group(0)
    return line.replace("? DONE", "? TODO")

content = re.sub(r"^\| T5\.6 .*$", replace_status, content, flags=re.MULTILINE)
content = re.sub(r"^\| T5\.7 .*$", replace_status, content, flags=re.MULTILINE)
content = re.sub(r"^\| T5\.8 .*$", replace_status, content, flags=re.MULTILINE)
content = re.sub(r"^\| T6\.\d .*$", replace_status, content, flags=re.MULTILINE)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated task.md")
