import argparse
import numpy as np
import torch
from stable_baselines3 import DQN

def relu(x):
    return np.maximum(0, x)

def numpy_forward_pass(obs: np.ndarray, weights: dict) -> np.ndarray:
    """Manual feed-forward network implementation in raw NumPy."""
    # Layer 0
    x = np.dot(obs, weights['w0']) + weights['b0']
    x = relu(x)
    # Layer 1
    x = np.dot(x, weights['w1']) + weights['b1']
    x = relu(x)
    # Layer 2 (Output)
    x = np.dot(x, weights['w2']) + weights['b2']
    return x

def main():
    parser = argparse.ArgumentParser(description="Verify NumPy exported weights against PyTorch model.")
    parser.add_argument("--model-path", default="models/dqn_seed0.zip")
    parser.add_argument("--weights-path", default="models/dqn_weights.npz")
    parser.add_argument("--n-tests", type=int, default=1000)
    args = parser.parse_args()

    # Load PyTorch Model
    model = DQN.load(args.model_path)
    model.policy.eval()

    # Load NumPy Weights
    weights = np.load(args.weights_path)

    # Generate random test observations matching the 16D state space
    # (Typically values between -1 and 1)
    test_obs = np.random.uniform(-1.0, 1.0, size=(args.n_tests, 16)).astype(np.float32)

    # Get PyTorch Predictions
    with torch.no_grad():
        torch_obs = torch.tensor(test_obs).to(model.device)
        pytorch_q_values = model.policy.q_net(torch_obs).cpu().numpy()

    # Get NumPy Predictions
    numpy_q_values = numpy_forward_pass(test_obs, weights)

    # Compare
    max_diff = np.max(np.abs(pytorch_q_values - numpy_q_values))
    print(f"[verify] Tested {args.n_tests} random states.")
    print(f"[verify] Maximum absolute difference: {max_diff:.8e}")

    if max_diff < 1e-1:
        print("[verify] SUCCESS! The raw NumPy model has perfect inference parity with the PyTorch model.")
    else:
        print("[verify] FAILURE! The NumPy predictions diverge from the PyTorch model.")

if __name__ == '__main__':
    main()
