#!/usr/bin/env python3
"""
ai_daemon.py — RIDOS-Core 1.0 Nova
Background health monitor daemon.
"""
import os, sys, time, logging
from datetime import datetime

LOG_PATH = '/opt/ridos-core/logs/daemon.log'
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [RIDOS-Core] %(levelname)s: %(message)s',
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('ridos-core')

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    log.warning("psutil not available — install with: pip3 install psutil")

CPU_WARN = 85.0; RAM_WARN = 85.0; DISK_WARN = 90.0
CHECK_INTERVAL = 60

def check():
    if not HAS_PSUTIL:
        return []
    alerts = []
    cpu = psutil.cpu_percent(interval=2)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    if cpu  > CPU_WARN:  alerts.append(f"HIGH CPU {cpu}%")
    if mem.percent > RAM_WARN:  alerts.append(f"HIGH RAM {mem.percent}%")
    if disk.percent > DISK_WARN: alerts.append(f"HIGH DISK {disk.percent}%")
    return alerts

log.info("RIDOS-Core daemon starting — v1.0 Nova")
while True:
    try:
        alerts = check()
        if alerts:
            for a in alerts: log.warning(a)
        else:
            log.info("System healthy.")
    except Exception as e:
        log.error(f"Check error: {e}")
    time.sleep(CHECK_INTERVAL)
