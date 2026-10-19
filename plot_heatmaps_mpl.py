import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

df = pd.read_csv('sensitivity_results/summary.csv')
df['diff_percent'] = (df['dqn_aoi'] - df['mw_aoi']) / df['mw_aoi'] * 100

for dist in ['Easy', 'Steep']:
    sub = df[df['dist_type'] == dist]
    pivot = sub.pivot_table(index='r50', columns=['arrival', 'burst'], values='diff_percent', aggfunc='mean')
    
    fig, ax = plt.subplots(figsize=(10, 6))
    cax = ax.matshow(pivot.values, cmap='RdYlGn_r')
    
    fig.colorbar(cax, label='AoI Diff % (Negative = DQN Wins)')
    
    # Set labels
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_xticklabels([f"Arr:{a}, B:{b}" for a, b in pivot.columns])
    ax.set_yticklabels(pivot.index)
    
    # Annotate
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            ax.text(j, i, f"{val:.1f}%", va='center', ha='center', color='black' if abs(val) < 15 else 'white')
            
    plt.title(f'DQN vs Max-Weight (Difference %)\\nDistance Profile: {dist}', pad=20)
    plt.xlabel('Arrival Prob / Burst Loss')
    plt.ylabel('R50 Threshold (dBm)')
    
    plt.tight_layout()
    plt.savefig(f'sensitivity_results/heatmap_{dist.lower()}.png')
    plt.close()

print("Heatmaps generated.")
