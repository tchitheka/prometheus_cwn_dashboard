#!/usr/bin/env python3
import subprocess, json, os
from collections import defaultdict
from app_map import classify

INTERFACE = "eno1"
CAPTURE_SECONDS = 55
OUT_FILE = "/var/lib/prometheus/node-exporter/app_traffic.prom"
STATE_FILE = "/home/takondwa/cwn_QoE_traffic_exporters/app_totals_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def main():
    cmd = [
        "tshark", "-i", INTERFACE, "-a", f"duration:{CAPTURE_SECONDS}",
        "-f", "tcp port 443",
        "-T", "fields",
        "-e", "ip.dst", "-e", "tls.handshake.extensions_server_name", "-e", "frame.len",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=CAPTURE_SECONDS + 15)

    ip_to_app = {}
    ip_bytes = defaultdict(int)

    for line in out.stdout.splitlines():
        parts = line.split("\t")
        dst_ip = parts[0] if len(parts) > 0 else ""
        sni = parts[1] if len(parts) > 1 else ""
        length = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        if sni:
            ip_to_app[dst_ip] = classify(sni)
        ip_bytes[dst_ip] += length

    window_bytes = defaultdict(int)
    for ip, total in ip_bytes.items():
        app = ip_to_app.get(ip, "Other")
        window_bytes[app] += total

    state = load_state()
    for app, b in window_bytes.items():
        state[app] = state.get(app, 0) + b
    save_state(state)

    with open(OUT_FILE, "w") as f:
        for app, total in state.items():
            f.write(f'node_app_traffic_bytes{{app_name="{app}"}} {total}\n')

if __name__ == "__main__":
    main()
