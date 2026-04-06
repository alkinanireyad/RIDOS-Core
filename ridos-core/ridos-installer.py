#!/usr/bin/env python3
"""
ridos-installer.py — RIDOS-Core 1.0 Nova
Correct installation sequence:
  1. Partition + format
  2. Mount target
  3. Bind /dev /proc /sys /run into target  ← was missing before
  4. Extract squashfs into target
  5. Configure (fstab, hostname, timezone, user) inside chroot
  6. Install GRUB inside chroot
  7. Remove live packages inside chroot
  8. Unbind + unmount cleanly
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import os, sys, subprocess, threading, re, shutil

VERSION = "RIDOS-Core 1.0 Nova"

# ── Shell helpers ─────────────────────────────────────────────────────────────
def sh(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return '', str(e), 1

def sh_log(cmd, log_fn, timeout=1800):
    """Run command and stream output to log_fn via GLib.idle_add."""
    try:
        p = subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             text=True, bufsize=1)
        for line in p.stdout:
            line = line.rstrip()
            if line:
                GLib.idle_add(log_fn, line)
        p.wait()
        return p.returncode
    except Exception as e:
        GLib.idle_add(log_fn, f'ERROR: {e}')
        return 1

# ── System detection ──────────────────────────────────────────────────────────
def get_disks():
    disks = []
    # Method 1: lsblk JSON
    out, _, rc = sh('lsblk -J -b -o NAME,SIZE,TYPE,MODEL 2>/dev/null')
    if rc == 0:
        try:
            import json
            for d in json.loads(out).get('blockdevices', []):
                if d.get('type') == 'disk':
                    name  = d['name']
                    model = (d.get('model') or '').strip() or name
                    size  = int(d.get('size') or 0)
                    gb    = round(size / 1024**3, 1)
                    disks.append((f'/dev/{name}', f'{model}  [{gb} GB]', gb))
            if disks:
                return disks
        except Exception:
            pass

    # Method 2: lsblk plain
    out, _, rc = sh("lsblk -d -n -o NAME,SIZE,TYPE,MODEL 2>/dev/null")
    if rc == 0:
        for line in out.splitlines():
            p = line.split()
            if len(p) >= 3 and p[2] == 'disk':
                name  = p[0]
                size  = p[1]
                model = ' '.join(p[3:]) if len(p) > 3 else name
                disks.append((f'/dev/{name}', f'{model}  [{size}]', 0))
        if disks:
            return disks

    # Method 3: /proc/partitions
    out, _, _ = sh('cat /proc/partitions 2>/dev/null')
    for line in out.splitlines()[2:]:
        p = line.split()
        if len(p) == 4:
            name = p[3]
            if re.match(r'^(sd[a-z]|vd[a-z]|nvme\d+n\d+|hd[a-z])$', name):
                gb = round(int(p[2]) / 1024**2, 1)
                disks.append((f'/dev/{name}', f'{name}  [{gb} GB]', gb))
    return disks

def part_name(disk, n):
    """Return correct partition name: /dev/sda1 or /dev/nvme0n1p1"""
    if re.search(r'(nvme|mmcblk)', disk):
        return f'{disk}p{n}'
    return f'{disk}{n}'

def is_efi():
    return os.path.exists('/sys/firmware/efi')

def find_squashfs():
    paths = [
        '/run/live/medium/live/filesystem.squashfs',
        '/run/live/rootfs/filesystem.squashfs',
        '/lib/live/mount/medium/live/filesystem.squashfs',
        '/cdrom/live/filesystem.squashfs',
        '/run/initramfs/live/filesystem.squashfs',
    ]
    return next((p for p in paths if os.path.exists(p)), None)

def get_timezones():
    out, _, rc = sh('timedatectl list-timezones 2>/dev/null')
    tzs = [t for t in out.splitlines() if t.strip()]
    return tzs or ['Asia/Baghdad','Asia/Dubai','UTC',
                   'Europe/London','America/New_York']

# ── Main installer window ─────────────────────────────────────────────────────
class Installer(Gtk.Window):

    STEPS = ['Welcome', 'Disk & Partitions', 'Account',
             'Timezone', 'Confirm', 'Install', 'Done']

    def __init__(self):
        super().__init__(title=f'Install {VERSION}')
        self.set_default_size(760, 560)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect('delete-event', self._on_close)

        # Install state
        self.disk     = ''
        self.disk_gb  = 0
        self.layout   = 'auto'   # 'auto' or 'manual'
        self.encrypt  = False
        self.luks_pw  = ''
        self.username = 'myuser'
        self.password = ''
        self.hostname = 'ridos-core'
        self.timezone = 'Asia/Baghdad'
        self.efi      = is_efi()
        self.step     = 0

        self._build_ui()
        self._go(0)

    def _on_close(self, *_):
        if self.step == 5:
            return True
        Gtk.main_quit()

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        hdr = Gtk.Box(spacing=0)
        hdr.set_margin_start(24); hdr.set_margin_end(24)
        hdr.set_margin_top(14);   hdr.set_margin_bottom(14)
        self.h_title = Gtk.Label()
        self.h_step  = Gtk.Label()
        hdr.pack_start(self.h_title, True, True, 0)
        hdr.pack_end(self.h_step, False, False, 0)
        root.pack_start(hdr, False, False, 0)
        root.pack_start(Gtk.Separator(), False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.body.set_margin_start(32); self.body.set_margin_end(32)
        self.body.set_margin_top(20);   self.body.set_margin_bottom(8)
        scroll.add(self.body)
        root.pack_start(scroll, True, True, 0)
        root.pack_start(Gtk.Separator(), False, False, 0)

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
        [self._s0,self._s1,self._s2,self._s3,
         self._s4,self._s5,self._s6][n]()
        self.body.show_all()

    def _on_next(self, _):
        if not self._validate():
            return
        if self.step == 4:
            self._go(5)
            threading.Thread(target=self._install_thread,
                             daemon=True).start()
        elif self.step < len(self.STEPS) - 1:
            self._go(self.step + 1)

    def _validate(self):
        if self.step == 1:
            if not self.disk:
                self._err('Please select a disk.')
                return False
            if self.encrypt:
                lp = self._luks_entry.get_text()
                lp2 = self._luks_entry2.get_text()
                if len(lp) < 8:
                    self._err('Encryption password must be at least 8 characters.')
                    return False
                if lp != lp2:
                    self._err('Encryption passwords do not match.')
                    return False
                self.luks_pw = lp
        if self.step == 2:
            u  = self._ue.get_text().strip()
            p  = self._pe.get_text()
            p2 = self._p2e.get_text()
            h  = self._he.get_text().strip()
            if not re.match(r'^[a-z][a-z0-9_-]{0,30}$', u):
                self._err('Invalid username.\nMust start with a letter.\nOnly lowercase letters, numbers, - and _')
                return False
            if len(p) < 4:
                self._err('Password must be at least 4 characters.')
                return False
            if p != p2:
                self._err('Passwords do not match.')
                return False
            self.username = u
            self.password = p
            self.hostname = h or 'ridos-core'
        if self.step == 3:
            self.timezone = self._tzc.get_active_text() or 'Asia/Baghdad'
        return True

    def _err(self, msg):
        d = Gtk.MessageDialog(transient_for=self, modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=msg)
        d.run(); d.destroy()

    def _add(self, widget, expand=False, top=0):
        widget.set_margin_top(top)
        self.body.pack_start(widget, expand, expand, 0)

    def _lbl(self, txt, markup=False, color=None, top=0, wrap=True):
        l = Gtk.Label()
        if markup:
            l.set_markup(txt)
        elif color:
            l.set_markup(f'<span color="{color}">{GLib.markup_escape_text(txt)}</span>')
        else:
            l.set_text(txt)
        l.set_halign(Gtk.Align.START)
        l.set_line_wrap(wrap)
        l.set_margin_top(top)
        return l

    # ── Step 0: Welcome ───────────────────────────────────────────────────────
    def _s0(self):
        self._add(self._lbl(
            f'<span size="x-large" weight="bold" color="#1F6FEB">'
            f'Welcome to {VERSION}</span>', markup=True))
        self._add(self._lbl(
            'Rust-Ready Linux — Built for the next generation',
            color='#888', top=4))

        mode = 'UEFI' if self.efi else 'BIOS/MBR'
        sq   = find_squashfs()
        sq_status = f'Found: {sq}' if sq else '⚠  Not found — installation may fail'

        for txt, warn in [
            (f'Boot mode : {mode}', False),
            (f'Squashfs  : {sq_status}', not sq),
            ('', False),
            ('This installer will:', False),
            ('  1. Partition and format the selected disk', False),
            ('  2. Extract the RIDOS-Core filesystem', False),
            ('  3. Configure your system settings', False),
            ('  4. Install the GRUB bootloader', False),
            ('', False),
            ('⚠  WARNING: The selected disk will be completely erased.', True),
        ]:
            if not txt:
                self._add(Gtk.Label(label=''))
                continue
            l = self._lbl(txt, top=4)
            if warn:
                l.set_markup(f'<span color="#D29922">{txt}</span>')
            self._add(l)

        self.btn_next.set_label('Start →')

    # ── Step 1: Disk & Partitions ─────────────────────────────────────────────
    def _s1(self):
        self._add(self._lbl(
            '<b><span size="large">Select Disk and Partition Layout</span></b>',
            markup=True))

        # Disk selection
        self._add(self._lbl('Target disk:', top=16))
        disks = get_disks()
        if not disks:
            self._add(self._lbl(
                '❌  No disks detected.\n\n'
                'In VirtualBox: Machine Settings → Storage → add a virtual disk (20GB+)\n'
                'On real hardware: ensure disk is connected and powered.',
                color='#DA3633', top=8))
            btn = Gtk.Button(label='🔄  Refresh')
            btn.connect('clicked', lambda _: self._go(1))
            self._add(btn, top=8)
            return

        self._disk_combo = Gtk.ComboBoxText()
        sel = 0
        for i, (dev, label, gb) in enumerate(disks):
            self._disk_combo.append_text(f'{dev}  —  {label}')
            if self.disk == dev:
                sel = i
        self._disk_combo.set_active(sel)
        self.disk = disks[sel][0]
        self.disk_gb = disks[sel][2]
        self._disk_combo.connect('changed', self._on_disk_changed, disks)
        self._add(self._disk_combo, top=4)

        # Partition layout
        self._add(self._lbl('<b>Partition layout:</b>', markup=True, top=20))

        frame = Gtk.Frame()
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vb.set_margin_start(12); vb.set_margin_end(12)
        vb.set_margin_top(8);    vb.set_margin_bottom(8)

        self._rb_auto = Gtk.RadioButton(label='Automatic — use entire disk (recommended)')
        self._rb_auto.set_active(self.layout == 'auto')
        self._rb_auto.connect('toggled', lambda w: setattr(self, 'layout', 'auto') if w.get_active() else None)

        self._rb_custom = Gtk.RadioButton(
            label='Custom — choose partition sizes manually',
            group=self._rb_auto)
        self._rb_custom.set_active(self.layout == 'manual')
        self._rb_custom.connect('toggled', self._on_layout_toggle)

        vb.pack_start(self._rb_auto,   False, False, 4)
        vb.pack_start(self._rb_custom, False, False, 4)

        # Custom size inputs (hidden until manual selected)
        self._custom_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._custom_box.set_margin_start(24)
        self._custom_box.set_margin_top(8)

        grid = Gtk.Grid(row_spacing=8, column_spacing=12)

        def part_row(row, label, default, unit='GB'):
            lbl = Gtk.Label(label=label); lbl.set_halign(Gtk.Align.END)
            sb  = Gtk.SpinButton.new_with_range(0, 2000, 1)
            sb.set_value(default)
            u   = Gtk.Label(label=unit); u.set_halign(Gtk.Align.START)
            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(sb,  1, row, 1, 1)
            grid.attach(u,   2, row, 1, 1)
            return sb

        self._efi_sb  = part_row(0, 'EFI partition:',  1,  'GB')
        self._root_sb = part_row(1, 'Root (/) :',      20, 'GB')
        self._swap_sb = part_row(2, 'Swap:',            2,  'GB')
        self._home_sb = part_row(3, 'Home (/home):',    0,
                                 'GB  (0 = rest of disk)')

        # Show/hide EFI row based on boot mode
        if not self.efi:
            self._efi_sb.set_sensitive(False)
            self._efi_sb.set_value(0)

        self._custom_box.pack_start(grid, False, False, 0)
        self._custom_box.set_no_show_all(True)
        self._custom_box.set_visible(self.layout == 'manual')
        vb.pack_start(self._custom_box, False, False, 0)
        frame.add(vb)
        self._add(frame, top=4)

        # Encryption option
        self._add(self._lbl('<b>Full disk encryption (LUKS):</b>',
                             markup=True, top=16))
        enc_frame = Gtk.Frame()
        enc_vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        enc_vb.set_margin_start(12); enc_vb.set_margin_end(12)
        enc_vb.set_margin_top(8);    enc_vb.set_margin_bottom(8)

        self._enc_cb = Gtk.CheckButton(
            label='Enable LUKS full-disk encryption')
        self._enc_cb.set_active(self.encrypt)
        self._enc_cb.connect('toggled', self._on_encrypt_toggle)
        enc_vb.pack_start(self._enc_cb, False, False, 0)

        self._luks_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._luks_box.set_margin_start(24)
        self._luks_box.set_margin_top(6)

        luks_grid = Gtk.Grid(row_spacing=8, column_spacing=12)

        def luks_row(row, label):
            lbl = Gtk.Label(label=label); lbl.set_halign(Gtk.Align.END)
            e   = Gtk.Entry(); e.set_visibility(False)
            e.set_placeholder_text('minimum 8 characters')
            luks_grid.attach(lbl, 0, row, 1, 1)
            luks_grid.attach(e,   1, row, 1, 1)
            e.set_hexpand(True)
            return e

        self._luks_entry  = luks_row(0, 'Encryption password:')
        self._luks_entry2 = luks_row(1, 'Confirm password:')
        self._luks_box.pack_start(luks_grid, False, False, 0)
        self._luks_box.set_no_show_all(True)
        self._luks_box.set_visible(self.encrypt)
        enc_vb.pack_start(self._luks_box, False, False, 0)
        enc_frame.add(enc_vb)
        self._add(enc_frame, top=4)

        self._add(self._lbl(
            '⚠  All data on the selected disk will be permanently lost.',
            color='#D29922', top=12))

    def _on_disk_changed(self, combo, disks):
        idx = combo.get_active()
        if 0 <= idx < len(disks):
            self.disk    = disks[idx][0]
            self.disk_gb = disks[idx][2]

    def _on_layout_toggle(self, widget):
        self.layout = 'manual' if widget.get_active() else 'auto'
        self._custom_box.set_visible(self.layout == 'manual')

    def _on_encrypt_toggle(self, widget):
        self.encrypt = widget.get_active()
        self._luks_box.set_visible(self.encrypt)

    # ── Step 2: Account ───────────────────────────────────────────────────────
    def _s2(self):
        self._add(self._lbl(
            '<b><span size="large">Create Your Account</span></b>',
            markup=True))

        grid = Gtk.Grid(row_spacing=12, column_spacing=16)
        grid.set_margin_top(16)

        def row(i, lbl_txt, widget):
            l = Gtk.Label(label=lbl_txt); l.set_halign(Gtk.Align.END)
            grid.attach(l, 0, i, 1, 1)
            grid.attach(widget, 1, i, 1, 1)
            widget.set_hexpand(True)

        self._ue  = Gtk.Entry(); self._ue.set_text(self.username)
        self._ue.set_placeholder_text('lowercase letters only, e.g. john')
        self._pe  = Gtk.Entry(); self._pe.set_visibility(False)
        self._pe.set_placeholder_text('minimum 4 characters')
        self._p2e = Gtk.Entry(); self._p2e.set_visibility(False)
        self._p2e.set_placeholder_text('repeat your password')
        self._he  = Gtk.Entry(); self._he.set_text(self.hostname)
        self._he.set_placeholder_text('computer name, e.g. my-laptop')

        row(0, 'Username:',         self._ue)
        row(1, 'Password:',         self._pe)
        row(2, 'Confirm password:', self._p2e)
        row(3, 'Computer name:',    self._he)
        self._add(grid)

    # ── Step 3: Timezone ──────────────────────────────────────────────────────
    def _s3(self):
        self._add(self._lbl(
            '<b><span size="large">Select Timezone</span></b>',
            markup=True))
        self._add(self._lbl(
            'Your system clock will be set to this timezone.',
            color='#888', top=4))

        tzs = get_timezones()
        self._tzc = Gtk.ComboBoxText()
        self._tzc.set_margin_top(16)
        sel = 0
        for i, tz in enumerate(tzs):
            self._tzc.append_text(tz)
            if tz == self.timezone:
                sel = i
        self._tzc.set_active(sel)
        self._add(self._tzc)

    # ── Step 4: Confirm ───────────────────────────────────────────────────────
    def _s4(self):
        self._add(self._lbl(
            '<b><span size="large">Ready to Install</span></b>',
            markup=True))
        self._add(self._lbl(
            'Review your choices carefully. This cannot be undone.',
            color='#888', top=4))

        grid = Gtk.Grid(row_spacing=10, column_spacing=24)
        grid.set_margin_top(20)
        layout_str = 'Automatic (full disk)' if self.layout == 'auto' else 'Custom'
        enc_str    = 'Yes (LUKS)' if self.encrypt else 'No'
        rows = [
            ('OS',         VERSION),
            ('Disk',       f'{self.disk}  ← WILL BE ERASED'),
            ('Boot mode',  'UEFI' if self.efi else 'BIOS/MBR'),
            ('Layout',     layout_str),
            ('Encryption', enc_str),
            ('Username',   self.username),
            ('Hostname',   self.hostname),
            ('Timezone',   self.timezone),
        ]
        for i, (k, v) in enumerate(rows):
            kl = Gtk.Label(); kl.set_markup(f'<b>{k}:</b>')
            kl.set_halign(Gtk.Align.END)
            vl = Gtk.Label(label=v); vl.set_halign(Gtk.Align.START)
            if 'ERASED' in v:
                vl.set_markup(
                    f'<span color="#DA3633" weight="bold">{v}</span>')
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        self._add(grid)
        self.btn_next.set_label('⚠  Install Now')
        self.btn_next.get_style_context().add_class('destructive-action')

    # ── Step 5: Install progress ──────────────────────────────────────────────
    def _s5(self):
        self.btn_back.set_sensitive(False)
        self.btn_next.set_sensitive(False)
        self._add(self._lbl(
            '<b><span size="large">Installing RIDOS-Core...</span></b>',
            markup=True))
        self._add(self._lbl(
            'Do not power off. This will take 5-20 minutes.',
            color='#888', top=4))
        self._prog = Gtk.ProgressBar()
        self._prog.set_margin_top(12)
        self._prog.set_margin_bottom(4)
        self._add(self._prog)
        self._slbl = Gtk.Label(label='Preparing...')
        self._slbl.set_halign(Gtk.Align.START)
        self._add(self._slbl)
        sc = Gtk.ScrolledWindow()
        sc.set_min_content_height(280)
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._logbuf = Gtk.TextBuffer()
        tv = Gtk.TextView(buffer=self._logbuf)
        tv.set_editable(False); tv.set_monospace(True)
        sc.add(tv)
        self._add(sc, expand=True)

    def _log(self, msg):
        self._logbuf.insert(self._logbuf.get_end_iter(), msg + '\n')

    def _status(self, msg, frac):
        GLib.idle_add(self._slbl.set_text, msg)
        GLib.idle_add(self._prog.set_fraction, frac)

    # ── Step 6: Done ─────────────────────────────────────────────────────────
    def _s6(self):
        self.btn_back.set_sensitive(False)
        self.btn_next.set_label('🔄  Reboot Now')
        self.btn_next.set_sensitive(True)
        self.btn_next.get_style_context().remove_class('destructive-action')
        self.btn_next.connect('clicked', lambda _: sh('reboot'))
        self._add(self._lbl(
            '<span size="xx-large" weight="bold" color="#238636">'
            '✓  Installation Complete!</span>', markup=True))
        self._add(self._lbl(
            f'\n{VERSION} is now installed.\n'
            'Remove the USB/live media and click Reboot Now.',
            top=12))

    # ── Installation thread ───────────────────────────────────────────────────
    def _install_thread(self):
        """
        Correct installation sequence:
        1. Wipe + partition + format
        2. Mount root (and EFI if needed)
        3. Bind /dev /proc /sys /run into /mnt  ← BEFORE extraction
        4. Extract squashfs
        5. Configure inside chroot (fstab, hostname, user, tz)
        6. GRUB inside chroot
        7. Clean up live packages
        8. Unbind + unmount
        """
        disk = self.disk
        efi  = self.efi

        p1 = part_name(disk, 1)
        p2 = part_name(disk, 2)
        p3 = part_name(disk, 3)

        def log(msg):
            GLib.idle_add(self._log, msg)

        def fail(msg):
            self._status(f'FAILED: {msg}', self._prog.get_fraction())
            log(f'\n❌  INSTALLATION FAILED: {msg}')
            log('Please check the log above for details.')
            log('You can close this window and try again.')
            GLib.idle_add(self.btn_next.set_sensitive, False)
            GLib.idle_add(self.btn_back.set_sensitive, True)

        try:
            # ── Step 1: Unmount anything on target disk ────────────────────
            self._status('Unmounting target disk...', 0.01)
            sh('umount /mnt/boot/efi 2>/dev/null || true')
            sh('umount /mnt/run 2>/dev/null || true')
            sh('umount /mnt/sys 2>/dev/null || true')
            sh('umount /mnt/proc 2>/dev/null || true')
            sh('umount /mnt/dev 2>/dev/null || true')
            sh('umount /mnt 2>/dev/null || true')
            sh(f'umount {disk}* 2>/dev/null || true')

            # ── Step 2: Partition ─────────────────────────────────────────
            self._status('Partitioning disk...', 0.03)
            if self.layout == 'auto':
                if efi:
                    log(f'GPT partition table on {disk}')
                    sh(f'parted -s {disk} mklabel gpt')
                    sh(f'parted -s {disk} mkpart primary fat32 1MiB 513MiB')
                    sh(f'parted -s {disk} set 1 esp on')
                    sh(f'parted -s {disk} mkpart primary linux-swap 513MiB 2561MiB')
                    sh(f'parted -s {disk} mkpart primary ext4 2561MiB 100%')
                    efi_part  = p1
                    swap_part = p2
                    root_part = p3
                else:
                    log(f'MBR partition table on {disk}')
                    sh(f'parted -s {disk} mklabel msdos')
                    sh(f'parted -s {disk} mkpart primary linux-swap 1MiB 2049MiB')
                    sh(f'parted -s {disk} mkpart primary ext4 2049MiB 100%')
                    sh(f'parted -s {disk} set 2 boot on')
                    efi_part  = None
                    swap_part = p1
                    root_part = p2
            else:
                # Manual layout
                efi_gb  = int(self._efi_sb.get_value())  if efi else 0
                swap_gb = int(self._swap_sb.get_value())
                root_gb = int(self._root_sb.get_value())
                home_gb = int(self._home_sb.get_value())

                start = 1  # MiB
                pnum  = 1
                efi_part = swap_part = root_part = home_part = None

                if efi and efi_gb > 0:
                    end = start + efi_gb * 1024
                    sh(f'parted -s {disk} mklabel gpt')
                    sh(f'parted -s {disk} mkpart primary fat32 {start}MiB {end}MiB')
                    sh(f'parted -s {disk} set {pnum} esp on')
                    efi_part = part_name(disk, pnum)
                    pnum += 1; start = end
                elif not efi:
                    sh(f'parted -s {disk} mklabel msdos')

                if swap_gb > 0:
                    end = start + swap_gb * 1024
                    sh(f'parted -s {disk} mkpart primary linux-swap {start}MiB {end}MiB')
                    swap_part = part_name(disk, pnum)
                    pnum += 1; start = end

                end = start + root_gb * 1024
                sh(f'parted -s {disk} mkpart primary ext4 {start}MiB {end}MiB')
                if not efi:
                    sh(f'parted -s {disk} set {pnum} boot on')
                root_part = part_name(disk, pnum)
                pnum += 1; start = end

                if home_gb > 0:
                    end = start + home_gb * 1024
                    sh(f'parted -s {disk} mkpart primary ext4 {start}MiB {end}MiB')
                    home_part = part_name(disk, pnum)
                    pnum += 1

            log(f'Partition layout: root={root_part} swap={swap_part} '
                f'efi={efi_part} home={getattr(self, "home_part", None)}')

            # ── Step 3: Format ────────────────────────────────────────────
            self._status('Formatting partitions...', 0.07)
            sh('partprobe 2>/dev/null || true')
            sh('sleep 2')

            if efi_part:
                log(f'Formatting EFI: {efi_part}')
                _, err, rc = sh(f'mkfs.fat -F32 {efi_part}')
                if rc != 0:
                    return fail(f'mkfs.fat failed: {err}')

            if swap_part:
                log(f'Formatting swap: {swap_part}')
                sh(f'mkswap {swap_part}')
                sh(f'swapon {swap_part} 2>/dev/null || true')

            log(f'Formatting root: {root_part}')
            if self.encrypt:
                log('Setting up LUKS encryption...')
                p = subprocess.Popen(
                    f'cryptsetup luksFormat --batch-mode {root_part}',
                    shell=True, stdin=subprocess.PIPE)
                p.communicate(input=(self.luks_pw + '\n').encode())
                if p.returncode != 0:
                    return fail('LUKS format failed')
                p2 = subprocess.Popen(
                    f'cryptsetup luksOpen {root_part} ridos_root',
                    shell=True, stdin=subprocess.PIPE)
                p2.communicate(input=(self.luks_pw + '\n').encode())
                root_device = '/dev/mapper/ridos_root'
            else:
                root_device = root_part

            _, err, rc = sh(f'mkfs.ext4 -F {root_device}')
            if rc != 0:
                return fail(f'mkfs.ext4 failed: {err}')

            # ── Step 4: Mount ─────────────────────────────────────────────
            self._status('Mounting partitions...', 0.10)
            sh('mkdir -p /mnt')
            _, err, rc = sh(f'mount {root_device} /mnt')
            if rc != 0:
                return fail(f'mount root failed: {err}')

            if efi_part:
                sh('mkdir -p /mnt/boot/efi')
                _, err, rc = sh(f'mount {efi_part} /mnt/boot/efi')
                if rc != 0:
                    return fail(f'mount EFI failed: {err}')

            # ── Step 5: Bind /dev /proc /sys /run ─────────────────────────
            # THIS is what was missing — these must be bound BEFORE
            # any chroot commands (chpasswd, grub-install, etc.)
            self._status('Binding system directories...', 0.12)
            for d in ['dev', 'proc', 'sys', 'run']:
                sh(f'mkdir -p /mnt/{d}')
                sh(f'mount --bind /{d} /mnt/{d}')
                log(f'Bound /{d} → /mnt/{d}')

            # Also bind /dev/pts for terminal support in chroot
            sh('mkdir -p /mnt/dev/pts')
            sh('mount --bind /dev/pts /mnt/dev/pts 2>/dev/null || true')

            # ── Step 6: Extract filesystem ────────────────────────────────
            self._status('Extracting filesystem (5-15 minutes)...', 0.14)
            sq = find_squashfs()
            if sq:
                log(f'Extracting squashfs: {sq}')
                log('This is the longest step — please wait...')
                rc = sh_log(f'unsquashfs -f -d /mnt {sq}', self._log)
                if rc != 0:
                    log(f'unsquashfs returned {rc} — trying rsync fallback...')
                    rc = sh_log(
                        'rsync -aAX --delete '
                        '--exclude={"/proc/*","/sys/*","/dev/*",'
                        '"/tmp/*","/run/*","/mnt/*","/media/*",'
                        '"/lost+found","/opt/ridos-core/logs/*"} '
                        '/ /mnt/', self._log)
            else:
                log('squashfs not found — using rsync (slower)...')
                rc = sh_log(
                    'rsync -aAX --delete '
                    '--exclude={"/proc/*","/sys/*","/dev/*",'
                    '"/tmp/*","/run/*","/mnt/*","/media/*",'
                    '"/lost+found","/opt/ridos-core/logs/*"} '
                    '/ /mnt/', self._log)

            # ── Step 7: Write fstab ───────────────────────────────────────
            self._status('Writing fstab...', 0.65)
            root_uuid, _, _ = sh(f'blkid -s UUID -o value {root_device}')
            fstab = (f'UUID={root_uuid.strip()} / ext4 '
                     f'defaults,errors=remount-ro 0 1\n')
            if efi_part:
                efi_uuid, _, _ = sh(f'blkid -s UUID -o value {efi_part}')
                fstab += (f'UUID={efi_uuid.strip()} /boot/efi '
                          f'vfat umask=0077 0 1\n')
            if swap_part:
                swap_uuid, _, _ = sh(f'blkid -s UUID -o value {swap_part}')
                fstab += f'UUID={swap_uuid.strip()} none swap sw 0 0\n'
            fstab += ('tmpfs /tmp tmpfs '
                      'defaults,noatime,nosuid,nodev,size=2G 0 0\n')
            open('/mnt/etc/fstab', 'w').write(fstab)
            log('fstab written')

            # ── Step 8: Configure ─────────────────────────────────────────
            self._status('Configuring system...', 0.68)

            # Hostname
            open('/mnt/etc/hostname', 'w').write(self.hostname + '\n')
            open('/mnt/etc/hosts', 'w').write(
                f'127.0.0.1 localhost\n'
                f'127.0.1.1 {self.hostname}\n'
                f'::1       localhost ip6-localhost ip6-loopback\n')

            # Timezone
            sh(f'ln -sf /usr/share/zoneinfo/{self.timezone} /mnt/etc/localtime')
            open('/mnt/etc/timezone', 'w').write(self.timezone + '\n')

            # Create user
            self._status(f'Creating user {self.username}...', 0.72)
            sh(f'chroot /mnt useradd -m -s /bin/bash '
               f'-G sudo,audio,video,netdev,plugdev '
               f'{self.username} 2>/dev/null || true')
            p = subprocess.Popen('chroot /mnt chpasswd',
                                 shell=True, stdin=subprocess.PIPE)
            p.communicate(
                input=f'{self.username}:{self.password}\n'.encode())
            sh(f'echo "{self.username} ALL=(ALL) ALL" '
               f'> /mnt/etc/sudoers.d/{self.username}')
            sh(f'chmod 440 /mnt/etc/sudoers.d/{self.username}')

            # Disable live autologin in installed system
            gdm = '/mnt/etc/gdm3/custom.conf'
            if os.path.exists(gdm):
                c = open(gdm).read()
                c = re.sub(r'AutomaticLoginEnable\s*=.*\n', '', c)
                c = re.sub(r'AutomaticLogin\s*=.*\n', '', c)
                open(gdm, 'w').write(c)

            # Remove live installer autostart from installed system
            sh('rm -f /mnt/etc/xdg/autostart/ridos-installer.desktop '
               '2>/dev/null || true')

            # ── Step 9: GRUB ──────────────────────────────────────────────
            self._status('Installing GRUB bootloader...', 0.80)
            if efi:
                rc = sh_log(
                    f'chroot /mnt grub-install '
                    f'--target=x86_64-efi '
                    f'--efi-directory=/boot/efi '
                    f'--bootloader-id=RIDOS-Core '
                    f'--recheck {disk}',
                    self._log)
            else:
                rc = sh_log(
                    f'chroot /mnt grub-install '
                    f'--target=i386-pc '
                    f'--recheck {disk}',
                    self._log)

            if rc != 0:
                log(f'WARNING: grub-install returned {rc}')
                log('Trying fallback grub-install...')
                if efi:
                    sh_log(f'chroot /mnt grub-install '
                           f'--target=x86_64-efi '
                           f'--efi-directory=/boot/efi '
                           f'--bootloader-id=RIDOS --no-nvram {disk}',
                           self._log)
                else:
                    sh_log(f'chroot /mnt grub-install '
                           f'--target=i386-pc {disk}',
                           self._log)

            self._status('Generating GRUB config...', 0.88)
            sh_log('chroot /mnt update-grub', self._log)

            # ── Step 10: Remove live packages ─────────────────────────────
            self._status('Removing live packages...', 0.92)
            sh_log('chroot /mnt apt-get remove -y '
                   'live-boot live-boot-initramfs-tools '
                   '2>/dev/null || true',
                   self._log)

            # ── Step 11: Clean unmount ────────────────────────────────────
            self._status('Unmounting...', 0.96)
            for d in ['dev/pts','run','sys','proc','dev']:
                sh(f'umount /mnt/{d} 2>/dev/null || true')
            sh('umount /mnt/boot/efi 2>/dev/null || true')
            sh('umount /mnt 2>/dev/null || true')
            if self.encrypt:
                sh('cryptsetup luksClose ridos_root 2>/dev/null || true')

            self._status('Installation complete!', 1.0)
            log('\n✓  RIDOS-Core installed successfully!')
            GLib.idle_add(self._go, 6)

        except Exception as e:
            fail(str(e))


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if os.geteuid() != 0:
        os.execvp('sudo', ['sudo', '--'] + sys.argv)
    app = Installer()
    app.connect('destroy', Gtk.main_quit)
    app.show_all()
    Gtk.main()
