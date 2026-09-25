#!/usr/bin/env python3
"""VPS SSH helper for RFUND deployment (local -> remote orchestration).

Usage:
  PYTHONPATH=/home/z/.local/lib/python3.13/site-packages \
  VPS_PASS='...' python3 scripts/vps_ssh.py run  'uptime'
  ... vps_ssh.py put  local_path remote_path
  ... vps_ssh.py get  remote_path local_path
  ... vps_ssh.py putdir local_dir remote_dir

Credentials come from env: VPS_HOST (default 194.5.157.242), VPS_USER (root), VPS_PASS.
NEVER hardcode the password here — this file lives in the repo.
"""
import os
import sys
import stat
import posixpath

import paramiko

HOST = os.environ.get("VPS_HOST", "194.5.157.242")
USER = os.environ.get("VPS_USER", "root")
PASS = os.environ["VPS_PASS"]


def connect() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=25,
                   allow_agent=False, look_for_keys=False)
    return client


def run(client, cmd, timeout=540):
    transport = client.get_transport()
    chan = transport.open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out_buf, err_buf = [], []
    while True:
        if chan.recv_ready():
            out_buf.append(chan.recv(65536))
        if chan.recv_stderr_ready():
            err_buf.append(chan.recv_stderr(65536))
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
    # drain remainder
    while chan.recv_ready():
        out_buf.append(chan.recv(65536))
    while chan.recv_stderr_ready():
        err_buf.append(chan.recv_stderr(65536))
    code = chan.recv_exit_status()
    out = b"".join(out_buf).decode("utf-8", "replace")
    err = b"".join(err_buf).decode("utf-8", "replace")
    return code, out, err


def mkdirs(sftp, path):
    parts = path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}"
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)


def putdir(sftp, local_dir, remote_dir, exclude_names=None):
    exclude_names = set(exclude_names or [])
    mkdirs(sftp, remote_dir)
    count = 0
    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in exclude_names]
        rel = os.path.relpath(root, local_dir)
        rdir = remote_dir if rel == "." else posixpath.join(remote_dir, rel.replace(os.sep, "/"))
        mkdirs(sftp, rdir)
        for f in files:
            if f in exclude_names:
                continue
            lp = os.path.join(root, f)
            rp = posixpath.join(rdir, f)
            sftp.put(lp, rp)
            count += 1
    return count


def main():
    mode = sys.argv[1]
    client = connect()
    try:
        if mode == "run":
            cmd = sys.argv[2]
            code, out, err = run(client, cmd, timeout=int(os.environ.get("VPS_TIMEOUT", "540")))
            if out:
                sys.stdout.write(out)
            if err:
                sys.stdout.write("\n[stderr]\n" + err)
            sys.stdout.write(f"\n[exit {code}]\n")
            sys.exit(code)
        elif mode == "put":
            sftp = client.open_sftp()
            sftp.put(sys.argv[2], sys.argv[3])
            print(f"put {sys.argv[2]} -> {sys.argv[3]}")
        elif mode == "get":
            sftp = client.open_sftp()
            sftp.get(sys.argv[2], sys.argv[3])
            print(f"get {sys.argv[2]} -> {sys.argv[3]}")
        elif mode == "putdir":
            sftp = client.open_sftp()
            n = putdir(sftp, sys.argv[2], sys.argv[3],
                       exclude_names=(os.environ.get("VPS_EXCLUDE", "").split(",") if os.environ.get("VPS_EXCLUDE") else None))
            print(f"uploaded {n} files -> {sys.argv[3]}")
        else:
            print(__doc__)
            sys.exit(2)
    finally:
        client.close()


if __name__ == "__main__":
    main()
