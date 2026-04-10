// ridos-welcome — RIDOS-Core 1.0 Nova Welcome Application
// Rust + GTK4 (gtk4-rs 0.7 via cargo/crates.io)
// Tabs: System Info | Optional Tools | Install to HDD | About

use gtk::prelude::*;
use gtk::{
    glib,
    Application, ApplicationWindow,
    Box as GtkBox, Button, CheckButton, Label,
    Notebook, Orientation, PolicyType,
    ProgressBar, ScrolledWindow, Separator,
    Spinner, TextView, WrapMode,
};
use std::cell::RefCell;
use std::rc::Rc;

const APP_ID:   &str = "com.ridos.welcome";
const VERSION:  &str = "RIDOS-Core 1.0 Nova";
const REPO_URL: &str = "https://github.com/alkinanireyad/RIDOS-Core";

// ── Optional tools ────────────────────────────────────────────────────────────
#[derive(Clone)]
struct Tool {
    name: &'static str,
    desc: &'static str,
    cmd:  &'static str,
    tier: &'static str,
}

fn tools() -> Vec<Tool> {
    vec![
        Tool { name: "Timeshift",
               desc: "System snapshots and restore — recommended for all users",
               cmd:  "pkexec apt-get install -y timeshift",
               tier: "Recommended" },
        Tool { name: "Flatpak + Flathub",
               desc: "Sandboxed app store with thousands of apps",
               cmd:  "pkexec apt-get install -y flatpak gnome-software-plugin-flatpak",
               tier: "Recommended" },
        Tool { name: "Firmware Updater (fwupd)",
               desc: "Update BIOS, SSD, and peripheral firmware automatically",
               cmd:  "pkexec apt-get install -y fwupd",
               tier: "Recommended" },
        Tool { name: "Zram Compression",
               desc: "Compressed RAM swap — big performance gain on low-RAM systems",
               cmd:  "pkexec apt-get install -y zram-tools",
               tier: "Power User" },
        Tool { name: "TLP Battery Optimizer",
               desc: "Extends laptop battery life significantly",
               cmd:  "pkexec apt-get install -y tlp tlp-rdw",
               tier: "Power User" },
        Tool { name: "Cockpit Web Admin",
               desc: "Browser-based system monitoring at localhost:9090",
               cmd:  "pkexec apt-get install -y cockpit",
               tier: "Power User" },
        Tool { name: "Distrobox",
               desc: "Run any Linux distro inside a container",
               cmd:  "pkexec apt-get install -y distrobox",
               tier: "Power User" },
        Tool { name: "Rust Toolchain",
               desc: "Full Rust development environment via rustup",
               cmd:  "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y",
               tier: "Power User" },
        Tool { name: "WireGuard VPN",
               desc: "Fast, modern, kernel-native VPN",
               cmd:  "pkexec apt-get install -y wireguard wireguard-tools",
               tier: "Advanced" },
        Tool { name: "Ollama AI Assistant",
               desc: "Local offline AI — requires 4 GB+ RAM (2 GB download)",
               cmd:  "bash /opt/ridos-core/bin/install-ollama.sh",
               tier: "Advanced" },
        Tool { name: "Panic Key (Security)",
               desc: "Emergency RAM wipe and shutdown — Ctrl+Alt+Pause",
               cmd:  "pkexec python3 /opt/ridos-core/bin/panic-key.py --install",
               tier: "Advanced" },
    ]
}

// ── System info ───────────────────────────────────────────────────────────────
fn get_sysinfo() -> String {
    let mut lines = vec![
        format!("OS         :  {VERSION}"),
        format!("Repository :  {REPO_URL}"),
        "Kernel     :  Linux 6.12 LTS (CONFIG_RUST=y)".to_string(),
        String::new(),
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
        let parse_kb = |prefix: &str| -> String {
            meminfo.lines()
                .find(|l| l.starts_with(prefix))
                .and_then(|l| l.split_whitespace().nth(1))
                .and_then(|v| v.parse::<u64>().ok())
                .map(|kb| format!("{:.1} GB", kb as f64 / 1_048_576.0))
                .unwrap_or_else(|| "Unknown".to_string())
        };
        lines.push(format!("RAM Total  :  {}", parse_kb("MemTotal")));
        lines.push(format!("RAM Free   :  {}", parse_kb("MemAvailable")));
    }

    // Disk
    if let Ok(out) = std::process::Command::new("df")
        .args(["-h", "--output=source,size,used,avail,pcent,target",
               "-x", "tmpfs", "-x", "devtmpfs"])
        .output()
    {
        let text = String::from_utf8_lossy(&out.stdout);
        lines.push(String::new());
        lines.push("Disk Usage:".to_string());
        for line in text.lines() {
            lines.push(format!("  {line}"));
        }
    }

    // Boot mode
    lines.push(String::new());
    lines.push(format!("Boot Mode  :  {}",
        if std::path::Path::new("/sys/firmware/efi").exists()
            { "UEFI" } else { "BIOS/MBR" }));

    // WiFi interfaces
    if let Ok(out) = std::process::Command::new("iw").args(["dev"]).output() {
        let text = String::from_utf8_lossy(&out.stdout);
        let ifaces: Vec<&str> = text.lines()
            .filter(|l| l.trim().starts_with("Interface"))
            .filter_map(|l| l.split_whitespace().nth(1))
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
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEW in 1.0 Nova
───────────────
• First stable release of RIDOS-Core
• Linux 6.12 LTS with Rust kernel support (CONFIG_RUST=y)
• GNOME desktop — Xorg default, Wayland available
• Brave Browser as primary browser (privacy-first)
• Firefox-ESR as fallback browser
• Full Pro IT toolkit pre-installed:
    Network   : nmap, wireshark, tcpdump, mtr, iperf3
    Security  : aircrack-ng, john, hydra, hashcat, nikto
    Monitoring: htop, btop, iotop, nethogs, ncdu
    DevOps    : docker, ansible, git
    Recovery  : testdisk, gddrescue, gparted
• Custom GTK3 installer (replaces Calamares)
• WiFi drivers for 2008-2025 hardware:
    Intel (iwlwifi), Atheros, Realtek, MediaTek, Broadcom
• zstd squashfs compression for fast boot
• VS Code pre-installed
• This welcome app built in Rust + GTK4

ARCHITECTURE
────────────
Base      : Debian 12 Bookworm
Kernel    : Linux 6.12 LTS
Desktop   : GNOME 43
Installer : ridos-installer.py (custom GTK3)
Welcome   : ridos-welcome (Rust + GTK4)
License   : GNU GPL v3

ROADMAP
───────
v1.1  — Panic Key v2.0, Rust coreutils (uutils)
v2.0  — Linux 7.0 kernel, Rust init system
v3.0  — Full Rust system stack, hardware certification

REPOSITORY
──────────
https://github.com/alkinanireyad/RIDOS-Core"
}

// ── Build UI ──────────────────────────────────────────────────────────────────
fn build_ui(app: &Application) {
    let window = ApplicationWindow::builder()
        .application(app)
        .title(&format!("Welcome to {VERSION}"))
        .default_width(820)
        .default_height(600)
        .build();

    let root = GtkBox::new(Orientation::Vertical, 0);
    window.set_child(Some(&root));

    // Header
    let hdr = GtkBox::new(Orientation::Horizontal, 0);
    hdr.set_margin_start(24); hdr.set_margin_end(24);
    hdr.set_margin_top(14);   hdr.set_margin_bottom(14);

    let title_lbl = Label::new(None);
    title_lbl.set_markup(&format!(
        "<span size='x-large' weight='bold' color='#1F6FEB'>{VERSION}</span>"));
    title_lbl.set_halign(gtk::Align::Start);
    title_lbl.set_hexpand(true);

    let sub_lbl = Label::new(None);
    sub_lbl.set_markup("<span color='#6E7781'>Rust-Ready Linux</span>");
    sub_lbl.set_halign(gtk::Align::End);

    hdr.append(&title_lbl);
    hdr.append(&sub_lbl);
    root.append(&hdr);
    root.append(&Separator::new(Orientation::Horizontal));

    // Notebook
    let nb = Notebook::new();
    nb.set_vexpand(true);
    nb.set_margin_top(8); nb.set_margin_bottom(8);
    nb.set_margin_start(8); nb.set_margin_end(8);
    root.append(&nb);

    // ── TAB 1: System Info ────────────────────────────────────────────────────
    {
        let tv = TextView::new();
        tv.set_editable(false);
        tv.set_monospace(true);
        tv.set_wrap_mode(WrapMode::None);
        tv.set_margin_start(12); tv.set_margin_end(12);
        tv.set_margin_top(8);    tv.set_margin_bottom(8);
        tv.buffer().set_text(&get_sysinfo());

        let sc = ScrolledWindow::builder()
            .hscrollbar_policy(PolicyType::Automatic)
            .vscrollbar_policy(PolicyType::Automatic)
            .child(&tv)
            .vexpand(true)
            .build();

        let refresh = Button::with_label("🔄  Refresh");
        refresh.set_halign(gtk::Align::End);
        refresh.set_margin_end(12);
        refresh.set_margin_bottom(8);
        let tv_c = tv.clone();
        refresh.connect_clicked(move |_| {
            tv_c.buffer().set_text(&get_sysinfo());
        });

        let tab = GtkBox::new(Orientation::Vertical, 0);
        tab.append(&sc);
        tab.append(&refresh);
        nb.append_page(&tab, Some(&Label::new(Some("💻  System Info"))));
    }

    // ── TAB 2: Optional Tools ─────────────────────────────────────────────────
    {
        let tab = GtkBox::new(Orientation::Vertical, 0);
        tab.set_margin_start(16); tab.set_margin_end(16);
        tab.set_margin_top(12);

        let intro = Label::new(None);
        intro.set_markup(
            "<span color='#6E7781'>Select optional tools to install. \
             Core system tools are already pre-installed.</span>");
        intro.set_halign(gtk::Align::Start);
        intro.set_margin_bottom(12);
        tab.append(&intro);

        let tools_box = GtkBox::new(Orientation::Vertical, 4);
        let checks: Rc<RefCell<Vec<(CheckButton, Tool)>>> =
            Rc::new(RefCell::new(Vec::new()));

        let mut cur_tier = "";
        for tool in tools() {
            if tool.tier != cur_tier {
                cur_tier = tool.tier;
                let color = match cur_tier {
                    "Recommended" => "#238636",
                    "Power User"  => "#1F6FEB",
                    _             => "#8250DF",
                };
                let lbl = Label::new(None);
                lbl.set_markup(&format!(
                    "<b><span color='{color}'>── {cur_tier} ──</span></b>"));
                lbl.set_halign(gtk::Align::Start);
                lbl.set_margin_top(12);
                lbl.set_margin_bottom(2);
                tools_box.append(&lbl);
            }

            let row = GtkBox::new(Orientation::Horizontal, 12);
            row.set_margin_bottom(2);

            let cb = CheckButton::new();
            cb.set_active(cur_tier == "Recommended");

            let lbox = GtkBox::new(Orientation::Vertical, 1);

            let name_lbl = Label::new(None);
            name_lbl.set_markup(&format!("<b>{}</b>", tool.name));
            name_lbl.set_halign(gtk::Align::Start);

            let desc_lbl = Label::new(Some(tool.desc));
            desc_lbl.set_halign(gtk::Align::Start);
            desc_lbl.add_css_class("dim-label");

            lbox.append(&name_lbl);
            lbox.append(&desc_lbl);
            row.append(&cb);
            row.append(&lbox);
            tools_box.append(&row);

            checks.borrow_mut().push((cb, tool));
        }

        let sc = ScrolledWindow::builder()
            .hscrollbar_policy(PolicyType::Never)
            .vscrollbar_policy(PolicyType::Automatic)
            .child(&tools_box)
            .vexpand(true)
            .build();
        tab.append(&sc);

        // Progress widgets
        let prog  = ProgressBar::new();
        prog.set_margin_top(8);
        prog.set_visible(false);
        tab.append(&prog);

        let slbl = Label::new(None);
        slbl.set_halign(gtk::Align::Start);
        slbl.set_visible(false);
        tab.append(&slbl);

        let log_tv = TextView::new();
        log_tv.set_editable(false);
        log_tv.set_monospace(true);
        log_tv.set_wrap_mode(WrapMode::WordChar);
        log_tv.set_visible(false);

        let log_sc = ScrolledWindow::builder()
            .vscrollbar_policy(PolicyType::Automatic)
            .child(&log_tv)
            .min_content_height(120)
            .build();
        log_sc.set_visible(false);
        tab.append(&log_sc);

        // Install button
        let btn = Button::with_label("Install Selected Tools");
        btn.add_css_class("suggested-action");
        btn.set_margin_top(12);
        btn.set_margin_bottom(12);
        btn.set_halign(gtk::Align::End);

        let checks_c = Rc::clone(&checks);
        let prog_c   = prog.clone();
        let slbl_c   = slbl.clone();
        let log_tv_c = log_tv.clone();
        let log_sc_c = log_sc.clone();
        let btn_c    = btn.clone();

        btn.connect_clicked(move |_| {
            let selected: Vec<Tool> = checks_c.borrow()
                .iter()
                .filter(|(cb, _)| cb.is_active())
                .map(|(_, t)| t.clone())
                .collect();

            if selected.is_empty() {
                slbl_c.set_markup(
                    "<span color='#D29922'>No tools selected.</span>");
                slbl_c.set_visible(true);
                return;
            }

            btn_c.set_sensitive(false);
            prog_c.set_visible(true);
            prog_c.set_fraction(0.0);
            slbl_c.set_visible(true);
            log_tv_c.set_visible(true);
            log_sc_c.set_visible(true);

            let total = selected.len() as f64;
            // Use glib channel — correct way to communicate
            // from a background thread to GTK main thread
            let (tx, rx) = glib::MainContext::channel::<String>(
                glib::Priority::DEFAULT);

            std::thread::spawn(move || {
                for (i, tool) in selected.iter().enumerate() {
                    let _ = tx.send(format!(
                        "STATUS:Installing {} ({}/{})...",
                        tool.name, i + 1, selected.len()));
                    let _ = tx.send(format!(
                        "PROG:{:.3}", i as f64 / total));
                    let _ = tx.send(format!("LOG:$ {}", tool.cmd));

                    let result = std::process::Command::new("sh")
                        .args(["-c", tool.cmd])
                        .output();

                    match result {
                        Ok(out) => {
                            for line in
                                String::from_utf8_lossy(&out.stdout)
                                    .lines()
                                    .chain(String::from_utf8_lossy(
                                        &out.stderr).lines())
                            {
                                let _ = tx.send(
                                    format!("LOG:{line}"));
                            }
                            if out.status.success() {
                                let _ = tx.send(format!(
                                    "LOG:✓ {} done.", tool.name));
                            } else {
                                let _ = tx.send(format!(
                                    "LOG:⚠ {} may have issues \
                                     (exit {})",
                                    tool.name,
                                    out.status.code()
                                        .unwrap_or(-1)));
                            }
                        }
                        Err(e) => {
                            let _ = tx.send(
                                format!("LOG:ERROR: {e}"));
                        }
                    }
                }
                let _ = tx.send(
                    "STATUS:✓ All selected tools installed!".into());
                let _ = tx.send("PROG:1.0".into());
                let _ = tx.send("DONE".into());
            });

            // rx.attach runs on the GTK main thread — correct
            let prog_r   = prog_c.clone();
            let slbl_r   = slbl_c.clone();
            let log_tv_r = log_tv_c.clone();
            let btn_r    = btn_c.clone();

            rx.attach(None, move |msg| {
                if let Some(rest) = msg.strip_prefix("STATUS:") {
                    slbl_r.set_text(rest);
                } else if let Some(rest) = msg.strip_prefix("PROG:") {
                    if let Ok(f) = rest.parse::<f64>() {
                        prog_r.set_fraction(f);
                    }
                } else if let Some(rest) = msg.strip_prefix("LOG:") {
                    let buf  = log_tv_r.buffer();
                    let mut end = buf.end_iter();
                    buf.insert(&mut end, &format!("{rest}\n"));
                    let mark = buf.create_mark(
                        None, &buf.end_iter(), false);
                    log_tv_r.scroll_to_mark(
                        &mark, 0.0, false, 0.0, 0.0);
                } else if msg == "DONE" {
                    btn_r.set_sensitive(true);
                    btn_r.set_label("Install More Tools");
                    return glib::ControlFlow::Break;
                }
                glib::ControlFlow::Continue
            });
        });

        tab.append(&btn);
        nb.append_page(&tab, Some(&Label::new(
            Some("🛠  Optional Tools"))));
    }

    // ── TAB 3: Install to HDD ─────────────────────────────────────────────────
    {
        let tab = GtkBox::new(Orientation::Vertical, 16);
        tab.set_margin_start(32); tab.set_margin_end(32);
        tab.set_margin_top(32);
        tab.set_halign(gtk::Align::Center);
        tab.set_valign(gtk::Align::Center);

        let icon = Label::new(None);
        icon.set_markup("<span size='xx-large'>💾</span>");

        let title = Label::new(None);
        title.set_markup(
            "<span size='x-large' weight='bold'>\
             Install RIDOS-Core to Hard Drive</span>");

        let desc = Label::new(None);
        desc.set_markup(
            "<span color='#6E7781'>\
             Launch the RIDOS-Core installer to install\n\
             this system to your hard drive or SSD.\n\n\
             The installer guides you through:\n\
             disk selection → partitioning → user setup → GRUB\
             </span>");
        desc.set_justify(gtk::Justification::Center);

        let warn = Label::new(None);
        warn.set_markup(
            "<span color='#D29922'>\
             ⚠  The installer will erase the selected disk.\n\
             Back up your data before continuing.\
             </span>");
        warn.set_justify(gtk::Justification::Center);

        let launch_btn = Button::with_label("🚀  Launch Installer");
        launch_btn.add_css_class("suggested-action");
        launch_btn.set_halign(gtk::Align::Center);

        let spinner   = Spinner::new();
        spinner.set_visible(false);

        let status = Label::new(None);
        status.set_visible(false);

        // Use glib channel for thread → main thread communication
        let (tx, rx) = glib::MainContext::channel::<String>(
            glib::Priority::DEFAULT);

        let spinner_c = spinner.clone();
        let status_c  = status.clone();
        let btn_c     = launch_btn.clone();

        launch_btn.connect_clicked(move |_| {
            btn_c.set_sensitive(false);
            spinner_c.set_visible(true);
            spinner_c.start();
            status_c.set_text("Launching installer...");
            status_c.set_visible(true);

            let tx = tx.clone();
            std::thread::spawn(move || {
                let ok = std::process::Command::new("gnome-terminal")
                    .args(["--title=RIDOS-Installer",
                           "--",
                           "bash", "-c",
                           "sudo python3 \
                            /opt/ridos-core/bin/ridos-installer.py; \
                            exec bash"])
                    .spawn()
                    .is_ok();
                let _ = tx.send(if ok {
                    "DONE:Installer launched.".to_string()
                } else {
                    "ERR:Could not launch gnome-terminal. \
                     Open a terminal and run: \
                     sudo python3 \
                     /opt/ridos-core/bin/ridos-installer.py"
                     .to_string()
                });
            });
        });

        let spinner_r = spinner.clone();
        let status_r  = status.clone();
        let btn_r     = launch_btn.clone();

        rx.attach(None, move |msg| {
            spinner_r.stop();
            spinner_r.set_visible(false);
            if let Some(rest) = msg.strip_prefix("DONE:") {
                status_r.set_markup(&format!(
                    "<span color='#238636'>{rest}</span>"));
                btn_r.set_label("Installer launched ✓");
            } else if let Some(rest) = msg.strip_prefix("ERR:") {
                status_r.set_markup(&format!(
                    "<span color='#D29922'>{rest}</span>"));
                btn_r.set_sensitive(true);
            }
            glib::ControlFlow::Break
        });

        tab.append(&icon);
        tab.append(&title);
        tab.append(&desc);
        tab.append(&warn);
        tab.append(&launch_btn);
        tab.append(&spinner);
        tab.append(&status);

        nb.append_page(&tab,
            Some(&Label::new(Some("💾  Install to HDD"))));
    }

    // ── TAB 4: About ─────────────────────────────────────────────────────────
    {
        let tv = TextView::new();
        tv.set_editable(false);
        tv.set_monospace(true);
        tv.set_wrap_mode(WrapMode::None);
        tv.set_margin_start(12); tv.set_margin_end(12);
        tv.set_margin_top(8);    tv.set_margin_bottom(8);
        tv.buffer().set_text(changelog());

        let sc = ScrolledWindow::builder()
            .hscrollbar_policy(PolicyType::Automatic)
            .vscrollbar_policy(PolicyType::Automatic)
            .child(&tv)
            .vexpand(true)
            .build();

        let link = Button::with_label("🔗  Open GitHub Repository");
        link.set_halign(gtk::Align::End);
        link.set_margin_end(12);
        link.set_margin_bottom(8);
        link.connect_clicked(|_| {
            let _ = std::process::Command::new("xdg-open")
                .arg(REPO_URL).spawn();
        });

        let tab = GtkBox::new(Orientation::Vertical, 0);
        tab.append(&sc);
        tab.append(&link);

        nb.append_page(&tab,
            Some(&Label::new(Some("ℹ  About"))));
    }

    // Footer
    root.append(&Separator::new(Orientation::Horizontal));

    let footer = GtkBox::new(Orientation::Horizontal, 0);
    footer.set_margin_start(24); footer.set_margin_end(24);
    footer.set_margin_top(10);   footer.set_margin_bottom(10);

    let flbl = Label::new(None);
    flbl.set_markup(&format!(
        "<span color='#6E7781' size='small'>\
         {VERSION}  •  GPL v3  •  {REPO_URL}</span>"));
    flbl.set_halign(gtk::Align::Start);
    flbl.set_hexpand(true);

    let close = Button::with_label("Close");
    let win_c = window.clone();
    close.connect_clicked(move |_| win_c.close());

    footer.append(&flbl);
    footer.append(&close);
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
