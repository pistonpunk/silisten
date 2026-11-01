import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config

ROOT = Path(__file__).resolve().parent.parent


def api(path, payload=None, timeout=15):
    cfg = config.load()
    url = f"http://127.0.0.1:{int(cfg.get('port') or 8756)}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method="POST" if payload is not None else "GET",
        headers={"X-Silisten-Token": config.token(), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def cmd_toggle(_args):
    try:
        api("/toggle", {})
    except (urllib.error.URLError, OSError):
        print("silisten is not running (start it with: silisten start)", file=sys.stderr)
        return 1
    return 0


def _boot():
    from . import server

    cfg = config.load()
    app, httpd = server.create_app(cfg)
    app.boot()
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return cfg, httpd


def cmd_backend(_args):
    cfg, httpd = _boot()
    print(f"silisten backend on 127.0.0.1:{cfg['port']}  shortcut {cfg['shortcut']}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


def cmd_start(_args):
    cfg, httpd = _boot()
    electron = ROOT / "ui" / "node_modules" / ".bin" / "electron"
    if not electron.exists():
        print("electron is not installed - run ./install.sh", file=sys.stderr)
        httpd.shutdown()
        return 1
    env = dict(os.environ)
    env["SILISTEN_URL"] = f"http://127.0.0.1:{cfg['port']}"
    env["SILISTEN_TOKEN"] = config.token()
    proc = subprocess.Popen(
        [str(electron), ".", "--ozone-platform=x11"], cwd=str(ROOT / "ui"), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    finally:
        httpd.shutdown()
    return 0


def cmd_setup(args):
    from . import setup

    return setup.run(args)


def cmd_config(args):
    cfg = config.load()
    for pair in args.set or []:
        key, _, value = pair.partition("=")
        value = value.strip()
        if value in ("true", "false"):
            value = value == "true"
        elif value in ("null", "None", ""):
            value = None
        cfg[key.strip()] = value
    if args.set:
        config.save(cfg)
    print(f"# {config.PATH}")
    print(json.dumps(cfg, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="silisten")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("start", help="run backend + notch UI")
    sub.add_parser("backend", help="run backend only")
    sub.add_parser("toggle", help="start/stop listening (bind this to a desktop shortcut)")
    setup_parser = sub.add_parser("setup", help="install input rule, autostart and models")
    setup_parser.add_argument("--hf-token", dest="hf_token")
    setup_parser.add_argument("--no-prefetch", action="store_true")
    config_parser = sub.add_parser("config", help="show or set config")
    config_parser.add_argument("--set", action="append", metavar="KEY=VALUE")
    args = parser.parse_args(argv)
    command = args.command or "start"
    if command == "start":
        return cmd_start(args)
    if command == "backend":
        return cmd_backend(args)
    if command == "toggle":
        return cmd_toggle(args)
    if command == "setup":
        return cmd_setup(args)
    if command == "config":
        return cmd_config(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
