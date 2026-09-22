import time

import spvault as spb
from conftest import self_test

# fixture root, popups e make_app: tests/conftest.py


def pump(root, condition, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        root.update()
        if condition():
            return
    raise AssertionError("timeout")


def wait_jobs(app, n):
    """Aspetta che la finestra abbia concluso n lavori (il primo è l'aggiornamento all'apertura)."""
    pump(app.root, lambda: app.finished >= n)


def test_opening_the_window_refreshes_folders_and_sizes(server, make_app):
    app = make_app()
    wait_jobs(app, 1)
    assert app.var_status.get().startswith("✓ Connesso come me@test")
    assert set(app.item_vars) == {"A", "B", "TOP"}
    assert spb.load_config()["items_updated"] > 0
    assert "dimensioni aggiornate alle" in app.var_selsize.get()
    assert any(s.startswith("Accesso a SharePoint") for s in app.statuses)
    assert any(s.startswith("Connesso: lettura delle cartelle") for s in app.statuses)
    assert server.logins == [False]  # all'apertura mai finestre del browser


def test_expired_session_on_opening_is_quiet(server, make_app, monkeypatch, popups):
    def expired(site, interactive, log):
        raise spb.LoginRequired("serve il login")
    monkeypatch.setattr(spb, "browser_login", expired)
    app = make_app()
    wait_jobs(app, 1)
    assert app.var_status.get() == 'Non connesso: premi "Connetti"'
    assert popups == []


def test_connect_opens_the_browser_when_the_session_expired(server, make_app, monkeypatch):
    calls = []

    def login(site, interactive, log):
        calls.append(interactive)
        if not interactive:
            raise spb.LoginRequired("serve il login")
        return [{"name": "FedAuth", "value": "x", "domain": "t.sharepoint.com", "path": "/"}], "Mozilla/5.0"
    monkeypatch.setattr(spb, "browser_login", login)
    app = make_app()
    wait_jobs(app, 1)                 # apertura: solo tentativo invisibile
    app.start_connect()
    wait_jobs(app, 2)
    assert calls == [False, False, True]
    assert any("Accedi nella finestra del browser" in s for s in app.statuses)
    assert app.var_status.get().startswith("✓ Connesso")


def test_backup_from_the_window_shows_phases_and_result(server, make_app, tmp_path, popups):
    app = make_app(selection=["A", "TOP"], dest=str(tmp_path / "backup"), online_only=False)
    wait_jobs(app, 1)
    app.start_backup()
    wait_jobs(app, 2)
    status = app.var_status.get()
    assert status.startswith("✓ VERIFICA OK"), status
    for phase in ("Lettura della libreria", "Download:", "Verifica dei file su disco", "Pulizia e versioni"):
        assert any(s.startswith(phase) for s in app.statuses), phase
    assert (tmp_path / "backup" / "Current" / "Inventory.xlsx").exists()
    assert popups == []


def test_errors_are_shown_in_a_popup(server, make_app, popups, monkeypatch):
    app = make_app()
    wait_jobs(app, 1)
    monkeypatch.setattr(spb.SharePoint, "top_items", lambda self: (_ for _ in ()).throw(RuntimeError("rotto")))
    app.start_connect()
    wait_jobs(app, 2)
    assert app.var_status.get() == "✗ rotto"
    assert popups == [("showerror", "SPVault", "rotto")]


def test_selection_is_saved(server, make_app):
    app = make_app()
    wait_jobs(app, 1)
    app.item_vars["A"].set(True)
    assert spb.load_config()["selection"] == ["A"]
    assert app.var_selsize.get().startswith("Selezionati: ")


def test_self_test_passes():
    assert self_test() == 0
