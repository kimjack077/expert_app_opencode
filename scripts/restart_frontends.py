#!/usr/bin/env python3
import socket
import time
import urllib.request

import paramiko

HOST = "49.232.213.79"
REMOTE = "/home/ubuntu/expert_app"
PASSWORD = "1234567890@sdtj"


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sock = socket.socket()
    sock.settimeout(60)
    sock.connect((HOST, 22))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    transport = paramiko.Transport(sock)
    transport.set_keepalive(30)
    transport.start_client(timeout=60)
    transport.auth_password("ubuntu", PASSWORD)
    ssh._transport = transport

    script = f"""
set -e
cd {REMOTE}/h5-app && npm run build
for name_port in web-admin:3000 h5-app:5173; do
  name=${{name_port%%:*}}
  port=${{name_port##*:}}
  if [ -f {REMOTE}/$name.pid ]; then
    pid=$(cat {REMOTE}/$name.pid || true)
    if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; fi
    rm -f {REMOTE}/$name.pid
  fi
  if command -v fuser >/dev/null 2>&1; then fuser -k $port/tcp >/dev/null 2>&1 || true; fi
done
cd {REMOTE}/web-admin
nohup npx vite preview --host 0.0.0.0 --port 3000 > {REMOTE}/web-admin.log 2>&1 < /dev/null &
echo $! > {REMOTE}/web-admin.pid
cd {REMOTE}/h5-app
nohup npx vite preview --host 0.0.0.0 --port 5173 > {REMOTE}/h5-app.log 2>&1 < /dev/null &
echo $! > {REMOTE}/h5-app.pid
sleep 2
echo web_pid=$(cat {REMOTE}/web-admin.pid)
echo h5_pid=$(cat {REMOTE}/h5-app.pid)
ss -lntp | grep -E ':3000|:5173' || netstat -lntp 2>/dev/null | grep -E ':3000|:5173' || true
"""
    print("running remote restart...")
    _i, stdout, stderr = ssh.exec_command(script, timeout=60)
    print(stdout.read().decode("utf-8", errors="replace"))
    print(stderr.read().decode("utf-8", errors="replace"))
    time.sleep(2)
    for url in [
        "http://49.232.213.79:3000/",
        "http://49.232.213.79:5173/h5/",
        "http://49.232.213.79:8000/api/health",
    ]:
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                print(url, r.status)
        except Exception as exc:
            print(url, "ERR", exc)
    ssh.close()


if __name__ == "__main__":
    main()
