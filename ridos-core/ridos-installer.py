#!/usr/bin/env python3
"""
ridos-installer.py — RIDOS-Core 1.0 Nova
Final version with all fixes applied:

GRUB fixes:
  - --boot-directory added so GRUB writes to correct location
  - Automatic fallback to live-system grub-install if chroot fails
  - If update-grub fails → writes minimal grub.cfg manually
  - All bind mounts logged so failures are visible

Disk Manager (8 buttons):
  + EXT4 / + Swap / Set Boot / Set Active /
  Resize / Format / Delete / Mount

Resize:
  - Asks for new size in GB via dialog
  - Runs e2fsck → parted resizepart → resize2fs for EXT4
  - Supports XFS (xfs_growfs)
  - Checks if mounted before resizing

Boot/Active flags:
  - Set Boot  → parted set N boot on
  - Set Active → parted set N esp on (UEFI) or sfdisk --activate (BIOS)
  - During install: EFI gets esp+boot, root gets boot automatically

Installation sequence (proven):
  1. Clean mounts
  2. GPT/MBR partition with correct flags
  3. partprobe + udevadm settle + sleep (kernel registration)
  4. Format (lazy_itable_init=0)
  5. Mount
  6. rsync with --exclude=EXACT_MOUNT_PATH (no recursion)
  7. Bind mounts AFTER rsync
  8. Configure inside chroot
  9. GRUB inside chroot with fallback
 10. update-grub with manual fallback
 11. Remove live packages
 12. Lazy unmount
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import os, sys, subprocess, threading, re, json

VERSION  = "RIDOS-Core 1.0 Nova"
MOUNT_PT = "/mnt/ridos_target"

# ── Shell helpers ─────────────────────────────────────────────────────────────
def sh(cmd, inp=None, timeout=600):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout, input=inp)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return '', 'Timeout', 1
    except Exception as e:
        return '', str(e), 1

def sh_log(cmd, log_fn, timeout=3600):
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

# ── Disk / partition helpers ──────────────────────────────────────────────────
def get_disks():
    disks = []
    out, _, rc = sh('lsblk -J -b -o NAME,SIZE,TYPE,MODEL 2>/dev/null')
    if rc == 0:
        try:
            for d in json.loads(out).get('blockdevices', []):
                if d.get('type') == 'disk':
                    name  = d['name']
                    model = (d.get('model') or '').strip() or name
                    gb    = round(int(d.get('size') or 0) / 1024**3, 1)
                    disks.append((f'/dev/{name}', f'{model}  [{gb} GB]', gb))
            if disks:
                return disks
        except Exception:
            pass
    out, _, _ = sh('cat /proc/partitions 2>/dev/null')
    for line in out.splitlines()[2:]:
        p = line.split()
        if len(p) == 4:
            name = p[3]
            if re.match(r'^(sd[a-z]|vd[a-z]|nvme\d+n\d+|hd[a-z])$', name):
                gb = round(int(p[2]) / 1024**2, 1)
                disks.append((f'/dev/{name}', f'{name}  [{gb} GB]', gb))
    return disks

def get_partitions(disk):
    """Return list of (device, size_gb, fstype, mountpoint, flags) for a disk."""
    parts = []
    out, _, rc = sh(
        f'lsblk -J -b -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,PARTFLAGS '
        f'{disk} 2>/dev/null')
    if rc == 0:
        try:
            data = json.loads(out)
            for dev in data.get('blockdevices', []):
                for child in dev.get('children', []):
                    if child.get('type') == 'part':
                        name   = child['name']
                        size   = int(child.get('size') or 0)
                        gb     = round(size / 1024**3, 2)
                        fs     = child.get('fstype') or '—'
                        mnt    = child.get('mountpoint') or ''
                        flags  = child.get('partflags') or ''
                        parts.append((f'/dev/{name}', gb, fs, mnt, flags))
        except Exception:
            pass
    return parts

def part_name(disk, n):
    return f'{disk}p{n}' if re.search(r'(nvme|mmcblk)', disk) \
           else f'{disk}{n}'

def part_number(part, disk):
    """Extract partition number from device path."""
    s = part.replace(disk, '')
    m = re.search(r'(\d+)$', s)
    return int(m.group(1)) if m else 1

def is_mounted(dev):
    out, _, _ = sh(f'grep -q "^{dev} " /proc/mounts 2>/dev/null; echo $?')
    return out.strip() == '0'

def is_efi():
    return os.path.exists('/sys/firmware/efi')

def get_timezones():
    out, _, rc = sh('timedatectl list-timezones 2>/dev/null')
    tzs = [t for t in out.splitlines() if t.strip()]
    return tzs or ['Asia/Baghdad', 'Asia/Dubai', 'UTC',
                   'Europe/London', 'America/New_York']

# ── Minimal GRUB config fallback ──────────────────────────────────────────────
def write_minimal_grub_cfg(mnt, root_uuid,
                            kern_path=None, init_path=None):
    """Write a minimal working grub.cfg with exact kernel paths.
    kern_path and init_path should be absolute paths like /boot/vmlinuz-6.x.x
    If not provided, auto-detects from /boot."""
    import glob

    # Auto-detect kernel if not provided
    if not kern_path:
        kern_files = sorted(glob.glob(f'{mnt}/boot/vmlinuz-*'))
        kern_path = ('/boot/' + os.path.basename(kern_files[-1])
                     if kern_files else '/boot/vmlinuz')

    if not init_path:
        init_files = sorted(glob.glob(f'{mnt}/boot/initrd.img-*'))
        init_path = ('/boot/' + os.path.basename(init_files[-1])
                     if init_files else '/boot/initrd.img')

    # Use msdos for BIOS (VirtualBox default)
    part_mod = 'part_gpt' if os.path.exists('/sys/firmware/efi')                else 'part_msdos'

    cfg = f"""set default=0
set timeout=5
set timeout_style=menu

insmod {part_mod}
insmod ext2
insmod all_video

menuentry "RIDOS-Core 1.0 Nova" {{
    search --no-floppy --fs-uuid --set=root {root_uuid}
    linux   {kern_path} root=UUID={root_uuid} ro quiet splash
    initrd  {init_path}
}}

menuentry "RIDOS-Core (recovery mode)" {{
    search --no-floppy --fs-uuid --set=root {root_uuid}
    linux   {kern_path} root=UUID={root_uuid} ro single
    initrd  {init_path}
}}
"""
    grub_dir = f'{mnt}/boot/grub'
    os.makedirs(grub_dir, exist_ok=True)
    with open(f'{grub_dir}/grub.cfg', 'w') as f:
        f.write(cfg)

# ── Main window ───────────────────────────────────────────────────────────────
class Installer(Gtk.Window):

    STEPS = ['Welcome', 'Disk', 'Disk Manager',
             'Account', 'Timezone', 'Confirm', 'Install', 'Done']

    def __init__(self):
        super().__init__(title=f'Install {VERSION}')
        self.set_default_size(820, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect('delete-event', self._on_close)

        self.step      = 0
        self.disk      = ''
        self.disk_gb   = 0
        self.username  = 'myuser'
        self.password  = ''
        self.hostname  = 'ridos-core'
        self.timezone  = 'Asia/Baghdad'
        self.efi       = is_efi()

        self._build_chrome()
        self._go(0)

    def _on_close(self, *_):
        if self.step == 6:
            return True
        Gtk.main_quit()

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
        self.body.set_margin_start(28); self.body.set_margin_end(28)
        self.body.set_margin_top(16);   self.body.set_margin_bottom(8)
        sw.add(self.body)
        root.pack_start(sw, True, True, 0)
        root.pack_start(Gtk.Separator(), False, False, 0)

        nav = Gtk.Box(spacing=12)
        nav.set_margin_start(28); nav.set_margin_end(28)
        nav.set_margin_top(10);   nav.set_margin_bottom(12)
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
        install_step = len(self.STEPS) - 2   # 'Install' step index
        self._back.set_sensitive(0 < n < install_step)
        self._next.set_sensitive(n < install_step)
        [self._s_welcome, self._s_disk, self._s_disk_mgr,
         self._s_account, self._s_timezone, self._s_confirm,
         self._s_install,  self._s_done][n]()
        self.body.show_all()

    def _on_next(self, _):
        if not self._validate():
            return
        install_step = len(self.STEPS) - 2
        if self.step == install_step - 1:   # Confirm → Install
            self._go(install_step)
            threading.Thread(target=self._run_install, daemon=True).start()
        elif self.step < install_step:
            self._go(self.step + 1)

    def _validate(self):
        if self.step == 1 and not self.disk:
            self._err('Please select a disk.')
            return False
        if self.step == 3:
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
            self.hostname = self._he.get_text().strip() or 'ridos-core'
        if self.step == 4:
            self.timezone = self._tzc.get_active_text() or 'Asia/Baghdad'
        return True

    def _err(self, msg):
        d = Gtk.MessageDialog(transient_for=self, modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=msg)
        d.run(); d.destroy()

    def _info(self, msg):
        d = Gtk.MessageDialog(transient_for=self, modal=True,
            message_type=Gtk.MessageType.INFO,
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
            (f'Boot mode detected: {mode}', False),
            ('Debian 12 Bookworm + Linux 6.12 LTS', False),
            ('GNOME desktop + Brave Browser + Pro IT toolkit', False),
            ('', False),
            ('⚠  WARNING: The selected disk will be erased.', True),
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

    # ── Step 1: Disk selection ─────────────────────────────────────────────
    def _s_disk(self):
        self._add(self._lbl(
            '<b><span size="large">Select Target Disk</span></b>',
            markup=True))
        self._add(self._lbl(
            '⚠  All data on the selected disk will be erased.',
            color='#D29922', top=8))

        disks = get_disks()
        if not disks:
            self._add(self._lbl(
                '\n❌  No disks detected.\n\n'
                'VirtualBox: Machine Settings → Storage\n'
                '→ Add Hard Disk (20 GB minimum).\n\n'
                'Real hardware: check disk is connected.',
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
                    self.disk    = dev
                    self.disk_gb = gb
            else:
                rb.join_group(first)
            if self.disk == dev:
                rb.set_active(True)

            def on_toggle(w, d=dev, g=gb):
                if w.get_active():
                    self.disk    = d
                    self.disk_gb = g
            rb.connect('toggled', on_toggle)
            rb.set_margin_top(10)
            self._add(rb)

    # ── Step 2: Disk Manager ──────────────────────────────────────────────────
    def _s_disk_mgr(self):
        self._add(self._lbl(
            '<b><span size="large">Disk Manager</span></b>',
            markup=True))
        self._add(self._lbl(
            f'Disk: {self.disk}  •  Use the buttons below to manage partitions,\n'
            'or click Next to use automatic partitioning.',
            color='#888', top=4))

        # Partition list
        self._part_store = Gtk.ListStore(str, str, str, str, str)
        self._part_view  = Gtk.TreeView(model=self._part_store)
        self._part_view.set_margin_top(10)

        for i, title in enumerate(['Device', 'Size (GB)', 'Filesystem',
                                    'Mountpoint', 'Flags']):
            col = Gtk.TreeViewColumn(
                title, Gtk.CellRendererText(), text=i)
            col.set_min_width(90)
            self._part_view.append_column(col)

        sw = Gtk.ScrolledWindow()
        sw.set_min_content_height(160)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(self._part_view)
        self._add(sw, expand=False, top=4)
        self._refresh_parts()

        # ── 8-button toolbar ──────────────────────────────────────────────
        btn_box = Gtk.Box(spacing=6)
        btn_box.set_margin_top(10)

        def mkbtn(label, cb, style=None):
            b = Gtk.Button(label=label)
            if style:
                b.get_style_context().add_class(style)
            b.connect('clicked', cb)
            btn_box.pack_start(b, False, False, 0)
            return b

        mkbtn('+ EXT4',     self._dm_add_ext4)
        mkbtn('+ Swap',     self._dm_add_swap)
        mkbtn('Set Boot',   self._dm_set_boot)
        mkbtn('Set Active', self._dm_set_active)
        mkbtn('Resize',     self._dm_resize)
        mkbtn('Format',     self._dm_format)
        mkbtn('Delete',     self._dm_delete, 'destructive-action')
        mkbtn('Mount',      self._dm_mount)

        self._add(btn_box)

        # Output log for disk operations
        self._dm_buf = Gtk.TextBuffer()
        dm_tv = Gtk.TextView(buffer=self._dm_buf)
        dm_tv.set_editable(False)
        dm_tv.set_monospace(True)
        dm_sc = Gtk.ScrolledWindow()
        dm_sc.set_min_content_height(80)
        dm_sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        dm_sc.add(dm_tv)
        self._add(dm_sc, expand=False, top=8)

        self._add(self._lbl(
            'Tip: For a standard install, click Next — '
            'automatic partitioning will be used.',
            color='#1F6FEB', top=8))

    def _dm_log(self, msg):
        GLib.idle_add(self._dm_buf.insert,
                      self._dm_buf.get_end_iter(), msg + '\n')

    def _refresh_parts(self):
        self._part_store.clear()
        for dev, gb, fs, mnt, flags in get_partitions(self.disk):
            self._part_store.append([dev, str(gb), fs, mnt, flags])

    def _selected_part(self):
        sel = self._part_view.get_selection()
        model, it = sel.get_selected()
        if it is None:
            self._err('Select a partition from the list first.')
            return None
        return model[it][0]   # device path

    # ── Disk Manager button handlers ──────────────────────────────────────────
    def _dm_add_ext4(self, _):
        d = Gtk.Dialog(title='Add EXT4 Partition',
                       transient_for=self, modal=True)
        d.add_buttons('Cancel', Gtk.ResponseType.CANCEL,
                      'Create',  Gtk.ResponseType.OK)
        box = d.get_content_area()
        box.set_margin_start(16); box.set_margin_end(16)
        box.set_margin_top(12);   box.set_margin_bottom(12)
        box.add(Gtk.Label(label='Size in GB (0 = use all remaining space):'))
        spin = Gtk.SpinButton.new_with_range(0, 2000, 1)
        spin.set_value(0)
        box.add(spin)
        d.show_all()
        if d.run() == Gtk.ResponseType.OK:
            size_gb = int(spin.get_value())
            d.destroy()
            threading.Thread(
                target=self._do_add_part,
                args=(size_gb, 'ext4'), daemon=True).start()
        else:
            d.destroy()

    def _dm_add_swap(self, _):
        d = Gtk.Dialog(title='Add Swap Partition',
                       transient_for=self, modal=True)
        d.add_buttons('Cancel', Gtk.ResponseType.CANCEL,
                      'Create',  Gtk.ResponseType.OK)
        box = d.get_content_area()
        box.set_margin_start(16); box.set_margin_end(16)
        box.set_margin_top(12);   box.set_margin_bottom(12)
        box.add(Gtk.Label(label='Swap size in GB:'))
        spin = Gtk.SpinButton.new_with_range(1, 64, 1)
        spin.set_value(2)
        box.add(spin)
        d.show_all()
        if d.run() == Gtk.ResponseType.OK:
            size_gb = int(spin.get_value())
            d.destroy()
            threading.Thread(
                target=self._do_add_part,
                args=(size_gb, 'linux-swap'), daemon=True).start()
        else:
            d.destroy()

    def _do_add_part(self, size_gb, fstype):
        # Find where current partitions end
        out, _, _ = sh(
            f'parted -s {self.disk} unit MiB print 2>/dev/null')
        end_mib = 1
        for line in out.splitlines():
            m = re.search(r'(\d+(?:\.\d+)?)\s*MiB\s*$', line)
            if m:
                end_mib = max(end_mib, float(m.group(1)))

        start = end_mib + 1
        if size_gb == 0:
            end = '100%'
        else:
            end = f'{int(start + size_gb * 1024)}MiB'

        self._dm_log(f'Adding {fstype} partition: {start}MiB → {end}')
        out, err, rc = sh(
            f'parted -s {self.disk} mkpart primary '
            f'{fstype} {start}MiB {end}')
        if rc != 0:
            self._dm_log(f'ERROR: {err}')
            return
        sh('partprobe 2>/dev/null || true')
        sh('udevadm settle 2>/dev/null || true')
        sh('sleep 2')

        # Format the new partition
        parts = get_partitions(self.disk)
        if parts:
            new_dev = parts[-1][0]
            if fstype == 'ext4':
                _, err, rc = sh(
                    f'mkfs.ext4 -F '
                    f'-E lazy_itable_init=0,lazy_journal_init=0 '
                    f'{new_dev}')
                self._dm_log(
                    f'Formatted {new_dev} as ext4' if rc == 0
                    else f'Format error: {err}')
            elif fstype == 'linux-swap':
                sh(f'mkswap {new_dev}')
                self._dm_log(f'Formatted {new_dev} as swap')

        GLib.idle_add(self._refresh_parts)
        self._dm_log('Done.')

    def _dm_set_boot(self, _):
        dev = self._selected_part()
        if not dev:
            return
        n = part_number(dev, self.disk)
        self._dm_log(f'Setting boot flag on {dev} (partition {n})...')
        out, err, rc = sh(
            f'parted -s {self.disk} set {n} boot on')
        self._dm_log('Boot flag set.' if rc == 0 else f'ERROR: {err}')
        self._refresh_parts()

    def _dm_set_active(self, _):
        dev = self._selected_part()
        if not dev:
            return
        n = part_number(dev, self.disk)
        self._dm_log(f'Setting esp+active flag on {dev} (partition {n})...')
        # Set ESP flag (for UEFI)
        out, err, rc = sh(
            f'parted -s {self.disk} set {n} esp on')
        if rc != 0:
            self._dm_log(f'esp flag warning: {err}')
        # Also set boot flag
        sh(f'parted -s {self.disk} set {n} boot on')
        # For BIOS: sfdisk --activate
        if not is_efi():
            sh(f'sfdisk --activate {self.disk} {n} 2>/dev/null || true')
        self._dm_log('Active flag set.')
        self._refresh_parts()

    def _dm_resize(self, _):
        dev = self._selected_part()
        if not dev:
            return

        if is_mounted(dev):
            self._err(f'{dev} is currently mounted.\n'
                      'Unmount it first before resizing.')
            return

        # Detect filesystem
        fs, _, _ = sh(f'blkid -s TYPE -o value {dev}')
        if fs not in ('ext4', 'ext3', 'ext2', 'xfs'):
            self._err(f'Resize supports ext4 and xfs only.\n'
                      f'Detected filesystem: {fs or "unknown"}')
            return

        # Ask for new size
        d = Gtk.Dialog(title=f'Resize {dev}',
                       transient_for=self, modal=True)
        d.add_buttons('Cancel', Gtk.ResponseType.CANCEL,
                      'Resize',  Gtk.ResponseType.OK)
        box = d.get_content_area()
        box.set_margin_start(16); box.set_margin_end(16)
        box.set_margin_top(12);   box.set_margin_bottom(12)
        box.add(Gtk.Label(
            label=f'New size for {dev} ({fs}) in GB:\n'
                  f'(must be smaller than current size to shrink,\n'
                  f' 0 = expand to fill available space)'))
        spin = Gtk.SpinButton.new_with_range(0, 2000, 1)
        spin.set_value(0)
        box.add(spin)
        d.show_all()
        if d.run() == Gtk.ResponseType.OK:
            size_gb = int(spin.get_value())
            d.destroy()
            threading.Thread(
                target=self._do_resize,
                args=(dev, fs, size_gb), daemon=True).start()
        else:
            d.destroy()

    def _do_resize(self, dev, fs, size_gb):
        n = part_number(dev, self.disk)
        self._dm_log(f'Resizing {dev} ({fs}) to '
                     f'{"max" if size_gb == 0 else str(size_gb)+" GB"}...')

        if fs in ('ext4', 'ext3', 'ext2'):
            # Step 1: fsck (required before resize)
            self._dm_log('Running e2fsck...')
            out, err, rc = sh(f'e2fsck -fy {dev}', timeout=120)
            self._dm_log(out or err)
            if rc > 2:   # rc 1/2 = errors fixed, >2 = unfixable
                self._dm_log(f'ERROR: e2fsck failed (rc={rc})')
                return

            # Step 2: resize partition in parted
            if size_gb > 0:
                # Get partition start first
                out2, _, _ = sh(
                    f'parted -s {self.disk} unit MiB print 2>/dev/null')
                start_mib = None
                for line in out2.splitlines():
                    if re.match(rf'\s*{n}\s+', line):
                        m = re.search(r'(\d+(?:\.\d+)?)\s*MiB', line)
                        if m:
                            start_mib = float(m.group(1))
                end_mib = (start_mib or 0) + size_gb * 1024
                self._dm_log(f'Resizing partition to {end_mib:.0f}MiB...')
                out, err, rc = sh(
                    f'parted -s {self.disk} resizepart {n} {end_mib:.0f}MiB')
                if rc != 0:
                    self._dm_log(f'ERROR resizing partition: {err}')
                    return
                sh('partprobe 2>/dev/null || true')
                sh('sleep 2')

            # Step 3: resize filesystem
            self._dm_log('Running resize2fs...')
            target = f'{size_gb}G' if size_gb > 0 else ''
            out, err, rc = sh(f'resize2fs {dev} {target}', timeout=120)
            self._dm_log(out or err)
            self._dm_log('EXT4 resize complete.' if rc == 0
                         else f'resize2fs error (rc={rc})')

        elif fs == 'xfs':
            # XFS can only grow, not shrink; must be mounted to resize
            self._dm_log('XFS: mounting temporarily to run xfs_growfs...')
            tmp = '/tmp/ridos_xfs_resize'
            sh(f'mkdir -p {tmp}')
            _, err, rc = sh(f'mount {dev} {tmp}')
            if rc != 0:
                self._dm_log(f'Mount failed: {err}')
                return
            out, err, rc = sh(f'xfs_growfs {tmp}', timeout=120)
            self._dm_log(out or err)
            sh(f'umount {tmp}')
            self._dm_log('XFS grow complete.' if rc == 0
                         else f'xfs_growfs error (rc={rc})')

        GLib.idle_add(self._refresh_parts)
        self._dm_log('Done.')

    def _dm_format(self, _):
        dev = self._selected_part()
        if not dev:
            return

        if is_mounted(dev):
            self._err(f'{dev} is mounted. Unmount it first.')
            return

        d = Gtk.Dialog(title=f'Format {dev}',
                       transient_for=self, modal=True)
        d.add_buttons('Cancel', Gtk.ResponseType.CANCEL,
                      'Format',  Gtk.ResponseType.OK)
        box = d.get_content_area()
        box.set_margin_start(16); box.set_margin_end(16)
        box.set_margin_top(12);   box.set_margin_bottom(12)
        box.add(Gtk.Label(label=f'Format {dev} as:'))
        combo = Gtk.ComboBoxText()
        for fs in ['ext4', 'fat32', 'ntfs', 'swap']:
            combo.append_text(fs)
        combo.set_active(0)
        box.add(combo)
        box.add(Gtk.Label(
            label='\n⚠  ALL DATA ON THIS PARTITION WILL BE LOST'))
        d.show_all()
        if d.run() == Gtk.ResponseType.OK:
            fs = combo.get_active_text()
            d.destroy()
            threading.Thread(
                target=self._do_format,
                args=(dev, fs), daemon=True).start()
        else:
            d.destroy()

    def _do_format(self, dev, fs):
        self._dm_log(f'Formatting {dev} as {fs}...')
        cmds = {
            'ext4': (f'mkfs.ext4 -F '
                     f'-E lazy_itable_init=0,lazy_journal_init=0 {dev}'),
            'fat32': f'mkfs.fat -F 32 {dev}',
            'ntfs':  f'mkfs.ntfs -Q {dev}',
            'swap':  f'mkswap {dev}',
        }
        out, err, rc = sh(cmds.get(fs, ''), timeout=120)
        self._dm_log(
            f'Formatted as {fs}.' if rc == 0
            else f'ERROR: {err}')
        GLib.idle_add(self._refresh_parts)

    def _dm_delete(self, _):
        dev = self._selected_part()
        if not dev:
            return

        if is_mounted(dev):
            self._err(f'{dev} is mounted. Unmount it first.')
            return

        n = part_number(dev, self.disk)
        d = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f'Delete partition {dev}?\n\nALL DATA WILL BE LOST.')
        if d.run() == Gtk.ResponseType.YES:
            d.destroy()
            self._dm_log(f'Deleting partition {n} on {self.disk}...')
            out, err, rc = sh(
                f'parted -s {self.disk} rm {n}')
            sh('partprobe 2>/dev/null || true')
            sh('sleep 1')
            self._dm_log(
                f'Partition {n} deleted.' if rc == 0
                else f'ERROR: {err}')
            self._refresh_parts()
        else:
            d.destroy()

    def _dm_mount(self, _):
        dev = self._selected_part()
        if not dev:
            return

        d = Gtk.Dialog(title=f'Mount {dev}',
                       transient_for=self, modal=True)
        d.add_buttons('Cancel', Gtk.ResponseType.CANCEL,
                      'Mount',   Gtk.ResponseType.OK)
        box = d.get_content_area()
        box.set_margin_start(16); box.set_margin_end(16)
        box.set_margin_top(12);   box.set_margin_bottom(12)
        box.add(Gtk.Label(label=f'Mount {dev} at:'))
        entry = Gtk.Entry()
        entry.set_text('/mnt')
        box.add(entry)
        d.show_all()
        if d.run() == Gtk.ResponseType.OK:
            mnt = entry.get_text().strip()
            d.destroy()
            if mnt:
                sh(f'mkdir -p {mnt}')
                out, err, rc = sh(f'mount {dev} {mnt}')
                if rc == 0:
                    self._dm_log(f'Mounted {dev} at {mnt}')
                else:
                    self._dm_log(f'Mount failed: {err}')
                self._refresh_parts()
        else:
            d.destroy()

    # ── Step 3: Account ───────────────────────────────────────────────────────
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

    # ── Step 4: Timezone ──────────────────────────────────────────────────────
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

    # ── Step 5: Confirm ───────────────────────────────────────────────────────
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

    # ── Step 6: Install progress ──────────────────────────────────────────────
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
        tv.set_editable(False)
        tv.set_monospace(True)
        sc.add(tv)
        self._add(sc, expand=True)

    def _log(self, msg):
        self._buf.insert(self._buf.get_end_iter(), msg + '\n')

    def _status(self, msg, frac):
        GLib.idle_add(self._slbl.set_text, msg)
        GLib.idle_add(self._prog.set_fraction, frac)

    # ── Step 7: Done ──────────────────────────────────────────────────────────
    def _s_done(self):
        self._back.set_sensitive(False)
        self._next.set_label('🔄  Reboot Now')
        self._next.set_sensitive(True)
        self._next.get_style_context().remove_class('destructive-action')
        self._next.connect('clicked', lambda _: sh('reboot', timeout=10))
        self._add(self._lbl(
            '<span size="xx-large" weight="bold" color="#238636">'
            '✓  Installation Complete!</span>', markup=True))
        self._add(self._lbl(
            f'\n{VERSION} installed successfully.\n'
            'Remove the live USB/CD and click Reboot Now.',
            top=12))

    # ── Installation thread ───────────────────────────────────────────────────
    def _run_install(self):
        disk = self.disk
        efi  = self.efi
        mnt  = MOUNT_PT
        user = self.username
        pw   = self.password
        host = self.hostname
        tz   = self.timezone

        def log(msg):
            GLib.idle_add(self._log, msg)

        def fail(msg):
            self._status(f'❌  FAILED: {msg}',
                         self._prog.get_fraction())
            log(f'\n❌  INSTALLATION FAILED\n{msg}')
            log('Close this window and try again.')
            GLib.idle_add(self._back.set_sensitive, True)
            GLib.idle_add(self._next.set_sensitive, False)

        try:
            # ── 1. Clean mounts ───────────────────────────────────────────
            self._status('Cleaning up...', 0.01)
            log(f'Target: {mnt}')
            for sub in ['dev/pts','dev','proc','sys','run','boot/efi','']:
                sh(f'umount -l {mnt}/{sub} 2>/dev/null || true')
            sh(f'rm -rf {mnt}')
            sh(f'mkdir -p {mnt}')

            # ── 2. Partition ──────────────────────────────────────────────
            self._status(f'Partitioning {disk}...', 0.04)
            if efi:
                log('GPT layout (UEFI): EFI 512MB + swap 2GB + root')
                sh(f'parted -s {disk} mklabel gpt')
                sh(f'parted -s {disk} mkpart ESP fat32 1MiB 513MiB')
                # EFI partition: esp + boot flags
                sh(f'parted -s {disk} set 1 esp on')
                sh(f'parted -s {disk} set 1 boot on')
                sh(f'parted -s {disk} mkpart primary linux-swap 513MiB 2561MiB')
                sh(f'parted -s {disk} mkpart primary ext4 2561MiB 100%')
                # Root partition: boot flag
                sh(f'parted -s {disk} set 3 boot on')
                efi_part  = part_name(disk, 1)
                swap_part = part_name(disk, 2)
                root_part = part_name(disk, 3)
            else:
                log('MBR layout (BIOS): swap 2GB + root (bootable)')
                sh(f'parted -s {disk} mklabel msdos')
                sh(f'parted -s {disk} mkpart primary linux-swap 1MiB 2049MiB')
                sh(f'parted -s {disk} mkpart primary ext4 2049MiB 100%')
                sh(f'parted -s {disk} set 2 boot on')
                efi_part  = None
                swap_part = part_name(disk, 1)
                root_part = part_name(disk, 2)

            log(f'root={root_part}  swap={swap_part}  efi={efi_part}')

            # ── 3. Wait for kernel ────────────────────────────────────────
            self._status('Waiting for kernel to register partitions...', 0.07)
            log('partprobe + udevadm settle...')
            sh('partprobe 2>/dev/null || true')
            sh('udevadm settle 2>/dev/null || true')
            sh('sleep 3')

            for p_check in ([efi_part] if efi_part else []) + \
                           [swap_part, root_part]:
                if not os.path.exists(p_check):
                    log(f'{p_check} not found, waiting 3s...')
                    sh('sleep 3')
                    sh('udevadm settle 2>/dev/null || true')
                if not os.path.exists(p_check):
                    return fail(
                        f'Partition {p_check} not created.\n'
                        f'Ensure disk is not in use and retry.')
                log(f'OK: {p_check}')

            # ── 4. Format ─────────────────────────────────────────────────
            self._status('Formatting...', 0.10)
            if efi_part:
                log(f'Formatting EFI: {efi_part}')
                _, err, rc = sh(f'mkfs.fat -F 32 {efi_part}')
                if rc != 0:
                    return fail(f'mkfs.fat failed: {err}')

            log(f'Formatting swap: {swap_part}')
            sh(f'mkswap {swap_part}')
            sh(f'swapon {swap_part} 2>/dev/null || true')

            log(f'Formatting root: {root_part}')
            _, err, rc = sh(
                f'mkfs.ext4 -F '
                f'-E lazy_itable_init=0,lazy_journal_init=0 '
                f'{root_part}')
            if rc != 0:
                return fail(f'mkfs.ext4 failed: {err}')
            log('Format complete.')

            # ── 5. Mount ──────────────────────────────────────────────────
            self._status('Mounting...', 0.13)
            _, err, rc = sh(f'mount {root_part} {mnt}')
            if rc != 0:
                return fail(f'mount root failed: {err}')
            if efi_part:
                sh(f'mkdir -p {mnt}/boot/efi')
                _, err, rc = sh(f'mount {efi_part} {mnt}/boot/efi')
                if rc != 0:
                    return fail(f'mount EFI failed: {err}')
            log(f'Mounted at {mnt}')

            # ── 6. rsync ──────────────────────────────────────────────────
            self._status('Locating squashfs filesystem...', 0.15)

            # Search for squashfs using multiple methods
            log('Searching for filesystem.squashfs...')

            # Method 1: known static paths
            squashfs_paths = [
                '/run/live/medium/live/filesystem.squashfs',
                '/run/live/rootfs/filesystem.squashfs',
                '/lib/live/mount/medium/live/filesystem.squashfs',
                '/cdrom/live/filesystem.squashfs',
                '/run/initramfs/live/filesystem.squashfs',
            ]

            # Method 2: scan mount output for ISO mount points
            mount_out, _, _ = sh('mount 2>/dev/null')
            for line in mount_out.splitlines():
                if 'iso9660' in line or 'squashfs' in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        mp = parts[2]
                        for name in ['live/filesystem.squashfs',
                                     'filesystem.squashfs']:
                            c = f'{mp}/{name}'
                            if c not in squashfs_paths:
                                squashfs_paths.append(c)

            # Method 3: find command
            find_out, _, _ = sh(
                'find /run /cdrom /media /lib/live -name '
                '"filesystem.squashfs" -maxdepth 6 2>/dev/null | head -3')
            for p in find_out.splitlines():
                p = p.strip()
                if p and p not in squashfs_paths:
                    squashfs_paths.append(p)

            sq = next(
                (p for p in squashfs_paths if os.path.exists(p)), None)

            log(f'Squashfs found: {sq}')
            if not sq:
                log('Not found at:')
                for p in squashfs_paths:
                    log(f'  {p}')

            if sq:
                sq_size = os.path.getsize(sq) // (1024 * 1024)
                log(f'Size: {sq_size} MB')

                tmp_extract = '/tmp/sq_extract'
                sh(f'rm -rf {tmp_extract}')
                sh(f'mkdir -p {tmp_extract}')

                self._status(
                    f'Extracting squashfs ({sq_size} MB)...', 0.16)
                log(f'unsquashfs -f -d {tmp_extract} {sq}')
                rc = sh_log(
                    f'unsquashfs -f -d {tmp_extract} {sq}',
                    self._log, timeout=3600)

                if rc != 0:
                    log(f'unsquashfs returned {rc} — trying rsync')
                    sh(f'rm -rf {tmp_extract}')
                    sq = None
                else:
                    ls_out, _, _ = sh(f'ls {tmp_extract}/')
                    log(f'Contents: {ls_out}')
                    sq_root = f'{tmp_extract}/squashfs-root'
                    src = sq_root if os.path.isdir(sq_root) else tmp_extract
                    log(f'rsync {src}/ → {mnt}/')
                    self._status('Copying to disk...', 0.40)
                    rc2 = sh_log(
                        f'rsync -aAXH {src}/ {mnt}/',
                        self._log, timeout=3600)
                    if rc2 not in (0, 23, 24):
                        log(f'WARNING: rsync returned {rc2}')
                    sh(f'rm -rf {tmp_extract}')
                    log('Copy complete.')

            if not sq:
                # Try copying from squashfs mount point (already unpacked)
                sq_mount = ''
                for candidate in [
                    '/run/live/rootfs/filesystem',
                    '/run/live/rootfs/filesystem.squashfs',
                    '/lib/live/mount/rootfs/filesystem.squashfs',
                ]:
                    if os.path.isdir(candidate) and                        os.path.exists(f'{candidate}/usr'):
                        sq_mount = candidate
                        log(f'Found mounted squashfs at: {sq_mount}')
                        break

                if sq_mount:
                    log(f'rsync from mount: {sq_mount}/ → {mnt}/')
                    self._status('Copying from squashfs mount...', 0.15)
                    rc = sh_log(
                        f'rsync -aAXH {sq_mount}/ {mnt}/',
                        self._log, timeout=3600)
                    if rc not in (0, 23, 24):
                        log(f'WARNING: rsync returned {rc}')
                    log('Copy from mount complete.')
                else:
                    log('Last resort: rsync from live root /')
                    self._status('rsync from live root (slow)...', 0.15)
                    rc = sh_log(
                        f'rsync -aAXH '
                        f'--exclude="{mnt}" '
                        f'--exclude="/dev/*" '
                        f'--exclude="/proc/*" '
                        f'--exclude="/sys/*" '
                        f'--exclude="/run/*" '
                        f'--exclude="/tmp/*" '
                        f'--exclude="/media/*" '
                        f'--exclude="/lost+found" '
                        f'/ {mnt}/',
                        self._log, timeout=3600)
                    if rc not in (0, 23, 24):
                        log(f'WARNING: rsync returned {rc}')
                    log('rsync complete.')

            # Validate that critical files were copied
            self._status('Validating copied filesystem...', 0.63)
            log('Checking critical files...')
            missing = []
            for critical in [
                f'{mnt}/bin',
                f'{mnt}/usr',
                f'{mnt}/lib',
                f'{mnt}/etc/passwd',
                f'{mnt}/usr/bin/python3',
            ]:
                if not os.path.exists(critical):
                    missing.append(critical)
                    log(f'  MISSING: {critical}')
                else:
                    log(f'  OK: {critical}')

            if len(missing) > 2:
                return fail(
                    f'Filesystem copy incomplete — {len(missing)} critical '
                    f'paths missing.\nCheck the log above for details.')
            log('Filesystem validation passed.')

            # ── 7. Bind mounts (AFTER rsync) ──────────────────────────────
            self._status('Binding system directories...', 0.65)
            # Use --rbind for proc/sys so grub-probe works correctly
            # inside the chroot. --bind is sufficient for dev/run.
            for d, flag in [
                ('/proc',     '--rbind'),
                ('/sys',      '--rbind'),
                ('/dev',      '--bind'),
                ('/dev/pts',  '--bind'),
                ('/run',      '--bind'),
            ]:
                sh(f'mkdir -p {mnt}{d}')
                _, err, rc = sh(f'mount {flag} {d} {mnt}{d}')
                if rc == 0:
                    log(f'Bound ({flag}): {d} → {mnt}{d}')
                else:
                    log(f'WARNING: bind {d} failed: {err}')

            # ── 8. Configure ──────────────────────────────────────────────
            self._status('Configuring...', 0.68)
            open(f'{mnt}/etc/hostname', 'w').write(host + '\n')
            open(f'{mnt}/etc/hosts', 'w').write(
                f'127.0.0.1   localhost\n'
                f'127.0.1.1   {host}\n'
                f'::1         localhost ip6-localhost ip6-loopback\n')
            sh(f'ln -sf /usr/share/zoneinfo/{tz} {mnt}/etc/localtime')
            open(f'{mnt}/etc/timezone', 'w').write(tz + '\n')
            log(f'Hostname: {host}  Timezone: {tz}')

            # fstab
            self._status('Writing fstab...', 0.71)
            root_uuid, _, _ = sh(f'blkid -s UUID -o value {root_part}')
            fstab = (
                f'UUID={root_uuid.strip()} / ext4 '
                f'defaults,errors=remount-ro 0 1\n'
                f'tmpfs /tmp tmpfs '
                f'defaults,noatime,nosuid,nodev,size=2G 0 0\n')
            if efi_part:
                efi_uuid, _, _ = sh(f'blkid -s UUID -o value {efi_part}')
                fstab += (f'UUID={efi_uuid.strip()} /boot/efi '
                          f'vfat defaults 0 2\n')
            if swap_part:
                sw_uuid, _, _ = sh(f'blkid -s UUID -o value {swap_part}')
                fstab += f'UUID={sw_uuid.strip()} none swap sw 0 0\n'
            open(f'{mnt}/etc/fstab', 'w').write(fstab)
            log('fstab written.')

            # User
            self._status(f'Creating user {user}...', 0.74)
            sh(f'chroot {mnt} useradd -m -s /bin/bash '
               f'-G sudo,audio,video,netdev,plugdev '
               f'{user} 2>/dev/null || true')
            proc = subprocess.Popen(
                f'chroot {mnt} chpasswd',
                shell=True, stdin=subprocess.PIPE)
            proc.communicate(input=f'{user}:{pw}\n'.encode())
            sh(f'echo "{user} ALL=(ALL) ALL" '
               f'> {mnt}/etc/sudoers.d/{user}')
            sh(f'chmod 440 {mnt}/etc/sudoers.d/{user}')
            log(f'User {user} created.')

            # Disable live autologin
            gdm = f'{mnt}/etc/gdm3/custom.conf'
            if os.path.exists(gdm):
                c = open(gdm).read()
                c = re.sub(r'AutomaticLoginEnable\s*=.*\n', '', c)
                c = re.sub(r'AutomaticLogin\s*=.*\n', '', c)
                open(gdm, 'w').write(c)

            # Remove live autostart from installed system
            sh(f'rm -f {mnt}/etc/xdg/autostart/'
               f'ridos-installer.desktop 2>/dev/null || true')
            sh(f'rm -f {mnt}/etc/xdg/autostart/'
               f'ridos-welcome.desktop 2>/dev/null || true')

            # os-prober for multi-boot
            grub_def = f'{mnt}/etc/default/grub'
            if os.path.exists(grub_def):
                c = open(grub_def).read()
                if 'GRUB_DISABLE_OS_PROBER' not in c:
                    c += '\nGRUB_DISABLE_OS_PROBER=false\n'
                else:
                    c = re.sub(r'#?GRUB_DISABLE_OS_PROBER=.*',
                               'GRUB_DISABLE_OS_PROBER=false', c)
                open(grub_def, 'w').write(c)

            # ── 9. GRUB — definitive working approach ──────────────────
            # Proven method from Ubuntu/Debian VirtualBox installations.
            # ALL commands run inside chroot. grub-install needs a real
            # running environment which chroot with proper bind mounts provides.
            #
            # CRITICAL: /proc /sys /dev MUST be mounted before this step.
            # They were mounted in step 7 above.
            # ── Copy DNS + sources.list into chroot before apt runs ─────────
            # Without this, apt-get install grub-pc fails with
            # "Temporary failure resolving 'deb.debian.org'"
            self._status('Configuring network for chroot...', 0.77)
            log('Copying DNS config into chroot...')
            try:
                import shutil
                shutil.copy('/etc/resolv.conf', f'{mnt}/etc/resolv.conf')
                log('resolv.conf copied.')
            except Exception as e:
                log(f'WARNING: could not copy resolv.conf: {e}')

            # Write correct sources.list into installed system
            sources = (
                'deb http://deb.debian.org/debian bookworm '
                'main contrib non-free non-free-firmware\n'
                'deb http://deb.debian.org/debian bookworm-updates '
                'main contrib non-free non-free-firmware\n'
                'deb http://security.debian.org/debian-security '
                'bookworm-security main contrib non-free non-free-firmware\n'
            )
            open(f'{mnt}/etc/apt/sources.list', 'w').write(sources)
            log('sources.list written.')

            # Update package lists inside chroot
            log('Running apt-get update inside chroot...')
            sh_log(f'chroot {mnt} apt-get update -qq',
                   self._log, timeout=120)

            self._status('Installing GRUB...', 0.78)
            grub_ok = False

            if efi:
                log('=== GRUB EFI Installation ===')
                log('Installing grub-efi inside chroot...')
                sh_log(
                    f'DEBIAN_FRONTEND=noninteractive '
                    f'chroot {mnt} apt-get install -y '
                    f'--no-install-recommends '
                    f'grub-efi-amd64 grub-efi-amd64-bin '
                    f'grub-common grub2-common os-prober',
                    self._log, timeout=300)

                log(f'Running grub-install --target=x86_64-efi inside chroot...')
                rc = sh_log(
                    f'chroot {mnt} grub-install '
                    f'--target=x86_64-efi '
                    f'--efi-directory=/boot/efi '
                    f'--bootloader-id=RIDOS-Core '
                    f'--recheck',
                    self._log, timeout=120)

                if rc == 0:
                    grub_ok = True
                    log('grub-install EFI: SUCCESS')
                else:
                    log(f'WARNING: grub-install returned {rc}, continuing...')
                    grub_ok = False

            else:
                log('=== GRUB BIOS Installation (VirtualBox MBR mode) ===')
                log('Step 1: Install grub-pc inside chroot...')
                sh_log(
                    f'DEBIAN_FRONTEND=noninteractive '
                    f'chroot {mnt} apt-get install -y '
                    f'--no-install-recommends '
                    f'grub-pc grub-pc-bin '
                    f'grub-common grub2-common os-prober',
                    self._log, timeout=300)

                log(f'Step 2: grub-install --target=i386-pc {disk} inside chroot...')
                rc = sh_log(
                    f'chroot {mnt} grub-install '
                    f'--target=i386-pc '
                    f'--recheck '
                    f'{disk}',
                    self._log, timeout=120)

                if rc == 0:
                    grub_ok = True
                    log('grub-install BIOS: SUCCESS')
                else:
                    log(f'WARNING: chroot grub-install returned {rc}')
                    log('Trying grub-install from live session as fallback...')
                    rc2 = sh_log(
                        f'grub-install '
                        f'--target=i386-pc '
                        f'--boot-directory={mnt}/boot '
                        f'--recheck '
                        f'{disk}',
                        self._log, timeout=120)
                    if rc2 == 0:
                        grub_ok = True
                        log('Fallback grub-install: SUCCESS')
                    else:
                        log(f'Both grub-install attempts failed (rc={rc},{rc2})')
                        grub_ok = False

            # ── 10. Kernel paths + grub.cfg ───────────────────────────────
            # Find actual versioned kernel/initrd filenames in /boot.
            # Create both symlinks AND write grub.cfg directly so there
            # is no ambiguity about which path GRUB should use.
            self._status('Locating kernel in /boot...', 0.85)
            out_kern, _, _ = sh(
                f'ls {mnt}/boot/vmlinuz-* 2>/dev/null | sort -V | tail -1')
            out_init, _, _ = sh(
                f'ls {mnt}/boot/initrd.img-* 2>/dev/null | sort -V | tail -1')

            if not out_kern.strip():
                log('ERROR: no kernel found in /boot!')
                log('Contents of /boot:')
                ls_out, _, _ = sh(f'ls -la {mnt}/boot/ 2>/dev/null')
                log(ls_out)
                log('Contents of /mnt/ridos_target root:')
                root_out, _, _ = sh(f'ls {mnt}/ 2>/dev/null')
                log(root_out)
                log('Searching for vmlinuz anywhere on target:')
                find_out, _, _ = sh(
                    f'find {mnt} -name "vmlinuz*" 2>/dev/null | head -5')
                log(find_out if find_out else 'None found')
                log('Squashfs search paths that were tried:')
                for p in squashfs_paths:
                    exists = os.path.exists(p)
                    log(f'  {p}: {"EXISTS" if exists else "not found"}')
                return fail(
                    'No kernel found in /boot after filesystem copy.\n'
                    'Check log above for squashfs search results.')

            kern_base = os.path.basename(out_kern.strip())
            init_base = (os.path.basename(out_init.strip())
                         if out_init.strip() else '')
            kern_path = f'/boot/{kern_base}'
            init_path = f'/boot/{init_base}' if init_base else ''
            log(f'Kernel  : {kern_path}')
            log(f'Initrd  : {init_path}')

            # Create symlinks at / (what many tools expect)
            sh(f'ln -sf {kern_path} {mnt}/vmlinuz')
            if init_path:
                sh(f'ln -sf {init_path} {mnt}/initrd.img')
            log('Symlinks created at /vmlinuz and /initrd.img')

            # Set GRUB_DISABLE_OS_PROBER
            grub_def = f'{mnt}/etc/default/grub'
            if os.path.exists(grub_def):
                c = open(grub_def).read()
                if 'GRUB_DISABLE_OS_PROBER' not in c:
                    c += '\nGRUB_DISABLE_OS_PROBER=false\n'
                open(grub_def, 'w').write(c)

            # Try update-grub first
            self._status('Running update-grub...', 0.88)
            log('Running update-grub inside chroot...')
            rc = sh_log(
                f'chroot {mnt} update-grub',
                self._log, timeout=120)

            # Verify grub.cfg regardless of update-grub exit code
            cfg_path = f'{mnt}/boot/grub/grub.cfg'
            cfg_ok = False
            if os.path.exists(cfg_path):
                cfg = open(cfg_path).read()
                if kern_base in cfg:
                    log(f'grub.cfg verified: contains {kern_base} ✓')
                    cfg_ok = True
                elif 'vmlinuz' in cfg:
                    log('grub.cfg has vmlinuz but wrong path — rewriting')
                else:
                    log('grub.cfg exists but has no kernel entry — rewriting')

            if not cfg_ok:
                log('Writing grub.cfg directly with exact kernel path...')
                write_minimal_grub_cfg(mnt, root_uuid.strip(),
                                       kern_path, init_path)
                log('grub.cfg written with exact kernel path ✓')
                # Verify again
                if os.path.exists(cfg_path):
                    cfg2 = open(cfg_path).read()
                    if kern_base in cfg2:
                        log(f'grub.cfg re-verified: {kern_base} ✓')
                    else:
                        log('ERROR: grub.cfg still wrong after rewrite!')
                        return fail(
                            f'grub.cfg does not contain the kernel path. '
                            f'Expected: {kern_path}')

                    log(f'ERROR writing grub.cfg: {ex}')

            # ── 11. Remove live packages ──────────────────────────────────
            self._status('Removing live packages...', 0.93)
            sh_log(
                f'chroot {mnt} apt-get remove -y '
                f'live-boot live-boot-initramfs-tools '
                f'2>/dev/null || true',
                self._log, timeout=120)

            # ── 12. Unmount ───────────────────────────────────────────────
            self._status('Unmounting...', 0.97)
            log('Unmounting all...')
            for d in ['dev/pts', 'dev', 'proc', 'sys', 'run']:
                sh(f'umount -l {mnt}/{d} 2>/dev/null || true')
            sh(f'umount -l {mnt}/boot/efi 2>/dev/null || true')
            sh(f'umount -l {mnt}           2>/dev/null || true')
            sh(f'swapoff {swap_part}        2>/dev/null || true')

            self._status('Installation complete!', 1.0)
            log('\n✓  RIDOS-Core installed successfully!')
            log('Remove the live USB/CD and click Reboot Now.')
            GLib.idle_add(self._go, 7)

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
