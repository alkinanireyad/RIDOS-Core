#!/usr/bin/env python3
"""
write-grub-config.py — RIDOS-Core 1.0 Nova
Writes GRUB menu with Wayland default + Xorg fallback + VirtualBox entry.
Run on HOST after kernel/initrd copied to iso/live/.
"""
import os

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: f.write(content)

for f in ['iso/live/vmlinuz', 'iso/live/initrd']:
    if not os.path.exists(f):
        print(f"ERROR: {f} not found.")
        raise SystemExit(1)

write('iso/boot/grub/grub.cfg', '''# RIDOS-Core 1.0 Nova — GRUB Boot Menu
set default=0
set timeout=10
set timeout_style=menu

insmod all_video
insmod font
insmod gfxterm
if loadfont /boot/grub/fonts/unicode.pf2; then
    set gfxmode=auto
    terminal_output gfxterm
fi

# ── Live — GNOME Wayland (default) ───────────────────────────────────────────
menuentry "RIDOS-Core 1.0 Nova — Live (GNOME Wayland)" --class ridos --class gnu-linux {
    set gfxpayload=keep
    linux  /live/vmlinuz boot=live components quiet splash \
           hostname=ridos-core username=ridos \
           locales=en_US.UTF-8 timezone=Asia/Baghdad noeject
    initrd /live/initrd
}

# ── Live — GNOME Xorg fallback (VirtualBox / safe mode) ──────────────────────
menuentry "RIDOS-Core 1.0 Nova — Live (Xorg / VirtualBox)" --class ridos --class gnu-linux {
    set gfxpayload=keep
    linux  /live/vmlinuz boot=live components nomodeset quiet splash \
           hostname=ridos-core username=ridos \
           locales=en_US.UTF-8 timezone=Asia/Baghdad noeject \
           MUTTER_DEBUG_FORCE_EGL_STREAM=1
    initrd /live/initrd
}

# ── Live — Safe graphics (troubleshooting) ────────────────────────────────────
menuentry "RIDOS-Core 1.0 Nova — Safe Graphics" --class ridos --class gnu-linux {
    set gfxpayload=keep
    linux  /live/vmlinuz boot=live components nomodeset \
           hostname=ridos-core username=ridos noeject
    initrd /live/initrd
}

# ── Install to HDD ────────────────────────────────────────────────────────────
menuentry "Install RIDOS-Core 1.0 Nova to Hard Drive" --class ridos --class gnu-linux {
    set gfxpayload=keep
    linux  /live/vmlinuz boot=live components quiet splash \
           hostname=ridos-core username=ridos \
           locales=en_US.UTF-8 timezone=Asia/Baghdad noeject
    initrd /live/initrd
}

# ── Memory test ───────────────────────────────────────────────────────────────
if [ -e /boot/memtest86+.bin ]; then
menuentry "Memory Test (memtest86+)" {
    linux16 /boot/memtest86+.bin
}
fi

# ── UEFI firmware setup ───────────────────────────────────────────────────────
if [ "${grub_platform}" = "efi" ]; then
menuentry "UEFI Firmware Setup" { fwsetup }
fi
''')

print("GRUB config written — 4 boot entries:")
print("  1. Live GNOME Wayland (default)")
print("  2. Live Xorg / VirtualBox fallback")
print("  3. Safe Graphics")
print("  4. Install to Hard Drive")
