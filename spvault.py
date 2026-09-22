r"""
SPVault - copia file per file di una libreria SharePoint o OneDrive for Business (o di una
sua cartella) a cui hai accesso solo dal browser (anche come ospite in sola lettura), con versioning.

Cosa copiare: basta incollare il link copiato dal browser. Accetta
  - l'indirizzo della libreria o di una sua cartella:
      https://contoso.sharepoint.com/sites/Team/Shared%20Documents/Projects
  - la barra degli indirizzi di una vista: .../Forms/AllItems.aspx?id=%2Fsites%2FTeam%2F...
  - i link di "Copia collegamento": .../:f:/r/sites/Team/... (percorso) e .../:f:/s/Team/Eabc...
    (link di condivisione, risolto dopo l'accesso)
  - OneDrive for Business (https://contoso-my.sharepoint.com/personal/...) e il sito principale
    (https://contoso.sharepoint.com/Shared%20Documents/...)
  "Cosa copiare" elenca il contenuto della libreria o della cartella indicata dal link.

Come funziona
  - Accesso: si apre Chrome/Edge con un profilo dedicato, fai il login una volta
    (spunta "Resta connesso"); poi la sessione viene rinnovata da sola in background.
    Niente registrazione app, niente permessi da amministratore: il tool usa le
    stesse API che usa la pagina SharePoint nel browser.
  - Elenco file: API "delta" di SharePoint. La prima volta legge tutta la libreria,
    le volte successive solo le modifiche (rilettura completa ogni 7 giorni).
  - Download solo se il contenuto è cambiato: confronto con l'hash (quickXorHash)
    che SharePoint calcola per ogni file. Ogni download viene verificato con lo
    stesso hash. File rinominati/spostati su SharePoint vengono spostati anche in
    locale senza riscaricarli.
  - Verifica di completezza a ogni backup: la dimensione di ogni cartella dichiarata
    da SharePoint deve coincidere con la somma dei file copiati (se non coincide il tool
    cerca i file mancanti cartella per cartella e li scarica), e ogni file deve essere
    presente su disco. Esito nel log e in _FileList.csv (OK / MANCANTE per ogni file).

Cartella di backup
  Current\                   copia aggiornata, stessa struttura di SharePoint
  _Versions\2026-09-21_r1\   versioni precedenti dei file modificati o eliminati
                             in quel backup (si tengono le ultime N cartelle)
  _Log\2026-09-21_r1.log     cosa è stato fatto in ogni esecuzione
  _FileList.csv           tutti i file del backup con dimensione, data, hash e stato

Dipendenze:  pip install playwright requests
Uso:         python spvault.py            (finestra)
             pythonw spvault.py --run     (backup senza finestra, per la pianificazione)
             SPVault.exe [--run]   (versione compilata, vedi build.ps1)
"""

import base64
import contextlib
import csv
import ctypes
import hashlib
import json
import os
import queue
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from urllib.parse import parse_qsl, quote, unquote, urlparse
from xml.sax.saxutils import escape

import requests

__version__ = "0.1.1"

APP_DIR =Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "SPVault"
PROFILE_DIR = APP_DIR / "browser_profile"
TMP_DIR = APP_DIR / "tmp"
CONFIG_FILE = APP_DIR / "config.json"
LOCK_FILE = APP_DIR / "backup.lock"
SCHEDULED_LOG = APP_DIR / "scheduled_backup.log"
TASK_NAME = "SPVault"

CURRENT_DIR, VERSIONS_DIR, LOG_DIR = "Current", "_Versions", "_Logs"
DOWNLOAD_THREADS = 4
CHUNK = 1024 * 1024
FULL_SCAN_DAYS = 7
MIN_FREE = 3 * 1024 ** 3   # spazio da lasciare sempre libero sul disco
SPACE_POLL = 10            # secondi tra un controllo e l'altro mentre OneDrive libera spazio
SPACE_WAIT_LIMIT = 30 * 60  # se OneDrive non libera niente per 30 minuti il backup si ferma
KEEP_LOGS = 100
MANIFEST = "_FileList.csv"
MAX_VERIFY_FOLDERS = 500  # cartelle da ricontrollare una per una se le dimensioni non tornano
GB = 1024 ** 3
LABEL_RE = re.compile(r"(\d{4}-\d{2}-\d{2})_r(\d+)")
IGNORED_LOCAL = {"desktop.ini", "thumbs.db"}
DELTA_SELECT = "id,name,size,parentReference,file,folder,package,root,deleted,cTag,lastModifiedDateTime"
KIND_FILE, KIND_FOLDER, KIND_PACKAGE = 0, 1, 2
SHAREPOINT_HOST = re.compile(r"\.sharepoint(-mil)?\.(com|us|de|cn)$")  # SharePoint Online (anche cloud nazionali)
SITE_KINDS = ("sites", "teams", "personal")  # /sites/<sito>, /teams/<team>, /personal/<utente> (OneDrive)
SHARE_KINDS = {"s": ["sites"], "t": ["teams"], "p": ["personal"], "g": []}  # link con token: /:f:/s/<sito>/<token>

DEFAULTS = {
    "library_url": "",   # link della libreria o cartella, incollato dall'utente
    "dest": "",          # cartella di backup scelta dall'utente
    "target": "",        # libreria/cartella indicata dal link ("drive|cartella"), per non mescolare i backup
    "selection": [],      # id delle cartelle/file di primo livello da copiare
    "known_items": [],    # ultimo elenco letto: [{id, name, size, folder}]
    "items_updated": 0,   # quando è stato letto (timestamp)
    "keep_versions": 10,
    "online_only": True,
    "schedule_time": "13:00",
    "language": "auto",   # "auto" (lingua di Windows), "it" o "en"
    "include_new": True,  # aggiunge da solo al backup le cartelle nuove di primo livello
    "installer_language": "",  # ultima lingua scelta nell'installer MSI, già applicata
}


class LoginRequired(Exception):
    pass


class Cancelled(Exception):
    pass


class HttpError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


# ------------------------------------------------------------------------ lingua

LANG = "it"  # lingua dei testi: "it" (originale) o "en"; all'avvio la imposta set_language
LANGUAGES = {"auto": "Automatica / Automatic", "it": "Italiano", "en": "English"}  # scelte nella finestra

# Traduzioni inglesi: chiave = testo originale italiano passato a tr(), stessi {segnaposto}.
# tests/test_i18n.py controlla che ogni tr("...") abbia la sua voce e che non ce ne siano di inutili.
EN: dict[str, str] = {
    # link della libreria o della cartella
    'Incolla il link della libreria o della cartella SharePoint da copiare (dalla barra degli indirizzi del '
    'browser o da "Copia collegamento"), es. https://<tenant>.sharepoint.com/sites/<sito>/<libreria>/<cartella>':
        'Paste the link of the SharePoint library or folder to back up (from the browser address bar or from '
        '"Copy link"), e.g. https://<tenant>.sharepoint.com/sites/<site>/<library>/<folder>',
    "Indirizzo non valido: serve il link https:// di una libreria o cartella SharePoint copiato dal browser, "
    "es. https://<tenant>.sharepoint.com/sites/<sito>/<libreria>/<cartella>":
        "Invalid address: paste the https:// link of a SharePoint library or folder copied from the browser, "
        "e.g. https://<tenant>.sharepoint.com/sites/<site>/<library>/<folder>",
    "Il link è di un sito, non di una libreria: apri la libreria o la cartella da copiare "
    "(es. Documenti) e copia il link dalla barra degli indirizzi":
        "This link is to a site, not a library: open the library or folder to back up "
        "(e.g. Documents) and copy the link from the address bar",
    "Cartella {folder} non trovata in {library}: controlla il link":
        "Folder {folder} not found in {library}: check the link",
    "Il link è di un file, non di una cartella: copia il link della cartella che lo contiene":
        "The link is to a file, not a folder: copy the link of the folder that contains it",
    "Link di condivisione non valido, scaduto o non accessibile con questo account ({error})":
        "Sharing link not valid, expired or not accessible with this account ({error})",
    # accesso e API
    "Manca Playwright: esegui  pip install playwright": "Playwright is missing: run  pip install playwright",
    "Impossibile avviare Chrome o Edge ({errors})": "Cannot start Chrome or Edge ({errors})",
    'Completa l\'accesso nella finestra del browser (spunta "Resta connesso")':
        'Complete the sign-in in the browser window (tick "Stay signed in")',
    "Accesso non completato ({error})": "Sign-in not completed ({error})",
    'Serve di nuovo il login: premi "Connetti" e accedi nel browser':
        'You need to sign in again: press "Connect" and sign in in the browser',
    "Sessione scaduta: la rinnovo...": "Session expired: renewing it...",
    "Libreria {library} non trovata (disponibili: {available})":
        "Library {library} not found (available: {available})",
    "Accesso a SharePoint...": "Connecting to SharePoint...",
    "Serve l'accesso: apro il browser": "Sign-in required: opening the browser",
    "Accedi nella finestra del browser che si è aperta...": "Sign in in the browser window that has opened...",
    # lettura della libreria
    "Elenco modifiche scaduto: rileggo tutta la libreria": "Change list expired: reading the whole library again",
    "Lettura completa della libreria (la prima volta richiede qualche minuto)...":
        "Reading the whole library (the first time takes a few minutes)...",
    "Lettura delle modifiche su SharePoint...": "Reading the changes on SharePoint...",
    "Lettura della libreria...": "Reading the library...",
    "Lettura della libreria: {count} elementi": "Reading the library: {count} items",
    "Lettura delle modifiche: {count} elementi": "Reading the changes: {count} items",
    "  ... {count} elementi letti": "  ... {count} items read",
    "Libreria letta: {count} elementi": "Library read: {count} items",
    "Modifiche lette: {count} elementi": "Changes read: {count} items",
    "L'account non può leggere tutta la libreria: leggo solo la cartella {folder}":
        "The account cannot read the whole library: reading only the folder {folder}",
    "Lettura della cartella: {count} elementi": "Reading the folder: {count} items",
    "Cartella letta: {count} elementi": "Folder read: {count} items",
    'Alcune cartelle selezionate non esistono più su SharePoint: premi "Connetti" e rivedi la selezione':
        'Some selected folders no longer exist on SharePoint: press "Connect" and review the selection',
    # backup
    "Backup {label} in {folder}": "Backup {label} to {folder}",
    "INTERROTTO: {error}": "INTERRUPTED: {error}",
    "Salto {path} (blocco appunti OneNote, non è un file)": "Skipping {path} (OneNote notebook, not a file)",
    "Verifica dell'elenco con le dimensioni su SharePoint...":
        "Checking the file list against the sizes on SharePoint...",
    "Confronto con il backup esistente...": "Comparing with the existing backup...",
    "SharePoint non restituisce nessun file per la selezione: "
    "backup annullato per non archiviare tutto per errore":
        "SharePoint returns no files for the selection: "
        "backup cancelled so as not to archive everything by mistake",
    "Selezione: {count} file, {size}": "Selection: {count} files, {size}",
    "Verifica dei file su disco...": "Checking the files on disk...",
    "Pulizia e versioni...": "Cleanup and versions...",
    "Backup {label}: {downloaded} scaricati ({size}), {unchanged} invariati, {moved} spostati, "
    "{archived} versioni salvate in {versions}\\{label}":
        "Backup {label}: {downloaded} downloaded ({size}), {unchanged} unchanged, {moved} moved, "
        "{archived} versions saved in {versions}\\{label}",
    ", {errors} errori di download": ", {errors} download errors",
    "✗ {path} (eliminato su SharePoint o non più selezionato: spostato in {folder})":
        "✗ {path} (deleted on SharePoint or no longer selected: moved to {folder})",
    "✗ {path} (non presente su SharePoint: spostato in {folder})": "✗ {path} (not on SharePoint: moved to {folder})",
    "Nessun file da scaricare": "No files to download",
    "Da scaricare: {count} file, {size}": "To download: {count} files, {size}",
    'Spazio su disco insufficiente: servono {need}, liberi {free}. Seleziona meno cartelle, oppure usa una '
    'cartella di backup dentro OneDrive con "solo online": il tool scarica a blocchi e OneDrive libera il '
    "disco man mano.":
        "Not enough disk space: {need} needed, {free} free. Select fewer folders, or use a backup folder "
        'inside OneDrive with "online-only": the tool then downloads in batches and OneDrive frees the disk '
        "as it goes.",
    "Lo spazio libero ({free}) non basta per {need} tutti insieme: scarico a blocchi. Ogni file viene "
    "caricato su OneDrive e tolto dal disco prima di continuare.":
        "The free space ({free}) is not enough for {need} at once: downloading in batches. Each file is "
        "uploaded to OneDrive and removed from the disk before continuing.",
    "troppo grande per lo spazio sul disco ({size})": "too large for the disk space ({size})",
    "Disco quasi pieno: aspetto che OneDrive carichi i file copiati e liberi spazio...":
        "Disk almost full: waiting for OneDrive to upload the copied files and free up space...",
    "OneDrive ha liberato spazio ({free} liberi): riprendo a scaricare":
        "OneDrive freed up space ({free} free): resuming downloads",
    "OneDrive non ha liberato spazio negli ultimi {minutes} minuti: controlla che sia avviato e stia "
    "sincronizzando. Il prossimo backup riprenderà da qui.":
        "OneDrive has not freed any space in the last {minutes} minutes: check that it is running and "
        "syncing. The next backup will resume from here.",
    "In attesa di OneDrive: {count} file da caricare, {free} liberi sul disco...":
        "Waiting for OneDrive: {count} files to upload, {free} free on disk...",
    "ERRORE su {path}: {error}": "ERROR on {path}: {error}",
    " - versione precedente salvata": " - previous version saved",
    " - ATTENZIONE: {warning}": " - WARNING: {warning}",
    "il file scaricato non corrisponde all'hash di SharePoint (succede con alcuni file Office)":
        "the downloaded file does not match the SharePoint hash (this happens with some Office files)",
    "  connessione interrotta su {path}, riprendo da {position}":
        "  connection lost on {path}, resuming from {position}",
    "Eliminata la versione più vecchia: {name}": "Deleted the oldest version: {name}",
    "ERRORE eliminando {name}: {error}": "ERROR deleting {name}: {error}",
    "C'è già un backup in corso": "A backup is already running",
    'Nessuna cartella selezionata: premi "Connetti" e scegli cosa copiare':
        'No folder selected: press "Connect" and choose what to back up',
    "Scegli la cartella di backup.": "Choose the backup folder.",
    "Il link indica un'altra libreria o cartella ({target}): scegli cosa copiare e avvia di nuovo il backup":
        "The link points to a different library or folder ({target}): choose what to back up and run the "
        "backup again",
    # verifica di completezza
    "Verifica dell'elenco con le dimensioni delle cartelle su SharePoint...":
        "Checking the file list against the folder sizes on SharePoint...",
    "  {folder}: SharePoint dichiara {declared:,} byte, l'elenco {listed:,}: controllo le sottocartelle":
        "  {folder}: SharePoint reports {declared:,} bytes, the list {listed:,}: checking the subfolders",
    "  {path}: mancava nell'elenco di SharePoint, aggiunto": "  {path}: missing from the SharePoint list, added",
    "  {path}: in elenco ma non più su SharePoint, tolto": "  {path}: in the list but no longer on SharePoint, removed",
    "  {count} file mancanti o non aggiornati in {folder}: li scarico":
        "  {count} files missing or out of date in {folder}: downloading them",
    "MANCANTE: {path}": "MISSING: {path}",
    "NON VERIFICATA: {folder}": "NOT VERIFIED: {folder}",
    "NON ACCESSIBILE: {folder}: {count} elementi ({size}) esistono su SharePoint "
    "ma non sono visibili con il tuo account":
        "NOT ACCESSIBLE: {folder}: {count} items ({size}) exist on SharePoint "
        "but are not visible to your account",
    "NON ACCESSIBILE: {folder}: la dimensione su SharePoint differisce di {diff:+,} byte "
    "da quella dei file visibili":
        "NOT ACCESSIBLE: {folder}: the size on SharePoint differs by {diff:+,} bytes "
        "from that of the visible files",
    "ATTENZIONE: {count} elementi ({size}) in {folders} cartelle non sono visibili con il tuo account "
    "e non si possono copiare (elenco nel log)":
        "WARNING: {count} items ({size}) in {folders} folders are not visible to your account "
        "and cannot be copied (list in the log)",
    "VERIFICA OK: tutti i {count} file visibili ({size}) sono in {folder}, identici a SharePoint":
        "VERIFICATION OK: all {count} visible files ({size}) are in {folder}, identical to SharePoint",
    "VERIFICA NON SUPERATA: {count} file mancanti": "VERIFICATION FAILED: {count} files missing",
    ", {count} cartelle non verificabili": ", {count} folders could not be verified",
    " (elenco nel log e in {manifest})": " (list in the log and in {manifest})",
    # _FileList.csv
    "Percorso": "Path",
    "Dimensione (byte)": "Size (bytes)",
    "Modificato su SharePoint": "Modified on SharePoint",
    "Stato": "Status",
    "Verifica {label}": "Verification {label}",
    "MANCANTE": "MISSING",
    "{folder}/ (contenuto non visibile)": "{folder}/ (content not visible)",
    "NON ACCESSIBILE ({count} elementi)": "NOT ACCESSIBLE ({count} items)",
    # finestra
    "Non connesso": "Not connected",
    "Connesso come {account}": "Connected as {account}",
    "Origine: {target}": "Source: {target}",
    "Pronto": "Ready",
    "Libreria o cartella SharePoint": "SharePoint library or folder",
    "Cartella di backup": "Backup folder",
    "Sfoglia...": "Browse...",
    "Connetti": "Connect",
    "Cosa copiare": "What to back up",
    "Versioni da conservare": "Versions to keep",
    "Dopo l'upload su OneDrive lascia i file solo online (non occupano spazio sul PC)":
        "After the upload to OneDrive keep the files online-only (they use no space on this PC)",
    "Esegui backup": "Run backup",
    "Ferma": "Stop",
    "Backup automatico ogni giorno alle": "Automatic backup every day at",
    "Pianifica": "Schedule",
    "Rimuovi": "Remove",
    'Premi "Connetti" per leggere le cartelle della libreria': 'Press "Connect" to read the folders of the library',
    'Incolla qui sopra il link della libreria o della cartella (copiato dal browser) e premi "Connetti"':
        'Paste the link of the library or folder above (copied from the browser) and press "Connect"',
    "Il link indica un'altra libreria o cartella ({target}): scegli di nuovo cosa copiare":
        "The link points to a different library or folder ({target}): choose again what to back up",
    "Selezionati: {size}{free}{when}": "Selected: {size}{free}{when}",
    " - spazio libero su {drive}: {size}": " - free space on {drive}: {size}",
    " - dimensioni aggiornate alle {time:%H:%M}{day}": " - sizes updated at {time:%H:%M}{day}",
    " del {date:%d/%m}": " on {date:%Y-%m-%d}",
    "Seleziona almeno una cartella da copiare.": "Select at least one folder to back up.",
    "Avvio del backup...": "Starting the backup...",
    "Aggiornamento delle cartelle e delle dimensioni...": "Updating folders and sizes...",
    "Connesso: lettura delle cartelle e delle dimensioni...": "Connected: reading folders and sizes...",
    "Connesso come {account}: {count} elementi, dimensioni aggiornate":
        "Connected as {account}: {count} items, sizes updated",
    "Interrotto": "Stopped",
    "Cartelle non aggiornate: {error}": "Folders not updated: {error}",
    'Non connesso: premi "Connetti"': 'Not connected: press "Connect"',
    "ERRORE: {error}": "ERROR: {error}",
    "Download: {done} di {total}": "Downloading: {done} of {total}",
    "Orario non valido (usa HH:MM, es. 13:00)": "Invalid time (use HH:MM, e.g. 13:00)",
    "(attivo)": "(active)",
    "(non pianificato)": "(not scheduled)",
    "Backup in corso: interromperlo e uscire?": "Backup in progress: stop it and exit?",
    # backup pianificato
    "Il backup pianificato non è partito perché la sessione SharePoint è scaduta.\n"
    'Apri SPVault e premi "Connetti".':
        "The scheduled backup did not start because the SharePoint session has expired.\n"
        'Open SPVault and press "Connect".',
    "Backup SharePoint non riuscito:\n{error}": "SharePoint backup failed:\n{error}",
    "Il backup pianificato non è partito: SPVault non è ancora configurato.\n"
    "Apri SPVault, incolla il link della libreria o della cartella e scegli la cartella di backup.":
        "The scheduled backup did not start: SPVault is not configured yet.\n"
        "Open SPVault, paste the link of the library or folder and choose the backup folder.",
    # cartelle nuove e pianificazione
    "Nuova cartella su SharePoint: {name}": "New folder on SharePoint: {name}",
    " (aggiunta al backup)": " (added to the backup)",
    "  - NUOVA": "  - NEW",
    "Copia anche le cartelle nuove che compariranno su SharePoint":
        "Also back up new folders that appear on SharePoint",
    "Backup giornaliero di SPVault": "SPVault daily backup",
    "Backup pianificato ogni giorno alle {time}. Se a quell'ora il PC è spento, parte appena lo riaccendi.":
        "Backup scheduled every day at {time}. If the PC is off at that time, it starts as soon as "
        "you turn it back on.",
}


def tr(text: str, **kw) -> str:
    """Testo nella lingua attiva. `text` è l'originale italiano (chiave di EN) con eventuali
    {segnaposto} riempiti da str.format(**kw); senza traduzione resta in italiano."""
    if LANG == "en":
        text = EN.get(text, text)
    return text.format(**kw) if kw else text


def windows_ui_language() -> int:
    """LANGID della lingua dell'interfaccia di Windows (es. 0x0410 = italiano)."""
    return ctypes.windll.kernel32.GetUserDefaultUILanguage()


def resolve_language(choice: str) -> str:
    """"it"/"en" dalla scelta in config. "auto" (o un valore sconosciuto): italiano se Windows
    è in italiano, altrimenti inglese (anche fuori da Windows o se la lettura non riesce)."""
    if choice in ("it", "en"):
        return choice
    try:
        return "it" if windows_ui_language() & 0x3FF == 0x10 else "en"  # LANG_ITALIAN
    except Exception:
        return "en"


def set_language(choice: str):
    global LANG
    LANG = resolve_language(choice)


def fmt_count(n: int) -> str:
    """Numero con separatore delle migliaia: 1.234 in italiano, 1,234 in inglese."""
    s = f"{n:,}"
    return s.replace(",", ".") if LANG == "it" else s


# ----------------------------------------------------------------------- utilità

def lp(p) -> str:
    """Percorso con prefisso \\\\?\\ per superare il limite di 260 caratteri di Windows."""
    s = os.path.abspath(p)
    if os.name != "nt" or s.startswith("\\\\?\\"):
        return s
    return "\\\\?\\UNC\\" + s[2:] if s.startswith("\\\\") else "\\\\?\\" + s


def file_size(p) -> int | None:
    try:
        return os.stat(lp(p)).st_size  # stat non scarica i file "solo online" di OneDrive
    except FileNotFoundError:
        return None


def fmt_size(n: float) -> str:
    if n < 1024:
        return f"{n:.0f} B"
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1024
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"


def parse_time(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


@dataclass(frozen=True)
class Link:
    """Cosa indica il link incollato: sito, libreria ed eventuale cartella, oppure un link di
    condivisione con token (libreria e cartella si sanno solo dopo l'accesso, con l'API "shares")."""
    site: str          # es. https://contoso.sharepoint.com/sites/Team
    library: str = ""  # percorso della libreria, es. /sites/Team/Shared Documents (vuoto: link con token)
    folder: str = ""   # cartella dentro la libreria, es. Projects/2026 (vuoto: tutta la libreria)
    share: str = ""    # link di condivisione con token, es. https://contoso.sharepoint.com/:f:/s/Team/Eabc...

    @property
    def web_url(self) -> str:
        """Indirizzo della libreria o della cartella, come il webUrl di SharePoint."""
        origin = "/".join(self.site.split("/")[:3])
        return origin + quote("/".join(p for p in (self.library, self.folder) if p))


def parse_link(url: str) -> Link:
    """Link incollato dall'utente -> Link. Accetta l'indirizzo di una libreria o di una sua cartella
    (anche la barra degli indirizzi di una vista: .../Forms/AllItems.aspx?id=<percorso>, o RootFolder=
    negli indirizzi vecchi), i link di "Copia collegamento" (/:f:/r/<percorso> e /:f:/s/<sito>/<token>),
    OneDrive for Business (/personal/<utente>/...) e le librerie del sito principale (/<libreria>/...)."""
    text = url.strip()
    if not text:
        raise ValueError(tr('Incolla il link della libreria o della cartella SharePoint da copiare (dalla barra '
                            'degli indirizzi del browser o da "Copia collegamento"), '
                            "es. https://<tenant>.sharepoint.com/sites/<sito>/<libreria>/<cartella>"))
    invalid = tr("Indirizzo non valido: serve il link https:// di una libreria o cartella SharePoint copiato "
                 "dal browser, es. https://<tenant>.sharepoint.com/sites/<sito>/<libreria>/<cartella>")
    try:
        u = urlparse(text)
        host = (u.hostname or "").lower()
    except ValueError:
        raise ValueError(invalid) from None
    if u.scheme.lower() != "https" or not SHAREPOINT_HOST.search(host):
        raise ValueError(invalid)
    origin = f"https://{host}"
    segs = [unquote(p) for p in u.path.split("/") if p]
    if segs and re.fullmatch(r":\w:", segs[0]):  # "Copia collegamento": /:<tipo>:/<r|s|t|p|g>/...
        kind, rest = (segs[1].lower() if len(segs) > 1 else ""), segs[2:]
        if kind in SHARE_KINDS and len(rest) >= (1 if kind == "g" else 2):  # ultimo pezzo = token
            site = origin + "".join("/" + quote(p) for p in SHARE_KINDS[kind] + rest[:-1])
            return Link(site, share=text.split("#")[0])
        if kind != "r":  # /r/ = percorso diretto, si legge come un indirizzo normale
            raise ValueError(invalid)
        segs = rest
    else:  # vista di una cartella: il percorso è nel parametro id (o RootFolder), già decodificato
        query = {k.lower(): v for k, v in parse_qsl(u.query)}
        for key in ("id", "rootfolder"):
            if query.get(key, "").startswith("/"):
                segs = [p for p in query[key].split("/") if p]
                break
    site_segs, rest = (segs[:2], segs[2:]) if segs and segs[0].lower() in SITE_KINDS else ([], segs)
    if len(site_segs) == 1:
        raise ValueError(invalid)
    if not rest or rest[0].startswith("_"):  # solo il sito o una sua pagina (_layouts/...)
        if not site_segs or site_segs[0].lower() != "personal":
            raise ValueError(tr("Il link è di un sito, non di una libreria: apri la libreria o la cartella da "
                                "copiare (es. Documenti) e copia il link dalla barra degli indirizzi"))
        rest = ["Documents"]  # OneDrive for Business: la libreria è sempre /personal/<utente>/Documents
    folder = rest[1:]
    if folder and folder[0].lower() == "forms":  # vista della libreria: .../Forms/AllItems.aspx
        folder = []
    site = origin + "".join("/" + quote(p) for p in site_segs)
    return Link(site, "/" + "/".join(site_segs + rest[:1]), "/".join(folder))


def set_online_only(p: Path):
    """Come "Libera spazio" di OneDrive: il file resta nel cloud e sparisce dal disco
    locale dopo l'upload (attributo Unpinned). Nessun effetto fuori da OneDrive."""
    if os.name != "nt":
        return
    k32 = ctypes.windll.kernel32
    k32.GetFileAttributesW.restype = ctypes.c_uint32
    attrs = k32.GetFileAttributesW(lp(p))
    if attrs != 0xFFFFFFFF:
        k32.SetFileAttributesW(lp(p), (attrs & ~0x80000) | 0x100000)  # -PINNED +UNPINNED


def is_online_only(p) -> bool:
    """File "solo online": OneDrive lo ha sincronizzato col cloud e lo ha tolto dal disco."""
    if os.name != "nt":
        return False
    k32 = ctypes.windll.kernel32
    k32.GetFileAttributesW.restype = ctypes.c_uint32
    attrs = k32.GetFileAttributesW(lp(p))
    return attrs != 0xFFFFFFFF and bool(attrs & (0x400000 | 0x1000))  # RECALL_ON_DATA_ACCESS | OFFLINE


def onedrive_roots() -> list[str]:
    """Cartelle sincronizzate da OneDrive: quelle personali/aziendali e le librerie SharePoint
    (elencate da OneDrive nel registro, anche se stanno fuori dalla cartella OneDrive)."""
    roots = [os.environ.get(k) for k in ("OneDriveCommercial", "OneDriveConsumer", "OneDrive")]
    with contextlib.suppress(ImportError, OSError):
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\SyncEngines\Providers\OneDrive") as providers:
            for i in range(winreg.QueryInfoKey(providers)[0]):
                with contextlib.suppress(OSError), winreg.OpenKey(providers, winreg.EnumKey(providers, i)) as key:
                    roots.append(winreg.QueryValueEx(key, "MountPoint")[0])
    return [os.path.normcase(os.path.abspath(r)).rstrip("\\/") for r in roots if r]


def in_onedrive(path) -> bool:
    p = os.path.normcase(os.path.abspath(path))
    return any(p == r or p.startswith(r + os.sep) for r in onedrive_roots())


def label_key(name: str):
    m = LABEL_RE.match(name)
    return m.group(1), int(m.group(2))


def next_label(root: Path) -> str:
    """Etichetta del backup: data di oggi + numero di revisione del giorno."""
    today = date.today().isoformat()
    used = [0]
    for sub in (VERSIONS_DIR, LOG_DIR):
        with contextlib.suppress(FileNotFoundError):
            for name in os.listdir(lp(root / sub)):
                m = LABEL_RE.match(name)
                if m and m.group(1) == today:
                    used.append(int(m.group(2)))
    return f"{today}_r{max(used) + 1}"


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    with contextlib.suppress(OSError, ValueError):  # utf-8-sig: accetta anche file salvati con BOM
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig")))
    chosen = installer_language()
    if chosen and chosen != cfg["installer_language"]:  # scelta nuova nell'installer: vale una volta,
        cfg.update(language=chosen, installer_language=chosen)  # poi comanda la scelta nella finestra
    return cfg


def installer_language() -> str | None:
    """Lingua scelta nell'installer MSI (HKCU\\Software\\SPVault, valore Language)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\SPVault") as key:
            value = winreg.QueryValueEx(key, "Language")[0]
    except (ImportError, OSError):
        return None
    return value if value in LANGUAGES else None


def merge_items(cfg: dict, items: list[dict]) -> list[dict]:
    """Aggiorna in cfg l'elenco delle cartelle di primo livello e restituisce quelle nuove
    (comparse dopo l'ultima lettura). Con "include_new" le aggiunge alla selezione, se il
    backup è già configurato. Ogni elemento ricorda quando è comparso (first_seen)."""
    previous = {i["id"]: i for i in cfg["known_items"]}
    now = time.time()
    new = [i for i in items if previous and i["id"] not in previous]
    for i in items:
        i["first_seen"] = previous[i["id"]].get("first_seen", 0) if i["id"] in previous else (
            now if previous else 0)
    ids = {i["id"] for i in items}
    selection = [s for s in cfg["selection"] if s in ids]
    if cfg.get("include_new", True) and selection:
        selection += [i["id"] for i in new if i["id"] not in selection]
    cfg.update(known_items=items, items_updated=now, selection=selection)
    return new


def apply_target(cfg: dict, key: str) -> bool:
    """Registra in cfg la libreria/cartella indicata dal link ("drive|cartella"). Se è diversa da quella
    già registrata azzera selezione ed elenco delle cartelle, per non mescolare i backup; la prima volta
    (anche con una configurazione di versioni precedenti) la registra e basta. True se è cambiata."""
    changed = bool(cfg.get("target")) and cfg["target"] != key
    if changed:
        cfg.update(selection=[], known_items=[], items_updated=0)
    cfg["target"] = key
    return changed


def is_new(item: dict) -> bool:
    """Comparsa su SharePoint negli ultimi 7 giorni (le cartelle della prima lettura no)."""
    return bool(item.get("first_seen")) and time.time() - item["first_seen"] < 7 * 86400


def task_xml(command: str, arguments: str, hhmm: str) -> str:
    """Attività pianificata giornaliera. StartWhenAvailable: se all'orario previsto il PC era
    spento parte appena possibile; nessun limite di durata, anche a batteria, con la rete."""
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{escape(tr("Backup giornaliero di SPVault"))}</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{date.today().isoformat()}T{hhmm}:00</StartBoundary>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>{escape(command)}</Command><Arguments>{escape(arguments)}</Arguments></Exec>
  </Actions>
</Task>
"""


def save_config(cfg: dict):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


class QuickXorHash:
    """L'hash che OneDrive/SharePoint calcola per ogni file (file.hashes.quickXorHash).

    Il byte n-esimo viene messo in XOR nello stato da 160 bit alla posizione
    (n * 11) mod 160: la posizione si ripete ogni 160 byte, quindi basta fare
    lo XOR di tutti i blocchi da 160 byte e distribuirli alla fine.
    """
    BLOCK = 160

    def __init__(self):
        self.acc = 0  # XOR di tutti i blocchi da 160 byte (intero little-endian)
        self.length = 0

    def update(self, data: bytes):
        offset = self.length % self.BLOCK
        buf = bytes(offset) + data + bytes(-(offset + len(data)) % self.BLOCK)
        x = int.from_bytes(buf, "little")
        blocks = len(buf) // self.BLOCK
        while blocks > 1:  # XOR della metà bassa con la metà alta finché resta un blocco
            half = blocks // 2
            shift = half * self.BLOCK * 8
            x = (x & ((1 << shift) - 1)) ^ (x >> shift)
            blocks -= half
        self.acc ^= x
        self.length += len(data)

    def digest(self) -> str:
        mask = (1 << 160) - 1
        state = 0
        for i, b in enumerate(self.acc.to_bytes(self.BLOCK, "little")):
            if b:
                v = b << (i * 11 % 160)
                state ^= (v | (v >> 160)) & mask  # rotazione su 160 bit
        out = bytearray(state.to_bytes(20, "little"))
        for i, b in enumerate(self.length.to_bytes(8, "little")):
            out[12 + i] ^= b
        return base64.b64encode(out).decode()


# ----------------------------------------------------------------- accesso e API

LOGIN_FORM = "input[type=email]:visible, input[type=password]:visible, #tilesHolder:visible"


def _shows_login_form(page, playwright_error) -> bool:
    """La pagina di Microsoft chiede email, password o la scelta dell'account?"""
    try:
        return page.locator(LOGIN_FORM).count() > 0
    except playwright_error:  # pagina in navigazione: si riprova al giro dopo
        return False


def browser_login(site_url: str, interactive: bool, log) -> tuple[list[dict], str]:
    """Apre il sito con il profilo browser dedicato e restituisce cookie di sessione e
    User-Agent del browser (le API v2.0 rifiutano i cookie se lo User-Agent non è di un
    browser). interactive=False: browser invisibile, funziona solo se il login è valido."""
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError:
        raise RuntimeError(tr("Manca Playwright: esegui  pip install playwright")) from None
    host = urlparse(site_url).hostname
    with sync_playwright() as pw:
        ctx, errors = None, []
        for channel in ("chrome", "msedge"):
            try:
                ctx = pw.chromium.launch_persistent_context(
                    str(PROFILE_DIR), channel=channel, headless=not interactive, no_viewport=True)
                break
            except PlaywrightError as e:
                errors.append(f"{channel}: {str(e).splitlines()[0]}")
        if ctx is None:
            raise RuntimeError(tr("Impossibile avviare Chrome o Edge ({errors})", errors="; ".join(errors)))
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            if interactive:
                log(tr('Completa l\'accesso nella finestra del browser (spunta "Resta connesso")'))
            page.goto(site_url, wait_until="domcontentloaded", timeout=60_000)
            deadline = time.time() + (600 if interactive else 30)
            while time.time() < deadline:
                if urlparse(page.url).hostname == host:
                    cookies = ctx.cookies(f"https://{host}")
                    if any(c["name"] == "FedAuth" for c in cookies):
                        user_agent = page.evaluate("navigator.userAgent")
                        return cookies, user_agent.replace("HeadlessChrome", "Chrome")
                elif not interactive and _shows_login_form(page, PlaywrightError):
                    break  # Microsoft chiede le credenziali: inutile aspettare in background
                page.wait_for_timeout(500)
        except PlaywrightError as e:
            raise LoginRequired(tr("Accesso non completato ({error})", error=str(e).splitlines()[0])) from None
        finally:
            with contextlib.suppress(Exception):
                ctx.close()
    raise LoginRequired(tr('Serve di nuovo il login: premi "Connetti" e accedi nel browser'))


class SharePoint:
    """Chiamate alle API di SharePoint con i cookie della sessione del browser."""

    def __init__(self, url: str, log):
        self.link = parse_link(url)
        self.site = self.link.site
        # con un link di condivisione il login passa dal link stesso: il browser lo riscatta
        # (serve agli ospiti per avere accesso alla cartella)
        self.login_url = self.link.share or self.site
        self.log = log
        self.drive_id = None
        self.base_id = "root"   # cartella da copiare: "root" = tutta la libreria
        self.target_name = ""   # es. "Shared Documents › Projects", mostrato nella finestra
        self._cookies: list[dict] = []
        self._user_agent = ""
        self._gen = 0  # cambia a ogni rinnovo della sessione
        self._last_login = 0.0
        self._lock = threading.Lock()
        self._local = threading.local()  # una requests.Session per thread

    @property
    def drive(self) -> str:
        return f"{self.site}/_api/v2.0/drives/{self.drive_id}"

    @property
    def base(self) -> str:
        """Url della cartella indicata dal link (la radice della libreria se il link è della libreria)."""
        return f"{self.drive}/root" if self.base_id == "root" else f"{self.drive}/items/{self.base_id}"

    @property
    def target_key(self) -> str:
        """Identifica libreria e cartella da copiare (config["target"])."""
        return f"{self.drive_id}|{self.base_id}"

    def connect(self, interactive: bool):
        session = browser_login(self.login_url, interactive, self.log)
        with self._lock:
            (self._cookies, self._user_agent), self._last_login = session, time.time()
            self._gen += 1
        self._resolve_target()

    def _session(self) -> requests.Session:
        loc = self._local
        if getattr(loc, "gen", None) != self._gen:
            s = requests.Session()
            s.headers["User-Agent"] = self._user_agent
            for c in self._cookies:
                s.cookies.set(c["name"], c["value"], domain=c["domain"], path=c["path"])
            loc.session, loc.gen = s, self._gen
        return loc.session

    def _renew(self, gen: int) -> bool:
        """Rinnova la sessione scaduta. False = sessione appena rinnovata, quindi il
        401/403 è un vero accesso negato."""
        with self._lock:
            if self._gen != gen:
                return True  # l'ha già rinnovata un altro thread
            if time.time() - self._last_login < 120:
                return False
            self.log(tr("Sessione scaduta: la rinnovo..."))
            (self._cookies, self._user_agent) = browser_login(self.login_url, False, self.log)
            self._last_login = time.time()
            self._gen += 1
            return True

    def get(self, url: str, *, stream=False, headers=None) -> requests.Response:
        for attempt in range(6):
            gen = self._gen
            try:
                r = self._session().get(url, stream=stream, headers=headers, timeout=(20, 120))
            except requests.RequestException:
                if attempt == 5:
                    raise
                time.sleep(2 ** attempt)
                continue
            if r.status_code in (401, 403) and attempt < 5 and self._renew(gen):
                r.close()
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 5:
                r.close()
                try:
                    wait = int(r.headers.get("Retry-After", ""))
                except ValueError:
                    wait = 2 ** attempt
                time.sleep(min(wait, 120))
                continue
            if not r.ok:
                try:
                    msg = r.json()["error"]["message"]
                    msg = msg.get("value", msg) if isinstance(msg, dict) else msg
                except Exception:
                    msg = r.text[:200]
                raise HttpError(r.status_code, msg)
            return r

    def get_json(self, url: str, accept="application/json", headers=None) -> dict:
        return self.get(url, headers={"Accept": accept, **(headers or {})}).json()

    def _resolve_target(self):
        """Libreria (drive) e cartella da copiare indicate dal link: self.drive_id, self.base_id
        e self.target_name. La libreria si trova tra quelle del sito confrontando l'indirizzo
        (webUrl), la cartella con il suo percorso dentro la libreria."""
        link = self.link
        if link.share:
            return self._resolve_share(link.share)
        try:
            drives = self.get_json(f"{self.site}/_api/v2.0/drives?$select=id,name,webUrl")["value"]
        except HttpError as e:
            if e.status not in (401, 403):
                raise
            # l'account non vede l'elenco delle librerie (es. ospite con accesso a una sola
            # cartella): l'API "shares" accetta anche l'indirizzo diretto della cartella
            return self._resolve_share(link.web_url)
        for d in drives:
            path = unquote(urlparse(d.get("webUrl", "")).path).rstrip("/")
            if path.casefold() == link.library.casefold():
                break
        else:
            raise RuntimeError(tr("Libreria {library} non trovata (disponibili: {available})",
                                  library=link.library, available=", ".join(d["name"] for d in drives)))
        self.drive_id, self.base_id = d["id"], "root"
        names = [d.get("name") or link.library.rsplit("/", 1)[-1]]
        if link.folder:
            rel = "/".join(quote(p, safe="") for p in link.folder.split("/"))
            try:
                item = self.get_json(f"{self.drive}/root:/{rel}?$select=id,name,folder,file")
            except HttpError as e:
                if e.status != 404:
                    raise
                raise RuntimeError(tr("Cartella {folder} non trovata in {library}: controlla il link",
                                      folder=link.folder, library=names[0])) from None
            self._check_folder(item)
            self.base_id = item["id"]
            names += link.folder.split("/")
        self.target_name = " › ".join(names)

    def _resolve_share(self, url: str):
        """Cartella indicata da un link di condivisione (o da un indirizzo diretto), con l'API
        GET /shares/u!<link in base64url>/driveItem; se serve il link viene riscattato."""
        token = "u!" + base64.urlsafe_b64encode(url.encode("utf-8")).decode().rstrip("=")
        try:
            item = self.get_json(f"{self.site}/_api/v2.0/shares/{token}/driveItem",
                                 headers={"Prefer": "redeemSharingLinkIfNecessary"})
        except HttpError as e:
            if e.status not in (400, 401, 403, 404):
                raise
            raise RuntimeError(tr("Link di condivisione non valido, scaduto o non accessibile con questo "
                                  "account ({error})", error=e)) from None
        self._check_folder(item)
        self.drive_id, self.base_id = item["parentReference"]["driveId"], item["id"]
        names = [item.get("name", "?")]
        with contextlib.suppress(ValueError):  # percorso leggibile dall'indirizzo della cartella
            where = parse_link(item.get("webUrl", ""))
            names = [where.library.rsplit("/", 1)[-1], *filter(None, where.folder.split("/"))]
        self.target_name = " › ".join(names)

    @staticmethod
    def _check_folder(item: dict):
        if "folder" not in item and "root" not in item:
            raise RuntimeError(tr("Il link è di un file, non di una cartella: copia il link della cartella "
                                  "che lo contiene"))

    def account(self) -> str:
        try:
            me = self.get_json(f"{self.site}/_api/web/currentuser?$select=Email,Title",
                               accept="application/json;odata=nometadata")
        except HttpError:  # es. ospite che vede solo una cartella del sito
            return "?"
        return me.get("Email") or me.get("Title") or "?"

    def children(self, item_id: str):
        url = (f"{self.drive}/items/{item_id}/children?$top=1000"
               "&$select=id,name,size,file,folder,package,cTag,lastModifiedDateTime")
        while url:
            data = self.get_json(url)
            yield from data.get("value", [])
            url = data.get("@odata.nextLink")

    def top_items(self) -> list[dict]:
        """Contenuto della cartella indicata dal link: le caselle di "Cosa copiare"."""
        data = self.get_json(f"{self.base}/children?$top=1000&$select=id,name,size,folder,file")
        return sorted(({"id": c["id"], "name": c["name"], "size": c.get("size", 0),
                        "folder": "folder" in c} for c in data["value"]),
                      key=lambda i: (not i["folder"], i["name"].casefold()))


def no_step(text: str):
    """Segnaposto per `step`: la fase in corso, mostrata dalla finestra."""


def connect(sp: SharePoint, interactive_allowed: bool, log, step=no_step):
    step(tr("Accesso a SharePoint..."))
    try:
        sp.connect(interactive=False)
    except LoginRequired:
        if not interactive_allowed:
            raise
        log(tr("Serve l'accesso: apro il browser"))
        step(tr("Accedi nella finestra del browser che si è aperta..."))
        sp.connect(interactive=True)


# --------------------------------------------------------------- stato e backup

@dataclass
class RemoteFile:
    id: str
    path: str               # relativo alla libreria, separatore "/"
    size: int
    hash: str | None        # quickXorHash calcolato da SharePoint
    ctag: str | None        # cambia solo quando cambia il contenuto
    mtime: float | None


@dataclass
class BackedUp:
    id: str
    path: str
    size: int
    hash: str | None
    ctag: str | None
    local_size: int | None = None

    def same_content(self, f: RemoteFile) -> bool:
        if self.hash and f.hash:
            return self.hash == f.hash and self.size == f.size
        return self.ctag == f.ctag and self.size == f.size


class State:
    """Stato locale (SQLite): albero della libreria + file presenti nel backup."""

    def __init__(self, drive_id: str, dest: Path):
        key = f"{drive_id}|{os.path.normcase(os.path.abspath(dest))}"
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(APP_DIR / f"state_{hashlib.sha1(key.encode()).hexdigest()[:12]}.sqlite")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, parent TEXT, name TEXT,
                kind INTEGER, size INTEGER, hash TEXT, ctag TEXT, mtime REAL);
            CREATE TABLE IF NOT EXISTS backup (id TEXT PRIMARY KEY, path TEXT, size INTEGER,
                hash TEXT, ctag TEXT, local_size INTEGER);
        """)
        with contextlib.suppress(sqlite3.OperationalError):  # database di versioni precedenti
            self.db.execute("ALTER TABLE backup ADD COLUMN local_size INTEGER")

    def meta(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, str(value)))

    def backed_up(self) -> dict[str, BackedUp]:
        return {r[0]: BackedUp(*r) for r in
                self.db.execute("SELECT id, path, size, hash, ctag, local_size FROM backup")}

    def record(self, f: "RemoteFile | BackedUp", local_size: int | None):
        """local_size: dimensione del file su disco (di solito uguale a quella su SharePoint)."""
        self.db.execute("INSERT OR REPLACE INTO backup VALUES (?, ?, ?, ?, ?, ?)",
                        (f.id, f.path, f.size, f.hash, f.ctag, local_size))

    def forget(self, file_id: str):
        self.db.execute("DELETE FROM backup WHERE id=?", (file_id,))


def update_tree(sp: SharePoint, state: State, log, check_cancel, step=no_step):
    """Aggiorna l'albero locale della libreria con l'API delta. Se il link è di una cartella e
    l'account non può leggere tutta la libreria (es. ospite con un link di condivisione), legge
    solo quella cartella, sottocartella per sottocartella."""
    try:
        link = state.meta("delta_link")
        if link and time.time() - float(state.meta("last_full_scan", 0)) < FULL_SCAN_DAYS * 86400:
            try:
                return _read_delta(sp, state, link, False, log, check_cancel, step)
            except HttpError as e:
                if e.status not in (400, 404, 410):
                    raise
                log(tr("Elenco modifiche scaduto: rileggo tutta la libreria"))
        _read_delta(sp, state, f"{sp.drive}/root/delta?$top=1000&$select={DELTA_SELECT}",
                    True, log, check_cancel, step)
    except HttpError as e:
        if sp.base_id == "root" or e.status not in (401, 403, 404):
            raise
        log(tr("L'account non può leggere tutta la libreria: leggo solo la cartella {folder}",
               folder=sp.target_name))
        _read_folder(sp, state, log, check_cancel, step)


def _read_folder(sp, state, log, check_cancel, step=no_step):
    """Albero della sola cartella del link con l'API "children" (una richiesta per cartella).
    Senza elenco delle modifiche: la volta dopo si riprova con il delta dell'intera libreria."""
    rows, stack = [], [sp.base_id]
    while stack:
        check_cancel()
        folder = stack.pop()
        for it in sp.children(folder):
            kind = (KIND_PACKAGE if "package" in it else KIND_FOLDER if "folder" in it else KIND_FILE)
            mtime = it.get("lastModifiedDateTime")
            rows.append((it["id"], folder, it.get("name", ""), kind, it.get("size", 0),
                         it.get("file", {}).get("hashes", {}).get("quickXorHash"),
                         it.get("cTag"), parse_time(mtime) if mtime else None))
            if kind == KIND_FOLDER:
                stack.append(it["id"])
        step(tr("Lettura della cartella: {count} elementi", count=fmt_count(len(rows))))
    with state.db:
        state.db.execute("DELETE FROM items")
        state.db.executemany("INSERT OR REPLACE INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        state.set_meta("delta_link", "")  # l'albero non è più quello del delta: la prossima lettura è completa
    log(tr("Cartella letta: {count} elementi", count=len(rows)))


def _read_delta(sp, state, url, full, log, check_cancel, step=no_step):
    log(tr("Lettura completa della libreria (la prima volta richiede qualche minuto)..."
           if full else "Lettura delle modifiche su SharePoint..."))
    step(tr("Lettura della libreria..." if full else "Lettura delle modifiche su SharePoint..."))
    upserts, deletes, root_id, count, pages = {}, set(), None, 0, 0
    while True:
        check_cancel()
        data = sp.get_json(url)
        for it in data.get("value", []):
            if "deleted" in it:
                deletes.add(it["id"])
                upserts.pop(it["id"], None)
                continue
            if "root" in it:
                root_id = it["id"]
            kind = (KIND_PACKAGE if "package" in it else
                    KIND_FOLDER if ("folder" in it or "root" in it) else KIND_FILE)
            mtime = it.get("lastModifiedDateTime")
            upserts[it["id"]] = (
                it["id"], it.get("parentReference", {}).get("id"), it.get("name", ""), kind,
                it.get("size", 0), it.get("file", {}).get("hashes", {}).get("quickXorHash"),
                it.get("cTag"), parse_time(mtime) if mtime else None)
            deletes.discard(it["id"])
        count += len(data.get("value", []))
        pages += 1
        step(tr("Lettura della libreria: {count} elementi" if full else "Lettura delle modifiche: {count} elementi",
                count=fmt_count(count)))
        if pages % 25 == 0:
            log(tr("  ... {count} elementi letti", count=count))
        if "@odata.deltaLink" in data:
            delta_link = data["@odata.deltaLink"]
            break
        url = data["@odata.nextLink"]
    with state.db:  # tutto in una transazione: se si interrompe, si riparte dal link precedente
        if full:
            state.db.execute("DELETE FROM items")
        state.db.executemany("DELETE FROM items WHERE id=?", [(i,) for i in deletes])
        state.db.executemany("INSERT OR REPLACE INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                             upserts.values())
        if root_id:
            state.set_meta("root_id", root_id)
        state.set_meta("delta_link", delta_link)
        if full:
            state.set_meta("last_full_scan", time.time())
    log(tr("Libreria letta: {count} elementi" if full else "Modifiche lette: {count} elementi", count=count))


def selected_files(state: State, selection: list[str]):
    """File e cartelle sotto gli elementi di primo livello selezionati (per id,
    così una cartella rinominata su SharePoint resta selezionata).
    Restituisce file, cartelle, blocchi OneNote saltati [(percorso, dimensione)] e
    {id selezionato: percorso}."""
    rows = state.db.execute("SELECT id, parent, name, kind, size, hash, ctag, mtime FROM items").fetchall()
    by_id = {r[0]: r for r in rows}
    children = defaultdict(list)
    for r in rows:
        children[r[1]].append(r)
    missing = [i for i in selection if i not in by_id]
    if missing:
        raise RuntimeError(tr('Alcune cartelle selezionate non esistono più su SharePoint: '
                              'premi "Connetti" e rivedi la selezione'))
    files, dirs, skipped = {}, set(), []
    roots = {i: by_id[i][2] for i in selection}
    stack = [(by_id[i], by_id[i][2]) for i in selection]
    while stack:
        (item_id, _, _, kind, size, qxh, ctag, mtime), rel = stack.pop()
        if kind == KIND_FOLDER:
            dirs.add(rel)
            stack.extend((c, f"{rel}/{c[2]}") for c in children[item_id])
        elif kind == KIND_FILE:
            files[item_id] = RemoteFile(item_id, rel, size, qxh, ctag, mtime)
        else:
            skipped.append((rel, size))
    return files, dirs, skipped, roots


class Backup:
    def __init__(self, sp: SharePoint, cfg: dict, log, progress, cancel: threading.Event, step=no_step):
        self.sp, self.progress, self.cancel, self.step = sp, progress, cancel, step
        self.root = Path(cfg["dest"])
        self.current = self.root / CURRENT_DIR
        self.versions = self.root / VERSIONS_DIR
        self.selection = list(cfg["selection"])
        self.keep = max(1, int(cfg["keep_versions"]))
        self.online_only = bool(cfg["online_only"])
        self.label = next_label(self.root)
        self.complete = False  # True solo se la verifica finale trova tutto
        self.hidden: list[tuple[str, int, int]] = []  # (cartella, elementi, byte) non visibili
        self._ui_log = log
        self._file = None
        self._file_lock = threading.Lock()
        self._abort = threading.Event()  # errore bloccante in un thread di download
        self._written: list[Path] = []   # file copiati, da caricare su OneDrive (scarico a blocchi)
        self._written_lock = threading.Lock()

    def log(self, msg: str, ui=True):
        if ui:
            self._ui_log(msg)
        if self._file:
            with self._file_lock:
                self._file.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")
                self._file.flush()

    def check_cancel(self):
        if self.cancel.is_set() or self._abort.is_set():
            raise Cancelled

    def _cur(self, rel: str) -> Path:
        return self.current.joinpath(*rel.split("/"))

    def run(self) -> str:
        os.makedirs(lp(self.root / LOG_DIR), exist_ok=True)
        with open(lp(self.root / LOG_DIR / f"{self.label}.log"), "a", encoding="utf-8") as self._file:
            self.log(tr("Backup {label} in {folder}", label=self.label, folder=self.root))
            try:
                summary = self._run()
            except Exception as e:
                self.log(tr("INTERROTTO: {error}", error=e or type(e).__name__), ui=False)
                raise
            finally:
                with contextlib.suppress(OSError):
                    self._prune(self.root / LOG_DIR, KEEP_LOGS, dirs=False)
            self.log(summary, ui=False)  # a video lo mostra chi ha avviato il backup
        self._file = None
        return summary

    def _run(self) -> str:
        state = State(self.sp.drive_id, self.root)
        stats = Counter()
        try:
            update_tree(self.sp, state, self.log, self.check_cancel, self.step)
            files, dirs, skipped, roots = selected_files(state, self.selection)
            for rel, _ in skipped:
                self.log(tr("Salto {path} (blocco appunti OneNote, non è un file)", path=rel))
            self.step(tr("Verifica dell'elenco con le dimensioni su SharePoint..."))
            unchecked = self._check_remote(state, files, dirs, skipped, roots)
            self.step(tr("Confronto con il backup esistente..."))
            backed = state.backed_up()
            if not files and backed:
                raise RuntimeError(tr("SharePoint non restituisce nessun file per la selezione: "
                                      "backup annullato per non archiviare tutto per errore"))
            self.log(tr("Selezione: {count} file, {size}", count=len(files),
                        size=fmt_size(sum(f.size for f in files.values()))))

            self._archive_removed(state, files, backed, stats)
            to_download = self._plan(state, files, backed, stats)
            state.db.commit()
            self._download_all(state, to_download, stats)
            self.check_cancel()
            self.step(tr("Verifica dei file su disco..."))
            verdict = self._check_local(state, files, unchecked, stats)
            self.step(tr("Pulizia e versioni..."))
            keep = {p for (p,) in state.db.execute("SELECT path FROM backup")}
            keep |= {f.path for f in files.values()}
            self._sync_local(dirs, keep, stats)
            self._prune(self.versions, self.keep, dirs=True)
        finally:
            state.db.commit()
            state.db.close()
        return (tr("Backup {label}: {downloaded} scaricati ({size}), {unchanged} invariati, {moved} spostati, "
                   "{archived} versioni salvate in {versions}\\{label}",
                   label=self.label, downloaded=stats["scaricati"], size=fmt_size(stats["byte"]),
                   unchanged=stats["invariati"], moved=stats["spostati"], archived=stats["archiviati"],
                   versions=VERSIONS_DIR)
                + (tr(", {errors} errori di download", errors=stats["errori"]) if stats["errori"] else "")
                + f"\n{verdict}")

    def _in_backup(self, f: RemoteFile, b: BackedUp | None) -> bool:
        """Il file è in Current, con lo stesso contenuto che ha ora su SharePoint?"""
        expected = f.size if b is None or b.local_size is None else b.local_size
        return (b is not None and b.path == f.path and b.same_content(f)
                and file_size(self._cur(f.path)) == expected)

    def _check_remote(self, state, files, dirs, skipped, roots) -> list[str]:
        """Verifica 1, prima del backup: l'elenco dei file è completo?
        La dimensione totale che SharePoint dichiara per ogni cartella selezionata deve
        coincidere con la somma dei file in elenco. Se non coincide scende (API
        "children") solo nelle sottocartelle che non tornano, aggiunge i file mancanti e
        toglie quelli che non esistono più. Restituisce le cartelle non verificabili."""
        self.log(tr("Verifica dell'elenco con le dimensioni delle cartelle su SharePoint..."))
        sums, by_dir = Counter(), defaultdict(set)
        for path, size in [*((f.path, f.size) for f in files.values()), *skipped]:
            parts = path.split("/")
            for k in range(1, len(parts)):
                sums["/".join(parts[:k]).casefold()] += size
        for f in files.values():
            by_dir[f.path.rpartition("/")[0].casefold()].add(f.id)
        unchecked = []
        for item_id, rel in roots.items():
            it = self.sp.get_json(f"{self.sp.drive}/items/{item_id}?$select=id,name,size,folder")
            if "folder" in it and it.get("size", 0) != sums[rel.casefold()]:
                self.log(tr("  {folder}: SharePoint dichiara {declared:,} byte, l'elenco {listed:,}: "
                            "controllo le sottocartelle",
                            folder=rel, declared=it.get("size", 0), listed=sums[rel.casefold()]))
                unchecked += self._reconcile(state, item_id, rel, it, files, dirs, sums, by_dir)
        return unchecked

    def _reconcile(self, state, folder_id, rel, info, files, dirs, sums, by_dir) -> list[str]:
        """Scende solo nelle cartelle la cui dimensione su SharePoint non torna e corregge
        l'elenco. Dove SharePoint conta più elementi di quelli visibili (permessi del tuo
        account) li annota in self.hidden. Restituisce le cartelle rimaste da controllare
        se le differenze sono troppo diffuse per un controllo cartella per cartella."""
        stack = [(folder_id, rel, info.get("size", 0), info["folder"].get("childCount", 0))]
        visited = 0
        while stack and visited < MAX_VERIFY_FOLDERS:
            self.check_cancel()
            folder_id, rel, declared, child_count = stack.pop()
            visited += 1
            listed, visible = set(), 0
            for c in self.sp.children(folder_id):
                path = f"{rel}/{c['name']}"
                listed.add(c["id"])
                visible += c.get("size", 0)
                if "folder" in c:
                    dirs.add(path)
                    if c.get("size", 0) != sums[path.casefold()]:
                        stack.append((c["id"], path, c.get("size", 0), c["folder"].get("childCount", 0)))
                elif "file" in c:
                    f = files.get(c["id"])
                    qxh = c["file"].get("hashes", {}).get("quickXorHash")
                    if f and f.path == path and f.size == c.get("size", 0) and (not qxh or f.hash == qxh):
                        continue
                    mtime = c.get("lastModifiedDateTime")
                    nf = RemoteFile(c["id"], path, c.get("size", 0), qxh, c.get("cTag"),
                                    parse_time(mtime) if mtime else None)
                    files[nf.id] = nf
                    state.db.execute("INSERT OR REPLACE INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                     (nf.id, folder_id, c["name"], KIND_FILE, nf.size, nf.hash,
                                      nf.ctag, nf.mtime))
                    self.log(tr("  {path}: mancava nell'elenco di SharePoint, aggiunto", path=path))
            for stale in by_dir[rel.casefold()] - listed:
                if stale in files and files[stale].path.rpartition("/")[0].casefold() == rel.casefold():
                    self.log(tr("  {path}: in elenco ma non più su SharePoint, tolto", path=files.pop(stale).path))
                    state.db.execute("DELETE FROM items WHERE id=?", (stale,))
            if child_count > len(listed) or declared != visible:
                self.hidden.append((rel, max(0, child_count - len(listed)), declared - visible))
        return [r for _, r, _, _ in stack]

    def _check_local(self, state, files, unchecked, stats) -> str:
        """Verifica 2, dopo il backup: ogni file deve essere in Current con il contenuto
        attuale di SharePoint. I mancanti vengono riscaricati; quelli ancora mancanti
        sono elencati nel log e in _FileList.csv."""
        self.log(tr("Verifica dei file su disco..."))
        backed = state.backed_up()
        todo = [f for f in files.values() if not self._in_backup(f, backed.get(f.id))]
        if todo:
            self.log(tr("  {count} file mancanti o non aggiornati in {folder}: li scarico",
                        count=len(todo), folder=CURRENT_DIR))
            self._download_all(state, todo, stats)
            state.db.commit()
            self.check_cancel()
            backed = state.backed_up()
        missing = [f for f in files.values() if not self._in_backup(f, backed.get(f.id))]
        self._write_manifest(files, missing)
        for f in sorted(missing, key=lambda f: f.path):
            self.log(tr("MANCANTE: {path}", path=f.path))
        for rel in unchecked:
            self.log(tr("NON VERIFICATA: {folder}", folder=rel))
        for rel, count, size in self.hidden:
            if count:
                self.log(tr("NON ACCESSIBILE: {folder}: {count} elementi ({size}) esistono su SharePoint "
                            "ma non sono visibili con il tuo account", folder=rel, count=count, size=fmt_size(size)))
            else:
                self.log(tr("NON ACCESSIBILE: {folder}: la dimensione su SharePoint differisce di {diff:+,} byte "
                            "da quella dei file visibili", folder=rel, diff=size))
        total = fmt_size(sum(f.size for f in files.values()))
        self.complete = not missing and not unchecked
        note = ""
        if self.hidden:
            n, size = sum(h[1] for h in self.hidden), sum(h[2] for h in self.hidden)
            note = "\n" + tr("ATTENZIONE: {count} elementi ({size}) in {folders} cartelle non sono visibili "
                             "con il tuo account e non si possono copiare (elenco nel log)",
                             count=n, size=fmt_size(max(size, 0)), folders=len(self.hidden))
        if self.complete:
            return tr("VERIFICA OK: tutti i {count} file visibili ({size}) sono in {folder}, identici a SharePoint",
                      count=len(files), size=total, folder=CURRENT_DIR) + note
        return (tr("VERIFICA NON SUPERATA: {count} file mancanti", count=len(missing))
                + (tr(", {count} cartelle non verificabili", count=len(unchecked)) if unchecked else "")
                + tr(" (elenco nel log e in {manifest})", manifest=MANIFEST) + note)

    def _write_manifest(self, files, missing):
        """_FileList.csv (si apre con Excel): ogni file del backup e il suo stato."""
        missing_ids = {f.id for f in missing}
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        tmp = TMP_DIR / MANIFEST
        with open(tmp, "w", encoding="utf-8-sig", newline="") as out:
            w = csv.writer(out, delimiter=";")
            w.writerow([tr("Percorso"), tr("Dimensione (byte)"), tr("Modificato su SharePoint"),
                        "quickXorHash", tr("Stato"), tr("Verifica {label}", label=self.label)])
            for f in sorted(files.values(), key=lambda f: f.path.casefold()):
                modified = datetime.fromtimestamp(f.mtime).strftime("%d/%m/%Y %H:%M:%S") if f.mtime else ""
                w.writerow([f.path, f.size, modified, f.hash or "",
                            tr("MANCANTE") if f.id in missing_ids else "OK"])
            for rel, count, size in self.hidden:
                w.writerow([tr("{folder}/ (contenuto non visibile)", folder=rel), size, "", "",
                            tr("NON ACCESSIBILE ({count} elementi)", count=count)])
        shutil.move(tmp, lp(self.root / MANIFEST))

    def _archive(self, rel: str):
        """Sposta Current/rel in _Versions/<etichetta>/rel (stesso disco: nessuna copia)."""
        dst = self.versions / self.label / Path(*rel.split("/"))
        os.makedirs(lp(dst.parent), exist_ok=True)
        n = 1
        while file_size(dst) is not None:
            n += 1
            dst = dst.with_name(f"{Path(rel).stem} ({n}){Path(rel).suffix}")
        os.replace(lp(self._cur(rel)), lp(dst))

    def _archive_removed(self, state, files, backed, stats):
        for b in list(backed.values()):
            if b.id in files:
                continue
            if file_size(self._cur(b.path)) is not None:
                self._archive(b.path)
                stats["archiviati"] += 1
                self.log(tr("✗ {path} (eliminato su SharePoint o non più selezionato: spostato in {folder})",
                            path=b.path, folder=VERSIONS_DIR))
            state.forget(b.id)
            del backed[b.id]

    def _plan(self, state, files, backed, stats) -> list[RemoteFile]:
        """Decide cosa scaricare. I file uguali (stesso hash) non si riscaricano."""
        to_download = []
        for f in files.values():
            self.check_cancel()
            target = self._cur(f.path)
            b = backed.get(f.id)
            moved = False
            if b and b.path != f.path:  # rinominato/spostato su SharePoint: sposto anche qui
                src = self._cur(b.path)
                case_only = b.path.casefold() == f.path.casefold()
                if file_size(src) is not None and (case_only or file_size(target) is None):
                    os.makedirs(lp(target.parent), exist_ok=True)
                    os.replace(lp(src), lp(target))
                    self.log(f"→ {b.path}  =>  {f.path}")
                    b.path = f.path
                    state.record(b, b.local_size)  # il contenuto su disco è ancora quello vecchio
                    stats["spostati"] += 1
                    moved = True
            if self._in_backup(f, b):
                if not moved:
                    stats["invariati"] += 1
                continue
            if b is None:
                st = None
                with contextlib.suppress(FileNotFoundError):
                    st = os.stat(lp(target))
                if (st and st.st_size == f.size and f.mtime
                        and abs(st.st_mtime - f.mtime) < 2):
                    state.record(f, st.st_size)  # già presente e identico (es. stato locale perso)
                    stats["invariati"] += 1
                    continue
            to_download.append(f)
        return to_download

    def _free(self) -> int:
        return shutil.disk_usage(self.root.anchor or ".").free

    def _download_all(self, state, to_download, stats):
        """Scarica i file. Se non ci stanno tutti sul disco e la cartella di backup è in OneDrive
        con "solo online", scarica a blocchi: ogni file copiato viene caricato da OneDrive e tolto
        dal disco (diventa "solo online", cioè sincronizzato) prima di far posto ai successivi."""
        if not to_download:
            self.log(tr("Nessun file da scaricare"))
            return
        need = sum(f.size for f in to_download)
        self.log(tr("Da scaricare: {count} file, {size}", count=len(to_download), size=fmt_size(need)))
        free = self._free()
        batched = need > free - MIN_FREE
        if batched and not (self.online_only and in_onedrive(self.root)):
            raise RuntimeError(tr('Spazio su disco insufficiente: servono {need}, liberi {free}. Seleziona meno '
                                  'cartelle, oppure usa una cartella di backup dentro OneDrive con "solo online": '
                                  "il tool scarica a blocchi e OneDrive libera il disco man mano.",
                                  need=fmt_size(need), free=fmt_size(free)))
        if batched:
            self.log(tr("Lo spazio libero ({free}) non basta per {need} tutti insieme: scarico a blocchi. "
                        "Ogni file viene caricato su OneDrive e tolto dal disco prima di continuare.",
                        free=fmt_size(free), need=fmt_size(need)))
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        for old in TMP_DIR.glob("*.partial"):
            with contextlib.suppress(OSError):
                old.unlink()
        done, fatal, count = 0, None, 0
        todo, pending = list(to_download), {}
        with ThreadPoolExecutor(DOWNLOAD_THREADS) as pool:
            while todo or pending:
                if self.cancel.is_set() or self._abort.is_set():
                    todo.clear()  # si aspettano solo i download già partiti (si fermano subito)
                while todo and len(pending) < DOWNLOAD_THREADS:
                    busy = sum(f.size for f in pending.values())
                    if batched and self._free() - busy - todo[0].size < MIN_FREE:
                        break  # niente spazio per il prossimo: prima finiscono quelli in corso
                    f = todo.pop(0)
                    pending[pool.submit(self._download, f)] = f
                if not pending:
                    if todo and not self._wait_for_space(todo[0].size):
                        f = todo.pop(0)  # non ci starebbe nemmeno col disco liberato: resta MANCANTE
                        stats["errori"] += 1
                        self.log(tr("ERRORE su {path}: {error}", path=f.path, error=tr(
                            "troppo grande per lo spazio sul disco ({size})", size=fmt_size(f.size))))
                        done += f.size
                        self.progress(done, need)
                    continue
                finished, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                for fut in finished:
                    f = pending.pop(fut)
                    try:
                        replaced, warning, local_size = fut.result()
                    except Cancelled:
                        continue
                    except LoginRequired as e:
                        fatal = fatal or e
                        self._abort.set()
                        continue
                    except Exception as e:
                        stats["errori"] += 1
                        self.log(tr("ERRORE su {path}: {error}", path=f.path, error=e))
                    else:
                        state.record(f, local_size)
                        stats["scaricati"] += 1
                        stats["byte"] += f.size
                        stats["archiviati"] += replaced
                        self.log(f"↓ {f.path} ({fmt_size(f.size)})"
                                 + (tr(" - versione precedente salvata") if replaced else "")
                                 + (tr(" - ATTENZIONE: {warning}", warning=warning) if warning else ""))
                        count += 1
                        if count % 100 == 0:
                            state.db.commit()
                    done += f.size
                    self.progress(done, need)
        if fatal:
            raise fatal

    def _uploading(self) -> list[Path]:
        """File copiati in questo backup che OneDrive non ha ancora caricato e tolto dal disco."""
        with self._written_lock:
            self._written = [p for p in self._written if file_size(p) is not None and not is_online_only(p)]
            return list(self._written)

    def _wait_for_space(self, size: int) -> bool:
        """Aspetta che OneDrive carichi i file già copiati e liberi il disco per `size` byte.
        False se non basterebbe nemmeno liberare tutto quello che questo backup ha scritto."""
        self.log(tr("Disco quasi pieno: aspetto che OneDrive carichi i file copiati e liberi spazio..."))
        stalled, best = 0, (self._free(), len(self._uploading()))
        while True:
            self.check_cancel()
            uploading, free = self._uploading(), self._free()
            if free - size >= MIN_FREE:
                self.log(tr("OneDrive ha liberato spazio ({free} liberi): riprendo a scaricare", free=fmt_size(free)))
                return True
            if not uploading:
                return False
            if free > best[0] or len(uploading) < best[1]:  # OneDrive sta lavorando
                stalled, best = 0, (max(free, best[0]), min(len(uploading), best[1]))
            else:
                stalled += 1
            if stalled * SPACE_POLL >= SPACE_WAIT_LIMIT:
                raise RuntimeError(tr("OneDrive non ha liberato spazio negli ultimi {minutes} minuti: controlla che "
                                      "sia avviato e stia sincronizzando. Il prossimo backup riprenderà da qui.",
                                      minutes=SPACE_WAIT_LIMIT // 60))
            self.step(tr("In attesa di OneDrive: {count} file da caricare, {free} liberi sul disco...",
                         count=len(uploading), free=fmt_size(free)))
            time.sleep(SPACE_POLL)

    def _download(self, f: RemoteFile) -> tuple[bool, str | None, int]:
        """-> (versione precedente archiviata?, avviso, dimensione del file scaricato)"""
        self.check_cancel()
        tmp = TMP_DIR / f"{f.id}.partial"
        try:
            for _ in range(2):
                digest, size = self._fetch(f, tmp)
                if (digest == f.hash) if f.hash else (size == f.size):
                    warning = None
                    break
            else:
                warning = tr("il file scaricato non corrisponde all'hash di SharePoint "
                             "(succede con alcuni file Office)")
            target = self._cur(f.path)
            replaced = file_size(target) is not None
            if replaced:
                self._archive(f.path)
            os.makedirs(lp(target.parent), exist_ok=True)
            shutil.move(lp(tmp), lp(target))
            if f.mtime:
                os.utime(lp(target), (f.mtime, f.mtime))
            if self.online_only:
                set_online_only(target)
                with self._written_lock:
                    self._written.append(target)
            return replaced, warning, size
        finally:
            with contextlib.suppress(OSError):
                os.remove(lp(tmp))

    def _fetch(self, f: RemoteFile, tmp: Path) -> tuple[str, int]:
        """Scarica in tmp calcolando l'hash; se la connessione cade riprende da dove era."""
        url = f"{self.sp.drive}/items/{f.id}/content"
        h, pos = QuickXorHash(), 0
        with open(lp(tmp), "wb") as out:
            for attempt in range(5):
                try:
                    with self.sp.get(url, stream=True,
                                     headers={"Range": f"bytes={pos}-"} if pos else None) as r:
                        if pos and r.status_code != 206:  # il server riparte da capo
                            out.seek(0)
                            out.truncate()
                            h, pos = QuickXorHash(), 0
                        for chunk in r.iter_content(CHUNK):
                            self.check_cancel()
                            out.write(chunk)
                            h.update(chunk)
                            pos += len(chunk)
                    break
                except requests.RequestException:
                    if attempt == 4:
                        raise
                    self.log(tr("  connessione interrotta su {path}, riprendo da {position}",
                                path=f.path, position=fmt_size(pos)))
                    time.sleep(2 ** attempt)
        return h.digest(), pos

    def _sync_local(self, dirs: set[str], keep_files: set[str], stats):
        """Crea le cartelle presenti su SharePoint, sposta in _Versions i file locali che
        non corrispondono a nulla su SharePoint e rimuove le cartelle vuote obsolete."""
        for d in dirs:
            os.makedirs(lp(self._cur(d)), exist_ok=True)
        keep_files = {p.casefold() for p in keep_files}
        keep_dirs = {d.casefold() for d in dirs}
        base = lp(self.current)
        for root, _, names in os.walk(base, topdown=False):
            rel_root = os.path.relpath(root, base).replace("\\", "/")
            rel_root = "" if rel_root == "." else rel_root
            for name in names:
                rel = f"{rel_root}/{name}" if rel_root else name
                if rel.casefold() not in keep_files and name.casefold() not in IGNORED_LOCAL:
                    self._archive(rel)
                    stats["archiviati"] += 1
                    self.log(tr("✗ {path} (non presente su SharePoint: spostato in {folder})",
                                path=rel, folder=VERSIONS_DIR))
            if rel_root and rel_root.casefold() not in keep_dirs:
                with contextlib.suppress(OSError):
                    os.rmdir(root)

    def _prune(self, folder: Path, keep: int, dirs: bool):
        """Tiene solo le ultime `keep` etichette (versioni o log)."""
        try:
            names = [n for n in os.listdir(lp(folder)) if LABEL_RE.match(n)]
        except FileNotFoundError:
            return
        for name in sorted(names, key=label_key)[:max(0, len(names) - keep)]:
            try:
                if dirs:
                    shutil.rmtree(lp(folder / name))
                    self.log(tr("Eliminata la versione più vecchia: {name}", name=name))
                else:
                    os.remove(lp(folder / name))
            except OSError as e:
                self.log(tr("ERRORE eliminando {name}: {error}", name=name, error=e))


@contextlib.contextmanager
def single_instance():
    """Impedisce due backup contemporanei (es. finestra + attività pianificata)."""
    import msvcrt
    APP_DIR.mkdir(parents=True, exist_ok=True)
    f = open(LOCK_FILE, "a+")
    try:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        raise RuntimeError(tr("C'è già un backup in corso")) from None
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        f.close()


def run_backup(cfg: dict, log, progress, cancel: threading.Event, interactive_login: bool,
               step=no_step, on_connected=None) -> tuple[str, bool]:
    """-> (riepilogo, verifica di completezza superata).
    on_connected(sp): chiamata appena connessi (la finestra aggiorna le dimensioni)."""
    if not cfg["dest"].strip():  # mai un backup nella cartella di lavoro
        raise RuntimeError(tr("Scegli la cartella di backup."))
    if not cfg["selection"]:
        raise RuntimeError(tr('Nessuna cartella selezionata: premi "Connetti" e scegli cosa copiare'))
    with single_instance():
        sp = SharePoint(cfg["library_url"], log)
        connect(sp, interactive_login, log, step)
        changed = apply_target(cfg, sp.target_key)  # link cambiato: selezione azzerata
        if on_connected:
            on_connected(sp)
        if changed:
            raise RuntimeError(tr("Il link indica un'altra libreria o cartella ({target}): scegli cosa copiare "
                                  "e avvia di nuovo il backup", target=sp.target_name))
        backup = Backup(sp, cfg, log, progress, cancel, step)
        return backup.run(), backup.complete


# ------------------------------------------------------------------------- GUI

ICON_FILES = ("spvault.png", "spvault.ico")  # in assets\, disegnate da assets\make_icon.py
# Pagina del programma, linkata in basso a destra nella finestra (poi il sito del progetto)
WEBSITE = "https://github.com/TarducciM/SPVault"


def asset_path(name: str) -> Path:
    """File di assets\\: nell'exe PyInstaller lo estrae in sys._MEIPASS, da sorgente è accanto a spvault.py."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets" / name


def set_window_icon(root: tk.Tk) -> bool:
    """Icona della finestra e della barra delle applicazioni. Se i file mancano o sono illeggibili
    la finestra resta con l'icona di Tk: nessun errore, solo False."""
    png, ico = (str(asset_path(name)) for name in ICON_FILES)
    if sys.platform == "win32":
        # il .ico ha tutte le dimensioni (nitida a 16, 24 e 32 px): predefinita per le finestre, poi per
        # questa. Non insieme a iconphoto(True, ...): dopo, -default lascia alla classe un'icona non valida.
        with contextlib.suppress(tk.TclError):
            root.iconbitmap(default=ico)
            root.iconbitmap(ico)
            return True
    try:  # altri sistemi, o .ico illeggibile: il PNG
        root.iconphoto(True, tk.PhotoImage(master=root, file=png))
    except tk.TclError:
        return False
    return True


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.cfg = load_config()
        set_language(self.cfg["language"])
        self.events: queue.Queue = queue.Queue()  # thread di lavoro -> GUI
        self.cancel = threading.Event()
        self.running = False
        self.verify_failed = False  # l'ultimo backup non ha superato la verifica
        self.account: str | None = None
        self.target: str | None = None  # libreria/cartella del link, letta all'ultima connessione
        self.item_vars: dict[str, tk.BooleanVar] = {}
        self.step_text, self.started, self.downloading, self._tick_job = "", 0.0, False, None

        self.var_url = tk.StringVar(value=self.cfg["library_url"])
        self.var_dest = tk.StringVar(value=self.cfg["dest"])
        self.var_keep = tk.StringVar(value=str(self.cfg["keep_versions"]))
        self.var_online = tk.BooleanVar(value=self.cfg["online_only"])
        self.var_include_new = tk.BooleanVar(value=self.cfg["include_new"])
        self.var_time = tk.StringVar(value=self.cfg["schedule_time"])
        self.var_lang = tk.StringVar(value=LANGUAGES.get(self.cfg["language"], LANGUAGES["auto"]))
        self.var_account = tk.StringVar()
        self.var_target = tk.StringVar()
        self.var_selsize = tk.StringVar()
        self.var_sched = tk.StringVar()
        self.var_status = tk.StringVar(value=tr("Pronto"))

        root.title(f"SPVault {__version__}")
        set_window_icon(root)
        root.minsize(820, 640)
        self._build()
        self._show_items(self.cfg["known_items"])
        self._show_account()
        self._refresh_schedule()
        self.var_url.trace_add("write", self._on_url_change)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(100, self._poll_events)
        root.after(300, self._auto_refresh)
        root.after(10_000, self._refresh_space)

    def _build(self):
        """Crea i widget con i testi nella lingua attiva (le variabili tk sono di App)."""
        self.frame = frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(7, weight=1)

        ttk.Label(frm, text=tr("Libreria o cartella SharePoint")).grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=self.var_url).grid(row=0, column=1, columnspan=2, sticky="ew")
        ttk.Label(frm, text=tr("Cartella di backup")).grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=self.var_dest).grid(row=1, column=1, sticky="ew")
        ttk.Button(frm, text=tr("Sfoglia..."), command=self._browse).grid(row=1, column=2, padx=(6, 0))

        acc = ttk.Frame(frm)
        acc.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        self.btn_connect = ttk.Button(acc, text=tr("Connetti"), command=self.start_connect)
        self.btn_connect.pack(side="left")
        # la scelta della lingua è scritta in entrambe le lingue: si trova anche se non si capisce l'altra
        self.cmb_lang = ttk.Combobox(acc, textvariable=self.var_lang, values=list(LANGUAGES.values()),
                                     state="readonly", width=max(map(len, LANGUAGES.values())))
        self.cmb_lang.pack(side="right")
        self.cmb_lang.bind("<<ComboboxSelected>>", self._on_language)
        ttk.Label(acc, text="Lingua / Language").pack(side="right", padx=(12, 4))
        ttk.Label(acc, textvariable=self.var_account).pack(side="left", padx=8)
        ttk.Label(acc, textvariable=self.var_target, foreground="gray").pack(side="left")

        box = ttk.LabelFrame(frm, text=tr("Cosa copiare"), padding=8)
        box.grid(row=3, column=0, columnspan=3, sticky="ew", pady=8)
        self.items_frame = ttk.Frame(box)
        self.items_frame.pack(fill="x")
        ttk.Checkbutton(box, text=tr("Copia anche le cartelle nuove che compariranno su SharePoint"),
                        variable=self.var_include_new, command=self._save).pack(anchor="w", pady=(6, 0))
        ttk.Label(box, textvariable=self.var_selsize, foreground="gray").pack(anchor="w", pady=(4, 0))

        opts = ttk.Frame(frm)
        opts.grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Label(opts, text=tr("Versioni da conservare")).pack(side="left")
        ttk.Spinbox(opts, from_=1, to=365, width=5, textvariable=self.var_keep,
                    command=self._save).pack(side="left", padx=(4, 20))
        ttk.Checkbutton(opts, text=tr("Dopo l'upload su OneDrive lascia i file solo online "
                                      "(non occupano spazio sul PC)"),
                        variable=self.var_online, command=self._save).pack(side="left")

        bar = ttk.Frame(frm)
        bar.grid(row=5, column=0, columnspan=3, sticky="ew", pady=10)
        self.btn_run = ttk.Button(bar, text=tr("Esegui backup"), command=self.start_backup)
        self.btn_run.pack(side="left")
        self.btn_stop = ttk.Button(bar, text=tr("Ferma"), command=self.cancel.set, state="disabled")
        self.btn_stop.pack(side="left", padx=6)
        self.status_label = ttk.Label(bar, textvariable=self.var_status)
        self.status_label.pack(side="right")

        self.progress = ttk.Progressbar(frm, mode="determinate")
        self.progress.grid(row=6, column=0, columnspan=3, sticky="ew")
        self.log_box = ScrolledText(frm, height=12, state="disabled", font=("Consolas", 9))
        self.log_box.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(8, 8))

        sched = ttk.Frame(frm)
        sched.grid(row=8, column=0, columnspan=3, sticky="ew")
        ttk.Label(sched, text=tr("Backup automatico ogni giorno alle")).pack(side="left")
        ttk.Entry(sched, textvariable=self.var_time, width=6).pack(side="left", padx=4)
        ttk.Button(sched, text=tr("Pianifica"), command=self._schedule).pack(side="left")
        ttk.Button(sched, text=tr("Rimuovi"), command=self._unschedule).pack(side="left", padx=6)
        ttk.Label(sched, textvariable=self.var_sched, foreground="gray").pack(side="left")
        # in basso a destra: versione e pagina del programma, cliccabile
        self.link = ttk.Label(sched, text=f"SPVault {__version__} · {WEBSITE.split('://', 1)[1]}",
                              foreground="#2563EB", cursor="hand2", font=("Segoe UI", 8, "underline"))
        self.link.pack(side="right")
        self.link.bind("<Button-1>", lambda _event: self._open_website())

    # --- lingua

    def _on_language(self, _event=None):
        self.cfg["language"] = next((k for k, v in LANGUAGES.items() if v == self.var_lang.get()), "auto")
        self._save()
        self.root.after_idle(self._apply_language)  # non distruggere il menu dentro il suo evento

    def _apply_language(self):
        """Applica subito la lingua scelta ricreando i widget: variabili, cartelle
        spuntate, log, barra di avanzamento e lavoro in corso restano come sono."""
        ready = self.var_status.get() == tr("Pronto")
        old = LANG
        set_language(self.cfg["language"])
        if LANG == old:
            return
        log_text = self.log_box.get("1.0", "end-1c")
        bar = {k: str(self.progress.cget(k)) for k in ("mode", "maximum", "value")}
        color = str(self.status_label.cget("foreground"))
        self.progress.stop()
        self.frame.destroy()
        self._build()
        self._draw_items(self.cfg["known_items"])
        self.log_box.configure(state="normal")
        self.log_box.insert("end", log_text)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.progress.configure(mode=bar["mode"], maximum=float(bar["maximum"]), value=float(bar["value"]))
        if self.running and not self.downloading:
            self._animate()
        self.status_label.configure(foreground=color)
        self._update_buttons()
        self._show_account()
        if ready:
            self.var_status.set(tr("Pronto"))
        self._refresh_schedule()

    # --- elenco cartelle

    def _show_items(self, items: list[dict]):
        self.item_vars.clear()
        selected = set(self.cfg["selection"])
        for item in items:
            var = tk.BooleanVar(value=item["id"] in selected)
            var.trace_add("write", lambda *_: self._save())
            self.item_vars[item["id"]] = var
        self._draw_items(items)

    def _draw_items(self, items: list[dict]):
        """Caselle delle cartelle legate alle variabili in self.item_vars."""
        for w in self.items_frame.winfo_children():
            w.destroy()
        if not items:
            hint = (tr('Premi "Connetti" per leggere le cartelle della libreria') if self.var_url.get().strip()
                    else tr('Incolla qui sopra il link della libreria o della cartella (copiato dal browser) '
                            'e premi "Connetti"'))
            ttk.Label(self.items_frame, text=hint).pack(anchor="w")
        for i, item in enumerate(items):
            text = f"{item['name']}  ({fmt_size(item['size'])})" + (tr("  - NUOVA") if is_new(item) else "")
            ttk.Checkbutton(self.items_frame, text=text, variable=self.item_vars[item["id"]]).grid(
                row=i // 3, column=i % 3, sticky="w", padx=(0, 18), pady=1)
        self._update_selection_info()

    def _update_selection_info(self):
        sizes = {i["id"]: i["size"] for i in self.cfg["known_items"]}
        total = sum(sizes.get(i, 0) for i in self.cfg["selection"])
        try:
            anchor = Path(self.var_dest.get()).anchor
            free = tr(" - spazio libero su {drive}: {size}", drive=anchor,
                      size=fmt_size(shutil.disk_usage(anchor).free))
        except (OSError, ValueError):
            free = ""
        when = ""
        if self.cfg.get("items_updated"):
            t = datetime.fromtimestamp(self.cfg["items_updated"])
            day = "" if t.date() == date.today() else tr(" del {date:%d/%m}", date=t)
            when = tr(" - dimensioni aggiornate alle {time:%H:%M}{day}", time=t, day=day)
        self.var_selsize.set(tr("Selezionati: {size}{free}{when}", size=fmt_size(total), free=free, when=when))

    def _refresh_space(self):
        self._update_selection_info()
        self.root.after(10_000, self._refresh_space)

    def _on_url_change(self, *_):
        """Link modificato: la libreria/cartella mostrata non vale più finché non ci si riconnette."""
        if self.target is not None:
            self.target = None
            self._show_account()
        if not self.cfg["known_items"]:
            self._draw_items([])  # suggerimento adatto: incollare il link o premere "Connetti"

    # --- azioni

    def _snapshot(self) -> dict:
        self._save()
        return dict(self.cfg)

    def _link_ok(self) -> bool:
        """Controlla il link prima di partire: se manca o non è valido lo spiega con un esempio."""
        try:
            parse_link(self.var_url.get())
        except ValueError as e:
            messagebox.showwarning("SPVault", str(e))
            return False
        return True

    def start_connect(self):
        if not self._link_ok():
            return
        self._start_worker(self._connect_job, self._snapshot(), True, title=tr("Accesso a SharePoint..."))

    def start_backup(self):
        cfg = self._snapshot()
        if not cfg["dest"]:
            messagebox.showwarning("SPVault", tr("Scegli la cartella di backup."))
            return
        if not self._link_ok():
            return
        if not cfg["selection"]:
            messagebox.showwarning("SPVault", tr("Seleziona almeno una cartella da copiare."))
            return
        self._start_worker(self._backup_job, cfg, title=tr("Avvio del backup..."))

    def _auto_refresh(self):
        """All'apertura aggiorna cartelle e dimensioni in background, senza aprire il browser."""
        if not self.running and self.var_url.get().strip():
            self._start_worker(self._connect_job, self._snapshot(), False,
                               title=tr("Aggiornamento delle cartelle e delle dimensioni..."), quiet=True)

    def _connect_job(self, cfg: dict, interactive: bool) -> str:
        sp = SharePoint(cfg["library_url"], self.log)
        connect(sp, interactive, self.log, self.step)
        account, items = self._send_items(sp)
        return tr("Connesso come {account}: {count} elementi, dimensioni aggiornate",
                  account=account, count=len(items))

    def _send_items(self, sp: SharePoint, cfg: dict | None = None) -> tuple[str, list[dict]]:
        """Legge account e cartelle di primo livello con le dimensioni attuali. Con cfg (la
        copia usata da un backup) le cartelle nuove entrano già in questo backup."""
        self.step(tr("Connesso: lettura delle cartelle e delle dimensioni..."))
        account, items = sp.account(), sp.top_items()
        if cfg is not None:
            merge_items(cfg, [dict(i) for i in items])
        self.events.put(("items", account, items, sp.target_key, sp.target_name))
        return account, items

    def _backup_job(self, cfg: dict) -> str:
        summary, complete = run_backup(cfg, self.log,
                                       lambda d, t: self.events.put(("progress", d, t)),
                                       self.cancel, interactive_login=True, step=self.step,
                                       on_connected=lambda sp: self._send_items(sp, cfg))
        if not complete:
            self.events.put(("warn", summary))
        return summary

    def _start_worker(self, job, *args, title: str, quiet=False):
        """Esegue job in un thread. quiet: errori solo nel log, senza avvisi a schermo."""
        self.cancel.clear()
        self._set_running(True, title)

        def run():
            try:
                self.events.put(("done", True, job(*args)))
            except Cancelled:
                self.events.put(("done", None, tr("Interrotto")))
            except Exception as e:
                if quiet:
                    self.log(tr("Cartelle non aggiornate: {error}", error=e))
                    self.events.put(("done", None, tr('Non connesso: premi "Connetti"')))
                else:
                    self.log(tr("ERRORE: {error}", error=e))
                    self.events.put(("done", False, str(e)))

        threading.Thread(target=run, daemon=True).start()

    def log(self, msg: str):  # chiamabile da qualsiasi thread
        self.events.put(("log", msg))

    def step(self, text: str):  # fase in corso, chiamabile da qualsiasi thread
        self.events.put(("step", text))

    # --- pianificazione (Utilità di pianificazione di Windows, non serve essere admin)

    def _schedule(self):
        hhmm = self.var_time.get().strip()
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", hhmm):
            messagebox.showwarning("SPVault", tr("Orario non valido (usa HH:MM, es. 13:00)"))
            return
        self._save()
        if getattr(sys, "frozen", False):  # SPVault.exe
            command, arguments = sys.executable, "--run"
        else:
            exe = Path(sys.executable).with_name("pythonw.exe")
            command, arguments = str(exe if exe.exists() else sys.executable), f'"{Path(__file__).resolve()}" --run'
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        xml = TMP_DIR / "task.xml"
        xml.write_text(task_xml(command, arguments, hhmm), encoding="utf-16")  # schtasks vuole UTF-16
        try:
            if self._schtasks("/Create", "/F", "/TN", TASK_NAME, "/XML", str(xml)):
                self._append_log(tr("Backup pianificato ogni giorno alle {time}. Se a quell'ora il PC è spento, "
                                    "parte appena lo riaccendi.", time=hhmm))
        finally:
            xml.unlink(missing_ok=True)

    def _unschedule(self):
        self._schtasks("/Delete", "/F", "/TN", TASK_NAME)

    def _schtasks(self, *args) -> bool:
        r = subprocess.run(["schtasks", *args], capture_output=True, errors="replace",
                           encoding="oem" if os.name == "nt" else None,  # messaggi nella lingua di Windows
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self._append_log((r.stdout or r.stderr).strip())
        self._refresh_schedule()
        return r.returncode == 0

    def _refresh_schedule(self):
        r = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"],
                           capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.var_sched.set(tr("(attivo)") if r.returncode == 0 else tr("(non pianificato)"))

    # --- GUI

    def _poll_events(self):
        try:
            while True:
                kind, *data = self.events.get_nowait()
                if kind == "log":
                    self._append_log(data[0])
                elif kind == "step":
                    self.step_text = data[0]
                    if self.downloading:  # finiti i download: di nuovo barra animata
                        self.downloading = False
                        self._animate()
                    self._show_status()
                elif kind == "progress":
                    done, total = data
                    if not self.downloading:
                        self.downloading = True
                        self.progress.stop()
                        self.progress.configure(mode="determinate")
                    self.progress.configure(maximum=max(total, 1), value=done)
                    self.step_text = tr("Download: {done} di {total}", done=fmt_size(done), total=fmt_size(total))
                    self._show_status()
                elif kind == "items":
                    self.account, items, key, self.target = data
                    if apply_target(self.cfg, key):  # link di un'altra libreria/cartella: selezione azzerata
                        self._append_log(tr("Il link indica un'altra libreria o cartella ({target}): "
                                            "scegli di nuovo cosa copiare", target=self.target))
                    self._show_account()
                    for item in merge_items(self.cfg, items):
                        added = tr(" (aggiunta al backup)") if item["id"] in self.cfg["selection"] else ""
                        self._append_log(tr("Nuova cartella su SharePoint: {name}", name=item["name"]) + added)
                    save_config(self.cfg)
                    self._show_items(self.cfg["known_items"])
                elif kind == "warn":  # verifica non superata: arriva prima di "done"
                    self.verify_failed = True
                    messagebox.showwarning("SPVault", data[0])
                elif kind == "done":
                    ok, text = data
                    self._set_running(False)
                    last = text.splitlines()[-1] if text else ""
                    failed = ok is False or self.verify_failed
                    self.progress.configure(mode="determinate", maximum=1, value=1 if ok and not failed else 0)
                    self.var_status.set(("✗ " if failed else "✓ " if ok else "") + last[:100])
                    self.status_label.configure(
                        foreground="#c62828" if failed else "#1a7f37" if ok else "")
                    if ok is not False:
                        self._append_log(text)
                    else:
                        messagebox.showerror("SPVault", text)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _append_log(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{datetime.now():%H:%M:%S}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_running(self, running: bool, title: str = ""):
        self.running = running
        self._update_buttons()
        if self._tick_job:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None
        if running:  # barra animata + fase e secondi trascorsi: si vede che sta lavorando
            self.step_text, self.started, self.downloading = title, time.time(), False
            self.verify_failed = False
            self.status_label.configure(foreground="")
            self._animate()
            self._tick()
        else:
            self.progress.stop()

    def _animate(self):
        """Barra animata per le fasi senza percentuale. La scala va reimpostata ogni volta: a fine
        lavoro la barra resta "piena" con maximum=1 e il blocco salterebbe da un estremo all'altro."""
        self.progress.stop()
        self.progress.configure(mode="indeterminate", maximum=100, value=0)
        self.progress.start(30)

    def _update_buttons(self):
        for b in (self.btn_run, self.btn_connect):
            b["state"] = "disabled" if self.running else "normal"
        self.btn_stop["state"] = "normal" if self.running else "disabled"

    def _show_account(self):
        self.var_account.set(tr("Connesso come {account}", account=self.account) if self.account
                             else tr("Non connesso"))
        self.var_target.set(tr("Origine: {target}", target=self.target) if self.account and self.target else "")

    def _show_status(self):
        self.var_status.set(f"{self.step_text}   {int(time.time() - self.started)} s")

    def _tick(self):
        self._show_status()
        self._tick_job = self.root.after(500, self._tick)

    def _open_website(self):
        webbrowser.open(WEBSITE)

    def _browse(self):
        path = filedialog.askdirectory(initialdir=self.var_dest.get() or Path.home())
        if path:
            self.var_dest.set(os.path.normpath(path))
            self._save()

    def _save(self):
        try:
            keep = max(1, int(self.var_keep.get()))
        except ValueError:
            keep = DEFAULTS["keep_versions"]
        self.cfg.update(
            library_url=self.var_url.get().strip(),
            dest=self.var_dest.get().strip(),
            keep_versions=keep,
            online_only=self.var_online.get(),
            include_new=self.var_include_new.get(),
            schedule_time=self.var_time.get().strip(),
        )
        if self.item_vars:
            self.cfg["selection"] = [i for i, v in self.item_vars.items() if v.get()]
        save_config(self.cfg)
        self._update_selection_info()

    def _on_close(self):
        if self.running and not messagebox.askyesno("SPVault",
                                                    tr("Backup in corso: interromperlo e uscire?")):
            return
        self.cancel.set()
        self._save()
        self.root.destroy()


# -------------------------------------------------------------- avvio pianificato

def run_scheduled() -> int:
    """Backup senza finestra (Utilità di pianificazione). Non apre mai il browser
    in modo visibile: se serve il login mostra un avviso."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(SCHEDULED_LOG, "a", encoding="utf-8") as logf:
        def log(msg):
            logf.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
            logf.flush()

        try:
            cfg = load_config()
            set_language(cfg["language"])  # la lingua scelta nella finestra
            if not cfg["library_url"].strip() or not cfg["dest"].strip():
                text = tr("Il backup pianificato non è partito: SPVault non è ancora configurato.\n"
                          "Apri SPVault, incolla il link della libreria o della cartella e scegli la cartella "
                          "di backup.")
                log(text)
                message_box(text)
                return 1

            def refresh_items(sp: SharePoint):  # cartelle nuove: elencate e, se previsto, copiate
                for item in merge_items(cfg, sp.top_items()):
                    added = tr(" (aggiunta al backup)") if item["id"] in cfg["selection"] else ""
                    log(tr("Nuova cartella su SharePoint: {name}", name=item["name"]) + added)
                save_config(cfg)

            summary, complete = run_backup(cfg, log, lambda d, t: None, threading.Event(),
                                           interactive_login=False, on_connected=refresh_items)
            log(summary)
            if not complete:
                message_box(summary)
            return 0 if complete else 1
        except Exception as e:
            log(tr("ERRORE: {error}", error=e))
            text = (tr("Il backup pianificato non è partito perché la sessione SharePoint è scaduta.\n"
                       'Apri SPVault e premi "Connetti".')
                    if isinstance(e, LoginRequired) else tr("Backup SharePoint non riuscito:\n{error}", error=e))
            message_box(text)
            return 1


def message_box(text: str):
    """Avviso di Windows in primo piano, senza finestra principale (backup pianificato)."""
    ctypes.windll.user32.MessageBoxW(0, text, "SPVault", 0x30 | 0x1000)


def self_test() -> int:
    """Controllo del pacchetto (usato dalla CI sull'exe compilato): 0 = tutto presente."""
    from playwright._impl._driver import compute_driver_executable
    ok = all(Path(p).is_file() for p in compute_driver_executable())
    h = QuickXorHash()
    h.update(b"")
    ok &= h.digest() == "AAAAAAAAAAAAAAAAAAAAAAAAAAA="
    ok &= all(asset_path(name).is_file() for name in ICON_FILES)  # icona inclusa da build.ps1
    root = tk.Tk()
    root.withdraw()
    ok &= set_window_icon(root)
    root.destroy()
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(self_test())
    if "--run" in sys.argv:
        sys.exit(run_scheduled())
    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk()
    App(root)
    if "--minimized" in sys.argv:  # avvio automatico all'accesso a Windows
        root.iconify()
    root.mainloop()


if __name__ == "__main__":
    main()
