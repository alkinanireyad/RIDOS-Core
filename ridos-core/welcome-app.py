#!/usr/bin/env python3
"""
welcome-app.py — RIDOS-Core 1.0 Nova
Post-install welcome app: lets user choose optional tools to install.
Uses GTK3 via PyGObject.
"""
import subprocess, threading, sys

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, GLib, Pango
except ImportError:
    print("GTK not available. Install: sudo apt-get install python3-gi gir1.2-gtk-3.0")
    sys.exit(1)

# ── Tool definitions ──────────────────────────────────────────────────────────
TOOLS = [
    # (id, label, description, apt_packages, default_checked, tier)
    ("timeshift",   "Timeshift",                "System snapshots & restore — recommended",
     "timeshift", True, 1),
    ("flatpak",     "Flatpak + Flathub",         "Sandboxed app store — recommended",
     "flatpak gnome-software-plugin-flatpak", True, 1),
    ("fwupd",       "Firmware Updater (fwupd)",  "Update hardware firmware automatically",
     "fwupd fwupd-signed", True, 1),
    ("zram",        "Zram Compression",          "Compressed RAM swap — great for low-RAM machines",
     "zram-tools", False, 2),
    ("tlp",         "TLP Battery Optimizer",     "Extends laptop battery life significantly",
     "tlp tlp-rdw", False, 2),
    ("cockpit",     "Cockpit Web Admin",         "Browser-based system monitoring at localhost:9090",
     "cockpit", False, 2),
    ("distrobox",   "Distrobox",                 "Run any Linux distro inside a container",
     "distrobox", False, 2),
    ("rust",        "Rust Toolchain",            "Full Rust development environment",
     "", False, 2),  # installed via rustup
    ("wireguard",   "WireGuard VPN",             "Fast, modern VPN — kernel-native",
     "wireguard wireguard-tools", False, 3),
    ("firejail",    "Firejail Sandbox",          "Isolate applications for extra security",
     "firejail", False, 3),
    ("ollama",      "Ollama AI Assistant",       "Local offline AI — requires 4GB+ RAM (2GB download)",
     "", False, 3),  # installed via install-ollama.sh
    ("panickey",    "Panic Key (Security)",      "Emergency RAM wipe + shutdown — Ctrl+Alt+Del override",
     "", False, 3),
]

TIER_LABELS = {1: "✓ Recommended", 2: "⚡ Power User", 3: "🔒 Advanced / Security"}


class WelcomeApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="Welcome to RIDOS-Core 1.0 Nova")
        self.set_default_size(680, 700)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)

        self.checks = {}
        self._build_ui()

    def _build_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(vbox)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header.set_margin_top(28)
        header.set_margin_bottom(16)
        header.set_margin_start(32)
        header.set_margin_end(32)

        title = Gtk.Label()
        title.set_markup('<span size="xx-large" weight="bold" color="#58a6ff">RIDOS-Core 1.0 Nova</span>')
        title.set_halign(Gtk.Align.START)

        subtitle = Gtk.Label()
        subtitle.set_markup('<span color="#8b949e">Rust-Ready Linux • Select optional tools to install</span>')
        subtitle.set_halign(Gtk.Align.START)

        header.pack_start(title, False, False, 0)
        header.pack_start(subtitle, False, False, 0)
        vbox.pack_start(header, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.pack_start(sep, False, False, 0)

        # Scrollable tool list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(400)

        tool_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        tool_box.set_margin_top(12)
        tool_box.set_margin_bottom(12)
        tool_box.set_margin_start(32)
        tool_box.set_margin_end(32)

        current_tier = None
        for tool_id, label, desc, pkgs, default, tier in TOOLS:
            if tier != current_tier:
                current_tier = tier
                tier_label = Gtk.Label()
                tier_label.set_markup(f'<span weight="bold" color="#58a6ff">{TIER_LABELS[tier]}</span>')
                tier_label.set_halign(Gtk.Align.START)
                tier_label.set_margin_top(12)
                tier_label.set_margin_bottom(4)
                tool_box.pack_start(tier_label, False, False, 0)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.set_margin_bottom(2)

            cb = Gtk.CheckButton()
            cb.set_active(default)
            self.checks[tool_id] = cb

            label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            name_lbl = Gtk.Label()
            name_lbl.set_markup(f'<b>{label}</b>')
            name_lbl.set_halign(Gtk.Align.START)
            desc_lbl = Gtk.Label(label=desc)
            desc_lbl.set_halign(Gtk.Align.START)
            desc_lbl.set_opacity(0.6)
            attr = Pango.AttrList()
            attr.insert(Pango.attr_size_new(10 * Pango.SCALE))
            desc_lbl.set_attributes(attr)

            label_box.pack_start(name_lbl, False, False, 0)
            label_box.pack_start(desc_lbl, False, False, 0)

            row.pack_start(cb, False, False, 0)
            row.pack_start(label_box, True, True, 0)
            tool_box.pack_start(row, False, False, 0)

        scroll.add(tool_box)
        vbox.pack_start(scroll, True, True, 0)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.pack_start(sep2, False, False, 0)

        # Status bar
        self.status = Gtk.Label(label="Select tools above and click Install.")
        self.status.set_halign(Gtk.Align.START)
        self.status.set_margin_start(32)
        self.status.set_margin_top(8)
        self.status.set_margin_bottom(8)
        vbox.pack_start(self.status, False, False, 0)

        # Progress bar
        self.progress = Gtk.ProgressBar()
        self.progress.set_margin_start(32)
        self.progress.set_margin_end(32)
        self.progress.set_visible(False)
        vbox.pack_start(self.progress, False, False, 0)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_margin_start(32)
        btn_box.set_margin_end(32)
        btn_box.set_margin_top(12)
        btn_box.set_margin_bottom(20)
        btn_box.set_halign(Gtk.Align.END)

        skip_btn = Gtk.Button(label="Skip for now")
        skip_btn.connect("clicked", lambda _: self.destroy())

        self.install_btn = Gtk.Button(label="Install Selected")
        self.install_btn.get_style_context().add_class("suggested-action")
        self.install_btn.connect("clicked", self._on_install)

        btn_box.pack_start(skip_btn, False, False, 0)
        btn_box.pack_start(self.install_btn, False, False, 0)
        vbox.pack_start(btn_box, False, False, 0)

    def _on_install(self, _):
        selected = [t for t in TOOLS if self.checks[t[0]].get_active()]
        if not selected:
            self.status.set_text("No tools selected.")
            return
        self.install_btn.set_sensitive(False)
        self.progress.set_visible(True)
        self.progress.set_fraction(0)
        threading.Thread(target=self._install_thread,
                         args=(selected,), daemon=True).start()

    def _install_thread(self, selected):
        total = len(selected)
        for i, (tool_id, label, desc, pkgs, *_) in enumerate(selected):
            GLib.idle_add(self.status.set_text, f"Installing {label}...")
            GLib.idle_add(self.progress.set_fraction, i / total)

            if tool_id == "rust":
                subprocess.run(
                    'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y',
                    shell=True)
            elif tool_id == "ollama":
                subprocess.run(
                    'bash /opt/ridos-core/bin/install-ollama.sh',
                    shell=True)
            elif tool_id == "panickey":
                subprocess.run(
                    'python3 /opt/ridos-core/bin/panic-key.py --install',
                    shell=True)
            elif pkgs:
                subprocess.run(
                    f'pkexec apt-get install -y {pkgs}',
                    shell=True)

            if tool_id == "flatpak":
                subprocess.run(
                    'flatpak remote-add --if-not-exists flathub '
                    'https://dl.flathub.org/repo/flathub.flatpakrepo',
                    shell=True)

        GLib.idle_add(self.progress.set_fraction, 1.0)
        GLib.idle_add(self.status.set_text, "✓ Installation complete!")
        GLib.idle_add(self.install_btn.set_label, "Done")

    def run(self):
        self.connect("destroy", Gtk.main_quit)
        self.show_all()
        Gtk.main()


if __name__ == '__main__':
    app = WelcomeApp()
    app.run()
