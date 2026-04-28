#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# build-ridos-welcome.sh — RIDOS-Core 1.0 Nova
# Repo location : build-system/scripts/build-ridos-welcome.sh
# Called by     : sudo bash build-system/scripts/build-ridos-welcome.sh
# Runs on HOST  : uses chroot/ prefix
# Output        : chroot/opt/ridos-core/bin/ridos-welcome
#
# CRITICAL: Uses a trap to GUARANTEE unmount even if build fails.
# Without this, leftover bind mounts corrupt the squashfs → kernel panic.
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "=== Building ridos-welcome (Rust + GTK4) ==="

# ── Verify source files ───────────────────────────────────────────────────────
if [ ! -f "ridos-welcome/Cargo.toml" ] || \
   [ ! -f "ridos-welcome/src/main.rs" ]; then
    echo "ERROR: ridos-welcome source files not found."
    exit 1
fi

# ── TRAP: guarantee cleanup no matter what happens ───────────────────────────
# This runs on EXIT (success, failure, or signal).
# Leftover bind mounts corrupt the squashfs and cause kernel panic on boot.
cleanup() {
    echo "=== Cleaning up build-ridos-welcome mounts ==="
    umount -l chroot/run  2>/dev/null || true
    umount -l chroot/sys  2>/dev/null || true
    umount -l chroot/proc 2>/dev/null || true
    umount -l chroot/dev  2>/dev/null || true
    echo "Mounts released."
}
trap cleanup EXIT

echo "Copying source into chroot..."
mkdir -p chroot/tmp/ridos-welcome/src
cp ridos-welcome/Cargo.toml    chroot/tmp/ridos-welcome/
cp ridos-welcome/src/main.rs   chroot/tmp/ridos-welcome/src/

# ── DNS for chroot ────────────────────────────────────────────────────────────
echo "Configuring DNS..."
cp /etc/resolv.conf chroot/etc/resolv.conf

# ── Bind mounts ───────────────────────────────────────────────────────────────
echo "Mounting system directories..."
mount --bind /dev  chroot/dev
mount --bind /proc chroot/proc
mount --bind /sys  chroot/sys
mount --bind /run  chroot/run

# ── Ensure correct sources.list ───────────────────────────────────────────────
cat > chroot/etc/apt/sources.list << 'SOURCES'
deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware
deb http://deb.debian.org/debian bookworm-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
SOURCES

# ── Update + install build dependencies ──────────────────────────────────────
echo "Running apt-get update..."
chroot chroot apt-get update

echo "Verifying packages are available..."
for pkg in build-essential libgtk-4-dev pkg-config ca-certificates curl; do
    if chroot chroot apt-cache show "$pkg" > /dev/null 2>&1; then
        echo "  FOUND: $pkg"
    else
        echo "  MISSING: $pkg"
        exit 1
    fi
done

echo "Installing build dependencies..."
chroot chroot apt-get install -y \
    build-essential \
    libgtk-4-dev \
    pkg-config \
    ca-certificates \
    curl

# ── Install Rust via rustup ───────────────────────────────────────────────────
echo "Installing Rust toolchain..."
chroot chroot bash << 'RUSTUP'
set -e
export HOME=/root
export CARGO_HOME=/root/.cargo
export RUSTUP_HOME=/root/.rustup

curl --proto '=https' --tlsv1.2 -sSf \
    https://sh.rustup.rs -o /tmp/rustup-init.sh

sh /tmp/rustup-init.sh -y \
    --default-toolchain stable \
    --no-modify-path \
    --profile minimal

echo "Rust ready:"
/root/.cargo/bin/rustc --version
/root/.cargo/bin/cargo --version
RUSTUP

# ── Build release binary ──────────────────────────────────────────────────────
echo "Compiling ridos-welcome (15-25 minutes)..."
chroot chroot bash << 'BUILD'
set -e
export HOME=/root
export CARGO_HOME=/root/.cargo
export RUSTUP_HOME=/root/.rustup
export PATH=/root/.cargo/bin:$PATH
export PKG_CONFIG_PATH=/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig

cd /tmp/ridos-welcome
cargo build --release
echo "Build done."
ls -lh target/release/ridos-welcome
BUILD

# ── Install binary ────────────────────────────────────────────────────────────
echo "Installing binary..."
mkdir -p chroot/opt/ridos-core/bin
cp chroot/tmp/ridos-welcome/target/release/ridos-welcome \
   chroot/opt/ridos-core/bin/ridos-welcome
chmod +x chroot/opt/ridos-core/bin/ridos-welcome

# ── Clean build artifacts BEFORE unmount ─────────────────────────────────────
echo "Cleaning up build artifacts..."
rm -rf chroot/tmp/ridos-welcome
rm -rf chroot/root/.cargo
rm -rf chroot/root/.rustup
rm -f  chroot/tmp/rustup-init.sh

# trap runs here automatically — unmounts /dev /proc /sys /run

# ── Verify binary ─────────────────────────────────────────────────────────────
BINARY="chroot/opt/ridos-core/bin/ridos-welcome"
if [ -f "$BINARY" ]; then
    SIZE=$(du -sh "$BINARY" | cut -f1)
    echo ""
    echo "=== ridos-welcome built successfully ==="
    echo "    Binary : /opt/ridos-core/bin/ridos-welcome"
    echo "    Size   : $SIZE"
else
    echo "ERROR: binary not found after build!"
    exit 1
fi
