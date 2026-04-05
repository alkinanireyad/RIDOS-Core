#!/bin/bash
# install-ridos-files.sh
# Called by build-iso.yml to install all RIDOS files and configure GNOME
# Run on HOST (not chroot) from repo root

set -e

echo "=== Installing RIDOS-Core files ==="

mkdir -p chroot/opt/ridos-core/bin
mkdir -p chroot/opt/ridos-core/logs
mkdir -p chroot/usr/share/ridos-core
mkdir -p chroot/home/ridos/Desktop
mkdir -p chroot/etc/xdg/autostart
mkdir -p chroot/home/ridos/.config/autostart
mkdir -p chroot/usr/share/glib-2.0/schemas

# Copy all scripts from repo
cp ridos-core/*.py chroot/opt/ridos-core/bin/
echo "Files copied:"
ls -lh chroot/opt/ridos-core/bin/

# Verify installer exists
if [ ! -f chroot/opt/ridos-core/bin/ridos-installer.py ]; then
  echo "ERROR: ridos-installer.py not found in ridos-core/"
  exit 1
fi
echo "ridos-installer.py: OK"

cp extras/install-ollama.sh chroot/opt/ridos-core/bin/ 2>/dev/null || true
cp extras/panic-key.py      chroot/opt/ridos-core/bin/ 2>/dev/null || true
chmod +x chroot/opt/ridos-core/bin/*.py 2>/dev/null || true
chmod +x chroot/opt/ridos-core/bin/*.sh 2>/dev/null || true

cp legal/LICENSE.txt legal/COPYRIGHT legal/CONTRIBUTORS.md \
   chroot/usr/share/ridos-core/ 2>/dev/null || true

# Global ridos-help command
printf '#!/bin/bash\npython3 /opt/ridos-core/bin/ridos-help.py "$@"\n' \
  > chroot/usr/local/bin/ridos-help
chmod +x chroot/usr/local/bin/ridos-help

# GNOME schema to enable desktop icons
cat > chroot/usr/share/glib-2.0/schemas/99-ridos-desktop.gschema.override << 'SCHEMA'
[org.gnome.desktop.background]
show-desktop-icons=true
SCHEMA

# Install gnome-shell-extension-desktop-icons if available
chroot chroot apt-get install -y gnome-shell-extension-desktop-icons 2>/dev/null \
  || chroot chroot apt-get install -y gnome-shell-extension-desktop-icons-ng 2>/dev/null || true

# Compile schemas
chroot chroot glib-compile-schemas /usr/share/glib-2.0/schemas/ 2>/dev/null || true

# Autostart installer — written to BOTH system and user autostart locations
for DEST in \
  chroot/etc/xdg/autostart/ridos-installer.desktop \
  chroot/home/ridos/.config/autostart/ridos-installer.desktop
do
  cat > "$DEST" << 'AUTOSTART'
[Desktop Entry]
Type=Application
Name=RIDOS-Core Installer
Comment=Install RIDOS-Core to your hard drive
Exec=bash -c "sleep 10 && gnome-terminal --title=Install-RIDOS-Core -- bash -c 'sudo python3 /opt/ridos-core/bin/ridos-installer.py; exec bash'"
Icon=system-software-install
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=10
StartupNotify=false
AUTOSTART
done

# Desktop shortcuts
cat > chroot/home/ridos/Desktop/install-ridos-core.desktop << 'DESK'
[Desktop Entry]
Version=1.0
Type=Application
Name=Install RIDOS-Core
Comment=Install RIDOS-Core 1.0 Nova to your hard drive
Exec=gnome-terminal --title=Install-RIDOS-Core -- bash -c "sudo python3 /opt/ridos-core/bin/ridos-installer.py; exec bash"
Icon=system-software-install
Terminal=false
Categories=System;
DESK

cat > chroot/home/ridos/Desktop/brave-browser.desktop << 'DESK'
[Desktop Entry]
Version=1.0
Type=Application
Name=Brave Browser
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
Exec=gnome-terminal -- bash -c "python3 /opt/ridos-core/bin/ridos_shell.py; exec bash"
Icon=utilities-terminal
Terminal=false
Categories=System;
DESK

cat > chroot/home/ridos/Desktop/ridos-welcome.desktop << 'DESK'
[Desktop Entry]
Version=1.0
Type=Application
Name=Optional Tools
Exec=gnome-terminal -- bash -c "python3 /opt/ridos-core/bin/welcome-app.py; exec bash"
Icon=preferences-system
Terminal=false
Categories=System;
DESK

cat > chroot/home/ridos/Desktop/ridos-help.desktop << 'DESK'
[Desktop Entry]
Version=1.0
Type=Application
Name=RIDOS-Core Help
Exec=gnome-terminal -- bash -c "ridos-help; exec bash"
Icon=help-browser
Terminal=false
Categories=System;
DESK

# Mark desktop files as trusted and set permissions
chmod +x chroot/home/ridos/Desktop/*.desktop
chown -R 1000:1000 chroot/home/ridos
chmod -R 755 chroot/opt/ridos-core/bin
chmod -R 777 chroot/opt/ridos-core/logs

echo "=== All RIDOS-Core files installed ==="
echo "    Installer autostart: 10s after GNOME loads"
echo "    Desktop icons: 5 shortcuts created"
