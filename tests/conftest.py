import os
import threading
import time
import tkinter as tk
from pathlib import Path

import pytest

import spvault as spb
from fakes import SITE, Server

REAL_SLEEP = time.sleep  # i test sostituiscono time.sleep con una funzione che non aspetta


@pytest.fixture(autouse=True)
def isolated_app_dir(tmp_path, monkeypatch):
    """Ogni test usa una sua cartella dati al posto di %LOCALAPPDATA%\\SPVault."""
    app = tmp_path / "appdata" / "SPVault"
    paths = {"APP_DIR": app, "PROFILE_DIR": app / "browser_profile", "TMP_DIR": app / "tmp",
             "CONFIG_FILE": app / "config.json", "LOCK_FILE": app / "backup.lock",
             "SCHEDULED_LOG": app / "scheduled_backup.log"}
    for name, value in paths.items():
        monkeypatch.setattr(spb, name, value)
    monkeypatch.setattr(spb.time, "sleep", lambda s: None)
    monkeypatch.setattr(spb, "installer_language", lambda: None)  # mai il registro vero del PC
    return app


@pytest.fixture(autouse=True)
def italian(monkeypatch):
    """I test controllano i testi originali in italiano, anche dove Windows è in inglese (CI):
    lingua attiva italiano e "auto" risolto come su un Windows italiano."""
    monkeypatch.setattr(spb, "LANG", "it")
    monkeypatch.setattr(spb, "windows_ui_language", lambda: 0x0410)


@pytest.fixture
def server(monkeypatch):
    srv = Server()
    srv.build_default_library()

    def fake_login(site, interactive, log):
        srv.logins.append(interactive)
        return [{"name": "FedAuth", "value": "x", "domain": "t.sharepoint.com", "path": "/"}], "Mozilla/5.0"

    monkeypatch.setattr(spb, "browser_login", fake_login)
    monkeypatch.setattr(spb.SharePoint, "_session", lambda self: srv)
    return srv


class Harness:
    """Esegue backup completi contro il server finto e ispeziona il risultato."""

    def __init__(self, server: Server, dest: Path):
        self.server, self.dest, self.logs = server, dest, []
        self.cfg = dict(spb.DEFAULTS, library_url=f"{SITE}/Documenti/Forms/AllItems.aspx?viewid=x",
                        dest=str(dest), selection=["A", "TOP"], keep_versions=2, online_only=True)

    @property
    def current(self) -> Path:
        return self.dest / spb.CURRENT_DIR

    def run(self, expect_complete=True, cancel=None, **overrides) -> str:
        self.server.downloads.clear()
        self.server.ranges.clear()
        self.logs.clear()
        summary, complete = spb.run_backup(dict(self.cfg, **overrides), self.logs.append,
                                           lambda done, total: None, cancel or threading.Event(),
                                           interactive_login=True)
        assert complete == expect_complete, summary
        return summary

    def tree(self, sub=spb.CURRENT_DIR) -> list[str]:
        base = self.dest / sub
        return sorted(p.relative_to(base).as_posix() for p in base.rglob("*")
                      if p.is_file() and p.name != "desktop.ini")

    def versions(self) -> list[str]:
        folder = self.dest / spb.VERSIONS_DIR
        return sorted(os.listdir(folder)) if folder.exists() else []

    def manifest(self) -> list[list[str]]:
        text = (self.dest / spb.MANIFEST).read_text(encoding="utf-8-sig")
        return [line.split(";") for line in text.splitlines()[1:]]

    def force_full_scan(self, delta_link=None):
        state = spb.State("D1", self.dest)
        state.set_meta("last_full_scan", 0)
        if delta_link:
            state.set_meta("delta_link", delta_link)
        state.db.commit()
        state.db.close()


@pytest.fixture
def bk(server, tmp_path) -> Harness:
    dest = tmp_path / "Backup Folder"
    dest.mkdir()
    (dest / "vecchio_backup.zip").write_bytes(b"zip")  # contenuto preesistente da non toccare
    return Harness(server, dest)


# --- finestra (test_gui.py, test_i18n.py)

@pytest.fixture
def root():
    for attempt in range(3):  # su Windows a volte Tk non legge i suoi file al primo colpo (antivirus)
        try:
            r = tk.Tk()
            break
        except tk.TclError as e:
            if attempt == 2:
                pytest.skip(f"nessun display: {e}")
            REAL_SLEEP(0.5)
    r.withdraw()
    yield r
    r.destroy()


def self_test() -> int:
    """spb.self_test() con gli stessi tentativi della fixture root: apre anche lei una finestra Tk."""
    for attempt in range(3):
        try:
            return spb.self_test()
        except tk.TclError:
            if attempt == 2:
                raise
            REAL_SLEEP(0.5)


@pytest.fixture
def popups(monkeypatch):
    """Registra gli avvisi a schermo invece di mostrarli."""
    calls = []
    for name in ("showerror", "showwarning", "showinfo"):
        monkeypatch.setattr(spb.messagebox, name, lambda *a, _n=name: calls.append((_n, *a)))
    return calls


@pytest.fixture
def make_app(root, monkeypatch, popups):
    monkeypatch.setattr(spb.App, "_refresh_schedule", lambda self: None)

    def make(**cfg):
        spb.save_config({**spb.DEFAULTS, "library_url": f"{SITE}/Documenti", **cfg})
        app = spb.App(root)
        app.statuses, app.finished = [], 0
        app.var_status.trace_add("write", lambda *_: app.statuses.append(app.var_status.get()))
        set_running = app._set_running

        def count_finished(running, title=""):
            app.finished += not running
            set_running(running, title)
        app._set_running = count_finished
        return app
    return make
