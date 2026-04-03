#!/usr/bin/env python3
"""
install-ridos-files.py — RIDOS-Core 1.0 Nova
Runs on HOST. Installs desktop shortcuts, systemd services, welcome app trigger.
"""
import os, subprocess

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: f.write(content)

def run(cmd):
    subprocess.run(cmd, shell=True, check=False)

print("[1] Directory structure ...")
for d in ['chroot/opt/ridos-core/bin','chroot/opt/ridos-core/data',
          'chroot/opt/ridos-core/logs','chroot/usr/share/ridos-core',
          'chroot/usr/share/applications','chroot/etc/ridos-core']:
    os.makedirs(d, exist_ok=True)

print("[2] Desktop shortcuts ...")
write('chroot/usr/share/applications/ridos-welcome.desktop', '''[Desktop Entry]
Version=1.0
Type=Application
Name=RIDOS-Core Welcome
Comment=Welcome to RIDOS-Core — Install optional tools
Exec=python3 /opt/ridos-core/bin/welcome-app.py
Icon=system-software-install
Terminal=false
Categories=System;
X-GNOME-Autostart-enabled=true
''')
write('chroot/usr/share/applications/install-ridos-core.desktop', '''[Desktop Entry]
Version=1.0
Type=Application
Name=Install RIDOS-Core
Comment=Install RIDOS-Core 1.0 Nova to your hard drive
Exec=pkexec /usr/bin/calamares
Icon=calamares
Terminal=false
Categories=System;
''')

print("[3] Autostart welcome app on first login ...")
os.makedirs('chroot/etc/xdg/autostart', exist_ok=True)
write('chroot/etc/xdg/autostart/ridos-welcome.desktop', '''[Desktop Entry]
Type=Application
Name=RIDOS-Core Welcome
Exec=python3 /opt/ridos-core/bin/welcome-app.py
Icon=system-software-install
Terminal=false
X-GNOME-Autostart-enabled=true
''')

print("[4] Systemd service for RIDOS daemon ...")
write('chroot/etc/systemd/system/ridos-core.service', '''[Unit]
Description=RIDOS-Core Background Daemon
After=network.target

[Service]
Type=simple
User=ridos
ExecStart=/usr/bin/python3 /opt/ridos-core/bin/ai_daemon.py
Restart=on-failure
RestartSec=10
StandardOutput=append:/opt/ridos-core/logs/daemon.log
StandardError=append:/opt/ridos-core/logs/daemon.log

[Install]
WantedBy=multi-user.target
''')

print("[5] Bash profile ...")
write('chroot/home/ridos/.bashrc', '''# RIDOS-Core 1.0 Nova
export PS1='\\[\\033[01;34m\\]ridos@RIDOS-Core\\[\\033[00m\\]:\\[\\033[01;36m\\]\\w\\[\\033[00m\\]\\$ '
export PATH="$PATH:/opt/ridos-core/bin"
alias ll='ls -alF'
alias update='sudo apt-get update && sudo apt-get upgrade'
alias ridos-info='cat /etc/ridos-core/version && cat /etc/ridos-core/neofetch-ascii.txt'
alias tools='python3 /opt/ridos-core/bin/welcome-app.py'
if [ -f /etc/ridos-core/neofetch-ascii.txt ]; then
    cat /etc/ridos-core/neofetch-ascii.txt
fi
''')

print("[6] Permissions ...")
run('chmod -R 755 chroot/opt/ridos-core/bin  2>/dev/null || true')
run('chmod -R 777 chroot/opt/ridos-core/logs 2>/dev/null || true')
run('chown -R 1000:1000 chroot/home/ridos    2>/dev/null || true')

print("\n" + "="*50)
print("  RIDOS-Core files installed")
print("="*50)
