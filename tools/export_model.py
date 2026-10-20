import argparse
from pathlib import Path
import numpy as np
from stable_baselines3 import DQN

def main():
    parser = argparse.ArgumentParser(description="Export PyTorch model weights to NumPy.")
    parser.add_argument("--model-path", default="models/dqn_seed0.zip", help="Path to the trained SB3 model")
    parser.add_argument("--out-path", default="models/dqn_weights.npz", help="Output .npz file")
    args = parser.parse_args()

    model = DQN.load(args.model_path)
    state_dict = model.policy.q_net.state_dict()

    # Extract weights and biases (convert to numpy)
    w0 = state_dict['q_net.0.weight'].cpu().numpy()
    b0 = state_dict['q_net.0.bias'].cpu().numpy()
    w1 = state_dict['q_net.2.weight'].cpu().numpy()
    b1 = state_dict['q_net.2.bias'].cpu().numpy()
    w2 = state_dict['q_net.4.weight'].cpu().numpy()
    b2 = state_dict['q_net.4.bias'].cpu().numpy()

    # Save to NPZ (Note: PyTorch stores linear weights as (out_features, in_features))
    # We transpose them so they match standard X * W + B logic in C/C++
    np.savez(
        args.out_path,
        w0=w0.T, b0=b0,
        w1=w1.T, b1=b1,
        w2=w2.T, b2=b2
    )
    print(f"[export] Extracted weights from {args.model_path}")
    print(f"[export] Saved to {args.out_path}")
    print(f"  w0: {w0.T.shape}, b0: {b0.shape}")
    print(f"  w1: {w1.T.shape}, b1: {b1.shape}")
    print(f"  w2: {w2.T.shape}, b2: {b2.shape}")

if __name__ == '__main__':
    main()

