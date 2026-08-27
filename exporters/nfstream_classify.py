#!/usr/bin/env python3
import json, os, sys, threading, time, tempfile, fcntl, atexit

INTERFACE = "eno1"
OUT_FILE = "/var/lib/prometheus/node-exporter/app_traffic_nfstream.prom"
STATE_FILE = "/home/takondwa/cwn_QoE_traffic_exporters/nfstream_totals_state.json"
LOCK_FILE = "/home/takondwa/cwn_QoE_traffic_exporters/nfstream_classify.lock"
FLUSH_INTERVAL = 30   # write totals to disk every 30s, independent of flow activity

state_lock = threading.Lock()
_lock_fd = None  # keep a reference so the OS lock isn't released by garbage collection


def acquire_singleton_lock():
    """Refuses to start a second instance. This is the actual fix for the
    corruption that just happened: two processes writing the same files
    with no coordination between them. flock() is released automatically
    if this process dies for any reason (crash, kill -9, reboot), so it
    can never get stuck 'locked' by a process that no longer exists."""
    global _lock_fd
    _lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[nfstream_classify.py] another instance is already running "
              "(lock held) -- refusing to start a second one. If you believe "
              "this is wrong, check `pgrep -af nfstream_classify.py` first.",
              file=sys.stderr)
        sys.exit(1)
    _lock_fd.write(str(os.getpid()))
    _lock_fd.flush()


def atomic_write(path, text):
    """Writes to a temp file in the same directory, then renames it over
    the target. os.replace() is atomic on POSIX -- any reader (including a
    second, misbehaving instance of this same script) only ever sees either
    the fully-old file or the fully-new file, never a half-written mix."""
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp_", text=True)
    os.chmod(tmp_path, 0o644)  # mkstemp defaults to 600; node_exporter needs read access
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # A corrupted state file (e.g. from a past concurrent-write
        # collision) should degrade to "start fresh with empty totals",
        # not crash the exporter and stop it updating entirely.
        print(f"[nfstream_classify.py] STATE_FILE unreadable ({e}); "
              f"starting from empty state. The corrupted file will be "
              f"overwritten on the next flush.", file=sys.stderr)
        return {}


def save_state(state):
    atomic_write(STATE_FILE, json.dumps(state))


def write_prom(state):
    lines = []
    for app, total in state.items():
        safe_app = app.replace('"', '')
        lines.append(f'node_app_traffic_bytes_nfstream{{app_name="{safe_app}"}} {total}\n')
    atomic_write(OUT_FILE, "".join(lines))


def periodic_flush(state):
    while True:
        time.sleep(FLUSH_INTERVAL)
        with state_lock:
            save_state(state)
            write_prom(state)


def main():
    acquire_singleton_lock()

    state = load_state()

    flusher = threading.Thread(target=periodic_flush, args=(state,), daemon=True)
    flusher.start()

    # Import nfstream only after the singleton check, so a rejected
    # second instance exits fast without the cost of loading it.
    from nfstream import NFStreamer

    streamer = NFStreamer(
        source=INTERFACE,          # LIVE interface, not a finite pcap file
        promiscuous_mode=False,
        snapshot_length=1536,
        idle_timeout=15,
        active_timeout=30,         # long flows get flushed every 30s, not lost until they end
        accounting_mode=0,
        n_dissections=20,
        statistical_analysis=False,
        splt_analysis=0,
        n_meters=1,
        performance_report=0,
    )

    for flow in streamer:   # runs forever, continuously, no gaps
        app = flow.application_name or "Unknown"
        with state_lock:
            state[app] = state.get(app, 0) + flow.bidirectional_bytes


if __name__ == "__main__":
    main()
