"""Regole dell'installer MSI: sono tutte cose che una volta non funzionavano."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

WXS = Path(__file__).resolve().parent.parent / "installer" / "SPVault.wxs"
NS = {"w": "http://wixtoolset.org/schemas/v4/wxs"}
SCORCIATOIE = ["StartMenuShortcutFeature", "DesktopShortcutFeature", "StartupShortcutFeature"]


@pytest.fixture(scope="module")
def testo():
    return WXS.read_text(encoding="utf-8-sig")


@pytest.fixture(scope="module")
def wix(testo):
    return ET.fromstring(testo)


def pubblicazioni(wix, dialogo):
    return [p for p in wix.iter(f"{{{NS['w']}}}Publish") if p.get("Dialog") == dialogo]


def test_the_accented_text_is_not_mangled(testo):
    """Scritto due volte in UTF-8, "è già" diventa "Ã¨ giÃ " e l'installer lo mostra così."""
    sbagliate = re.findall(r"[ÃÂ].", testo)
    assert not sbagliate, sbagliate
    assert "is already installed" in testo


def test_reinstalling_the_same_version_does_not_leave_two_copies(wix):
    """Senza questo ogni installazione si somma alle altre e i collegamenti non si tolgono più."""
    aggiornamento = wix.find(".//w:MajorUpgrade", NS)
    assert aggiornamento.get("AllowSameVersionUpgrades") == "yes"


def test_the_shortcuts_are_features_so_they_can_be_changed_later(wix):
    """Con i componenti a condizione, "Modifica opzioni" non aveva alcun effetto."""
    funzioni = {f.get("Id") for f in wix.iter(f"{{{NS['w']}}}Feature")}
    assert set(SCORCIATOIE) <= funzioni


def test_the_default_options_only_apply_to_a_first_installation(wix):
    """Le condizioni sul livello sono valide solo alla prima installazione: dopo comanda la scelta
    fatta in "Modifica opzioni", altrimenti i collegamenti tornerebbero come prima."""
    for funzione in wix.iter(f"{{{NS['w']}}}Feature"):
        for livello in funzione.findall("w:Level", NS):
            assert livello.get("Condition", "").endswith("AND NOT Installed"), funzione.get("Id")


def test_the_boxes_start_from_the_shortcuts_that_are_really_there(wix):
    """"!Funzione" è lo stato installato; "&Funzione" è quello richiesto, che qui non c'è ancora."""
    condizioni = " ".join(p.get("Condition", "") for p in pubblicazioni(wix, "MaintenanceChoiceDlg"))
    for funzione in SCORCIATOIE:
        assert f"!{funzione}" in condizioni
        assert f"&{funzione}" not in condizioni


def test_every_maintenance_choice_says_what_the_summary_page_shows(wix):
    """Senza WixUI_InstallMode l'ultima pagina resta vuota, senza testo e senza pulsante."""
    modi = [p for p in pubblicazioni(wix, "MaintenanceChoiceDlg")
            if p.get("Property") == "WixUI_InstallMode"]
    scelte = " ".join(p.get("Condition", "") for p in modi)
    for scelta in ("Repair", "Change", "Reinstall", "Remove"):
        assert scelta in scelte
    assert {p.get("Value") for p in modi} == {"Repair", "Change", "Remove"}
    benvenuto = [p for p in pubblicazioni(wix, "WelcomeDlg") if p.get("Property") == "WixUI_InstallMode"]
    assert [p.get("Value") for p in benvenuto] == ["InstallTypical"]


def test_uninstalling_leaves_nothing_behind(wix):
    """Chiave di registro, cartella del programma e backup pianificato."""
    chiave = wix.find(".//w:RemoveRegistryKey", NS)
    assert chiave.get("Action") == "removeOnUninstall" and chiave.get("Key") == r"Software\SPVault"
    cartelle = {c.get("Directory") for c in wix.iter(f"{{{NS['w']}}}RemoveFolder")}
    assert {"INSTALLFOLDER", "ProgramsDir"} <= cartelle
    attivita = wix.find(".//w:InstallExecuteSequence/w:Custom", NS)
    assert attivita.get("Action") == "RemoveScheduledTask"
    assert "REMOVE = \"ALL\"" in attivita.get("Condition")
    assert "NOT UPGRADINGPRODUCTCODE" in attivita.get("Condition")  # non durante un aggiornamento


def test_an_upgrade_keeps_the_options_chosen_before(wix):
    """Le opzioni si rileggono dal registro; quelle passate all'installer restano più forti."""
    letture = {r.get("Name") for r in wix.iter(f"{{{NS['w']}}}RegistrySearch")}
    assert {"InstallDir", "StartMenuShortcut", "DesktopShortcut", "StartupShortcut", "Language"} <= letture
    for prop, prima in (("STARTMENUSHORTCUT", "PREVSTARTMENU"), ("DESKTOPSHORTCUT", "PREVDESKTOP"),
                        ("STARTUP", "PREVSTARTUP")):
        [imposta] = [s for s in wix.iter(f"{{{NS['w']}}}SetProperty") if s.get("Id") == prop]
        assert imposta.get("Condition").startswith(f"NOT {prop} AND")
        assert prima in imposta.get("Condition")
