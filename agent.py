import os, time, socket, getpass, threading, queue, requests
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ─── EDIT THESE BEFORE BUILDING ───────────────────────────
SERVER  = "http://192.168.1.50:5000"   # ← Replace with your server PC's IP
FOLDERS = [
    os.path.expandvars(r"%USERPROFILE%\Documents"),
    os.path.expandvars(r"%USERPROFILE%\Desktop"),
    r"C:\Shared",
]
# ──────────────────────────────────────────────────────────

EXTS = (".xlsx",".xls",".xlsm",".docx",".doc",".pptx",".ppt",".csv",".pdf")
MACHINE  = socket.gethostname()
USERNAME = getpass.getuser()
Q = queue.Queue()

def is_office(p): return any((p or '').lower().endswith(e) for e in EXTS)

def in_watch(p):
    a = os.path.abspath(p).lower()
    return any(a.startswith(os.path.abspath(f).lower()) for f in FOLDERS)

def push(t, src=None, dst=None):
    if src and not in_watch(src) and not (dst and in_watch(dst)): return
    try: size = os.path.getsize(dst or src)
    except Exception: size = 0
    Q.put({"timestamp": datetime.now().isoformat(timespec='seconds'),
           "machine": MACHINE, "user": USERNAME, "event_type": t,
           "src_path": src, "dest_path": dst, "file_size": size,
           "process": None, "is_office": is_office(src) or is_office(dst)})

class H(FileSystemEventHandler):
    def on_created(self, e):
        if not e.is_directory: push("created", e.src_path)
    def on_modified(self, e):
        if not e.is_directory: push("modified", e.src_path)
    def on_deleted(self, e):
        if not e.is_directory: push("deleted", e.src_path)
    def on_moved(self, e):
        if not e.is_directory: push("moved", e.src_path, e.dest_path)

def sender():
    while True:
        ev = Q.get()
        try: requests.post(SERVER + "/api/event", json=ev, timeout=5)
        except Exception as e: print("[!]", e)
        finally: Q.task_done()

if __name__ == "__main__":
    threading.Thread(target=sender, daemon=True).start()
    obs = Observer()
    for f in FOLDERS:
        if os.path.isdir(f):
            obs.schedule(H(), f, recursive=True)
            print("[+] watching", f)
        else:
            print("[!] missing:", f)
    obs.start()
    print(f"[*] {MACHINE} -> {SERVER}")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: obs.stop()