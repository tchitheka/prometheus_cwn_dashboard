#!/usr/bin/env python3
import subprocess, statistics, re, sys

TARGETS = ["8.8.8.8", "1.1.1.1"]   # add your real upstream gateway IP here
PING_COUNT = 20                     # single source of truth -- must match -C below
OUT_FILE = "/var/lib/prometheus/node-exporter/qoe.prom"

# Written when zero RTT samples could be collected at all -- e.g. total
# loss to both targets, or every probe timing out. This deliberately
# maps, through the panel's own threshold formula
#   clamp_min(clamp_max(floor((300 - p90) / 100), 2), 0)
# to the WORST verdict (0, red/critical), not the best. The old sentinel
# of -1 produced "healthy" instead -- a total connectivity failure was
# computing to the exact same verdict as a perfect 0ms connection, and
# was directly observed doing so live on the dashboard.
NO_DATA_SENTINEL_MS = 99999


def probe(target):
    """Returns (rtts, lost) for one target. On any failure to get a
    usable result from fping, treats every attempted ping to this
    target as lost rather than silently excluding it."""
    try:
        cmd = ["fping", "-C", str(PING_COUNT), "-p", "200", "-q", target]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        print(f"[latency.py] probe({target}) failed to run fping: {e}", file=sys.stderr)
        return [], PING_COUNT

    line = out.stderr.strip()
    if ":" not in line:
        print(f"[latency.py] probe({target}) produced no parseable output; "
              f"stderr={line!r}", file=sys.stderr)
        return [], PING_COUNT

    _, rtts_str = line.split(":", 1)
    tokens = rtts_str.split()
    rtts = [float(x) for x in tokens if re.match(r"^\d+\.?\d*$", x)]
    lost = len(tokens) - len(rtts)
    return rtts, lost


def main():
    all_rtts = []
    total_sent = 0
    total_lost = 0

    for t in TARGETS:
        try:
            rtts, lost = probe(t)
        except Exception as e:
            print(f"[latency.py] unexpected error probing {t}: {e}", file=sys.stderr)
            rtts, lost = [], PING_COUNT
        all_rtts.extend(rtts)
        total_sent += PING_COUNT
        total_lost += lost

    loss_ratio = (total_lost / total_sent) if total_sent else 1.0

    try:
        with open(OUT_FILE, "w") as f:
            if all_rtts:
                all_rtts.sort()
                p90 = all_rtts[int(len(all_rtts) * 0.9) - 1]
                p50 = statistics.median(all_rtts)
                jitter = statistics.pstdev(all_rtts) if len(all_rtts) > 1 else 0.0
                f.write(f'node_qoe_rtt_p90_ms{{job="gw-latency"}} {p90:.2f}\n')
                f.write(f'node_qoe_rtt_p50_ms{{job="gw-latency"}} {p50:.2f}\n')
                f.write(f'node_qoe_jitter_ms{{job="gw-latency"}} {jitter:.2f}\n')
            else:
                f.write(f'node_qoe_rtt_p90_ms{{job="gw-latency"}} {NO_DATA_SENTINEL_MS}\n')

            f.write(f'node_qoe_packet_loss_ratio{{job="gw-latency"}} {loss_ratio:.4f}\n')
    except OSError as e:
        print(f"[latency.py] FAILED to write {OUT_FILE}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
