#!/usr/bin/env python3
"""
configure-system.py — RIDOS-Core 1.0 Nova
Configures the base system inside the chroot.
Run INSIDE chroot: sudo chroot /chroot python3 /tmp/configure-system.py
"""
import os, subprocess

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

def run(cmd):
    print(f"  $ {cmd}")
    subprocess.run(cmd, shell=True, check=False)

print("[1] Hostname and hosts ...")
write('/etc/hostname', 'ridos-core\n')
write('/etc/hosts', '127.0.0.1   localhost\n127.0.1.1   ridos-core\n::1         localhost ip6-localhost ip6-loopback\n')

print("[2] Locale and timezone ...")
write('/etc/locale.gen', 'en_US.UTF-8 UTF-8\nar_IQ.UTF-8 UTF-8\n')
run('locale-gen')
write('/etc/default/locale', 'LANG=en_US.UTF-8\n')
run('ln -sf /usr/share/zoneinfo/Asia/Baghdad /etc/localtime')
write('/etc/timezone', 'Asia/Baghdad\n')

print("[3] Creating live user ridos (username=ridos password=ridos) ...")
run('useradd -m -s /bin/bash -G sudo,audio,video,netdev,plugdev ridos 2>/dev/null || true')
run('echo "ridos:ridos" | chpasswd')
run('echo "root:ridos"  | chpasswd')
write('/etc/sudoers.d/ridos', 'ridos ALL=(ALL) NOPASSWD:ALL\n')
run('chmod 440 /etc/sudoers.d/ridos')

print("[4] Enabling services ...")
for svc in ['NetworkManager', 'gdm3', 'bluetooth', 'ssh', 'fwupd', 'tlp']:
    run(f'systemctl enable {svc} 2>/dev/null || true')

print("[5] Configuring GDM — GNOME Wayland default, Xorg fallback ...")
os.makedirs('/etc/gdm3', exist_ok=True)
write('/etc/gdm3/custom.conf', '''[daemon]
WaylandEnable=true
AutomaticLoginEnable=true
AutomaticLogin=ridos

[security]
[xdmcp]
[chooser]
[debug]
''')

print("[6] Flatpak — add Flathub remote ...")
run('flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null || true')

print("[7] Zram configuration ...")
write('/etc/default/zramswap', 'ALGO=zstd\nPERCENT=25\n')

print("[8] Live boot config ...")
os.makedirs('/etc/live/config.conf.d', exist_ok=True)
write('/etc/live/config.conf.d/ridos-core.conf',
      'LIVE_HOSTNAME="ridos-core"\nLIVE_USERNAME="ridos"\nLIVE_USER_FULLNAME="RIDOS-Core Live"\n'
      'LIVE_USER_DEFAULT_GROUPS="audio bluetooth cdrom video plugdev netdev sudo"\n')

print("[9] Disabling apt recommends ...")
write('/etc/apt/apt.conf.d/99norecommends',
      'APT::Install-Recommends "false";\nAPT::Install-Suggests "false";\n')

print("[10] Cleaning apt cache ...")
run('apt-get clean')
run('rm -rf /var/lib/apt/lists/*')

print("\n" + "="*50)
print("  System configured — RIDOS-Core 1.0 Nova")
print("="*50)
