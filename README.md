# 🛡️ LAN File Audit

A lightweight file activity monitoring system for office networks. Tracks **who created, modified, copied, moved, deleted, or opened** files across Windows PCs and Macs — with special highlighting for **Excel, Word, PowerPoint, CSV, and PDF** files.

Built for small offices that need visibility into file activity on shared folders and local machines without enterprise-grade complexity.

---

## ✨ Features

- 🔍 **Real-time file monitoring** — detects create / modify / delete / move / open events
- 📊 **Live desktop dashboard** — dark-themed GUI with filters and search
- 📁 **Office file detection** — Excel, Word, PowerPoint, CSV, PDF highlighted in amber
- 🖥️ **Multi-machine** — agents on Windows PCs report to one central server
- 🌐 **LAN-wide** — monitors all computers on your local network
- 💾 **SQLite storage** — no database setup required
- 📤 **CSV export** — export filtered events for reporting
- 🎯 **Configurable folders** — watch any path on any machine
- 🔒 **Auto-ignore** — skips temp files, builds, and virtual environments

---

## 🏗️ Architecture

```
┌──────────────────────────┐
│   SERVER PC (Windows/Mac)│
│   ─ audit_app.py         │  ← Runs the GUI + embedded server
│   ─ Listens on :5000     │
└────────────┬─────────────┘
             │ receives events over LAN
   ┌─────────┼─────────┬─────────┐
   ▼         ▼         ▼         ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│ PC 1 │ │ PC 2 │ │ PC 3 │ │ PC N │
│agent │ │agent │ │agent │ │agent │  ← FileAuditAgent.exe
└──────┘ └──────┘ └──────┘ └──────┘
```

- **`audit_app.py`** — the main application: GUI + local file watcher + Flask collector
- **`agent.py`** — lightweight watcher installed on each remote PC (no GUI)
- Events flow over HTTP (port 5000) from agents → server

---

## 📦 Components

| File | Purpose | Runs on |
|------|---------|---------|
| `audit_app.py` | Main app with GUI + server | One "server" PC |
| `agent.py` | Background watcher | Every monitored PC |
| `requirements.txt` | Python dependencies | — |
| `.github/workflows/build.yml` | Auto-builds `.exe` / `.app` | GitHub Actions |

---

## 🚀 Quick Start

### Option A — Run from Python (development)

**1. Install Python 3.10+** from [python.org](https://python.org)  
✅ Check **"Add Python to PATH"** during install (Windows)

**2. Clone the repo**
```bash
git clone https://github.com/khajadaudjamadar/file-audit.git
cd file-audit
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Run the main app**
```bash
python audit_app.py
```

A dark-themed window opens. It watches the folders listed in `config.json` (created on first run).

### Option B — Download prebuilt binaries

Go to the **Actions** tab → click the latest successful run → download artifacts:
- **FileAuditAgent-Windows** → `FileAuditAgent.exe`
- **LANFileAudit-Windows** → `LANFileAudit.exe`
- **LANFileAudit-Mac** → `LANFileAudit.app`

No Python needed on target machines.

---

## ⚙️ Configuration

On first run, `config.json` is auto-created:

```json
{
  "server_port": 5000,
  "watch_folders": [
    "C:\\Shared",
    "C:\\Users\\Public\\Documents"
  ],
  "office_extensions": [
    ".xlsx", ".xls", ".xlsm",
    ".docx", ".doc",
    ".pptx", ".ppt",
    ".csv", ".pdf"
  ],
  "access_poll_seconds": 3,
  "heartbeat_seconds": 30
}
```

### Fields

| Field | Description |
|-------|-------------|
| `server_port` | HTTP port for the collector (default 5000) |
| `watch_folders` | List of folders to monitor |
| `office_extensions` | File extensions to flag as "office files" |
| `access_poll_seconds` | How often to check for open file handles |
| `heartbeat_seconds` | How often each agent pings the server |

**Mac path example:** `/Users/yourname/Documents`  
**Windows path example:** `C:\\Users\\Public\\Documents`

---

## 🌐 Deploying Agents to Office PCs

### 1. Note your server's LAN IP

On the server PC:
```bash
# Mac
ipconfig getifaddr en0

# Windows (in Command Prompt)
ipconfig
```
Look for something like `192.168.1.50`.

### 2. Edit `agent.py` on GitHub

Change these two lines:
```python
SERVER  = "http://192.168.1.50:5000"   # ← your server IP
FOLDERS = [r"C:\Shared"]                # ← folders to watch
```

Commit — GitHub Actions rebuilds the `.exe` automatically.

### 3. Deploy the agent to each PC

1. Download `FileAuditAgent.exe` from the latest Actions run
2. Copy it to `C:\Program Files\FileAudit\` on each PC
3. Press `Win + R` → `shell:startup` → Enter
4. Right-click → **New → Shortcut** → point to the exe

The agent now runs on every boot and reports to the server.

---

## 🔐 Firewall Setup

On the **server PC**, allow inbound on port 5000:

**Windows:**
```
Control Panel → Windows Defender Firewall → Advanced Settings
→ Inbound Rules → New Rule → Port → TCP 5000 → Allow
```

**macOS:**
```
System Settings → Network → Firewall → Options → allow Python
```

---

## 🖥️ Using the Dashboard

| Control | What it does |
|---------|--------------|
| **Machine** dropdown | Filter events by source PC |
| **Event** dropdown | Filter by `created`, `modified`, `moved`, `opened`, `deleted` |
| **Office only** checkbox | Show only Excel/Word/PPT/PDF/CSV events |
| **Search box** | Substring search in paths and usernames |
| **Export CSV** | Save all events to a file |
| **Clear DB** | Delete all events (asks confirmation) |

Amber-highlighted rows = office file create/move/open events.

---

## 📊 Event Types

| Event | Trigger |
|-------|---------|
| `created` | New file appears (includes files copied in) |
| `modified` | File contents changed / saved |
| `moved` | File renamed or moved to a new location |
| `deleted` | File removed |
| `opened` | Process opened the file (polled every 3s) |
| `heartbeat` | Agent is alive |

**Note:** Copy detection works by catching the `created` event at the destination folder. Combined with the source's `opened` event, you can reconstruct copy chains.

---

## 🛠️ Development

### Project structure

```
file-audit/
├── audit_app.py               # Main app (GUI + server)
├── agent.py                   # Remote agent
├── requirements.txt
├── .gitignore
├── README.md
└── .github/
    └── workflows/
        └── build.yml          # Auto-build pipeline
```

### Local development

```bash
python -m venv .venv
source .venv/bin/activate       # Mac/Linux
# .venv\Scripts\activate        # Windows
pip install -r requirements.txt
python audit_app.py
```

### Building standalone executables

**Windows:**
```bat
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name LANFileAudit audit_app.py
pyinstaller --noconfirm --onefile --noconsole --name FileAuditAgent agent.py
```

**macOS:**
```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "LAN File Audit" audit_app.py
```

Or push to GitHub — Actions builds them automatically.

---

## 🐛 Troubleshooting

| Problem | Fix |
|---------|-----|
| App won't start (missing tkinter) | `brew install python-tk@3.14` (Mac) |
| `Address already in use` port 5000 | macOS AirPlay uses 5000. Change `server_port` to 5001 in `config.json` |
| Agent says "Connection refused" | Wrong server IP, or server not running |
| No events appear | Watched folders don't exist, or files not saved inside them |
| macOS blocks the app | Right-click → Open → Open (for unsigned apps) |
| Windows Defender deletes exe | Whitelist it (common PyInstaller false positive) |
| `psutil.AccessDenied` warnings | Grant Full Disk Access: System Settings → Privacy → Full Disk Access |

---

## ⚠️ Limitations

- **Not a DLP tool** — this logs events, it does not block file operations
- **`opened` events are polled** — very short reads (<3 s) may be missed
- **No encryption on the wire** — events travel as plain HTTP on your LAN (fine for trusted networks)
- **Single-file SQLite** — suitable up to ~1 million events; consider Postgres for larger scale
- **Copy detection** — reconstructs copy events from create + open, not a kernel-level hook

For enterprise/compliance requirements (tamper-proof logs, retention policies, real-time alerts), consider commercial tools like Netwrix Auditor or ManageEngine ADAudit Plus.

---

## 🗺️ Roadmap

- [ ] System tray icon + desktop notifications
- [ ] Email / Telegram alerts on rules ("alert if .xlsx leaves folder X")
- [ ] Rules engine — conditional alerts with whitelists
- [ ] Password protection for the dashboard
- [ ] PostgreSQL backend for high-volume deployments
- [ ] Web dashboard (browser alternative to desktop GUI)

---

## 📜 License

MIT License — free to use, modify, and distribute.

---

## 🙏 Credits

Built with:
- [Flask](https://flask.palletsprojects.com/) — HTTP server
- [Watchdog](https://github.com/gorakhargosh/watchdog) — filesystem events
- [psutil](https://github.com/giampaolo/psutil) — process/file handle inspection
- [Tkinter](https://docs.python.org/3/library/tkinter.html) — desktop UI
- [PyInstaller](https://pyinstaller.org/) — standalone builds

---

## 📬 Contact

**Author:** Khajadaud Jamadar  
**Repository:** [github.com/khajadaudjamadar/file-audit](https://github.com/khajadaudjamadar/file-audit)

For issues, bugs, or feature requests — please open an [issue](https://github.com/khajadaudjamadar/file-audit/issues).
