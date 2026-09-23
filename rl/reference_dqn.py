"""From-scratch PyTorch DQN reference implementation (T5.6).

Completely independent of SB3 — exists to cross-check that the SB3 training
run is not hiding implementation bugs. Final CW-AoI must be within 15% of
the SB3 result (literal T5.1 acceptance criterion).

Usage:
    python -m rl.reference_dqn --seed 0 --timesteps 200000
"""
import argparse
import collections
import copy
import random

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from common.config import load_measured_params, load_system_config
from common.metrics import criticality_weighted_aoi
from rl.env import AoiSchedulerEnv

# ──────────────────────────────────────────────
# Replay buffer
# ──────────────────────────────────────────────
Transition = collections.namedtuple(
    "Transition", ("obs", "action", "reward", "next_obs", "done")
)


class ReplayBuffer:
    def __init__(self, capacity: int, rng: np.random.Generator):
        self._buf: collections.deque[Transition] = collections.deque(maxlen=capacity)
        self._rng = rng

    def push(self, *args):
        self._buf.append(Transition(*args))

    def sample(self, batch_size: int) -> Transition:
        idxs = self._rng.integers(0, len(self._buf), size=batch_size)
        batch = [self._buf[i] for i in idxs]
        return Transition(*[np.array(x) for x in zip(*batch)])

    def __len__(self):
        return len(self._buf)


# ──────────────────────────────────────────────
# Q-Network (matches SB3 MlpPolicy net_arch)
# ──────────────────────────────────────────────
class QNet(nn.Module):
    def __init__(self, obs_dim: int, n_actions: int, net_arch: list[int]):
        super().__init__()
        layers = []
        in_dim = obs_dim
        for h in net_arch:
            layers += [nn.Linear(in_dim, h), nn.ReLU()]
            in_dim = h
        layers.append(nn.Linear(in_dim, n_actions))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ──────────────────────────────────────────────
# Training loop
# ──────────────────────────────────────────────
def train(seed: int, timesteps: int, sys_cfg: dict, meas_cfg: dict) -> float:
    rl_cfg = sys_cfg["rl"]
    rng = np.random.Generator(np.random.PCG64(seed))
    torch.manual_seed(seed)
    random.seed(seed)

    env = AoiSchedulerEnv(sys_cfg, meas_cfg, seed=seed)
    obs_dim = env.observation_space.shape[0]
    n_actions = env.action_space.n

    q_net = QNet(obs_dim, n_actions, rl_cfg["net_arch"])
    target_net = copy.deepcopy(q_net)
    target_net.eval()

    optimizer = optim.Adam(q_net.parameters(), lr=rl_cfg["learning_rate"])
    buf = ReplayBuffer(rl_cfg["buffer_size"], rng)

    gamma = rl_cfg["gamma"]
    batch_size = rl_cfg["batch_size"]
    target_update = rl_cfg["target_update_interval"]
    eps_start = rl_cfg["eps_start"]
    eps_end = rl_cfg["eps_end"]
    eps_fraction = rl_cfg["eps_fraction"]

    obs, _ = env.reset(seed=seed)
    step = 0

    while step < timesteps:
        # Epsilon-greedy exploration
        frac = min(1.0, step / (eps_fraction * timesteps))
        eps = eps_start + frac * (eps_end - eps_start)
        if rng.random() < eps:
            action = env.action_space.sample()
        else:
            with torch.no_grad():
                q_vals = q_net(torch.tensor(obs).unsqueeze(0))
                action = int(q_vals.argmax(dim=1).item())

        next_obs, reward, terminated, truncated, _ = env.step(action)
        done = terminated or truncated
        buf.push(obs, action, reward, next_obs, float(done))
        obs = next_obs if not done else env.reset(seed=rng.integers(0, 2**31))[0]

        if len(buf) >= batch_size:
            batch = buf.sample(batch_size)
            obs_t = torch.tensor(batch.obs, dtype=torch.float32)
            act_t = torch.tensor(batch.action, dtype=torch.long).unsqueeze(1)
            rew_t = torch.tensor(batch.reward, dtype=torch.float32).unsqueeze(1)
            nobs_t = torch.tensor(batch.next_obs, dtype=torch.float32)
            done_t = torch.tensor(batch.done, dtype=torch.float32).unsqueeze(1)

            with torch.no_grad():
                next_q = target_net(nobs_t).max(dim=1, keepdim=True).values
                target_q = rew_t + gamma * (1 - done_t) * next_q

            current_q = q_net(obs_t).gather(1, act_t)
            loss = nn.functional.mse_loss(current_q, target_q)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            if step % target_update == 0:
                target_net.load_state_dict(q_net.state_dict())

        step += 1

    # Evaluate
    weights = np.array(
        [sys_cfg["scheduler"]["weights"][c] for c in sys_cfg["system"]["node_classes"]]
    )
    eval_env = AoiSchedulerEnv(sys_cfg, meas_cfg)
    eval_obs, _ = eval_env.reset(seed=100)
    cw_aois = []
    q_net.eval()
    for _ in range(rl_cfg["episode_length"]):
        with torch.no_grad():
            act = int(q_net(torch.tensor(eval_obs).unsqueeze(0)).argmax(dim=1).item())
        eval_obs, _, term, trunc, info = eval_env.step(act)
        cw_aois.append(criticality_weighted_aoi(info["aoi"], weights))
        if term or trunc:
            break

    return float(np.mean(cw_aois))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timesteps", type=int, default=200_000)
    args = parser.parse_args()

    sys_cfg = load_system_config()
    meas_cfg = load_measured_params()
    result = train(args.seed, args.timesteps, sys_cfg, meas_cfg)
    print(f"[reference_dqn] seed={args.seed} cw_mean_aoi={result:.4f}")


if __name__ == "__main__":
    main()
