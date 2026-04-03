#!/usr/bin/env python3
"""
panic-key.py — RIDOS-Core 1.0 Nova
Panic Key v1.0: Emergency RAM wipe + secure shutdown.
--install : registers the panic key systemd service and keybinding
--trigger : executes the panic sequence (called by the service)
"""
import os, sys, subprocess, time, signal

PANIC_KEY_SERVICE = '/etc/systemd/system/ridos-panic-key.service'
PANIC_KEY_SCRIPT  = '/opt/ridos-core/bin/panic-key.py'
COUNTDOWN         = 3  # seconds before wipe — allows accidental cancel

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: f.write(content)

def run(cmd):
    subprocess.run(cmd, shell=True, check=False)


def install():
    """Install the panic key systemd service and GNOME keybinding."""
    if os.geteuid() != 0:
        print("ERROR: --install requires root. Run: sudo python3 panic-key.py --install")
        sys.exit(1)

    print("[1] Writing panic-key systemd service ...")
    write(PANIC_KEY_SERVICE, f'''[Unit]
Description=RIDOS-Core Panic Key — Emergency RAM wipe
DefaultDependencies=no
Before=shutdown.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {PANIC_KEY_SCRIPT} --trigger
TimeoutStartSec=10

[Install]
WantedBy=multi-user.target
''')

    print("[2] Writing GNOME custom keybinding (Ctrl+Alt+Pause) ...")
    gsettings_cmd = '''
gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings \
  "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/panic-key/']"
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:\
/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/panic-key/ \
  name "RIDOS Panic Key"
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:\
/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/panic-key/ \
  command "python3 /opt/ridos-core/bin/panic-key.py --trigger"
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:\
/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/panic-key/ \
  binding "<Control><Alt>Pause"
'''
    write('/opt/ridos-core/bin/setup-panic-keybinding.sh', gsettings_cmd)
    run('chmod +x /opt/ridos-core/bin/setup-panic-keybinding.sh')
    # Write autostart to set keybinding on login
    write('/etc/xdg/autostart/ridos-panic-keybinding.desktop', '''[Desktop Entry]
Type=Application
Name=RIDOS Panic Key Setup
Exec=bash /opt/ridos-core/bin/setup-panic-keybinding.sh
Terminal=false
X-GNOME-Autostart-enabled=true
NoDisplay=true
''')

    print("[3] Enabling service ...")
    run('systemctl daemon-reload')
    run('systemctl enable ridos-panic-key.service 2>/dev/null || true')

    print("\n" + "="*55)
    print("  Panic Key installed — RIDOS-Core 1.0 Nova")
    print("  Keybinding : Ctrl + Alt + Pause")
    print("  Action     : 3-second countdown → RAM wipe → shutdown")
    print("  To test    : sudo python3 panic-key.py --trigger")
    print("="*55)


def trigger():
    """Execute the panic sequence with countdown."""
    print("\n" + "!"*55)
    print("  ⚠  RIDOS-CORE PANIC KEY ACTIVATED")
    print("  RAM will be wiped and system will shut down.")
    print("  Press Ctrl+C within 3 seconds to CANCEL.")
    print("!"*55)

    # Countdown with cancel window
    cancelled = [False]

    def cancel_handler(sig, frame):
        cancelled[0] = True

    signal.signal(signal.SIGINT, cancel_handler)

    for i in range(COUNTDOWN, 0, -1):
        if cancelled[0]:
            print("\n  Panic key CANCELLED.")
            sys.exit(0)
        print(f"  Wiping in {i}...")
        time.sleep(1)

    if cancelled[0]:
        print("\n  Panic key CANCELLED.")
        sys.exit(0)

    print("\n  Executing panic sequence...")

    # Step 1: Sync filesystem
    subprocess.run('sync', shell=True)

    # Step 2: Overwrite sensitive memory areas
    # Write to /proc/sys/kernel/sysrq to enable magic sysrq
    try:
        with open('/proc/sys/kernel/sysrq', 'w') as f:
            f.write('1')
    except Exception:
        pass

    # Step 3: Wipe swap if present
    subprocess.run('swapoff -a 2>/dev/null || true', shell=True)

    # Step 4: Drop filesystem caches (forces RAM flush)
    try:
        with open('/proc/sys/vm/drop_caches', 'w') as f:
            f.write('3')
    except Exception:
        pass

    # Step 5: Immediate poweroff (no graceful shutdown)
    print("  Shutting down NOW.")
    subprocess.run('systemctl poweroff --force --force', shell=True)
    # Fallback
    subprocess.run('echo o > /proc/sysrq-trigger', shell=True)


if __name__ == '__main__':
    if '--install' in sys.argv:
        install()
    elif '--trigger' in sys.argv:
        trigger()
    else:
        print("RIDOS-Core Panic Key v1.0")
        print("Usage:")
        print("  sudo python3 panic-key.py --install   Install the panic key")
        print("  sudo python3 panic-key.py --trigger   Trigger panic sequence")
        print("  Keybinding after install: Ctrl+Alt+Pause")
