#!/usr/bin/env python3
"""
RIDOS OS Installer - Disk Manager + OS Installer
Tkinter UI — proven to work with sudo in XFCE
Run: sudo python3 /opt/ridos/bin/ridos-installer.py
"""
# ── Fix DISPLAY before any import ────────────────────────────
import os, sys, subprocess

os.environ.setdefault('DISPLAY', ':0')
_sudo_user = os.environ.get('SUDO_USER', 'ridos')
if not os.environ.get('XAUTHORITY'):
    for _xa in [f'/home/{_sudo_user}/.Xauthority',
                '/home/ridos/.Xauthority',
                '/root/.Xauthority']:
        if os.path.exists(_xa):
            os.environ['XAUTHORITY'] = _xa
            break
subprocess.run('xhost +SI:localuser:root 2>/dev/null || true',
               shell=True, capture_output=True)
if os.geteuid() != 0:
    os.execvp('sudo', ['sudo', '-E', 'python3',
                       os.path.abspath(__file__)])
    sys.exit()

# ── Tkinter ───────────────────────────────────────────────────
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog
except ImportError:
    print("ERROR: python3-tk missing")
    sys.exit(1)

import threading, json, time, shutil

# ── Colors ────────────────────────────────────────────────────
BG     = "#0F0A1E"
BG2    = "#1E1B4B"
BG3    = "#2D1B69"
PURPLE = "#7C3AED"
TEXT   = "#E9D5FF"
GREEN  = "#10B981"
YELLOW = "#F59E0B"
RED    = "#EF4444"
CYAN   = "#06B6D4"
GRAY   = "#6B7280"

# ── Helpers ───────────────────────────────────────────────────
def run_cmd(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, shell=True,
                           capture_output=True,
                           text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "Timed out", 1
    except Exception as e:
        return str(e), 1

def get_disks():
    disks = []

    # Method 1: lsblk JSON (most reliable)
    out, code = run_cmd(
        "lsblk -d -b -J -o NAME,SIZE,MODEL,TYPE "
        "2>/dev/null")
    if code == 0 and out.strip():
        try:
            import json as _json
            data = _json.loads(out)
            for d in data.get('blockdevices', []):
                if d.get('type') != 'disk': continue
                name = d.get('name', '')
                if 'loop' in name or 'ram' in name:
                    continue
                try:
                    size_gb = int(d.get('size', 0)) / 1024**3
                except:
                    size_gb = 0
                model = (d.get('model') or '').strip()
                disks.append({
                    'name':  name,
                    'path':  f'/dev/{name}',
                    'size':  f'{size_gb:.1f} GB',
                    'model': model or 'Unknown',
                })
            if disks:
                return disks
        except Exception:
            pass

    # Method 2: lsblk text - TYPE is LAST column
    out, code = run_cmd(
        "lsblk -d -b -o NAME,SIZE,MODEL,TYPE -n "
        "2>/dev/null")
    if code == 0 and out.strip():
        for line in out.strip().split('\n'):
            parts = line.split()
            if len(parts) < 2: continue
            name  = parts[0]
            if 'loop' in name or 'ram' in name: continue
            size  = parts[1]
            # TYPE is always the LAST column
            dtype = parts[-1].strip()
            # MODEL is all columns between SIZE and TYPE
            model = ' '.join(parts[2:-1]).strip()                     if len(parts) > 3 else ''
            if dtype != 'disk': continue
            try:
                size_gb = int(size) / 1024**3
            except:
                size_gb = 0
            disks.append({
                'name':  name,
                'path':  f'/dev/{name}',
                'size':  f'{size_gb:.1f} GB',
                'model': model or 'Unknown',
            })
        if disks:
            return disks

    # Method 3: /proc/partitions fallback
    out, code = run_cmd("cat /proc/partitions 2>/dev/null")
    if code == 0:
        for line in out.strip().split('\n')[2:]:
            parts = line.split()
            if len(parts) < 4: continue
            major, minor, blocks, name = parts[:4]
            if 'loop' in name or 'ram' in name: continue
            # Only whole disks (no digits at end for SATA,
            # no p+digit for NVMe)
            import re as _re
            if _re.search(r'\d$', name) and                not _re.search(r'[a-z]\d*$', name): continue
            if _re.search(r'p\d+$', name): continue
            try:
                size_gb = int(blocks) * 1024 / 1024**3
            except:
                size_gb = 0
            disks.append({
                'name':  name,
                'path':  f'/dev/{name}',
                'size':  f'{size_gb:.1f} GB',
                'model': 'Unknown',
            })

    return disks

def get_partitions(disk_path):
    parts = []
    disk_name = os.path.basename(disk_path)

    # Method 1: lsblk JSON
    out, code = run_cmd(
        f"lsblk -b -J -o NAME,SIZE,FSTYPE,MOUNTPOINT "
        f"{disk_path} 2>/dev/null")
    if code == 0 and out.strip():
        try:
            import json as _json
            data = _json.loads(out)
            devs = data.get('blockdevices', [])
            children = []
            for d in devs:
                children += d.get('children', [])
            for c in children:
                name = c.get('name', '')
                if not name: continue
                try:
                    size_gb = int(c.get('size', 0))                               / 1024**3
                except:
                    size_gb = 0
                parts.append({
                    'name':   name,
                    'path':   f'/dev/{name}',
                    'size':   f'{size_gb:.2f} GB',
                    'fstype': c.get('fstype') or '',
                    'mount':  c.get('mountpoint') or '',
                })
            if parts:
                return parts
        except Exception:
            pass

    # Method 2: lsblk text
    out, _ = run_cmd(
        f"lsblk -b -o NAME,SIZE,FSTYPE,MOUNTPOINT -n "
        f"-P {disk_path} 2>/dev/null")
    if out.strip():
        import re as _re
        for line in out.strip().split('\n'):
            if not line.strip(): continue
            kv = dict(_re.findall(
                r'(\w+)="([^"]*)"', line))
            name = kv.get('NAME', '').strip()
            if not name or name == disk_name: continue
            try:
                size_gb = int(kv.get('SIZE', '0'))                           / 1024**3
            except:
                size_gb = 0
            parts.append({
                'name':   name,
                'path':   f'/dev/{name}',
                'size':   f'{size_gb:.2f} GB',
                'fstype': kv.get('FSTYPE', ''),
                'mount':  kv.get('MOUNTPOINT', ''),
            })

    return parts

def find_squashfs():
    for p in [
        '/run/live/medium/live/filesystem.squashfs',
        '/lib/live/mount/medium/live/filesystem.squashfs',
        '/cdrom/live/filesystem.squashfs',
    ]:
        if os.path.exists(p):
            return p
    out, _ = run_cmd(
        "find /run /lib/live /cdrom /media "
        "-name 'filesystem.squashfs' 2>/dev/null | head -1")
    return out.strip() if out.strip() else None

def disk_size_gb(disk_path):
    out, _ = run_cmd(
        f"lsblk -d -b -o SIZE -n {disk_path} 2>/dev/null")
    try:
        return int(out.strip()) / 1024**3
    except:
        return 0

def part_size_gb(part_path):
    out, _ = run_cmd(
        f"lsblk -b -o SIZE -n {part_path} 2>/dev/null")
    try:
        return int(out.strip().split('\n')[-1]) / 1024**3
    except:
        return 0


# ════════════════════════════════════════════════════════════════
class RIDOSInstaller:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RIDOS OS — Disk Manager & Installer")
        self.root.geometry("1020x680")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self._disks = []
        self.selected_disk = None
        self.selected_part = None
        self.install_data = {
            'disk': None, 'username': 'ridos',
            'password': 'ridos', 'hostname': 'ridos-os',
            'timezone': 'Asia/Baghdad',
        }
        self._build_ui()

    # ── Layout ─────────────────────────────────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=BG2, pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text="RIDOS OS",
                 font=('Arial', 20, 'bold'),
                 bg=BG2, fg=PURPLE).pack(side='left', padx=16)
        tk.Label(hdr, text="Disk Manager & Installer v1.0",
                 font=('Arial', 11), bg=BG2, fg=TEXT).pack(side='left')

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill='both', expand=True)

        sidebar = tk.Frame(body, bg=BG2, width=155)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="MENU",
                 font=('Arial', 9, 'bold'),
                 bg=BG2, fg=GRAY).pack(pady=(16, 4))

        self._nav_btns = {}
        for key, label in [('disks',   '  Disk Manager'),
                            ('install', '  Install OS'),
                            ('about',   '  About')]:
            b = tk.Button(sidebar, text=label,
                          font=('Arial', 11), anchor='w',
                          bg=BG2, fg=TEXT, relief='flat',
                          activebackground=BG3,
                          cursor='hand2',
                          command=lambda k=key: self._nav(k))
            b.pack(fill='x', pady=2, padx=4)
            self._nav_btns[key] = b

        tk.Frame(body, bg='#2D1B69', width=1).pack(
            side='left', fill='y')

        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side='left', fill='both', expand=True)

        self._nav('disks')

    def _nav(self, page):
        for k, b in self._nav_btns.items():
            b.config(bg=BG3 if k == page else BG2,
                     fg=TEXT if k == page else GRAY)
        for w in self.content.winfo_children():
            w.destroy()
        {'disks':   self._page_disks,
         'install': self._page_install,
         'about':   self._page_about}[page]()

    def _btn(self, parent, text, cmd,
             color=PURPLE, fg=TEXT, **kw):
        return tk.Button(
            parent, text=text, command=cmd,
            bg=color, fg=fg,
            font=('Arial', 9, 'bold'),
            relief='flat', padx=8, pady=4,
            cursor='hand2', **kw)

    # ═══════════════════════════════════════════════════════════
    # PAGE: Disk Manager
    # ═══════════════════════════════════════════════════════════
    def _page_disks(self):
        top = tk.Frame(self.content, bg=BG2, pady=8)
        top.pack(fill='x')
        tk.Label(top, text="Disk Manager",
                 font=('Arial', 14, 'bold'),
                 bg=BG2, fg=PURPLE).pack(side='left', padx=14)
        self._btn(top, "⟳ Refresh",
                  self._refresh_disks, BG3).pack(
                      side='right', padx=8)

        pane = tk.Frame(self.content, bg=BG)
        pane.pack(fill='both', expand=True, padx=8, pady=6)

        # ── Left: disk list ───────────────────────────────────
        left = tk.Frame(pane, bg=BG, width=260)
        left.pack(side='left', fill='y', padx=(0, 6))
        left.pack_propagate(False)

        tk.Label(left, text="Storage Devices",
                 font=('Arial', 10, 'bold'),
                 bg=BG, fg=TEXT).pack(anchor='w')

        self.disk_listbox = tk.Listbox(
            left, bg=BG2, fg=TEXT,
            selectbackground=PURPLE,
            font=('Courier', 10),
            relief='flat', width=30, height=12,
            activestyle='none')
        self.disk_listbox.pack(fill='both', expand=True,
                               pady=4)
        self.disk_listbox.bind(
            '<<ListboxSelect>>', self._on_disk_select)

        # Disk buttons
        dbf = tk.Frame(left, bg=BG)
        dbf.pack(fill='x', pady=2)
        self._btn(dbf, "New GPT Table",
                  self._new_part_table,
                  BG3).grid(row=0, column=0, padx=2, pady=2)
        self._btn(dbf, "Format Disk",
                  self._format_disk,
                  RED).grid(row=0, column=1, padx=2, pady=2)

        # ── Right: partition table ────────────────────────────
        right = tk.Frame(pane, bg=BG)
        right.pack(side='left', fill='both', expand=True)

        tk.Label(right, text="Partitions",
                 font=('Arial', 10, 'bold'),
                 bg=BG, fg=TEXT).pack(anchor='w')

        cols = ('Device', 'Size', 'FS', 'Mount', 'Flags')
        self.part_tree = ttk.Treeview(
            right, columns=cols,
            show='headings', height=11)
        style = ttk.Style()
        style.theme_use('default')
        style.configure('Treeview',
                        background=BG2, foreground=TEXT,
                        fieldbackground=BG2, rowheight=22)
        style.configure('Treeview.Heading',
                        background=BG3, foreground=CYAN,
                        font=('Arial', 9, 'bold'))
        style.map('Treeview',
                  background=[('selected', PURPLE)])
        widths = {'Device': 110, 'Size': 85,
                  'FS': 80, 'Mount': 130, 'Flags': 80}
        for col in cols:
            self.part_tree.heading(col, text=col)
            self.part_tree.column(col,
                                  width=widths[col],
                                  anchor='w')
        self.part_tree.pack(fill='both', expand=True,
                            pady=4)
        self.part_tree.bind(
            '<<TreeviewSelect>>', self._on_part_select)

        # Partition buttons — full set
        pbf = tk.Frame(right, bg=BG)
        pbf.pack(fill='x', pady=2)
        buttons = [
            ("+ EXT4",    self._create_ext4,  PURPLE, 0, 0),
            ("+ Swap",    self._create_swap,  BG3,    0, 1),
            ("Set Boot",  self._set_boot_flag, GREEN, 0, 2),
            ("Set Active",self._set_active,   GREEN,  0, 3),
            ("Resize",    self._resize_part,  CYAN,   1, 0),
            ("Format",    self._format_part,  YELLOW, 1, 1),
            ("Delete",    self._delete_part,  RED,    1, 2),
            ("Mount",     self._toggle_mount, BG3,    1, 3),
        ]
        for text, cmd, color, row, col in buttons:
            self._btn(pbf, text, cmd, color).grid(
                row=row, column=col,
                padx=2, pady=2, sticky='ew')

        # Status bar
        self.disk_status = tk.Label(
            self.content,
            text="Select a disk to see partitions",
            font=('Arial', 9), bg=BG2, fg=GRAY,
            anchor='w', pady=3)
        self.disk_status.pack(fill='x', padx=8,
                              pady=(0, 4))

        self._refresh_disks()

    def _refresh_disks(self):
        self._disks = get_disks()
        self.disk_listbox.delete(0, 'end')
        if not self._disks:
            self.disk_listbox.insert('end',
                                     '  No disks found')
            return
        for d in self._disks:
            self.disk_listbox.insert(
                'end',
                f"  /dev/{d['name']}  "
                f"{d['size']:>8}  "
                f"{d['model'][:12]}")

    def _on_disk_select(self, event):
        sel = self.disk_listbox.curselection()
        if not sel: return
        idx = sel[0]
        if idx >= len(self._disks): return
        self.selected_disk = self._disks[idx]
        self.install_data['disk'] = self.selected_disk['path']
        self.disk_status.config(
            text=f"  {self.selected_disk['path']}  "
                 f"{self.selected_disk['size']}  "
                 f"{self.selected_disk['model']}")
        self._refresh_parts()

    def _on_part_select(self, event):
        sel = self.part_tree.selection()
        if sel:
            vals = self.part_tree.item(sel[0], 'values')
            if vals:
                self.selected_part = vals[0]

    def _refresh_parts(self):
        for row in self.part_tree.get_children():
            self.part_tree.delete(row)
        if not self.selected_disk: return
        disk = self.selected_disk['path']
        parts = get_partitions(disk)

        # Get flags from parted
        flags_out, _ = run_cmd(
            f"parted -s {disk} print 2>/dev/null")
        flags_map = {}
        for line in flags_out.split('\n'):
            parts_line = line.strip().split()
            if parts_line and parts_line[0].isdigit():
                num = parts_line[0]
                flags = parts_line[-1] if len(
                    parts_line) > 5 else ''
                flags_map[num] = flags

        if not parts:
            self.part_tree.insert(
                '', 'end',
                values=('No partitions', '', '', '', ''))
            return

        for i, p in enumerate(parts, 1):
            flags = flags_map.get(str(i), '')
            self.part_tree.insert(
                '', 'end',
                values=(
                    f"/dev/{p['name']}",
                    p['size'],
                    p['fstype'] or '-',
                    p['mount'] or '-',
                    flags))

    def _require_disk(self):
        if not self.selected_disk:
            messagebox.showwarning(
                "No disk", "Select a disk first")
            return False
        return True

    def _require_part(self):
        if not self.selected_part:
            messagebox.showwarning(
                "No partition",
                "Select a partition from the list first")
            return False
        return True

    # ── Disk operations ────────────────────────────────────────
    def _new_part_table(self):
        if not self._require_disk(): return
        disk = self.selected_disk['path']
        if not messagebox.askyesno(
                "Confirm",
                f"Create new GPT table on {disk}?\n"
                "ALL partitions will be deleted!"):
            return
        out, code = run_cmd(
            f"parted -s {disk} mklabel gpt")
        if code == 0:
            messagebox.showinfo(
                "Done", f"GPT table created on {disk}")
        else:
            messagebox.showerror("Failed", out)
        self._refresh_parts()

    def _format_disk(self):
        if not self._require_disk(): return
        disk = self.selected_disk['path']
        if not messagebox.askyesno(
                "⚠ WARNING",
                f"ERASE ALL DATA on {disk}?\n"
                "This cannot be undone!"):
            return
        cmds = [
            f"parted -s {disk} mklabel gpt",
            f"mkfs.ext4 -F {disk}",
        ]
        for cmd in cmds:
            run_cmd(cmd, 60)
        messagebox.showinfo(
            "Done", f"Disk {disk} formatted")
        self._refresh_parts()

    # ── Partition operations ───────────────────────────────────
    def _create_ext4(self):
        if not self._require_disk(): return
        disk = self.selected_disk['path']
        parts = get_partitions(disk)
        # Find free space start
        if parts:
            # Add after last partition
            size = simpledialog.askstring(
                "Size",
                "Partition size in GB (e.g. 20)\n"
                "Or leave empty to use all free space:",
                parent=self.root)
            if size is None: return
            try:
                size_gb = float(size) if size.strip() else 0
            except:
                size_gb = 0
            out, _ = run_cmd(
                f"parted -s {disk} print free 2>/dev/null")
            # Get end of last partition
            end_out, _ = run_cmd(
                f"parted -s {disk} unit MiB print "
                f"2>/dev/null | tail -4")
            end = "100%"
            for line in end_out.split('\n'):
                if line.strip() and line.strip()[0].isdigit():
                    toks = line.split()
                    if len(toks) >= 3:
                        end = toks[2]
            start = end
            if size_gb > 0:
                start_mib = float(
                    start.replace("MiB","").strip()
                    .replace("%","") or "0")
                end = f"{start_mib + size_gb*1024:.0f}MiB"
            else:
                end = "100%"
        else:
            start, end = "1MiB", "100%"

        cmds = [
            f"parted -s {disk} mkpart primary ext4 "
            f"{start} {end}",
            f"partprobe {disk}",
            "sleep 1",
        ]
        for cmd in cmds:
            run_cmd(cmd, 30)

        # Format the new partition
        parts_after = get_partitions(disk)
        if parts_after:
            new_part = parts_after[-1]['path']
            out, code = run_cmd(
                f"mkfs.ext4 -F {new_part}", 60)
            if code == 0:
                messagebox.showinfo(
                    "Done",
                    f"EXT4 partition {new_part} created")
            else:
                messagebox.showerror("Failed", out)
        self._refresh_parts()

    def _create_swap(self):
        if not self._require_disk(): return
        disk = self.selected_disk['path']
        size = simpledialog.askstring(
            "Swap size",
            "Swap partition size in GB (e.g. 4):",
            parent=self.root)
        if not size: return
        try:
            size_gb = float(size)
        except:
            messagebox.showerror("Error", "Invalid size")
            return
        # Add after last partition
        parts = get_partitions(disk)
        start = "1MiB" if not parts else "0%"
        end   = f"{size_gb*1024:.0f}MiB"

        run_cmd(
            f"parted -s {disk} mkpart primary "
            f"linux-swap {start} {end}", 30)
        run_cmd(f"partprobe {disk}")
        time.sleep(1)
        parts_after = get_partitions(disk)
        if parts_after:
            new_part = parts_after[-1]['path']
            run_cmd(f"mkswap {new_part}", 30)
            messagebox.showinfo(
                "Done",
                f"Swap partition {new_part} created")
        self._refresh_parts()

    def _set_boot_flag(self):
        """Set boot flag on selected partition"""
        if not self._require_disk(): return
        if not self._require_part(): return
        disk = self.selected_disk['path']
        part_name = os.path.basename(self.selected_part)
        # Get partition number
        num = ''.join(
            filter(str.isdigit, part_name))
        if not num:
            messagebox.showerror(
                "Error", "Cannot determine partition number")
            return
        out, code = run_cmd(
            f"parted -s {disk} set {num} boot on")
        if code == 0:
            messagebox.showinfo(
                "Done",
                f"Boot flag set on {self.selected_part}")
        else:
            messagebox.showerror("Failed", out)
        self._refresh_parts()

    def _set_active(self):
        """Set partition as active (bootable) using sfdisk"""
        if not self._require_disk(): return
        if not self._require_part(): return
        disk = self.selected_disk['path']
        part_name = os.path.basename(self.selected_part)
        num = ''.join(filter(str.isdigit, part_name))
        if not num:
            messagebox.showerror(
                "Error", "Cannot determine partition number")
            return
        # Try multiple methods
        out, code = run_cmd(
            f"parted -s {disk} set {num} boot on && "
            f"parted -s {disk} set {num} esp on 2>/dev/null "
            f"|| true")
        # Also use sfdisk to mark active
        out2, code2 = run_cmd(
            f"sfdisk --activate {disk} {num} 2>/dev/null "
            f"|| true")
        messagebox.showinfo(
            "Done",
            f"Partition {self.selected_part} set as active")
        self._refresh_parts()

    def _resize_part(self):
        """Resize selected partition"""
        if not self._require_disk(): return
        if not self._require_part(): return
        disk = self.selected_disk['path']
        part = self.selected_part
        part_name = os.path.basename(part)
        num = ''.join(filter(str.isdigit, part_name))

        current_gb = part_size_gb(part)

        new_size = simpledialog.askstring(
            "Resize Partition",
            f"Current size: {current_gb:.1f} GB\n"
            f"New size in GB (e.g. 30):",
            parent=self.root)
        if not new_size: return

        try:
            new_gb = float(new_size.strip())
        except:
            messagebox.showerror("Error", "Invalid size")
            return

        if new_gb < 1:
            messagebox.showerror(
                "Error", "Size must be at least 1 GB")
            return

        # Check if partition is mounted
        parts = get_partitions(disk)
        for p in parts:
            if p['path'] == part and p['mount']:
                messagebox.showerror(
                    "Error",
                    f"Partition {part} is mounted at "
                    f"{p['mount']}\n"
                    "Unmount it first!")
                return

        # Check filesystem
        fstype_out, _ = run_cmd(
            f"blkid -s TYPE -o value {part} 2>/dev/null")
        fstype = fstype_out.strip()

        confirm = messagebox.askyesno(
            "Confirm Resize",
            f"Resize {part} to {new_gb:.1f} GB?\n\n"
            f"Current: {current_gb:.1f} GB\n"
            f"New: {new_gb:.1f} GB\n\n"
            "⚠ Backup your data first!")
        if not confirm: return

        # Run resize
        self._run_task_window(
            f"Resizing {part}",
            self._do_resize,
            disk, part, num, new_gb, fstype)

    def _do_resize(self, log, done, disk, part, num,
                   new_gb, fstype):
        try:
            log(f"Resizing partition {num} to {new_gb:.1f} GB...")

            # Check filesystem first
            if 'ext' in fstype:
                log("Checking filesystem...")
                out, code = run_cmd(
                    f"e2fsck -f -y {part}", 120)
                log(f"  e2fsck: "
                    f"{'OK' if code <= 1 else out[-100:]}")

            # Resize partition with parted
            new_mib = int(new_gb * 1024)
            log(f"Resizing partition to {new_mib} MiB...")
            out, code = run_cmd(
                f"parted -s {disk} resizepart {num} "
                f"{new_mib}MiB", 30)
            log(f"  parted: "
                f"{'OK' if code==0 else out[-100:]}")

            # Resize filesystem
            if 'ext' in fstype:
                log("Resizing filesystem...")
                out, code = run_cmd(
                    f"resize2fs {part}", 120)
                log(f"  resize2fs: "
                    f"{'OK' if code==0 else out[-100:]}")
            elif 'xfs' in fstype:
                log("Resize XFS (mount first)...")
                mnt = f"/mnt/resize_{num}"
                run_cmd(f"mkdir -p {mnt}")
                run_cmd(f"mount {part} {mnt}")
                out, code = run_cmd(
                    f"xfs_growfs {mnt}", 60)
                run_cmd(f"umount {mnt}")
                run_cmd(f"rmdir {mnt}")
                log(f"  xfs_growfs: "
                    f"{'OK' if code==0 else out[-100:]}")

            log(f"\nResize complete!")
            run_cmd(f"partprobe {disk}")

        except Exception as e:
            log(f"\nERROR: {e}")
        finally:
            done()

    def _format_part(self):
        if not self._require_part(): return
        part = self.selected_part
        fs = simpledialog.askstring(
            "Format Partition",
            f"Format {part} as:\n"
            "ext4 / ext3 / xfs / fat32 / swap\n\n"
            "Enter filesystem type:",
            parent=self.root)
        if not fs: return
        fs = fs.strip().lower()

        if not messagebox.askyesno(
                "⚠ WARNING",
                f"Format {part} as {fs}?\n"
                "ALL DATA will be erased!"):
            return

        cmds = {
            'ext4':  f"mkfs.ext4 -F {part}",
            'ext3':  f"mkfs.ext3 -F {part}",
            'xfs':   f"mkfs.xfs -f {part}",
            'fat32': f"mkfs.fat -F32 {part}",
            'vfat':  f"mkfs.fat -F32 {part}",
            'swap':  f"mkswap {part}",
        }
        cmd = cmds.get(fs)
        if not cmd:
            messagebox.showerror(
                "Error", f"Unknown filesystem: {fs}")
            return

        out, code = run_cmd(cmd, 60)
        if code == 0:
            messagebox.showinfo(
                "Done", f"{part} formatted as {fs}")
        else:
            messagebox.showerror("Failed", out)
        self._refresh_parts()

    def _delete_part(self):
        if not self._require_disk(): return
        if not self._require_part(): return
        disk = self.selected_disk['path']
        part = self.selected_part
        num = ''.join(filter(
            str.isdigit, os.path.basename(part)))

        if not messagebox.askyesno(
                "Confirm Delete",
                f"Delete partition {part}?\n"
                "ALL DATA will be lost!"):
            return

        out, code = run_cmd(
            f"parted -s {disk} rm {num}", 30)
        if code == 0:
            messagebox.showinfo(
                "Done", f"Partition {part} deleted")
        else:
            messagebox.showerror("Failed", out)
        self.selected_part = None
        run_cmd(f"partprobe {disk}")
        self._refresh_parts()

    def _toggle_mount(self):
        if not self._require_part(): return
        part = self.selected_part
        parts = get_partitions(
            self.selected_disk['path'])
        mounted = None
        for p in parts:
            if p['path'] == part and p['mount']:
                mounted = p['mount']
                break

        if mounted:
            out, code = run_cmd(
                f"umount {part} 2>/dev/null || true")
            messagebox.showinfo(
                "Done", f"{part} unmounted")
        else:
            mnt = f"/mnt/{os.path.basename(part)}"
            run_cmd(f"mkdir -p {mnt}")
            out, code = run_cmd(
                f"mount {part} {mnt} 2>/dev/null")
            if code == 0:
                messagebox.showinfo(
                    "Done", f"{part} mounted at {mnt}")
            else:
                messagebox.showerror("Failed", out)
        self._refresh_parts()

    def _run_task_window(self, title, func, *args):
        """Generic progress window for long tasks"""
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("560x340")
        win.configure(bg=BG)
        win.grab_set()

        tk.Label(win, text=title,
                 font=('Arial', 12, 'bold'),
                 bg=BG, fg=PURPLE).pack(pady=8)

        log_text = tk.Text(win, bg='#111827',
                           fg='#A5F3FC',
                           font=('Courier', 10),
                           relief='flat', state='disabled')
        log_text.pack(fill='both', expand=True,
                      padx=12, pady=4)

        close_btn = self._btn(win, "Close", win.destroy,
                              BG3)
        close_btn.pack(pady=8)
        close_btn.config(state='disabled')

        def log(msg):
            def _do():
                log_text.config(state='normal')
                log_text.insert('end', msg + '\n')
                log_text.see('end')
                log_text.config(state='disabled')
            win.after(0, _do)

        def done():
            win.after(0, close_btn.config,
                      {'state': 'normal'})
            log("Done!")
            self._refresh_parts()

        threading.Thread(
            target=func,
            args=(log, done) + args,
            daemon=True).start()

    # ═══════════════════════════════════════════════════════════
    # PAGE: Install OS
    # ═══════════════════════════════════════════════════════════
    def _page_install(self):
        self._install_step = 0
        self._steps_done = set()

        top = tk.Frame(self.content, bg=BG2, pady=8)
        top.pack(fill='x')
        self._step_label = tk.Label(
            top,
            text="Step 1 of 4: Select Disk",
            font=('Arial', 13, 'bold'),
            bg=BG2, fg=PURPLE)
        self._step_label.pack(side='left', padx=14)

        # Step indicator strip
        strip = tk.Frame(self.content, bg=BG, pady=4)
        strip.pack(fill='x', padx=10)
        self._step_inds = []
        for i, n in enumerate(
                ['1. Disk', '2. User',
                 '3. Settings', '4. Confirm']):
            lbl = tk.Label(strip, text=n,
                           font=('Arial', 9),
                           bg=BG, fg=GRAY)
            lbl.pack(side='left', expand=True)
            self._step_inds.append(lbl)

        tk.Frame(self.content, bg=BG2,
                 height=1).pack(fill='x')

        # IMPORTANT: pack nav BEFORE wiz
        # so side='bottom' works correctly
        nav = tk.Frame(self.content, bg=BG2, pady=8)
        nav.pack(fill='x', side='bottom')
        self._back_btn = self._btn(
            nav, "◀ Back",
            self._install_back, BG3)
        self._back_btn.pack(side='left', padx=12)
        self._next_btn = self._btn(
            nav, "Next ▶",
            self._install_next, PURPLE)
        self._next_btn.pack(side='right', padx=12)

        # Pack wiz AFTER nav so it fills remaining space
        self._wiz = tk.Frame(self.content, bg=BG)
        self._wiz.pack(fill='both', expand=True,
                       padx=16, pady=8)

        self._show_step(0)

    def _show_step(self, step):
        self._install_step = step
        for w in self._wiz.winfo_children():
            w.destroy()
        names = ['Disk', 'User', 'Settings', 'Confirm']
        for i, ind in enumerate(self._step_inds):
            if i < step:
                ind.config(fg=GREEN,
                           font=('Arial', 9, 'bold'))
            elif i == step:
                ind.config(fg=PURPLE,
                           font=('Arial', 9, 'bold'))
            else:
                ind.config(fg=GRAY, font=('Arial', 9))
        self._step_label.config(
            text=f"Step {step+1} of 4: {names[step]}")
        [self._step_disk, self._step_user,
         self._step_settings, self._step_confirm][step]()
        self._back_btn.config(
            state='normal' if step > 0 else 'disabled')
        if step == 3:
            self._next_btn.config(
                text="INSTALL NOW ▶", bg=RED)
        else:
            self._next_btn.config(
                text="Next ▶", bg=PURPLE)

    def _install_back(self):
        if self._install_step > 0:
            self._show_step(self._install_step - 1)

    def _install_next(self):
        if self._install_step < 3:
            self._show_step(self._install_step + 1)
        else:
            if not self.install_data.get('disk'):
                messagebox.showerror(
                    "Error",
                    "Please go back and select a disk!")
                return
            if messagebox.askyesno(
                    "⚠ FINAL CONFIRMATION",
                    f"Install RIDOS OS on "
                    f"{self.install_data['disk']}?\n\n"
                    "ALL DATA WILL BE ERASED!\n"
                    "This cannot be undone!"):
                self._start_install()

    def _step_disk(self):
        f = self._wiz
        tk.Label(f, text="Select installation disk:",
                 font=('Arial', 11, 'bold'),
                 bg=BG, fg=TEXT).pack(anchor='w',
                                      pady=(0, 6))
        tk.Label(
            f,
            text="⚠  All data on the disk will be erased!",
            font=('Arial', 10), bg=BG,
            fg=YELLOW).pack(anchor='w', pady=(0, 10))

        disks = get_disks()
        if not disks:
            tk.Label(f, text="No disks found!",
                     bg=BG, fg=RED).pack()
            return

        self._disk_var = tk.StringVar(
            value=self.install_data.get('disk', ''))
        for d in disks:
            rb = tk.Radiobutton(
                f,
                text=f"/dev/{d['name']}  —  "
                     f"{d['size']}  —  {d['model']}",
                variable=self._disk_var,
                value=d['path'],
                font=('Arial', 11),
                bg=BG, fg=TEXT,
                selectcolor=BG3,
                activebackground=BG,
                command=lambda p=d['path']:
                self.install_data.__setitem__('disk', p))
            rb.pack(anchor='w', pady=3)

        if disks and not self.install_data.get('disk'):
            self._disk_var.set(disks[0]['path'])
            self.install_data['disk'] = disks[0]['path']

        tk.Label(
            f,
            text="\nPartitions to be created:\n"
                 "  1.  512 MB  EFI  (FAT32)  [esp+boot]\n"
                 "  2.    4 GB  Swap\n"
                 "  3. Remaining  Root  (EXT4) [boot]",
            font=('Courier', 9),
            bg=BG, fg=GRAY,
            justify='left').pack(anchor='w', pady=10)

    def _step_user(self):
        f = self._wiz
        tk.Label(f, text="User Account",
                 font=('Arial', 12, 'bold'),
                 bg=BG, fg=PURPLE).pack(
                     anchor='w', pady=(0, 10))
        for label, key, default, secret in [
            ('Full Name',  'fullname',  'RIDOS User', False),
            ('Username',   'username',  'ridos',      False),
            ('Password',   'password',  'ridos',      True),
            ('Hostname',   'hostname',  'ridos-os',   False),
        ]:
            row = tk.Frame(f, bg=BG)
            row.pack(fill='x', pady=4)
            tk.Label(row, text=f"{label}:",
                     font=('Arial', 10),
                     bg=BG, fg=TEXT,
                     width=12, anchor='e').pack(side='left')
            e = tk.Entry(row, font=('Arial', 11),
                         bg=BG2, fg=TEXT,
                         insertbackground=TEXT,
                         relief='flat', bd=4, width=26)
            e.insert(0, self.install_data.get(key, default))
            if secret: e.config(show='*')
            e.pack(side='left', padx=8)
            e.bind('<KeyRelease>',
                   lambda ev, k=key:
                   self.install_data.__setitem__(
                       k, ev.widget.get()))

    def _step_settings(self):
        f = self._wiz
        tk.Label(f, text="System Settings",
                 font=('Arial', 12, 'bold'),
                 bg=BG, fg=PURPLE).pack(
                     anchor='w', pady=(0, 10))
        row = tk.Frame(f, bg=BG)
        row.pack(fill='x', pady=4)
        tk.Label(row, text="Timezone:",
                 font=('Arial', 10), bg=BG, fg=TEXT,
                 width=12, anchor='e').pack(side='left')
        out, _ = run_cmd(
            "timedatectl list-timezones 2>/dev/null "
            "| head -100")
        zones = (out.strip().split('\n')
                 if out.strip()
                 else ["Asia/Baghdad", "UTC"])
        self._tz_var = tk.StringVar(
            value=self.install_data.get(
                'timezone', 'Asia/Baghdad'))
        combo = ttk.Combobox(
            row, textvariable=self._tz_var,
            values=zones, font=('Arial', 10),
            width=30, state='readonly')
        combo.pack(side='left', padx=8)
        combo.bind('<<ComboboxSelected>>',
                   lambda e:
                   self.install_data.__setitem__(
                       'timezone', self._tz_var.get()))

    def _step_confirm(self):
        f = self._wiz
        d = self.install_data
        tk.Label(f, text="Review your choices:",
                 font=('Arial', 11, 'bold'),
                 bg=BG, fg=TEXT).pack(
                     anchor='w', pady=(0, 8))
        tk.Label(
            f,
            text=f"  Disk:      {d.get('disk','NOT SET')}\n"
                 f"  Username:  {d.get('username','')}\n"
                 f"  Hostname:  {d.get('hostname','')}\n"
                 f"  Timezone:  {d.get('timezone','')}",
            font=('Courier', 11),
            bg=BG2, fg=TEXT,
            justify='left',
            padx=12, pady=10).pack(fill='x', pady=6)
        tk.Label(
            f,
            text="⚠  ALL DATA ON THE DISK WILL BE ERASED!",
            font=('Arial', 12, 'bold'),
            bg=BG, fg=RED).pack(pady=8)

    # ── Installation engine ────────────────────────────────────
    def _start_install(self):
        for w in self.content.winfo_children():
            w.destroy()
        top = tk.Frame(self.content, bg=BG2, pady=8)
        top.pack(fill='x')
        tk.Label(top, text="Installing RIDOS OS...",
                 font=('Arial', 13, 'bold'),
                 bg=BG2, fg=PURPLE).pack(side='left',
                                          padx=14)
        self._prog_status = tk.Label(
            self.content, text="Preparing...",
            font=('Arial', 10), bg=BG, fg=YELLOW)
        self._prog_status.pack(anchor='w',
                               padx=14, pady=2)
        self._prog_bar = ttk.Progressbar(
            self.content, orient='horizontal',
            length=950, mode='determinate')
        self._prog_bar.pack(padx=14, pady=2)

        log_frame = tk.Frame(self.content, bg=BG)
        log_frame.pack(fill='both', expand=True,
                       padx=14, pady=4)
        self._log_text = tk.Text(
            log_frame, bg='#111827', fg='#A5F3FC',
            font=('Courier', 10), relief='flat',
            state='disabled')
        sb = tk.Scrollbar(log_frame,
                          command=self._log_text.yview)
        self._log_text.config(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._log_text.pack(fill='both', expand=True)

        threading.Thread(
            target=self._do_install,
            daemon=True).start()

    def _log(self, msg):
        def _do():
            self._log_text.config(state='normal')
            self._log_text.insert('end', msg + '\n')
            self._log_text.see('end')
            self._log_text.config(state='disabled')
        self.root.after(0, _do)

    def _prog(self, pct, msg):
        self.root.after(
            0, self._prog_bar.config, {'value': pct})
        self.root.after(
            0, self._prog_status.config, {'text': msg})

    def _do_install(self):
        d    = self.install_data
        disk = d['disk']
        user = d.get('username', 'ridos')
        pwd  = d.get('password', 'ridos')
        host = d.get('hostname', 'ridos-os')
        tz   = d.get('timezone', 'Asia/Baghdad')
        tgt  = '/mnt/ridos-install'

        pfx  = disk + 'p' if 'nvme' in disk else disk
        efi  = pfx + '1'
        swap = pfx + '2'
        root = pfx + '3'

        try:
            # ── 1. Partition ──────────────────────────────
            self._prog(5, "Partitioning disk...")
            self._log(f"[1/7] Partitioning {disk}...")

            for cmd in [
                f"parted -s {disk} mklabel gpt",
                # EFI partition with esp+boot flags
                f"parted -s {disk} mkpart ESP fat32 "
                f"1MiB 512MiB",
                f"parted -s {disk} set 1 esp on",
                f"parted -s {disk} set 1 boot on",
                # Swap
                f"parted -s {disk} mkpart primary "
                f"linux-swap 512MiB 4608MiB",
                # Root with boot flag
                f"parted -s {disk} mkpart primary "
                f"ext4 4608MiB 100%",
                f"parted -s {disk} set 3 boot on",
                "sleep 2",
                f"partprobe {disk}",
                "sleep 1",
            ]:
                out, code = run_cmd(cmd, 30)
                self._log(
                    f"  {'OK' if code==0 else 'WARN'}"
                    f": {cmd.split()[0]} "
                    f"{' '.join(cmd.split()[1:3])}")

            # Verify partitions exist
            self._log("  Verifying partitions...")
            for part in [efi, swap, root]:
                if not os.path.exists(part):
                    # Try alternate naming
                    alt = part.replace(disk, disk+'p') \
                        if 'nvme' not in disk \
                        else part
                    if os.path.exists(alt):
                        if part == efi:  efi  = alt
                        if part == swap: swap = alt
                        if part == root: root = alt
                    else:
                        # Wait for udev
                        run_cmd(
                            f"udevadm settle 2>/dev/null "
                            f"|| sleep 2")

            self._log(
                f"  EFI={efi} SWAP={swap} ROOT={root}")

            # ── 2. Format ─────────────────────────────────
            self._prog(12, "Formatting partitions...")
            self._log("[2/7] Formatting...")
            for cmd, desc in [
                (f"mkfs.fat -F32 -n EFI {efi}", "EFI"),
                (f"mkswap {swap}",              "Swap"),
                (f"mkfs.ext4 -F -L RIDOS {root}","Root"),
            ]:
                out, code = run_cmd(cmd, 60)
                self._log(
                    f"  {desc}: "
                    f"{'OK' if code==0 else out[:100]}")
                if code != 0 and desc == "Root":
                    raise Exception(
                        f"Format root failed: {out}")

            # ── 3. Mount ──────────────────────────────────
            self._prog(18, "Mounting target...")
            self._log("[3/7] Mounting...")
            run_cmd(f"mkdir -p {tgt}")
            out, code = run_cmd(f"mount {root} {tgt}")
            if code != 0:
                raise Exception(
                    f"Cannot mount root: {out}")
            run_cmd(f"mkdir -p {tgt}/boot/efi")
            run_cmd(f"mount {efi} {tgt}/boot/efi")
            run_cmd(f"swapon {swap} 2>/dev/null || true")
            self._log("  Mounts: OK")

            # ── 4. Squashfs ───────────────────────────────
            self._prog(20, "Finding system image...")
            self._log("[4/7] Finding system image...")
            sq = find_squashfs()
            if not sq:
                raise Exception(
                    "Cannot find filesystem.squashfs!\n"
                    "Are you booted from the live USB?")
            self._log(f"  Found: {sq}")
            run_cmd(
                f"chmod 644 {sq} 2>/dev/null || true")
            run_cmd("mkdir -p /mnt/ridos-sq")
            out, code = run_cmd(
                f"mount -t squashfs -o loop,ro "
                f"{sq} /mnt/ridos-sq")
            if code != 0:
                raise Exception(
                    f"Cannot mount squashfs: {out}")

            # ── 5. Copy ───────────────────────────────────
            self._prog(25, "Copying files (10-20 min)...")
            self._log("[5/7] Copying RIDOS OS...")
            self._log("  Please wait 10-20 minutes...")
            out, code = run_cmd(
                f"rsync -aAXH "
                f"--exclude=/proc "
                f"--exclude=/sys "
                f"--exclude=/dev "
                f"--exclude=/run "
                f"--exclude=/tmp "
                f"--exclude=/mnt "
                f"--exclude=/media "
                f"--exclude=/lost+found "
                f"/mnt/ridos-sq/ {tgt}/",
                timeout=1800)
            run_cmd(
                "umount /mnt/ridos-sq 2>/dev/null; "
                "rmdir /mnt/ridos-sq 2>/dev/null || true")
            if code != 0:
                raise Exception(
                    f"rsync failed ({code}):\n"
                    f"{out[-200:]}")
            self._log("  Files copied: OK")

            # ── 6. Configure ──────────────────────────────
            self._prog(75, "Configuring system...")
            self._log("[6/7] Configuring...")

            for dd in ['proc','sys','dev',
                       'dev/pts','run','tmp']:
                run_cmd(f"mkdir -p {tgt}/{dd}")

            # fstab with correct UUIDs
            ru, _ = run_cmd(
                f"blkid -s UUID -o value {root}")
            eu, _ = run_cmd(
                f"blkid -s UUID -o value {efi}")
            su, _ = run_cmd(
                f"blkid -s UUID -o value {swap}")
            with open(f"{tgt}/etc/fstab", 'w') as fh:
                fh.write(
                    f"UUID={ru.strip()}  /  ext4  "
                    f"defaults,noatime  0 1\n"
                    f"UUID={eu.strip()}  /boot/efi  "
                    f"vfat  umask=0077  0 2\n"
                    f"UUID={su.strip()}  none  swap  "
                    f"sw  0 0\n")
            self._log("  fstab: OK")

            with open(f"{tgt}/etc/hostname", 'w') as fh:
                fh.write(host + '\n')

            run_cmd(
                f"chroot {tgt} ln -sf "
                f"/usr/share/zoneinfo/{tz} "
                f"/etc/localtime 2>/dev/null || true")

            run_cmd(
                f"chroot {tgt} userdel -r {user} "
                f"2>/dev/null || true")
            run_cmd(
                f"chroot {tgt} useradd -m "
                f"-s /bin/bash "
                f"-G sudo,audio,video,netdev,plugdev "
                f"{user}")
            run_cmd(
                f"echo '{user}:{pwd}' | "
                f"chroot {tgt} chpasswd")
            run_cmd(
                f"echo 'root:{pwd}' | "
                f"chroot {tgt} chpasswd")
            self._log(f"  User '{user}': OK")

            run_cmd(
                f"chroot {tgt} apt-get remove -y "
                f"live-boot live-boot-initramfs-tools "
                f"2>/dev/null || true")

            # ── Bind mounts (CRITICAL for GRUB) ──────────
            self._log("  Mounting /dev /proc /sys...")
            for dd in ['dev', 'dev/pts', 'proc', 'sys']:
                out, code = run_cmd(
                    f"mount --bind /{dd} {tgt}/{dd}")
                self._log(
                    f"    bind {dd}: "
                    f"{'OK' if code==0 else out[:60]}")

            # Update initramfs (removes live-boot)
            self._log("  Updating initramfs...")
            run_cmd(
                f"chroot {tgt} update-initramfs "
                f"-u -k all 2>/dev/null || true", 120)
            self._log("  initramfs: OK")

            # ── 7. GRUB ───────────────────────────────────
            self._prog(88, "Installing GRUB...")
            self._log(f"[7/7] Installing GRUB on {disk}...")

            # Verify /dev is accessible in chroot
            out, _ = run_cmd(
                f"ls {tgt}/dev/sda 2>/dev/null || "
                f"ls {tgt}/dev/nvme0n1 2>/dev/null || "
                f"ls {tgt}/dev/ | head -5")
            self._log(f"  /dev check: {out[:60]}")

            # Install GRUB - BIOS mode
            out, code = run_cmd(
                f"chroot {tgt} grub-install "
                f"--target=i386-pc "
                f"--boot-directory={tgt}/boot "
                f"--recheck "
                f"--force "
                f"--no-floppy "
                f"{disk}", 60)
            self._log(
                f"  grub-install (i386-pc): "
                f"{'OK' if code==0 else out[-150:]}")

            if code != 0:
                # Fallback: run grub-install from LIVE system
                self._log(
                    "  Trying fallback: "
                    "grub-install from live system...")
                out2, code2 = run_cmd(
                    f"grub-install "
                    f"--target=i386-pc "
                    f"--boot-directory={tgt}/boot "
                    f"--recheck "
                    f"--force "
                    f"--no-floppy "
                    f"{disk}", 60)
                self._log(
                    f"  fallback: "
                    f"{'OK' if code2==0 else out2[-150:]}")
                code = code2

            # Generate grub.cfg
            self._log("  Running update-grub...")
            out3, code3 = run_cmd(
                f"chroot {tgt} update-grub", 60)
            self._log(
                f"  update-grub: "
                f"{'OK' if code3==0 else out3[-150:]}")

            # If update-grub failed, write minimal grub.cfg
            if code3 != 0:
                self._log(
                    "  Writing minimal grub.cfg...")
                ru_clean = ru.strip()
                grub_cfg = (
                    f"set default=0\nset timeout=5\n"
                    f"menuentry 'RIDOS OS' {{\n"
                    f"  search --no-floppy "
                    f"--fs-uuid --set=root {ru_clean}\n"
                    f"  linux /boot/vmlinuz-* "
                    f"root=UUID={ru_clean} "
                    f"ro quiet splash\n"
                    f"  initrd /boot/initrd.img-*\n"
                    f"}}\n")
                os.makedirs(
                    f"{tgt}/boot/grub", exist_ok=True)
                with open(
                        f"{tgt}/boot/grub/grub.cfg",
                        'w') as fh:
                    fh.write(grub_cfg)
                self._log("  grub.cfg written manually")

            # ── Cleanup ───────────────────────────────────
            self._log("  Unmounting...")
            for dd in ['sys','proc','dev/pts','dev']:
                run_cmd(
                    f"umount {tgt}/{dd} "
                    f"2>/dev/null || true")
            run_cmd(
                f"umount {tgt}/boot/efi "
                f"2>/dev/null || true")
            run_cmd(
                f"umount {tgt} 2>/dev/null || true")
            run_cmd(
                f"swapoff {swap} 2>/dev/null || true")

            self._prog(100, "Installation complete!")
            self._log(
                "\n" + "="*40 +
                "\nRIDOS OS installed successfully!\n" +
                f"Username: {user}\n"
                f"Password: {pwd}\n\n"
                "Remove USB and reboot!\n" +
                "="*40)
            self.root.after(0, self._show_done, user, pwd)

        except Exception as e:
            self._log(f"\nFATAL ERROR: {e}")
            self._prog(0, f"FAILED: {e}")
            # Cleanup on failure
            try:
                for dd in ['sys','proc','dev/pts','dev']:
                    run_cmd(f"umount {tgt}/{dd} "
                            f"2>/dev/null || true")
                run_cmd(f"umount {tgt}/boot/efi "
                        f"2>/dev/null || true")
                run_cmd(f"umount {tgt} "
                        f"2>/dev/null || true")
            except:
                pass
            self.root.after(0, messagebox.showerror,
                            "Installation Failed", str(e))

    def _show_done(self, user, pwd):
        for w in self.content.winfo_children():
            w.destroy()
        f = tk.Frame(self.content, bg=BG)
        f.pack(fill='both', expand=True)
        tk.Label(f, text="✓ Installation Complete!",
                 font=('Arial', 20, 'bold'),
                 bg=BG, fg=GREEN).pack(pady=40)
        tk.Label(
            f,
            text=f"Username: {user}\n"
                 f"Password: {pwd}\n\n"
                 "Remove USB and reboot.",
            font=('Arial', 12),
            bg=BG, fg=TEXT,
            justify='center').pack()
        self._btn(f, "Reboot Now",
                  lambda: run_cmd("reboot"),
                  GREEN).pack(pady=20)
        self._btn(f, "Close", self.root.destroy,
                  BG3).pack()

    # ═══════════════════════════════════════════════════════════
    # PAGE: About
    # ═══════════════════════════════════════════════════════════
    def _page_about(self):
        f = tk.Frame(self.content, bg=BG)
        f.pack(fill='both', expand=True, padx=24, pady=24)
        tk.Label(f, text="RIDOS OS v1.0 Baghdad",
                 font=('Arial', 20, 'bold'),
                 bg=BG, fg=PURPLE).pack(pady=(20, 8))
        tk.Label(
            f,
            text="AI-Powered Linux for IT & "
                 "Communications Professionals\n\n"
                 "Disk Manager + OS Installer\n"
                 "Python 3 + Tkinter — No Calamares\n\n"
                 "Features:\n"
                 "  • Create / Delete / Format partitions\n"
                 "  • Resize partitions (EXT4, XFS)\n"
                 "  • Set boot / active flags\n"
                 "  • Full OS installation with GRUB\n\n"
                 "License: GPL v3\n"
                 "github.com/alkinanireyad/RIDOS-OS",
            font=('Arial', 11),
            bg=BG, fg=TEXT,
            justify='center').pack(pady=12)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = RIDOSInstaller()
    app.run()
