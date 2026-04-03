#!/usr/bin/env python3
"""
apply-branding.py — RIDOS-Core 1.0 Nova
Run INSIDE chroot.
"""
import os, subprocess

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

def run(cmd):
    subprocess.run(cmd, shell=True, check=False)

print("[1] OS release info ...")
write('/etc/os-release', '''PRETTY_NAME="RIDOS-Core 1.0 Nova"
NAME="RIDOS-Core"
VERSION_ID="1.0"
VERSION="1.0 (Nova)"
VERSION_CODENAME=nova
ID=ridos-core
ID_LIKE=debian
HOME_URL="https://github.com/alkinanireyad/RIDOS-Core"
SUPPORT_URL="https://github.com/alkinanireyad/RIDOS-Core/issues"
BUG_REPORT_URL="https://github.com/alkinanireyad/RIDOS-Core/issues"
''')
write('/etc/lsb-release', 'DISTRIB_ID=RIDOS-Core\nDISTRIB_RELEASE=1.0\nDISTRIB_CODENAME=nova\nDISTRIB_DESCRIPTION="RIDOS-Core 1.0 Nova"\n')
write('/etc/issue',     'RIDOS-Core 1.0 Nova \\n \\l\n')
write('/etc/issue.net', 'RIDOS-Core 1.0 Nova\n')

print("[2] Calamares branding ...")
os.makedirs('/etc/calamares/branding/ridos-core', exist_ok=True)
write('/etc/calamares/branding/ridos-core/branding.desc', '''---
componentName: ridos-core
welcomeStyleCalamares: true
welcomeExpandingLogo:  true
strings:
  productName:          "RIDOS-Core"
  version:              "1.0"
  shortVersion:         "1.0"
  versionedName:        "RIDOS-Core 1.0"
  shortVersionedName:   "RIDOS-Core 1.0"
  bootloaderEntryName:  "RIDOS-Core"
  productUrl:           "https://github.com/alkinanireyad/RIDOS-Core"
  supportUrl:           "https://github.com/alkinanireyad/RIDOS-Core/issues"
  releaseNotesUrl:      "https://github.com/alkinanireyad/RIDOS-Core/releases"
images:
  productLogo:    "ridos-core-logo.png"
  productIcon:    "ridos-core-logo.png"
  productWelcome: "ridos-core-welcome.png"
slideshow:    "show.qml"
slideshowAPI: 2
style:
  sidebarBackground:    "#0d1117"
  sidebarText:          "#c9d1d9"
  sidebarTextSelect:    "#ffffff"
  sidebarTextHighlight: "#58a6ff"
''')

write('/etc/calamares/branding/ridos-core/show.qml', '''import QtQuick 2.0
import calamares.slideshow 1.0
Presentation {
    id: presentation
    Slide {
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: "#0d1117" }
        Text {
            anchors.centerIn: parent
            font.pixelSize: 26; color: "#58a6ff"
            text: "RIDOS-Core 1.0 Nova"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom; anchors.bottomMargin: 60
            font.pixelSize: 15; color: "#8b949e"
            text: "Rust-Ready Linux • Built for the next generation"
        }
    }
    Slide {
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: "#0d1117" }
        Text {
            anchors.centerIn: parent; font.pixelSize: 16
            color: "#c9d1d9"; horizontalAlignment: Text.AlignHCenter
            text: "Installing RIDOS-Core to your system...\\nThis may take a few minutes."
        }
    }
    Timer {
        interval: 5000; repeat: true
        running: presentation.activatedInCalamares
        onTriggered: presentation.goToNextSlide()
    }
}
''')

# Minimal PNG placeholder logos
try:
    from PIL import Image, ImageDraw
    def make_logo(path, w, h):
        img = Image.new('RGB', (w, h), '#0d1117')
        d = ImageDraw.Draw(img)
        d.ellipse([w//4, h//4, 3*w//4, 3*h//4], fill='#58a6ff')
        d.text((w//2, h//2), 'R', fill='#ffffff')
        img.save(path)
    make_logo('/etc/calamares/branding/ridos-core/ridos-core-logo.png', 256, 256)
    make_logo('/etc/calamares/branding/ridos-core/ridos-core-welcome.png', 800, 450)
    print("  Branding images created.")
except ImportError:
    import struct, zlib
    def minimal_png(path):
        def chunk(n, d):
            c = zlib.crc32(n+d) & 0xffffffff
            return struct.pack('>I',len(d))+n+d+struct.pack('>I',c)
        png = b'\x89PNG\r\n\x1a\n'
        png += chunk(b'IHDR', struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
        png += chunk(b'IDAT', zlib.compress(b'\x00\x0d\x11\x17'))
        png += chunk(b'IEND', b'')
        open(path,'wb').write(png)
    minimal_png('/etc/calamares/branding/ridos-core/ridos-core-logo.png')
    minimal_png('/etc/calamares/branding/ridos-core/ridos-core-welcome.png')
    print("  Placeholder branding images created.")

print("[3] Version file ...")
os.makedirs('/etc/ridos-core', exist_ok=True)
write('/etc/ridos-core/version',
      'RIDOS_VERSION=1.0.0\nRIDOS_CODENAME=Nova\nRIDOS_KERNEL=6.12-LTS\n'
      'RIDOS_RUST=enabled\nRIDOS_REPO=alkinanireyad/RIDOS-Core\n')

print("[4] Neofetch ASCII ...")
write('/etc/ridos-core/neofetch-ascii.txt', r"""
  ____  _________  ____  _____     ______
 / __ \/  _/ __ \ / __ \/ ___/    / ____/___  ________
/ /_/ // // / / // / / /\__ \    / /   / __ \/ ___/ _ \
\__, // // /_/ // /_/ /___/ /   / /___/ /_/ / /  /  __/
  /_/___/_____/ \____//____/    \____/\____/_/   \___/

  RIDOS-Core 1.0 Nova — Rust-Ready Linux
  github.com/alkinanireyad/RIDOS-Core
""")

print("\n" + "="*50)
print("  Branding applied — RIDOS-Core 1.0 Nova")
print("="*50)
