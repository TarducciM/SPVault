"""Lingua: traduzioni inglesi complete e coerenti, backup e finestra in inglese, scelta della lingua."""
import ast
import re
import string
from pathlib import Path

import pytest

import spvault as spb
from test_gui import pump, wait_jobs

# --- tabella delle traduzioni


def _literals(node) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):  # tr("a" if x else "b")
        return _literals(node.body) + _literals(node.orelse)
    raise AssertionError(f"spvault.py riga {node.lineno}: tr() vuole un testo letterale da tradurre")


def tr_calls() -> list[tuple[int, list[str], set[str]]]:
    """(riga, testi italiani, nomi dei parametri) di ogni chiamata tr(...) in spvault.py."""
    tree = ast.parse(Path(spb.__file__).read_text(encoding="utf-8"))
    return [(node.lineno, _literals(node.args[0]), {k.arg for k in node.keywords})
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr"]


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


def test_every_translated_text_has_an_english_version_with_the_same_placeholders():
    calls = tr_calls()
    assert len(calls) > 80
    for line, texts, params in calls:
        for it in texts:
            assert it in spb.EN, f"riga {line}: manca la traduzione inglese di {it!r}"
            en = spb.EN[it]
            assert en.strip(), it
            assert fields(it) == params, f"riga {line}: segnaposto {fields(it)}, parametri {params}"
            assert fields(en) == fields(it), f"segnaposto diversi in inglese: {it!r} -> {en!r}"


def test_no_unused_translations():
    used = {text for _, texts, _ in tr_calls() for text in texts}
    assert set(spb.EN) - used == set()


def test_tr_formats_and_falls_back_to_italian(monkeypatch):
    assert spb.tr("MANCANTE: {path}", path="a/b") == "MANCANTE: a/b"
    monkeypatch.setattr(spb, "LANG", "en")
    assert spb.tr("MANCANTE: {path}", path="a/{b}") == "MISSING: a/{b}"
    assert spb.tr("Testo senza traduzione: {n}", n=3) == "Testo senza traduzione: 3"
    assert spb.fmt_count(1234567) == "1,234,567"
    monkeypatch.setattr(spb, "LANG", "it")
    assert spb.fmt_count(1234567) == "1.234.567"


# --- scelta della lingua

@pytest.mark.parametrize("choice, ui, lang", [
    ("auto", 0x0410, "it"), ("auto", 0x0810, "it"),   # italiano (Italia, Svizzera)
    ("auto", 0x0409, "en"), ("auto", 0x0407, "en"),   # inglese, tedesco -> inglese
    ("it", 0x0409, "it"), ("en", 0x0410, "en"),       # scelta esplicita
    ("xx", 0x0410, "it"), (None, 0x0409, "en"),       # valore sconosciuto = automatica
])
def test_language_resolution(monkeypatch, choice, ui, lang):
    monkeypatch.setattr(spb, "windows_ui_language", lambda: ui)
    assert spb.resolve_language(choice) == lang


def test_unknown_windows_language_means_english(monkeypatch):
    def fail():
        raise AttributeError("windll")  # es. fuori da Windows
    monkeypatch.setattr(spb, "windows_ui_language", fail)
    assert spb.resolve_language("auto") == "en"
    assert spb.resolve_language("it") == "it"


def test_default_is_automatic():
    assert spb.DEFAULTS["language"] == "auto" and spb.load_config()["language"] == "auto"


@pytest.mark.parametrize("language, ui, verdict", [
    ("en", 0x0410, "VERIFICATION OK: all 5 visible files"), ("it", 0x0409, "VERIFICA OK: tutti i 5 file"),
    ("auto", 0x0409, "VERIFICATION OK: all 5 visible files"), ("auto", 0x0410, "VERIFICA OK: tutti i 5 file"),
])
def test_scheduled_run_uses_the_saved_language(bk, monkeypatch, language, ui, verdict):
    monkeypatch.setattr(spb, "windows_ui_language", lambda: ui)
    boxes = []
    monkeypatch.setattr(spb, "message_box", boxes.append)
    spb.save_config(dict(bk.cfg, language=language))
    assert spb.run_scheduled() == 0
    assert verdict in spb.SCHEDULED_LOG.read_text(encoding="utf-8")
    assert boxes == []


def test_scheduled_run_messages_in_english(bk, monkeypatch):
    boxes = []
    monkeypatch.setattr(spb, "message_box", boxes.append)
    spb.save_config(dict(bk.cfg, language="en", selection=[]))
    assert spb.run_scheduled() == 1
    assert boxes[-1] == 'SharePoint backup failed:\nNo folder selected: press "Connect" and choose what to back up'

    def expired(site, interactive, log):
        raise spb.LoginRequired(spb.tr('Serve di nuovo il login: premi "Connetti" e accedi nel browser'))
    monkeypatch.setattr(spb, "browser_login", expired)
    spb.save_config(dict(bk.cfg, language="en"))
    assert spb.run_scheduled() == 1
    assert boxes[-1].startswith("The scheduled backup did not start because the SharePoint session has expired.")
    log = spb.SCHEDULED_LOG.read_text(encoding="utf-8")
    assert "ERROR: No folder selected" in log and "ERROR: You need to sign in again" in log


# --- backup in inglese

ITALIAN = re.compile(r"\b(Lettura|Libreria|Verifica|VERIFICA|MANCANTE|ACCESSIBILE|elementi|scaricati|invariati"
                     r"|ERRORE|ATTENZIONE|Salto|Selezione|scaricare|cartelle|versioni|salvata|spostato)\b")


def test_backup_in_english(bk, monkeypatch):
    monkeypatch.setattr(spb, "LANG", "en")
    bk.server.add("priv", "riservato.psd", "A1", content=b"p" * 777)
    bk.server.private.add("priv")     # non visibile con l'account
    bk.server.always_fail.add("f3")   # download sempre in errore
    summary = bk.run(expect_complete=False)
    head, verdict, warning = summary.splitlines()
    assert re.fullmatch(r"Backup (\S+_r1): 4 downloaded \(.+\), 0 unchanged, 0 moved, "
                        r"0 versions saved in _Versions\\\1, \d+ download errors", head), head
    assert verdict == "VERIFICATION FAILED: 1 files missing (list in the log and in _FileList.csv)"
    assert warning == ("WARNING: 1 items (777 B) in 1 folders are not visible to your account "
                       "and cannot be copied (list in the log)")
    assert "MISSING: 2. Projects/note.txt" in bk.logs
    assert "NOT ACCESSIBLE: 2. Projects/Progetto1: 1 items (777 B) exist on SharePoint " \
           "but are not visible to your account" in bk.logs
    assert "Skipping 2. Projects/Appunti (OneNote notebook, not a file)" in bk.logs
    assert any(line.startswith("ERROR on 2. Projects/note.txt: HTTP 500") for line in bk.logs)
    assert any(re.fullmatch(r"Library read: \d+ items", line) for line in bk.logs)

    [log_file] = (bk.dest / spb.LOG_DIR).glob("*.log")
    text = log_file.read_text(encoding="utf-8")
    label = log_file.stem
    assert f"Backup {label} to {bk.dest}" in text and verdict in text
    for line in [*bk.logs, *summary.splitlines(), *text.splitlines()]:
        assert not ITALIAN.search(line), line

    lines = (bk.dest / spb.MANIFEST).read_text(encoding="utf-8-sig").splitlines()
    assert lines[0].split(";") == ["Path", "Size (bytes)", "Modified on SharePoint", "quickXorHash", "Status",
                                   f"Verification {label}"]
    rows = {r[0]: r[4] for r in bk.manifest()}
    assert rows["2. Projects/note.txt"] == "MISSING" and rows["Inventory.xlsx"] == "OK"
    assert rows["2. Projects/Progetto1/ (content not visible)"] == "NOT ACCESSIBLE (1 items)"

    bk.server.always_fail.clear()
    bk.server.private.clear()
    summary = bk.run()
    assert re.fullmatch(r"VERIFICATION OK: all 6 visible files \(\d+\.\d KB\) are in Current, identical to SharePoint",
                        summary.splitlines()[-1]), summary
    assert all(r[4] == "OK" for r in bk.manifest())


# --- finestra

def switch(app, label):
    app.cmb_lang.set(label)
    app.cmb_lang.event_generate("<<ComboboxSelected>>")
    pump(app.root, lambda: spb.LANG == {"English": "en", "Italiano": "it"}[label])
    app.root.update()


def test_switching_language_relabels_the_window(server, make_app, tmp_path, popups):
    app = make_app(selection=["A", "TOP"], dest=str(tmp_path / "backup"), online_only=False)
    wait_jobs(app, 1)
    assert (app.btn_connect["text"], app.btn_run["text"], app.btn_stop["text"]) == ("Connetti", "Esegui backup",
                                                                                     "Ferma")
    log = app.log_box.get("1.0", "end")
    assert "Connesso come me@test" in log

    switch(app, "English")
    assert (app.btn_connect["text"], app.btn_run["text"], app.btn_stop["text"]) == ("Connect", "Run backup", "Stop")
    assert spb.load_config()["language"] == "en"
    assert app.log_box.get("1.0", "end") == log                         # il log resta
    assert app.var_account.get() == "Connected as me@test"
    assert app.var_selsize.get().startswith("Selected: ")
    assert {k: v.get() for k, v in app.item_vars.items()} == {"A": True, "B": False, "TOP": True}
    boxes = app.items_frame.winfo_children()                             # caselle legate alle stesse variabili
    assert sorted(str(b.cget("variable")) for b in boxes) == sorted(str(v) for v in app.item_vars.values())

    app.start_backup()                                                   # la finestra ricreata funziona
    wait_jobs(app, 2)
    assert app.var_status.get().startswith("✓ VERIFICATION OK: all 5 visible files"), app.var_status.get()
    for phase in ("Reading the library", "Downloading:", "Checking the files on disk", "Cleanup and versions"):
        assert any(s.startswith(phase) for s in app.statuses), phase
    assert popups == []

    switch(app, "Italiano")
    assert app.btn_run["text"] == "Esegui backup" and spb.load_config()["language"] == "it"
    assert "VERIFICATION OK" in app.log_box.get("1.0", "end")


def test_language_switch_keeps_a_running_job(server, make_app):
    app = make_app()
    wait_jobs(app, 1)
    app._set_running(True, "Lavoro in corso...")
    switch(app, "English")
    assert str(app.btn_run["state"]) == "disabled" and str(app.btn_stop["state"]) == "normal"
    assert str(app.progress.cget("mode")) == "indeterminate"
    app._set_running(False)
    assert str(app.btn_run["state"]) == "normal"


def test_initial_texts_follow_the_language(server, make_app, monkeypatch):
    monkeypatch.setattr(spb, "windows_ui_language", lambda: 0x0409)  # Windows in inglese
    app = make_app()                                                 # lingua "auto"
    assert spb.LANG == "en" and app.btn_run["text"] == "Run backup"
    assert (app.var_status.get(), app.var_account.get()) == ("Ready", "Not connected")
    assert app.var_lang.get() == "Automatica / Automatic"
    app.var_lang.set("Italiano")
    app._on_language()
    app._apply_language()
    assert (app.var_status.get(), app.var_account.get()) == ("Pronto", "Non connesso")
    wait_jobs(app, 1)
