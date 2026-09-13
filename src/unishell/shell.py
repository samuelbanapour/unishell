#!/usr/bin/env python3
"""UniShell: one REPL that understands PowerShell, cmd.exe, and POSIX/Linux
command styles against the same built-in, simulated command implementations
(no shelling out to the OS's own ls/dir/ps/etc.)."""

import os
import sys
import shutil
import socket
import getpass
import platform
import shlex
import fnmatch
import time
from datetime import datetime

import psutil

HISTORY = []
ENV = dict(os.environ)
START_DIR = os.getcwd()


class ShellError(Exception):
    pass


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def resolve(path):
    if not path:
        return os.getcwd()
    path = os.path.expanduser(os.path.expandvars(path))
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    return os.path.normpath(path)


def human_size(n):
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}P"


def split_flags(args):
    """Split args into (flags, positional). Accepts -x, --long, /x (cmd), -Recurse (PS)."""
    flags, pos = set(), []
    for a in args:
        if a.startswith("--"):
            flags.add(a[2:].lower())
        elif a.startswith("-") and len(a) > 1 and not a[1:].replace(".", "").isdigit():
            flags.add(a[1:].lower())
        elif a.startswith("/") and len(a) <= 3:
            flags.add(a[1:].lower())
        else:
            pos.append(a)
    return flags, pos


def has(flags, *names):
    return any(n in flags for n in names)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_help(args, flags):
    print("""UniShell -- PowerShell + cmd.exe + POSIX, one interpreter.

Type any of these families interchangeably; they all hit the same logic:
  ls / dir / gci / Get-ChildItem      list directory
  cd / chdir / sl / Set-Location      change directory
  pwd / gl / Get-Location             print working directory
  mkdir / md / New-Item -ItemType Directory
  rmdir / rd                         remove empty/recursive directory
  rm / del / erase / ri / Remove-Item  remove file(s) (add -r/-Recurse for dirs)
  cp / copy / cpi / Copy-Item         copy file/dir
  mv / move / ren / Rename-Item / mi / Move-Item
  cat / type / gc / Get-Content       print file contents
  touch / New-Item -ItemType File     create empty file / update timestamp
  echo / Write-Output / Write-Host    print text
  cls / clear / Clear-Host            clear screen
  find / findstr / grep / sls / Select-String   search text in files
  head / tail                        first/last N lines
  wc                                  line/word/char count
  tree                                recursive directory tree
  whoami                              current user
  hostname                            machine name
  date / Get-Date                     current date/time
  env / set / export / $env:          show or set environment variables
  ps / tasklist / Get-Process [name]   list running processes (real, via psutil)
  kill / taskkill / Stop-Process PID [-f]   terminate a process (add -f for SIGKILL)
  ipconfig / ifconfig / Get-NetIPConfiguration   local network info
  ping / Test-Connection              simple TCP-based reachability check
  history                             command history
  help / ?                            this message
  exit / quit / q / Exit              leave UniShell
""")


def cmd_pwd(args, flags):
    print(os.getcwd())


def cmd_cd(args, flags):
    target = args[0] if args else ENV.get("HOME", START_DIR)
    if target == "-":
        target = ENV.get("OLDPWD", os.getcwd())
    path = resolve(target)
    if not os.path.isdir(path):
        raise ShellError(f"cd: no such directory: {target}")
    ENV["OLDPWD"] = os.getcwd()
    os.chdir(path)


def cmd_ls(args, flags):
    show_all = has(flags, "a", "all", "force")
    long_fmt = has(flags, "l", "long")
    targets = args or ["."]
    for i, t in enumerate(targets):
        path = resolve(t)
        if not os.path.exists(path):
            print(f"ls: cannot access '{t}': No such file or directory")
            continue
        if len(targets) > 1:
            print(f"{t}:")
        if os.path.isfile(path):
            entries = [os.path.basename(path)]
            base = os.path.dirname(path)
        else:
            base = path
            entries = sorted(os.listdir(path))
            if not show_all:
                entries = [e for e in entries if not e.startswith(".")]
        for name in entries:
            full = os.path.join(base, name)
            if long_fmt:
                try:
                    st = os.stat(full)
                    kind = "d" if os.path.isdir(full) else "-"
                    mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                    print(f"{kind}  {human_size(st.st_size):>8}  {mtime}  {name}")
                except OSError:
                    print(name)
            else:
                print(name + ("/" if os.path.isdir(full) else ""))
        if len(targets) > 1 and i < len(targets) - 1:
            print()


def cmd_tree(args, flags):
    root = resolve(args[0]) if args else os.getcwd()
    max_depth = None
    for a in args:
        if a.isdigit():
            max_depth = int(a)

    def walk(path, prefix, depth):
        if max_depth is not None and depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(path))
        except OSError:
            return
        entries = [e for e in entries if not e.startswith(".")]
        for idx, name in enumerate(entries):
            full = os.path.join(path, name)
            last = idx == len(entries) - 1
            connector = "└── " if last else "├── "
            print(prefix + connector + name + ("/" if os.path.isdir(full) else ""))
            if os.path.isdir(full):
                walk(full, prefix + ("    " if last else "│   "), depth + 1)

    print(root)
    walk(root, "", 1)


def cmd_mkdir(args, flags):
    if not args:
        raise ShellError("mkdir: missing operand")
    for a in args:
        path = resolve(a)
        os.makedirs(path, exist_ok=has(flags, "p", "parents", "force"))


def cmd_rmdir(args, flags):
    if not args:
        raise ShellError("rmdir: missing operand")
    recurse = has(flags, "r", "recurse", "recursive", "s")
    for a in args:
        path = resolve(a)
        if recurse:
            shutil.rmtree(path, ignore_errors=has(flags, "force", "f"))
        else:
            os.rmdir(path)


def cmd_rm(args, flags):
    if not args:
        raise ShellError("rm: missing operand")
    recurse = has(flags, "r", "recurse", "recursive", "s")
    force = has(flags, "f", "force")
    for a in args:
        for path in (expand_glob(a) or [resolve(a)]):
            if not os.path.exists(path):
                if not force:
                    print(f"rm: cannot remove '{a}': No such file or directory")
                continue
            if os.path.isdir(path):
                if recurse:
                    shutil.rmtree(path)
                else:
                    raise ShellError(f"rm: cannot remove '{a}': Is a directory (use -r/-Recurse)")
            else:
                os.remove(path)


def expand_glob(pattern):
    path = resolve(pattern)
    base = os.path.dirname(path)
    name = os.path.basename(path)
    if not any(c in name for c in "*?[]"):
        return None
    if not os.path.isdir(base):
        return []
    return [os.path.join(base, f) for f in os.listdir(base) if fnmatch.fnmatch(f, name)]


def cmd_cp(args, flags):
    if len(args) < 2:
        raise ShellError("cp: missing file operand")
    *srcs, dst = args
    dst_path = resolve(dst)
    recurse = has(flags, "r", "recurse", "recursive")
    for s in srcs:
        src_path = resolve(s)
        if os.path.isdir(src_path):
            if not recurse:
                raise ShellError(f"cp: -r/-Recurse not specified; omitting directory '{s}'")
            target = os.path.join(dst_path, os.path.basename(src_path)) if os.path.isdir(dst_path) else dst_path
            shutil.copytree(src_path, target, dirs_exist_ok=True)
        else:
            target = dst_path
            if os.path.isdir(dst_path):
                target = os.path.join(dst_path, os.path.basename(src_path))
            shutil.copy2(src_path, target)


def cmd_mv(args, flags):
    if len(args) < 2:
        raise ShellError("mv: missing file operand")
    *srcs, dst = args
    dst_path = resolve(dst)
    for s in srcs:
        src_path = resolve(s)
        target = dst_path
        if os.path.isdir(dst_path):
            target = os.path.join(dst_path, os.path.basename(src_path))
        shutil.move(src_path, target)


def cmd_touch(args, flags):
    if not args:
        raise ShellError("touch: missing file operand")
    for a in args:
        path = resolve(a)
        if os.path.exists(path):
            os.utime(path, None)
        else:
            open(path, "a").close()


def cmd_cat(args, flags):
    if not args:
        data = sys.stdin.read()
        print(data, end="")
        return
    for a in args:
        path = resolve(a)
        try:
            with open(path, "r", errors="replace") as f:
                sys.stdout.write(f.read())
        except IsADirectoryError:
            print(f"cat: {a}: Is a directory")
        except OSError as e:
            print(f"cat: {a}: {e.strerror}")


def cmd_head_tail(args, flags, tail=False):
    n = 10
    files = []
    it = iter(args)
    for a in it:
        if a in ("-n", "-N"):
            n = int(next(it))
        elif a.lower().startswith("-n") and a[2:].isdigit():
            n = int(a[2:])
        else:
            files.append(a)
    if not files:
        raise ShellError("missing file operand")
    for f in files:
        path = resolve(f)
        with open(path, "r", errors="replace") as fh:
            lines = fh.readlines()
        chosen = lines[-n:] if tail else lines[:n]
        sys.stdout.write("".join(chosen))


def cmd_wc(args, flags):
    if not args:
        raise ShellError("wc: missing file operand")
    for a in args:
        path = resolve(a)
        with open(path, "r", errors="replace") as f:
            text = f.read()
        print(f"{text.count(chr(10)):>7} {len(text.split()):>7} {len(text):>7} {a}")


def cmd_grep(args, flags):
    if len(args) < 2:
        raise ShellError("grep: usage: grep PATTERN FILE...")
    pattern, *files = args
    ignore_case = has(flags, "i")
    needle = pattern.lower() if ignore_case else pattern
    for f in files:
        path = resolve(f)
        try:
            with open(path, "r", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    hay = line.lower() if ignore_case else line
                    if needle in hay:
                        prefix = f"{f}:{lineno}:" if len(files) > 1 else f"{lineno}:"
                        print(prefix + line.rstrip("\n"))
        except OSError as e:
            print(f"grep: {f}: {e.strerror}")


def cmd_echo(args, flags):
    print(" ".join(args))


def cmd_clear(args, flags):
    print("\033c", end="")


def cmd_whoami(args, flags):
    print(getpass.getuser())


def cmd_hostname(args, flags):
    print(socket.gethostname())


def cmd_date(args, flags):
    print(datetime.now().strftime("%a %b %d %H:%M:%S %Y"))


def cmd_env(args, flags):
    if not args:
        for k in sorted(ENV):
            print(f"{k}={ENV[k]}")
        return
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            ENV[k] = v
            os.environ[k] = v
        else:
            print(f"{a}={ENV.get(a, '')}")


def cmd_ps(args, flags):
    name_filter = args[0].lower() if args else None
    print(f"{'PID':>7}  {'%CPU':>5}  {'%MEM':>5}  {'STATUS':<10}  CMD")
    procs = []
    for p in psutil.process_iter(["pid", "name", "status", "memory_percent"]):
        try:
            info = p.info
            if name_filter and name_filter not in (info["name"] or "").lower():
                continue
            procs.append((info["pid"], info["name"] or "?", info["status"],
                          info["memory_percent"] or 0.0, p.cpu_percent(interval=None)))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    for pid, name, status, mem, cpu in sorted(procs, key=lambda r: r[0]):
        print(f"{pid:>7}  {cpu:>5.1f}  {mem:>5.1f}  {status:<10}  {name}")


def cmd_kill(args, flags):
    if not args:
        raise ShellError("kill: missing PID")
    force = has(flags, "f", "force", "9")
    for a in args:
        try:
            pid = int(a)
        except ValueError:
            raise ShellError(f"kill: invalid PID: {a}")
        try:
            proc = psutil.Process(pid)
            if force:
                proc.kill()
                print(f"Killed (SIGKILL) {pid} ({proc.name()})")
            else:
                proc.terminate()
                print(f"Terminated (SIGTERM) {pid} ({proc.name()})")
        except psutil.NoSuchProcess:
            print(f"kill: ({pid}) - No such process")
        except psutil.AccessDenied:
            print(f"kill: ({pid}) - Access denied")


def cmd_ipconfig(args, flags):
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except OSError:
        ip = "unavailable"
    print(f"Host Name . . . . . . . . . . . : {hostname}")
    print(f"IPv4 Address. . . . . . . . . . : {ip}")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        print(f"Outbound Address (route probe). : {s.getsockname()[0]}")
        s.close()
    except OSError:
        pass


def cmd_ping(args, flags):
    if not args:
        raise ShellError("ping: missing host operand")
    host = args[0]
    count = 4
    for a in args[1:]:
        if a.isdigit():
            count = int(a)
    for i in range(count):
        start = time.time()
        try:
            with socket.create_connection((host, 80), timeout=2):
                elapsed = (time.time() - start) * 1000
                print(f"Reply from {host}: tcp_connect time={elapsed:.1f}ms (seq={i+1})")
        except OSError as e:
            print(f"Request to {host} failed: {e}")
        if i < count - 1:
            time.sleep(0.5)


def cmd_history(args, flags):
    for i, h in enumerate(HISTORY, 1):
        print(f"{i:>4}  {h}")


# --------------------------------------------------------------------------
# dispatch table: every alias from PowerShell / cmd.exe / POSIX points at
# the same simulated implementation
# --------------------------------------------------------------------------

COMMANDS = {
    # navigation
    **{k: cmd_ls for k in ("ls", "dir", "gci", "get-childitem", "ll")},
    **{k: cmd_cd for k in ("cd", "chdir", "sl", "set-location")},
    **{k: cmd_pwd for k in ("pwd", "gl", "get-location")},
    "tree": cmd_tree,
    # filesystem
    **{k: cmd_mkdir for k in ("mkdir", "md", "new-item")},
    **{k: cmd_rmdir for k in ("rmdir", "rd")},
    **{k: cmd_rm for k in ("rm", "del", "erase", "ri", "remove-item")},
    **{k: cmd_cp for k in ("cp", "copy", "cpi", "copy-item")},
    **{k: cmd_mv for k in ("mv", "move", "ren", "rename-item", "mi", "move-item")},
    "touch": cmd_touch,
    **{k: cmd_cat for k in ("cat", "type", "gc", "get-content")},
    "head": lambda args, flags: cmd_head_tail(args, flags, tail=False),
    "tail": lambda args, flags: cmd_head_tail(args, flags, tail=True),
    "wc": cmd_wc,
    **{k: cmd_grep for k in ("grep", "findstr", "find", "sls", "select-string")},
    # output / screen
    **{k: cmd_echo for k in ("echo", "write-output", "write-host")},
    **{k: cmd_clear for k in ("cls", "clear", "clear-host")},
    # system
    "whoami": cmd_whoami,
    "hostname": cmd_hostname,
    **{k: cmd_date for k in ("date", "get-date")},
    **{k: cmd_env for k in ("env", "set", "export")},
    **{k: cmd_ps for k in ("ps", "tasklist", "get-process")},
    **{k: cmd_kill for k in ("kill", "taskkill", "stop-process")},
    **{k: cmd_ipconfig for k in ("ipconfig", "ifconfig", "get-netipconfiguration")},
    **{k: cmd_ping for k in ("ping", "test-connection")},
    "history": cmd_history,
    **{k: cmd_help for k in ("help", "?")},
}


def run_line(line):
    line = line.strip()
    if not line:
        return
    HISTORY.append(line)
    try:
        parts = shlex.split(line)
    except ValueError as e:
        print(f"unishell: parse error: {e}")
        return
    if not parts:
        return
    name = parts[0].lower()
    # strip a leading '$' as in `$env:` style noise, and normalize PS verbs
    args_raw = parts[1:]
    if name in ("exit", "quit", "q") or name == "exit":
        raise SystemExit(0)
    handler = COMMANDS.get(name)
    if handler is None:
        print(f"unishell: command not found: {parts[0]}  (type 'help' for the supported command list)")
        return
    flags, positional = split_flags(args_raw)
    try:
        handler(positional, flags)
    except ShellError as e:
        print(str(e))
    except FileNotFoundError as e:
        print(f"{name}: {e.filename}: No such file or directory")
    except NotADirectoryError as e:
        print(f"{name}: not a directory: {e.filename}")
    except PermissionError as e:
        print(f"{name}: permission denied: {e.filename}")
    except OSError as e:
        print(f"{name}: {e}")


def banner():
    print("UniShell -- PowerShell + cmd.exe + POSIX commands, one interpreter.")
    print(f"({platform.system()} {platform.release()}, python {platform.python_version()})")
    print("Type 'help' for the command list, 'exit' to leave.\n")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] in ("--version", "-v"):
            from unishell import __version__
            print(f"unishell {__version__}")
            return
        run_line(" ".join(sys.argv[1:]))
        return
    banner()
    while True:
        try:
            prompt = f"PS/cmd/sh {os.getcwd()}> "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        try:
            run_line(line)
        except SystemExit:
            break


if __name__ == "__main__":
    main()
