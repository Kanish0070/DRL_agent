import numpy as np
from stable_baselines3 import DQN
from common.contracts.state_spec import get_state_schema_hash

def export_model(model: DQN, output_path: str):
    q_net = model.q_net  # SB3's QNetwork
    layers = [(l.weight.detach().numpy(), l.bias.detach().numpy())
              for l in q_net.q_net if hasattr(l, "weight")]
    np.savez(output_path,
             **{f"w{i}": w for i, (w, b) in enumerate(layers)},
             **{f"b{i}": b for i, (w, b) in enumerate(layers)},
             n_layers=len(layers),
             state_schema_hash=get_state_schema_hash())
