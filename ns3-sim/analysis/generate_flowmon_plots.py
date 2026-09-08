"""Turn an NS-3 FlowMonitor XML export into review-panel bar charts.

Usage:
    python generate_flowmon_plots.py results/flowmon-results.xml [--out results/flowmon_metrics.png]
"""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib.pyplot as plt

PORT_GRANT = 5006
PORT_DATA = 5005
PORT_HB = 5007


def _parse_ns_duration(value: str) -> float:
    """Parse an ns-3 duration string like '+123456789.0ns' into seconds."""
    cleaned = value.replace("+", "").replace("ns", "")
    return float(cleaned) / 1e9


def _classify_flow(src_port: int, dst_port: int) -> str:
    if dst_port == PORT_GRANT:
        return "AP -> STA (GRANT)"
    if dst_port == PORT_DATA:
        return "STA -> AP (DATA)"
    if dst_port == PORT_HB:
        return "STA -> AP (HEARTBEAT)"
    return f"port {src_port}->{dst_port}"


def parse_flowmon(xml_path: Path) -> list[dict]:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    classifier_by_id = {}
    classifier = root.find("Ipv4FlowClassifier")
    if classifier is not None:
        for flow in classifier.findall("Flow"):
            classifier_by_id[flow.get("flowId")] = {
                "src": flow.get("sourceAddress"),
                "dst": flow.get("destinationAddress"),
                "src_port": int(flow.get("sourcePort", 0)),
                "dst_port": int(flow.get("destinationPort", 0)),
            }

    flows = []
    for stats in root.find("FlowStats").findall("Flow"):
        flow_id = stats.get("flowId")
        tx_packets = int(stats.get("txPackets", 0))
        rx_packets = int(stats.get("rxPackets", 0))
        lost_packets = int(stats.get("lostPackets", 0))
        rx_bytes = int(stats.get("rxBytes", 0))

        first_tx = _parse_ns_duration(stats.get("timeFirstTxPacket", "+0ns"))
        last_rx = _parse_ns_duration(stats.get("timeLastRxPacket", "+0ns"))
        duration_s = max(last_rx - first_tx, 1e-9)

        delay_sum_s = _parse_ns_duration(stats.get("delaySum", "+0ns"))
        jitter_sum_s = _parse_ns_duration(stats.get("jitterSum", "+0ns"))

        meta = classifier_by_id.get(flow_id, {})
        label = _classify_flow(meta.get("src_port", 0), meta.get("dst_port", 0))
        endpoint = f"{meta.get('src', '?')} -> {meta.get('dst', '?')}"

        flows.append({
            "flow_id": flow_id,
            "label": f"{label} [{endpoint}]",
            "is_uplink": meta.get("dst_port") in (PORT_DATA, PORT_HB),
            "throughput_kbps": (rx_bytes * 8 / duration_s) / 1024.0,
            "avg_delay_ms": (delay_sum_s / rx_packets * 1000.0) if rx_packets else 0.0,
            "avg_jitter_ms": (jitter_sum_s / max(rx_packets - 1, 1) * 1000.0) if rx_packets else 0.0,
            "loss_pct": (lost_packets / tx_packets * 100.0) if tx_packets else 0.0,
        })
    return flows


def plot_flowmon(flows: list[dict], out_path: Path) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    labels = [f["label"] for f in flows]
    colors = ["#2A9D8F" if f["is_uplink"] else "#457B9D" for f in flows]
    y = range(len(flows))

    panels = [
        (axes[0][0], "throughput_kbps", "Throughput (Kbps)"),
        (axes[0][1], "avg_delay_ms", "Average Delay (ms)"),
        (axes[1][0], "loss_pct", "Packet Loss (%)"),
        (axes[1][1], "avg_jitter_ms", "Average Jitter (ms)"),
    ]
    for ax, key, title in panels:
        ax.barh(list(y), [f[key] for f in flows], color=colors)
        ax.set_yticks(list(y))
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_title(title, fontsize=11)
        ax.grid(True, axis="x", alpha=0.3)
        ax.invert_yaxis()

    fig.suptitle("FlowMonitor Metrics (green=uplink STA->AP, blue=downlink AP->STA)", fontsize=13)
    plt.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml_path", type=Path)
    parser.add_argument("--out", type=Path, default=None,
                         help="Output PNG path (default: <xml_dir>/flowmon_metrics.png)")
    args = parser.parse_args()

    out_path = args.out or (args.xml_path.parent / "flowmon_metrics.png")
    flows = parse_flowmon(args.xml_path)
    if not flows:
        raise SystemExit(f"No flows found in {args.xml_path}")

    saved = plot_flowmon(flows, out_path)
    print(f"Saved: {saved}")


if __name__ == "__main__":
    main()
