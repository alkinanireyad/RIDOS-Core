#!/usr/bin/env python3
"""
configure-calamares.py — RIDOS-Core 1.0 Nova
FIXED version — correct Calamares paths and complete module configs.
Run INSIDE chroot: sudo chroot /chroot python3 /tmp/configure-calamares.py
"""
import os, subprocess

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

def run(cmd):
    subprocess.run(cmd, shell=True, check=False)

# ── Correct Calamares paths ───────────────────────────────────────────────────
# /etc/calamares/     = main config (settings.conf)
# /usr/share/calamares/branding/ = branding (ChatGPT was right about this)
# /usr/share/calamares/modules/  = module defaults (already exist from package)
# /etc/calamares/modules/        = our custom module overrides

for d in [
    '/etc/calamares/modules',
    '/usr/share/calamares/branding/ridos-core',
    '/etc/xdg/autostart',
    '/etc/polkit-1/rules.d',
]:
    os.makedirs(d, exist_ok=True)

print("[1/15] settings.conf ...")
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

# ── BRANDING — correct path is /usr/share/calamares/branding/ ─────────────────
print("[2/15] branding.desc (FIXED path: /usr/share/calamares/branding/) ...")
write('/usr/share/calamares/branding/ridos-core/branding.desc',
    '---\n'
    'componentName: ridos-core\n'
    'welcomeStyleCalamares: true\n'
    'welcomeExpandingLogo:  true\n'
    'strings:\n'
    '  productName:          "RIDOS-Core"\n'
    '  shortProductName:     "RIDOS"\n'
    '  version:              "1.0"\n'
    '  shortVersion:         "1.0"\n'
    '  versionedName:        "RIDOS-Core 1.0"\n'
    '  shortVersionedName:   "RIDOS-Core 1.0"\n'
    '  bootloaderEntryName:  "RIDOS-Core"\n'
    '  productUrl:           "https://github.com/alkinanireyad/RIDOS-Core"\n'
    '  supportUrl:           "https://github.com/alkinanireyad/RIDOS-Core/issues"\n'
    '  releaseNotesUrl:      "https://github.com/alkinanireyad/RIDOS-Core/releases"\n'
    'images:\n'
    '  productLogo:    "ridos-core-logo.png"\n'
    '  productIcon:    "ridos-core-logo.png"\n'
    '  productWelcome: "ridos-core-welcome.png"\n'
    'slideshow:    "show.qml"\n'
    'slideshowAPI: 2\n'
    'style:\n'
    '  sidebarBackground:    "#0D1117"\n'
    '  sidebarText:          "#C9D1D9"\n'
    '  sidebarTextSelect:    "#FFFFFF"\n'
    '  sidebarTextHighlight: "#1F6FEB"\n'
)

# Minimal QML slideshow
write('/usr/share/calamares/branding/ridos-core/show.qml',
    'import QtQuick 2.0\n'
    'import calamares.slideshow 1.0\n'
    'Presentation {\n'
    '    id: presentation\n'
    '    Slide {\n'
    '        anchors.fill: parent\n'
    '        Rectangle { anchors.fill: parent; color: "#0D1117" }\n'
    '        Text {\n'
    '            anchors.centerIn: parent\n'
    '            font.pixelSize: 26\n'
    '            color: "#1F6FEB"\n'
    '            text: "Installing RIDOS-Core 1.0 Nova..."\n'
    '        }\n'
    '    }\n'
    '    Timer {\n'
    '        interval: 5000; repeat: true\n'
    '        running: presentation.activatedInCalamares\n'
    '        onTriggered: presentation.goToNextSlide()\n'
    '    }\n'
    '}\n'
)

# Placeholder logo PNG (apply-branding.py will overwrite with real images)
try:
    import struct, zlib
    def tiny_png(path, r, g, b):
        def chunk(n, d):
            c = zlib.crc32(n + d) & 0xffffffff
            return struct.pack('>I', len(d)) + n + d + struct.pack('>I', c)
        png  = b'\x89PNG\r\n\x1a\n'
        png += chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
        png += chunk(b'IDAT', zlib.compress(b'\x00' + bytes([r, g, b])))
        png += chunk(b'IEND', b'')
        open(path, 'wb').write(png)
    tiny_png('/usr/share/calamares/branding/ridos-core/ridos-core-logo.png',    13, 17, 23)
    tiny_png('/usr/share/calamares/branding/ridos-core/ridos-core-welcome.png', 13, 17, 23)
except Exception as e:
    print('  Placeholder PNG skipped:', e)

# ── MODULE CONFIGS ────────────────────────────────────────────────────────────
print("[3/15] welcome.conf ...")
write('/etc/calamares/modules/welcome.conf',
    '---\n'
    'showSupportUrl:        true\n'
    'showKnownIssuesUrl:    true\n'
    'showReleaseNotesUrl:   false\n'
    'requirements:\n'
    '  requiredStorage:     10\n'
    '  requiredRam:         1.0\n'
    '  check:\n'
    '    - storage\n'
    '    - ram\n'
    '    - power\n'
    '    - internet\n'
    '  required:\n'
    '    - storage\n'
    '    - ram\n'
)

print("[4/15] locale.conf ...")
write('/etc/calamares/modules/locale.conf',
    '---\n'
    'region: "Asia"\n'
    'zone:   "Baghdad"\n'
    'localeGenPath: "/etc/locale.gen"\n'
    'geoipUrl: "https://geoip.kde.org/v2/city"\n'
)

print("[5/15] keyboard.conf ...")
write('/etc/calamares/modules/keyboard.conf',
    '---\n'
    'convertedKeymapPath: "/lib/kbd/keymaps/xkb"\n'
    'writeEtcDefaultKeyboard: true\n'
)

print("[6/15] partition.conf (LUKS ready) ...")
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

print("[7/15] unpackfs.conf ...")
# Debian live-boot path — verified for our ISO structure
write('/etc/calamares/modules/unpackfs.conf',
    '---\n'
    'unpack:\n'
    '  - source: "/run/live/medium/live/filesystem.squashfs"\n'
    '    sourcefs: "squashfs"\n'
    '    destination: ""\n'
)

print("[8/15] mount.conf ...")
write('/etc/calamares/modules/mount.conf',
    '---\n'
    'btrfsSubvolumes:\n'
    '  - mountPoint: /\n'
    '    subvolume: /@\n'
    '  - mountPoint: /home\n'
    '    subvolume: /@home\n'
    'mountOptions:\n'
    '  btrfs: defaults,compress=zstd,noatime\n'
)

print("[9/15] machineid.conf ...")
write('/etc/calamares/modules/machineid.conf',
    '---\n'
    'systemd: true\n'
    'dbus: true\n'
    'symlink: false\n'
)

print("[10/15] fstab.conf ...")
# umask=0077 as QUOTED STRING — avoids Python 3 SyntaxError with leading zeros
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

print("[11/15] users.conf ...")
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

print("[12/15] displaymanager.conf ...")
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

print("[13/15] bootloader / grubcfg / networkcfg / hwclock / removeuser / finished ...")
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
write('/etc/calamares/modules/grubcfg.conf',
    '---\n'
    'overwrite: false\n'
    'updateDistribution: true\n'
)
write('/etc/calamares/modules/networkcfg.conf', '---\nbackend: NetworkManager\n')
write('/etc/calamares/modules/hwclock.conf',    '---\nsetHardwareClock: true\n')
write('/etc/calamares/modules/removeuser.conf', '---\nusername: ridos\n')
write('/etc/calamares/modules/finished.conf',
    '---\n'
    'restartNowEnabled: true\n'
    'restartNowChecked: true\n'
    'restartNowCommand: "systemctl reboot"\n'
)

print("[14/15] packages.conf — apt backend (Debian-based OS) ...")
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

print("[15/15] polkit rule + autostart ...")
# polkit rule — lets ridos user run Calamares without password prompt
write('/etc/polkit-1/rules.d/49-calamares.rules',
    'polkit.addRule(function(action, subject) {\n'
    '    if (action.id == "org.freedesktop.policykit.exec" &&\n'
    '        subject.user == "ridos") {\n'
    '        return polkit.Result.YES;\n'
    '    }\n'
    '});\n'
)

# Autostart — sleep 15 gives GNOME + polkit agent time to fully load
# Uses direct calamares binary (no pkexec) because polkit rule above allows it
write('/etc/xdg/autostart/calamares.desktop',
    '[Desktop Entry]\n'
    'Type=Application\n'
    'Name=Install RIDOS-Core\n'
    'GenericName=System Installer\n'
    'Comment=Install RIDOS-Core 1.0 Nova\n'
    'Exec=bash -c "sleep 15 && /usr/bin/calamares"\n'
    'Icon=calamares\n'
    'Terminal=false\n'
    'X-GNOME-Autostart-enabled=true\n'
    'X-GNOME-Autostart-Delay=15\n'
    'StartupNotify=true\n'
    'Categories=System;\n'
)

# Verify Calamares binary exists
if os.path.exists('/usr/bin/calamares'):
    print('  Calamares binary: FOUND at /usr/bin/calamares')
else:
    print('  WARNING: /usr/bin/calamares NOT FOUND — install calamares package')

# Verify branding path
if os.path.exists('/usr/share/calamares/branding/ridos-core/branding.desc'):
    print('  Branding: FOUND at /usr/share/calamares/branding/ridos-core/')
else:
    print('  WARNING: branding.desc not found')

print('')
print('=' * 60)
print('  Calamares fully configured — RIDOS-Core 1.0 Nova')
print('  Branding path: /usr/share/calamares/branding/ridos-core/')
print('  Autostart:     sleep 15 then /usr/bin/calamares')
print('  polkit rule:   passwordless for ridos user')
print('=' * 60)
