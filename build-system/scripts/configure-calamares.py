#!/usr/bin/env python3
"""
configure-calamares.py — RIDOS-Core 1.0 Nova
Repository: alkinanireyad/RIDOS-Core

All paths are ABSOLUTE — run INSIDE chroot only:
    sudo chroot /path/to/chroot python3 /tmp/configure-calamares.py
"""
import os

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

os.makedirs('/etc/calamares/branding/ridos-core', exist_ok=True)
os.makedirs('/etc/calamares/modules', exist_ok=True)
os.makedirs('/etc/xdg/autostart', exist_ok=True)
os.makedirs('/etc/polkit-1/rules.d', exist_ok=True)

print("[1/12] settings.conf ...")
write('/etc/calamares/settings.conf',
'---\n'
'modules-search: [ local, /usr/lib/calamares/modules ]\n'
'\n'
'sequence:\n'
'  - show:\n'
'      - welcome\n'
'      - locale\n'
'      - keyboard\n'
'      - partition\n'
'      - users\n'
'      - summary\n'
'  - exec:\n'
'      - partition\n'
'      - mount\n'
'      - unpackfs\n'
'      - machineid\n'
'      - fstab\n'
'      - locale\n'
'      - keyboard\n'
'      - localecfg\n'
'      - users\n'
'      - displaymanager\n'
'      - networkcfg\n'
'      - hwclock\n'
'      - grubcfg\n'
'      - bootloader\n'
'      - packages\n'
'      - removeuser\n'
'      - umount\n'
'  - show:\n'
'      - finished\n'
'\n'
'branding: ridos-core\n'
'prompt-install: true\n'
'dont-chroot: false\n'
)

print("[2/12] partition.conf ...")
write('/etc/calamares/modules/partition.conf',
'---\n'
'efiSystemPartition:       "/boot/efi"\n'
'efiSystemPartitionSize:   "512M"\n'
'defaultPartitionTableType: gpt\n'
'availableFileSystemTypes:  [ ext4, btrfs, xfs ]\n'
'initialPartitioningChoice: erase\n'
'initialSwapChoice:         small\n'
'allowManualPartitioning:   true\n'
'showNotEncryptedBootMessage: true\n'
)

print("[3/12] unpackfs.conf ...")
write('/etc/calamares/modules/unpackfs.conf',
'---\n'
'unpack:\n'
'  - source: "/run/live/medium/live/filesystem.squashfs"\n'
'    sourcefs: "squashfs"\n'
'    destination: ""\n'
)

print("[4/12] bootloader.conf ...")
write('/etc/calamares/modules/bootloader.conf',
'---\n'
'efiBootLoader:      "grub"\n'
'kernelLine:         "quiet splash"\n'
'kernelLineRemove:   "rhgb quiet"\n'
'grubInstall:        "grub-install"\n'
'grubMkconfig:       "grub-mkconfig"\n'
'grubCfg:            "/boot/grub/grub.cfg"\n'
'grubProbe:          "grub-probe"\n'
'efiBootloaderId:    "RIDOS-Core"\n'
'installEFIfallback: true\n'
)

print("[5/12] grubcfg.conf ...")
write('/etc/calamares/modules/grubcfg.conf',
'---\n'
'overwrite: false\n'
'updateDistribution: true\n'
)

print("[6/12] users.conf ...")
write('/etc/calamares/modules/users.conf',
'---\n'
'defaultGroups:\n'
'  - sudo\n'
'  - audio\n'
'  - video\n'
'  - netdev\n'
'  - plugdev\n'
'  - bluetooth\n'
'autologinGroup:   autologin\n'
'doAutologin:      false\n'
'sudoersGroup:     sudo\n'
'setRootPassword:  false\n'
'doReusePassword:  true\n'
'passwordRequirements:\n'
'  minLength:     0\n'
'  maxLength:     -1\n'
'  requireUpper:  false\n'
'  requireLower:  false\n'
'  requireNum:    false\n'
'  requireStrong: false\n'
)

print("[7/12] locale.conf ...")
write('/etc/calamares/modules/locale.conf',
'---\n'
'region: "Asia"\n'
'zone:   "Baghdad"\n'
'localeGenPath: "/etc/locale.gen"\n'
'geoipUrl: "https://geoip.kde.org/v2/city"\n'
)

print("[8/12] fstab.conf ...")
# NOTE: umask=0077 is written as a quoted string to avoid Python SyntaxError
# Python 3 does not allow leading zeros in integer literals (0077 is invalid)
write('/etc/calamares/modules/fstab.conf',
'---\n'
'mountOptions:\n'
'  default: defaults\n'
'  btrfs:   defaults,compress=zstd\n'
'  efi:     "umask=0077"\n'
'ssdExtraMountOptions:\n'
'  ext4:  discard\n'
'  btrfs: discard,compress=zstd\n'
'efiMountPoint: "/boot/efi"\n'
)

print("[9/12] displaymanager.conf (GDM + GNOME) ...")
write('/etc/calamares/modules/displaymanager.conf',
'---\n'
'displaymanagers:\n'
'  - gdm\n'
'\n'
'defaultDesktopEnvironment:\n'
'  executable: "gnome-session"\n'
'  desktopFile: "gnome.desktop"\n'
'\n'
'sysconfigSetup: false\n'
)

print("[10/12] packages / removeuser / networkcfg / hwclock / finished ...")
write('/etc/calamares/modules/packages.conf',
'---\n'
'backend: apt\n'
'operations:\n'
'  - remove:\n'
'      - live-boot\n'
'      - live-boot-initramfs-tools\n'
'      - calamares\n'
'      - calamares-data\n'
)

write('/etc/calamares/modules/removeuser.conf',
'---\n'
'username: ridos\n'
)

write('/etc/calamares/modules/networkcfg.conf',
'---\n'
'backend: NetworkManager\n'
)

write('/etc/calamares/modules/hwclock.conf',
'---\n'
'setHardwareClock: true\n'
)

write('/etc/calamares/modules/finished.conf',
'---\n'
'restartNowEnabled: true\n'
'restartNowChecked: true\n'
'restartNowCommand: "systemctl reboot"\n'
)

print("[11/12] polkit rule so Calamares runs without password prompt ...")
write('/etc/polkit-1/rules.d/49-calamares.rules',
'polkit.addRule(function(action, subject) {\n'
'    if (action.id == "org.freedesktop.policykit.exec" &&\n'
'        subject.user == "ridos") {\n'
'        return polkit.Result.YES;\n'
'    }\n'
'});\n'
)

print("[12/12] Calamares autostart (GNOME, 15s delay) ...")
# Uses gnome-terminal so the installer window is always visible
# sleep 15 gives GNOME Shell time to fully load before Calamares launches
write('/etc/xdg/autostart/calamares.desktop',
'[Desktop Entry]\n'
'Type=Application\n'
'Name=Install RIDOS-Core\n'
'GenericName=System Installer\n'
'Comment=Install RIDOS-Core 1.0 Nova to your hard drive\n'
'Exec=sh -c "sleep 15 && sudo /usr/bin/calamares"\n'
'Icon=calamares\n'
'Terminal=false\n'
'X-GNOME-Autostart-enabled=true\n'
'X-GNOME-Autostart-Delay=15\n'
'StartupNotify=false\n'
'Categories=System;\n'
)

print('')
print('=' * 55)
print('  Calamares configured — RIDOS-Core 1.0 Nova')
print('  LUKS encryption available in partition step')
print('  Autostart: 15s after GNOME loads')
print('=' * 55)
