"""Link incollato dall'utente: libreria, cartella, "Copia collegamento", link di condivisione,
OneDrive, sito principale. "Cosa copiare" segue il link; cambiare link non mescola i backup;
primo avvio senza configurazione."""
import time

import pytest

import spvault as spb
from conftest import Harness
from fakes import DRIVE, SITE
from test_backup import INITIAL
from test_gui import wait_jobs

C = "https://contoso.sharepoint.com"
MY = "https://contoso-my.sharepoint.com"
TEAM, LIB = f"{C}/sites/Team", "/sites/Team/Shared Documents"
ONEDRIVE = spb.Link(f"{MY}/personal/user_contoso_com", "/personal/user_contoso_com/Documents", "Projects")


# --- lettura del link

@pytest.mark.parametrize("url, expected", [
    # radice della libreria (anche la sua vista), /sites e /teams
    (f"{C}/sites/Team/Shared%20Documents", spb.Link(TEAM, LIB)),
    (f"{C}/sites/Team/Shared%20Documents/", spb.Link(TEAM, LIB)),
    (f"{C}/sites/Team/Shared%20Documents/Forms/AllItems.aspx?viewid=1a2b&view=0", spb.Link(TEAM, LIB)),
    (f"{C}/teams/Sales%20EU/Documents/Forms/AllItems.aspx",
     spb.Link(f"{C}/teams/Sales%20EU", "/teams/Sales EU/Documents")),
    # cartella per percorso
    (f"{C}/sites/Team/Shared%20Documents/Projects/2026", spb.Link(TEAM, LIB, "Projects/2026")),
    (f"  {C}/sites/Team/Shared%20Documents/Projects/2026?web=1#top  ", spb.Link(TEAM, LIB, "Projects/2026")),
    (f"{C}/sites/Team/Shared%20Documents/R%26D%20%231/100%25", spb.Link(TEAM, LIB, "R&D #1/100%")),
    ("HTTPS://Contoso.SharePoint.com/sites/Team/Shared%20Documents/Projects", spb.Link(TEAM, LIB, "Projects")),
    # barra degli indirizzi di una vista: parametro id (RootFolder negli indirizzi vecchi)
    (f"{C}/sites/Team/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2FTeam%2FShared%20Documents%2FProjects"
     "&viewid=1a2b-3c4d", spb.Link(TEAM, LIB, "Projects")),
    (f"{C}/sites/Team/Shared%20Documents/Forms/AllItems.aspx?viewid=x&id=%2Fsites%2FTeam%2FShared%20Documents",
     spb.Link(TEAM, LIB)),
    (f"{C}/sites/Team/Shared%20Documents/Forms/AllItems.aspx?RootFolder=%2Fsites%2FTeam%2FShared%20Documents"
     "%2FProjects%2F2026&FolderCTID=0x0120", spb.Link(TEAM, LIB, "Projects/2026")),
    # "Copia collegamento" con il percorso diretto: /:<lettera>:/r/...
    (f"{C}/:f:/r/sites/Team/Shared%20Documents/Projects?csf=1&web=1&e=abc", spb.Link(TEAM, LIB, "Projects")),
    (f"{C}/:x:/r/teams/Sales/Shared%20Documents/Budget?csf=1",
     spb.Link(f"{C}/teams/Sales", "/teams/Sales/Shared Documents", "Budget")),
    # "Copia collegamento" con token: risolto dopo l'accesso (qui solo sito e link)
    (f"{C}/:f:/s/Team/EabcdEFGH123?e=xyz", spb.Link(TEAM, share=f"{C}/:f:/s/Team/EabcdEFGH123?e=xyz")),
    (f"{C}/:f:/t/Sales/EtokenX#x", spb.Link(f"{C}/teams/Sales", share=f"{C}/:f:/t/Sales/EtokenX")),
    (f"{C}/:f:/g/personal/user_contoso_com/EkLmNoP?e=1",
     spb.Link(f"{C}/personal/user_contoso_com", share=f"{C}/:f:/g/personal/user_contoso_com/EkLmNoP?e=1")),
    (f"{C}/:f:/g/EkLmNoP", spb.Link(C, share=f"{C}/:f:/g/EkLmNoP")),
    # OneDrive for Business
    (f"{MY}/personal/user_contoso_com/Documents/Projects", ONEDRIVE),
    (f"{MY}/personal/user_contoso_com/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Fuser_contoso_com%2FDocuments"
     "%2FProjects&view=0", ONEDRIVE),
    (f"{MY}/my?id=%2Fpersonal%2Fuser_contoso_com%2FDocuments%2FProjects", ONEDRIVE),
    (f"{MY}/personal/user_contoso_com/_layouts/15/onedrive.aspx",
     spb.Link(f"{MY}/personal/user_contoso_com", "/personal/user_contoso_com/Documents")),
    # libreria del sito principale
    (f"{C}/Shared%20Documents/Projects", spb.Link(C, "/Shared Documents", "Projects")),
    (f"{C}/Shared%20Documents/Forms/AllItems.aspx", spb.Link(C, "/Shared Documents")),
])
def test_parse_link(url, expected):
    assert spb.parse_link(url) == expected


@pytest.mark.parametrize("url", [
    "", "   ", "not a link", "contoso.sharepoint.com/sites/Team/Shared%20Documents",
    "http://contoso.sharepoint.com/sites/Team/Shared%20Documents",        # non https
    "https://example.com/sites/Team/Shared%20Documents",                  # non SharePoint
    "https://contoso.sharepoint.com.example.com/sites/Team/Shared%20Documents",
    "https://onedrive.live.com/?id=root",                                 # OneDrive personale
    "https://contoso.sharepoint.com", "https://contoso.sharepoint.com/sites",
    "https://contoso.sharepoint.com/sites/Team",                          # solo il sito
    "https://contoso.sharepoint.com/sites/Team/_layouts/15/viewlsts.aspx",
    "https://contoso.sharepoint.com/:f:/s/Team",                          # link senza token
    "https://contoso.sharepoint.com/:f:/x/sites/Team/Shared%20Documents",
])
def test_parse_link_rejects_invalid(url):
    with pytest.raises(ValueError):
        spb.parse_link(url)


def test_invalid_links_are_explained_with_an_example(monkeypatch):
    def message(url):
        with pytest.raises(ValueError) as e:
            spb.parse_link(url)
        return str(e.value)
    assert message("").startswith("Incolla il link della libreria o della cartella SharePoint")
    assert "es. https://<tenant>.sharepoint.com/sites/<sito>/<libreria>/<cartella>" in message("")
    assert message("http://contoso.sharepoint.com/sites/Team/Docs").startswith("Indirizzo non valido")
    assert message(f"{C}/sites/Team").startswith("Il link è di un sito, non di una libreria")
    monkeypatch.setattr(spb, "LANG", "en")
    assert message("https://example.com/a/b").endswith("e.g. https://<tenant>.sharepoint.com/sites/<site>/"
                                                       "<library>/<folder>")


def test_web_url_of_a_link():
    assert spb.parse_link(f"{C}/:f:/r/sites/Team/Shared%20Documents/R%26D%20%231?e=1").web_url == \
        f"{C}/sites/Team/Shared%20Documents/R%26D%20%231"
    assert spb.parse_link(f"{C}/Shared%20Documents").web_url == f"{C}/Shared%20Documents"


# --- libreria e cartella trovate dopo l'accesso (server finto)

SUBFOLDER = f"{SITE}/Documenti/Forms/AllItems.aspx?id=%2Fsites%2FTest%2FDocumenti%2F2.%20Projects&viewid=x"
SHARE = "https://t.sharepoint.com/:f:/s/Test/EaBcD-3_xYz?e=k9Q"  # in base64 ha "/" e "=": serve base64url
A_CHILDREN = {"A1", "E1", "NB", "big", "f3"}


def connected(url) -> spb.SharePoint:
    sp = spb.SharePoint(url, lambda msg: None)
    spb.connect(sp, False, lambda msg: None)
    return sp


def test_library_link_targets_the_whole_library(server):
    sp = connected(f"{SITE}/Documenti/Forms/AllItems.aspx?viewid=x")
    assert (sp.drive_id, sp.base_id, sp.target_key, sp.target_name) == ("D1", "root", "D1|root", "Documenti")
    assert {i["id"] for i in sp.top_items()} == {"A", "B", "TOP"}


@pytest.mark.parametrize("url", [
    f"{SITE}/Documenti/2.%20Projects/Progetto1",
    f"{SITE}/Documenti/Forms/AllItems.aspx?id=%2Fsites%2FTest%2FDocumenti%2F2.%20Projects%2FProgetto1&viewid=x",
    "https://t.sharepoint.com/:f:/r/sites/Test/Documenti/2.%20Projects/Progetto1?csf=1&web=1&e=abc",
])
def test_folder_link_targets_the_folder(server, url):
    sp = connected(url)
    assert (sp.drive_id, sp.base_id, sp.target_key) == ("D1", "A1", "D1|A1")
    assert sp.target_name == "Documenti › 2. Projects › Progetto1"
    assert sorted(i["name"] for i in sp.top_items()) == ["bg.png", "logo.psd"]


def test_folder_path_is_url_encoded(server):
    server.add("W", "R&D #1 100%", "A", "folder")
    sp = connected(f"{SITE}/Documenti/2.%20Projects/R%26D%20%231%20100%25")
    assert sp.base_id == "W"
    assert any(u.startswith(f"{DRIVE}/root:/2.%20Projects/R%26D%20%231%20100%25?") for u in server.urls)


def test_missing_folder_file_or_library_is_explained(server):
    with pytest.raises(RuntimeError, match="Cartella 2. Projects/Nessuna non trovata in Documenti"):
        connected(f"{SITE}/Documenti/2.%20Projects/Nessuna")
    with pytest.raises(RuntimeError, match="Il link è di un file, non di una cartella"):
        connected(f"{SITE}/Documenti/2.%20Projects/note.txt")
    with pytest.raises(RuntimeError, match="Libreria /sites/Test/Nessuna non trovata"):
        connected(f"{SITE}/Nessuna/cartella")


def test_sharing_link_is_resolved_with_the_shares_api(server):
    server.shares[SHARE] = "A"
    sp = connected(SHARE)
    assert sp.login_url == SHARE  # il browser apre il link: lo riscatta (serve agli ospiti)
    assert (sp.drive_id, sp.base_id, sp.target_key) == ("D1", "A", "D1|A")
    assert sp.target_name == "Documenti › 2. Projects"
    assert server.prefer == ["redeemSharingLinkIfNecessary"]
    assert {i["id"] for i in sp.top_items()} == A_CHILDREN


def test_sharing_link_to_a_file_or_no_longer_valid(server):
    server.shares[SHARE] = "f3"
    with pytest.raises(RuntimeError, match="Il link è di un file"):
        connected(SHARE)
    del server.shares[SHARE]
    with pytest.raises(RuntimeError, match="Link di condivisione non valido, scaduto o non accessibile"):
        connected(SHARE)


def test_guest_who_cannot_list_the_libraries_uses_the_folder_address(server):
    server.guest = True
    server.shares[f"{SITE}/Documenti/2.%20Projects"] = "A"  # l'API shares accetta anche l'indirizzo diretto
    sp = connected(SUBFOLDER)
    assert (sp.drive_id, sp.base_id) == ("D1", "A")
    assert {i["id"] for i in sp.top_items()} == A_CHILDREN


# --- backup di una cartella

A_TREE = ["Progetto1/bg.png", "Progetto1/logo.psd", "grande.psd", "note.txt"]


def test_backup_of_a_folder_link_copies_only_that_folder(bk: Harness):
    selection = [i["id"] for i in connected(SUBFOLDER).top_items()]
    assert set(selection) == A_CHILDREN
    summary = bk.run(library_url=SUBFOLDER, selection=selection)
    assert bk.tree() == A_TREE                                  # percorsi relativi alla cartella del link
    assert (bk.current / "Vuota").is_dir()
    assert "VERIFICA OK: tutti i 4 file" in summary
    assert sorted(row[0] for row in bk.manifest()) == A_TREE
    assert not {"TOP", "g1"} & set(bk.server.downloads)
    bk.server.modify("f3", b"note-2")
    bk.server.modify("TOP", b"xlsx-2")                          # fuori dalla cartella: non conta
    summary = bk.run(library_url=SUBFOLDER, selection=selection)
    assert bk.server.downloads == ["f3"] and "VERIFICA OK" in summary
    assert (bk.current / "note.txt").read_bytes() == b"note-2"


def test_guest_backup_through_a_sharing_link_reads_only_that_folder(bk: Harness):
    bk.server.shares[SHARE] = "A"
    bk.server.guest = True                                      # niente delta della libreria intera
    selection = [i["id"] for i in connected(SHARE).top_items()]
    summary = bk.run(library_url=SHARE, selection=selection)
    assert bk.tree() == A_TREE
    assert "VERIFICA OK: tutti i 4 file" in summary
    assert "L'account non può leggere tutta la libreria: leggo solo la cartella Documenti › 2. Projects" in bk.logs
    bk.server.modify("f3", b"note-2")
    bk.server.add("f5", "nuovo.txt", "A1", content=b"nuovo")
    bk.server.delete("f2")
    summary = bk.run(library_url=SHARE, selection=selection)
    assert sorted(bk.server.downloads) == ["f3", "f5"]
    assert bk.tree() == ["Progetto1/logo.psd", "Progetto1/nuovo.txt", "grande.psd", "note.txt"]
    assert "VERIFICA OK: tutti i 4 file" in summary


def test_backup_needs_a_backup_folder(bk: Harness):
    with pytest.raises(RuntimeError, match="Scegli la cartella di backup"):
        bk.run(dest="  ")
    assert bk.server.logins == []


# --- cambio di link: niente backup mescolati

def test_scheduled_backup_after_a_link_change_stops_and_resets_the_selection(bk: Harness, monkeypatch):
    boxes = []
    monkeypatch.setattr(spb, "message_box", boxes.append)
    spb.save_config(dict(bk.cfg))                               # configurazione senza "target" (versione precedente)
    assert spb.run_scheduled() == 0
    cfg = spb.load_config()
    assert cfg["target"] == "D1|root" and cfg["selection"] == ["A", "TOP"]  # la prima volta si tiene
    spb.save_config(dict(cfg, library_url=SUBFOLDER))           # link cambiato nella finestra, senza "Connetti"
    assert spb.run_scheduled() == 1
    assert boxes == ["Backup SharePoint non riuscito:\nIl link indica un'altra libreria o cartella "
                     "(Documenti › 2. Projects): scegli cosa copiare e avvia di nuovo il backup"]
    cfg = spb.load_config()
    assert (cfg["target"], cfg["selection"]) == ("D1|A", [])
    assert {i["id"] for i in cfg["known_items"]} == A_CHILDREN
    assert bk.tree() == INITIAL and bk.versions() == []        # il backup precedente non è stato toccato


def test_changing_the_link_in_the_window_resets_the_selection(server, make_app):
    app = make_app(selection=["A", "TOP"])                      # configurazione senza "target"
    wait_jobs(app, 1)
    assert (spb.load_config()["target"], spb.load_config()["selection"]) == ("D1|root", ["A", "TOP"])
    assert app.var_target.get() == "Origine: Documenti"
    app.var_url.set(SUBFOLDER)
    assert app.var_target.get() == ""                           # non vale più finché non ci si riconnette
    app.start_connect()
    wait_jobs(app, 2)
    cfg = spb.load_config()
    assert (cfg["target"], cfg["selection"]) == ("D1|A", [])
    assert set(app.item_vars) == A_CHILDREN and not any(v.get() for v in app.item_vars.values())
    assert app.var_target.get() == "Origine: Documenti › 2. Projects"
    assert "Il link indica un'altra libreria o cartella (Documenti › 2. Projects): scegli di nuovo cosa copiare" \
        in app.log_box.get("1.0", "end")
    app.item_vars["f3"].set(True)
    app.start_connect()                                         # stesso link: la selezione resta
    wait_jobs(app, 3)
    assert spb.load_config()["selection"] == ["f3"]
    app.var_url.set(f"{SITE}/Documenti/Forms/AllItems.aspx")    # di nuovo tutta la libreria
    app.start_connect()
    wait_jobs(app, 4)
    assert spb.load_config()["selection"] == [] and set(app.item_vars) == {"A", "B", "TOP"}


def test_backup_from_the_window_after_a_link_change(server, make_app, popups, tmp_path):
    dest = tmp_path / "backup"
    app = make_app(selection=["A", "TOP"], dest=str(dest), online_only=False)
    wait_jobs(app, 1)
    app.var_url.set(SUBFOLDER)
    app.start_backup()                                          # senza "Connetti": si ferma prima di copiare
    wait_jobs(app, 2)
    assert popups[-1][0] == "showerror" and "Il link indica un'altra libreria o cartella" in popups[-1][2]
    assert set(app.item_vars) == A_CHILDREN and spb.load_config()["selection"] == []
    assert not (dest / spb.CURRENT_DIR).exists()
    for v in app.item_vars.values():
        v.set(True)
    app.start_backup()
    wait_jobs(app, 3)
    assert app.var_status.get().startswith("✓ VERIFICA OK: tutti i 4 file"), app.var_status.get()
    assert (dest / spb.CURRENT_DIR / "Progetto1" / "logo.psd").exists()
    assert not (dest / spb.CURRENT_DIR / "Inventory.xlsx").exists()


# --- primo avvio

EMPTY_HINT = 'Incolla qui sopra il link della libreria o della cartella (copiato dal browser) e premi "Connetti"'


def idle(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.root.update()


def test_first_run_is_empty_and_explains_what_to_do(server, make_app, popups, tmp_path):
    app = make_app(library_url="")
    assert (app.var_url.get(), app.var_dest.get()) == ("", "")
    assert [w.cget("text") for w in app.items_frame.winfo_children()] == [EMPTY_HINT]
    assert app.var_account.get() == "Non connesso" and app.var_target.get() == ""
    idle(app, 1)                                                # nessun aggiornamento automatico senza link
    assert (app.running, app.finished, server.logins) == (False, 0, [])

    app.start_connect()
    [(kind, title, text)] = popups
    assert (kind, title) == ("showwarning", "SPVault")
    assert text.startswith("Incolla il link") and "https://<tenant>.sharepoint.com/sites/" in text
    app.start_backup()                                          # prima di tutto la cartella di backup
    assert popups[-1] == ("showwarning", "SPVault", "Scegli la cartella di backup.")
    app.var_dest.set(str(tmp_path / "backup"))
    app.start_backup()
    assert popups[-1][2].startswith("Incolla il link")
    app.var_url.set("http://example.com/sites/Team/Shared%20Documents")
    app.start_connect()
    assert popups[-1][2].startswith("Indirizzo non valido") and "es. https://<tenant>" in popups[-1][2]

    app.var_url.set(f"{SITE}/Documenti")                        # link incollato: cambia il suggerimento
    assert [w.cget("text") for w in app.items_frame.winfo_children()] == [
        'Premi "Connetti" per leggere le cartelle della libreria']
    app.start_backup()
    assert popups[-1] == ("showwarning", "SPVault", "Seleziona almeno una cartella da copiare.")
    idle(app, 0.5)
    assert (app.running, app.finished, server.logins, len(popups)) == (False, 0, [], 5)
    assert not (tmp_path / "backup").exists()


def test_scheduled_run_without_configuration_explains_what_to_do(server, monkeypatch, tmp_path):
    boxes = []
    monkeypatch.setattr(spb, "message_box", boxes.append)
    assert spb.run_scheduled() == 1                             # nessuna configurazione salvata
    expected = ("Il backup pianificato non è partito: SPVault non è ancora configurato.\n"
                "Apri SPVault, incolla il link della libreria o della cartella e scegli la cartella di backup.")
    assert boxes == [expected]
    assert expected.splitlines()[0] in spb.SCHEDULED_LOG.read_text(encoding="utf-8")
    spb.save_config(dict(spb.DEFAULTS, library_url=f"{SITE}/Documenti", selection=["A"]))  # manca la cartella
    assert spb.run_scheduled() == 1 and boxes[-1] == expected
    spb.save_config(dict(spb.DEFAULTS, dest=str(tmp_path), selection=["A"]))               # manca il link
    assert spb.run_scheduled() == 1 and boxes[-1] == expected
    spb.save_config(dict(spb.DEFAULTS, library_url="https://example.com/a/b", dest=str(tmp_path), selection=["A"]))
    assert spb.run_scheduled() == 1
    assert boxes[-1].startswith("Backup SharePoint non riuscito:\nIndirizzo non valido")
    spb.save_config(dict(spb.DEFAULTS, language="en"))
    assert spb.run_scheduled() == 1
    assert boxes[-1].startswith("The scheduled backup did not start: SPVault is not configured yet.")
    assert server.logins == []                                  # mai il browser
    assert list(tmp_path.iterdir()) == [tmp_path / "appdata"]   # niente scritto fuori dalla cartella dati
