#!/usr/bin/env python3
import subprocess

INTERFACE = "eno1"          # confirm with `ip link`
CAPTURE_SECONDS = 30
OUT_FILE = "/var/lib/prometheus/node-exporter/dns_health.prom"

def main():
    cmd = [
        "tshark", "-i", INTERFACE, "-a", f"duration:{CAPTURE_SECONDS}",
        "-f", "udp port 53", "-Y", "dns.flags.response == 1",
        "-T", "fields", "-e", "dns.flags.rcode",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=CAPTURE_SECONDS + 15)
    rcodes = [l for l in out.stdout.splitlines() if l.strip()]

    total = len(rcodes)
    # rcode 0 = success. Anything else (2=SERVFAIL, 3=NXDOMAIN, 4=NOTIMP, etc) counts as failure.
    failures = sum(1 for r in rcodes if r.strip() != "0")
    ratio = (failures / total) if total else 0.0

    with open(OUT_FILE, "w") as f:
        f.write(f'node_dns_failure_ratio {ratio:.4f}\n')
        f.write(f'node_dns_queries_total {total}\n')
        f.write(f'node_dns_failures_total {failures}\n')

if __name__ == "__main__":
    main()