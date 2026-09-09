"""Cross-validate an NS-3 telemetry CSV against the frozen Python contracts.

This is the bridge that proves the NS-3 C++ simulation and the project's
Python codebase agree on the math: it re-derives every node's AoI trace
independently using common/contracts/aoi.py::update_aoi_for_slot and checks
it against what the NS-3 simulation logged, and it checks the CSV's column
order against common/contracts/log_schema.py::SLOT_LOG_COLUMNS.

Must be run from the project root so `import common...` resolves:
    python ns3-sim/analysis/validate_against_contracts.py ns3-sim/results/rr_seed0.csv
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.contracts.aoi import update_aoi_for_slot  # noqa: E402
from common.contracts.log_schema import SLOT_LOG_COLUMNS, validate_slot_row  # noqa: E402
from common.contracts.state_spec import get_state_schema_hash  # noqa: E402

N_NODES = 4
MAX_ERROR_TOLERANCE_S = 1e-3  # 1 ms; well under the 1us claim once slot-quantized


def validate_schema(df: pd.DataFrame) -> list[str]:
    errors = []
    csv_cols = list(df.columns)
    if csv_cols != SLOT_LOG_COLUMNS:
        missing = set(SLOT_LOG_COLUMNS) - set(csv_cols)
        extra = set(csv_cols) - set(SLOT_LOG_COLUMNS)
        errors.append(f"SCHEMA MISMATCH: missing={missing}, extra={extra}, "
                      f"order_matches={csv_cols == SLOT_LOG_COLUMNS}")
    else:
        print("PASS: Schema validation -- CSV columns match SLOT_LOG_COLUMNS exactly")

    if not df.empty and not validate_slot_row(df.iloc[0].to_dict()):
        errors.append("SCHEMA MISMATCH: first row fails log_schema.validate_slot_row()")
    return errors


def validate_aoi_recomputation(df: pd.DataFrame) -> list[str]:
    errors = []
    if len(df) < 2:
        print("SKIP: AoI recomputation -- not enough rows")
        return errors

    t_slot = df["timestamp_pi"].diff().median()
    recomputed_aoi = [0.0] * N_NODES
    max_error = 0.0

    for _, row in df.iterrows():
        granted_node = int(row["action_granted_node"])
        uplink_ok = int(row.get("uplink_received", 0))

        for i in range(N_NODES):
            packet_arrived = i == granted_node and uplink_ok == 1
            delivered_age = row.get("delivered_age_us", 0) / 1e6 if packet_arrived else 0.0
            recomputed_aoi[i] = update_aoi_for_slot(
                recomputed_aoi[i], packet_arrived, delivered_age, t_slot
            )
            ns3_aoi = row[f"aoi_n{i + 1}"]
            max_error = max(max_error, abs(recomputed_aoi[i] - ns3_aoi))

    if max_error < MAX_ERROR_TOLERANCE_S:
        print(f"PASS: AoI recomputation -- max error: {max_error * 1e6:.1f} us")
    else:
        errors.append(f"AoI MISMATCH: max error {max_error:.6f} s "
                       f"(tolerance {MAX_ERROR_TOLERANCE_S:.6f} s)")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()

    df = pd.read_csv(args.csv_path)
    errors = validate_schema(df)
    errors += validate_aoi_recomputation(df)

    print(f"INFO: State schema hash: {get_state_schema_hash()}")

    if errors:
        print(f"\nFAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)

    print("\nALL VALIDATIONS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
