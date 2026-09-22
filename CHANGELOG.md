# Changelog

## 2026-09-22 — Link alla pagina del programma

- **In basso a destra nella finestra** ora ci sono la versione e il link alla pagina del programma
  (per ora il repository GitHub, poi il sito del progetto): un clic lo apre nel browser.

## 2026-09-22 — Nuova icona (0.1.1)

- **Icona ridisegnata**: una nuvola bianca da cui scende una freccia dorata dentro un vassoio (i file
  dal cloud al sicuro sul PC), sugli stessi colori verde smeraldo. Il simbolo è più piccolo e centrato
  nel quadrato, come nelle altre app della stessa famiglia, e ha tratti più grossi nelle dimensioni da
  16 a 48 px per restare nitido nella barra delle applicazioni.
- **Anteprima per GitHub** (`assets/social-preview.png`) rifatta con la nuova icona.

## 2026-09-22 — Prima versione pubblica (0.1.0)

- **Backup file per file di SharePoint e OneDrive for Business dal browser**: basta poter aprire i
  file nel browser, anche da ospite di un'altra organizzazione e in sola lettura. Niente client
  OneDrive, niente app registrate su Azure, niente permessi da amministratore.
- **Il link decide cosa copiare**: il link di una libreria copia la libreria; il link di una cartella
  (dalla barra degli indirizzi, da "Copia collegamento", anche un link di condivisione) copia solo
  quella cartella. Funziona anche con i siti di Teams e con OneDrive for Business, e anche da ospite
  con accesso a una sola cartella. "Cosa copiare" mostra il contenuto del link con le dimensioni, e si
  spunta quello che si vuole copiare.
- **Primo avvio senza configurazione**: si incolla il link, si sceglie la cartella di backup e si
  preme "Connetti".
- **Accesso con un browser dedicato**: usa il Chrome o l'Edge già installati con un profilo separato.
  La prima volta si accede nel browser, poi la sessione viene riusata e rinnovata in background con il
  browser invisibile. Se Microsoft chiede di nuovo le credenziali, SPVault se ne accorge in pochi
  secondi.
- **Solo le modifiche**: l'elenco arriva dall'API delta di SharePoint (lettura completa la prima volta
  e ogni 7 giorni, poi solo le modifiche) e un file viene scaricato solo se il suo hash del contenuto
  (quickXorHash) è cambiato. File e cartelle rinominati o spostati vengono spostati anche in locale,
  senza riscaricarli.
- **Download affidabili**: 4 in parallelo, hash verificato durante il download, ripresa dal punto in
  cui si era fermato se la connessione cade, file messo al suo posto in `Current\` solo a download
  completo e con la data di modifica di SharePoint.
- **Versioni**: la versione precedente di ogni file modificato o eliminato va in
  `_Versions\<data>_r<n>\`, e si tengono le ultime N (10 di default). Da `Current\` non si cancella
  mai niente.
- **Verifica di completezza a ogni backup**: le dimensioni delle cartelle dichiarate da SharePoint
  devono coincidere al byte con i file in elenco, e ogni file deve essere su disco. Esito
  `VERIFICA OK` o `VERIFICA NON SUPERATA` con l'elenco dei file mancanti, nel log e in
  `_FileList.csv`. Il contenuto che il proprio account non può vedere viene segnalato come
  `NON ACCESSIBILE`.
- **OneDrive e spazio sul disco**: con la cartella di backup dentro OneDrive i file copiati possono
  restare "solo online". Se il disco non basta, SPVault scarica a blocchi e aspetta che OneDrive
  carichi i file e liberi spazio prima di continuare.
- **Cartelle nuove**: le cartelle comparse su SharePoint vengono segnalate e, se si vuole, aggiunte
  da sole al backup, anche a quello pianificato.
- **Backup automatico giornaliero** con l'Utilità di pianificazione di Windows, senza permessi da
  amministratore. Se all'orario previsto il PC è spento, il backup parte appena lo si riaccende.
- **Interfaccia in italiano e in inglese**, automatica in base alla lingua di Windows o a scelta,
  con cambio immediato dalla finestra.
- **Installer MSI per utente** (collegamenti nel menu Start e sul desktop, avvio all'accesso a
  Windows ridotto a icona, lingua dell'app; la disinstallazione toglie anche il backup pianificato) e
  **versione portabile**.
- **Icona dell'app** (porta di cassaforte con freccia di download, verde smeraldo) su exe, finestra,
  barra delle applicazioni, collegamenti e voce di "App e funzionalità", più l'anteprima per GitHub
  (`assets/social-preview.png`). Tutto viene generato da `assets/make_icon.py`.
