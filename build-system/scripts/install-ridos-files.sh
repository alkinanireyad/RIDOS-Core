#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# install-ridos-files.sh — RIDOS-Core 1.0 Nova
# Repo location: build-system/scripts/install-ridos-files.sh
# Called by build-iso.yml: sudo bash build-system/scripts/install-ridos-files.sh
# Runs on HOST. Uses chroot/ prefix for all target paths.
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "=== Installing RIDOS-Core files ==="

# ── Directories ───────────────────────────────────────────────────────────────
mkdir -p chroot/opt/ridos-core/bin
mkdir -p chroot/opt/ridos-core/logs
mkdir -p chroot/usr/share/ridos-core
mkdir -p chroot/usr/local/bin
mkdir -p chroot/home/ridos/Desktop
mkdir -p chroot/home/ridos/.config/autostart
mkdir -p chroot/etc/xdg/autostart
mkdir -p chroot/usr/share/glib-2.0/schemas
mkdir -p chroot/etc/dconf/db/local.d
mkdir -p chroot/etc/dconf/profile

# ── Copy Python scripts ───────────────────────────────────────────────────────
cp ridos-core/*.py chroot/opt/ridos-core/bin/
echo "Copied files:"
ls -lh chroot/opt/ridos-core/bin/

# Verify installer
if [ ! -f chroot/opt/ridos-core/bin/ridos-installer.py ]; then
  echo "ERROR: ridos-installer.py missing from ridos-core/"
  exit 1
fi
echo "ridos-installer.py: OK"

# ── Extras and legal ──────────────────────────────────────────────────────────
cp extras/install-ollama.sh chroot/opt/ridos-core/bin/ 2>/dev/null || true
cp extras/panic-key.py      chroot/opt/ridos-core/bin/ 2>/dev/null || true
chmod +x chroot/opt/ridos-core/bin/*.py 2>/dev/null || true
chmod +x chroot/opt/ridos-core/bin/*.sh 2>/dev/null || true
cp legal/LICENSE.txt legal/COPYRIGHT legal/CONTRIBUTORS.md \
   chroot/usr/share/ridos-core/ 2>/dev/null || true

# ── Global ridos-help command ─────────────────────────────────────────────────
cat > chroot/usr/local/bin/ridos-help << 'EOF'
#!/bin/bash
python3 /opt/ridos-core/bin/ridos-help.py "$@"
EOF
chmod +x chroot/usr/local/bin/ridos-help

# ── Install GNOME desktop-icons extension (needs mounts) ─────────────────────
echo "Installing GNOME desktop icons extension..."
sudo mount --bind /dev  chroot/dev
sudo mount --bind /proc chroot/proc
sudo mount --bind /sys  chroot/sys

sudo chroot chroot apt-get install -y gnome-shell-extension-desktop-icons 2>/dev/null \
  || sudo chroot chroot apt-get install -y gnome-shell-extension-desktop-icons-ng 2>/dev/null \
  || echo "WARNING: desktop-icons extension not found in repos"

# Also install GNOME tweaks for user to manage extensions
sudo chroot chroot apt-get install -y gnome-tweaks 2>/dev/null || true

# Compile glib schemas
sudo chroot chroot glib-compile-schemas /usr/share/glib-2.0/schemas/ 2>/dev/null || true

sudo umount chroot/sys  || true
sudo umount chroot/proc || true
sudo umount chroot/dev  || true

# ── GNOME system-wide dconf defaults ─────────────────────────────────────────
# Sets desktop icons on, enables extensions, sets dock favorites
cat > chroot/etc/dconf/db/local.d/01-ridos << 'DCONF'
[org/gnome/shell]
enabled-extensions=['desktop-icons@csoriano', 'desktop-icons-ng@csoriano']
favorite-apps=['brave-browser.desktop', 'org.gnome.Terminal.desktop', 'org.gnome.Nautilus.desktop', 'org.gnome.Software.desktop']

[org/gnome/desktop/background]
show-desktop-icons=true

[org/gnome/nautilus/desktop]
home-icon-visible=false
trash-icon-visible=true

[org/gnome/desktop/interface]
clock-show-date=true
show-battery-percentage=true
DCONF

cat > chroot/etc/dconf/profile/user << 'DCONF'
user-db:user
system-db:local
DCONF

# Compile dconf database
chroot chroot dconf update 2>/dev/null || true

# ── GLib schema override (belt + suspenders) ──────────────────────────────────
cat > chroot/usr/share/glib-2.0/schemas/99-ridos-desktop.gschema.override << 'SCHEMA'
[org.gnome.desktop.background]
show-desktop-icons=true

[org.gnome.nautilus.desktop]
home-icon-visible=false
trash-icon-visible=true
SCHEMA
chroot chroot glib-compile-schemas /usr/share/glib-2.0/schemas/ 2>/dev/null || true

# ── Autostart: ridos-welcome ONLY ────────────────────────────────────────────
# The welcome app autostarts 5s after login.
# It has an "Install to HDD" tab — no separate installer popup needed.
# Installer is still launchable from the desktop shortcut.

# Remove old installer autostart if it exists from a previous build
rm -f chroot/etc/xdg/autostart/ridos-installer.desktop
rm -f chroot/home/ridos/.config/autostart/ridos-installer.desktop

cat > chroot/etc/xdg/autostart/ridos-welcome.desktop << 'AUTOSTART'
[Desktop Entry]
Type=Application
Name=RIDOS-Core Welcome
Comment=Welcome to RIDOS-Core 1.0 Nova
Exec=bash -c "sleep 5 && /opt/ridos-core/bin/ridos-welcome"
Icon=system-software-install
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
StartupNotify=false
NotShowIn=KDE;
AUTOSTART

# ── Desktop shortcuts ─────────────────────────────────────────────────────────
cat > chroot/home/ridos/Desktop/install-ridos-core.desktop << 'DESK'
[Desktop Entry]
Version=1.0
Type=Application
Name=Install RIDOS-Core
GenericName=System Installer
Comment=Install RIDOS-Core 1.0 Nova to your hard drive
Exec=gnome-terminal --title=RIDOS-Installer -- bash -c "sudo python3 /opt/ridos-core/bin/ridos-installer.py; exec bash"
Icon=system-software-install
Terminal=false
Categories=System;
StartupNotify=true
DESK

cat > chroot/home/ridos/Desktop/brave-browser.desktop << 'DESK'
[Desktop Entry]
Version=1.0
Type=Application
Name=Brave Browser
Comment=Fast, private browser
Exec=brave-browser %U
Icon=brave-browser
Terminal=false
Categories=Network;WebBrowser;
DESK

cat > chroot/home/ridos/Desktop/ridos-tools.desktop << 'DESK'
[Desktop Entry]
Version=1.0
Type=Application
Name=RIDOS-Core IT Tools
Comment=Pro IT toolkit
Exec=gnome-terminal -- bash -c "python3 /opt/ridos-core/bin/ridos_shell.py; exec bash"
Icon=utilities-terminal
Terminal=false
Categories=System;
DESK

cat > chroot/home/ridos/Desktop/ridos-help.desktop << 'DESK'
[Desktop Entry]
Version=1.0
Type=Application
Name=RIDOS-Core Help
Comment=Help for beginners and pro users
Exec=gnome-terminal -- bash -c "ridos-help; exec bash"
Icon=help-browser
Terminal=false
Categories=System;
DESK

# RIDOS-Core Welcome — launches the Rust/GTK4 binary
# Falls back to welcome-app.py if binary not yet compiled
cat > chroot/home/ridos/Desktop/ridos-welcome.desktop << 'DESK'
[Desktop Entry]
Version=1.0
Type=Application
Name=RIDOS-Core Welcome
Comment=System info, optional tools, about and HDD installer
Exec=bash -c "/opt/ridos-core/bin/ridos-welcome 2>/dev/null || python3 /opt/ridos-core/bin/welcome-app.py"
Icon=system-software-install
Terminal=false
Categories=System;
DESK

# ── Permissions ───────────────────────────────────────────────────────────────
chmod +x chroot/home/ridos/Desktop/*.desktop
chown -R 1000:1000 chroot/home/ridos
chmod -R 755 chroot/opt/ridos-core/bin
chmod -R 777 chroot/opt/ridos-core/logs

# ── Verification ──────────────────────────────────────────────────────────────
echo ""
echo "=== Verification ==="
echo "Installer:"
ls -lh chroot/opt/ridos-core/bin/ridos-installer.py
echo "Desktop shortcuts:"
ls -la chroot/home/ridos/Desktop/
echo "Autostart (system only — no duplicate):"
ls -la chroot/etc/xdg/autostart/
echo ""
echo "=== install-ridos-files.sh complete ==="
echo "    ONE autostart entry (no duplicate popup)"
echo "    Desktop icons extension installed"
echo "    dconf defaults set for GNOME"
echo "    5 desktop shortcuts created"
