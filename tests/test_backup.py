"""Scenari di backup completi contro il server SharePoint finto (tests/fakes.py)."""
import threading

import pytest

import spvault as spb

INITIAL = ["2. Projects/Progetto1/bg.png", "2. Projects/Progetto1/logo.psd", "2. Projects/grande.psd",
           "2. Projects/note.txt", "Inventory.xlsx"]


def test_first_backup_copies_the_selection_and_verifies_it(bk):
    summary = bk.run()
    assert bk.tree() == INITIAL
    assert (bk.current / "2. Projects/Vuota").is_dir()                     # cartelle vuote comprese
    assert (bk.current / "2. Projects/grande.psd").read_bytes() == bk.server.items["big"]["content"]
    assert abs((bk.current / "2. Projects/note.txt").stat().st_mtime - bk.server.items["f3"]["mtime"]) < 1
    assert any("OneNote" in line for line in bk.logs)                  # blocco appunti saltato
    assert "VERIFICA OK: tutti i 5 file" in summary
    assert bk.versions() == []
    assert (bk.dest / "vecchio_backup.zip").exists()                   # il resto non si tocca
    assert sorted(row[0] for row in bk.manifest()) == INITIAL
    assert all(row[4] == "OK" for row in bk.manifest())
    assert len(list((bk.dest / spb.LOG_DIR).glob("*.log"))) == 1


def test_interrupted_download_resumes_with_range(bk):
    bk.server.break_once.add("big")
    bk.run()
    assert ("big", 3000) in bk.server.ranges
    assert (bk.current / "2. Projects/grande.psd").read_bytes() == bk.server.items["big"]["content"]


def test_unchanged_library_downloads_nothing(bk):
    bk.run()
    summary = bk.run()
    assert bk.server.downloads == []
    assert "5 invariati" in summary


def test_changes_on_sharepoint_are_mirrored_with_versions(bk):
    bk.run()
    s = bk.server
    s.modify("f2", b"png-2" * 100)            # modificato
    s.rename("f3", name="note_v2.txt")        # rinominato
    s.rename("A1", name="Progetto1_OK")       # cartella rinominata (con dentro f2 modificato)
    s.delete("f1")                            # eliminato
    s.add("f4", "nuovo.txt", "A1", content=b"nuovo")
    s.touch_metadata("TOP")                   # cambiano solo i metadati
    bk.run()
    assert sorted(s.downloads) == ["f2", "f4"]  # nessun download per rinomine e metadati
    assert bk.tree() == ["2. Projects/Progetto1_OK/bg.png", "2. Projects/Progetto1_OK/nuovo.txt",
                         "2. Projects/grande.psd", "2. Projects/note_v2.txt", "Inventory.xlsx"]
    assert not (bk.current / "2. Projects/Progetto1").exists()
    [label] = bk.versions()
    assert bk.tree(f"{spb.VERSIONS_DIR}/{label}") == ["2. Projects/Progetto1/logo.psd",
                                                      "2. Projects/Progetto1_OK/bg.png"]
    old = bk.dest / spb.VERSIONS_DIR / label / "2. Projects/Progetto1_OK/bg.png"
    assert old.read_bytes() == b"png-1" * 100


def test_foreign_local_files_are_archived(bk):
    bk.run()
    (bk.current / "2. Projects/estraneo.txt").write_text("x")
    (bk.current / "2. Projects/desktop.ini").write_text("x")  # creato da OneDrive/Explorer: resta
    bk.run()
    assert not (bk.current / "2. Projects/estraneo.txt").exists()
    assert (bk.current / "2. Projects/desktop.ini").exists()
    [label] = bk.versions()
    assert bk.tree(f"{spb.VERSIONS_DIR}/{label}") == ["2. Projects/estraneo.txt"]


def test_locally_deleted_file_is_downloaded_again(bk):
    bk.run()
    (bk.current / "2. Projects/note.txt").unlink()
    bk.run()
    assert bk.server.downloads == ["f3"]
    assert (bk.current / "2. Projects/note.txt").read_bytes() == b"note"


def test_session_is_renewed_when_it_expires(bk, monkeypatch):
    bk.run()
    bk.server.modify("TOP", b"xlsx-2")
    bk.server.unauth_once = True
    connect = spb.SharePoint.connect

    def connect_long_ago(self, interactive):
        connect(self, interactive)
        self._last_login -= 1000  # sessione ottenuta "tanto tempo fa": il 401 va rinnovato

    monkeypatch.setattr(spb.SharePoint, "connect", connect_long_ago)
    bk.server.logins.clear()
    bk.run()
    assert bk.server.logins == [False, False]  # login iniziale + rinnovo, sempre invisibile
    assert (bk.current / "Inventory.xlsx").read_bytes() == b"xlsx-2"


def test_only_the_last_n_versions_are_kept(bk):
    bk.run()
    for n in range(3):
        bk.server.modify("f3", f"note-{n}".encode())
        bk.run(keep_versions=2)
    assert len(bk.versions()) == 2
    assert bk.versions()[-1].endswith("_r4")


def test_lost_local_state_does_not_redownload(bk, isolated_app_dir):
    bk.run()
    for db in isolated_app_dir.glob("state_*.sqlite"):
        db.unlink()
    summary = bk.run()
    assert bk.server.downloads == []
    assert "VERIFICA OK" in summary


def test_hash_mismatch_is_retried_and_reported(bk):
    bk.server.bad_hash.add("f3")
    bk.run()
    assert bk.server.downloads.count("f3") == 2
    assert any("ATTENZIONE" in line and "note.txt" in line for line in bk.logs)
    bk.run()
    assert bk.server.downloads == []  # nessun ciclo di riscaricamenti


def test_expired_delta_token_triggers_a_full_scan(bk):
    bk.run()
    bk.force_full_scan(delta_link="https://t.sharepoint.com/sites/Test/_api/v2.0/drives/D1/root/delta?token=v-1")
    state = spb.State("D1", bk.dest)
    state.set_meta("last_full_scan", 9e12)  # link "recente" ma scaduto lato server
    state.db.commit()
    state.db.close()
    bk.run()
    assert any("scaduto" in line for line in bk.logs)
    assert bk.server.downloads == []


def test_selection_can_grow_and_shrink(bk):
    bk.run()
    bk.run(selection=["A", "TOP", "B"])
    assert "3. Marketing/online.psd" in bk.tree()
    bk.run(selection=["A", "TOP"])
    assert "3. Marketing/online.psd" not in bk.tree()
    assert any("3. Marketing/online.psd" in line and "✗" in line for line in bk.logs)


def test_missing_selected_folder_aborts_without_archiving(bk):
    bk.run()
    with pytest.raises(RuntimeError, match="non esistono più"):
        bk.run(selection=["A", "NONESISTE"])
    assert bk.tree() == INITIAL


def test_empty_selection_is_rejected(bk):
    with pytest.raises(RuntimeError, match="Nessuna cartella"):
        bk.run(selection=[])


def test_cancel(bk):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(spb.Cancelled):
        bk.run(cancel=cancel)


def test_only_one_backup_at_a_time(isolated_app_dir):
    with spb.single_instance():
        with pytest.raises(RuntimeError, match="già un backup"):
            with spb.single_instance():
                pass


def test_paths_longer_than_260_characters(bk):
    parent = "A"
    for k in range(8):
        bk.server.add(f"deep{k}", f"cartella_con_un_nome_molto_lungo_{str(k) * 10}", parent, "folder")
        parent = f"deep{k}"
    bk.server.add("deepf", "file_in_profondita.psd", parent, content=b"deep")
    bk.run()
    [path] = [p for p in bk.tree() if p.endswith("file_in_profondita.psd")]
    assert len(str(bk.current / path)) > 260


# --- verifica di completezza

def test_file_missing_from_the_listing_is_found_by_folder_sizes(bk):
    bk.server.add("hid", "nascosto.psd", "A1", content=b"hidden-content")
    bk.server.hidden.add("hid")  # SharePoint non lo riporta nell'elenco delta
    summary = bk.run()
    assert "hid" in bk.server.downloads
    assert (bk.current / "2. Projects/Progetto1/nascosto.psd").exists()
    assert any("mancava nell'elenco" in line for line in bk.logs)
    assert "VERIFICA OK: tutti i 6 file" in summary
    for _ in range(2):  # anche dopo una rilettura completa: niente archiviazioni né riscaricamenti
        bk.run()
        assert bk.server.downloads == [] and not any("✗" in line for line in bk.logs)
        bk.force_full_scan()


def test_stale_file_in_the_listing_is_dropped(bk):
    bk.server.ghosts["ghost"] = {"id": "ghost", "name": "fantasma.psd", "parentReference": {"id": "A"},
                                 "file": {"hashes": {"quickXorHash": "AAAA"}}, "size": 123,
                                 "cTag": "c:g,1", "lastModifiedDateTime": "2026-01-01T00:00:00Z"}
    summary = bk.run()
    assert any("non più su SharePoint, tolto" in line for line in bk.logs)
    assert "ghost" not in bk.server.downloads and "VERIFICA OK" in summary


def test_failed_download_fails_verification_then_recovers(bk):
    bk.server.always_fail.add("f3")
    summary = bk.run(expect_complete=False)
    assert "VERIFICA NON SUPERATA: 1 file mancanti" in summary
    assert "MANCANTE: 2. Projects/note.txt" in bk.logs
    assert ["2. Projects/note.txt", "4"] == [r[:2] for r in bk.manifest() if r[4] == "MANCANTE"][0]
    bk.server.always_fail.clear()
    summary = bk.run()
    assert bk.server.downloads == ["f3"] and "VERIFICA OK" in summary
    assert all(row[4] == "OK" for row in bk.manifest())


def test_content_the_account_cannot_see_is_reported(bk):
    bk.server.add("priv", "riservato.psd", "A1", content=b"p" * 777)
    bk.server.private.add("priv")  # esiste ma l'utente non lo vede (permessi)
    summary = bk.run()
    assert "VERIFICA OK" in summary
    assert "ATTENZIONE: 1 elementi (777 B) in 1 cartelle non sono visibili" in summary
    assert any(line.startswith("NON ACCESSIBILE: 2. Projects/Progetto1: 1 elementi") for line in bk.logs)
    assert any(row[4] == "NON ACCESSIBILE (1 elementi)" for row in bk.manifest())
    assert "priv" not in bk.server.downloads
