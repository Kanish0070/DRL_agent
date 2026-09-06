# AoI DRL Scheduler

DRL-Based Age-of-Information-Aware Cross-Layer Scheduler for mixed-criticality wireless IoT networks.

## Setup

This project uses Python 3.11 and is designed to run both on a laptop (for training/simulation) and a Raspberry Pi Zero 2W (for deployment).

### 1. Create a Virtual Environment

```bash
python3.11 -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 2. Install Dependencies

Depending on what part of the project you are working on, install the necessary dependencies:

**For Simulation & Training (Laptop):**
```bash
pip install -e .[train,dev]
```

**For Gateway Deployment (Raspberry Pi):**
*(Note: PyTorch is explicitly excluded to save space and avoid ARM wheel issues on the Pi Zero)*
```bash
pip install -e .
```

### 3. Pre-commit Hooks

Ensure code formatting remains consistent by installing the pre-commit hooks:
```bash
pre-commit install
```
