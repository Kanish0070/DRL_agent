import os
import re

filepath = "task.md"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# I need to set T5.6, T5.7, T5.8, P6 statuses to their true state.
# But I don't know the exact text. Let's print out the relevant lines from task.md.
lines = content.split('\n')
for i, line in enumerate(lines):
    if "T5.6" in line or "T5.7" in line or "T5.8" in line or "P6" in line:
        print(f"{i}: {line}")

