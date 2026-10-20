import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv('sensitivity_results/summary.csv')

# We want a heatmap of DQN vs MaxWeight AoI Difference
# Let's map it based on r50 (y-axis) and (arrival, burst) on x-axis
# We can do this for both Easy and Steep distances

df['diff_percent'] = (df['dqn_aoi'] - df['mw_aoi']) / df['mw_aoi'] * 100

for dist in ['Easy', 'Steep']:
    sub = df[df['dist_type'] == dist]
    
    # Average over slopes
    pivot = sub.pivot_table(index='r50', columns=['arrival', 'burst'], values='diff_percent', aggfunc='mean')
    
    plt.figure(figsize=(10, 6))
    sns.heatmap(pivot, annot=True, fmt=".1f", cmap="RdYlGn_r", center=0, 
                cbar_kws={'label': 'AoI Difference % (Negative = DQN Wins)'})
    plt.title(f'DQN vs Max-Weight (Difference %)\\nDistance Profile: {dist}')
    plt.ylabel('R50 Threshold (dBm)')
    plt.xlabel('Arrival Prob / Burst Loss')
    plt.tight_layout()
    plt.savefig(f'sensitivity_results/heatmap_{dist.lower()}.png')
    plt.close()

print("Heatmaps generated at sensitivity_results/heatmap_easy.png and heatmap_steep.png")
