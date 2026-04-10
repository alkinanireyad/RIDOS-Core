#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# build-ridos-welcome.sh — RIDOS-Core 1.0 Nova
# Repo location : build-system/scripts/build-ridos-welcome.sh
# Called by     : build-iso.yml with: sudo bash build-system/scripts/build-ridos-welcome.sh
# Runs on HOST  : uses chroot/ prefix, mounts /dev /proc /sys for apt/cargo
# Output        : chroot/opt/ridos-core/bin/ridos-welcome (native binary)
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "=== Building ridos-welcome (Rust + GTK4) ==="

# ── Verify source files exist ─────────────────────────────────────────────────
if [ ! -f "ridos-welcome/Cargo.toml" ] || \
   [ ! -f "ridos-welcome/src/main.rs" ]; then
    echo "ERROR: ridos-welcome source files not found."
    echo "  Expected: ridos-welcome/Cargo.toml"
    echo "  Expected: ridos-welcome/src/main.rs"
    exit 1
fi

echo "Source files found. Copying into chroot..."
mkdir -p chroot/tmp/ridos-welcome/src
cp ridos-welcome/Cargo.toml      chroot/tmp/ridos-welcome/
cp ridos-welcome/src/main.rs     chroot/tmp/ridos-welcome/src/

# ── Set up chroot DNS so cargo/rustup can download ────────────────────────────
# Without this, network requests inside chroot will fail
echo "Configuring DNS for chroot..."
cp /etc/resolv.conf chroot/etc/resolv.conf

# ── Bind mounts ───────────────────────────────────────────────────────────────
echo "Mounting system directories..."
mount --bind /dev  chroot/dev
mount --bind /proc chroot/proc
mount --bind /sys  chroot/sys
mount --bind /run  chroot/run

# ── Install GTK4 C development library ───────────────────────────────────────
# gtk4-rs (the Rust crate) wraps the GTK4 C library.
# libgtk-4-dev must be present for cargo to compile against it.
echo "Installing GTK4 dev libraries..."
chroot chroot apt-get install -y \
    libgtk-4-dev \
    libglib2.0-dev \
    pkgconf \
    gcc \
    ca-certificates \
    curl \

# ── Install Rust via rustup ───────────────────────────────────────────────────
echo "Installing Rust toolchain via rustup..."
chroot chroot bash << 'RUSTUP'
set -e
export HOME=/root
export CARGO_HOME=/root/.cargo
export RUSTUP_HOME=/root/.rustup

# Download and run rustup installer
curl --proto '=https' --tlsv1.2 -sSf \
    https://sh.rustup.rs -o /tmp/rustup-init.sh

chmod +x /tmp/rustup-init.sh
/tmp/rustup-init.sh -y \
    --default-toolchain stable \
    --no-modify-path \
    --profile minimal

echo "Rust installed:"
/root/.cargo/bin/rustc --version
/root/.cargo/bin/cargo --version
RUSTUP

# ── Build the release binary ──────────────────────────────────────────────────
echo "Compiling ridos-welcome (release build)..."
echo "This will take 15-25 minutes on first build..."

chroot chroot bash << 'BUILD'
set -e
export HOME=/root
export CARGO_HOME=/root/.cargo
export RUSTUP_HOME=/root/.rustup
export PATH=/root/.cargo/bin:$PATH

cd /tmp/ridos-welcome

echo "Starting cargo build --release..."
cargo build --release

echo "Build complete."
ls -lh target/release/ridos-welcome
BUILD

# ── Install binary ────────────────────────────────────────────────────────────
echo "Installing binary to /opt/ridos-core/bin/..."
mkdir -p chroot/opt/ridos-core/bin
cp chroot/tmp/ridos-welcome/target/release/ridos-welcome \
   chroot/opt/ridos-core/bin/ridos-welcome
chmod +x chroot/opt/ridos-core/bin/ridos-welcome

# ── Clean up to keep ISO lean ─────────────────────────────────────────────────
echo "Cleaning up build artifacts..."
rm -rf chroot/tmp/ridos-welcome
rm -rf chroot/root/.cargo
rm -rf chroot/root/.rustup
rm -f  chroot/tmp/rustup-init.sh

# ── Unmount ───────────────────────────────────────────────────────────────────
umount chroot/run  || true
umount chroot/sys  || true
umount chroot/proc || true
umount chroot/dev  || true

# ── Verify ────────────────────────────────────────────────────────────────────
BINARY="chroot/opt/ridos-core/bin/ridos-welcome"
if [ -f "$BINARY" ]; then
    SIZE=$(du -sh "$BINARY" | cut -f1)
    echo ""
    echo "=== ridos-welcome built successfully ==="
    echo "    Binary : /opt/ridos-core/bin/ridos-welcome"
    echo "    Size   : $SIZE"
    echo "    Type   : $(file "$BINARY" | cut -d: -f2)"
else
    echo "ERROR: binary not found after build!"
    exit 1
fi
