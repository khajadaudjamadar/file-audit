#!/usr/bin/env python3
"""LAN File Audit — Desktop App (Tkinter + embedded Flask collector)."""
import os, sys, json, time, sqlite3, socket, getpass, threading, queue
import csv
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from flask import Flask, request, jsonify
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

try:
    import psutil
except ImportError:
    psutil = None

APP_DIR     = Path(__file__).parent
CONFIG_PATH = APP_DIR / "config.json"
DB_PATH     = APP_DIR / "audit.db"

DEFAULT_CONFIG = {
    "server_port": 5000,
    "watch_folders": [str(Path.home() / "Desktop" / "AuditTest")],
    "office_extensions": [".xlsx",".xls",".xlsm",".docx",".doc",".pptx",".ppt",".csv",".pdf"],
    "access_poll_seconds": 3,
    "heartbeat_seconds": 30,
}

def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
    cfg = json.loads(CONFIG_PATH.read_text())
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg

CFG = load_config()
OFFICE_EXTS = set(e.lower() for e in CFG["office_extensions"])
MACHINE  = socket.gethostname()
USERNAME = getpass.getuser()

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            machine   TEXT,
            user      TEXT,
            event_type TEXT,
            src_path  TEXT,
            dest_path TEXT,
            file_size INTEGER DEFAULT 0,
            process   TEXT,
            is_office INTEGER DEFAULT 0
        )''')

def insert_event(d):
    with db() as conn:
        conn.execute('''INSERT INTO events
          (timestamp,machine,user,event_type,src_path,dest_path,file_size,process,is_office)
          VALUES (?,?,?,?,?,?,?,?,?)''',
          (d.get('timestamp', datetime.now().isoformat()),
           d.get('machine'), d.get('user'), d.get('event_type'),
           d.get('src_path'), d.get('dest_path'), d.get('file_size', 0),
           d.get('process'), 1 if d.get('is_office') else 0))

flask_app = Flask(__name__)

@flask_app.route('/api/event', methods=['POST'])
def api_event():
    insert_event(request.get_json(force=True))
    return jsonify({"ok": True})

@flask_app.route('/api/ping')
def api_ping():
    return jsonify({"ok": True, "machine": MACHINE})

def run_flask():
    flask_app.run(host='0.0.0.0', port=CFG["server_port"],
                  threaded=True, use_reloader=False, debug=False)

EVENT_QUEUE = queue.Queue()

def is_office(path):
    return any((path or '').lower().endswith(e) for e in OFFICE_EXTS)

def in_watch(path):
    p = os.path.abspath(path).lower()
    return any(p.startswith(os.path.abspath(f).lower()) for f in CFG["watch_folders"])

def safe_size(path):
    try: return os.path.getsize(path)
    except Exception: return 0

def push(event_type, src_path=None, dest_path=None, process=None, user=None):
    if src_path and not in_watch(src_path) and not (dest_path and in_watch(dest_path)):
        return
    EVENT_QUEUE.put({
        "timestamp": datetime.now().isoformat(timespec='seconds'),
        "machine": MACHINE, "user": user or USERNAME,
        "event_type": event_type, "src_path": src_path,
        "dest_path": dest_path,
        "file_size": safe_size(dest_path or src_path or ""),
        "process": process,
        "is_office": is_office(src_path) or is_office(dest_path),
    })

class Handler(FileSystemEventHandler):
    def on_created(self, e):
        if not e.is_directory: push("created", e.src_path)
    def on_modified(self, e):
        if not e.is_directory: push("modified", e.src_path)
    def on_deleted(self, e):
        if not e.is_directory: push("deleted", e.src_path)
    def on_moved(self, e):
        if not e.is_directory: push("moved", e.src_path, e.dest_path)

def local_collector_loop():
    while True:
        ev = EVENT_QUEUE.get()
        try: insert_event(ev)
        except Exception as ex: print("[!] insert failed:", ex)
        finally: EVENT_QUEUE.task_done()

def access_poller():
    if psutil is None: return
    seen = set()
    while True:
        try:
            for proc in psutil.process_iter(['pid','name','username']):
                try:
                    for f in proc.open_files():
                        path = f.path
                        if not is_office(path) or not in_watch(path): continue
                        key = (proc.pid, path)
                        if key in seen: continue
                        seen.add(key)
                        push("opened", path,
                             process=proc.info.get('name'),
                             user=proc.info.get('username') or USERNAME)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if len(seen) > 20000: seen.clear()
        except Exception as e:
            print("[!] poller:", e)
        time.sleep(CFG["access_poll_seconds"])

def heartbeat_loop():
    while True:
        push("heartbeat")
        time.sleep(CFG["heartbeat_seconds"])

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("🛡️  LAN File Audit")
        self.root.geometry("1100x650")
        self.root.minsize(900, 500)
        self._style()
        self._topbar()
        self._cards()
        self._filters()
        self._table()
        self._statusbar()
        self.observer = None
        self.started = False
        self.start_engine()
        self.refresh()

    def _style(self):
        s = ttk.Style()
        try: s.theme_use("clam")
        except Exception: pass
        s.configure("TFrame", background="#0f172a")
        s.configure("Card.TFrame", background="#1e293b")
        s.configure("TLabel", background="#0f172a", foreground="#e2e8f0")
        s.configure("CardLabel.TLabel", background="#1e293b",
                    foreground="#94a3b8", font=("Helvetica", 10))
        s.configure("CardValue.TLabel", background="#1e293b",
                    foreground="#e2e8f0", font=("Helvetica", 22, "bold"))
        s.configure("Title.TLabel", background="#1e293b",
                    foreground="#e2e8f0", font=("Helvetica", 14, "bold"))
        s.configure("Treeview", background="#1e293b", foreground="#e2e8f0",
                    fieldbackground="#1e293b", rowheight=24, borderwidth=0)
        s.configure("Treeview.Heading", background="#0b1220",
                    foreground="#94a3b8", font=("Helvetica", 10, "bold"))
        s.map("Treeview", background=[("selected", "#334155")])

    def _topbar(self):
        bar = ttk.Frame(self.root, style="Card.TFrame", padding=(16, 10))
        bar.pack(fill="x")
        ttk.Label(bar, text="🛡️  LAN File Audit", style="Title.TLabel").pack(side="left")
        self.lbl_server = ttk.Label(bar, text="", style="CardLabel.TLabel")
        self.lbl_server.pack(side="right")

    def _cards(self):
        wrap = ttk.Frame(self.root, padding=(16, 12, 16, 6))
        wrap.pack(fill="x")
        self.card_total  = self._card(wrap, "Total Events", 0)
        self.card_today  = self._card(wrap, "Today",        1)
        self.card_office = self._card(wrap, "Office Files", 2)

    def _card(self, parent, label, col):
        f = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
        f.grid(row=0, column=col, sticky="nsew", padx=(0, 10))
        parent.columnconfigure(col, weight=1)
        ttk.Label(f, text=label.upper(), style="CardLabel.TLabel").pack(anchor="w")
        v = ttk.Label(f, text="0", style="CardValue.TLabel")
        v.pack(anchor="w")
        return v

    def _filters(self):
        bar = ttk.Frame(self.root, padding=(16, 4, 16, 8))
        bar.pack(fill="x")
        ttk.Label(bar, text="Machine:").pack(side="left")
        self.cb_machine = ttk.Combobox(bar, values=["All"], state="readonly", width=18)
        self.cb_machine.set("All")
        self.cb_machine.pack(side="left", padx=(4, 12))
        self.cb_machine.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(bar, text="Event:").pack(side="left")
        self.cb_type = ttk.Combobox(bar,
            values=["All","created","modified","deleted","moved","opened","heartbeat"],
            state="readonly", width=12)
        self.cb_type.set("All")
        self.cb_type.pack(side="left", padx=(4, 12))
        self.cb_type.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.var_office = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Office only", variable=self.var_office,
                        command=self.refresh).pack(side="left", padx=(0, 12))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.var_q = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.var_q, width=28)
        e.pack(side="left", padx=(4, 12))
        e.bind("<KeyRelease>", lambda ev: self.refresh())
        ttk.Button(bar, text="Export CSV", command=self.export).pack(side="right")
        ttk.Button(bar, text="Clear DB",   command=self.clear).pack(side="right", padx=(0, 6))

    def _table(self):
        wrap = ttk.Frame(self.root, padding=(16, 0, 16, 8))
        wrap.pack(fill="both", expand=True)
        cols = ("time","machine","user","event","src","dest","process")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        heads = {"time":"Time","machine":"Machine","user":"User","event":"Event",
                 "src":"Source","dest":"Destination","process":"Process"}
        widths = {"time":150,"machine":130,"user":110,"event":90,
                  "src":280,"dest":280,"process":120}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor="w",
                             stretch=(c in ("src","dest")))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("odd",   background="#1e293b")
        self.tree.tag_configure("even",  background="#182234")
        self.tree.tag_configure("alert", background="#3b2a00", foreground="#fbbf24")

    def _statusbar(self):
        self.var_status = tk.StringVar(value="Starting…")
        sb = ttk.Frame(self.root, style="Card.TFrame", padding=(16, 6))
        sb.pack(fill="x", side="bottom")
        ttk.Label(sb, textvariable=self.var_status, style="CardLabel.TLabel").pack(side="left")

    def start_engine(self):
        if self.started: return
        threading.Thread(target=run_flask,           daemon=True).start()
        threading.Thread(target=local_collector_loop,daemon=True).start()
        threading.Thread(target=access_poller,       daemon=True).start()
        threading.Thread(target=heartbeat_loop,      daemon=True).start()
        self.observer = Observer()
        started = []
        for folder in CFG["watch_folders"]:
            if os.path.isdir(folder):
                self.observer.schedule(Handler(), folder, recursive=True)
                started.append(folder)
        self.observer.start()
        self.started = True
        ip = self._lan_ip()
        self.lbl_server.config(
            text=f"Server: http://{ip}:{CFG['server_port']}  ·  Watching {len(started)} folder(s)")

    def _lan_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]; s.close(); return ip
        except Exception:
            return "127.0.0.1"

    def refresh(self):
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            with db() as conn:
                total   = conn.execute('SELECT COUNT(*) c FROM events').fetchone()['c']
                today_c = conn.execute('SELECT COUNT(*) c FROM events WHERE timestamp LIKE ?',
                                       (today+'%',)).fetchone()['c']
                office_c= conn.execute('SELECT COUNT(*) c FROM events WHERE is_office=1').fetchone()['c']
                machines = [r['machine'] for r in
                            conn.execute('SELECT DISTINCT machine FROM events ORDER BY machine')
                            if r['machine']]
                where, params = [], []
                m = self.cb_machine.get()
                if m and m != "All": where.append('machine=?'); params.append(m)
                t = self.cb_type.get()
                if t and t != "All": where.append('event_type=?'); params.append(t)
                if self.var_office.get(): where.append('is_office=1')
                q = self.var_q.get().strip()
                if q:
                    where.append('(src_path LIKE ? OR dest_path LIKE ? OR user LIKE ?)')
                    params += [f'%{q}%']*3
                sql = 'SELECT * FROM events'
                if where: sql += ' WHERE ' + ' AND '.join(where)
                sql += ' ORDER BY id DESC LIMIT 500'
                rows = conn.execute(sql, params).fetchall()

            self.card_total.config(text=str(total))
            self.card_today.config(text=str(today_c))
            self.card_office.config(text=str(office_c))
            vals = ["All"] + machines
            if list(self.cb_machine["values"]) != vals:
                self.cb_machine["values"] = vals

            self.tree.delete(*self.tree.get_children())
            for i, r in enumerate(rows):
                ts = (r["timestamp"] or "").replace("T"," ")[:19]
                tags = ["odd" if i % 2 else "even"]
                if r["is_office"] and r["event_type"] in ("created","moved","opened"):
                    tags.append("alert")
                self.tree.insert("", "end", tags=tags, values=(
                    ts, r["machine"] or "", r["user"] or "",
                    r["event_type"] or "", r["src_path"] or "",
                    r["dest_path"] or "", r["process"] or ""))
            self.var_status.set(
                f"Showing {len(rows)} rows  ·  {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            self.var_status.set(f"Refresh error: {e}")
        self.root.after(2500, self.refresh)

    def export(self):
        p = filedialog.asksaveasfilename(defaultextension=".csv",
                filetypes=[("CSV","*.csv")],
                initialfile=f"audit_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        if not p: return
        with db() as conn:
            rows = conn.execute('SELECT * FROM events ORDER BY id DESC').fetchall()
        with open(p,"w",newline="",encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id","timestamp","machine","user","event_type",
                        "src_path","dest_path","file_size","process","is_office"])
            for r in rows: w.writerow([r[k] for k in r.keys()])
        messagebox.showinfo("Export", f"Exported {len(rows)} rows to:\n{p}")

    def clear(self):
        if not messagebox.askyesno("Clear DB","Delete all events permanently?"): return
        with db() as conn: conn.execute('DELETE FROM events')
        self.refresh()

    def on_close(self):
        try:
            if self.observer: self.observer.stop(); self.observer.join(timeout=1)
        except Exception: pass
        self.root.destroy()

def main():
    init_db()
    for f in CFG["watch_folders"]:
        try: os.makedirs(f, exist_ok=True)
        except Exception: pass
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
