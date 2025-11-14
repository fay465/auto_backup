"""
Python Backup Prototype

"""

import os
import sys
import json
import time
import hashlib
import threading
import datetime as dt
import zipfile
import subprocess, shutil, tempfile
import sqlite3
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

CONFIG_FILE = "backup_config.json"
LOG_FILE = "backup_log.csv"
CREDENTIALS_FILE = "credentials.json"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def timestamp() -> str:
    return dt.datetime.now().strftime('%Y%m%d-%H%M%S')


def safe_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ('-', '_', '.', ' ')).strip()


def ensure_log_header():
    if not Path(LOG_FILE).exists():
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("date_time,source,zip_path,zip_size,checksum,drive_file_id,status,message\n")


def append_log(row: dict):
    ensure_log_header()
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(
            f"{row.get('date_time','')},{row.get('source','')},{row.get('zip_path','')},{row.get('zip_size','')},"
            f"{row.get('checksum','')},{row.get('drive_file_id','')},{row.get('status','')},{row.get('message','')}\n"
        )
      
      
SUPPORTED_EXTS = {".sqlite", ".db", ".duckdb", ".mdf"}

def detect_engine_from_path(p: Path) -> str:
    ext = p.suffix.lower()
    if ext in (".sqlite", ".db"): return "sqlite"
    if ext == ".duckdb": return "duckdb"
    if ext == ".mdf": return "sqllocaldb"
    return "other"

def get_drive_client():
    gauth = GoogleAuth()
    if os.path.exists(CREDENTIALS_FILE):
        gauth.LoadCredentialsFile(CREDENTIALS_FILE)
    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
        gauth.SaveCredentialsFile(CREDENTIALS_FILE)
    elif gauth.access_token_expired:
        gauth.Refresh()
        gauth.SaveCredentialsFile(CREDENTIALS_FILE)
    else:
        gauth.Authorize()
    return GoogleDrive(gauth)


def upload_to_drive(drive: GoogleDrive, file_path: Path, drive_folder_id: str) -> str:
    metadata = {"title": file_path.name}
    if drive_folder_id:
        metadata["parents"] = [{"id": drive_folder_id}]
    gfile = drive.CreateFile(metadata)
    gfile.SetContentFile(str(file_path))
    gfile.Upload()
    return gfile["id"]

def make_backup_zip(source_path: Path, local_dest_dir: Path) -> Path:
    if not source_path.exists():
        raise FileNotFoundError(f"Origen no encontrado: {source_path}")
    local_dest_dir.mkdir(parents=True, exist_ok=True)

    base = safe_name(source_path.stem if source_path.is_file() else source_path.name)
    out_name = f"backup-{base}-{timestamp()}.zip"
    out_path = local_dest_dir / out_name

    with zipfile.ZipFile(out_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        if source_path.is_file():
            zf.write(source_path, arcname=source_path.name)
        else:
            for root, _, files in os.walk(source_path):
                root_path = Path(root)
                for fn in files:
                    fp = root_path / fn
                    rel = fp.relative_to(source_path)
                    zf.write(fp, arcname=str(rel))
    return out_path

def load_config() -> dict:
    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "source_path": "",
        "local_dest": str(Path.cwd() / "backups"),
        "drive_folder_id": "",
        "interval_minutes": 60,
    }


def save_config(cfg: dict):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

class BackupScheduler:
    def __init__(self, ui_callback):
        self._thread = None
        self._stop = threading.Event()
        self.ui_callback = ui_callback

    def start(self, cfg: dict):
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(cfg,), daemon=True)
        self._thread.start()
        self.ui_callback("Scheduler iniciado")

    def stop(self):
        if self._thread and self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=2)
            self.ui_callback("Scheduler detenido")
        self._thread = None

    def _run(self, cfg: dict):
        interval = max(1, int(cfg.get("interval_minutes", 60))) * 60
        while not self._stop.is_set():
            try:
                do_backup(cfg, self.ui_callback)
            except Exception as e:
                self.ui_callback(f"Error en ejecución programada: {e}")
            for _ in range(interval):
                if self._stop.is_set():
                    break
                time.sleep(1)

def do_backup(cfg: dict, log_fn=print):
    src = Path(cfg["source_path"]).expanduser()
    dst_dir = Path(cfg["local_dest"]).expanduser()
    drive_id = cfg.get("drive_folder_id", "").strip()

    start = dt.datetime.now()
    try:
        zip_path = make_backup_zip(src, dst_dir)
        checksum = sha256_file(zip_path)
        size = zip_path.stat().st_size
        log_fn(f"ZIP creado: {zip_path} ({size} bytes), sha256={checksum}")

        drive = get_drive_client()
        file_id = upload_to_drive(drive, zip_path, drive_id)
        log_fn(f"Subido a Drive, file_id={file_id}")

        append_log({
            "date_time": start.isoformat(timespec='seconds'),
            "source": str(src),
            "zip_path": str(zip_path),
            "zip_size": size,
            "checksum": checksum,
            "drive_file_id": file_id,
            "status": "OK",
            "message": "",
        })
    except Exception as e:
        append_log({
            "date_time": start.isoformat(timespec='seconds'),
            "source": str(src),
            "zip_path": "",
            "zip_size": 0,
            "checksum": "",
            "drive_file_id": "",
            "status": "ERROR",
            "message": str(e),
        })
        raise

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Backup Prototype – Tkinter + Google Drive")
        self.geometry("760x520")
        self.resizable(False, False)

        self.cfg = load_config()
        self.scheduler = BackupScheduler(self.log)

        self._build()

    def _build(self):
        pad = {"padx": 8, "pady": 6}

        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True)
        
        frm.grid_columnconfigure(1, weight=1)
        self.resizable(True, False)
        self.minsize(820, 480)

        ttk.Label(frm, text="Origen (archivo o carpeta):").grid(row=0, column=0, sticky=tk.W, **pad)
        self.var_source = tk.StringVar(value=self.cfg.get("source_path", ""))
        e_source = ttk.Entry(frm, textvariable=self.var_source, width=70)
        e_source.grid(row=0, column=1, sticky=tk.W, **pad)
        ttk.Button(frm, text="Buscar…", command=self.choose_source).grid(row=0, column=2, **pad)

        ttk.Label(frm, text="Carpeta local para ZIPs:").grid(row=1, column=0, sticky=tk.W, **pad)
        self.var_local = tk.StringVar(value=self.cfg.get("local_dest", str(Path.cwd() / "backups")))
        e_local = ttk.Entry(frm, textvariable=self.var_local, width=70)
        e_local.grid(row=1, column=1, sticky=tk.W, **pad)
        ttk.Button(frm, text="Buscar…", command=self.choose_local).grid(row=1, column=2, **pad)

        ttk.Label(frm, text="Google Drive Folder ID (opcional):").grid(row=2, column=0, sticky=tk.W, **pad)
        self.var_drive = tk.StringVar(value=self.cfg.get("drive_folder_id", ""))
        e_drive = ttk.Entry(frm, textvariable=self.var_drive, width=70)
        e_drive.grid(row=2, column=1, sticky=tk.W, **pad)

        ttk.Label(frm, text="Intervalo automático (minutos):").grid(row=3, column=0, sticky=tk.W, **pad)
        self.var_interval = tk.StringVar(value=str(self.cfg.get("interval_minutes", 60)))
        e_interval = ttk.Entry(frm, textvariable=self.var_interval, width=10)
        e_interval.grid(row=3, column=1, sticky=tk.W, **pad)

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=3, sticky=tk.W, **pad)
        ttk.Button(btns, text="Guardar configuración", command=self.save_cfg).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Ejecutar ahora", command=self.run_now).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Iniciar automático", command=self.start_sched).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Detener automático", command=self.stop_sched).pack(side=tk.LEFT, padx=4)

        self.txt = tk.Text(frm, height=16, width=100, state=tk.DISABLED)
        self.txt.grid(row=5, column=0, columnspan=3, sticky=tk.W, **pad)

        ttk.Label(frm, text=f"Config: {CONFIG_FILE} | Log: {LOG_FILE}").grid(row=6, column=0, columnspan=3, sticky=tk.W, **pad)

    def choose_source(self):
        path = filedialog.askopenfilename(title="Seleccionar archivo para backup")
        if not path:
            path = filedialog.askdirectory(title="Seleccionar carpeta para backup")
        if path:
            self.var_source.set(path)

    def choose_local(self):
        path = filedialog.askdirectory(title="Seleccionar carpeta local para ZIPs")
        if path:
            self.var_local.set(path)

    def save_cfg(self):
        try:
            cfg = {
                "source_path": self.var_source.get().strip(),
                "local_dest": self.var_local.get().strip(),
                "drive_folder_id": self.var_drive.get().strip(),
                "interval_minutes": int(self.var_interval.get().strip() or "60"),
            }
            save_config(cfg)
            self.cfg = cfg
            messagebox.showinfo("OK", "Configuración guardada")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def run_now(self):
        self.save_cfg()
        def job():
            try:
                self.log("Ejecutando backup…")
                do_backup(self.cfg, self.log)
                self.log("Backup completado")
            except Exception as e:
                self.log(f"ERROR: {e}")
        threading.Thread(target=job, daemon=True).start()

    def start_sched(self):
        self.save_cfg()
        self.scheduler.start(self.cfg)

    def stop_sched(self):
        self.scheduler.stop()

    def log(self, msg: str):
        ts = dt.datetime.now().strftime('%H:%M:%S')
        self.txt.configure(state=tk.NORMAL)
        self.txt.insert(tk.END, f"[{ts}] {msg}\n")
        self.txt.see(tk.END)
        self.txt.configure(state=tk.DISABLED)


if __name__ == "__main__":
    App().mainloop()
