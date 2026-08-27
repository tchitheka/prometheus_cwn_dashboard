#!/usr/bin/env python3
import subprocess, statistics, re

TARGETS = ["8.8.8.8", "1.1.1.1"]   # add your real upstream gateway IP here
OUT_FILE = "/var/lib/prometheus/node-exporter/qoe.prom"

def probe(target):
    cmd = ["fping", "-C", "20", "-p", "200", "-q", target]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    # fping -q prints results to stderr as: "target : rtt1 rtt2 - rtt3 ..."
    line = out.stderr.strip()
    if ":" not in line:
        return None
    _, rtts_str = line.split(":", 1)
    rtts = [float(x) for x in rtts_str.split() if re.match(r"^\d+\.?\d*$", x)]
    return rtts

def main():
    all_rtts = []
    for t in TARGETS:
        rtts = probe(t)
        if rtts:
            all_rtts.extend(rtts)

    with open(OUT_FILE, "w") as f:
        if all_rtts:
            all_rtts.sort()
            p90 = all_rtts[int(len(all_rtts) * 0.9) - 1]
            p50 = statistics.median(all_rtts)
            f.write(f'node_qoe_rtt_p90_ms{{job="gw-latency"}} {p90:.2f}\n')
            f.write(f'node_qoe_rtt_p50_ms{{job="gw-latency"}} {p50:.2f}\n')
        else:
            f.write(f'node_qoe_rtt_p90_ms{{job="gw-latency"}} -1\n')

if __name__ == "__main__":
    main()
