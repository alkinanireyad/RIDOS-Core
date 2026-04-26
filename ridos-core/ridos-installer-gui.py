#!/usr/bin/env python3
# ============================================================
#  RIDOS-Core 1.0 Nova — Native GUI Installer
#  Modern GTK4 wizard installer with full hardware detection
#
#  Handles:
#    - NVMe, SATA, VirtIO, USB, eMMC disks
#    - BIOS/MBR and EFI/GPT auto-detection
#    - VirtualBox VDI and real HDD identically
#    - Real-time progress with rsync
#    - Full logging to /tmp/ridos-install.log
#
#  Run:  sudo python3 ridos-installer-gui.py
# ============================================================

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib, Gdk, Pango
import subprocess, threading, os, sys, re, json, time, logging, shutil
from pathlib import Path
from datetime import datetime

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_FILE = "/tmp/ridos-install.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("ridos-installer")

# ── Constants ─────────────────────────────────────────────────────────────────
MOUNT_TARGET   = "/mnt/ridos_target"
SQUASHFS_PATHS = [
    "/run/live/medium/live/filesystem.squashfs",
    "/lib/live/mount/medium/live/filesystem.squashfs",
    "/cdrom/live/filesystem.squashfs",
    "/run/initramfs/live/filesystem.squashfs",
    "/mnt/live/filesystem.squashfs",
]
VERSION  = "1.0 Nova"
APP_NAME = "RIDOS-Core Installer"

# ── CSS Theme ─────────────────────────────────────────────────────────────────
CSS = b"""
@import url("https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap");

* {
    font-family: 'DM Sans', 'Cantarell', sans-serif;
}

window {
    background-color: #0d1117;
    color: #e6edf3;
}

.sidebar {
    background: linear-gradient(180deg, #0a1628 0%, #0d1117 100%);
    border-right: 1px solid #21262d;
    min-width: 220px;
}

.sidebar-logo {
    color: #00d4aa;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.5px;
}

.sidebar-version {
    color: #484f58;
    font-size: 11px;
    font-weight: 400;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.step-item {
    padding: 10px 16px;
    border-radius: 8px;
    margin: 2px 8px;
    color: #484f58;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s ease;
}

.step-item-active {
    background: rgba(0, 212, 170, 0.12);
    color: #00d4aa;
    border-left: 3px solid #00d4aa;
}

.step-item-done {
    color: #3fb950;
}

.step-item-done-mark {
    color: #3fb950;
    font-size: 14px;
}

.page-title {
    font-size: 26px;
    font-weight: 700;
    color: #e6edf3;
    letter-spacing: -0.5px;
}

.page-subtitle {
    font-size: 14px;
    color: #8b949e;
    font-weight: 400;
}

.card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 16px;
}

.card:hover {
    border-color: #30363d;
}

.card-selected {
    background: rgba(0, 212, 170, 0.08);
    border-color: #00d4aa;
}

.disk-name {
    font-size: 15px;
    font-weight: 600;
    color: #e6edf3;
    font-family: 'JetBrains Mono', monospace;
}

.disk-detail {
    font-size: 12px;
    color: #8b949e;
    font-weight: 400;
}

.disk-size {
    font-size: 20px;
    font-weight: 700;
    color: #00d4aa;
}

.disk-size-unit {
    font-size: 12px;
    color: #484f58;
}

.warning-card {
    background: rgba(210, 153, 34, 0.08);
    border: 1px solid rgba(210, 153, 34, 0.3);
    border-radius: 10px;
    padding: 12px 16px;
}

.warning-text {
    color: #d29922;
    font-size: 13px;
    font-weight: 500;
}

.error-card {
    background: rgba(248, 81, 73, 0.08);
    border: 1px solid rgba(248, 81, 73, 0.3);
    border-radius: 10px;
    padding: 12px 16px;
}

.error-text {
    color: #f85149;
    font-size: 13px;
    font-weight: 500;
}

.success-card {
    background: rgba(63, 185, 80, 0.08);
    border: 1px solid rgba(63, 185, 80, 0.3);
    border-radius: 10px;
    padding: 12px 16px;
}

.success-text {
    color: #3fb950;
    font-size: 13px;
    font-weight: 500;
}

.info-card {
    background: rgba(0, 212, 170, 0.06);
    border: 1px solid rgba(0, 212, 170, 0.2);
    border-radius: 10px;
    padding: 12px 16px;
}

.info-text {
    color: #00d4aa;
    font-size: 13px;
    font-weight: 400;
}

.btn-primary {
    background: linear-gradient(135deg, #00d4aa 0%, #00b894 100%);
    color: #0d1117;
    font-weight: 700;
    font-size: 14px;
    border-radius: 8px;
    padding: 10px 28px;
    border: none;
    box-shadow: 0 4px 16px rgba(0, 212, 170, 0.3);
    transition: all 0.2s ease;
}

.btn-primary:hover {
    background: linear-gradient(135deg, #00e5bb 0%, #00cba3 100%);
    box-shadow: 0 6px 20px rgba(0, 212, 170, 0.45);
}

.btn-primary:disabled {
    background: #21262d;
    color: #484f58;
    box-shadow: none;
}

.btn-secondary {
    background: #21262d;
    color: #8b949e;
    font-weight: 500;
    font-size: 14px;
    border-radius: 8px;
    padding: 10px 24px;
    border: 1px solid #30363d;
    transition: all 0.2s ease;
}

.btn-secondary:hover {
    background: #30363d;
    color: #e6edf3;
}

.btn-danger {
    background: rgba(248, 81, 73, 0.15);
    color: #f85149;
    font-weight: 600;
    font-size: 14px;
    border-radius: 8px;
    padding: 10px 24px;
    border: 1px solid rgba(248, 81, 73, 0.3);
}

.input-field {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    color: #e6edf3;
    font-size: 14px;
    padding: 10px 14px;
    font-family: 'DM Sans', sans-serif;
}

.input-field:focus {
    border-color: #00d4aa;
    box-shadow: 0 0 0 3px rgba(0, 212, 170, 0.15);
}

.input-label {
    font-size: 13px;
    font-weight: 600;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
}

.progress-bar trough {
    background: #21262d;
    border-radius: 4px;
    min-height: 8px;
}

.progress-bar progress {
    background: linear-gradient(90deg, #00d4aa, #00b894);
    border-radius: 4px;
    min-height: 8px;
}

.log-view {
    background: #0a0e13;
    color: #00d4aa;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 11px;
    border-radius: 8px;
    border: 1px solid #21262d;
    padding: 12px;
}

.summary-row {
    padding: 10px 0;
    border-bottom: 1px solid #21262d;
}

.summary-label {
    font-size: 13px;
    color: #8b949e;
    font-weight: 500;
}

.summary-value {
    font-size: 13px;
    color: #e6edf3;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}

.badge-bios {
    background: rgba(139, 148, 158, 0.15);
    color: #8b949e;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

.badge-efi {
    background: rgba(0, 212, 170, 0.15);
    color: #00d4aa;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

.done-title {
    font-size: 32px;
    font-weight: 700;
    color: #3fb950;
    letter-spacing: -1px;
}

.done-sub {
    font-size: 15px;
    color: #8b949e;
}

.separator {
    background: #21262d;
    min-height: 1px;
}

.status-dot-ok   { color: #3fb950; font-size: 16px; }
.status-dot-warn { color: #d29922; font-size: 16px; }
.status-dot-err  { color: #f85149; font-size: 16px; }
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd, **kw):
    log.debug(f"RUN: {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    if r.stdout.strip(): log.debug(f"OUT: {r.stdout.strip()}")
    if r.stderr.strip(): log.debug(f"ERR: {r.stderr.strip()}")
    return r

def run_ok(cmd):
    return run(cmd).returncode == 0

def detect_efi():
    return os.path.exists("/sys/firmware/efi")

def find_squashfs():
    for p in SQUASHFS_PATHS:
        if os.path.exists(p):
            log.info(f"Found squashfs: {p}")
            return p
    # Deep search fallback
    r = run("find /run /lib /mnt /cdrom -name 'filesystem.squashfs' 2>/dev/null | head -1")
    p = r.stdout.strip()
    if p and os.path.exists(p):
        log.info(f"Found squashfs (deep): {p}")
        return p
    return None

def get_disks():
    """Detect all installable disks with full metadata."""
    disks = []
    try:
        r = run("lsblk -J -b -o NAME,SIZE,TYPE,MODEL,TRAN,HOTPLUG,ROTA,VENDOR 2>/dev/null")
        data = json.loads(r.stdout)
        for dev in data.get("blockdevices", []):
            if dev.get("type") != "disk":
                continue
            name = dev.get("name","")
            path = f"/dev/{name}"
            size_b = int(dev.get("size") or 0)
            size_gb = round(size_b / (1024**3), 1)
            if size_gb < 4:
                continue  # skip tiny devices
            model  = (dev.get("model") or "").strip() or "Unknown Disk"
            tran   = (dev.get("tran")  or "").strip().upper()
            rota   = dev.get("rota","1")
            hotplug= dev.get("hotplug","0")

            # Friendly type label
            if "nvme" in name:        dtype = "NVMe SSD"
            elif "mmcblk" in name:    dtype = "eMMC"
            elif tran == "USB":       dtype = "USB Drive"
            elif rota == "0":         dtype = "SSD"
            else:                     dtype = "HDD"

            # VirtualBox / VM detection
            vendor = (dev.get("vendor") or "").strip().upper()
            if any(x in model.upper() for x in ["VBOX","VIRTIO","QEMU","VMWARE"]):
                dtype = f"Virtual Disk ({dtype})"

            disks.append({
                "path":    path,
                "name":    name,
                "size_b":  size_b,
                "size_gb": size_gb,
                "model":   model,
                "type":    dtype,
                "tran":    tran,
            })
    except Exception as e:
        log.error(f"lsblk JSON failed: {e}, falling back to text parse")
        # Fallback: plain lsblk
        r = run("lsblk -d -o NAME,SIZE,MODEL 2>/dev/null")
        for line in r.stdout.splitlines()[1:]:
            parts = line.split(None, 2)
            if len(parts) < 2: continue
            name = parts[0]
            size = parts[1]
            model = parts[2].strip() if len(parts)>2 else "Unknown"
            disks.append({
                "path": f"/dev/{name}", "name": name,
                "size_b": 0, "size_gb": 0,
                "model": model, "type": "Disk", "tran": ""
            })
    log.info(f"Detected {len(disks)} disk(s)")
    return disks

def validate_username(u):
    return bool(re.match(r'^[a-z_][a-z0-9_-]{0,31}$', u))

def validate_hostname(h):
    return bool(re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$', h))

# ── Installer State ───────────────────────────────────────────────────────────
class InstallState:
    def __init__(self):
        self.disk       = None   # dict from get_disks()
        self.efi        = detect_efi()
        self.username   = ""
        self.password   = ""
        self.hostname   = "ridos-pc"
        self.autologin  = False
        self.squashfs   = find_squashfs()
        self.timezone   = "Asia/Baghdad"
        self.locale     = "en_US.UTF-8"

state = InstallState()

# ── Main Window ───────────────────────────────────────────────────────────────
class RIDOSInstaller(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.ridos.installer")
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        self.win = InstallerWindow(application=app)
        self.win.present()

# ── Installer Window ──────────────────────────────────────────────────────────
class InstallerWindow(Adw.ApplicationWindow):

    STEPS = [
        ("welcome",   "Welcome",      "⬡"),
        ("disk",      "Select Disk",  "◈"),
        ("user",      "User Setup",   "◉"),
        ("summary",   "Summary",      "◎"),
        ("install",   "Installing",   "▶"),
        ("done",      "Complete",     "✓"),
    ]

    def __init__(self, **kw):
        super().__init__(**kw)
        self.set_title(APP_NAME)
        self.set_default_size(920, 620)
        self.set_resizable(True)
        self.current_step = 0
        self._apply_css()
        self._build_ui()

    def _apply_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_content(root)

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.add_css_class("sidebar")
        sidebar.set_size_request(220, -1)

        # Logo area
        logo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        logo_box.set_margin_top(32)
        logo_box.set_margin_start(20)
        logo_box.set_margin_bottom(32)

        logo = Gtk.Label(label="RIDOS-Core")
        logo.add_css_class("sidebar-logo")
        logo.set_halign(Gtk.Align.START)

        ver = Gtk.Label(label=f"Version {VERSION}")
        ver.add_css_class("sidebar-version")
        ver.set_halign(Gtk.Align.START)

        logo_box.append(logo)
        logo_box.append(ver)
        sidebar.append(logo_box)

        sep = Gtk.Separator()
        sep.add_css_class("separator")
        sep.set_margin_start(20)
        sep.set_margin_end(20)
        sep.set_margin_bottom(16)
        sidebar.append(sep)

        # Step list
        self.step_labels = []
        for i, (key, label, icon) in enumerate(self.STEPS):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("step-item")

            icon_lbl = Gtk.Label(label=icon)
            icon_lbl.set_size_request(20, -1)

            txt = Gtk.Label(label=label)
            txt.set_halign(Gtk.Align.START)
            txt.set_hexpand(True)

            row.append(icon_lbl)
            row.append(txt)
            sidebar.append(row)
            self.step_labels.append((row, icon_lbl, txt))

        # Spacer
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar.append(spacer)

        # Log path hint
        log_hint = Gtk.Label(label=f"Log: {LOG_FILE}")
        log_hint.set_margin_bottom(16)
        log_hint.set_margin_start(16)
        log_hint.set_margin_end(16)
        log_hint.set_halign(Gtk.Align.START)
        log_hint.add_css_class("sidebar-version")
        log_hint.set_wrap(True)
        sidebar.append(log_hint)

        root.append(sidebar)

        # ── Content area ─────────────────────────────────────────────────────
        content_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_wrap.set_hexpand(True)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)

        # Build pages
        self.stack.add_named(self._page_welcome(), "welcome")
        self.stack.add_named(self._page_disk(),    "disk")
        self.stack.add_named(self._page_user(),    "user")
        self.stack.add_named(self._page_summary(), "summary")
        self.stack.add_named(self._page_install(), "install")
        self.stack.add_named(self._page_done(),    "done")

        content_wrap.append(self.stack)

        # Nav bar
        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        nav.set_margin_top(12)
        nav.set_margin_bottom(16)
        nav.set_margin_start(32)
        nav.set_margin_end(32)

        self.btn_back = Gtk.Button(label="← Back")
        self.btn_back.add_css_class("btn-secondary")
        self.btn_back.connect("clicked", self.go_back)

        spacer2 = Gtk.Box()
        spacer2.set_hexpand(True)

        self.btn_next = Gtk.Button(label="Continue →")
        self.btn_next.add_css_class("btn-primary")
        self.btn_next.connect("clicked", self.go_next)

        nav.append(self.btn_back)
        nav.append(spacer2)
        nav.append(self.btn_next)
        content_wrap.append(nav)

        root.append(content_wrap)
        self._update_sidebar()
        self._update_nav()

    # ── Page: Welcome ─────────────────────────────────────────────────────────
    def _page_welcome(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(48)
        box.set_margin_start(48)
        box.set_margin_end(48)

        title = Gtk.Label(label=f"Welcome to RIDOS-Core {VERSION}")
        title.add_css_class("page-title")
        title.set_halign(Gtk.Align.START)

        sub = Gtk.Label(label="Let's get your system ready. This wizard will guide you through the installation.")
        sub.add_css_class("page-subtitle")
        sub.set_halign(Gtk.Align.START)
        sub.set_wrap(True)

        box.append(title)
        box.append(sub)

        # System check cards
        checks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        checks_box.set_margin_top(16)

        efi_mode = "EFI / UEFI" if state.efi else "BIOS / Legacy"
        efi_cls  = "badge-efi" if state.efi else "badge-bios"

        squash_ok = state.squashfs is not None
        squash_msg = state.squashfs if squash_ok else "Not found — cannot install"
        squash_dot = "●" if squash_ok else "●"
        squash_cls = "status-dot-ok" if squash_ok else "status-dot-err"

        checks = [
            ("Boot Mode",    efi_mode,    "badge-efi" if state.efi else "badge-bios", True),
            ("Filesystem",   squash_msg,  squash_cls,  squash_ok),
            ("Target Mount", MOUNT_TARGET,"status-dot-ok", True),
            ("Log File",     LOG_FILE,    "status-dot-ok", True),
        ]

        for label, value, cls, ok in checks:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.add_css_class("card")
            row.set_margin_bottom(2)

            dot = Gtk.Label(label="●")
            dot.add_css_class("status-dot-ok" if ok else "status-dot-err")

            lbl = Gtk.Label(label=label)
            lbl.add_css_class("summary-label")
            lbl.set_size_request(120, -1)
            lbl.set_halign(Gtk.Align.START)

            val = Gtk.Label(label=value)
            val.add_css_class("summary-value")
            val.set_halign(Gtk.Align.START)
            val.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            val.set_hexpand(True)

            row.append(dot)
            row.append(lbl)
            row.append(val)
            checks_box.append(row)

        box.append(checks_box)

        if not squash_ok:
            err = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            err.add_css_class("error-card")
            err.set_margin_top(8)
            msg = Gtk.Label(label="⚠  Filesystem image not found. Make sure you are running from the RIDOS-Core live ISO.")
            msg.add_css_class("error-text")
            msg.set_wrap(True)
            err.append(msg)
            box.append(err)

        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        info.add_css_class("info-card")
        info.set_margin_top(8)
        info_msg = Gtk.Label(label="ℹ  Installation will erase all data on the selected disk. Make sure you have backups.")
        info_msg.add_css_class("info-text")
        info_msg.set_wrap(True)
        info.append(info_msg)
        box.append(info)

        return self._scrollable(box)

    # ── Page: Disk ────────────────────────────────────────────────────────────
    def _page_disk(self):
        self._disk_page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self._disk_page_box.set_margin_top(48)
        self._disk_page_box.set_margin_start(48)
        self._disk_page_box.set_margin_end(48)
        self._disk_buttons = []
        self._refresh_disk_page()
        return self._scrollable(self._disk_page_box)

    def _refresh_disk_page(self):
        # Clear
        child = self._disk_page_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._disk_page_box.remove(child)
            child = nxt
        self._disk_buttons = []

        title = Gtk.Label(label="Select Installation Disk")
        title.add_css_class("page-title")
        title.set_halign(Gtk.Align.START)

        sub = Gtk.Label(label="Choose the disk where RIDOS-Core will be installed. All data on the selected disk will be erased.")
        sub.add_css_class("page-subtitle")
        sub.set_halign(Gtk.Align.START)
        sub.set_wrap(True)

        self._disk_page_box.append(title)
        self._disk_page_box.append(sub)

        # Refresh button
        ref_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        ref_btn = Gtk.Button(label="⟳  Refresh Disks")
        ref_btn.add_css_class("btn-secondary")
        ref_btn.connect("clicked", lambda _: self._refresh_disk_page())
        ref_row.append(ref_btn)
        self._disk_page_box.append(ref_row)

        disks = get_disks()
        if not disks:
            err = Gtk.Box()
            err.add_css_class("error-card")
            msg = Gtk.Label(label="⚠  No suitable disks found. Make sure the virtual hard disk is attached (VirtualBox: Settings → Storage).")
            msg.add_css_class("error-text")
            msg.set_wrap(True)
            err.append(msg)
            self._disk_page_box.append(err)
            return

        disks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        disks_box.set_margin_top(8)

        for d in disks:
            btn = Gtk.ToggleButton()
            btn.add_css_class("card")

            inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            inner.set_margin_top(4)
            inner.set_margin_bottom(4)

            # Disk icon by type
            icon_map = {
                "NVMe SSD": "⚡", "SSD": "⬡", "HDD": "◈",
                "Virtual Disk (SSD)": "▣", "Virtual Disk (HDD)": "▣",
                "USB Drive": "⬦", "eMMC": "◉"
            }
            icon_char = icon_map.get(d["type"], "◈")
            icon_lbl = Gtk.Label(label=icon_char)
            icon_lbl.set_markup(f'<span font="20">{icon_char}</span>')
            icon_lbl.set_size_request(40, -1)

            text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text_col.set_hexpand(True)

            name_lbl = Gtk.Label(label=d["path"])
            name_lbl.add_css_class("disk-name")
            name_lbl.set_halign(Gtk.Align.START)

            detail_lbl = Gtk.Label(label=f"{d['model']}  ·  {d['type']}")
            detail_lbl.add_css_class("disk-detail")
            detail_lbl.set_halign(Gtk.Align.START)

            text_col.append(name_lbl)
            text_col.append(detail_lbl)

            size_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            size_col.set_halign(Gtk.Align.END)

            size_num = Gtk.Label(label=f"{d['size_gb']}")
            size_num.add_css_class("disk-size")
            size_num.set_halign(Gtk.Align.END)

            size_unit = Gtk.Label(label="GB")
            size_unit.add_css_class("disk-size-unit")
            size_unit.set_halign(Gtk.Align.END)

            size_col.append(size_num)
            size_col.append(size_unit)

            inner.append(icon_lbl)
            inner.append(text_col)
            inner.append(size_col)
            btn.set_child(inner)

            btn._disk_data = d
            btn.connect("toggled", self._on_disk_toggled)
            self._disk_buttons.append(btn)
            disks_box.append(btn)

        self._disk_page_box.append(disks_box)

        warn = Gtk.Box()
        warn.add_css_class("warning-card")
        warn.set_margin_top(8)
        wmsg = Gtk.Label(label="⚠  The selected disk will be completely erased. Partition table and all data will be overwritten.")
        wmsg.add_css_class("warning-text")
        wmsg.set_wrap(True)
        warn.append(wmsg)
        self._disk_page_box.append(warn)

    def _on_disk_toggled(self, btn):
        if btn.get_active():
            state.disk = btn._disk_data
            log.info(f"Selected disk: {state.disk['path']}")
            for other in self._disk_buttons:
                if other is not btn:
                    other.set_active(False)
                    other.remove_css_class("card-selected")
            btn.add_css_class("card-selected")
        else:
            if state.disk and state.disk["path"] == btn._disk_data["path"]:
                state.disk = None
            btn.remove_css_class("card-selected")
        self._update_nav()

    # ── Page: User ────────────────────────────────────────────────────────────
    def _page_user(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(48)
        box.set_margin_start(48)
        box.set_margin_end(48)

        title = Gtk.Label(label="Create Your Account")
        title.add_css_class("page-title")
        title.set_halign(Gtk.Align.START)

        sub = Gtk.Label(label="Set up the primary user account for your RIDOS-Core installation.")
        sub.add_css_class("page-subtitle")
        sub.set_halign(Gtk.Align.START)

        box.append(title)
        box.append(sub)

        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        form.add_css_class("card")
        form.set_margin_top(8)

        def field(label_text, placeholder, is_pass=False):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            lbl = Gtk.Label(label=label_text)
            lbl.add_css_class("input-label")
            lbl.set_halign(Gtk.Align.START)
            entry = Gtk.Entry()
            entry.add_css_class("input-field")
            entry.set_placeholder_text(placeholder)
            if is_pass:
                entry.set_visibility(False)
            col.append(lbl)
            col.append(entry)
            return col, entry

        user_col, self.entry_user = field("Username", "e.g. john")
        pass_col, self.entry_pass = field("Password", "Enter password", True)
        pass2_col, self.entry_pass2 = field("Confirm Password", "Re-enter password", True)
        host_col, self.entry_host = field("Hostname", "e.g. ridos-pc")
        self.entry_host.set_text("ridos-pc")

        self.entry_user.connect("changed", self._validate_user_form)
        self.entry_pass.connect("changed", self._validate_user_form)
        self.entry_pass2.connect("changed", self._validate_user_form)
        self.entry_host.connect("changed", self._validate_user_form)

        # Autologin toggle
        auto_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        auto_lbl = Gtk.Label(label="Enable automatic login at boot")
        auto_lbl.add_css_class("disk-detail")
        auto_lbl.set_hexpand(True)
        auto_lbl.set_halign(Gtk.Align.START)
        self.toggle_autologin = Gtk.Switch()
        self.toggle_autologin.connect("state-set", lambda sw, s: setattr(state, "autologin", s))
        auto_row.append(auto_lbl)
        auto_row.append(self.toggle_autologin)

        form.append(user_col)
        form.append(pass_col)
        form.append(pass2_col)
        form.append(host_col)
        form.append(Gtk.Separator())
        form.append(auto_row)

        self.user_feedback = Gtk.Label(label="")
        self.user_feedback.set_halign(Gtk.Align.START)
        self.user_feedback.set_wrap(True)

        box.append(form)
        box.append(self.user_feedback)
        return self._scrollable(box)

    def _validate_user_form(self, *_):
        u  = self.entry_user.get_text().strip()
        p  = self.entry_pass.get_text()
        p2 = self.entry_pass2.get_text()
        h  = self.entry_host.get_text().strip()

        errors = []
        if u and not validate_username(u):
            errors.append("Username must start with a letter, only a-z 0-9 _ - allowed")
        if p and p2 and p != p2:
            errors.append("Passwords do not match")
        if len(p) > 0 and len(p) < 6:
            errors.append("Password must be at least 6 characters")
        if h and not validate_hostname(h):
            errors.append("Hostname contains invalid characters")

        if errors:
            self.user_feedback.set_markup(f'<span color="#f85149">⚠  {errors[0]}</span>')
        else:
            self.user_feedback.set_text("")

        if u and p and p2 and h and not errors:
            state.username = u
            state.password = p
            state.hostname = h

        self._update_nav()

    # ── Page: Summary ─────────────────────────────────────────────────────────
    def _page_summary(self):
        self._summary_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self._summary_box.set_margin_top(48)
        self._summary_box.set_margin_start(48)
        self._summary_box.set_margin_end(48)
        return self._scrollable(self._summary_box)

    def _refresh_summary(self):
        child = self._summary_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._summary_box.remove(child)
            child = nxt

        title = Gtk.Label(label="Review & Confirm")
        title.add_css_class("page-title")
        title.set_halign(Gtk.Align.START)

        sub = Gtk.Label(label="Please review the installation settings below. Click Install to begin.")
        sub.add_css_class("page-subtitle")
        sub.set_halign(Gtk.Align.START)

        self._summary_box.append(title)
        self._summary_box.append(sub)

        rows = [
            ("Target Disk",    state.disk["path"] if state.disk else "—"),
            ("Disk Model",     state.disk["model"] if state.disk else "—"),
            ("Disk Size",      f"{state.disk['size_gb']} GB" if state.disk else "—"),
            ("Boot Mode",      "EFI / UEFI" if state.efi else "BIOS / Legacy"),
            ("Filesystem",     state.squashfs or "Not found"),
            ("Username",       state.username or "—"),
            ("Hostname",       state.hostname or "—"),
            ("Auto-login",     "Yes" if state.autologin else "No"),
            ("Timezone",       state.timezone),
            ("Locale",         state.locale),
        ]

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("card")

        for label, value in rows:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.add_css_class("summary-row")

            lbl = Gtk.Label(label=label)
            lbl.add_css_class("summary-label")
            lbl.set_size_request(160, -1)
            lbl.set_halign(Gtk.Align.START)

            val = Gtk.Label(label=value)
            val.add_css_class("summary-value")
            val.set_halign(Gtk.Align.START)
            val.set_hexpand(True)
            val.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

            row.append(lbl)
            row.append(val)
            card.append(row)

        self._summary_box.append(card)

        warn = Gtk.Box()
        warn.add_css_class("warning-card")
        warn.set_margin_top(12)
        wmsg = Gtk.Label(label=f"⚠  This will permanently erase ALL data on {state.disk['path'] if state.disk else 'selected disk'}. This cannot be undone.")
        wmsg.add_css_class("warning-text")
        wmsg.set_wrap(True)
        warn.append(wmsg)
        self._summary_box.append(warn)

    # ── Page: Install ─────────────────────────────────────────────────────────
    def _page_install(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(48)
        box.set_margin_start(48)
        box.set_margin_end(48)

        title = Gtk.Label(label="Installing RIDOS-Core")
        title.add_css_class("page-title")
        title.set_halign(Gtk.Align.START)

        self.install_status = Gtk.Label(label="Preparing installation...")
        self.install_status.add_css_class("page-subtitle")
        self.install_status.set_halign(Gtk.Align.START)
        self.install_status.set_wrap(True)

        self.progress = Gtk.ProgressBar()
        self.progress.add_css_class("progress-bar")
        self.progress.set_margin_top(8)
        self.progress.set_margin_bottom(8)

        self.progress_label = Gtk.Label(label="0%")
        self.progress_label.add_css_class("disk-detail")
        self.progress_label.set_halign(Gtk.Align.END)

        # Log view
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_vexpand(True)
        log_scroll.set_min_content_height(220)
        log_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.add_css_class("log-view")
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        log_scroll.set_child(self.log_view)

        box.append(title)
        box.append(self.install_status)
        box.append(self.progress)
        box.append(self.progress_label)
        box.append(log_scroll)

        return box

    # ── Page: Done ────────────────────────────────────────────────────────────
    def _page_done(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_top(48)
        box.set_margin_bottom(48)

        icon = Gtk.Label()
        icon.set_markup('<span font="64" color="#3fb950">✓</span>')

        title = Gtk.Label(label="Installation Complete!")
        title.add_css_class("done-title")

        sub = Gtk.Label(label="RIDOS-Core has been installed successfully.\nRemove the USB/ISO and reboot your computer.")
        sub.add_css_class("done-sub")
        sub.set_justify(Gtk.Justification.CENTER)
        sub.set_wrap(True)

        log_info = Gtk.Label(label=f"Full installation log saved to:\n{LOG_FILE}")
        log_info.add_css_class("disk-detail")
        log_info.set_justify(Gtk.Justification.CENTER)
        log_info.set_margin_top(8)

        reboot_btn = Gtk.Button(label="⏻  Reboot Now")
        reboot_btn.add_css_class("btn-primary")
        reboot_btn.set_margin_top(16)
        reboot_btn.set_halign(Gtk.Align.CENTER)
        reboot_btn.connect("clicked", lambda _: run_ok("reboot"))

        box.append(icon)
        box.append(title)
        box.append(sub)
        box.append(log_info)
        box.append(reboot_btn)

        return box

    # ── Navigation ────────────────────────────────────────────────────────────
    def go_next(self, *_):
        step_keys = [s[0] for s in self.STEPS]
        key = step_keys[self.current_step]

        # Pre-advance hooks
        if key == "summary":
            self._start_installation()
            self.current_step += 1
        elif key == "disk":
            if not state.disk:
                return
            self.current_step += 1
        elif key == "user":
            if not self._user_form_valid():
                return
            self.current_step += 1
        elif key == "install":
            return  # install page advances automatically
        elif key == "done":
            return
        else:
            self.current_step += 1

        # Post-advance hooks
        new_key = step_keys[self.current_step]
        if new_key == "summary":
            self._refresh_summary()

        self.stack.set_visible_child_name(new_key)
        self._update_sidebar()
        self._update_nav()

    def go_back(self, *_):
        if self.current_step == 0:
            return
        step_keys = [s[0] for s in self.STEPS]
        if step_keys[self.current_step] in ("install", "done"):
            return
        self.current_step -= 1
        self.stack.set_visible_child_name(step_keys[self.current_step])
        self._update_sidebar()
        self._update_nav()

    def _user_form_valid(self):
        u  = self.entry_user.get_text().strip()
        p  = self.entry_pass.get_text()
        p2 = self.entry_pass2.get_text()
        h  = self.entry_host.get_text().strip()
        return (u and p and p2 and h and
                p == p2 and len(p) >= 6 and
                validate_username(u) and validate_hostname(h))

    def _update_nav(self):
        step_keys = [s[0] for s in self.STEPS]
        key = step_keys[self.current_step]

        self.btn_back.set_visible(self.current_step > 0 and key not in ("install","done"))
        self.btn_next.set_visible(key not in ("install","done"))

        # Label changes
        if key == "summary":
            self.btn_next.set_label("⚡  Install Now")
        else:
            self.btn_next.set_label("Continue →")

        # Disable next if conditions not met
        if key == "disk":
            self.btn_next.set_sensitive(state.disk is not None)
        elif key == "user":
            self.btn_next.set_sensitive(self._user_form_valid())
        elif key == "welcome":
            self.btn_next.set_sensitive(state.squashfs is not None)
        else:
            self.btn_next.set_sensitive(True)

    def _update_sidebar(self):
        for i, (row, icon_lbl, txt_lbl) in enumerate(self.step_labels):
            row.remove_css_class("step-item-active")
            row.remove_css_class("step-item-done")
            icon_lbl.remove_css_class("step-item-done-mark")
            if i == self.current_step:
                row.add_css_class("step-item-active")
            elif i < self.current_step:
                row.add_css_class("step-item-done")
                icon_lbl.add_css_class("step-item-done-mark")

    # ── Installation Engine ───────────────────────────────────────────────────
    def _start_installation(self):
        self.stack.set_visible_child_name("install")
        self._update_sidebar()
        self.btn_next.set_visible(False)
        self.btn_back.set_visible(False)
        t = threading.Thread(target=self._run_installation, daemon=True)
        t.start()

    def _log(self, msg):
        log.info(msg)
        GLib.idle_add(self._append_log, msg)

    def _append_log(self, msg):
        end = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end, f"{msg}\n")
        self.log_view.scroll_to_iter(self.log_buffer.get_end_iter(), 0, False, 0, 0)
        return False

    def _set_progress(self, frac, msg):
        GLib.idle_add(self._update_progress_ui, frac, msg)

    def _update_progress_ui(self, frac, msg):
        self.progress.set_fraction(min(frac, 1.0))
        self.progress_label.set_text(f"{int(frac*100)}%")
        self.install_status.set_text(msg)
        return False

    def _run_installation(self):
        disk  = state.disk["path"]
        efi   = state.efi
        sqfs  = state.squashfs
        user  = state.username
        passwd= state.password
        host  = state.hostname
        auto  = state.autologin
        target= MOUNT_TARGET

        try:
            # ── Step 1: Prepare ─────────────────────────────────────────────
            self._set_progress(0.02, "Preparing disk...")
            self._log(f"=== RIDOS-Core Installation Started ===")
            self._log(f"Disk:     {disk}")
            self._log(f"Mode:     {'EFI' if efi else 'BIOS'}")
            self._log(f"Source:   {sqfs}")
            self._log(f"User:     {user}@{host}")

            # Unmount anything on target
            run(f"umount -lf {target}/dev/pts 2>/dev/null || true")
            run(f"umount -lf {target}/dev     2>/dev/null || true")
            run(f"umount -lf {target}/proc    2>/dev/null || true")
            run(f"umount -lf {target}/sys     2>/dev/null || true")
            run(f"umount -lf {target}/run     2>/dev/null || true")
            run(f"umount -lf {target}         2>/dev/null || true")
            run(f"swapoff -a 2>/dev/null || true")

            os.makedirs(target, exist_ok=True)

            # ── Step 2: Partition ────────────────────────────────────────────
            self._set_progress(0.08, "Partitioning disk...")
            self._log("Wiping disk signatures...")
            run(f"wipefs -a {disk}")
            run(f"sgdisk --zap-all {disk} 2>/dev/null || parted -s {disk} mklabel {'gpt' if efi else 'msdos'}")

            if efi:
                self._log("Creating GPT/EFI partition layout...")
                cmds = [
                    f"parted -s {disk} mklabel gpt",
                    f"parted -s {disk} mkpart primary fat32 1MiB 513MiB",
                    f"parted -s {disk} set 1 esp on",
                    f"parted -s {disk} mkpart primary linux-swap 513MiB 2561MiB",
                    f"parted -s {disk} mkpart primary ext4 2561MiB 100%",
                ]
                for c in cmds:
                    r = run(c)
                    if r.returncode != 0:
                        raise Exception(f"Partition failed: {c}\n{r.stderr}")

                efi_part, swap_part, root_part = self._get_partitions(disk, 3)
                self._log(f"EFI:  {efi_part}")
                self._log(f"Swap: {swap_part}")
                self._log(f"Root: {root_part}")
            else:
                self._log("Creating MBR/BIOS partition layout...")
                cmds = [
                    f"parted -s {disk} mklabel msdos",
                    f"parted -s {disk} mkpart primary linux-swap 1MiB 2049MiB",
                    f"parted -s {disk} mkpart primary ext4 2049MiB 100%",
                    f"parted -s {disk} set 2 boot on",
                ]
                for c in cmds:
                    r = run(c)
                    if r.returncode != 0:
                        raise Exception(f"Partition failed: {c}\n{r.stderr}")

                swap_part, root_part = self._get_partitions(disk, 2)
                efi_part = None
                self._log(f"Swap: {swap_part}")
                self._log(f"Root: {root_part}")

            # Let kernel re-read
            run(f"partprobe {disk} 2>/dev/null || true")
            run("udevadm settle")
            time.sleep(2)

            # ── Step 3: Format ───────────────────────────────────────────────
            self._set_progress(0.15, "Formatting partitions...")
            self._log("Formatting partitions...")

            if efi_part:
                r = run(f"mkfs.vfat -F32 -n RIDOSEFI {efi_part}")
                if r.returncode != 0:
                    raise Exception(f"EFI format failed: {r.stderr}")
                self._log(f"Formatted EFI: {efi_part}")

            r = run(f"mkswap -L ridos-swap {swap_part}")
            if r.returncode != 0:
                raise Exception(f"Swap format failed: {r.stderr}")
            self._log(f"Formatted swap: {swap_part}")

            r = run(f"mkfs.ext4 -F -L ridos-root {root_part}")
            if r.returncode != 0:
                raise Exception(f"Root format failed: {r.stderr}")
            self._log(f"Formatted root: {root_part}")

            # ── Step 4: Mount ────────────────────────────────────────────────
            self._set_progress(0.20, "Mounting partitions...")
            r = run(f"mount {root_part} {target}")
            if r.returncode != 0:
                raise Exception(f"Mount failed: {r.stderr}")
            self._log(f"Mounted root at {target}")

            if efi_part:
                os.makedirs(f"{target}/boot/efi", exist_ok=True)
                r = run(f"mount {efi_part} {target}/boot/efi")
                if r.returncode != 0:
                    raise Exception(f"EFI mount failed: {r.stderr}")
                self._log(f"Mounted EFI at {target}/boot/efi")

            run(f"swapon {swap_part}")

            # ── Step 5: Copy filesystem ──────────────────────────────────────
            self._set_progress(0.25, "Copying filesystem (this takes 5-15 minutes)...")
            self._log(f"Copying from: {sqfs}")

            # Mount squashfs
            sqfs_mount = "/mnt/ridos_squashfs"
            os.makedirs(sqfs_mount, exist_ok=True)
            run(f"umount -lf {sqfs_mount} 2>/dev/null || true")
            r = run(f"mount -t squashfs -o loop,ro {sqfs} {sqfs_mount}")
            if r.returncode != 0:
                raise Exception(f"Cannot mount squashfs: {r.stderr}")
            self._log("Squashfs mounted, starting rsync...")

            # rsync with progress tracking
            self._rsync_with_progress(sqfs_mount, target)

            run(f"umount {sqfs_mount}")
            self._log("Filesystem copy complete.")

            # ── Step 6: Generate fstab ───────────────────────────────────────
            self._set_progress(0.72, "Generating fstab...")
            root_uuid = self._get_uuid(root_part)
            swap_uuid = self._get_uuid(swap_part)
            efi_uuid  = self._get_uuid(efi_part) if efi_part else None

            fstab = "# /etc/fstab — generated by RIDOS-Core Installer\n"
            fstab += f"UUID={root_uuid}  /          ext4  errors=remount-ro  0  1\n"
            if efi_uuid:
                fstab += f"UUID={efi_uuid}   /boot/efi  vfat  umask=0077         0  1\n"
            fstab += f"UUID={swap_uuid}  none       swap  sw                 0  0\n"
            fstab += "tmpfs             /tmp       tmpfs defaults,nosuid,nodev  0  0\n"

            with open(f"{target}/etc/fstab", "w") as f:
                f.write(fstab)
            self._log(f"fstab written (root UUID: {root_uuid})")

            # ── Step 7: Bind mounts for chroot ───────────────────────────────
            self._set_progress(0.76, "Setting up chroot environment...")
            for d in ["dev", "proc", "sys", "run"]:
                os.makedirs(f"{target}/{d}", exist_ok=True)
                run(f"mount --bind /{d} {target}/{d}")
            run(f"mount --bind /dev/pts {target}/dev/pts 2>/dev/null || true")
            self._log("Chroot bind mounts ready.")

            # ── Step 8: Hostname ─────────────────────────────────────────────
            self._set_progress(0.79, "Configuring system...")
            with open(f"{target}/etc/hostname", "w") as f:
                f.write(f"{host}\n")
            with open(f"{target}/etc/hosts", "w") as f:
                f.write(f"127.0.0.1  localhost\n127.0.1.1  {host}\n::1        localhost\n")
            self._log(f"Hostname: {host}")

            # ── Step 9: User account ─────────────────────────────────────────
            self._set_progress(0.82, f"Creating user '{user}'...")
            run(f"chroot {target} userdel -r ridos 2>/dev/null || true")
            run(f"chroot {target} userdel -r user  2>/dev/null || true")

            r = run(f"chroot {target} useradd -m -s /bin/bash "
                    f"-G sudo,audio,video,plugdev,netdev,bluetooth,cdrom,lp {user}")
            if r.returncode != 0:
                raise Exception(f"useradd failed: {r.stderr}")

            # Set password via chpasswd
            r = run(f"echo '{user}:{passwd}' | chroot {target} chpasswd")
            if r.returncode != 0:
                raise Exception(f"chpasswd failed: {r.stderr}")
            self._log(f"User '{user}' created.")

            # Autologin
            if auto:
                gdm_conf = f"{target}/etc/gdm3/custom.conf"
                if os.path.exists(gdm_conf):
                    run(f"sed -i 's/#AutomaticLoginEnable/AutomaticLoginEnable/' {gdm_conf}")
                    run(f"sed -i 's/#AutomaticLogin.*/AutomaticLogin={user}/' {gdm_conf}")
                    self._log(f"Autologin enabled for {user}")

            # ── Step 10: Remove live packages ────────────────────────────────
            self._set_progress(0.85, "Cleaning up live packages...")
            live_pkgs = "live-boot live-boot-initramfs-tools live-config live-config-sysvinit live-tools"
            run(f"chroot {target} apt-get purge -y {live_pkgs} 2>/dev/null || true")
            run(f"chroot {target} apt-get autoremove -y 2>/dev/null || true")
            self._log("Live packages removed.")

            # ── Step 11: Initramfs ───────────────────────────────────────────
            self._set_progress(0.88, "Rebuilding initramfs...")
            r = run(f"chroot {target} update-initramfs -u -k all")
            if r.returncode != 0:
                self._log(f"WARNING: initramfs rebuild had issues: {r.stderr[:200]}")
            else:
                self._log("Initramfs rebuilt.")

            # ── Step 12: GRUB ────────────────────────────────────────────────
            self._set_progress(0.92, "Installing GRUB bootloader...")
            if efi:
                r = run(f"chroot {target} grub-install --target=x86_64-efi "
                        f"--efi-directory=/boot/efi --bootloader-id=RIDOS "
                        f"--recheck {disk}")
            else:
                r = run(f"chroot {target} grub-install --target=i386-pc "
                        f"--recheck {disk}")

            if r.returncode != 0:
                raise Exception(f"GRUB install failed: {r.stderr}")
            self._log(f"GRUB installed ({'EFI' if efi else 'BIOS'}).")

            r = run(f"chroot {target} update-grub")
            if r.returncode != 0:
                self._log(f"WARNING: update-grub: {r.stderr[:200]}")
            else:
                self._log("GRUB config updated.")

            # ── Step 13: Cleanup ─────────────────────────────────────────────
            self._set_progress(0.97, "Finalising installation...")
            for d in ["dev/pts", "dev", "proc", "sys", "run"]:
                run(f"umount -lf {target}/{d} 2>/dev/null || true")
            run(f"swapoff {swap_part} 2>/dev/null || true")
            if efi_part:
                run(f"umount {target}/boot/efi 2>/dev/null || true")
            run(f"umount {target} 2>/dev/null || true")
            run("sync")

            self._log("=== Installation completed successfully! ===")
            self._set_progress(1.0, "Installation complete!")

            # Advance to done
            GLib.idle_add(self._advance_to_done)

        except Exception as e:
            log.error(f"Installation error: {e}", exc_info=True)
            # Cleanup on error
            for d in ["dev/pts","dev","proc","sys","run"]:
                run(f"umount -lf {target}/{d} 2>/dev/null || true")
            run(f"umount -lf {target} 2>/dev/null || true")
            GLib.idle_add(self._show_install_error, str(e))

    def _rsync_with_progress(self, src, dst):
        """Run rsync and update progress bar based on file count."""
        # Count files first
        self._log("Counting files...")
        r = run(f"unsquashfs -l {state.squashfs} 2>/dev/null | wc -l || find {src} | wc -l")
        try:
            total = max(int(r.stdout.strip()), 1)
        except:
            total = 100000

        self._log(f"Total files to copy: ~{total}")

        cmd = (f"rsync -aAXH --delete --info=progress2 "
               f"--exclude=/proc --exclude=/sys --exclude=/dev "
               f"--exclude=/run --exclude=/tmp --exclude=/mnt "
               f"--exclude=/media --exclude=/lost+found "
               f"{src}/ {dst}/")

        proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )

        file_re = re.compile(r'(\d+),?(\d*)\s+(\d+)%')
        last_pct = 0

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            m = file_re.search(line)
            if m:
                pct = int(m.group(3))
                if pct != last_pct:
                    last_pct = pct
                    prog = 0.25 + (pct / 100) * 0.45
                    GLib.idle_add(self._update_progress_ui, prog,
                                  f"Copying filesystem... {pct}%")
            if len(line) > 2 and not line.startswith("sent"):
                log.debug(f"rsync: {line}")

        proc.wait()
        if proc.returncode != 0:
            raise Exception(f"rsync failed with code {proc.returncode}")

    def _get_partitions(self, disk, count):
        """Get partition paths robustly for NVMe, SATA, VirtIO etc."""
        run("udevadm settle")
        time.sleep(1)
        parts = []

        # NVMe uses p1, p2... others use 1, 2...
        sep = "p" if "nvme" in disk or "mmcblk" in disk else ""

        for i in range(1, count+1):
            p = f"{disk}{sep}{i}"
            # Try with separator first, fallback without
            if os.path.exists(p):
                parts.append(p)
            elif os.path.exists(f"{disk}{i}"):
                parts.append(f"{disk}{i}")
            else:
                # Wait and retry
                time.sleep(2)
                run("partprobe")
                run("udevadm settle")
                if os.path.exists(p):
                    parts.append(p)
                else:
                    raise Exception(f"Partition {p} not found after partitioning. "
                                    f"Try: ls {disk}*")
        return parts

    def _get_uuid(self, part):
        if not part:
            return ""
        r = run(f"blkid -s UUID -o value {part}")
        uuid = r.stdout.strip()
        if not uuid:
            raise Exception(f"Cannot get UUID for {part}")
        return uuid

    def _advance_to_done(self):
        self.current_step = len(self.STEPS) - 1
        self.stack.set_visible_child_name("done")
        self._update_sidebar()
        self._update_nav()
        return False

    def _show_install_error(self, msg):
        self.install_status.set_markup(
            f'<span color="#f85149">⚠  Installation failed: {GLib.markup_escape_text(msg[:200])}\n'
            f'See log: {LOG_FILE}</span>'
        )
        self.progress.add_css_class("error")
        # Show back button to allow retry
        self.btn_back.set_visible(True)
        self.btn_back.set_label("← Start Over")
        self.btn_back.connect("clicked", lambda _: self._hard_reset())
        return False

    def _hard_reset(self):
        self.current_step = 0
        self.stack.set_visible_child_name("welcome")
        self._update_sidebar()
        self._update_nav()

    def _scrollable(self, child):
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        sw.set_child(child)
        return sw


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Error: RIDOS Installer must be run as root.")
        print("Usage: sudo python3 ridos-installer-gui.py")
        sys.exit(1)

    log.info(f"RIDOS-Core Installer {VERSION} starting")
    log.info(f"EFI mode: {detect_efi()}")
    log.info(f"Squashfs: {find_squashfs()}")

    app = RIDOSInstaller()
    app.run(sys.argv)
