#!/usr/bin/env python3
"""
ridos-installer.py — RIDOS-Core 1.0 Nova
Custom GTK3 installer. Replaces Calamares entirely.
Run as: sudo python3 /opt/ridos-core/bin/ridos-installer.py
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import os, sys, subprocess, threading, re

VERSION = "RIDOS-Core 1.0 Nova"

# ── Helpers ───────────────────────────────────────────────────────────────────
def run(cmd, timeout=300):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), 1

def run_log(cmd, log_fn, timeout=600):
    try:
        p = subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             text=True)
        for line in p.stdout:
            GLib.idle_add(log_fn, line.rstrip())
        p.wait()
        return p.returncode
    except Exception as e:
        GLib.idle_add(log_fn, f"ERROR: {e}")
        return 1

def get_disks():
    """
    Robust disk detection — tries multiple methods.
    Returns list of (device_path, display_label) tuples.
    """
    disks = []

    # Method 1: lsblk with JSON (preferred)
    out, rc = run("lsblk -J -b -o NAME,SIZE,TYPE,MODEL,HOTPLUG 2>/dev/null")
    if rc == 0 and out:
        try:
            import json
            data = json.loads(out)
            for dev in data.get('blockdevices', []):
                if dev.get('type') != 'disk':
                    continue
                name  = dev.get('name', '')
                model = (dev.get('model') or '').strip()
                size_b = int(dev.get('size') or 0)
                size_gb = round(size_b / (1024**3), 1)
                label = f"{model or name}  [{size_gb} GB]"
                disks.append((f"/dev/{name}", label))
            if disks:
                return disks
        except Exception:
            pass

    # Method 2: lsblk plain text fallback
    out, rc = run("lsblk -d -o NAME,SIZE,TYPE,MODEL 2>/dev/null | grep disk")
    if rc == 0 and out:
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 1:
                name  = parts[0].strip()
                size  = parts[1].strip() if len(parts) > 1 else '?'
                model = ' '.join(parts[3:]).strip() if len(parts) > 3 else name
                disks.append((f"/dev/{name}", f"{model}  [{size}]"))
        if disks:
            return disks

    # Method 3: /proc/partitions raw fallback
    out, _ = run("cat /proc/partitions 2>/dev/null")
    for line in out.splitlines()[2:]:
        parts = line.split()
        if len(parts) == 4:
            name = parts[3]
            # Only whole disks (no numbers at end, no loop/ram)
            if re.match(r'^(sd[a-z]|vd[a-z]|nvme\d+n\d+|hd[a-z])$', name):
                blocks = int(parts[2])
                size_gb = round(blocks / (1024**2), 1)
                disks.append((f"/dev/{name}", f"{name}  [{size_gb} GB]"))

    return disks

def is_efi():
    return os.path.exists('/sys/firmware/efi')

def get_timezones():
    out, _ = run("timedatectl list-timezones 2>/dev/null")
    tzs = [t for t in out.splitlines() if t.strip()]
    return tzs if tzs else [
        'Asia/Baghdad', 'Asia/Dubai', 'Asia/Riyadh',
        'UTC', 'Europe/London', 'Europe/Berlin',
        'America/New_York', 'America/Los_Angeles',
    ]

# ── Installer Window ──────────────────────────────────────────────────────────
class Installer(Gtk.Window):

    STEPS = ['Welcome', 'Disk', 'Account', 'Timezone', 'Confirm', 'Install', 'Done']

    def __init__(self):
        super().__init__(title=f"Install {VERSION}")
        self.set_default_size(740, 540)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect('delete-event', self._on_close)

        # State
        self.step     = 0
        self.disk     = ''
        self.username = 'myuser'
        self.password = ''
        self.hostname = 'ridos-core'
        self.timezone = 'Asia/Baghdad'
        self.efi      = is_efi()

        self._build_ui()
        self._go(0)

    def _on_close(self, *_):
        if self.step == 5:
            return True  # block close during install
        Gtk.main_quit()

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        # Header
        hdr = Gtk.Box(spacing=0)
        hdr.set_margin_start(24); hdr.set_margin_end(24)
        hdr.set_margin_top(14);   hdr.set_margin_bottom(14)
        self.h_title = Gtk.Label()
        self.h_step  = Gtk.Label()
        hdr.pack_start(self.h_title, True, True, 0)
        hdr.pack_end(self.h_step, False, False, 0)
        root.pack_start(hdr, False, False, 0)
        root.pack_start(Gtk.Separator(), False, False, 0)

        # Content area
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.body.set_margin_start(32); self.body.set_margin_end(32)
        self.body.set_margin_top(20);   self.body.set_margin_bottom(8)
        root.pack_start(self.body, True, True, 0)
        root.pack_start(Gtk.Separator(), False, False, 0)

        # Nav buttons
        nav = Gtk.Box(spacing=12)
        nav.set_margin_start(32); nav.set_margin_end(32)
        nav.set_margin_top(12);   nav.set_margin_bottom(14)
        self.btn_back = Gtk.Button(label='← Back')
        self.btn_next = Gtk.Button(label='Next →')
        self.btn_next.get_style_context().add_class('suggested-action')
        self.btn_back.connect('clicked', lambda _: self._go(self.step - 1))
        self.btn_next.connect('clicked', self._on_next)
        nav.pack_start(self.btn_back, False, False, 0)
        nav.pack_end(self.btn_next, False, False, 0)
        root.pack_start(nav, False, False, 0)

    def _clear(self):
        for c in self.body.get_children():
            self.body.remove(c)

    def _go(self, n):
        self._clear()
        self.step = n
        self.h_title.set_markup(
            f'<b><span size="large" color="#1F6FEB">{VERSION}</span></b>')
        self.h_step.set_markup(
            f'<span color="#888">Step {n+1}/{len(self.STEPS)}: '
            f'<b>{self.STEPS[n]}</b></span>')
        self.btn_back.set_sensitive(0 < n < 5)
        self.btn_next.set_sensitive(n < 5)
        [self._s0, self._s1, self._s2, self._s3,
         self._s4, self._s5, self._s6][n]()
        self.body.show_all()

    def _on_next(self, _):
        if not self._validate():
            return
        if self.step == 4:
            self._go(5)
            threading.Thread(target=self._do_install, daemon=True).start()
        elif self.step < len(self.STEPS) - 1:
            self._go(self.step + 1)

    def _validate(self):
        if self.step == 1:
            if not self.disk:
                self._err('Please select a disk to install on.')
                return False
        if self.step == 2:
            u  = self._ue.get_text().strip()
            p  = self._pe.get_text()
            p2 = self._p2e.get_text()
            h  = self._he.get_text().strip()
            if not re.match(r'^[a-z][a-z0-9_-]{0,30}$', u):
                self._err('Username must start with a lowercase letter.\nOnly lowercase letters, numbers, - and _ allowed.')
                return False
            if len(p) < 4:
                self._err('Password must be at least 4 characters.')
                return False
            if p != p2:
                self._err('Passwords do not match.')
                return False
            self.username = u
            self.password = p
            self.hostname = h if h else 'ridos-core'
        if self.step == 3:
            self.timezone = self._tzc.get_active_text() or 'Asia/Baghdad'
        return True

    def _err(self, msg):
        d = Gtk.MessageDialog(transient_for=self, modal=True,
                              message_type=Gtk.MessageType.ERROR,
                              buttons=Gtk.ButtonsType.OK, text=msg)
        d.run(); d.destroy()

    def _lbl(self, txt, markup=False, top=0, color=None):
        l = Gtk.Label()
        if markup:
            l.set_markup(txt)
        else:
            if color:
                l.set_markup(f'<span color="{color}">{txt}</span>')
            else:
                l.set_text(txt)
        l.set_halign(Gtk.Align.START)
        l.set_margin_top(top)
        l.set_line_wrap(True)
        return l

    # ── Step 0: Welcome ───────────────────────────────────────────────────────
    def _s0(self):
        self.body.pack_start(
            self._lbl('<span size="x-large" weight="bold" color="#1F6FEB">'
                      f'Welcome to {VERSION}</span>', markup=True), False, False, 0)
        self.body.pack_start(
            self._lbl('Rust-Ready Linux — Built for the next generation',
                      color='#888', top=4), False, False, 0)

        mode = 'UEFI (EFI)' if self.efi else 'Legacy BIOS'
        for text, is_warn in [
            (f'• Debian 12 Bookworm base with Linux 6.12 LTS', False),
            (f'• GNOME desktop with fast zstd boot', False),
            (f'• Brave Browser + Pro IT security toolkit pre-installed', False),
            (f'• Boot mode detected: {mode}', False),
            ('', False),
            ('⚠  WARNING: The selected disk will be completely erased.', True),
            ('⚠  Back up your data before continuing.', True),
        ]:
            if not text:
                self.body.pack_start(Gtk.Label(label=''), False, False, 2)
                continue
            l = self._lbl(text, top=6)
            if is_warn:
                l.set_markup(f'<span color="#D29922">{text}</span>')
            self.body.pack_start(l, False, False, 0)

        self.btn_next.set_label('Start Installation →')

    # ── Step 1: Disk selection ─────────────────────────────────────────────
    def _s1(self):
        self.body.pack_start(
            self._lbl('<b><span size="large">Select Installation Disk</span></b>',
                      markup=True), False, False, 0)
        self.body.pack_start(
            self._lbl('⚠  The selected disk will be completely erased.',
                      color='#D29922', top=6), False, False, 0)

        disks = get_disks()

        if not disks:
            # Show diagnostic info when no disks found
            self.body.pack_start(
                self._lbl('\n❌  No disks detected.', color='#DA3633', top=16),
                False, False, 0)
            out, _ = run('lsblk 2>&1 || echo "lsblk not available"')
            tv = Gtk.TextView()
            tv.set_editable(False)
            tv.set_monospace(True)
            tv.get_buffer().set_text(
                'lsblk output:\n' + out + '\n\n'
                'If you are in VirtualBox:\n'
                '  1. Make sure the VM has a virtual hard disk attached\n'
                '  2. Storage > Add Hard Disk in VM settings\n'
                '  3. Minimum 20GB recommended\n\n'
                'If on real hardware, check that the disk is connected\n'
                'and powered on.')
            sc = Gtk.ScrolledWindow()
            sc.set_min_content_height(180)
            sc.add(tv)
            self.body.pack_start(sc, True, True, 16)

            # Refresh button
            btn = Gtk.Button(label='🔄  Refresh disk list')
            btn.connect('clicked', lambda _: self._go(1))
            self.body.pack_start(btn, False, False, 8)
            return

        # Show disk radio buttons
        first = None
        for dev, label in disks:
            rb = Gtk.RadioButton(label=f'{dev}   —   {label}')
            if first is None:
                first = rb
                if not self.disk:
                    self.disk = dev
            else:
                rb.join_group(first)
            if self.disk == dev:
                rb.set_active(True)
            rb.connect('toggled',
                       lambda w, d=dev: setattr(self, 'disk', d) if w.get_active() else None)
            rb.set_margin_top(8)
            self.body.pack_start(rb, False, False, 0)

        self.btn_next.set_label('Next →')

    # ── Step 2: Account ───────────────────────────────────────────────────────
    def _s2(self):
        self.body.pack_start(
            self._lbl('<b><span size="large">Create Your Account</span></b>',
                      markup=True), False, False, 0)

        grid = Gtk.Grid(row_spacing=12, column_spacing=16)
        grid.set_margin_top(16)

        def row(i, label_text, widget):
            lbl = Gtk.Label(label=label_text)
            lbl.set_halign(Gtk.Align.END)
            grid.attach(lbl, 0, i, 1, 1)
            grid.attach(widget, 1, i, 1, 1)
            widget.set_hexpand(True)

        self._ue  = Gtk.Entry(); self._ue.set_text(self.username)
        self._ue.set_placeholder_text('lowercase letters only')
        self._pe  = Gtk.Entry(); self._pe.set_visibility(False)
        self._pe.set_placeholder_text('minimum 4 characters')
        self._p2e = Gtk.Entry(); self._p2e.set_visibility(False)
        self._p2e.set_placeholder_text('repeat password')
        self._he  = Gtk.Entry(); self._he.set_text(self.hostname)

        row(0, 'Username:',         self._ue)
        row(1, 'Password:',         self._pe)
        row(2, 'Confirm password:', self._p2e)
        row(3, 'Computer name:',    self._he)

        self.body.pack_start(grid, False, False, 0)

    # ── Step 3: Timezone ──────────────────────────────────────────────────────
    def _s3(self):
        self.body.pack_start(
            self._lbl('<b><span size="large">Select Timezone</span></b>',
                      markup=True), False, False, 0)

        tzs = get_timezones()
        self._tzc = Gtk.ComboBoxText()
        self._tzc.set_margin_top(16)
        sel = 0
        for i, tz in enumerate(tzs):
            self._tzc.append_text(tz)
            if tz == self.timezone:
                sel = i
        self._tzc.set_active(sel)
        self.body.pack_start(self._tzc, False, False, 0)

    # ── Step 4: Confirm ───────────────────────────────────────────────────────
    def _s4(self):
        self.body.pack_start(
            self._lbl('<b><span size="large">Ready to Install</span></b>',
                      markup=True), False, False, 0)
        self.body.pack_start(
            self._lbl('Review your choices. Click Install Now to begin.',
                      color='#666', top=4), False, False, 0)

        grid = Gtk.Grid(row_spacing=10, column_spacing=24)
        grid.set_margin_top(20)
        details = [
            ('OS',        VERSION),
            ('Disk',      f'{self.disk}   ⚠  WILL BE ERASED'),
            ('Boot mode', 'UEFI' if self.efi else 'BIOS/MBR'),
            ('Username',  self.username),
            ('Hostname',  self.hostname),
            ('Timezone',  self.timezone),
        ]
        for i, (k, v) in enumerate(details):
            kl = Gtk.Label(); kl.set_markup(f'<b>{k}:</b>')
            kl.set_halign(Gtk.Align.END)
            vl = Gtk.Label(label=v); vl.set_halign(Gtk.Align.START)
            if 'ERASED' in v:
                vl.set_markup(f'<span color="#DA3633" weight="bold">{v}</span>')
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        self.body.pack_start(grid, False, False, 0)

        self.btn_next.set_label('⚠  Install Now')
        self.btn_next.get_style_context().add_class('destructive-action')

    # ── Step 5: Installing ────────────────────────────────────────────────────
    def _s5(self):
        self.btn_back.set_sensitive(False)
        self.btn_next.set_sensitive(False)

        self.body.pack_start(
            self._lbl('<b><span size="large">Installing RIDOS-Core...</span></b>',
                      markup=True), False, False, 0)
        self.body.pack_start(
            self._lbl('Do not power off. This will take 5-15 minutes.',
                      color='#888', top=4), False, False, 0)

        self._prog = Gtk.ProgressBar()
        self._prog.set_margin_top(12); self._prog.set_margin_bottom(4)
        self.body.pack_start(self._prog, False, False, 0)

        self._slbl = Gtk.Label(label='Preparing...')
        self._slbl.set_halign(Gtk.Align.START)
        self.body.pack_start(self._slbl, False, False, 4)

        sc = Gtk.ScrolledWindow()
        sc.set_min_content_height(260)
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._logbuf = Gtk.TextBuffer()
        tv = Gtk.TextView(buffer=self._logbuf)
        tv.set_editable(False); tv.set_monospace(True)
        sc.add(tv)
        self.body.pack_start(sc, True, True, 0)

    def _log(self, msg):
        end = self._logbuf.get_end_iter()
        self._logbuf.insert(end, msg + '\n')

    def _status(self, msg, frac):
        GLib.idle_add(self._slbl.set_text, msg)
        GLib.idle_add(self._prog.set_fraction, frac)

    # ── Step 6: Done ─────────────────────────────────────────────────────────
    def _s6(self):
        self.btn_back.set_sensitive(False)
        self.btn_next.set_sensitive(True)
        self.btn_next.set_label('🔄  Reboot Now')
        self.btn_next.get_style_context().remove_class('destructive-action')
        self.btn_next.connect('clicked', lambda _: run('reboot'))

        self.body.pack_start(
            self._lbl('<span size="xx-large" weight="bold" color="#238636">'
                      '✓  Installation Complete!</span>', markup=True),
            False, False, 0)
        self.body.pack_start(
            self._lbl(f'\n{VERSION} has been installed successfully.\n'
                      f'Remove the USB/CD and click Reboot Now.',
                      top=12), False, False, 0)

    # ── Installation logic ────────────────────────────────────────────────────
    def _do_install(self):
        disk = self.disk
        efi  = self.efi
        user = self.username
        pw   = self.password
        host = self.hostname
        tz   = self.timezone

        # Determine partition names (handle NVMe: nvme0n1p1 not nvme0n11)
        if 'nvme' in disk or 'mmcblk' in disk:
            p1 = disk + 'p1'
            p2 = disk + 'p2'
        else:
            p1 = disk + '1'
            p2 = disk + '2'

        self._status('Unmounting any existing mounts on target disk...', 0.02)
        run(f'umount {disk}* 2>/dev/null || true')
        run('umount /mnt/boot/efi 2>/dev/null || true')
        run('umount /mnt 2>/dev/null || true')

        # ── Partition ─────────────────────────────────────────────────────────
        self._status('Partitioning disk...', 0.05)
        if efi:
            GLib.idle_add(self._log, f'Partitioning {disk} as GPT (EFI)...')
            run(f'parted -s {disk} mklabel gpt')
            run(f'parted -s {disk} mkpart primary fat32 1MiB 513MiB')
            run(f'parted -s {disk} set 1 esp on')
            run(f'parted -s {disk} mkpart primary ext4 513MiB 100%')
            self._status('Formatting partitions...', 0.08)
            run(f'mkfs.fat -F32 {p1}')
            run(f'mkfs.ext4 -F {p2}')
            self._status('Mounting partitions...', 0.10)
            run(f'mount {p2} /mnt')
            run('mkdir -p /mnt/boot/efi')
            run(f'mount {p1} /mnt/boot/efi')
            root_part = p2
            efi_part  = p1
        else:
            GLib.idle_add(self._log, f'Partitioning {disk} as MBR (BIOS)...')
            run(f'parted -s {disk} mklabel msdos')
            run(f'parted -s {disk} mkpart primary ext4 1MiB 100%')
            run(f'parted -s {disk} set 1 boot on')
            self._status('Formatting partition...', 0.08)
            run(f'mkfs.ext4 -F {p1}')
            self._status('Mounting partition...', 0.10)
            run(f'mount {p1} /mnt')
            root_part = p1
            efi_part  = None

        # ── Extract filesystem ────────────────────────────────────────────────
        self._status('Extracting filesystem (this takes several minutes)...', 0.12)
        squashfs_paths = [
            '/run/live/medium/live/filesystem.squashfs',
            '/run/live/rootfs/filesystem.squashfs',
            '/lib/live/mount/medium/live/filesystem.squashfs',
            '/cdrom/live/filesystem.squashfs',
            '/run/initramfs/live/filesystem.squashfs',
        ]
        sq = next((p for p in squashfs_paths if os.path.exists(p)), '')
        if sq:
            GLib.idle_add(self._log, f'Extracting: {sq}')
            rc = run_log(f'unsquashfs -f -d /mnt {sq}', self._log)
            if rc != 0:
                GLib.idle_add(self._log, 'unsquashfs failed — trying rsync...')
                run_log(
                    'rsync -aAX --delete '
                    '--exclude={"/proc/*","/sys/*","/dev/*","/tmp/*",'
                    '"/run/*","/mnt/*","/media/*","/lost+found"} / /mnt/',
                    self._log)
        else:
            GLib.idle_add(self._log, 'squashfs not found — using rsync...')
            run_log(
                'rsync -aAX --delete '
                '--exclude={"/proc/*","/sys/*","/dev/*","/tmp/*",'
                '"/run/*","/mnt/*","/media/*","/lost+found"} / /mnt/',
                self._log)

        # ── fstab ─────────────────────────────────────────────────────────────
        self._status('Writing fstab...', 0.62)
        root_uuid, _ = run(f'blkid -s UUID -o value {root_part}')
        root_uuid = root_uuid.strip()
        fstab  = f'UUID={root_uuid} / ext4 defaults,errors=remount-ro 0 1\n'
        fstab += 'tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=2G 0 0\n'
        if efi_part:
            efi_uuid, _ = run(f'blkid -s UUID -o value {efi_part}')
            fstab += f'UUID={efi_uuid.strip()} /boot/efi vfat umask=0077 0 1\n'
        open('/mnt/etc/fstab', 'w').write(fstab)
        GLib.idle_add(self._log, 'fstab written')

        # ── Hostname and timezone ─────────────────────────────────────────────
        self._status(f'Setting hostname and timezone...', 0.65)
        open('/mnt/etc/hostname', 'w').write(host + '\n')
        hosts_content = '127.0.0.1 localhost\n127.0.1.1 ' + host + '\n'
        open('/mnt/etc/hosts', 'w').write(hosts_content)
        run(f'ln -sf /usr/share/zoneinfo/{tz} /mnt/etc/localtime')
        open('/mnt/etc/timezone', 'w').write(tz + '\n')

        # ── Create user ───────────────────────────────────────────────────────
        self._status(f'Creating user {user}...', 0.68)
        run(f'for d in dev proc sys run; do mount --bind /$d /mnt/$d 2>/dev/null || true; done')
        run(f'chroot /mnt useradd -m -s /bin/bash '
            f'-G sudo,audio,video,netdev,plugdev {user} 2>/dev/null || true')
        run(f'echo "{user}:{pw}" | chroot /mnt chpasswd')
        run(f'echo "{user} ALL=(ALL) ALL" > /mnt/etc/sudoers.d/{user}')
        run(f'chmod 440 /mnt/etc/sudoers.d/{user}')

        # Remove live autologin — user should log in with their own credentials
        gdm_conf = '/mnt/etc/gdm3/custom.conf'
        if os.path.exists(gdm_conf):
            content = open(gdm_conf).read()
            content = re.sub(r'AutomaticLoginEnable\s*=.*\n', '', content)
            content = re.sub(r'AutomaticLogin\s*=.*\n', '', content)
            open(gdm_conf, 'w').write(content)

        # Remove live installer shortcut from installed system's autostart
        for f in [
            '/mnt/etc/xdg/autostart/ridos-installer.desktop',
            f'/mnt/home/{user}/.config/autostart/ridos-installer.desktop',
        ]:
            run(f'rm -f {f} 2>/dev/null || true')

        # ── GRUB ─────────────────────────────────────────────────────────────
        self._status('Installing GRUB bootloader...', 0.78)
        if efi:
            rc = run_log(
                f'chroot /mnt grub-install --target=x86_64-efi '
                f'--efi-directory=/boot/efi '
                f'--bootloader-id=RIDOS-Core --recheck {disk}',
                self._log)
        else:
            rc = run_log(
                f'chroot /mnt grub-install --target=i386-pc '
                f'--recheck {disk}',
                self._log)

        self._status('Generating GRUB config...', 0.86)
        run_log('chroot /mnt update-grub', self._log)

        # ── Remove live packages from installed system ─────────────────────
        self._status('Removing live packages...', 0.91)
        run('chroot /mnt apt-get remove -y '
            'live-boot live-boot-initramfs-tools 2>/dev/null || true')

        # ── Unmount ──────────────────────────────────────────────────────────
        self._status('Unmounting...', 0.96)
        run('for d in run sys proc dev; do umount /mnt/$d 2>/dev/null || true; done')
        run('umount /mnt/boot/efi 2>/dev/null || true')
        run('umount /mnt 2>/dev/null || true')

        self._status('Installation complete!', 1.0)
        GLib.idle_add(self._go, 6)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if os.geteuid() != 0:
        # Re-launch with sudo
        os.execvp('sudo', ['sudo', '--'] + sys.argv)
    app = Installer()
    app.connect('destroy', Gtk.main_quit)
    app.show_all()
    Gtk.main()
