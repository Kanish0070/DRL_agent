import os
import re

filepath = "docs/FITTING_REPORT.md"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(
    r"This document serves as the formal record of how the simulation environment.*?training\.",
    "This document outlines the parameter ranges consistent with literature and external datasets.\n**Note:** The current parameters in config/measured_params.yaml are placeholders pending the real P1 hardware campaign. No automated fit script has been run against raw data yet.",
    content,
    flags=re.DOTALL
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated FITTING_REPORT.md using regex")
