#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# build-ridos-welcome.sh — RIDOS-Core 1.0 Nova
# Repo location: build-system/scripts/build-ridos-welcome.sh
# Compiles the Rust/GTK4 welcome app inside the chroot.
# Called by build-iso.yml AFTER all packages are installed.
# The compiled binary is placed at /opt/ridos-core/bin/ridos-welcome
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "=== Building ridos-welcome (Rust + GTK4) ==="

# Verify source files exist in the repo
if [ ! -f "ridos-welcome/Cargo.toml" ] || \
   [ ! -f "ridos-welcome/src/main.rs" ]; then
    echo "ERROR: ridos-welcome/ source not found in repo."
    echo "Expected: ridos-welcome/Cargo.toml"
    echo "Expected: ridos-welcome/src/main.rs"
    exit 1
fi

# Copy source into chroot
mkdir -p chroot/tmp/ridos-welcome/src
cp ridos-welcome/Cargo.toml   chroot/tmp/ridos-welcome/
cp ridos-welcome/src/main.rs  chroot/tmp/ridos-welcome/src/

# Install Rust build dependencies inside chroot
echo "Installing Rust build dependencies..."
mount --bind /dev  chroot/dev
mount --bind /proc chroot/proc
mount --bind /sys  chroot/sys

chroot chroot apt-get install -y \
    libgtk-4-dev \
    pkg-config \
    libglib2.0-dev \
    gcc \
    --no-install-recommends 2>/dev/null || true

# Install rustup inside chroot (as root, for the build only)
echo "Installing Rust toolchain via rustup..."
chroot chroot bash -c "
    curl --proto '=https' --tlsv1.2 -sSf \
        https://sh.rustup.rs -o /tmp/rustup-init.sh
    sh /tmp/rustup-init.sh -y --default-toolchain stable \
        --no-modify-path --profile minimal
    export PATH=\$PATH:/root/.cargo/bin
    echo 'Rust version:'; rustc --version
    echo 'Cargo version:'; cargo --version
" 2>&1

# Build the release binary
echo "Compiling ridos-welcome (release build)..."
chroot chroot bash -c "
    export PATH=\$PATH:/root/.cargo/bin
    cd /tmp/ridos-welcome
    cargo build --release 2>&1
    echo 'Build complete.'
    ls -lh target/release/ridos-welcome
" 2>&1

# Copy binary to final location
echo "Installing binary..."
mkdir -p chroot/opt/ridos-core/bin
cp chroot/tmp/ridos-welcome/target/release/ridos-welcome \
   chroot/opt/ridos-core/bin/ridos-welcome
chmod +x chroot/opt/ridos-core/bin/ridos-welcome

# Clean up build artifacts to keep ISO lean
rm -rf chroot/tmp/ridos-welcome
# Remove rustup to save space in the ISO
# (users can install it themselves via Optional Tools)
rm -rf chroot/root/.cargo chroot/root/.rustup

umount chroot/sys  || true
umount chroot/proc || true
umount chroot/dev  || true

# Verify
BINARY="chroot/opt/ridos-core/bin/ridos-welcome"
if [ -f "$BINARY" ]; then
    SIZE=$(du -sh "$BINARY" | cut -f1)
    echo "=== ridos-welcome compiled successfully ==="
    echo "    Binary: /opt/ridos-core/bin/ridos-welcome"
    echo "    Size  : $SIZE"
else
    echo "ERROR: binary not found after build!"
    exit 1
fi
