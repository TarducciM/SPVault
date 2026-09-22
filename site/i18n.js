// Dizionario italiano/inglese del sito SPVault, condiviso da tutte le pagine
// (index + privacy + terms + cookie-policy). Stesso pattern leggero usato in
// tutto l'ecosistema MTSolutions: dizionario piatto, data-i18n per il testo
// statico, italiano come contenuto di partenza nell'HTML (fallback/SEO se JS
// non gira), lingua rilevata da navigator.language finche' non se ne sceglie
// una a mano (persistita in localStorage).
(function () {
  'use strict';

  var STORAGE_KEY = 'spvault_site_lang';
  var SUPPORTED = ['it', 'en'];
  var DEFAULT_LANG = 'it';

  var DICT = {
    it: {
      'nav.github': 'GitHub',
      'nav.back': '← Indietro',

      'hero.eyebrow': 'backup sharepoint · windows · open source',
      'hero.title_pre': 'Il backup di SharePoint che ',
      'hero.title_em': 'ti dice se manca qualcosa.',
      'hero.sub': 'SPVault copia file per file una libreria SharePoint, una sua cartella o OneDrive for Business — solo quello che è cambiato, con le versioni precedenti conservate e una verifica al byte a ogni backup. Nessun account amministratore, nessuna app registrata su Azure: basta poter aprire i file nel browser.',
      'hero.cta_primary_fallback': 'Vedi il progetto su GitHub',
      'hero.cta_secondary': 'Altri file',
      'hero.cta_readme': 'Elenco completo delle funzioni ↗',
      'hero.note': 'Windows 10/11, 64-bit. Richiede Google Chrome o Microsoft Edge (già installato).',

      'demo.window_label': 'SPVault — backup',
      'demo.step1': 'Accesso a SharePoint',
      'demo.step2': 'Lettura delle modifiche',
      'demo.step2_val': '3 file cambiati',
      'demo.step3': 'Download 3/3',
      'demo.step4': 'Verifica dei file su disco',
      'demo.verdict': 'VERIFICA OK — 12.482 file (86,4 GB)',
      'demo.verdict_sub': 'tutti identici a SharePoint, incluse le sottocartelle non lette dall’ultimo backup.',

      'features.eyebrow': 'cosa fa',
      'features.title': 'Un backup non è tale se non sai cosa manca.',
      'features.sub': 'Il download a mano dal browser (zip) non avvisa se qualcosa manca e riscarica sempre tutto. SPVault copia solo le differenze e controlla di aver preso tutto, ogni volta.',
      'features.f1_tok': 'Δ',
      'features.f1_title': 'Solo quello che è cambiato',
      'features.f1_desc': 'L’hash del contenuto calcolato da SharePoint dice cosa scaricare davvero: un file identico non viene mai riscaricato, uno spostato viene solo spostato in locale.',
      'features.f2_tok': 'N',
      'features.f2_title': 'Versioni, non copie intere',
      'features.f2_desc': 'Ogni backup mette in _Versions\\ solo i file cambiati o eliminati, non l’intera cartella: dieci versioni occupano poco più di una copia sola.',
      'features.f3_tok': '✓',
      'features.f3_title': 'Verifica al byte, ogni volta',
      'features.f3_desc': 'La dimensione che SharePoint dichiara per ogni cartella è confrontata al byte con quello che c’è davvero sul disco: quello che manca viene ripreso subito, non scoperto dopo.',
      'features.f4_tok': 'OSPITE',
      'features.f4_title': 'Funziona anche da ospite',
      'features.f4_desc': 'Usa la sessione del browser che hai già — niente app registrata su Azure, niente consenso di un amministratore, niente client OneDrive.',
      'features.f5_tok': 'AUTO',
      'features.f5_title': 'Parte da solo',
      'features.f5_desc': 'Backup giornaliero pianificato senza permessi da amministratore. Se il PC era spento all’orario previsto, riparte alla riaccensione.',
      'features.f6_tok': 'DISK',
      'features.f6_title': 'Poco spazio sul disco? Va bene lo stesso',
      'features.f6_desc': 'Con la cartella di backup dentro OneDrive, SPVault scarica a blocchi: carica e libera spazio man mano invece di aver bisogno di tutto il disco in una volta.',

      'downloads.eyebrow': 'scarica',
      'downloads.title': 'Scegli il file.',
      'downloads.checking': 'Verifico l’ultima release su GitHub…',
      'downloads.no_release_sub': 'Nessuna release pubblicata ancora — SPVault è in sviluppo attivo.',
      'downloads.no_release_title': 'Nessuna versione installabile ancora',
      'downloads.no_release_body': 'Metti una stella al repository o segui le release per sapere subito quando esce la prima versione.',
      'downloads.star': 'Metti una stella su GitHub ↗',
      'downloads.watch': 'Segui le release ↗',
      'downloads.noscript': 'JavaScript è disattivato, quindi questa pagina non può controllare da sola l’ultima release — vai direttamente alla',
      'downloads.noscript_link': 'pagina delle release',
      'downloads.requirements': 'Serve Windows 10/11 a 64 bit e Google Chrome o Microsoft Edge già installato.',
      'downloads.all_releases_pre': 'Versioni precedenti e changelog completo sulla',
      'downloads.all_releases_link': 'pagina delle release ↗',
      'downloads.msi_name': 'Installer (MSI)',
      'downloads.msi_desc': 'Per utente, senza permessi da amministratore',
      'downloads.portable_name': 'Portabile',
      'downloads.portable_desc': 'Nessuna installazione, si avvia da dove vuoi',
      'downloads.see_release_page': 'vedi la pagina della release',
      'downloads.primary_label': 'Scarica per Windows',
      'downloads.latest_pre': 'Ultima versione:',
      'downloads.latest_published': 'pubblicata il',

      'footer.license': 'Con licenza MIT. Realizzato da',
      'footer.source': 'Sorgente',
      'footer.issues': 'Segnala un problema',
      'footer.license_link': 'Licenza',
      'footer.privacy': 'Privacy',
      'footer.terms': 'Termini',
      'footer.cookie': 'Cookie Policy',
      'footer.home': 'Home',

      'privacy.eyebrow': 'privacy',
      'privacy.title': 'Informativa sulla privacy',
      'privacy.updated': 'Ultimo aggiornamento: 22 settembre 2026',
      'privacy.intro': 'SPVault è un programma desktop che gira sul tuo PC: non ha un proprio server, non raccoglie dati per venderli o profilarti, e non manda nessuna telemetria. Questa pagina spiega con esattezza cosa succede — e cosa no — in termini semplici.',
      'privacy.h2_app': 'Il programma desktop',
      'privacy.app_p1': 'SPVault gira interamente sul tuo dispositivo. Parla solo con le pagine di accesso di Microsoft (nel browser, alla prima connessione) e con le API di SharePoint del tuo account — niente altro.',
      'privacy.app_li1': '<strong>Nessun server proprio, nessuna telemetria.</strong> SPVault non manda a nessun server di sua proprietà informazioni di alcun tipo — non analytics, non crash report, non statistiche d’uso.',
      'privacy.app_li2': '<strong>L’accesso avviene con il tuo browser.</strong> SPVault apre Chrome o Edge (già installati sul tuo PC) con un profilo dedicato e separato da quello che usi tutti i giorni, in <code>%LOCALAPPDATA%\\SPVault\\browser_profile</code>. Le credenziali le inserisci tu, direttamente nella pagina di accesso Microsoft — SPVault non le vede né le maneggia mai.',
      'privacy.app_li3': '<strong>La sessione di accesso resta solo sul tuo PC.</strong> Dopo il primo accesso, SPVault riusa i cookie di sessione salvati in quel profilo dedicato per parlare con le API di SharePoint — non vengono mai inviati altrove.',
      'privacy.app_li4': '<strong>I dati del backup restano dove li metti tu.</strong> I file copiati vanno nella cartella di backup che scegli, sul tuo disco o dentro il tuo OneDrive — mai su un server di SPVault, perché non esiste.',
      'privacy.app_li5': '<strong>SPVault vede solo quello che vedi tu.</strong> Usa il tuo account e i tuoi permessi, nessun privilegio aggiuntivo: non può leggere né copiare niente che il tuo account non veda già nel browser.',
      'privacy.app_li6': '<strong>Disinstallando SPVault</strong> restano i file che ha già copiato (sono tuoi, sul tuo disco) — i dati dell’app (sessione, impostazioni, stato) restano in <code>%LOCALAPPDATA%\\SPVault</code> finché non li cancelli a mano.',
      'privacy.h2_site': 'Questo sito (la pagina che stai leggendo)',
      'privacy.site_p1': 'È un sito statico, senza form, senza account e senza analytics di alcun tipo. Due cose vengono comunque caricate da fuori il tuo browser, entrambe standard e dichiarate onestamente:',
      'privacy.site_li1': '<strong>L’API pubblica delle release di GitHub</strong> — per mostrare se esiste già una versione scaricabile e il link giusto. La richiesta va dal tuo browser direttamente a GitHub; questo sito non la vede.',
      'privacy.site_li2': '<strong>Google Fonts</strong> — i caratteri della pagina sono caricati dai server di Google, come sulla maggior parte dei siti che usano Google Fonts. Il tuo browser richiede quei file direttamente a Google.',
      'privacy.site_p2': 'Nessuna delle due è qualcosa che questo sito raccoglie o a cui ha accesso — sono richieste che il tuo browser fa direttamente a terzi, normali per una pagina che mostra l’ultima release e usa web font.',
      'privacy.h2_cookies': 'Cookie',
      'privacy.cookies_p1': 'Né il programma né questo sito usano cookie. Vedi la',
      'privacy.cookies_link': 'Cookie Policy',
      'privacy.cookies_p1_end': 'per la risposta completa, breve.',
      'privacy.h2_changes': 'Modifiche a questa pagina',
      'privacy.changes_p1': 'Questa pagina resta allineata a quello che il programma fa davvero, non a quello che potrebbe fare in futuro — se SPVault aggiungesse una funzione opzionale che cambia qualcosa di quanto sopra, questa pagina verrebbe aggiornata nello stesso cambiamento, non dopo.',
      'privacy.h2_controller': 'Titolare del trattamento',
      'privacy.controller_p1': 'SPVault non fa parte del catalogo commerciale MTSolutions — è un progetto personale con licenza MIT — ma è pubblicato dalla stessa persona/entità dietro MTSolutions: <strong>San Marino Games S.r.l.</strong>, Via Fondo Ausa 68, 47891 Dogana, Repubblica di San Marino (RSM), C.O.E. SM18083.',
      'privacy.h2_questions': 'Domande',
      'privacy.questions_p1': 'Apri una segnalazione su',
      'privacy.questions_p1_end': ', oppure scrivi a',

      'terms.eyebrow': 'termini',
      'terms.title': 'Termini di utilizzo',
      'terms.updated': 'Ultimo aggiornamento: 22 settembre 2026',
      'terms.intro': 'SPVault è software libero e open source. Questi termini sono volutamente brevi — la maggior parte di quello che normalmente ci andrebbe è già coperta dalla licenza.',
      'terms.h2_license': 'Licenza',
      'terms.license_p1': 'SPVault è distribuito con licenza',
      'terms.license_link_text': 'MIT',
      'terms.license_p1_end': '. In pratica: puoi usarlo, copiarlo, modificarlo e ridistribuirlo, per scopi personali o commerciali, senza chiedere permesso — l’unica condizione reale è mantenere la nota di copyright nelle copie che ridistribuisci.',
      'terms.h2_warranty': 'Nessuna garanzia',
      'terms.warranty_p1': 'La licenza MIT lo dice già, ma in chiaro: SPVault è fornito <strong>così com’è</strong>, senza garanzia di alcun tipo. È un progetto personale mantenuto a tempo perso, oggi in sviluppo attivo — non è garantito privo di bug né completo in ogni funzione, e non c’è nessun impegno di livello di servizio. Prima di affidargli l’unica copia di dati importanti, prova il programma su una cartella non critica.',
      'terms.h2_acceptable': 'Uso corretto',
      'terms.acceptable_p1': 'Non usare il nome, l’icona o l’immagine di SPVault per far credere un’affiliazione ufficiale che non esiste. A parte questo, non ci sono restrizioni d’uso oltre a quelle già previste dalla licenza MIT.',
      'terms.h2_ms': 'Nessuna affiliazione con Microsoft',
      'terms.ms_p1': 'SPVault è un progetto indipendente, non affiliato a Microsoft. SharePoint, OneDrive e Microsoft Edge sono marchi di Microsoft; Google Chrome è un marchio di Google. SPVault accede a SharePoint con il tuo account e i tuoi permessi, esattamente come faresti tu nel browser — prima di tenere una copia di dati di altri, verifica che le regole di chi li gestisce lo consentano.',
      'terms.h2_site': 'Questo sito',
      'terms.site_p1': 'Il sito esiste per lo stesso motivo del programma: essere utile, senza condizioni nascoste. Vedi la',
      'terms.site_p1_mid': 'per cosa fa e non fa con i tuoi dati, e la',
      'terms.site_p1_end': 'per i cookie in particolare (non ce ne sono).',
      'terms.h2_changes': 'Modifiche',
      'terms.changes_p1': 'Questi termini possono cambiare se cambia lo scopo del progetto — la data in cima riflette sempre l’ultima revisione vera.',
      'terms.h2_publisher': 'Editore e legge applicabile',
      'terms.publisher_p1': 'SPVault non fa parte del catalogo commerciale MTSolutions — è un progetto personale con licenza MIT — ma è pubblicato dalla stessa entità dietro MTSolutions: <strong>San Marino Games S.r.l.</strong>, Via Fondo Ausa 68, 47891 Dogana, Repubblica di San Marino (RSM), C.O.E. SM18083. Questi termini sono regolati dalla legge della Repubblica di San Marino; qualunque controversia è di competenza esclusiva del Tribunale della Repubblica di San Marino.',
      'terms.h2_questions': 'Domande',
      'terms.questions_p1': 'Apri una segnalazione su',
      'terms.questions_p1_end': ', oppure scrivi a',

      'cookie.eyebrow': 'cookie',
      'cookie.title': 'Cookie Policy',
      'cookie.updated': 'Ultimo aggiornamento: 22 settembre 2026',
      'cookie.answer_title': 'Nessun cookie.',
      'cookie.answer_sub': 'Né questo sito né il programma SPVault impostano alcun cookie — non tecnico, non di analisi, non di terze parti. Non c’è niente su cui dare consenso, quindi non c’è nessun banner.',
      'cookie.h2_why': 'Perché non c’è un banner',
      'cookie.why_p1': 'Un banner di consenso serve a chiedere il permesso per cookie non strettamente necessari al funzionamento del sito — analisi, pubblicità, tracciamento. Dato che questo sito non ne imposta nessuno (né alcun altro cookie), mostrare un banner suggerirebbe un trattamento dati che semplicemente non avviene.',
      'cookie.h2_loads': 'Cosa carica la pagina da altrove',
      'cookie.loads_p1': 'Due richieste escono dal tuo browser quando visiti questo sito — nessuna delle due è un cookie, ma vale la pena nominarle per trasparenza (stessa informazione della',
      'cookie.loads_p1_end': '):',
      'cookie.loads_li1': '<strong>L’API delle release di GitHub</strong>, per controllare se esiste già una versione e mostrare il link giusto.',
      'cookie.loads_li2': '<strong>Google Fonts</strong>, per caricare i caratteri della pagina.',
      'cookie.h2_app': 'Il programma desktop',
      'cookie.app_p1': 'SPVault salva la sessione di accesso a SharePoint localmente sul tuo PC (nel profilo del browser dedicato) — non è un cookie di questo sito, e come tutto il resto del programma non lascia mai il tuo dispositivo se non verso SharePoint stesso.',
      'cookie.h2_questions': 'Domande',
      'cookie.questions_p1': 'Apri una segnalazione su',
    },
    en: {
      'nav.github': 'GitHub',
      'nav.back': '← Back',

      'hero.eyebrow': 'sharepoint backup · windows · open source',
      'hero.title_pre': 'SharePoint backups that ',
      'hero.title_em': 'tell you if something’s missing.',
      'hero.sub': 'SPVault copies a SharePoint library, one of its folders, or OneDrive for Business file by file — only what changed, with previous versions kept and a byte-level check on every run. No admin account, no Azure app registration: if you can open the files in a browser, SPVault can back them up.',
      'hero.cta_primary_fallback': 'See the project on GitHub',
      'hero.cta_secondary': 'Other builds',
      'hero.cta_readme': 'Full feature list ↗',
      'hero.note': 'Windows 10/11, 64-bit. Requires Google Chrome or Microsoft Edge (already installed).',

      'demo.window_label': 'SPVault — backup',
      'demo.step1': 'Signing in to SharePoint',
      'demo.step2': 'Reading changes',
      'demo.step2_val': '3 files changed',
      'demo.step3': 'Downloading 3/3',
      'demo.step4': 'Verifying files on disk',
      'demo.verdict': 'VERIFIED — 12,482 files (86.4 GB)',
      'demo.verdict_sub': 'all identical to SharePoint, including subfolders the last run didn’t re-read.',

      'features.eyebrow': 'what it does',
      'features.title': 'A backup isn’t one if you don’t know what’s missing.',
      'features.sub': 'A manual browser download (zip) never warns you when something’s missing, and re-downloads everything every time. SPVault copies only what changed and checks it got everything, every run.',
      'features.f1_tok': 'Δ',
      'features.f1_title': 'Only what changed',
      'features.f1_desc': 'The content hash SharePoint computes says what actually needs downloading: an identical file is never re-downloaded, a moved one is just moved locally.',
      'features.f2_tok': 'N',
      'features.f2_title': 'Versions, not full copies',
      'features.f2_desc': 'Each run puts only the changed or deleted files in _Versions\\, not the whole folder — ten versions take up little more than a single copy.',
      'features.f3_tok': '✓',
      'features.f3_title': 'Byte-level verification, every time',
      'features.f3_desc': 'The size SharePoint reports for each folder is checked byte-for-byte against what’s actually on disk: anything missing is fetched right away, not discovered later.',
      'features.f4_tok': 'GUEST',
      'features.f4_title': 'Works as a guest too',
      'features.f4_desc': 'Uses the browser session you already have — no Azure app registration, no admin consent, no OneDrive sync client.',
      'features.f5_tok': 'AUTO',
      'features.f5_title': 'Runs itself',
      'features.f5_desc': 'Daily scheduled backup, no admin rights required. If the PC was off at the scheduled time, it catches up as soon as it’s back on.',
      'features.f6_tok': 'DISK',
      'features.f6_title': 'Low on disk? Still fine',
      'features.f6_desc': 'With the backup folder inside OneDrive, SPVault downloads in chunks — uploading and freeing space as it goes instead of needing the whole thing on disk at once.',

      'downloads.eyebrow': 'get it',
      'downloads.title': 'Pick your build.',
      'downloads.checking': 'Checking GitHub for the latest release…',
      'downloads.no_release_sub': 'No release has been published yet — SPVault is under active development.',
      'downloads.no_release_title': 'No installable build yet',
      'downloads.no_release_body': 'Star the repo or watch releases to get notified the moment the first version is out.',
      'downloads.star': 'Star on GitHub ↗',
      'downloads.watch': 'Watch releases ↗',
      'downloads.noscript': 'JavaScript is off, so this page can’t check for a release automatically — see the',
      'downloads.noscript_link': 'releases page',
      'downloads.requirements': 'Requires Windows 10/11, 64-bit, and Google Chrome or Microsoft Edge already installed.',
      'downloads.all_releases_pre': 'Older versions and full changelog on the',
      'downloads.all_releases_link': 'releases page ↗',
      'downloads.msi_name': 'Installer (MSI)',
      'downloads.msi_desc': 'Per-user, no admin rights required',
      'downloads.portable_name': 'Portable',
      'downloads.portable_desc': 'No install, just run it from anywhere',
      'downloads.see_release_page': 'see the release page',
      'downloads.primary_label': 'Download for Windows',
      'downloads.latest_pre': 'Latest release:',
      'downloads.latest_published': 'published',

      'footer.license': 'MIT licensed. Built by',
      'footer.source': 'Source',
      'footer.issues': 'Report an issue',
      'footer.license_link': 'License',
      'footer.privacy': 'Privacy',
      'footer.terms': 'Terms',
      'footer.cookie': 'Cookie Policy',
      'footer.home': 'Home',

      'privacy.eyebrow': 'privacy',
      'privacy.title': 'Privacy Policy',
      'privacy.updated': 'Last updated: September 22, 2026',
      'privacy.intro': 'SPVault is a desktop app that runs on your PC: it has no server of its own, doesn’t collect data to sell or profile you, and sends no telemetry. This page explains exactly what does and doesn’t happen, in plain terms.',
      'privacy.h2_app': 'The desktop app',
      'privacy.app_p1': 'SPVault runs entirely on your own device. It only talks to Microsoft’s sign-in pages (in the browser, the first time you connect) and to your account’s SharePoint APIs — nothing else.',
      'privacy.app_li1': '<strong>No server of its own, no telemetry.</strong> SPVault doesn’t send any information to a server it owns — no analytics, no crash reports, no usage statistics.',
      'privacy.app_li2': '<strong>Sign-in happens in your own browser.</strong> SPVault opens Chrome or Edge (already installed on your PC) with a dedicated profile, separate from the one you use every day, at <code>%LOCALAPPDATA%\\SPVault\\browser_profile</code>. You type your credentials directly into Microsoft’s sign-in page — SPVault never sees or handles them.',
      'privacy.app_li3': '<strong>The sign-in session stays on your PC.</strong> After the first sign-in, SPVault reuses the session cookies saved in that dedicated profile to talk to SharePoint’s APIs — they’re never sent anywhere else.',
      'privacy.app_li4': '<strong>Backup data stays wherever you put it.</strong> Copied files go into the backup folder you choose, on your own disk or inside your own OneDrive — never to a SPVault server, because there isn’t one.',
      'privacy.app_li5': '<strong>SPVault sees only what you see.</strong> It uses your account and your permissions, no extra privilege — it can’t read or copy anything your account doesn’t already see in the browser.',
      'privacy.app_li6': '<strong>Uninstalling SPVault</strong> leaves the files it already copied in place (they’re yours, on your own disk) — the app’s own data (session, settings, state) stays in <code>%LOCALAPPDATA%\\SPVault</code> until you delete it yourself.',
      'privacy.h2_site': 'This website (the page you’re reading)',
      'privacy.site_p1': 'This is a static site with no forms, no accounts, and no analytics of any kind. Two things it does load from outside your browser, both standard and both worth naming honestly:',
      'privacy.site_li1': '<strong>GitHub’s public release API</strong> — to show whether a release exists yet and the right download link. That request goes from your browser directly to GitHub; this site never sees it.',
      'privacy.site_li2': '<strong>Google Fonts</strong> — the page’s typefaces are loaded from Google’s font servers, same as most websites that use Google Fonts. Your browser requests those files directly from Google.',
      'privacy.site_p2': 'Neither is something this site collects or has access to — they’re requests your own browser makes to a third party, standard for a page that shows live release info and uses web fonts.',
      'privacy.h2_cookies': 'Cookies',
      'privacy.cookies_p1': 'Neither the app nor this website use cookies. See the',
      'privacy.cookies_link': 'Cookie Policy',
      'privacy.cookies_p1_end': 'for the full, short answer.',
      'privacy.h2_changes': 'Changes to this page',
      'privacy.changes_p1': 'This page is kept in sync with what the app actually does, not what it might do later — if SPVault ever adds an opt-in feature that changes any of the above, this page will be updated in the same change that ships it, not after the fact.',
      'privacy.h2_controller': 'Data controller',
      'privacy.controller_p1': 'SPVault isn’t part of the commercial MTSolutions product catalog — it’s a personal, MIT-licensed project — but it’s published by the same entity behind MTSolutions: <strong>San Marino Games S.r.l.</strong>, Via Fondo Ausa 68, 47891 Dogana, Repubblica di San Marino (RSM), C.O.E. SM18083.',
      'privacy.h2_questions': 'Questions',
      'privacy.questions_p1': 'Open an issue on',
      'privacy.questions_p1_end': ', or write to',

      'terms.eyebrow': 'terms',
      'terms.title': 'Terms',
      'terms.updated': 'Last updated: September 22, 2026',
      'terms.intro': 'SPVault is free, open-source software. These terms are short on purpose — most of what would normally go here is already handled by the license.',
      'terms.h2_license': 'License',
      'terms.license_p1': 'SPVault is released under the',
      'terms.license_link_text': 'MIT License',
      'terms.license_p1_end': '. In practice: you can use, copy, modify, and redistribute it, for personal or commercial purposes, without asking permission — the only real condition is keeping the copyright notice in copies you redistribute.',
      'terms.h2_warranty': 'No warranty',
      'terms.warranty_p1': 'The MIT License already says this, but plainly: SPVault is provided <strong>as-is</strong>, with no warranty of any kind. It’s a personal project maintained on a best-effort basis, currently in active development — it isn’t guaranteed to be bug-free or feature-complete, and there’s no service-level commitment behind it. Before trusting it with the only copy of anything important, try it on a non-critical folder first.',
      'terms.h2_acceptable': 'Acceptable use',
      'terms.acceptable_p1': 'Don’t use SPVault’s name, icon, or branding to imply an official affiliation it doesn’t have. Beyond that, there are no usage restrictions beyond what the MIT License itself sets out.',
      'terms.h2_ms': 'No affiliation with Microsoft',
      'terms.ms_p1': 'SPVault is an independent project, not affiliated with Microsoft. SharePoint, OneDrive, and Microsoft Edge are trademarks of Microsoft; Google Chrome is a trademark of Google. SPVault accesses SharePoint with your own account and your own permissions, exactly as you would in the browser — before keeping a copy of someone else’s data, check that the rules of whoever manages it allow it.',
      'terms.h2_site': 'This website',
      'terms.site_p1': 'The site exists for the same reason as the app: to be useful, with no strings attached. See the',
      'terms.site_p1_mid': 'for what it does and doesn’t do with your data, and the',
      'terms.site_p1_end': 'for cookies specifically (there are none).',
      'terms.h2_changes': 'Changes',
      'terms.changes_p1': 'These terms may be updated if the project’s scope changes — the date at the top always reflects the last real revision.',
      'terms.h2_publisher': 'Publisher and governing law',
      'terms.publisher_p1': 'SPVault isn’t part of the commercial MTSolutions product catalog — it’s a personal, MIT-licensed project — but it’s published by the same entity behind MTSolutions: <strong>San Marino Games S.r.l.</strong>, Via Fondo Ausa 68, 47891 Dogana, Repubblica di San Marino (RSM), C.O.E. SM18083. These terms are governed by the law of the Republic of San Marino; any dispute falls under the exclusive jurisdiction of the Court of the Republic of San Marino.',
      'terms.h2_questions': 'Questions',
      'terms.questions_p1': 'Open an issue on',
      'terms.questions_p1_end': ', or write to',

      'cookie.eyebrow': 'cookies',
      'cookie.title': 'Cookie Policy',
      'cookie.updated': 'Last updated: September 22, 2026',
      'cookie.answer_title': 'No cookies.',
      'cookie.answer_sub': 'Neither this website nor the SPVault app set any cookie — not technical, not analytics, not third-party. There’s nothing here to consent to, so there’s no banner.',
      'cookie.h2_why': 'Why there’s no banner',
      'cookie.why_p1': 'A consent banner exists to ask permission for cookies that aren’t strictly necessary for the site to work — analytics, advertising, tracking. Since this site sets none of those (or any cookie at all), showing a banner would suggest a kind of data processing that simply isn’t happening.',
      'cookie.h2_loads': 'What the page does load from elsewhere',
      'cookie.loads_p1': 'Two requests leave your browser when you visit this site — neither is a cookie, but worth naming for full transparency (same disclosure as the',
      'cookie.loads_p1_end': '):',
      'cookie.loads_li1': '<strong>GitHub’s release API</strong>, to check whether a build exists yet and show the right download links.',
      'cookie.loads_li2': '<strong>Google Fonts</strong>, to load the page’s typefaces.',
      'cookie.h2_app': 'The desktop app',
      'cookie.app_p1': 'SPVault saves your SharePoint sign-in session locally on your PC (in the dedicated browser profile) — that’s not a cookie from this site, and like everything else the app does, it never leaves your device except toward SharePoint itself.',
      'cookie.h2_questions': 'Questions',
      'cookie.questions_p1': 'Open an issue on',
    }
  };

  function detectInitialLang() {
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      if (saved && SUPPORTED.indexOf(saved) !== -1) return saved;
    } catch (e) { /* ignore */ }
    var nav = (navigator.language || DEFAULT_LANG).toLowerCase().slice(0, 2);
    return SUPPORTED.indexOf(nav) !== -1 ? nav : DEFAULT_LANG;
  }

  var currentLang = detectInitialLang();

  function t(key) {
    var dict = DICT[currentLang] || DICT[DEFAULT_LANG];
    return (dict && dict[key]) || (DICT[DEFAULT_LANG] && DICT[DEFAULT_LANG][key]) || key;
  }

  function apply() {
    document.documentElement.lang = currentLang;
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var value = t(el.getAttribute('data-i18n'));
      var attr = el.getAttribute('data-i18n-attr');
      if (attr) {
        el.setAttribute(attr, value);
      } else if (el.hasAttribute('data-i18n-html')) {
        el.innerHTML = value;
      } else {
        el.textContent = value;
      }
    });
    document.querySelectorAll('[data-lang-switch]').forEach(function (btn) {
      var active = btn.getAttribute('data-lang-switch') === currentLang;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    if (typeof window.onSPVaultI18nApply === 'function') window.onSPVaultI18nApply(currentLang);
  }

  function setLang(lang) {
    if (SUPPORTED.indexOf(lang) === -1 || lang === currentLang) return;
    currentLang = lang;
    try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) { /* ignore */ }
    apply();
  }

  function init() {
    // Vedi il commento in style.css su .lang-switch: la sigla lingua va in
    // un <span> proprio PRIMA di applicare .active, cosi' il
    // text-decoration non puo' mai sconfinare sul separatore del bottone
    // vicino qualunque sia il display del bottone che lo contiene.
    document.querySelectorAll('[data-lang-switch]').forEach(function (btn) {
      if (!btn.querySelector('.lang-code')) {
        var span = document.createElement('span');
        span.className = 'lang-code';
        span.textContent = btn.textContent;
        btn.textContent = '';
        btn.appendChild(span);
      }
    });
    apply();
    document.querySelectorAll('[data-lang-switch]').forEach(function (btn) {
      btn.addEventListener('click', function () { setLang(btn.getAttribute('data-lang-switch')); });
    });
  }

  window.SPVaultI18n = {
    get currentLang() { return currentLang; },
    t: t,
    setLang: setLang,
    init: init
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
