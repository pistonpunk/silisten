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
    if not _already_running():
        _spawn("start")
        for _ in range(120):
            time.sleep(0.5)
            if _already_running():
                break
        else:
            print("silisten did not start", file=sys.stderr)
            return 1
    for _ in range(40):
        try:
            state = api("/toggle", {}, timeout=20)
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)
            continue
        if state.get("status") == "thinking" or state.get("reveal"):
            return 0
    return 0


def _spawn(command):
    env = dict(os.environ)
    subprocess.Popen(
        [sys.executable, "-m", "silisten", command],
        cwd=str(ROOT),
        env={**env, "PYTHONPATH": str(ROOT)},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def cmd_shortcut(args):
    from . import setup

    cfg = config.load()
    if args.chord:
        cfg["shortcut"] = args.chord.strip()
        config.save(cfg)
    if not setup.gnome_shortcut(cfg["shortcut"]):
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
    if _already_running():
        print("silisten backend is already running", file=sys.stderr)
        return 1
    cfg, httpd = _boot()
    print(f"silisten backend on 127.0.0.1:{cfg['port']}  shortcut {cfg['shortcut']}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


def _already_running():
    try:
        api("/state", timeout=2)
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _kill_stale_ui():
    import signal

    try:
        out = subprocess.run(["pgrep", "-f", "silisten-qt"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return
    for pid in out.stdout.split():
        try:
            with open(f"/proc/{pid}/comm") as handle:
                if "silisten-qt" not in handle.read():
                    continue
            os.kill(int(pid), signal.SIGTERM)
        except (OSError, ValueError):
            continue


def cmd_start(_args):
    cfg = config.load()
    owns_backend = not _already_running()
    if owns_backend:
        cfg, httpd = _boot()
    ui = ROOT / "ui-qt" / "build" / "silisten-qt"
    if not ui.exists():
        print("ui not built - run ./install.sh", file=sys.stderr)
        if owns_backend:
            httpd.shutdown()
        return 1
    _kill_stale_ui()
    argv, cwd = [str(ui)], str(ROOT / "ui-qt")
    env = dict(os.environ)
    env["SILISTEN_URL"] = f"http://127.0.0.1:{cfg['port']}"
    env["SILISTEN_TOKEN"] = config.token()
    proc = subprocess.Popen(
        argv, cwd=cwd, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    finally:
        if owns_backend:
            httpd.shutdown()
    return 0


def cmd_setup(args):
    from . import setup

    return setup.run(args)


def cmd_models(args):
    from . import models

    cfg = config.load()
    if args.action == "install":
        if not args.kind or not args.name:
            print("usage: silisten models install <speech|romanian|vad|diarization> <name>", file=sys.stderr)
            return 2
        ok = models.install(args.kind, args.name)
        return 0 if ok else 1
    if args.action == "profile":
        if not args.kind:
            print("profiles: " + ", ".join(models.PROFILES), file=sys.stderr)
            return 2
        ok = models.install_profile(cfg, args.kind)
        config.save(cfg)
        print(f"profile '{args.kind}' applied")
        return 0 if ok else 1
    data = models.status(cfg)
    print(f"models in {data['dir']}\n")
    labels = {"speech": "Speech", "romanian": "Romanian", "vad": "Voice detection", "diarization": "Speakers"}
    for kind, rows in labels.items() and ((k, v) for k, v in labels.items()):
        print(f"{rows}:")
        for row in data[kind]:
            mark = "x" if row["installed"] else " "
            current = "  <- in use" if data["current"].get(kind) == row["name"] else ""
            print(f"  [{mark}] {row['name']:<20} {row['note']}{current}")
        print()
    return 0


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
    sub.add_parser("toggle", help="start/stop listening; launches the app if needed")
    shortcut_parser = sub.add_parser("shortcut", help="bind the GNOME shortcut")
    shortcut_parser.add_argument("chord", nargs="?", help="e.g. 'Shift+Tab+Q'")
    setup_parser = sub.add_parser("setup", help="install models, desktop entry and shortcut")
    setup_parser.add_argument("--no-prefetch", action="store_true")
    setup_parser.add_argument("--profile", choices=["best", "balanced", "fast", "minimal"])
    setup_parser.add_argument("--yes", action="store_true", help="accept defaults")
    models_parser = sub.add_parser("models", help="list or install speech models")
    models_parser.add_argument("action", nargs="?", default="list", choices=["list", "install", "profile"])
    models_parser.add_argument("kind", nargs="?")
    models_parser.add_argument("name", nargs="?")
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
    if command == "shortcut":
        return cmd_shortcut(args)
    if command == "setup":
        return cmd_setup(args)
    if command == "models":
        return cmd_models(args)
    if command == "config":
        return cmd_config(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
