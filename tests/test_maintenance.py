"""Pulizia delle versioni vecchie (anche in sola lettura) ed esito dell'ultimo backup automatico."""
import os
import stat
import time
import types

import spvault as spb
from conftest import Harness

REAL_REFRESH = spb.App._refresh_schedule  # make_app la sostituisce: qui serve quella vera


def read_only(path):
    """Come le cartelle che OneDrive marca in sola lettura: Windows non le fa eliminare."""
    os.chmod(path, stat.S_IREAD)


def test_remove_tree_deletes_read_only_folders(tmp_path):
    folder = tmp_path / "2026-09-22_r3"
    (folder / "3. ONLINE").mkdir(parents=True)
    (folder / "3. ONLINE" / "file.psd").write_text("x")
    read_only(folder / "3. ONLINE" / "file.psd")
    read_only(folder / "3. ONLINE")
    spb.remove_tree(folder)
    assert not folder.exists()


def test_remove_empty_dir(tmp_path):
    empty = tmp_path / "vuota"
    empty.mkdir()
    read_only(empty)
    assert spb.remove_empty_dir(empty) and not empty.exists()
    full = tmp_path / "piena"
    full.mkdir()
    (full / "f.txt").write_text("x")
    assert spb.remove_empty_dir(full) is False and full.exists()
    assert spb.remove_empty_dir(tmp_path / "inesistente") is False


def test_old_versions_are_pruned_even_when_read_only(bk: Harness):
    bk.run()
    old = bk.dest / spb.VERSIONS_DIR / "2020-01-01_r1" / "3. Projects" / "GAME47"
    old.mkdir(parents=True)
    (old / "vecchio.psd").write_text("x")
    read_only(old / "vecchio.psd")
    read_only(old)
    bk.server.modify("f3", b"nuovo")
    bk.run(keep_versions=1)
    assert not (bk.dest / spb.VERSIONS_DIR / "2020-01-01_r1").exists()
    assert not any("ERRORE eliminando" in line for line in bk.logs), bk.logs


# --- esito dell'ultimo backup automatico

def test_scheduled_run_records_its_result(bk: Harness, monkeypatch):
    monkeypatch.setattr(spb, "message_box", lambda text: None)
    spb.save_config(dict(bk.cfg, known_items=[], selection=["A"]))
    assert spb.run_scheduled() == 0
    last = spb.load_config()["last_scheduled"]
    assert last["ok"] is True and "VERIFICA OK" in last["text"] and last["when"] > 0


def test_failed_scheduled_run_is_recorded_too(bk: Harness, monkeypatch):
    shown = []
    monkeypatch.setattr(spb, "message_box", shown.append)
    monkeypatch.setattr(spb, "browser_login", lambda *a, **k: (_ for _ in ()).throw(spb.LoginRequired("scaduta")))
    spb.save_config(dict(bk.cfg, known_items=[], selection=["A"]))
    assert spb.run_scheduled() == 1
    last = spb.load_config()["last_scheduled"]
    assert last["ok"] is False and "scaduta" in last["text"]
    assert shown and "Connetti" in shown[0]


def test_window_shows_the_last_scheduled_result(server, make_app, monkeypatch):
    app = make_app(last_scheduled={"when": time.time(), "ok": True, "text": "VERIFICA OK: tutti i 12 file"})
    log = app.log_box.get("1.0", "end")
    assert "Ultimo backup automatico" in log and "VERIFICA OK: tutti i 12 file" in log
    monkeypatch.setattr(spb.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="", stderr=""))
    REAL_REFRESH(app)
    assert "(attivo)" in app.var_sched.get() and "ultimo automatico" in app.var_sched.get()
    assert "riuscito" in app.var_sched.get()


# --- file riscritti dalla sincronizzazione dopo la copia (tipico dei file Office)

def test_files_rewritten_by_the_sync_are_not_downloaded_again(bk: Harness):
    bk.run()
    copia = bk.current / "2. Projects" / "note.txt"
    copia.write_bytes(b"note con i metadati riscritti da SharePoint")  # come fa la sincronizzazione
    summary = bk.run()
    assert bk.server.downloads == [], bk.server.downloads
    assert "1 riscritti dalla sincronizzazione" in summary
    assert [r[0] for r in bk.manifest() if r[4].startswith("OK (riscritto")] == ["2. Projects/note.txt"]
    assert copia.read_bytes() == b"note con i metadati riscritti da SharePoint"  # non sovrascritto
    summary = bk.run()  # la volta dopo è un file normale: niente da segnalare
    assert bk.server.downloads == [] and "riscritti" not in summary


def test_a_file_changed_on_sharepoint_is_still_downloaded(bk: Harness):
    bk.run()
    (bk.current / "2. Projects" / "note.txt").write_bytes(b"riscritto dalla sincronizzazione")
    bk.server.modify("f3", b"contenuto nuovo")  # cambia anche su SharePoint: vince SharePoint
    bk.run()
    assert bk.server.downloads == ["f3"]
    assert (bk.current / "2. Projects" / "note.txt").read_bytes() == b"contenuto nuovo"


def test_a_deleted_local_file_is_still_downloaded(bk: Harness):
    bk.run()
    (bk.current / "2. Projects" / "note.txt").unlink()
    bk.run()
    assert bk.server.downloads == ["f3"]
