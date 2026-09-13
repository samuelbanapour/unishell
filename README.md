# UniShell

One interpreter for PowerShell, cmd.exe, and POSIX/Linux commands. Type any of
the three styles interchangeably — `ls`, `dir`, and `Get-ChildItem` all run
the same built-in implementation. Commands are implemented directly (file
ops via Python's `os`/`shutil`, process info via `psutil`), not by shelling
out to the host OS's own `ls`/`dir`/`ps`/etc.

## Download

Prebuilt standalone binaries (no Python required) are attached to each
[GitHub Release](https://github.com/samuelbanapour/unishell/releases/latest):

| Platform | Download |
|----------|----------|
| Linux (x86_64) | [unishell-linux-x86_64](https://github.com/samuelbanapour/unishell/releases/latest/download/unishell-linux-x86_64) |
| macOS (x86_64 — also runs on Apple Silicon via Rosetta 2) | [unishell-macos-x86_64](https://github.com/samuelbanapour/unishell/releases/latest/download/unishell-macos-x86_64) |
| Windows (x86_64) | [unishell-windows-x86_64.exe](https://github.com/samuelbanapour/unishell/releases/latest/download/unishell-windows-x86_64.exe) |

After downloading on Linux/macOS, mark it executable before running:

```bash
chmod +x unishell-linux-x86_64   # or unishell-macos-x86_64
./unishell-linux-x86_64
```

Every push of a `vX.Y.Z` tag builds fresh binaries for all three platforms
and publishes them as a new release automatically (see
[azure-pipelines.yml](azure-pipelines.yml)).

## Run it

**Standalone binary (no Python required):**

```bash
./dist/unishell
```

**From source:**

```bash
pip install -e .
unishell
```

Run a single command without entering the REPL:

```bash
unishell echo "hello"
```

## Supported commands

| Family        | Aliases                                                        |
|---------------|------------------------------------------------------------------|
| List dir      | `ls`, `dir`, `gci`, `Get-ChildItem`, `ll`                        |
| Change dir    | `cd`, `chdir`, `sl`, `Set-Location`                               |
| Where am I    | `pwd`, `gl`, `Get-Location`                                       |
| Tree          | `tree`                                                            |
| Make dir      | `mkdir`, `md`, `New-Item`                                        |
| Remove dir    | `rmdir`, `rd`                                                     |
| Remove file   | `rm`, `del`, `erase`, `ri`, `Remove-Item`                         |
| Copy          | `cp`, `copy`, `cpi`, `Copy-Item`                                  |
| Move/rename   | `mv`, `move`, `ren`, `Rename-Item`, `mi`, `Move-Item`             |
| Touch         | `touch`                                                           |
| Read file     | `cat`, `type`, `gc`, `Get-Content`                                |
| Head/tail     | `head`, `tail`                                                    |
| Word count    | `wc`                                                              |
| Search        | `grep`, `findstr`, `find`, `sls`, `Select-String`                 |
| Print         | `echo`, `Write-Output`, `Write-Host`                              |
| Clear screen  | `cls`, `clear`, `Clear-Host`                                      |
| Whoami        | `whoami`                                                          |
| Hostname      | `hostname`                                                        |
| Date          | `date`, `Get-Date`                                                |
| Env vars      | `env`, `set`, `export`                                            |
| Processes     | `ps`, `tasklist`, `Get-Process` (real data via `psutil`)          |
| Kill process  | `kill`, `taskkill`, `Stop-Process` (`-f` for SIGKILL)             |
| Network info  | `ipconfig`, `ifconfig`, `Get-NetIPConfiguration`                  |
| Ping          | `ping`, `Test-Connection` (TCP reachability probe, no root needed)|
| History       | `history`                                                         |
| Help          | `help`, `?`                                                       |

Flags are also cross-style: `-r`, `-Recurse`, and `/s` are all read as
"recursive" where relevant; same idea for `-f`/`-Force`/`/f`.

## Build the standalone binary yourself

```bash
pip install -e . pyinstaller
pyinstaller --onefile --name unishell src/unishell/shell.py
```

This produces a self-contained executable for the platform you build on
(PyInstaller does not cross-compile — build on macOS for a macOS binary,
on Windows for a `.exe`, on Linux for a Linux binary).

## Limitations

- `ps`/`kill` need the `psutil` dependency; the standalone binary already
  bundles it.
- `ping` uses a TCP connection attempt rather than raw ICMP, since ICMP
  echo requires elevated privileges on most OSes — reachability results are
  accurate, but latency numbers reflect TCP connect time, not ICMP RTT.
- This project implements a broad, commonly-used subset of PowerShell/cmd/
  POSIX commands, not the complete cmdlet or utility surface of any one
  shell.
