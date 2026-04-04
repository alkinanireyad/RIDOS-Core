#!/usr/bin/env python3
"""
configure-calamares.py — RIDOS-Core 1.0 Nova
All paths are ABSOLUTE — run INSIDE chroot only.
Includes LUKS full-disk encryption option.
"""
import os

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

os.makedirs('/etc/calamares/branding/ridos-core', exist_ok=True)
os.makedirs('/etc/calamares/modules', exist_ok=True)
os.makedirs('/etc/xdg/autostart', exist_ok=True)

print("[1/11] settings.conf ...")
write('/etc/calamares/settings.conf', '''---
modules-search: [ local, /usr/lib/calamares/modules ]

sequence:
  - show:
      - welcome
      - locale
      - keyboard
      - partition
      - users
      - summary
  - exec:
      - partition
      - mount
      - unpackfs
      - machineid
      - fstab
      - locale
      - keyboard
      - localecfg
      - users
      - displaymanager
      - networkcfg
      - hwclock
      - grubcfg
      - bootloader
      - packages
      - removeuser
      - umount
  - show:
      - finished

branding: ridos-core
prompt-install: true
dont-chroot: false
''')

print("[2/11] partition.conf (with LUKS encryption support) ...")
/etc/calamares/modules/partition.conf', '''---
efiSystemPartition:       "/boot/efi"
efiSystemPartitionSize:   "512M"
defaultPartitionTableType: gpt
availableFileSystemTypes:  [ ext4, btrfs, xfs ]
initialPartitioningChoice: erase
initialSwapChoice:         small
allowManualPartitioning:   true
showNotEncryptedBootMessage: true
''')

print("[3/11] unpackfs.conf ...")
write('/etc/calamares/modules/unpackfs.conf', '''---
unpack:
  - source: "/run/live/medium/live/filesystem.squashfs"
    sourcefs: "squashfs"
    destination: ""
''')

print("[4/11] bootloader.conf ...")
write('/etc/calamares/modules/bootloader.conf', '''---
efiBootLoader:      "grub"
kernelLine:         "quiet splash"
kernelLineRemove:   "rhgb quiet"
grubInstall:        "grub-install"
grubMkconfig:       "grub-mkconfig"
grubCfg:            "/boot/grub/grub.cfg"
grubProbe:          "grub-probe"
efiBootloaderId:    "RIDOS-Core"
installEFIfallback: true
''')

print("[5/11] grubcfg.conf ...")
write('/etc/calamares/modules/grubcfg.conf', '''---
overwrite: false
updateDistribution: true
''')

print("[6/11] users.conf ...")
write('/etc/calamares/modules/users.conf', '''---
defaultGroups:
  - sudo
  - audio
  - video
  - netdev
  - plugdev
  - bluetooth
autologinGroup:   autologin
doAutologin:      false
sudoersGroup:     sudo
setRootPassword:  false
doReusePassword:  true
passwordRequirements:
  minLength:     0
  maxLength:     -1
  requireUpper:  false
  requireLower:  false
  requireNum:    false
  requireStrong: false
''')

print("[7/11] locale.conf ...")
write('/etc/calamares/modules/locale.conf', '''---
region: "Asia"
zone:   "Baghdad"
localeGenPath: "/etc/locale.gen"
geoipUrl: "https://geoip.kde.org/v2/city"
''')

print("[8/11] displaymanager.conf (GDM + GNOME Wayland) ...")
write('/etc/calamares/modules/displaymanager.conf', '''---
displaymanagers:
  - gdm

defaultDesktopEnvironment:
  executable: "gnome-session"
  desktopFile: "gnome-wayland.desktop"

sysconfigSetup: false
''')

print("[9/11] fstab / hwclock / networkcfg / finished / removeuser ...")
write('/etc/calamares/modules/fstab.conf', '''---
mountOptions:
  default: defaults
  btrfs:   defaults,compress=zstd
  efi:     "umask=0077"
efiMountPoint: "/boot/efi"
''')
write('/etc/calamares/modules/hwclock.conf',    '---\nsetHardwareClock: true\n')
write('/etc/calamares/modules/networkcfg.conf', '---\nbackend: NetworkManager\n')
write('/etc/calamares/modules/removeuser.conf', '---\nusername: ridos\n')
write('/etc/calamares/modules/finished.conf', '''---
restartNowEnabled: true
restartNowChecked: true
restartNowCommand: "systemctl reboot"
''')

print("[10/11] packages.conf (remove live packages after install) ...")
write('/etc/calamares/modules/packages.conf', '''---
backend: apt
operations:
  - remove:
      - live-boot
      - live-boot-initramfs-tools
      - calamares
      - calamares-data
''')

print("[11/11] Calamares autostart desktop entry ...")
# Autostart via gnome-terminal so it's always visible
write('/etc/xdg/autostart/calamares.desktop', '''[Desktop Entry]
Type=Application
Name=Install RIDOS-Core
Exec=sh -c "sleep 15 && sudo /usr/bin/calamares"
Icon=calamares
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=15
''')

# Also write a polkit rule so calamares can run without password prompt
os.makedirs('/etc/polkit-1/rules.d', exist_ok=True)
write('/etc/polkit-1/rules.d/49-calamares.rules', '''polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.policykit.exec" &&
        subject.user == "ridos") {
        return polkit.Result.YES;
    }
});
''')

print("\n" + "="*55)
print("  Calamares configured — RIDOS-Core 1.0 Nova")
print("  LUKS encryption available in partition step")
print("="*55)
