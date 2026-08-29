#!/usr/bin/env python3
"""Claude backend adapter. Contract: --cwd --prompt --log --timeout --model;
full read/write inside cwd, exit nonzero on failure, transcript to --log.
Retired from scheduled authority on 2026-08-28; the file stays as history."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

NO_WINDOW = 0x08000000 if os.name == "nt" else 0

def find_claude():
    c = shutil.which("claude")
    if c:
        return c
    for p in [Path.home() / "AppData/Roaming/npm/claude.cmd",
              Path.home() / ".local/bin/claude"]:
        if p.exists():
            return str(p)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--model", default="claude-fable-5")
    a = ap.parse_args()

    exe = find_claude()
    if not exe:
        Path(a.log).write_text("claude CLI not found on PATH", encoding="utf-8")
        sys.exit(2)
    prompt = Path(a.prompt).read_text(encoding="utf-8")
    prompt += f"\n\n(You are running as model {a.model}; sign your work with it.)"
    cmd = [exe, "-p", prompt, "--model", a.model, "--dangerously-skip-permissions"]
    with open(a.log, "w", encoding="utf-8", errors="replace") as log:
        try:
            rc = subprocess.run(cmd, cwd=a.cwd, stdout=log, stderr=subprocess.STDOUT,
                                timeout=a.timeout, creationflags=NO_WINDOW).returncode
        except subprocess.TimeoutExpired:
            log.write("\n[adapter] timeout, killed\n")
            rc = 3
    sys.exit(rc)

if __name__ == "__main__":
    main()
