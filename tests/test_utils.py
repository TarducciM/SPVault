import os
from datetime import date

import pytest

import spvault as spb


@pytest.mark.parametrize("url, site, library", [
    ("https://t.sharepoint.com/sites/Contoso/Documenti/Forms/AllItems.aspx?viewid=x",
     "https://t.sharepoint.com/sites/Contoso", "/sites/Contoso/Documenti"),
    ("https://t.sharepoint.com/sites/Sito/Shared%20Documents",
     "https://t.sharepoint.com/sites/Sito", "/sites/Sito/Shared Documents"),
    ("  https://t.sharepoint.com/teams/Team%20A/Doc/  ",
     "https://t.sharepoint.com/teams/Team%20A", "/teams/Team A/Doc"),
    ("https://t.sharepoint.com/personal/x/Documents",  # OneDrive for Business: ora supportato
     "https://t.sharepoint.com/personal/x", "/personal/x/Documents"),
])
def test_parse_link_of_a_library(url, site, library):
    assert spb.parse_link(url) == spb.Link(site, library)


@pytest.mark.parametrize("url", ["", "http://t.sharepoint.com/sites/A/B", "https://t.sharepoint.com/sites/A"])
def test_parse_link_rejects_invalid(url):
    with pytest.raises(ValueError):
        spb.parse_link(url)


@pytest.mark.parametrize("n, text", [(0, "0 B"), (1023, "1023 B"), (1024, "1.0 KB"),
                                     (5 * 1024 ** 2, "5.0 MB"), (66 * 1024 ** 3, "66.0 GB")])
def test_fmt_size(n, text):
    assert spb.fmt_size(n) == text


def test_next_label_counts_revisions_of_today(tmp_path):
    today = date.today().isoformat()
    assert spb.next_label(tmp_path) == f"{today}_r1"
    (tmp_path / spb.LOG_DIR).mkdir()
    (tmp_path / spb.LOG_DIR / f"{today}_r1.log").write_text("")
    (tmp_path / spb.LOG_DIR / "2020-01-01_r9.log").write_text("")
    (tmp_path / spb.VERSIONS_DIR / f"{today}_r3").mkdir(parents=True)
    assert spb.next_label(tmp_path) == f"{today}_r4"


def test_label_order_is_numeric():
    names = ["2026-09-21_r10", "2026-09-21_r9", "2026-09-20_r11"]
    assert sorted(names, key=spb.label_key) == ["2026-09-20_r11", "2026-09-21_r9", "2026-09-21_r10"]


@pytest.mark.skipif(os.name != "nt", reason="prefisso \\\\?\\ solo su Windows")
def test_long_path_prefix(tmp_path):
    p = spb.lp(tmp_path / "a")
    assert p.startswith("\\\\?\\") and spb.lp(p) == p
    assert spb.lp(r"\\server\share\x") == "\\\\?\\UNC\\server\\share\\x"


def test_config_defaults_and_bom(isolated_app_dir):
    assert spb.load_config() == spb.DEFAULTS
    isolated_app_dir.mkdir(parents=True)
    spb.CONFIG_FILE.write_text('{"keep_versions": 3}', encoding="utf-8-sig")  # es. Blocco note
    assert spb.load_config()["keep_versions"] == 3
    spb.CONFIG_FILE.write_text("{rotto", encoding="utf-8")
    assert spb.load_config() == spb.DEFAULTS


def test_config_round_trip(isolated_app_dir):
    cfg = dict(spb.DEFAULTS, selection=["id1"], dest="C:\\Backup àèì")
    spb.save_config(cfg)
    assert spb.load_config() == cfg


def test_same_content_uses_hash_then_ctag():
    f = spb.RemoteFile("i", "a/b", 10, "H", "c1", 0)
    assert spb.BackedUp("i", "a/b", 10, "H", "c0").same_content(f)       # cTag diverso, hash uguale
    assert not spb.BackedUp("i", "a/b", 10, "X", "c1").same_content(f)   # hash diverso
    assert not spb.BackedUp("i", "a/b", 11, "H", "c1").same_content(f)   # dimensione diversa
    f.hash = None
    assert spb.BackedUp("i", "a/b", 10, None, "c1").same_content(f)
    assert not spb.BackedUp("i", "a/b", 10, None, "c2").same_content(f)
