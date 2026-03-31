import math
import random
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
BOOT_TIME = datetime.now(KST) - timedelta(days=45, hours=3, minutes=22)
NUM_CORES = 8


def _dynamic(base: float, amplitude: float, period: float, noise: float, offset: float = 0) -> float:
    t = time.time()
    return base + amplitude * math.sin(t / period + offset) + random.gauss(0, noise)


def get_system_overview() -> dict:
    cpu_usage = round(max(0, min(100, _dynamic(35, 15, 20, 3))), 1)
    mem_total_gb = 31.3
    mem_used_gb = round(max(1, min(30, _dynamic(16, 4, 60, 1))), 1)
    mem_free_gb = round(mem_total_gb - mem_used_gb, 1)
    disk_total = "500G"
    disk_used_gb = round(_dynamic(200, 5, 300, 1), 1)
    disk_free_gb = round(500 - disk_used_gb, 1)

    return {
        "hostname": "hc-prod-01",
        "os": "Ubuntu 22.04.3 LTS",
        "cpu": {
            "cores": NUM_CORES,
            "model": "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
            "usage": cpu_usage,
        },
        "memory": {
            "total": f"{mem_total_gb}G",
            "used": f"{mem_used_gb}G",
            "free": f"{mem_free_gb}G",
            "usage": round(mem_used_gb / mem_total_gb * 100, 1),
        },
        "disk": {
            "total": disk_total,
            "used": f"{disk_used_gb}G",
            "free": f"{disk_free_gb}G",
            "usage": round(disk_used_gb / 500 * 100, 1),
        },
        "network": {
            "connections": random.randint(80, 200),
            "interfaces": ["lo", "eth0", "docker0", "br-a1b2c3d4"],
        },
        "logins": {
            "total": 3,
            "active": 2,
        },
        "processes": {
            "total": random.randint(180, 220),
            "running": random.randint(2, 8),
        },
        "docker": {
            "version": "24.0.7",
            "containers": 21,
            "images": 35,
            "driver": "overlay2",
            "storage": [
                {"name": "Backing Filesystem", "value": "extfs"},
                {"name": "Data Space Used", "value": "18.2GB"},
                {"name": "Data Space Total", "value": "100GB"},
            ],
        },
    }


def get_cpu_detail() -> dict:
    t = time.time()
    overall = round(max(0, min(100, _dynamic(35, 15, 20, 3))), 1)

    per_core = []
    for i in range(NUM_CORES):
        usage = round(max(0, min(100, _dynamic(30, 20, 15 + i, 5, offset=i * 2))), 1)
        per_core.append({"core": i, "usage": usage})

    return {
        "model": "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
        "cores": NUM_CORES,
        "overall": overall,
        "loadAvg": {
            "avg1": round(max(0, _dynamic(1.5, 0.8, 30, 0.2)), 2),
            "avg5": round(max(0, _dynamic(1.2, 0.5, 60, 0.1)), 2),
            "avg15": round(max(0, _dynamic(1.0, 0.3, 120, 0.05)), 2),
        },
        "perCore": per_core,
    }


def get_network_detail() -> dict:
    t = time.time()
    rx_base = int(_dynamic(500000000, 100000000, 60, 10000000))
    tx_base = int(_dynamic(200000000, 50000000, 60, 5000000))

    return {
        "interfaces": [
            {
                "name": "lo",
                "up": True,
                "mac": "00:00:00:00:00:00",
                "addresses": [
                    {"address": "127.0.0.1", "family": "IPv4"},
                    {"address": "::1", "family": "IPv6"},
                ],
                "speed": None,
                "mtu": None,
            },
            {
                "name": "eth0",
                "up": True,
                "mac": "02:42:ac:11:00:02",
                "addresses": [
                    {"address": "192.168.0.16", "family": "IPv4"},
                    {"address": "fe80::42:acff:fe11:2", "family": "IPv6"},
                ],
                "speed": None,
                "mtu": None,
            },
            {
                "name": "docker0",
                "up": True,
                "mac": "02:42:d8:5e:3a:1f",
                "addresses": [
                    {"address": "172.17.0.1", "family": "IPv4"},
                ],
                "speed": None,
                "mtu": None,
            },
            {
                "name": "br-a1b2c3d4",
                "up": True,
                "mac": "02:42:f0:1a:2b:3c",
                "addresses": [
                    {"address": "172.18.0.1", "family": "IPv4"},
                ],
                "speed": None,
                "mtu": None,
            },
        ],
        "stats": {
            "rx_bytes": max(0, rx_base),
            "tx_bytes": max(0, tx_base),
            "rx_packets": random.randint(300000, 800000),
            "tx_packets": random.randint(200000, 500000),
            "rx_errors": random.randint(0, 5),
            "tx_errors": 0,
        },
        "connections": random.randint(80, 200),
    }


_MOCK_PROCESSES = [
    {"name": "dockerd", "user": "root", "cpu_base": 3.0, "mem_base": 2.5, "vsz": 2500000, "rss": 180000, "status": "S", "command": "/usr/bin/dockerd -H fd://"},
    {"name": "containerd", "user": "root", "cpu_base": 1.5, "mem_base": 1.8, "vsz": 1800000, "rss": 120000, "status": "S", "command": "/usr/bin/containerd"},
    {"name": "postgres", "user": "postgres", "cpu_base": 2.0, "mem_base": 3.0, "vsz": 800000, "rss": 95000, "status": "S", "command": "postgres: writer process"},
    {"name": "nginx", "user": "www-data", "cpu_base": 0.5, "mem_base": 0.3, "vsz": 50000, "rss": 8000, "status": "S", "command": "nginx: worker process"},
    {"name": "python", "user": "root", "cpu_base": 4.0, "mem_base": 4.5, "vsz": 1200000, "rss": 280000, "status": "S", "command": "python manage.py runserver 0.0.0.0:8000"},
    {"name": "node", "user": "node", "cpu_base": 2.5, "mem_base": 3.2, "vsz": 900000, "rss": 150000, "status": "S", "command": "node server.js"},
    {"name": "redis-server", "user": "redis", "cpu_base": 0.8, "mem_base": 0.5, "vsz": 60000, "rss": 12000, "status": "S", "command": "redis-server *:6379"},
    {"name": "celery", "user": "root", "cpu_base": 3.5, "mem_base": 5.0, "vsz": 1400000, "rss": 320000, "status": "S", "command": "celery -A config worker -l info"},
    {"name": "sshd", "user": "root", "cpu_base": 0.1, "mem_base": 0.2, "vsz": 30000, "rss": 5000, "status": "S", "command": "sshd: /usr/sbin/sshd -D"},
    {"name": "systemd", "user": "root", "cpu_base": 0.2, "mem_base": 0.8, "vsz": 200000, "rss": 12000, "status": "S", "command": "/lib/systemd/systemd --system"},
    {"name": "uvicorn", "user": "root", "cpu_base": 2.0, "mem_base": 2.2, "vsz": 700000, "rss": 95000, "status": "S", "command": "uvicorn config.asgi:application --host 0.0.0.0"},
    {"name": "gunicorn", "user": "www-data", "cpu_base": 1.8, "mem_base": 2.0, "vsz": 650000, "rss": 85000, "status": "S", "command": "gunicorn app:app -w 4 -b 0.0.0.0:5000"},
    {"name": "cron", "user": "root", "cpu_base": 0.0, "mem_base": 0.1, "vsz": 8000, "rss": 3000, "status": "S", "command": "/usr/sbin/cron -f"},
    {"name": "containerd-shim", "user": "root", "cpu_base": 0.3, "mem_base": 0.4, "vsz": 120000, "rss": 15000, "status": "S", "command": "containerd-shim-runc-v2 -namespace moby"},
    {"name": "jupyter", "user": "jovyan", "cpu_base": 1.2, "mem_base": 6.0, "vsz": 2000000, "rss": 400000, "status": "S", "command": "jupyter-notebook --no-browser --port=8888"},
    {"name": "daphne", "user": "root", "cpu_base": 0.6, "mem_base": 1.0, "vsz": 350000, "rss": 45000, "status": "S", "command": "daphne -b 0.0.0.0 -p 8001 config.asgi:application"},
    {"name": "prometheus", "user": "nobody", "cpu_base": 1.0, "mem_base": 2.0, "vsz": 500000, "rss": 120000, "status": "S", "command": "/bin/prometheus --config.file=/etc/prometheus/prometheus.yml"},
    {"name": "grafana", "user": "grafana", "cpu_base": 0.8, "mem_base": 1.5, "vsz": 400000, "rss": 90000, "status": "S", "command": "/usr/share/grafana/bin/grafana server"},
    {"name": "bash", "user": "agics", "cpu_base": 0.0, "mem_base": 0.1, "vsz": 25000, "rss": 6000, "status": "S", "command": "-bash"},
    {"name": "tail", "user": "root", "cpu_base": 0.0, "mem_base": 0.0, "vsz": 8000, "rss": 1500, "status": "S", "command": "tail -f /var/log/syslog"},
]


def get_processes() -> dict:
    processes = []
    total_running = 0
    total_sleeping = 0
    total_zombie = 0

    for i, p in enumerate(_MOCK_PROCESSES):
        cpu = round(max(0, p["cpu_base"] + random.gauss(0, 0.5)), 1)
        mem = round(max(0, p["mem_base"] + random.gauss(0, 0.3)), 1)
        status = p["status"]

        if status == "R":
            total_running += 1
        elif status == "Z":
            total_zombie += 1
        else:
            total_sleeping += 1

        processes.append({
            "pid": 1000 + i * 137,
            "name": p["name"],
            "user": p["user"],
            "cpu": cpu,
            "memory": mem,
            "vsz": p["vsz"],
            "rss": p["rss"],
            "tty": "?" if p["user"] != "agics" else "pts/0",
            "status": status,
            "start": "Mar25",
            "time": f"{random.randint(0, 99)}:{random.randint(0, 59):02d}",
            "command": p["command"],
        })

    # Sort by CPU descending, return top 20
    processes.sort(key=lambda x: x["cpu"], reverse=True)
    processes = processes[:20]

    return {
        "processes": processes,
        "totalProcesses": random.randint(180, 220),
        "runningProcesses": max(1, total_running + random.randint(1, 4)),
        "sleepingProcesses": total_sleeping + random.randint(150, 180),
        "zombieProcesses": total_zombie,
    }


def get_logins() -> dict:
    now = datetime.now(KST)
    uptime_seconds = (now - BOOT_TIME).total_seconds()

    return {
        "users": [
            {
                "user": "agics",
                "terminal": "pts/0",
                "host": "192.168.0.100",
                "loginTime": (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"),
                "lastActivity": "N/A",
                "active": True,
                "process": "bash",
            },
            {
                "user": "deploy",
                "terminal": "pts/1",
                "host": "192.168.0.50",
                "loginTime": (now - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M"),
                "lastActivity": "N/A",
                "active": True,
                "process": "bash",
            },
            {
                "user": "root",
                "terminal": "tty1",
                "host": "",
                "loginTime": BOOT_TIME.strftime("%Y-%m-%d %H:%M"),
                "lastActivity": "N/A",
                "active": False,
                "process": "N/A",
            },
        ],
        "totalUsers": 3,
        "activeUsers": 2,
        "uptime": int(uptime_seconds),
        "lastBoot": BOOT_TIME.strftime("%Y-%m-%d %H:%M:%S"),
    }
