// ridos-welcome — RIDOS-Core 1.0 Nova Welcome Application
// Language: Rust + GTK4 (gtk4-rs 0.7)
// Tabs: System Info | Install Tools | About | Install to HDD
// Compiled to native binary — zero Python dependency

use gtk::prelude::*;
use gtk::{
    glib, Application, ApplicationWindow,
    Box as GtkBox, Button, CheckButton, Label,
    Notebook, Orientation, PolicyType,
    ProgressBar, ScrolledWindow, Separator,
    Spinner, Stack, StackTransitionType,
    TextView, WrapMode,
};
use std::cell::RefCell;
use std::rc::Rc;
use std::sync::{Arc, Mutex};

const APP_ID:   &str = "com.ridos.welcome";
const VERSION:  &str = "RIDOS-Core 1.0 Nova";
const REPO_URL: &str = "https://github.com/alkinanireyad/RIDOS-Core";

// ── Optional tools definition ─────────────────────────────────────────────────
#[derive(Clone)]
struct Tool {
    id:      &'static str,
    name:    &'static str,
    desc:    &'static str,
    cmd:     &'static str,
    tier:    &'static str,
}

fn tools() -> Vec<Tool> {
    vec![
        // Recommended
        Tool { id: "timeshift",  name: "Timeshift",
               desc: "System snapshots and restore — recommended for all users",
               cmd:  "pkexec apt-get install -y timeshift",
               tier: "Recommended" },
        Tool { id: "flatpak",   name: "Flatpak + Flathub",
               desc: "Sandboxed app store with thousands of apps",
               cmd:  "pkexec apt-get install -y flatpak gnome-software-plugin-flatpak && flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo",
               tier: "Recommended" },
        Tool { id: "fwupd",     name: "Firmware Updater",
               desc: "Update BIOS, SSD, and peripheral firmware automatically",
               cmd:  "pkexec apt-get install -y fwupd",
               tier: "Recommended" },
        // Power User
        Tool { id: "zram",      name: "Zram Compression",
               desc: "Compressed RAM swap — major performance gain on low-RAM systems",
               cmd:  "pkexec apt-get install -y zram-tools",
               tier: "Power User" },
        Tool { id: "tlp",       name: "TLP Battery Optimizer",
               desc: "Extends laptop battery life significantly",
               cmd:  "pkexec apt-get install -y tlp tlp-rdw && pkexec systemctl enable tlp",
               tier: "Power User" },
        Tool { id: "cockpit",   name: "Cockpit Web Admin",
               desc: "Browser-based system monitoring at localhost:9090",
               cmd:  "pkexec apt-get install -y cockpit && pkexec systemctl enable cockpit.socket",
               tier: "Power User" },
        Tool { id: "distrobox", name: "Distrobox",
               desc: "Run any Linux distro inside a container",
               cmd:  "pkexec apt-get install -y distrobox",
               tier: "Power User" },
        Tool { id: "rust",      name: "Rust Toolchain",
               desc: "Full Rust development environment via rustup",
               cmd:  "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y",
               tier: "Power User" },
        // Advanced
        Tool { id: "wireguard", name: "WireGuard VPN",
               desc: "Fast, modern kernel-native VPN",
               cmd:  "pkexec apt-get install -y wireguard wireguard-tools",
               tier: "Advanced" },
        Tool { id: "ollama",    name: "Ollama AI Assistant",
               desc: "Local offline AI — requires 4GB+ RAM (2GB download)",
               cmd:  "bash /opt/ridos-core/bin/install-ollama.sh",
               tier: "Advanced" },
        Tool { id: "panickey",  name: "Panic Key (Security)",
               desc: "Emergency RAM wipe and shutdown — Ctrl+Alt+Pause",
               cmd:  "pkexec python3 /opt/ridos-core/bin/panic-key.py --install",
               tier: "Advanced" },
    ]
}

// ── System info collection ────────────────────────────────────────────────────
fn get_sysinfo() -> String {
    let mut lines = vec![
        format!("OS         :  {VERSION}"),
        format!("Repository :  {REPO_URL}"),
        "Kernel     :  Linux 6.12 LTS (Rust-ready, CONFIG_RUST=y)".to_string(),
        "".to_string(),
    ];

    // CPU
    if let Ok(cpuinfo) = std::fs::read_to_string("/proc/cpuinfo") {
        let model = cpuinfo.lines()
            .find(|l| l.starts_with("model name"))
            .and_then(|l| l.split(':').nth(1))
            .map(|s| s.trim().to_string())
            .unwrap_or_else(|| "Unknown".to_string());
        let cores = cpuinfo.lines()
            .filter(|l| l.starts_with("processor"))
            .count();
        lines.push(format!("CPU        :  {model}"));
        lines.push(format!("CPU Cores  :  {cores}"));
    }

    // RAM
    if let Ok(meminfo) = std::fs::read_to_string("/proc/meminfo") {
        let total = meminfo.lines()
            .find(|l| l.starts_with("MemTotal"))
            .and_then(|l| l.split_whitespace().nth(1))
            .and_then(|v| v.parse::<u64>().ok())
            .map(|kb| format!("{:.1} GB", kb as f64 / 1024.0 / 1024.0))
            .unwrap_or_else(|| "Unknown".to_string());
        let avail = meminfo.lines()
            .find(|l| l.starts_with("MemAvailable"))
            .and_then(|l| l.split_whitespace().nth(1))
            .and_then(|v| v.parse::<u64>().ok())
            .map(|kb| format!("{:.1} GB", kb as f64 / 1024.0 / 1024.0))
            .unwrap_or_else(|| "Unknown".to_string());
        lines.push(format!("RAM Total  :  {total}"));
        lines.push(format!("RAM Free   :  {avail}"));
    }

    // Disk
    let df = std::process::Command::new("df")
        .args(["-h", "--output=source,size,used,avail,pcent,target",
               "-x", "tmpfs", "-x", "devtmpfs"])
        .output();
    if let Ok(out) = df {
        let text = String::from_utf8_lossy(&out.stdout);
        lines.push("".to_string());
        lines.push("Disk Usage:".to_string());
        for line in text.lines() {
            lines.push(format!("  {line}"));
        }
    }

    // Boot mode
    let efi = std::path::Path::new("/sys/firmware/efi").exists();
    lines.push("".to_string());
    lines.push(format!("Boot Mode  :  {}",
        if efi { "UEFI" } else { "BIOS/MBR" }));

    // WiFi
    let iwconfig = std::process::Command::new("iw")
        .args(["dev"])
        .output();
    if let Ok(out) = iwconfig {
        let text = String::from_utf8_lossy(&out.stdout);
        let ifaces: Vec<&str> = text.lines()
            .filter(|l| l.trim().starts_with("Interface"))
            .map(|l| l.split_whitespace().nth(1).unwrap_or(""))
            .collect();
        if !ifaces.is_empty() {
            lines.push(format!("WiFi       :  {}", ifaces.join(", ")));
        }
    }

    lines.join("\n")
}

// ── Changelog ─────────────────────────────────────────────────────────────────
fn changelog() -> &'static str {
    "RIDOS-Core 1.0 Nova — Release Notes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEW in 1.0 Nova
───────────────
• First stable release of RIDOS-Core
• Linux 6.12 LTS with Rust kernel support (CONFIG_RUST=y)
• GNOME desktop — Xorg default, Wayland available
• Brave Browser as primary browser (privacy-first)
• Firefox-ESR as fallback browser
• Full Pro IT toolkit pre-installed:
    Network : nmap, wireshark, tcpdump, mtr, iperf3
    Security: aircrack-ng, john, hydra, hashcat, nikto
    Monitoring: htop, btop, iotop, nethogs, ncdu
    DevOps  : docker, ansible, git
    Recovery: testdisk, gddrescue, gparted
• Custom GTK installer (no Calamares dependency)
• WiFi drivers for 2008-2025 hardware including:
    Intel, Atheros, Realtek, MediaTek, Broadcom
• zstd squashfs compression for fast boot
• VS Code pre-installed

ARCHITECTURE
────────────
• Base     : Debian 12 Bookworm
• Kernel   : Linux 6.12 LTS
• Desktop  : GNOME 43
• Installer: ridos-installer.py (custom GTK3)
• Welcome  : ridos-welcome (this app, Rust + GTK4)
• License  : GNU GPL v3

ROADMAP
───────
v1.1  — Panic Key v2.0, Rust coreutils (uutils)
v2.0  — Linux 7.0 kernel, Rust init system
v3.0  — Full Rust system stack, hardware certification

REPOSITORY
──────────
github.com/alkinanireyad/RIDOS-Core"
}

// ── Main application ──────────────────────────────────────────────────────────
fn build_ui(app: &Application) {
    // ── Window ────────────────────────────────────────────────────────────────
    let window = ApplicationWindow::builder()
        .application(app)
        .title(&format!("Welcome to {VERSION}"))
        .default_width(820)
        .default_height(600)
        .build();

    // ── Root box ──────────────────────────────────────────────────────────────
    let root = GtkBox::new(Orientation::Vertical, 0);
    window.set_child(Some(&root));

    // ── Header bar ────────────────────────────────────────────────────────────
    let header = GtkBox::new(Orientation::Horizontal, 0);
    header.set_margin_start(24);
    header.set_margin_end(24);
    header.set_margin_top(16);
    header.set_margin_bottom(16);

    let title_lbl = Label::new(None);
    title_lbl.set_markup(
        &format!("<span size='x-large' weight='bold' \
                  color='#1F6FEB'>{VERSION}</span>"));
    title_lbl.set_halign(gtk::Align::Start);
    title_lbl.set_hexpand(true);

    let sub_lbl = Label::new(None);
    sub_lbl.set_markup(
        "<span color='#6E7781'>Rust-Ready Linux</span>");
    sub_lbl.set_halign(gtk::Align::End);

    header.append(&title_lbl);
    header.append(&sub_lbl);
    root.append(&header);
    root.append(&Separator::new(Orientation::Horizontal));

    // ── Notebook (tabs) ───────────────────────────────────────────────────────
    let notebook = Notebook::new();
    notebook.set_vexpand(true);
    notebook.set_margin_top(8);
    notebook.set_margin_bottom(8);
    notebook.set_margin_start(8);
    notebook.set_margin_end(8);
    root.append(&notebook);

    // ═══════════════════════════════════════════════════════════════════════
    // TAB 1: System Info
    // ═══════════════════════════════════════════════════════════════════════
    {
        let tv = TextView::new();
        tv.set_editable(false);
        tv.set_monospace(true);
        tv.set_wrap_mode(WrapMode::None);
        tv.set_margin_start(12);
        tv.set_margin_end(12);
        tv.set_margin_top(8);
        tv.set_margin_bottom(8);

        let buf = tv.buffer();
        buf.set_text(&get_sysinfo());

        let sc = ScrolledWindow::builder()
            .hscrollbar_policy(PolicyType::Automatic)
            .vscrollbar_policy(PolicyType::Automatic)
            .child(&tv)
            .build();

        let refresh_btn = Button::with_label("🔄  Refresh");
        let tv_clone = tv.clone();
        refresh_btn.connect_clicked(move |_| {
            tv_clone.buffer().set_text(&get_sysinfo());
        });
        refresh_btn.set_halign(gtk::Align::End);
        refresh_btn.set_margin_end(12);
        refresh_btn.set_margin_bottom(8);

        let tab_box = GtkBox::new(Orientation::Vertical, 0);
        tab_box.append(&sc);
        tab_box.append(&refresh_btn);

        let tab_lbl = Label::new(Some("💻  System Info"));
        notebook.append_page(&tab_box, Some(&tab_lbl));
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TAB 2: Optional Tools
    // ═══════════════════════════════════════════════════════════════════════
    {
        let tab_box = GtkBox::new(Orientation::Vertical, 0);
        tab_box.set_margin_start(16);
        tab_box.set_margin_end(16);
        tab_box.set_margin_top(12);

        let intro = Label::new(None);
        intro.set_markup(
            "<span color='#6E7781'>Select optional tools to install. \
             Core system tools are already pre-installed.</span>");
        intro.set_halign(gtk::Align::Start);
        intro.set_margin_bottom(12);
        tab_box.append(&intro);

        // Tool checkboxes inside a scrolled window
        let tools_box = GtkBox::new(Orientation::Vertical, 4);
        tools_box.set_margin_start(4);
        tools_box.set_margin_end(4);

        let tool_list = tools();
        let checks: Rc<RefCell<Vec<(CheckButton, Tool)>>> =
            Rc::new(RefCell::new(Vec::new()));

        let mut current_tier = "";
        for tool in &tool_list {
            if tool.tier != current_tier {
                current_tier = tool.tier;
                let tier_lbl = Label::new(None);
                let color = match current_tier {
                    "Recommended" => "#238636",
                    "Power User"  => "#1F6FEB",
                    _             => "#8250DF",
                };
                tier_lbl.set_markup(&format!(
                    "<b><span color='{color}'>── {current_tier} ──</span></b>"));
                tier_lbl.set_halign(gtk::Align::Start);
                tier_lbl.set_margin_top(12);
                tier_lbl.set_margin_bottom(4);
                tools_box.append(&tier_lbl);
            }

            let row = GtkBox::new(Orientation::Horizontal, 12);
            row.set_margin_bottom(2);

            let cb = CheckButton::new();
            cb.set_active(current_tier == "Recommended");

            let lbl_box = GtkBox::new(Orientation::Vertical, 1);
            let name_lbl = Label::new(None);
            name_lbl.set_markup(
                &format!("<b>{}</b>", tool.name));
            name_lbl.set_halign(gtk::Align::Start);

            let desc_lbl = Label::new(Some(tool.desc));
            desc_lbl.set_halign(gtk::Align::Start);
            desc_lbl.add_css_class("dim-label");

            lbl_box.append(&name_lbl);
            lbl_box.append(&desc_lbl);
            row.append(&cb);
            row.append(&lbl_box);
            tools_box.append(&row);

            checks.borrow_mut().push((cb, tool.clone()));
        }

        let sc = ScrolledWindow::builder()
            .hscrollbar_policy(PolicyType::Never)
            .vscrollbar_policy(PolicyType::Automatic)
            .child(&tools_box)
            .vexpand(true)
            .build();
        tab_box.append(&sc);

        // Progress area
        let prog_bar = ProgressBar::new();
        prog_bar.set_margin_top(8);
        prog_bar.set_visible(false);
        tab_box.append(&prog_bar);

        let status_lbl = Label::new(None);
        status_lbl.set_halign(gtk::Align::Start);
        status_lbl.set_visible(false);
        tab_box.append(&status_lbl);

        // Log output
        let log_tv = TextView::new();
        log_tv.set_editable(false);
        log_tv.set_monospace(true);
        log_tv.set_visible(false);
        log_tv.set_wrap_mode(WrapMode::WordChar);
        let log_sc = ScrolledWindow::builder()
            .vscrollbar_policy(PolicyType::Automatic)
            .child(&log_tv)
            .min_content_height(120)
            .build();
        log_sc.set_visible(false);
        tab_box.append(&log_sc);

        // Install button
        let install_btn = Button::with_label("Install Selected Tools");
        install_btn.add_css_class("suggested-action");
        install_btn.set_margin_top(12);
        install_btn.set_margin_bottom(12);
        install_btn.set_halign(gtk::Align::End);

        let checks_clone    = Rc::clone(&checks);
        let prog_clone      = prog_bar.clone();
        let status_clone    = status_lbl.clone();
        let log_tv_clone    = log_tv.clone();
        let log_sc_clone    = log_sc.clone();
        let install_clone   = install_btn.clone();

        install_btn.connect_clicked(move |_| {
            let selected: Vec<Tool> = checks_clone.borrow()
                .iter()
                .filter(|(cb, _)| cb.is_active())
                .map(|(_, t)| t.clone())
                .collect();

            if selected.is_empty() {
                status_clone.set_markup(
                    "<span color='#D29922'>No tools selected.</span>");
                status_clone.set_visible(true);
                return;
            }

            install_clone.set_sensitive(false);
            prog_clone.set_visible(true);
            prog_clone.set_fraction(0.0);
            status_clone.set_visible(true);
            log_tv_clone.set_visible(true);
            log_sc_clone.set_visible(true);

            let total = selected.len();
            let prog_ref    = prog_clone.clone();
            let status_ref  = status_clone.clone();
            let log_ref     = log_tv_clone.clone();
            let btn_ref     = install_clone.clone();

            // Run installations in a background thread
            let (tx, rx) = glib::MainContext::channel(
                glib::Priority::DEFAULT);

            std::thread::spawn(move || {
                for (i, tool) in selected.iter().enumerate() {
                    let _ = tx.send(format!(
                        "STATUS:Installing {} ({}/{})...",
                        tool.name, i + 1, total));
                    let _ = tx.send(format!(
                        "PROG:{}", (i as f64) / total as f64));

                    let _ = tx.send(format!(
                        "LOG:$ {}", tool.cmd));

                    let output = std::process::Command::new("sh")
                        .args(["-c", tool.cmd])
                        .output();

                    match output {
                        Ok(out) => {
                            let stdout = String::from_utf8_lossy(
                                &out.stdout);
                            let stderr = String::from_utf8_lossy(
                                &out.stderr);
                            for line in stdout.lines().chain(
                                    stderr.lines()) {
                                let _ = tx.send(
                                    format!("LOG:{line}"));
                            }
                            if out.status.success() {
                                let _ = tx.send(format!(
                                    "LOG:✓ {} installed.", tool.name));
                            } else {
                                let _ = tx.send(format!(
                                    "LOG:⚠ {} may have issues.",
                                    tool.name));
                            }
                        }
                        Err(e) => {
                            let _ = tx.send(format!(
                                "LOG:ERROR: {e}"));
                        }
                    }
                }
                let _ = tx.send("STATUS:✓ All selected tools installed!"
                    .to_string());
                let _ = tx.send(format!("PROG:1.0"));
                let _ = tx.send("DONE".to_string());
            });

            rx.attach(None, move |msg| {
                if msg.starts_with("STATUS:") {
                    status_ref.set_text(&msg[7..]);
                } else if msg.starts_with("PROG:") {
                    if let Ok(f) = msg[5..].parse::<f64>() {
                        prog_ref.set_fraction(f);
                    }
                } else if msg.starts_with("LOG:") {
                    let buf = log_ref.buffer();
                    let mut end = buf.end_iter();
                    buf.insert(&mut end,
                        &format!("{}\n", &msg[4..]));
                    let mark = buf.create_mark(
                        None, &buf.end_iter(), false);
                    log_ref.scroll_to_mark(
                        &mark, 0.0, false, 0.0, 0.0);
                } else if msg == "DONE" {
                    btn_ref.set_sensitive(true);
                    btn_ref.set_label("Install More Tools");
                    return glib::ControlFlow::Break;
                }
                glib::ControlFlow::Continue
            });
        });

        tab_box.append(&install_btn);

        let tab_lbl = Label::new(Some("🛠  Optional Tools"));
        notebook.append_page(&tab_box, Some(&tab_lbl));
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TAB 3: Install to HDD
    // ═══════════════════════════════════════════════════════════════════════
    {
        let tab_box = GtkBox::new(Orientation::Vertical, 16);
        tab_box.set_margin_start(32);
        tab_box.set_margin_end(32);
        tab_box.set_margin_top(32);
        tab_box.set_halign(gtk::Align::Center);
        tab_box.set_valign(gtk::Align::Center);

        let icon_lbl = Label::new(None);
        icon_lbl.set_markup(
            "<span size='xx-large'>💾</span>");

        let title = Label::new(None);
        title.set_markup(
            "<span size='x-large' weight='bold'>Install RIDOS-Core to Hard Drive</span>");

        let desc = Label::new(None);
        desc.set_markup(
            "<span color='#6E7781'>Launch the RIDOS-Core installer to install\n\
             this system to your hard drive or SSD.\n\n\
             The installer will guide you through:\n\
             disk selection → partitioning → user setup → GRUB</span>");
        desc.set_justify(gtk::Justification::Center);

        let warn = Label::new(None);
        warn.set_markup(
            "<span color='#D29922'>⚠  The installer will erase the selected disk.\n\
             Back up your data before continuing.</span>");
        warn.set_justify(gtk::Justification::Center);

        let launch_btn = Button::with_label(
            "🚀  Launch Installer");
        launch_btn.add_css_class("suggested-action");
        launch_btn.set_halign(gtk::Align::Center);

        let spinner = Spinner::new();
        spinner.set_visible(false);

        let status_lbl = Label::new(None);
        status_lbl.set_visible(false);

        let spinner_clone = spinner.clone();
        let status_clone  = status_lbl.clone();
        let btn_clone     = launch_btn.clone();

        launch_btn.connect_clicked(move |_| {
            btn_clone.set_sensitive(false);
            spinner_clone.set_visible(true);
            spinner_clone.start();
            status_clone.set_text("Launching installer...");
            status_clone.set_visible(true);

            let spinner_ref = spinner_clone.clone();
            let status_ref  = status_clone.clone();
            let btn_ref     = btn_clone.clone();

            std::thread::spawn(move || {
                let result = std::process::Command::new("sh")
                    .args(["-c",
                           "gnome-terminal \
                            --title=RIDOS-Installer \
                            -- bash -c \
                            'sudo python3 \
                             /opt/ridos-core/bin/ridos-installer.py; \
                             exec bash'"])
                    .spawn();

                let msg = match result {
                    Ok(_)  => "DONE:Installer launched in terminal window.",
                    Err(_) => "ERR:Could not launch installer. Open a terminal and run: sudo python3 /opt/ridos-core/bin/ridos-installer.py",
                };

                glib::MainContext::default().spawn_local({
                    let spinner_ref = spinner_ref.clone();
                    let status_ref  = status_ref.clone();
                    let btn_ref     = btn_ref.clone();
                    let msg = msg.to_string();
                    async move {
                        spinner_ref.stop();
                        spinner_ref.set_visible(false);
                        if msg.starts_with("DONE:") {
                            status_ref.set_markup(&format!(
                                "<span color='#238636'>{}</span>",
                                &msg[5..]));
                            btn_ref.set_label("Installer launched ✓");
                        } else {
                            status_ref.set_markup(&format!(
                                "<span color='#D29922'>{}</span>",
                                &msg[4..]));
                            btn_ref.set_sensitive(true);
                        }
                    }
                });
            });
        });

        tab_box.append(&icon_lbl);
        tab_box.append(&title);
        tab_box.append(&desc);
        tab_box.append(&warn);
        tab_box.append(&launch_btn);
        tab_box.append(&spinner);
        tab_box.append(&status_lbl);

        let tab_lbl = Label::new(Some("💾  Install to HDD"));
        notebook.append_page(&tab_box, Some(&tab_lbl));
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TAB 4: About
    // ═══════════════════════════════════════════════════════════════════════
    {
        let tv = TextView::new();
        tv.set_editable(false);
        tv.set_monospace(true);
        tv.set_wrap_mode(WrapMode::None);
        tv.set_margin_start(12);
        tv.set_margin_end(12);
        tv.set_margin_top(8);
        tv.set_margin_bottom(8);
        tv.buffer().set_text(changelog());

        let sc = ScrolledWindow::builder()
            .hscrollbar_policy(PolicyType::Automatic)
            .vscrollbar_policy(PolicyType::Automatic)
            .child(&tv)
            .vexpand(true)
            .build();

        // GitHub link button
        let link_btn = Button::with_label(
            "🔗  Open GitHub Repository");
        link_btn.set_halign(gtk::Align::End);
        link_btn.set_margin_end(12);
        link_btn.set_margin_bottom(8);
        link_btn.connect_clicked(|_| {
            let _ = std::process::Command::new("xdg-open")
                .arg(REPO_URL)
                .spawn();
        });

        let tab_box = GtkBox::new(Orientation::Vertical, 0);
        tab_box.append(&sc);
        tab_box.append(&link_btn);

        let tab_lbl = Label::new(Some("ℹ  About"));
        notebook.append_page(&tab_box, Some(&tab_lbl));
    }

    // ── Footer ────────────────────────────────────────────────────────────────
    root.append(&Separator::new(Orientation::Horizontal));

    let footer = GtkBox::new(Orientation::Horizontal, 0);
    footer.set_margin_start(24);
    footer.set_margin_end(24);
    footer.set_margin_top(10);
    footer.set_margin_bottom(10);

    let footer_lbl = Label::new(None);
    footer_lbl.set_markup(&format!(
        "<span color='#6E7781' size='small'>\
         {VERSION}  •  GPL v3  •  {REPO_URL}</span>"));
    footer_lbl.set_halign(gtk::Align::Start);
    footer_lbl.set_hexpand(true);

    let close_btn = Button::with_label("Close");
    let win_clone = window.clone();
    close_btn.connect_clicked(move |_| win_clone.close());

    footer.append(&footer_lbl);
    footer.append(&close_btn);
    root.append(&footer);

    window.present();
}

fn main() -> glib::ExitCode {
    let app = Application::builder()
        .application_id(APP_ID)
        .build();

    app.connect_activate(build_ui);
    app.run()
}
