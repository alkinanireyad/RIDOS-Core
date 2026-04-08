#!/usr/bin/env python3
"""
ridos-installer.py — RIDOS-Core 1.0 Nova
Installation sequence based on proven bash script approach:
  1. Partition with GPT
  2. partprobe + sleep (wait for kernel to register partitions)
  3. Format with lazy_itable_init=0 (full initialization)
  4. Mount target
  5. rsync filesystem (BEFORE bind mounts)
  6. Bind /dev /dev/pts /proc /sys /run
  7. Configure inside chroot (fstab, hostname, user, timezone)
  8. Install GRUB inside chroot via apt (more reliable)
  9. update-grub inside chroot
 10. Lazy unmount
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import os, sys, subprocess, threading, re

VERSION   = "RIDOS-Core 1.0 Nova"
MOUNT_PT  = "/mnt/ridos_target"

# ── Shell helpers ─────────────────────────────────────────────────────────────
def sh(cmd, inp=None, timeout=600):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout,
                           input=inp)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return '', 'Timeout', 1
    except Exception as e:
        return '', str(e), 1

def sh_log(cmd, log_fn, timeout=1800):
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

# ── Disk detection ────────────────────────────────────────────────────────────
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
                    gb    = round(int(d.get('size') or 0) / 1024**3, 1)
                    disks.append((f'/dev/{name}',
                                  f'{model}  [{gb} GB]', gb))
            if disks:
                return disks
        except Exception:
            pass
    # Method 2: /proc/partitions
    out, _, _ = sh('cat /proc/partitions 2>/dev/null')
    for line in out.splitlines()[2:]:
        p = line.split()
        if len(p) == 4:
            name = p[3]
            if re.match(
                    r'^(sd[a-z]|vd[a-z]|nvme\d+n\d+|hd[a-z])$', name):
                gb = round(int(p[2]) / 1024**2, 1)
                disks.append((f'/dev/{name}',
                               f'{name}  [{gb} GB]', gb))
    return disks

def part(disk, n):
    """Return correct partition name handling NVMe."""
    return f'{disk}p{n}' if re.search(r'(nvme|mmcblk)', disk) \
           else f'{disk}{n}'

def is_efi():
    return os.path.exists('/sys/firmware/efi')

def get_timezones():
    out, _, rc = sh('timedatectl list-timezones 2>/dev/null')
    tzs = [t for t in out.splitlines() if t.strip()]
    return tzs or ['Asia/Baghdad', 'Asia/Dubai', 'UTC',
                   'Europe/London', 'America/New_York']

# ── GTK installer window ──────────────────────────────────────────────────────
class Installer(Gtk.Window):

    STEPS = ['Welcome', 'Disk', 'Account',
             'Timezone', 'Confirm', 'Install', 'Done']

    def __init__(self):
        super().__init__(title=f'Install {VERSION}')
        self.set_default_size(760, 560)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect('delete-event', self._on_close)

        self.step     = 0
        self.disk     = ''
        self.disk_gb  = 0
        self.username = 'myuser'
        self.password = ''
        self.hostname = 'ridos-core'
        self.timezone = 'Asia/Baghdad'
        self.efi      = is_efi()

        self._build_chrome()
        self._go(0)

    def _on_close(self, *_):
        if self.step == 5:
            return True
        Gtk.main_quit()

    # ── Window chrome ─────────────────────────────────────────────────────────
    def _build_chrome(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        hdr = Gtk.Box(spacing=0)
        hdr.set_margin_start(24); hdr.set_margin_end(24)
        hdr.set_margin_top(14);   hdr.set_margin_bottom(14)
        self._htitle = Gtk.Label()
        self._hstep  = Gtk.Label()
        hdr.pack_start(self._htitle, True, True, 0)
        hdr.pack_end(self._hstep, False, False, 0)
        root.pack_start(hdr, False, False, 0)
        root.pack_start(Gtk.Separator(), False, False, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.body.set_margin_start(32); self.body.set_margin_end(32)
        self.body.set_margin_top(20);   self.body.set_margin_bottom(8)
        sw.add(self.body)
        root.pack_start(sw, True, True, 0)
        root.pack_start(Gtk.Separator(), False, False, 0)

        nav = Gtk.Box(spacing=12)
        nav.set_margin_start(32); nav.set_margin_end(32)
        nav.set_margin_top(12);   nav.set_margin_bottom(14)
        self._back = Gtk.Button(label='← Back')
        self._next = Gtk.Button(label='Next →')
        self._next.get_style_context().add_class('suggested-action')
        self._back.connect('clicked', lambda _: self._go(self.step - 1))
        self._next.connect('clicked', self._on_next)
        nav.pack_start(self._back, False, False, 0)
        nav.pack_end(self._next, False, False, 0)
        root.pack_start(nav, False, False, 0)

    def _clear(self):
        for c in self.body.get_children():
            self.body.remove(c)

    def _go(self, n):
        self._clear()
        self.step = n
        self._htitle.set_markup(
            f'<b><span size="large" color="#1F6FEB">{VERSION}</span></b>')
        self._hstep.set_markup(
            f'<span color="#888">Step {n+1}/{len(self.STEPS)}: '
            f'<b>{self.STEPS[n]}</b></span>')
        self._back.set_sensitive(0 < n < 5)
        self._next.set_sensitive(n < 5)
        [self._s_welcome, self._s_disk, self._s_account,
         self._s_timezone, self._s_confirm,
         self._s_install,  self._s_done][n]()
        self.body.show_all()

    def _on_next(self, _):
        if not self._validate():
            return
        if self.step == 4:
            self._go(5)
            threading.Thread(target=self._run_install,
                             daemon=True).start()
        elif self.step < len(self.STEPS) - 1:
            self._go(self.step + 1)

    def _validate(self):
        if self.step == 1 and not self.disk:
            self._err('Please select a disk.')
            return False
        if self.step == 2:
            u  = self._ue.get_text().strip()
            p  = self._pe.get_text()
            p2 = self._p2e.get_text()
            if not re.match(r'^[a-z][a-z0-9_-]{0,30}$', u):
                self._err('Invalid username.\n'
                          'Must start with a lowercase letter.\n'
                          'Only: a-z 0-9 - _')
                return False
            if len(p) < 4:
                self._err('Password must be at least 4 characters.')
                return False
            if p != p2:
                self._err('Passwords do not match.')
                return False
            self.username = u
            self.password = p
            self.hostname = (self._he.get_text().strip()
                             or 'ridos-core')
        if self.step == 3:
            self.timezone = (self._tzc.get_active_text()
                             or 'Asia/Baghdad')
        return True

    def _err(self, msg):
        d = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=msg)
        d.run(); d.destroy()

    def _add(self, w, expand=False, top=0):
        w.set_margin_top(top)
        self.body.pack_start(w, expand, expand, 0)

    def _lbl(self, txt, markup=False, color=None, top=0):
        l = Gtk.Label()
        if markup:
            l.set_markup(txt)
        elif color:
            l.set_markup(
                f'<span color="{color}">'
                f'{GLib.markup_escape_text(txt)}</span>')
        else:
            l.set_text(txt)
        l.set_halign(Gtk.Align.START)
        l.set_line_wrap(True)
        l.set_margin_top(top)
        return l

    # ── Step 0: Welcome ───────────────────────────────────────────────────────
    def _s_welcome(self):
        self._add(self._lbl(
            f'<span size="x-large" weight="bold" color="#1F6FEB">'
            f'Welcome to {VERSION}</span>', markup=True))
        self._add(self._lbl(
            'Rust-Ready Linux — Built for the next generation',
            color='#888', top=6))
        mode = 'UEFI' if self.efi else 'BIOS/MBR'
        for txt, warn in [
            ('', False),
            (f'• Boot mode detected: {mode}', False),
            ('• Debian 12 Bookworm + Linux 6.12 LTS', False),
            ('• GNOME desktop with fast zstd boot', False),
            ('• Brave Browser + Pro IT toolkit', False),
            ('', False),
            ('This installer will:', False),
            ('  1. Partition and format the selected disk (GPT)', False),
            ('  2. Copy the live filesystem using rsync', False),
            ('  3. Configure hostname, timezone, user account', False),
            ('  4. Install GRUB bootloader', False),
            ('', False),
            ('⚠  WARNING: The selected disk will be completely erased.',
             True),
            ('⚠  Back up your data before continuing.', True),
        ]:
            if not txt:
                self._add(Gtk.Label(label=''))
                continue
            l = self._lbl(txt, top=4)
            if warn:
                l.set_markup(f'<span color="#D29922">{txt}</span>')
            self._add(l)
        self._next.set_label('Start →')

    # ── Step 1: Disk ──────────────────────────────────────────────────────────
    def _s_disk(self):
        self._add(self._lbl(
            '<b><span size="large">Select Target Disk</span></b>',
            markup=True))
        self._add(self._lbl(
            '⚠  All data on the selected disk will be permanently erased.',
            color='#D29922', top=8))

        disks = get_disks()
        if not disks:
            self._add(self._lbl(
                '\n❌  No disks detected.\n\n'
                'In VirtualBox: Machine Settings → Storage\n'
                '→ Add Hard Disk → at least 20 GB.\n\n'
                'On real hardware: check disk is connected.',
                color='#DA3633', top=16))
            btn = Gtk.Button(label='🔄  Refresh disk list')
            btn.connect('clicked', lambda _: self._go(1))
            self._add(btn, top=12)
            return

        first = None
        for dev, label, gb in disks:
            rb = Gtk.RadioButton(label=f'{dev}   —   {label}')
            if first is None:
                first = rb
                if not self.disk:
                    self.disk   = dev
                    self.disk_gb = gb
            else:
                rb.join_group(first)
            if self.disk == dev:
                rb.set_active(True)
            rb.connect(
                'toggled',
                lambda w, d=dev, g=gb: (
                    setattr(self, 'disk', d),
                    setattr(self, 'disk_gb', g)
                ) if w.get_active() else None)
            rb.set_margin_top(10)
            self._add(rb)

        self._next.set_label('Next →')

    # ── Step 2: Account ───────────────────────────────────────────────────────
    def _s_account(self):
        self._add(self._lbl(
            '<b><span size="large">Create Your Account</span></b>',
            markup=True))
        grid = Gtk.Grid(row_spacing=12, column_spacing=16)
        grid.set_margin_top(16)

        def row(i, lbl_txt, w):
            l = Gtk.Label(label=lbl_txt)
            l.set_halign(Gtk.Align.END)
            grid.attach(l, 0, i, 1, 1)
            grid.attach(w, 1, i, 1, 1)
            w.set_hexpand(True)

        self._ue  = Gtk.Entry()
        self._ue.set_text(self.username)
        self._ue.set_placeholder_text('lowercase letters only')
        self._pe  = Gtk.Entry()
        self._pe.set_visibility(False)
        self._pe.set_placeholder_text('minimum 4 characters')
        self._p2e = Gtk.Entry()
        self._p2e.set_visibility(False)
        self._p2e.set_placeholder_text('repeat password')
        self._he  = Gtk.Entry()
        self._he.set_text(self.hostname)
        self._he.set_placeholder_text('e.g. my-laptop')

        row(0, 'Username:',         self._ue)
        row(1, 'Password:',         self._pe)
        row(2, 'Confirm password:', self._p2e)
        row(3, 'Computer name:',    self._he)
        self._add(grid)

    # ── Step 3: Timezone ──────────────────────────────────────────────────────
    def _s_timezone(self):
        self._add(self._lbl(
            '<b><span size="large">Select Timezone</span></b>',
            markup=True))
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
    def _s_confirm(self):
        self._add(self._lbl(
            '<b><span size="large">Ready to Install</span></b>',
            markup=True))
        self._add(self._lbl(
            'Review carefully — this cannot be undone.',
            color='#888', top=4))
        grid = Gtk.Grid(row_spacing=10, column_spacing=24)
        grid.set_margin_top(20)
        for i, (k, v) in enumerate([
            ('OS',        VERSION),
            ('Disk',      f'{self.disk}  ← WILL BE ERASED'),
            ('Boot mode', 'UEFI' if self.efi else 'BIOS/MBR'),
            ('Username',  self.username),
            ('Hostname',  self.hostname),
            ('Timezone',  self.timezone),
        ]):
            kl = Gtk.Label()
            kl.set_markup(f'<b>{k}:</b>')
            kl.set_halign(Gtk.Align.END)
            vl = Gtk.Label(label=v)
            vl.set_halign(Gtk.Align.START)
            if 'ERASED' in v:
                vl.set_markup(
                    f'<span color="#DA3633" weight="bold">{v}</span>')
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        self._add(grid)
        self._next.set_label('⚠  Install Now')
        self._next.get_style_context().add_class('destructive-action')

    # ── Step 5: Progress ─────────────────────────────────────────────────────
    def _s_install(self):
        self._back.set_sensitive(False)
        self._next.set_sensitive(False)
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
        sc.set_min_content_height(290)
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._buf = Gtk.TextBuffer()
        tv = Gtk.TextView(buffer=self._buf)
        tv.set_editable(False); tv.set_monospace(True)
        sc.add(tv)
        self._add(sc, expand=True)

    def _log(self, msg):
        self._buf.insert(self._buf.get_end_iter(), msg + '\n')

    def _status(self, msg, frac):
        GLib.idle_add(self._slbl.set_text, msg)
        GLib.idle_add(self._prog.set_fraction, frac)

    # ── Step 6: Done ─────────────────────────────────────────────────────────
    def _s_done(self):
        self._back.set_sensitive(False)
        self._next.set_label('🔄  Reboot Now')
        self._next.set_sensitive(True)
        self._next.get_style_context().remove_class('destructive-action')
        self._next.connect('clicked',
                           lambda _: sh('reboot', timeout=10))
        self._add(self._lbl(
            '<span size="xx-large" weight="bold" color="#238636">'
            '✓  Installation Complete!</span>', markup=True))
        self._add(self._lbl(
            f'\n{VERSION} installed successfully.\n'
            'Remove the live USB/CD and click Reboot Now.',
            top=12))

    # ── Installation thread ───────────────────────────────────────────────────
    def _run_install(self):
        """
        Proven sequence based on working bash installer:
        1. Clean unmount of anything on disk
        2. GPT partition table
        3. partprobe + sleep 2 (CRITICAL — wait for kernel)
        4. Format with lazy_itable_init=0
        5. Mount target
        6. rsync filesystem (BEFORE bind mounts)
        7. Bind /dev /dev/pts /proc /sys /run
        8. Configure inside chroot
        9. Install GRUB inside chroot
        10. update-grub
        11. Lazy unmount
        """
        disk  = self.disk
        efi   = self.efi
        mnt   = MOUNT_PT
        user  = self.username
        pw    = self.password
        host  = self.hostname
        tz    = self.timezone

        def log(msg):
            GLib.idle_add(self._log, msg)

        def fail(msg):
            self._status(f'❌  FAILED: {msg}',
                         self._prog.get_fraction())
            log(f'\n❌  INSTALLATION FAILED\n{msg}')
            log('\nYou can close this window and try again.')
            GLib.idle_add(self._back.set_sensitive, True)
            GLib.idle_add(self._next.set_sensitive, False)

        try:
            # ── Step 1: Clean existing mounts ────────────────────────────
            self._status('Cleaning up existing mounts...', 0.01)
            log('Cleaning up...')
            sh(f'umount -l {mnt}/boot/efi 2>/dev/null || true')
            sh(f'umount -l {mnt}/dev/pts  2>/dev/null || true')
            sh(f'umount -l {mnt}/dev      2>/dev/null || true')
            sh(f'umount -l {mnt}/proc     2>/dev/null || true')
            sh(f'umount -l {mnt}/sys      2>/dev/null || true')
            sh(f'umount -l {mnt}/run      2>/dev/null || true')
            sh(f'umount -l {mnt}          2>/dev/null || true')
            sh(f'umount -l {disk}1        2>/dev/null || true')
            sh(f'umount -l {disk}2        2>/dev/null || true')
            sh(f'umount -l {disk}3        2>/dev/null || true')
            sh(f'mkdir -p {mnt}')

            # ── Step 2: Partition with GPT ────────────────────────────────
            self._status('Partitioning disk (GPT)...', 0.04)
            log(f'Creating GPT partition table on {disk}...')

            if efi:
                # GPT: EFI (512MB) + swap (2GB) + root (rest)
                _, err, rc = sh(
                    f'parted -s {disk} mklabel gpt')
                if rc != 0:
                    return fail(f'parted mklabel failed: {err}')
                sh(f'parted -s {disk} mkpart ESP fat32 1MiB 513MiB')
                sh(f'parted -s {disk} set 1 esp on')
                sh(f'parted -s {disk} mkpart primary linux-swap '
                   f'513MiB 2561MiB')
                sh(f'parted -s {disk} mkpart primary ext4 '
                   f'2561MiB 100%')
                efi_part  = part(disk, 1)
                swap_part = part(disk, 2)
                root_part = part(disk, 3)
            else:
                # MBR: swap (2GB) + root (rest, bootable)
                _, err, rc = sh(
                    f'parted -s {disk} mklabel msdos')
                if rc != 0:
                    return fail(f'parted mklabel failed: {err}')
                sh(f'parted -s {disk} mkpart primary linux-swap '
                   f'1MiB 2049MiB')
                sh(f'parted -s {disk} mkpart primary ext4 '
                   f'2049MiB 100%')
                sh(f'parted -s {disk} set 2 boot on')
                efi_part  = None
                swap_part = part(disk, 1)
                root_part = part(disk, 2)

            log(f'Partitions: root={root_part} swap={swap_part} '
                f'efi={efi_part}')

            # ── Step 3: CRITICAL — wait for kernel to see partitions ──────
            # Without this, mkfs fails with "does not exist"
            self._status('Waiting for kernel to register partitions...',
                         0.07)
            log('Running partprobe...')
            sh('partprobe 2>/dev/null || true')
            sh('udevadm settle 2>/dev/null || true')
            sh('sleep 3')

            # Verify partitions exist
            for p_check in ([efi_part] if efi_part else []) + \
                           [swap_part, root_part]:
                if not os.path.exists(p_check):
                    log(f'WARNING: {p_check} not found, waiting...')
                    sh('sleep 3')
                    if not os.path.exists(p_check):
                        return fail(
                            f'Partition {p_check} was not created.\n'
                            f'Check that the disk is not in use.')
                log(f'Verified: {p_check} exists')

            # ── Step 4: Format partitions ─────────────────────────────────
            self._status('Formatting partitions...', 0.10)

            if efi_part:
                log(f'Formatting EFI partition: {efi_part}')
                _, err, rc = sh(f'mkfs.fat -F 32 {efi_part}')
                if rc != 0:
                    return fail(f'mkfs.fat failed: {err}')

            log(f'Formatting swap: {swap_part}')
            sh(f'mkswap {swap_part}')
            sh(f'swapon {swap_part} 2>/dev/null || true')

            log(f'Formatting root: {root_part}')
            # lazy_itable_init=0,lazy_journal_init=0 ensures full init
            _, err, rc = sh(
                f'mkfs.ext4 -F '
                f'-E lazy_itable_init=0,lazy_journal_init=0 '
                f'{root_part}')
            if rc != 0:
                return fail(f'mkfs.ext4 failed: {err}')
            log('Formatting complete.')

            # ── Step 5: Mount target ──────────────────────────────────────
            self._status('Mounting target partition...', 0.13)
            _, err, rc = sh(f'mount {root_part} {mnt}')
            if rc != 0:
                return fail(f'mount root failed: {err}')

            if efi_part:
                sh(f'mkdir -p {mnt}/boot/efi')
                _, err, rc = sh(f'mount {efi_part} {mnt}/boot/efi')
                if rc != 0:
                    return fail(f'mount EFI failed: {err}')

            log(f'Target mounted at {mnt}')

            # ── Step 6: Copy filesystem with rsync ────────────────────────
            # rsync BEFORE bind mounts — this is the correct order
            self._status(
                'Copying filesystem (rsync) — this takes 5-15 min...',
                0.15)
            log('Starting rsync...')
            log('(Copying live system to target disk)')

            rc = sh_log(
                f'rsync -aAXv '
                f'--exclude={{"/dev/*","/proc/*","/sys/*",'
                f'"/tmp/*","/run/*","/mnt/*","/media/*",'
                f'"/lost+found","/opt/ridos-core/logs/*"}} '
                f'/ {mnt}/',
                self._log, timeout=3600)

            if rc not in (0, 23, 24):
                # rc 23/24 = some files not transferred (ok for /proc etc)
                log(f'WARNING: rsync exited with {rc} — '
                    f'continuing anyway')
            log('rsync complete.')

            # ── Step 7: Bind system directories ──────────────────────────
            # AFTER rsync — bind mounts must not interfere with copy
            self._status('Binding system directories...', 0.65)
            for d in ['/dev', '/dev/pts', '/proc', '/sys', '/run']:
                sh(f'mkdir -p {mnt}{d}')
                sh(f'mount --bind {d} {mnt}{d}')
                log(f'Bound {d} → {mnt}{d}')

            # ── Step 8: Configure inside chroot ───────────────────────────
            self._status('Configuring system...', 0.68)

            # hostname
            open(f'{mnt}/etc/hostname', 'w').write(host + '\n')
            open(f'{mnt}/etc/hosts', 'w').write(
                f'127.0.0.1   localhost\n'
                f'127.0.1.1   {host}\n'
                f'::1         localhost ip6-localhost ip6-loopback\n')
            log(f'Hostname set: {host}')

            # timezone
            sh(f'ln -sf /usr/share/zoneinfo/{tz} '
               f'{mnt}/etc/localtime')
            open(f'{mnt}/etc/timezone', 'w').write(tz + '\n')
            log(f'Timezone set: {tz}')

            # fstab — using blkid for stable UUIDs
            self._status('Writing fstab...', 0.70)
            root_uuid, _, _ = sh(
                f'blkid -s UUID -o value {root_part}')
            fstab = (
                f'UUID={root_uuid.strip()} / ext4 '
                f'defaults,errors=remount-ro 0 1\n'
                f'tmpfs /tmp tmpfs '
                f'defaults,noatime,nosuid,nodev,size=2G 0 0\n')
            if efi_part:
                efi_uuid, _, _ = sh(
                    f'blkid -s UUID -o value {efi_part}')
                fstab += (f'UUID={efi_uuid.strip()} /boot/efi '
                          f'vfat defaults 0 2\n')
            if swap_part:
                sw_uuid, _, _ = sh(
                    f'blkid -s UUID -o value {swap_part}')
                fstab += f'UUID={sw_uuid.strip()} none swap sw 0 0\n'
            open(f'{mnt}/etc/fstab', 'w').write(fstab)
            log('fstab written.')

            # create user
            self._status(f'Creating user {user}...', 0.73)
            sh(f'chroot {mnt} useradd -m -s /bin/bash '
               f'-G sudo,audio,video,netdev,plugdev '
               f'{user} 2>/dev/null || true')
            proc = subprocess.Popen(
                f'chroot {mnt} chpasswd',
                shell=True, stdin=subprocess.PIPE)
            proc.communicate(
                input=f'{user}:{pw}\n'.encode())
            sh(f'echo "{user} ALL=(ALL) ALL" '
               f'> {mnt}/etc/sudoers.d/{user}')
            sh(f'chmod 440 {mnt}/etc/sudoers.d/{user}')
            log(f'User {user} created.')

            # disable live autologin in installed system
            gdm = f'{mnt}/etc/gdm3/custom.conf'
            if os.path.exists(gdm):
                c = open(gdm).read()
                c = re.sub(r'AutomaticLoginEnable\s*=.*\n', '', c)
                c = re.sub(r'AutomaticLogin\s*=.*\n', '', c)
                open(gdm, 'w').write(c)
                log('Live autologin disabled in installed system.')

            # remove installer autostart from installed system
            for f in [
                f'{mnt}/etc/xdg/autostart/ridos-installer.desktop',
            ]:
                sh(f'rm -f {f} 2>/dev/null || true')

            # ── Step 9: Install GRUB inside chroot ────────────────────────
            # Installing inside chroot is more reliable than from live
            self._status('Installing GRUB (inside chroot)...', 0.78)
            log('Updating apt inside chroot...')
            sh_log(f'chroot {mnt} apt-get update -qq',
                   self._log, timeout=120)

            if efi:
                log('Installing grub-efi-amd64 inside chroot...')
                sh_log(
                    f'chroot {mnt} apt-get install -y '
                    f'--no-install-recommends '
                    f'grub-efi-amd64-bin grub-efi-amd64 os-prober',
                    self._log, timeout=300)
                log(f'Running grub-install (EFI)...')
                rc = sh_log(
                    f'chroot {mnt} grub-install '
                    f'--target=x86_64-efi '
                    f'--efi-directory=/boot/efi '
                    f'--bootloader-id=RIDOS-Core '
                    f'--recheck',
                    self._log, timeout=120)
            else:
                log('Installing grub-pc inside chroot...')
                sh_log(
                    f'chroot {mnt} apt-get install -y '
                    f'--no-install-recommends '
                    f'grub-pc grub-pc-bin os-prober',
                    self._log, timeout=300)
                log(f'Running grub-install (BIOS) on {disk}...')
                rc = sh_log(
                    f'chroot {mnt} grub-install '
                    f'--target=i386-pc '
                    f'--recheck '
                    f'{disk}',
                    self._log, timeout=120)

            if rc != 0:
                log(f'WARNING: grub-install returned {rc}')

            # enable os-prober for multi-boot
            grub_default = f'{mnt}/etc/default/grub'
            if os.path.exists(grub_default):
                c = open(grub_default).read()
                if 'GRUB_DISABLE_OS_PROBER' not in c:
                    c += '\nGRUB_DISABLE_OS_PROBER=false\n'
                else:
                    c = re.sub(
                        r'#?GRUB_DISABLE_OS_PROBER=.*',
                        'GRUB_DISABLE_OS_PROBER=false', c)
                open(grub_default, 'w').write(c)

            # ── Step 10: update-grub ──────────────────────────────────────
            self._status('Generating GRUB configuration...', 0.88)
            log('Running update-grub...')
            sh_log(f'chroot {mnt} update-grub',
                   self._log, timeout=120)

            # ── Step 11: Remove live packages ─────────────────────────────
            self._status('Removing live packages...', 0.93)
            sh_log(
                f'chroot {mnt} apt-get remove -y '
                f'live-boot live-boot-initramfs-tools '
                f'2>/dev/null || true',
                self._log, timeout=120)

            # ── Step 12: Lazy unmount ─────────────────────────────────────
            self._status('Unmounting...', 0.97)
            log('Unmounting all...')
            for d in ['dev/pts', 'dev', 'proc', 'sys', 'run']:
                sh(f'umount -l {mnt}/{d} 2>/dev/null || true')
            sh(f'umount -l {mnt}/boot/efi 2>/dev/null || true')
            sh(f'umount -l {mnt}           2>/dev/null || true')
            sh(f'swapoff {swap_part}        2>/dev/null || true')

            self._status('Installation complete!', 1.0)
            log('\n✓  RIDOS-Core installed successfully!')
            log('Remove the live USB/CD and reboot.')
            GLib.idle_add(self._go, 6)

        except Exception as e:
            import traceback
            log(traceback.format_exc())
            fail(str(e))


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if os.geteuid() != 0:
        os.execvp('sudo', ['sudo', '--'] + sys.argv)
    w = Installer()
    w.connect('destroy', Gtk.main_quit)
    w.show_all()
    Gtk.main()
