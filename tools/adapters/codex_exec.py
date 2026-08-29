#!/usr/bin/env python3
"""GPT 5.6 Sol backend adapter (Codex CLI).
Sole operator from 2026-08-28."""
import argparse
import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path

NO_WINDOW = 0x08000000 if os.name == "nt" else 0

def find_codex():
    c = shutil.which("codex")
    if c:
        return c
    p = Path.home() / "AppData/Local/Programs/OpenAI/Codex/bin/codex.exe"
    return str(p) if p.exists() else None


def sandbox_args():
    """Use the OS account boundary only for the installed service identity."""
    if os.name == "nt" and getpass.getuser().casefold() == "census-agent":
        return ["--dangerously-bypass-approvals-and-sandbox"]
    return ["--sandbox", "workspace-write", "-c",
            "sandbox_workspace_write.network_access=true"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--model", default="gpt-5.6-sol")
    a = ap.parse_args()

    exe = find_codex()
    if not exe:
        Path(a.log).write_text("codex CLI not found", encoding="utf-8")
        sys.exit(2)
    prompt = Path(a.prompt).read_text(encoding="utf-8")
    prompt += f"\n\n(You are running as model {a.model}; sign your work with it.)"
    cmd = [exe, "exec", "--cd", a.cwd, *sandbox_args(),
           "--skip-git-repo-check", "-m", a.model, prompt]
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
