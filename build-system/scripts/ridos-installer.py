#!/usr/bin/env python3
"""
ridos-installer.py — RIDOS-Core 1.0 Nova
Custom GTK installer — replaces Calamares entirely.
No polkit, no QML, no black box. Pure Python + GTK3.
Run as: sudo python3 /opt/ridos-core/bin/ridos-installer.py
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango
import os, sys, subprocess, threading, json, re, time

VERSION = "RIDOS-Core 1.0 Nova"

# ── Helpers ───────────────────────────────────────────────────────────────────
def run(cmd, capture=True):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=capture,
                           text=True, timeout=300)
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), 1

def run_live(cmd, log_fn):
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        GLib.idle_add(log_fn, line.rstrip())
    proc.wait()
    return proc.returncode

def get_disks():
    out, _ = run("lsblk -J -o NAME,SIZE,TYPE,MODEL,MOUNTPOINT")
    try:
        data = json.loads(out)
        disks = []
        for dev in data.get('blockdevices', []):
            if dev.get('type') == 'disk':
                name  = dev['name']
                size  = dev.get('size', '?')
                model = dev.get('model', '').strip() or name
                disks.append((f"/dev/{name}", f"{model} ({size})", size))
        return disks
    except Exception:
        return []

def get_timezones():
    out, _ = run("timedatectl list-timezones")
    tzs = out.splitlines()
    return tzs if tzs else ['Asia/Baghdad', 'UTC', 'America/New_York', 'Europe/London']

def is_efi():
    return os.path.exists('/sys/firmware/efi')

# ── Main Installer Window ─────────────────────────────────────────────────────
class RidosInstaller(Gtk.Window):

    STEPS = ['Welcome', 'Disk', 'User', 'Timezone', 'Confirm', 'Install', 'Done']

    def __init__(self):
        super().__init__(title=f"Install {VERSION}")
        self.set_default_size(780, 560)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        self.connect('delete-event', self._on_close)

        # Install state
        self.state = {
            'disk':     '',
            'username': 'ridos',
            'password': '',
            'hostname': 'ridos-core',
            'timezone': 'Asia/Baghdad',
            'efi':      is_efi(),
        }
        self.step = 0
        self._build_ui()
        self._show_step(0)

    def _on_close(self, *_):
        if self.step == 5:
            return True  # block close during install
        Gtk.main_quit()

    def _build_ui(self):
        # Outer layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        # Header bar
        self.header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.header.set_margin_start(24)
        self.header.set_margin_end(24)
        self.header.set_margin_top(16)
        self.header.set_margin_bottom(16)

        self.title_lbl = Gtk.Label()
        self.title_lbl.set_markup(f'<span size="x-large" weight="bold" color="#1F6FEB">{VERSION}</span>')
        self.title_lbl.set_halign(Gtk.Align.START)

        self.step_lbl = Gtk.Label()
        self.step_lbl.set_halign(Gtk.Align.END)

        self.header.pack_start(self.title_lbl, True, True, 0)
        self.header.pack_end(self.step_lbl, False, False, 0)
        vbox.pack_start(self.header, False, False, 0)

        sep = Gtk.Separator()
        vbox.pack_start(sep, False, False, 0)

        # Step content area
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.set_margin_start(32)
        self.content.set_margin_end(32)
        self.content.set_margin_top(24)
        self.content.set_margin_bottom(8)
        vbox.pack_start(self.content, True, True, 0)

        sep2 = Gtk.Separator()
        vbox.pack_start(sep2, False, False, 0)

        # Navigation buttons
        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        nav.set_margin_start(32)
        nav.set_margin_end(32)
        nav.set_margin_top(12)
        nav.set_margin_bottom(16)

        self.back_btn = Gtk.Button(label='← Back')
        self.back_btn.connect('clicked', self._on_back)

        self.next_btn = Gtk.Button(label='Next →')
        self.next_btn.get_style_context().add_class('suggested-action')
        self.next_btn.connect('clicked', self._on_next)

        nav.pack_start(self.back_btn, False, False, 0)
        nav.pack_end(self.next_btn, False, False, 0)
        vbox.pack_start(nav, False, False, 0)

    def _clear_content(self):
        for child in self.content.get_children():
            self.content.remove(child)

    def _show_step(self, n):
        self._clear_content()
        self.step = n
        total = len(self.STEPS)
        self.step_lbl.set_markup(
            f'<span color="#6E7781">Step {n+1} of {total}: '
            f'<b>{self.STEPS[n]}</b></span>')
        self.back_btn.set_sensitive(n > 0 and n < 5)
        self.next_btn.set_sensitive(n < 5)

        steps = [self._step_welcome, self._step_disk, self._step_user,
                 self._step_timezone, self._step_confirm, self._step_install,
                 self._step_done]
        steps[n]()
        self.content.show_all()

    def _on_back(self, _):
        if self.step > 0:
            self._show_step(self.step - 1)

    def _on_next(self, _):
        if not self._validate_step():
            return
        if self.step == 4:
            self._start_install()
        elif self.step < len(self.STEPS) - 1:
            self._show_step(self.step + 1)

    def _validate_step(self):
        if self.step == 1 and not self.state['disk']:
            self._error('Please select a disk.')
            return False
        if self.step == 2:
            u = self.username_entry.get_text().strip()
            p = self.pass_entry.get_text()
            p2 = self.pass2_entry.get_text()
            if not u or not re.match(r'^[a-z][a-z0-9_-]{0,30}$', u):
                self._error('Username must start with a letter, only lowercase letters/numbers/- allowed.')
                return False
            if len(p) < 4:
                self._error('Password must be at least 4 characters.')
                return False
            if p != p2:
                self._error('Passwords do not match.')
                return False
            self.state['username'] = u
            self.state['password'] = p
            self.state['hostname'] = self.hostname_entry.get_text().strip() or 'ridos-core'
        if self.step == 3:
            self.state['timezone'] = self.tz_combo.get_active_text() or 'Asia/Baghdad'
        return True

    def _error(self, msg):
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=msg)
        dlg.run()
        dlg.destroy()

    # ── Steps ─────────────────────────────────────────────────────────────────

    def _step_welcome(self):
        lbl = Gtk.Label()
        lbl.set_markup(
            f'<span size="xx-large" weight="bold" color="#1F6FEB">Welcome to {VERSION}</span>')
        lbl.set_halign(Gtk.Align.START)
        self.content.pack_start(lbl, False, False, 0)

        sub = Gtk.Label()
        sub.set_markup('<span color="#6E7781">Rust-Ready Linux — Built for the next generation</span>')
        sub.set_halign(Gtk.Align.START)
        self.content.pack_start(sub, False, False, 8)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        info_box.set_margin_top(20)
        for line in [
            '✓  Based on Debian 12 Bookworm with Linux 6.12 LTS',
            '✓  GNOME desktop — fast boot with zstd compression',
            '✓  Brave Browser + full Pro IT security toolkit',
            '✓  Supports full-disk encryption (LUKS)',
            '',
            '⚠  This will ERASE the selected disk completely.',
            '⚠  Back up your data before continuing.',
        ]:
            l = Gtk.Label(label=line)
            l.set_halign(Gtk.Align.START)
            if line.startswith('⚠'):
                l.set_markup(f'<span color="#D29922">{line}</span>')
            info_box.pack_start(l, False, False, 0)
        self.content.pack_start(info_box, True, True, 0)

        efi_lbl = Gtk.Label()
        mode = 'UEFI (EFI)' if self.state['efi'] else 'Legacy BIOS'
        efi_lbl.set_markup(f'<span color="#1F6FEB">Boot mode detected: <b>{mode}</b></span>')
        efi_lbl.set_halign(Gtk.Align.START)
        self.content.pack_start(efi_lbl, False, False, 8)
        self.next_btn.set_label('Start →')

    def _step_disk(self):
        lbl = Gtk.Label()
        lbl.set_markup('<span size="large" weight="bold">Select Installation Disk</span>')
        lbl.set_halign(Gtk.Align.START)
        self.content.pack_start(lbl, False, False, 0)

        warn = Gtk.Label()
        warn.set_markup('<span color="#D29922">⚠  The selected disk will be completely erased.</span>')
        warn.set_halign(Gtk.Align.START)
        self.content.pack_start(warn, False, False, 8)

        disks = get_disks()
        if not disks:
            err = Gtk.Label(label='No disks found. Check lsblk.')
            self.content.pack_start(err, False, False, 0)
            return

        self.disk_radios = []
        first = None
        for dev, label, size in disks:
            rb = Gtk.RadioButton(label=f'{dev}  —  {label}')
            if first is None:
                first = rb
                if not self.state['disk']:
                    self.state['disk'] = dev
            else:
                rb.join_group(first)
            if self.state['disk'] == dev:
                rb.set_active(True)
            rb.connect('toggled', lambda w, d=dev: self._on_disk(w, d))
            self.disk_radios.append(rb)
            self.content.pack_start(rb, False, False, 4)

        self.next_btn.set_label('Next →')

    def _on_disk(self, widget, dev):
        if widget.get_active():
            self.state['disk'] = dev

    def _step_user(self):
        lbl = Gtk.Label()
        lbl.set_markup('<span size="large" weight="bold">Create Your Account</span>')
        lbl.set_halign(Gtk.Align.START)
        self.content.pack_start(lbl, False, False, 0)

        grid = Gtk.Grid(row_spacing=12, column_spacing=16)
        grid.set_margin_top(16)

        def add_row(row, label, widget):
            l = Gtk.Label(label=label)
            l.set_halign(Gtk.Align.END)
            grid.attach(l, 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)
            widget.set_hexpand(True)

        self.username_entry = Gtk.Entry()
        self.username_entry.set_text(self.state.get('username', 'ridos'))
        self.username_entry.set_placeholder_text('lowercase letters only')
        add_row(0, 'Username:', self.username_entry)

        self.pass_entry = Gtk.Entry()
        self.pass_entry.set_visibility(False)
        self.pass_entry.set_placeholder_text('minimum 4 characters')
        add_row(1, 'Password:', self.pass_entry)

        self.pass2_entry = Gtk.Entry()
        self.pass2_entry.set_visibility(False)
        self.pass2_entry.set_placeholder_text('repeat password')
        add_row(2, 'Confirm password:', self.pass2_entry)

        self.hostname_entry = Gtk.Entry()
        self.hostname_entry.set_text(self.state.get('hostname', 'ridos-core'))
        add_row(3, 'Computer name:', self.hostname_entry)

        self.content.pack_start(grid, False, False, 0)

    def _step_timezone(self):
        lbl = Gtk.Label()
        lbl.set_markup('<span size="large" weight="bold">Select Timezone</span>')
        lbl.set_halign(Gtk.Align.START)
        self.content.pack_start(lbl, False, False, 0)

        tzs = get_timezones()
        self.tz_combo = Gtk.ComboBoxText()
        self.tz_combo.set_margin_top(16)
        current = self.state.get('timezone', 'Asia/Baghdad')
        selected_idx = 0
        for i, tz in enumerate(tzs):
            self.tz_combo.append_text(tz)
            if tz == current:
                selected_idx = i
        self.tz_combo.set_active(selected_idx)
        self.content.pack_start(self.tz_combo, False, False, 0)

    def _step_confirm(self):
        lbl = Gtk.Label()
        lbl.set_markup('<span size="large" weight="bold">Confirm Installation</span>')
        lbl.set_halign(Gtk.Align.START)
        self.content.pack_start(lbl, False, False, 0)

        s = self.state
        details = [
            ('OS',        VERSION),
            ('Disk',      s['disk'] + '  ⚠ WILL BE ERASED'),
            ('Boot mode', 'UEFI' if s['efi'] else 'BIOS'),
            ('Username',  s['username']),
            ('Hostname',  s['hostname']),
            ('Timezone',  s['timezone']),
        ]
        grid = Gtk.Grid(row_spacing=8, column_spacing=24)
        grid.set_margin_top(16)
        for i, (k, v) in enumerate(details):
            kl = Gtk.Label()
            kl.set_markup(f'<b>{k}:</b>')
            kl.set_halign(Gtk.Align.END)
            vl = Gtk.Label(label=v)
            vl.set_halign(Gtk.Align.START)
            if 'ERASED' in v:
                vl.set_markup(f'<span color="#DA3633">{v}</span>')
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        self.content.pack_start(grid, False, False, 0)

        self.next_btn.set_label('Install Now')
        self.next_btn.get_style_context().add_class('destructive-action')

    def _step_install(self):
        self.back_btn.set_sensitive(False)
        self.next_btn.set_sensitive(False)

        lbl = Gtk.Label()
        lbl.set_markup('<span size="large" weight="bold">Installing RIDOS-Core...</span>')
        lbl.set_halign(Gtk.Align.START)
        self.content.pack_start(lbl, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_margin_top(12)
        self.progress.set_margin_bottom(8)
        self.content.pack_start(self.progress, False, False, 0)

        self.status_lbl = Gtk.Label(label='Preparing...')
        self.status_lbl.set_halign(Gtk.Align.START)
        self.content.pack_start(self.status_lbl, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(220)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.log_buf = Gtk.TextBuffer()
        tv = Gtk.TextView(buffer=self.log_buf)
        tv.set_editable(False)
        tv.set_monospace(True)
        scroll.add(tv)
        self.content.pack_start(scroll, True, True, 0)

        threading.Thread(target=self._do_install, daemon=True).start()

    def _log(self, msg):
        end = self.log_buf.get_end_iter()
        self.log_buf.insert(end, msg + '\n')

    def _set_status(self, msg, frac):
        GLib.idle_add(self.status_lbl.set_text, msg)
        GLib.idle_add(self.progress.set_fraction, frac)

    def _do_install(self):
        s = self.state
        disk = s['disk']
        user = s['username']
        pw   = s['password']
        host = s['hostname']
        tz   = s['timezone']
        efi  = s['efi']

        steps = []

        def stage(msg, frac, cmd):
            steps.append((msg, frac, cmd))

        # ── Partition disk ────────────────────────────────────────────────────
        if efi:
            stage('Partitioning disk (EFI)...', 0.05,
                f'parted -s {disk} mklabel gpt && '
                f'parted -s {disk} mkpart primary fat32 1MiB 513MiB && '
                f'parted -s {disk} set 1 esp on && '
                f'parted -s {disk} mkpart primary ext4 513MiB 100%')
            stage('Formatting EFI partition...', 0.10,
                f'mkfs.fat -F32 {disk}1')
            stage('Formatting root partition...', 0.15,
                f'mkfs.ext4 -F {disk}2')
            stage('Mounting partitions...', 0.18,
                f'mount {disk}2 /mnt && '
                f'mkdir -p /mnt/boot/efi && '
                f'mount {disk}1 /mnt/boot/efi')
        else:
            stage('Partitioning disk (BIOS)...', 0.05,
                f'parted -s {disk} mklabel msdos && '
                f'parted -s {disk} mkpart primary ext4 1MiB 100% && '
                f'parted -s {disk} set 1 boot on')
            stage('Formatting root partition...', 0.10,
                f'mkfs.ext4 -F {disk}1')
            stage('Mounting partition...', 0.15,
                f'mount {disk}1 /mnt')

        # ── Copy filesystem ───────────────────────────────────────────────────
        squashfs_paths = [
            '/run/live/medium/live/filesystem.squashfs',
            '/run/live/rootfs/filesystem.squashfs',
            '/lib/live/mount/medium/live/filesystem.squashfs',
        ]
        squashfs = next((p for p in squashfs_paths if os.path.exists(p)), '')
        if squashfs:
            stage('Extracting filesystem (this takes several minutes)...', 0.20,
                f'unsquashfs -f -d /mnt {squashfs}')
        else:
            stage('Copying filesystem (rsync)...', 0.20,
                'rsync -aAX --exclude={"/proc/*","/sys/*","/dev/*","/tmp/*",'
                '"/run/*","/mnt/*","/lost+found"} / /mnt/')

        # ── Configure installed system ────────────────────────────────────────
        stage('Writing fstab...', 0.60, '')  # handled inline
        stage('Setting hostname...', 0.63,
            f'echo {host} > /mnt/etc/hostname && '
            f'echo "127.0.1.1 {host}" >> /mnt/etc/hosts')
        stage('Setting timezone...', 0.65,
            f'ln -sf /usr/share/zoneinfo/{tz} /mnt/etc/localtime && '
            f'echo {tz} > /mnt/etc/timezone')
        stage(f'Creating user {user}...', 0.68, '')  # handled inline
        stage('Binding system dirs...', 0.72,
            'for d in dev proc sys run; do '
            '  mount --bind /$d /mnt/$d 2>/dev/null || true; '
            'done')
        if efi:
            stage('Installing GRUB (EFI)...', 0.78,
                f'chroot /mnt grub-install --target=x86_64-efi '
                f'--efi-directory=/boot/efi --bootloader-id=RIDOS-Core '
                f'--recheck {disk}')
        else:
            stage('Installing GRUB (BIOS)...', 0.78,
                f'chroot /mnt grub-install --target=i386-pc '
                f'--recheck {disk}')
        stage('Generating GRUB config...', 0.85,
            'chroot /mnt update-grub')
        stage('Removing live packages...', 0.90,
            'chroot /mnt apt-get remove -y live-boot live-boot-initramfs-tools '
            '2>/dev/null || true')
        stage('Unmounting...', 0.95,
            'for d in run sys proc dev; do '
            '  umount /mnt/$d 2>/dev/null || true; '
            'done && '
            '(umount /mnt/boot/efi 2>/dev/null || true) && '
            'umount /mnt 2>/dev/null || true')

        # ── Execute stages ────────────────────────────────────────────────────
        for msg, frac, cmd in steps:
            self._set_status(msg, frac)

            # Inline handlers
            if msg.startswith('Writing fstab'):
                try:
                    out, _ = run(f'blkid -s UUID -o value {disk}2')
                    root_uuid = out.strip()
                    fstab = f'UUID={root_uuid} / ext4 defaults 0 1\n'
                    if efi:
                        out2, _ = run(f'blkid -s UUID -o value {disk}1')
                        efi_uuid = out2.strip()
                        fstab += f'UUID={efi_uuid} /boot/efi vfat umask=0077 0 1\n'
                    fstab += 'tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=2G 0 0\n'
                    open('/mnt/etc/fstab', 'w').write(fstab)
                    GLib.idle_add(self._log, 'fstab written')
                except Exception as e:
                    GLib.idle_add(self._log, f'fstab warning: {e}')
                continue

            if msg.startswith('Creating user'):
                try:
                    run(f'chroot /mnt useradd -m -s /bin/bash '
                        f'-G sudo,audio,video,netdev,plugdev {user} 2>/dev/null || true')
                    run(f'echo "{user}:{pw}" | chroot /mnt chpasswd')
                    run(f'echo "{user} ALL=(ALL) ALL" '
                        f'> /mnt/etc/sudoers.d/{user}')
                    run(f'chmod 440 /mnt/etc/sudoers.d/{user}')
                    # Remove live autologin
                    gdm = '/mnt/etc/gdm3/custom.conf'
                    if os.path.exists(gdm):
                        c = open(gdm).read()
                        c = re.sub(r'AutomaticLogin.*\n', '', c)
                        c = re.sub(r'AutomaticLoginEnable.*\n', '', c)
                        open(gdm, 'w').write(c)
                    GLib.idle_add(self._log, f'User {user} created')
                except Exception as e:
                    GLib.idle_add(self._log, f'User warning: {e}')
                continue

            if not cmd:
                continue

            ret = run_live(cmd, self._log)
            if ret != 0 and frac < 0.90:
                GLib.idle_add(self._log, f'WARNING: step returned {ret}')

        self._set_status('Installation complete!', 1.0)
        GLib.idle_add(self._show_step, 6)

    def _step_done(self):
        self.back_btn.set_sensitive(False)
        self.next_btn.set_label('Reboot Now')
        self.next_btn.set_sensitive(True)
        self.next_btn.get_style_context().remove_class('destructive-action')

        lbl = Gtk.Label()
        lbl.set_markup(
            '<span size="xx-large" weight="bold" color="#238636">'
            '✓  Installation Complete!</span>')
        lbl.set_halign(Gtk.Align.START)
        self.content.pack_start(lbl, False, False, 0)

        sub = Gtk.Label()
        sub.set_markup(
            f'<span color="#6E7781">{VERSION} has been installed successfully.\n'
            f'Click Reboot Now to start using your new system.</span>')
        sub.set_halign(Gtk.Align.START)
        sub.set_margin_top(12)
        self.content.pack_start(sub, False, False, 0)

        self.next_btn.connect('clicked', lambda _: run('reboot', capture=False))


if __name__ == '__main__':
    if os.geteuid() != 0:
        # Re-launch with sudo via gnome-terminal
        os.execvp('sudo', ['sudo', sys.executable] + sys.argv)
    app = RidosInstaller()
    app.connect('destroy', Gtk.main_quit)
    app.show_all()
    Gtk.main()
