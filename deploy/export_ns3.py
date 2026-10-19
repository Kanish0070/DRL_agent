"""Export trained DQN models to plain-text format for ns-3 C++ inference (N1.1).

Format:
    AOIDQN 1
    schema_hash <get_state_schema_hash()>
    n_layers <int>
    layer <idx> <out_features> <in_features>
    <out * in weights in row-major order, space-separated>
    <out biases, space-separated>
"""
import argparse
from pathlib import Path
import numpy as np

from common.contracts.state_spec import get_state_schema_hash


def export_npz_to_txt(npz_path: str, txt_path: str) -> None:
    data = np.load(npz_path, allow_pickle=True)
    schema_hash = str(data["state_schema_hash"])
    expected_hash = get_state_schema_hash()
    if schema_hash != expected_hash:
        raise ValueError(
            f"Schema hash mismatch: file has {schema_hash}, expected {expected_hash}"
        )

    n_layers = int(data["n_layers"])

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("AOIDQN 1\n")
        f.write(f"schema_hash {schema_hash}\n")
        f.write(f"n_layers {n_layers}\n")

        for i in range(n_layers):
            w = data[f"w{i}"]  # shape: (out_features, in_features)
            b = data[f"b{i}"]  # shape: (out_features,)
            out_features, in_features = w.shape

            f.write(f"layer {i} {out_features} {in_features}\n")
            # Write weights row-major
            weight_strs = [f"{float(val):.9g}" for val in w.flatten()]
            f.write(" ".join(weight_strs) + "\n")
            # Write biases
            bias_strs = [f"{float(val):.9g}" for val in b.flatten()]
            f.write(" ".join(bias_strs) + "\n")

    print(f"[export_ns3] Wrote {txt_path}")


def export_all(artifacts_dir: str = "deploy/artifacts"):
    artifacts_path = Path(artifacts_dir)
    seeds = [0, 1, 2, 3, 4]
    for seed in seeds:
        npz_file = artifacts_path / f"dqn_seed{seed}.npz"
        txt_file = artifacts_path / f"dqn_seed{seed}.txt"
        if npz_file.exists():
            export_npz_to_txt(str(npz_file), str(txt_file))
        else:
            print(f"[skip] {npz_file} not found")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export .npz weights to plain-text for ns-3 C++.")
    parser.add_argument("--npz", help="Path to input .npz file (optional, exports all if omitted)")
    parser.add_argument("--out", help="Path to output .txt file")
    parser.add_argument("--artifacts-dir", default="deploy/artifacts", help="Artifacts directory")
    args = parser.parse_args()

    if args.npz and args.out:
        export_npz_to_txt(args.npz, args.out)
    else:
        export_all(args.artifacts_dir)
