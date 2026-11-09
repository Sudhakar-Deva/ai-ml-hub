"""Capture the raw MCP JSON-RPC exchange with the claims-system server.

    .venv/bin/python week9/wire_capture.py        # -> week9/wire_raw.jsonl

No SDK client and no model: this writes JSON-RPC lines to the server's stdin and
reads its stdout, byte for byte, the way the MCP stdio transport defines it
(one JSON object per line). Each line is saved exactly as it crossed the pipe.
week9/wire.json is these same lines with hand annotations.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "week9" / "wire_raw.jsonl"

MESSAGES = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "wire-capture", "version": "1.0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "get_claim_status", "arguments": {"claim_number": "CLM-2026-10002"}}},
]


def main() -> None:
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", ""),
           "CLAIMS_API_TOKEN": "demo-readonly-token", "FASTMCP_LOG_LEVEL": "WARNING",
           "CLAIMS_SYSTEM_LOG": str(ROOT / "week9" / "claims_system_access.log")}
    proc = subprocess.Popen([sys.executable, "server.py"], cwd=ROOT / "vendor" / "claims_system_mcp",
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, env=env)
    log = []
    for msg in MESSAGES:
        line = json.dumps(msg, separators=(",", ":"))
        proc.stdin.write(line + "\n")
        proc.stdin.flush()
        log.append({"direction": "client -> server", "raw": line})
        if "id" in msg:                       # a request gets exactly one response; a notification none
            reply = proc.stdout.readline().rstrip("\n")
            log.append({"direction": "server -> client", "raw": reply})
    proc.stdin.close()
    proc.wait(timeout=10)
    OUT.write_text("".join(json.dumps(e) + "\n" for e in log))
    for e in log:
        print(f"{e['direction']}: {e['raw']}\n")
    print(f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
