#!/usr/bin/env python3
"""
ridos_shell.py — RIDOS-Core 1.0 Nova
Interactive shell with built-in system commands.
"""
import os, sys, subprocess, shlex

PROMPT = "\033[01;34mridos@RIDOS-Core\033[00m:\033[01;36m{cwd}\033[00m$ "

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return str(e)

HELP = """
RIDOS-Core Shell — Commands
  status    System stats       version   RIDOS version
  tools     Open welcome app   ai <q>    Ask AI assistant
  install   Launch Calamares   update    apt update+upgrade
  clear     Clear screen       exit      Quit
All other input is passed to bash.
"""

print("\033[01;34m  RIDOS-Core 1.0 Nova\033[00m — Type 'help' for commands\n")

while True:
    try:
        cwd = os.getcwd().replace(os.path.expanduser('~'), '~')
        line = input(PROMPT.format(cwd=cwd)).strip()
    except (KeyboardInterrupt, EOFError):
        print("\nType 'exit' to quit.")
        continue
    if not line: continue
    cmd = line.split()[0]
    arg = line[len(cmd):].strip()

    if cmd in ('exit','quit'):
        print("Goodbye from RIDOS-Core!")
        break
    elif cmd == 'help':   print(HELP)
    elif cmd == 'version': print("RIDOS-Core 1.0 Nova\ngithub.com/alkinanireyad/RIDOS-Core")
    elif cmd == 'status':
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            print(f"CPU: {cpu}%  RAM: {mem.used//(1024**2)}MB/{mem.total//(1024**2)}MB ({mem.percent}%)")
        except ImportError:
            print(run("free -h"))
    elif cmd == 'tools':   subprocess.Popen(['python3', '/opt/ridos-core/bin/welcome-app.py'])
    elif cmd == 'ai':      print(run(f"bash /opt/ridos-core/bin/ridos-ai.sh {shlex.quote(arg)}") if arg else "Usage: ai <question>")
    elif cmd == 'install': subprocess.Popen(['pkexec', '/usr/bin/calamares'])
    elif cmd == 'update':  os.system('sudo apt-get update && sudo apt-get upgrade')
    elif cmd in ('clear','cls'): os.system('clear')
    elif cmd == 'cd':
        try: os.chdir(arg or os.path.expanduser('~'))
        except Exception as e: print(f"cd: {e}")
    else:
        out = run(line)
        if out: print(out)
