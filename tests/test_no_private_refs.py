"""Il progetto non deve contenere riferimenti a organizzazioni, persone o percorsi privati.

Le parole vietate sono salvate solo come impronta SHA-256 (troncata): così non compaiono
nemmeno qui. Si controllano le singole parole e le coppie di parole consecutive unite
(per nomi scritti con lo spazio in mezzo)."""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "build", "dist", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv"}
TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".ps1", ".wxs", ".toml", ".txt", ".json", ".cfg", ".ini", "",
                 ".html", ".js", ".css", ".svg"}  # anche il sito (site/) e la grafica
FORBIDDEN = {
    "4e8c72c0bd52fca9", "6176b107d72ab5ad", "08882d4ee4810f89", "079aa75b2a7543f5", "c1d59cd10354bda6",
    "d46a17aa92169153", "018b3e2babc33045", "b077e4f617423641", "54c9ef4d88c6734c", "3b13bdde41d4aca7",
    "409c614a9c4c2539", "b116a4cf991ddf65", "c857d09db23e6822", "c70eca6b0f88f44d",
}


# Le pagine legali del sito indicano l'editore (come nei siti degli altri progetti dello stesso
# editore): solo lì è ammesso il suo nome, e nient'altro della lista.
LEGAL_PAGES = {"site/privacy.html", "site/terms.html", "site/cookie-policy.html", "site/i18n.js"}
PUBLISHER = {"c1d59cd10354bda6", "d46a17aa92169153"}


def fingerprint(word: str) -> str:
    return hashlib.sha256(word.encode()).hexdigest()[:16]


def project_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not SKIP_DIRS & set(path.relative_to(ROOT).parts) and path.suffix in TEXT_SUFFIXES:
            yield path


def test_no_private_references():
    hits = []
    for path in project_files():
        words = re.findall(r"[a-z0-9]+", path.read_text(encoding="utf-8", errors="ignore").lower())
        candidates = set(words) | {a + b for a, b in zip(words, words[1:], strict=False)}
        forbidden = FORBIDDEN - PUBLISHER if path.relative_to(ROOT).as_posix() in LEGAL_PAGES else FORBIDDEN
        found = sorted(w for w in candidates if fingerprint(w) in forbidden)
        if found:
            hits.append(f"{path.relative_to(ROOT)}: {len(found)} parole vietate")
    assert not hits, "\n".join(hits)


def test_the_check_finds_single_and_split_words(tmp_path, monkeypatch):
    monkeypatch.setattr("test_no_private_refs.ROOT", tmp_path)
    monkeypatch.setattr("test_no_private_refs.FORBIDDEN", {fingerprint("acmecorp")})
    (tmp_path / "ok.md").write_text("Contoso, Shared Documents")
    test_no_private_references()
    (tmp_path / "bad.md").write_text("backup of ACME Corp files")
    try:
        test_no_private_references()
    except AssertionError as e:
        assert "bad.md" in str(e) and "ok.md" not in str(e)
    else:
        raise AssertionError("il controllo non ha trovato la parola vietata")
    assert fingerprint("sharepoint") not in FORBIDDEN


def test_publisher_name_is_allowed_only_in_legal_pages():
    assert PUBLISHER <= FORBIDDEN  # fuori dalle pagine legali resta vietato
    assert LEGAL_PAGES <= {p.relative_to(ROOT).as_posix() for p in project_files()}
