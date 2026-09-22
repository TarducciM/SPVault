"""Scaricamento a blocchi quando lo spazio sul disco non basta: disco e OneDrive simulati."""
import pytest

import spvault as spb
from conftest import Harness


class FakeDisk:
    """Disco da `capacity` byte con dentro la cartella di backup, sincronizzata da un OneDrive
    finto: a ogni attesa del tool (time.sleep) carica un file e lo toglie dal disco."""

    def __init__(self, bk: Harness, capacity: int, working=True):
        self.bk, self.capacity, self.working = bk, capacity, working
        self.uploaded: set[str] = set()
        self.peak = 0

    def used(self) -> int:
        return sum(p.stat().st_size for p in self.bk.dest.rglob("*")
                   if p.is_file() and str(p) not in self.uploaded)

    def free(self, _backup=None) -> int:
        used = self.used()
        self.peak = max(self.peak, used)
        return self.capacity - used

    def is_online_only(self, p) -> bool:
        return str(p).removeprefix("\\\\?\\") in self.uploaded

    def onedrive_works(self, _seconds):
        if not self.working:
            return
        for p in sorted(self.bk.current.rglob("*")):
            if p.is_file() and str(p) not in self.uploaded:
                self.uploaded.add(str(p))  # caricato e tolto dal disco
                return


@pytest.fixture
def disk(bk, monkeypatch):
    def make(capacity, working=True, onedrive=True):
        d = FakeDisk(bk, capacity, working)
        monkeypatch.setattr(spb.Backup, "_free", d.free)
        monkeypatch.setattr(spb, "is_online_only", d.is_online_only)
        monkeypatch.setattr(spb, "in_onedrive", lambda path: onedrive)
        monkeypatch.setattr(spb.time, "sleep", d.onedrive_works)
        monkeypatch.setattr(spb, "MIN_FREE", 1000)
        bk.cfg["selection"] = ["A"]  # file da 5 KB, 500 B, 4 B, 20 KB
        return d
    return make


def test_everything_fits_no_batches(bk, disk):
    d = disk(capacity=10 ** 9)
    summary = bk.run()
    assert "VERIFICA OK" in summary
    assert not any("a blocchi" in line for line in bk.logs)
    assert d.uploaded == set()


def test_downloads_in_batches_when_the_disk_is_too_small(bk, disk):
    d = disk(capacity=24_000)  # ci sta il file da 20 KB, ma non insieme agli altri
    summary = bk.run()
    assert "VERIFICA OK: tutti i 4 file" in summary
    assert any("scarico a blocchi" in line for line in bk.logs)
    assert any("OneDrive ha liberato spazio" in line for line in bk.logs)
    assert d.peak <= 24_000 - 1000       # il margine sul disco è sempre rispettato
    assert len(bk.tree()) == 4
    assert bk.dest.joinpath("vecchio_backup.zip").exists()


def test_a_file_larger_than_the_whole_space_is_reported_missing(bk, disk):
    disk(capacity=12_000)  # il file da 20 KB non ci sta nemmeno col disco liberato
    summary = bk.run(expect_complete=False)
    assert "VERIFICA NON SUPERATA: 1 file mancanti" in summary
    assert any("troppo grande per lo spazio sul disco" in line for line in bk.logs)
    assert "MANCANTE: 2. Projects/grande.psd" in bk.logs


def test_stops_when_onedrive_does_not_free_space(bk, disk):
    disk(capacity=24_000, working=False)  # OneDrive chiuso: non carica niente
    with pytest.raises(RuntimeError, match="OneDrive non ha liberato spazio negli ultimi 30 minuti"):
        bk.run()


def test_outside_onedrive_the_error_explains_what_to_do(bk, disk):
    disk(capacity=24_000, onedrive=False)
    with pytest.raises(RuntimeError, match="usa una cartella di backup dentro OneDrive"):
        bk.run()


def test_onedrive_folders_are_recognised(monkeypatch, tmp_path):
    monkeypatch.setenv("OneDriveCommercial", str(tmp_path / "OneDrive - Azienda"))
    assert spb.in_onedrive(tmp_path / "OneDrive - Azienda" / "Team" / "Backup")
    assert not spb.in_onedrive(tmp_path / "OneDrive - Azienda altro")
    assert not spb.in_onedrive(tmp_path / "Documenti")
