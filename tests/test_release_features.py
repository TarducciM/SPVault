"""Cartelle nuove, pianificazione che sopravvive agli spegnimenti, lingua dall'installer,
barra di avanzamento."""
import xml.etree.ElementTree as ET

import spvault as spb
from conftest import Harness
from fakes import SITE

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def items(*ids):
    return [{"id": i, "name": f"cartella {i}", "size": 1, "folder": True} for i in ids]


# --- cartelle nuove

def test_first_listing_marks_nothing_as_new():
    cfg = dict(spb.DEFAULTS, known_items=[], selection=[])
    assert spb.merge_items(cfg, items("A", "B")) == []
    assert not any(spb.is_new(i) for i in cfg["known_items"])


def test_new_folder_is_reported_and_added_to_the_selection():
    cfg = dict(spb.DEFAULTS, selection=["A"])
    spb.merge_items(cfg, items("A", "B"))
    new = spb.merge_items(cfg, items("A", "B", "C"))
    assert [i["id"] for i in new] == ["C"]
    assert cfg["selection"] == ["A", "C"]
    assert [spb.is_new(i) for i in cfg["known_items"]] == [False, False, True]
    spb.merge_items(cfg, items("A", "B", "C"))  # alla lettura dopo non è più "comparsa ora"...
    assert spb.is_new(cfg["known_items"][2])     # ...ma resta segnata come nuova per 7 giorni


def test_new_folder_is_not_added_when_the_option_is_off_or_nothing_is_selected():
    cfg = dict(spb.DEFAULTS, selection=["A"], include_new=False)
    spb.merge_items(cfg, items("A"))
    spb.merge_items(cfg, items("A", "B"))
    assert cfg["selection"] == ["A"]
    cfg = dict(spb.DEFAULTS, selection=[])
    spb.merge_items(cfg, items("A"))
    spb.merge_items(cfg, items("A", "B"))
    assert cfg["selection"] == []


def test_deleted_folder_leaves_the_selection():
    cfg = dict(spb.DEFAULTS, selection=["A", "B"])
    spb.merge_items(cfg, items("A", "B"))
    spb.merge_items(cfg, items("A"))
    assert cfg["selection"] == ["A"]


def test_scheduled_backup_includes_a_folder_created_since_the_last_run(bk: Harness, monkeypatch):
    popups = []
    monkeypatch.setattr(spb, "message_box", popups.append)
    spb.save_config(dict(bk.cfg, known_items=[], selection=["A"]))
    assert spb.run_scheduled() == 0
    bk.server.add("N", "11. NUOVA CARTELLA", "ROOT", "folder")
    bk.server.add("n1", "dentro.psd", "N", content=b"nuovo")
    assert spb.run_scheduled() == 0
    assert (bk.current / "11. NUOVA CARTELLA" / "dentro.psd").read_bytes() == b"nuovo"
    assert "N" in spb.load_config()["selection"]
    log = spb.SCHEDULED_LOG.read_text(encoding="utf-8")
    assert "Nuova cartella su SharePoint: 11. NUOVA CARTELLA (aggiunta al backup)" in log
    assert popups == []


# --- pianificazione

def test_scheduled_task_survives_shutdowns():
    task = ET.fromstring(spb.task_xml(r"C:\Program Files\x\SPVault.exe", "--run", "07:30")
                         .replace('encoding="UTF-16"', ""))
    setting = lambda name: task.find(f"t:Settings/t:{name}", NS).text  # noqa: E731
    assert setting("StartWhenAvailable") == "true"          # orario saltato: parte appena possibile
    assert setting("DisallowStartIfOnBatteries") == "false"
    assert setting("StopIfGoingOnBatteries") == "false"
    assert setting("ExecutionTimeLimit") == "PT0S"          # nessun limite di durata
    assert task.find("t:Triggers/t:CalendarTrigger/t:StartBoundary", NS).text.endswith("T07:30:00")
    assert task.find("t:Triggers/t:CalendarTrigger/t:ScheduleByDay/t:DaysInterval", NS).text == "1"
    assert task.find("t:Actions/t:Exec/t:Command", NS).text == r"C:\Program Files\x\SPVault.exe"
    assert task.find("t:Actions/t:Exec/t:Arguments", NS).text == "--run"
    assert task.find("t:Principals/t:Principal/t:LogonType", NS).text == "InteractiveToken"


def test_task_xml_escapes_paths():
    xml = spb.task_xml(r"C:\A & B\<x>.exe", '"C:\\s p.py" --run', "13:00")
    assert r"C:\A &amp; B\&lt;x&gt;.exe" in xml
    ET.fromstring(xml.replace('encoding="UTF-16"', ""))


# --- lingua scelta nell'installer

def test_installer_language_applies_once_then_the_window_choice_wins(monkeypatch):
    monkeypatch.setattr(spb, "installer_language", lambda: "en")
    cfg = spb.load_config()
    assert cfg["language"] == "en"
    spb.save_config(dict(cfg, language="it"))     # poi l'utente sceglie italiano nella finestra
    assert spb.load_config()["language"] == "it"
    monkeypatch.setattr(spb, "installer_language", lambda: "auto")  # reinstallazione con altra scelta
    assert spb.load_config()["language"] == "auto"


# --- finestra

def test_progress_bar_scale_is_reset_for_every_job(server, make_app):
    from test_gui import wait_jobs
    app = make_app()
    wait_jobs(app, 1)
    assert float(app.progress.cget("maximum")) == 1        # a fine lavoro: barra piena, scala 0..1
    app._set_running(True, "prova")
    assert str(app.progress.cget("mode")) == "indeterminate"
    assert float(app.progress.cget("maximum")) == 100      # prima saltava da un estremo all'altro
    app._set_running(False)


def test_new_folder_is_shown_in_the_window(server, make_app):
    from test_gui import wait_jobs
    app = make_app(selection=["A"])
    wait_jobs(app, 1)
    server.add("N", "11. NUOVA CARTELLA", "ROOT", "folder")
    app.start_connect()
    wait_jobs(app, 2)
    labels = [w.cget("text") for w in app.items_frame.winfo_children()]
    assert any(t.startswith("11. NUOVA CARTELLA") and t.endswith("- NUOVA") for t in labels), labels
    log = app.log_box.get("1.0", "end")
    assert "Nuova cartella su SharePoint: 11. NUOVA CARTELLA (aggiunta al backup)" in log
    assert app.item_vars["N"].get() and "N" in spb.load_config()["selection"]
    app.var_include_new.set(False)
    app._save()
    assert spb.load_config()["include_new"] is False


def test_site_url_used_by_the_window_tests_is_the_fake_one():
    assert SITE.startswith("https://t.sharepoint.com")
