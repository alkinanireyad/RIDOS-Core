#!/usr/bin/env python3
"""
ridos-help.py — RIDOS-Core 1.0 Nova
Comprehensive help system for beginners and pro users.
Usage:
    ridos-help              — interactive menu
    ridos-help <topic>      — jump to topic directly
    ridos-help search <kw>  — search all topics
"""
import sys, os, subprocess

# ── Colors ────────────────────────────────────────────────────────────────────
B  = '\033[01;34m'   # bold blue
G  = '\033[01;32m'   # bold green
Y  = '\033[01;33m'   # bold yellow
R  = '\033[01;31m'   # bold red
C  = '\033[01;36m'   # bold cyan
W  = '\033[00m'      # reset
H  = '\033[01;37m'   # bold white

def hdr(text):
    print(f"\n{C}{'─'*60}{W}")
    print(f"{H}  {text}{W}")
    print(f"{C}{'─'*60}{W}\n")

def section(title):
    print(f"\n{B}  ▸ {title}{W}")

def cmd(command, desc):
    print(f"    {G}{command:<35}{W} {desc}")

def note(text):
    print(f"    {Y}ℹ  {text}{W}")

def warn(text):
    print(f"    {R}⚠  {text}{W}")

# ── Help Topics ───────────────────────────────────────────────────────────────

TOPICS = {}

def topic(name, aliases=None):
    def decorator(fn):
        TOPICS[name] = fn
        if aliases:
            for a in aliases:
                TOPICS[a] = fn
        return fn
    return decorator


@topic('about', ['os', 'version'])
def help_about():
    hdr('RIDOS-Core 1.0 Nova — About This OS')
    print(f"""  {H}RIDOS-Core{W} is a next-generation Linux distribution built on:
  • Debian 12 (Bookworm) as the stable base
  • Linux Kernel 6.12 LTS with Rust support (CONFIG_RUST=y)
  • GNOME desktop — Xorg default, Wayland available
  • Brave Browser as the primary browser
  • Full Pro IT / Security / DevOps toolkit pre-installed

  {B}Login credentials (live session):{W}
    Username : ridos
    Password : ridos

  {B}Repository:{W}  github.com/alkinanireyad/RIDOS-Core
  {B}License:{W}     GNU General Public License v3
  {B}Kernel:{W}      Linux 6.12 LTS (Rust-ready)
""")


@topic('install', ['calamares', 'hdd'])
def help_install():
    hdr('Installing RIDOS-Core to Hard Drive')
    section('Method 1 — Desktop icon (easiest)')
    print('    Double-click "Install RIDOS-Core" on the desktop.')
    print('    The Calamares installer will open.\n')
    section('Method 2 — From terminal')
    cmd('sudo /usr/bin/calamares', 'Launch installer directly')
    print()
    section('Installation steps in Calamares')
    steps = [
        ('Welcome',    'Select your language'),
        ('Location',   'Set your timezone'),
        ('Keyboard',   'Choose keyboard layout'),
        ('Partitions', 'Choose disk — Manual or Erase Disk'),
        ('Encryption', 'Optional: enable LUKS full-disk encryption'),
        ('Users',      'Set your username and password'),
        ('Summary',    'Review all choices'),
        ('Install',    'Click Install — takes 5-15 minutes'),
        ('Finish',     'Reboot into your installed system'),
    ]
    for i, (step, desc) in enumerate(steps, 1):
        print(f"    {G}{i}.{W} {H}{step:<12}{W} {desc}")
    print()
    note('VirtualBox: Enable EFI — Machine > Settings > System > Motherboard > Enable EFI')
    note('Minimum disk: 20GB    Recommended: 25GB+')
    warn('Back up your data before erasing a disk')


@topic('network', ['net', 'wifi', 'ip'])
def help_network():
    hdr('Network Commands')
    section('Basic network info')
    cmd('ip addr',                     'Show all network interfaces and IPs')
    cmd('ip addr show eth0',           'Show specific interface')
    cmd('ip route',                    'Show routing table')
    cmd('curl ifconfig.me',            'Show your public IP')
    cmd('hostname -I',                 'Show local IP addresses')
    print()
    section('WiFi')
    cmd('nmcli dev wifi',              'List available WiFi networks')
    cmd('nmcli dev wifi connect "SSID" password "PASS"', 'Connect to WiFi')
    cmd('nmcli con show',              'Show saved connections')
    cmd('nmtui',                       'Text UI for NetworkManager')
    print()
    section('DNS and routing')
    cmd('nslookup google.com',         'DNS lookup')
    cmd('dig google.com',              'Detailed DNS query')
    cmd('traceroute google.com',       'Trace network path')
    cmd('mtr google.com',              'Live network path monitor')
    print()
    section('Network testing')
    cmd('ping -c 4 8.8.8.8',          'Test connectivity')
    cmd('iperf3 -s',                   'Start bandwidth test server')
    cmd('iperf3 -c <server-ip>',       'Run bandwidth test to server')
    cmd('netstat -tuln',               'Show open ports (listening)')
    cmd('ss -tuln',                    'Modern netstat replacement')


@topic('security', ['sec', 'pentest', 'hack'])
def help_security():
    hdr('Security & Penetration Testing Tools')
    warn('Use these tools only on systems you own or have written permission to test.')
    print()
    section('Network scanning')
    cmd('nmap -sV <target>',           'Scan open ports + service versions')
    cmd('nmap -A <target>',            'Aggressive scan (OS, scripts, versions)')
    cmd('nmap -sn 192.168.1.0/24',    'Ping scan — find live hosts on network')
    cmd('nmap --script vuln <target>', 'Vulnerability scan')
    print()
    section('Packet capture and analysis')
    cmd('sudo tcpdump -i eth0',        'Capture all traffic on eth0')
    cmd('sudo tcpdump -i eth0 port 80','Capture HTTP traffic only')
    cmd('wireshark',                   'Launch Wireshark GUI')
    cmd('tshark -i eth0',              'Wireshark in terminal mode')
    print()
    section('Password auditing')
    cmd('john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt', 'Crack password hash')
    cmd('hashcat -m 0 hash.txt wordlist.txt', 'GPU-accelerated hash cracking')
    cmd('hydra -l admin -P passwords.txt ssh://<target>', 'Brute-force SSH login')
    print()
    section('Web application testing')
    cmd('nikto -h http://<target>',    'Web server vulnerability scanner')
    cmd('sqlmap -u "http://target/?id=1"', 'SQL injection tester')
    cmd('dirb http://<target>',        'Directory/file brute-force')
    print()
    section('WiFi security')
    cmd('sudo airmon-ng start wlan0',  'Enable monitor mode')
    cmd('sudo airodump-ng wlan0mon',   'Capture WiFi packets')
    note('aircrack-ng suite is pre-installed for authorized WiFi security testing')
    print()
    section('Forensics and steganography')
    cmd('binwalk firmware.bin',        'Analyze binary/firmware files')
    cmd('steghide extract -sf image.jpg', 'Extract hidden data from image')
    cmd('foremost -i disk.img',        'File recovery from disk image')
    cmd('testdisk',                    'Partition and file recovery tool')


@topic('system', ['sys', 'monitor', 'performance'])
def help_system():
    hdr('System Monitoring and Management')
    section('Process monitoring')
    cmd('htop',                        'Interactive process viewer (press q to quit)')
    cmd('btop',                        'Modern resource monitor with graphs')
    cmd('iotop',                       'Monitor disk I/O per process')
    cmd('iftop',                       'Monitor network bandwidth per connection')
    cmd('nethogs',                     'Network usage per process')
    cmd('ps aux',                      'List all running processes')
    cmd('kill <PID>',                  'Stop a process by ID')
    cmd('killall firefox',             'Stop all processes by name')
    print()
    section('Disk and storage')
    cmd('df -h',                       'Show disk space usage')
    cmd('du -sh *',                    'Show folder sizes in current directory')
    cmd('ncdu',                        'Interactive disk usage analyzer')
    cmd('lsblk',                       'List block devices (disks, partitions)')
    cmd('gparted',                     'Graphical partition manager')
    cmd('smartctl -a /dev/sda',        'Check disk health (SMART data)')
    print()
    section('Memory and CPU')
    cmd('free -h',                     'Show RAM usage')
    cmd('vmstat 1',                    'System stats every 1 second')
    cmd('lscpu',                       'Show CPU information')
    cmd('cat /proc/cpuinfo',           'Detailed CPU info')
    print()
    section('Services (systemd)')
    cmd('systemctl status <service>',  'Check if a service is running')
    cmd('sudo systemctl start <svc>',  'Start a service')
    cmd('sudo systemctl stop <svc>',   'Stop a service')
    cmd('sudo systemctl enable <svc>', 'Start service on boot')
    cmd('sudo systemctl disable <svc>','Disable service on boot')
    cmd('journalctl -f',               'Follow system logs live')
    cmd('journalctl -u <service>',     'Logs for a specific service')
    print()
    section('Hardware info')
    cmd('lshw -short',                 'Hardware summary')
    cmd('dmidecode -t system',         'System BIOS/motherboard info')
    cmd('lspci',                       'List PCI devices (GPU, network, etc)')
    cmd('lsusb',                       'List USB devices')
    cmd('inxi -Fxz',                   'Full system info (install if missing)')


@topic('docker', ['containers', 'container'])
def help_docker():
    hdr('Docker — Container Management')
    section('Basic commands')
    cmd('sudo docker ps',              'List running containers')
    cmd('sudo docker ps -a',           'List all containers (including stopped)')
    cmd('sudo docker images',          'List downloaded images')
    cmd('sudo docker pull ubuntu',     'Download Ubuntu image')
    cmd('sudo docker run -it ubuntu bash', 'Run Ubuntu container interactively')
    cmd('sudo docker stop <name>',     'Stop a container')
    cmd('sudo docker rm <name>',       'Remove a container')
    print()
    section('Docker Compose')
    cmd('sudo docker-compose up -d',   'Start services in background')
    cmd('sudo docker-compose down',    'Stop and remove services')
    cmd('sudo docker-compose logs -f', 'Follow service logs')
    print()
    note('Add yourself to docker group to avoid typing sudo: sudo usermod -aG docker $USER')
    note('Then log out and back in for the change to take effect')


@topic('git', ['version-control', 'github'])
def help_git():
    hdr('Git — Version Control')
    section('Setup (first time)')
    cmd('git config --global user.name "Your Name"',   'Set your name')
    cmd('git config --global user.email "you@email.com"', 'Set your email')
    print()
    section('Daily workflow')
    cmd('git clone <url>',             'Download a repository')
    cmd('git status',                  'See what changed')
    cmd('git add .',                   'Stage all changes')
    cmd('git add <file>',              'Stage specific file')
    cmd('git commit -m "message"',     'Save staged changes')
    cmd('git push',                    'Upload commits to remote')
    cmd('git pull',                    'Download latest changes')
    print()
    section('Branches')
    cmd('git branch',                  'List branches')
    cmd('git checkout -b feature-x',   'Create and switch to new branch')
    cmd('git merge feature-x',         'Merge branch into current')
    cmd('git log --oneline',           'Show commit history')


@topic('files', ['filesystem', 'fs', 'find'])
def help_files():
    hdr('File Management')
    section('Navigation')
    cmd('pwd',                         'Show current directory')
    cmd('ls -la',                      'List files with details and hidden files')
    cmd('cd /path/to/dir',             'Change directory')
    cmd('cd ~',                        'Go to home directory')
    cmd('cd -',                        'Go back to previous directory')
    print()
    section('File operations')
    cmd('cp source dest',              'Copy file')
    cmd('cp -r source/ dest/',         'Copy directory recursively')
    cmd('mv source dest',              'Move or rename file')
    cmd('rm file',                     'Delete file')
    cmd('rm -rf directory/',           'Delete directory and contents')
    cmd('mkdir -p path/to/dir',        'Create directory (and parents)')
    print()
    section('Search')
    cmd('find / -name "*.conf"',       'Find files by name')
    cmd('find /home -size +100M',      'Find files larger than 100MB')
    cmd('rg "search term"',            'Fast text search in files (ripgrep)')
    cmd('grep -r "pattern" /path',     'Search text in files recursively')
    cmd('fd filename',                 'Fast file finder (fd-find)')
    print()
    section('Permissions')
    cmd('chmod 755 file',              'Set file permissions')
    cmd('chmod +x script.sh',          'Make file executable')
    cmd('chown user:group file',       'Change file owner')
    cmd('ls -la',                      'View file permissions')
    print()
    section('Archives')
    cmd('tar -czf archive.tar.gz dir/','Create compressed archive')
    cmd('tar -xzf archive.tar.gz',     'Extract archive')
    cmd('zip -r archive.zip dir/',     'Create zip archive')
    cmd('unzip archive.zip',           'Extract zip')
    cmd('7z x archive.7z',             'Extract 7-zip archive')


@topic('apt', ['packages', 'install-pkg', 'software'])
def help_apt():
    hdr('Package Management (APT)')
    section('Installing software')
    cmd('sudo apt-get update',         'Refresh package list (run first)')
    cmd('sudo apt-get upgrade',        'Upgrade all installed packages')
    cmd('sudo apt-get install <pkg>',  'Install a package')
    cmd('sudo apt-get remove <pkg>',   'Remove a package (keep config)')
    cmd('sudo apt-get purge <pkg>',    'Remove package and config files')
    cmd('sudo apt-get autoremove',     'Remove unused dependencies')
    print()
    section('Searching')
    cmd('apt-cache search keyword',    'Search for packages')
    cmd('apt-cache show <pkg>',        'Show package details')
    cmd('dpkg -l | grep <pkg>',        'Check if package is installed')
    print()
    section('Flatpak (sandboxed apps)')
    cmd('flatpak install flathub <app>','Install app from Flathub')
    cmd('flatpak list',                 'List installed Flatpak apps')
    cmd('flatpak update',               'Update all Flatpak apps')
    cmd('flatpak run <app-id>',         'Run Flatpak app')
    note('Flathub website: https://flathub.org — browse thousands of apps')


@topic('ssh', ['remote', 'server'])
def help_ssh():
    hdr('SSH — Remote Access')
    section('Connecting')
    cmd('ssh user@hostname',           'Connect to remote server')
    cmd('ssh user@192.168.1.100',      'Connect by IP address')
    cmd('ssh -p 2222 user@host',       'Connect on non-standard port')
    cmd('ssh -i key.pem user@host',    'Connect with SSH key file')
    print()
    section('File transfer')
    cmd('scp file.txt user@host:/path','Copy file to remote server')
    cmd('scp user@host:/path/file .',  'Copy file from remote server')
    cmd('rsync -avz src/ user@host:dst/','Sync directory to remote')
    print()
    section('SSH keys (more secure than passwords)')
    cmd('ssh-keygen -t ed25519',       'Generate new SSH key pair')
    cmd('ssh-copy-id user@host',       'Copy your key to remote server')
    note('After copying key, you can login without password')
    print()
    section('SSH server (on this machine)')
    cmd('sudo systemctl start ssh',    'Start SSH server')
    cmd('sudo systemctl enable ssh',   'Start SSH on boot')
    cmd('sudo systemctl status ssh',   'Check if SSH is running')


@topic('rust', ['rustlang', 'cargo'])
def help_rust():
    hdr('Rust Development (RIDOS-Core Native Language)')
    note('RIDOS-Core runs on Linux 6.12 LTS with CONFIG_RUST=y — Rust is in the kernel!')
    print()
    section('Install Rust toolchain (optional — not in base OS)')
    cmd('curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh',
        'Install Rust via rustup')
    cmd('source ~/.cargo/env',         'Load Rust into current shell')
    cmd('rustc --version',             'Check Rust version')
    print()
    section('Cargo — Rust package manager')
    cmd('cargo new my-project',        'Create new Rust project')
    cmd('cargo build',                 'Compile project')
    cmd('cargo run',                   'Compile and run')
    cmd('cargo test',                  'Run tests')
    cmd('cargo add <crate>',           'Add dependency')
    print()
    section('Why Rust matters in RIDOS-Core')
    print('    Memory safety without garbage collection')
    print('    Zero-cost abstractions — fast as C')
    print('    Kernel 6.12+ supports Rust drivers natively')
    print('    Future RIDOS versions will replace C utilities with Rust')


@topic('vpn', ['wireguard', 'privacy'])
def help_vpn():
    hdr('VPN — WireGuard')
    section('Setup WireGuard VPN')
    cmd('sudo apt-get install wireguard', 'Install WireGuard (if not installed)')
    cmd('wg genkey | tee private.key | wg pubkey > public.key',
        'Generate key pair')
    cmd('sudo wg show',                'Show active VPN connections')
    cmd('sudo wg-quick up wg0',        'Connect to VPN (needs config file)')
    cmd('sudo wg-quick down wg0',      'Disconnect VPN')
    print()
    note('Config file goes in /etc/wireguard/wg0.conf')
    note('WireGuard is built into Linux 6.12 kernel — fastest possible VPN')


@topic('ai', ['ollama', 'llm'])
def help_ai():
    hdr('AI Assistant — Ollama (Optional)')
    note('Ollama is NOT installed by default — install via Optional Tools app')
    print()
    section('Install Ollama')
    cmd('bash /opt/ridos-core/bin/install-ollama.sh', 'Install Ollama + Phi-3 model')
    print()
    section('Using the AI assistant')
    cmd('ridos-ai',                    'Start interactive AI chat')
    cmd('ridos-ai "explain nmap"',     'Ask one question and exit')
    cmd('ollama run phi3:mini',        'Run Phi-3 mini directly')
    cmd('ollama run llama3',           'Run Llama 3 (if downloaded)')
    cmd('ollama list',                 'Show downloaded models')
    cmd('ollama pull phi3:mini',       'Download Phi-3 mini (~2GB)')
    print()
    note('Phi-3 mini: fast, 2GB RAM, good for quick questions')
    note('Llama 3: better quality, needs 8GB+ RAM')


@topic('panic', ['panic-key', 'emergency', 'security-key'])
def help_panic():
    hdr('Panic Key — Emergency Security Feature')
    warn('This feature wipes RAM and shuts down immediately. Use with care.')
    print()
    section('Install the Panic Key')
    cmd('sudo python3 /opt/ridos-core/bin/panic-key.py --install',
        'Install Panic Key system service')
    print()
    section('How it works')
    print('    After installing, the keybinding Ctrl+Alt+Pause triggers:')
    print('    1. A 3-second countdown (press Ctrl+C to cancel)')
    print('    2. Filesystem sync')
    print('    3. Swap wipe')
    print('    4. RAM cache drop')
    print('    5. Immediate forced poweroff')
    print()
    note('Useful for: protecting data in urgent security situations')
    note('For LUKS-encrypted systems: disk data is safe even if machine is seized')


@topic('shortcuts', ['keybindings', 'keyboard', 'gnome-keys'])
def help_shortcuts():
    hdr('GNOME Keyboard Shortcuts')
    section('Window management')
    cmd('Super (Win key)',             'Open Activities overview')
    cmd('Super + D',                   'Show desktop')
    cmd('Super + Arrow keys',          'Snap window to sides')
    cmd('Alt + F4',                    'Close window')
    cmd('Alt + Tab',                   'Switch between windows')
    cmd('Super + Tab',                 'Switch between applications')
    print()
    section('Terminal shortcuts')
    cmd('Ctrl + Alt + T',              'Open new terminal')
    cmd('Ctrl + C',                    'Cancel running command')
    cmd('Ctrl + L',                    'Clear terminal screen')
    cmd('Ctrl + R',                    'Search command history')
    cmd('Tab',                         'Auto-complete command or filename')
    cmd('Up/Down arrows',              'Navigate command history')
    print()
    section('Screenshot')
    cmd('Print Screen',                'Screenshot whole screen')
    cmd('Shift + Print Screen',        'Screenshot selected area')
    cmd('Alt + Print Screen',          'Screenshot current window')


@topic('update', ['upgrade', 'updates'])
def help_update():
    hdr('Updating RIDOS-Core')
    section('System update (full)')
    cmd('sudo apt-get update',         'Refresh package list')
    cmd('sudo apt-get upgrade',        'Upgrade all packages')
    cmd('sudo apt-get dist-upgrade',   'Upgrade including kernel')
    cmd('sudo apt-get autoremove',     'Clean unused packages')
    print()
    section('One-liner full update')
    cmd('sudo apt-get update && sudo apt-get upgrade -y',
        'Update and upgrade in one command')
    print()
    section('Firmware updates')
    cmd('sudo fwupdmgr refresh',       'Check for firmware updates')
    cmd('sudo fwupdmgr update',        'Apply firmware updates')
    note('fwupd handles BIOS, SSD, and peripheral firmware automatically')


@topic('beginners', ['beginner', 'new', 'start', 'intro'])
def help_beginners():
    hdr('Getting Started — Guide for New Users')
    print(f"""  Welcome to RIDOS-Core! Here are the most important things to know:

  {B}1. Open a terminal{W}
     Right-click the desktop > Open Terminal
     Or press Ctrl+Alt+T

  {B}2. Install RIDOS-Core to your hard drive{W}
     Double-click "Install RIDOS-Core" on the desktop
     Or type: sudo /usr/bin/calamares

  {B}3. Install software{W}
     sudo apt-get install <software-name>
     Example: sudo apt-get install vlc

  {B}4. Connect to WiFi{W}
     Click the network icon in the top bar
     Or type: nmtui

  {B}5. Update your system{W}
     sudo apt-get update && sudo apt-get upgrade

  {B}6. Browse the web{W}
     Brave Browser is pre-installed (privacy-first)
     Firefox-ESR is also available as backup

  {B}7. Get help{W}
     ridos-help <topic>     — this help system
     man <command>          — manual for any command
     <command> --help       — quick help for a command
""")
    note('Type "ridos-help topics" to see all available help topics')


@topic('topics', ['list', 'help'])
def help_topics():
    hdr('All Available Help Topics')
    topics_list = [
        ('about',     'About RIDOS-Core — version, features, credentials'),
        ('beginners', 'Getting started guide for new users'),
        ('install',   'Install RIDOS-Core to hard drive (Calamares)'),
        ('network',   'Network commands — IP, WiFi, DNS, testing'),
        ('security',  'Security tools — nmap, wireshark, john, hydra, nikto'),
        ('system',    'System monitoring — htop, btop, disk, services'),
        ('docker',    'Docker container management'),
        ('git',       'Git version control'),
        ('files',     'File management — find, copy, search, permissions'),
        ('apt',       'Package management — install, update, Flatpak'),
        ('ssh',       'SSH remote access and file transfer'),
        ('rust',      'Rust development — cargo, rustup'),
        ('vpn',       'WireGuard VPN setup and usage'),
        ('ai',        'Ollama AI assistant setup and usage'),
        ('panic',     'Panic Key emergency security feature'),
        ('shortcuts', 'GNOME keyboard shortcuts'),
        ('update',    'System and firmware updates'),
    ]
    for name, desc in topics_list:
        print(f"    {G}ridos-help {name:<12}{W} {desc}")
    print()
    note('You can also search: ridos-help search <keyword>')


def search_topics(keyword):
    kw = keyword.lower()
    hdr(f'Search results for: "{keyword}"')
    found = False
    # Search through function docstrings and names
    search_map = {
        'nmap': 'security', 'wireshark': 'security', 'scan': 'security',
        'password': 'security', 'hack': 'security', 'pentest': 'security',
        'wifi': 'network', 'ip': 'network', 'dns': 'network', 'ping': 'network',
        'disk': 'system', 'cpu': 'system', 'ram': 'system', 'memory': 'system',
        'process': 'system', 'service': 'system', 'log': 'system',
        'file': 'files', 'find': 'files', 'copy': 'files', 'permission': 'files',
        'install': 'apt', 'package': 'apt', 'apt': 'apt', 'flatpak': 'apt',
        'remote': 'ssh', 'ssh': 'ssh', 'server': 'ssh',
        'docker': 'docker', 'container': 'docker',
        'git': 'git', 'github': 'git', 'commit': 'git',
        'rust': 'rust', 'cargo': 'rust',
        'vpn': 'vpn', 'wireguard': 'vpn',
        'ai': 'ai', 'ollama': 'ai', 'llm': 'ai',
        'panic': 'panic', 'emergency': 'panic',
        'update': 'update', 'upgrade': 'update', 'firmware': 'update',
        'shortcut': 'shortcuts', 'keyboard': 'shortcuts',
        'beginner': 'beginners', 'start': 'beginners', 'new': 'beginners',
        'calamares': 'install', 'hdd': 'install', 'partition': 'install',
    }
    matched = set()
    for term, topic_name in search_map.items():
        if kw in term or term in kw:
            matched.add(topic_name)
    if matched:
        for topic_name in matched:
            print(f"    {G}ridos-help {topic_name}{W}")
        found = True
    if not found:
        print(f"    No results for '{keyword}'. Try: ridos-help topics")


# ── Main ──────────────────────────────────────────────────────────────────────

def interactive_menu():
    os.system('clear')
    hdr('RIDOS-Core 1.0 Nova — Help System')
    print(f"""  {H}Quick navigation:{W}
    {G}1{W}  About this OS          {G}2{W}  Getting started (beginners)
    {G}3{W}  Install to hard drive  {G}4{W}  Network commands
    {G}5{W}  Security tools         {G}6{W}  System monitoring
    {G}7{W}  Docker containers      {G}8{W}  Git version control
    {G}9{W}  File management        {G}10{W} Package management (apt)
    {G}11{W} SSH remote access      {G}12{W} Rust development
    {G}13{W} WireGuard VPN          {G}14{W} AI assistant (Ollama)
    {G}15{W} Panic Key security     {G}16{W} Keyboard shortcuts
    {G}17{W} System updates         {G}18{W} All topics list
    {G}q{W}  Quit
""")
    menu_map = {
        '1':'about','2':'beginners','3':'install','4':'network',
        '5':'security','6':'system','7':'docker','8':'git',
        '9':'files','10':'apt','11':'ssh','12':'rust',
        '13':'vpn','14':'ai','15':'panic','16':'shortcuts',
        '17':'update','18':'topics',
    }
    try:
        choice = input(f"  {C}Enter number or topic name: {W}").strip().lower()
        if choice in ('q', 'quit', 'exit'):
            return
        topic_name = menu_map.get(choice, choice)
        if topic_name in TOPICS:
            TOPICS[topic_name]()
        else:
            print(f"\n  Unknown topic '{choice}'. Type 'ridos-help topics' for list.")
    except (KeyboardInterrupt, EOFError):
        print()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        interactive_menu()
    elif sys.argv[1] == 'search' and len(sys.argv) > 2:
        search_topics(' '.join(sys.argv[2:]))
    elif sys.argv[1] in TOPICS:
        TOPICS[sys.argv[1]]()
    else:
        # Try partial match
        kw = sys.argv[1].lower()
        matches = [t for t in TOPICS if kw in t]
        if len(matches) == 1:
            TOPICS[matches[0]]()
        elif matches:
            print(f"\nDid you mean: {', '.join(matches)}?")
        else:
            print(f"\nUnknown topic '{sys.argv[1]}'")
            help_topics()
