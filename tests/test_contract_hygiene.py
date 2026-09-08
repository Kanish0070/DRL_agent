"""Repo-hygiene guards for the P0 acceptance criteria that aren't tied to
a single function's behavior: exactly one AoI implementation must exist
anywhere in the codebase, so training, evaluation, and every simulator
back-end (including ns3-sim) can never silently drift onto their own
definition of Age of Information."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Directories that are expected to *reference* AoI (via imports or plain
# English/CSV-column mentions) but must never *define* their own update
# rule. ns3-sim is a separate C++ implementation by necessity (it cannot
# import Python) -- its cross-validation against the one true rule lives
# in ns3-sim/analysis/validate_against_contracts.py instead.
SEARCH_DIRS = ["common", "sim", "schedulers", "rl", "eval", "gateway", "tools"]

THIS_FILE = Path(__file__).resolve()


def _python_files():
    for d in SEARCH_DIRS:
        yield from (PROJECT_ROOT / d).rglob("*.py")
    # Include tests/ too, but never this file itself -- its own docstring
    # necessarily names the functions it's guarding.
    for f in (PROJECT_ROOT / "tests").rglob("*.py"):
        if f.resolve() != THIS_FILE:
            yield f


def _defines(symbol: str) -> list[Path]:
    return [f for f in _python_files() if f"def {symbol}" in f.read_text(encoding="utf-8")]


def test_exactly_one_update_aoi_for_slot_definition():
    assert _defines("update_aoi_for_slot") == [PROJECT_ROOT / "common" / "contracts" / "aoi.py"]


def test_exactly_one_compute_delivered_age_definition():
    assert _defines("compute_delivered_age") == [PROJECT_ROOT / "common" / "contracts" / "aoi.py"]
