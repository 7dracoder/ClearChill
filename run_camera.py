#!/usr/bin/env python3
"""
Remote launcher for camera_stream.py on the Raspberry Pi.
Connects via SSH key, copies pi/ files, installs deps, starts the server.
"""

import os
import time
import argparse
import paramiko
from dotenv import load_dotenv

load_dotenv()

PI_HOST     = os.getenv("PI_HOST",     "172.20.10.5")
PI_USER     = os.getenv("PI_USER",     "pi")
PI_PASSWORD = os.getenv("PI_PASSWORD", "")
PI_SSH_KEY  = os.getenv("PI_SSH_KEY",  os.path.expanduser("~/.ssh/id_rsa"))
PI_VENV     = os.getenv("PI_VENV",     "/data/venv")
PI_APP_DIR  = os.getenv("PI_APP_DIR",  "/data/pi")
CAMERA_PORT = int(os.getenv("CAMERA_PORT", "8001"))


def _connect() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_kwargs = {"hostname": PI_HOST, "username": PI_USER, "timeout": 20}
    if PI_SSH_KEY and os.path.exists(PI_SSH_KEY):
        connect_kwargs["key_filename"] = PI_SSH_KEY
        print(f"Connecting to {PI_USER}@{PI_HOST} via key {PI_SSH_KEY}...")
    elif PI_PASSWORD:
        connect_kwargs["password"] = PI_PASSWORD
        print(f"Connecting to {PI_USER}@{PI_HOST} via password...")
    else:
        raise ValueError("No SSH credentials. Set PI_PASSWORD or PI_SSH_KEY in .env")
    client.connect(**connect_kwargs)
    return client


def _run(client, cmd, check=True):
    stdin, stdout, stderr = client.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if check and exit_code != 0 and err:
        print(f"  [stderr] {err}")
    return out


def deploy_files(client):
    """SCP all pi/ files to PI_APP_DIR on the Pi."""
    sftp = client.open_sftp()
    _run(client, f"mkdir -p {PI_APP_DIR}", check=False)

    pi_dir = os.path.join(os.path.dirname(__file__), "pi")
    files = [f for f in os.listdir(pi_dir) if f.endswith(".py")]

    for fname in files:
        local = os.path.join(pi_dir, fname)
        remote = f"{PI_APP_DIR}/{fname}"
        sftp.put(local, remote)
        print(f"  ✓ Copied {fname} → {remote}")

    # Copy .env if it exists locally
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        sftp.put(env_path, f"{PI_APP_DIR}/.env")
        print(f"  ✓ Copied .env → {PI_APP_DIR}/.env")
    else:
        print("  ⚠ No .env found locally — Pi will use defaults")

    sftp.close()


def install_pi_deps(client):
    """Install missing Python packages into the Pi venv."""
    print("Installing Pi dependencies...")
    activate = f"source {PI_VENV}/bin/activate"
    cmd = f"{activate} && pip install requests==2.31.0 httpx==0.27.2 RPi.GPIO==0.7.1 --quiet 2>&1"
    out = _run(client, cmd)
    if out:
        print(f"  {out}")
    print("  ✓ Dependencies installed")


def start_camera_server(client):
    """Kill any existing instance and start a fresh camera server."""
    print("Stopping existing camera_stream processes...")
    _run(client, "pkill -f camera_stream.py", check=False)
    time.sleep(1)

    activate = f"source {PI_VENV}/bin/activate"
    log_file = f"{PI_APP_DIR}/camera.log"
    start_cmd = (
        f"{activate} && cd {PI_APP_DIR} && "
        f"nohup python3 camera_stream.py > {log_file} 2>&1 &"
    )
    print("Starting camera_stream.py...")
    _run(client, start_cmd)
    time.sleep(3)

    proc = _run(client, "pgrep -a python3 | grep camera_stream", check=False)
    if proc:
        print(f"  ✓ Process running: {proc}")
    else:
        print("  ⚠ Process not found — check log below")

    log = _run(client, f"tail -20 {log_file}", check=False)
    print(f"\n--- camera.log ---\n{log}\n---")


def trigger_capture(client):
    """Hit /capture on the Pi to grab a frame and run inference."""
    print(f"\nTriggering capture on http://localhost:{CAMERA_PORT}/capture ...")
    result = _run(client, f"curl -s -X POST http://localhost:{CAMERA_PORT}/capture", check=False)
    print(f"  Response: {result or '(no response)'}")


def main():
    parser = argparse.ArgumentParser(description="Deploy and manage Pi camera server")
    parser.add_argument("--deploy", action="store_true", help="Copy pi/ files to Pi")
    parser.add_argument("--install", action="store_true", help="Install Pi dependencies")
    parser.add_argument("--start", action="store_true", help="Start camera_stream.py")
    parser.add_argument("--capture", action="store_true", help="Trigger a capture after starting")
    parser.add_argument("--all", action="store_true", help="Deploy + install + start (full setup)")
    args = parser.parse_args()

    # Default: --all if no flags given
    if not any([args.deploy, args.install, args.start, args.capture, args.all]):
        args.all = True

    client = _connect()
    try:
        if args.all or args.deploy:
            deploy_files(client)
        if args.all or args.install:
            install_pi_deps(client)
        if args.all or args.start:
            start_camera_server(client)
        if args.capture:
            trigger_capture(client)
    finally:
        client.close()
        print("\nSSH connection closed.")


if __name__ == "__main__":
    main()
