import os

filepath = "common/provenance.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

if "import os" not in content:
    content = "import os\n" + content
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Added import os to provenance.py")
