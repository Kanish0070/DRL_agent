import os

filepath = "docs/FITTING_REPORT.md"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old = "This document serves as the formal record of how the simulation environment (NetworkSim) was mathematically calibrated using external datasets before commencing Deep Reinforcement Learning (DRL) training."
new = "This document outlines the parameter ranges consistent with literature and external datasets.\n**Note:** The current parameters in config/measured_params.yaml are placeholders pending the real P1 hardware campaign. No automated fit script has been run against raw data yet."

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated FITTING_REPORT.md")
else:
    print("Could not find string in FITTING_REPORT.md. Here are the first 300 chars:")
    print(content[:300])
