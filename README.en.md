<img src="assets/app-icon.svg" width="96" alt="SPVault">

# SPVault

[![CI](https://github.com/TarducciM/SPVault/actions/workflows/ci.yml/badge.svg)](https://github.com/TarducciM/SPVault/actions/workflows/ci.yml)

[Italiano](README.md) · **English**

SPVault makes a **file-by-file** backup of a SharePoint library, of one of its folders or of a
OneDrive for Business folder, keeps the **previous versions** of changed files and, on every run,
**checks that nothing is missing**. All you need is to be able to open the files **in the browser**:
it also works as a **guest** of another organization, read-only, without the OneDrive client,
without apps registered in Azure and without administrator rights. It downloads only what has
changed, checks that everything has arrived and can run on its own every day. For Windows.

---

## Why

You have access to a SharePoint library or a shared folder, in your own organization or in another
one as a guest, and you want to keep an up-to-date, reliable copy of it on your PC or in your own
OneDrive.

The obvious way is **downloading from the browser**: you select a folder, press "Download" and
SharePoint prepares a zip. It works, but it is not fit for a backup:

- **there is no guarantee the zip contains everything.** When you download large folders, files are
  sometimes missing and nothing tells you: you find out when you look for a file that isn't there;
- **everything is downloaded again every time**, even if only one file has changed;
- **keeping versions takes a huge amount of space**: every version is a full copy, so ten backups of
  a 15 GB folder take 150 GB, almost all of it identical;
- **no visibility**: inside a zip you can't see what changed, what was deleted or whether something
  went wrong;
- **it is all manual**: someone has to remember to do it, wait for the zip, rename it, move it.

The "official" alternatives are often not an option:

- **the OneDrive sync client** can't be used with libraries of another organization that you access
  as a guest, unless the administrators enable it;
- **rclone, Microsoft Graph, Power Automate** and the like require an app registered in Azure or the
  **consent of a tenant administrator**, which a guest (and often an internal user too) doesn't
  have.

**The idea**: if the browser can see and download the files, so can a program that uses **the same
browser session and the same APIs as the SharePoint page**. But it does it properly: one file at a
time, only what has changed, checking at the end that everything has arrived.

## What it does

- **The link decides what to back up**: a library link backs up the library, a folder link (sharing
  links included) backs up only that folder. OneDrive for Business works too.
- Copies the selected items into `Current\`, with the **same structure as SharePoint** and the same
  modification dates.
- Downloads **only the files that changed**, identified by the **content hash** computed by
  SharePoint: an identical file is never downloaded again.
- Files and folders **renamed or moved** on SharePoint are moved locally too, without downloading
  them again.
- Keeps the **previous version** of every modified or deleted file in `_Versions\<date>_r<n>\`,
  keeping only the last N.
- **Checks on every backup that everything is there** and says so clearly: `VERIFICATION OK` or
  `VERIFICATION FAILED`, with the exact list of missing files.
- Reports separately any content that exists on SharePoint but **is not visible to your account**:
  no program can copy it with those credentials, but at least you know.
- **New folders** that appear on SharePoint are listed automatically, highlighted and, if you want,
  added to the backup automatically (the scheduled one too).
- Can keep the copy **inside OneDrive** with the files "online-only", and if the disk is too small it
  **downloads in batches**, waiting for OneDrive to free up space.
- Can run **on its own every day** (Windows Task Scheduler). If the PC is off at the scheduled time,
  the backup starts as soon as you turn it back on.
- Interface in **Italian or English** (automatic based on the Windows language, or your choice).
- Installs with a **per-user MSI** (no administrator rights needed), or you can use the
  **portable** version.

## How it works

### 1. The link decides what to back up

In the **SharePoint library or folder** field you paste a link copied from the browser:

- a **library** link, for example
  `https://contoso.sharepoint.com/sites/Marketing/Shared%20Documents/Forms/AllItems.aspx`, backs up
  the library: **What to back up** lists its top-level folders and files;
- a **folder** link backs up only that folder: **What to back up** lists its contents. Any of these
  works:
  - the address in the browser's address bar while the folder is open, for example
    `https://contoso.sharepoint.com/sites/Marketing/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2FMarketing%2FShared%20Documents%2FCampaigns`,
    or the direct address
    `https://contoso.sharepoint.com/sites/Marketing/Shared%20Documents/Campaigns`;
  - the link from **Copy link**, either in the form
    `https://contoso.sharepoint.com/:f:/r/sites/Marketing/Shared%20Documents/Campaigns?csf=1&web=1`
    or as a sharing link
    `https://contoso.sharepoint.com/:f:/s/Marketing/Ek3...Qw?e=AbC123`;
- Teams sites (`/teams/...`), libraries of the root site
  (`https://contoso.sharepoint.com/Shared%20Documents/...`) and **OneDrive for Business**
  (`https://contoso-my.sharepoint.com/personal/<name>_contoso_com/Documents/...`; the OneDrive
  address without a folder backs up all the files) work the same way.

After **Connect**, the source appears next to the account, for example
`Source: Shared Documents › Campaigns`, and every item in **What to back up** shows its size: you tick
what you want to copy. The selection is tied to SharePoint's IDs, not to names: a renamed folder
stays selected.

The link only says *what* to back up: access always happens with your account and your permissions.
SPVault checks the link before connecting and, if it's not suitable (the link of a site instead of a
library, the link of a file instead of a folder, an expired sharing link), explains which link is
needed.

If you change the link and it points to a different library or folder, the selection is cleared and
SPVault asks you to choose again what to back up, so backups don't get mixed up. To back up a
different library or folder, use a different backup folder as well: in the same one, the files of
the previous link would be moved to `_Versions\` as no longer selected.

### 2. Sign-in: a dedicated browser

SPVault launches the **Chrome or Edge you already have installed** (Chrome first, then Edge) via
[Playwright](https://playwright.dev/python/), with a **separate profile** that doesn't touch the
browser you use every day: `%LOCALAPPDATA%\SPVault\browser_profile`. No browser is downloaded.

- **The first time**, the browser opens in a window: sign in as usual (multi-factor authentication
  included) and answer **Yes** to "Stay signed in?".
- **On later runs**, the browser starts **hidden**, reuses the saved session and closes right away,
  after handing SPVault SharePoint's **session cookies** and the browser's **User-Agent**.
- **API calls** are made by SPVault itself using those cookies. The User-Agent is needed because
  SharePoint's v2.0 APIs reject the browser session (error 403) if the request doesn't present
  itself as a browser.
- **If the session expires** in the middle of a backup, SPVault renews it in the background with the
  hidden browser and carries on.
- **If Microsoft asks for your credentials again**, SPVault notices within a few seconds instead of
  waiting: from the window it opens the browser so you can sign in; during a scheduled backup it
  shows a notice.

SPVault sees exactly what you see in the browser: same permissions, no extra privileges. Apart from
Microsoft's sign-in pages opened in the browser, it talks only to SharePoint: no intermediate
servers, no telemetry.

### 3. File list: the "delta" API

The list comes from SharePoint's **delta** API (`/_api/v2.0/drives/{id}/root/delta`):

- **the first time** it returns the whole library: large libraries take a few minutes;
- **on later runs**, thanks to the saved token, it returns **only the changes**: a few seconds;
- **every 7 days** there is a full re-read anyway, to be safe (sooner if SharePoint considers the
  token expired).

The library tree is stored in a local SQLite database together with the IDs of files and folders,
and paths are rebuilt from there. So a folder **renamed or moved** on SharePoint is recognized and
**moved** locally too, instead of being downloaded again. The database is updated in a single
transaction: if reading is interrupted, the next run starts again from the last complete state.

If the link is to a folder and your account can't read the whole library (this happens as a guest
with the link of a single folder), SPVault reads only that folder, subfolder by subfolder with the
"children" API. In this case no change list is available and every backup re-reads the whole folder;
the hash comparison still avoids downloading unchanged files again.

### 4. What to download: the content hash

For every file, SharePoint computes a fingerprint of its content, the **quickXorHash**. SPVault
compares it with that of the file already saved in the backup:

| Situation                                             | What SPVault does                                     |
|-------------------------------------------------------|-------------------------------------------------------|
| identical file on SharePoint                          | nothing                                               |
| only a column or metadata changed on SharePoint       | nothing (the content is the same)                     |
| file renamed or moved on SharePoint                   | moves it within `Current\`, without downloading       |
| content modified on SharePoint                        | old copy to `_Versions\`, downloads the new one       |
| new file on SharePoint                                | downloads it                                          |
| file deleted on SharePoint, or no longer selected     | moves the local copy to `_Versions\`                  |
| file deleted from `Current\` or with a different size | downloads it again                                    |
| file in `Current\` that doesn't exist on SharePoint   | moves it to `_Versions\`                              |

To tell whether a local file is still in place, SPVault reads only its name, size and date, without
opening it: OneDrive "online-only" files are never downloaded back from the cloud just to check
them.

### 5. Downloads

- **4 in parallel**, each one first into a temporary folder (`%LOCALAPPDATA%\SPVault\tmp`);
- **the hash is computed during the download** and must match SharePoint's. If it doesn't match, the
  file is downloaded again; if it still doesn't match, it is kept with a warning in the log (this
  happens with some Office files, see the [FAQ](#faq));
- **if the connection drops**, the download **resumes where it left off**;
- **temporary errors** (too many requests, server busy) are retried with increasing waits,
  respecting the delays requested by SharePoint;
- **only once the download is complete** is the file moved into `Current\`, with SharePoint's
  modification date: `Current\` never gets half-downloaded files. If a previous version existed, it
  is moved to `_Versions\` first.

### 6. Versions

```
<backup folder>\
  Current\                   up-to-date copy, same structure as SharePoint
  _Versions\2026-09-21_r1\   previous versions of the files modified or deleted in that backup
  _Versions\2026-09-22_r1\
  _Logs\2026-09-22_r1.log    everything that was done in that backup
  _FileList.csv              every file with size, date, hash and status
```

- **The label** is the **date** plus the day's **revision number**: `_r1`, `_r2`, …
- **A folder in `_Versions\`** contains only the files that changed in that backup, not a full copy:
  ten versions take up little more than a single copy, not ten times as much. A backup in which
  nothing changes creates no version folder.
- **The last N version folders are kept** (**Versions to keep**, 10 by default); older ones are
  deleted. The last 100 logs are kept.
- **Nothing is deleted from `Current\`**: files deleted on SharePoint, or no longer part of the
  selection, are moved to `_Versions\`. So unticking a folder moves its copy to `_Versions\`, where
  it stays until that version drops out of the last N.
- **If SharePoint suddenly returns no files** for the selection while the backup contains some,
  SPVault stops instead of archiving everything.
- **The rest of the backup folder is left untouched**: SPVault only works in `Current\`,
  `_Versions\`, `_Logs\` and `_FileList.csv`.

### 7. Completeness check

This is the main reason SPVault exists. On every backup:

1. **Is the list complete?** SharePoint reports the total size of every folder. SPVault compares it,
   **down to the byte**, with the sum of the files in its list. If a folder doesn't add up, it
   drills down only into the subfolders that don't add up ("children" API), **retrieves the missing
   files** and removes those that no longer exist. If the differences are so widespread that more
   than 500 folders would need checking, the remaining ones are reported as `NOT VERIFIED`.
2. **Is everything on disk?** Every file in the list must be in `Current\` with SharePoint's current
   content. Missing ones are downloaded again immediately.
3. **The result**, in the log, in the window and in the status line:
   - `VERIFICATION OK: all N visible files (X GB) are in Current, identical to SharePoint`, or
   - `VERIFICATION FAILED: N files missing`, with the list in the log and in `_FileList.csv` and an
     on-screen notice. The next backup tries again.
4. **Content your account can't see.** If SharePoint counts more items (or more bytes) in a folder
   than are visible to your account, the difference is reported as `NOT ACCESSIBLE`, with the
   folder, the number of items and their size, and the summary adds a `WARNING` line. It doesn't
   fail the verification, because it can't be copied with your account.

`_FileList.csv` lists every file with **Path**, **Size (bytes)**, **Modified on SharePoint**,
**quickXorHash** and **Status** (`OK`, `MISSING` or `NOT ACCESSIBLE`). Fields are separated by
semicolons (if Excel shows everything in one column, open it with *Data > From Text/CSV*).

### 8. OneDrive and disk space

The backup folder can be inside OneDrive, so the copy also ends up in the cloud.

- **With the "online-only" option** (*After the upload to OneDrive keep the files online-only*, on by
  default) every copied file is marked as "Free up space": OneDrive uploads it and then removes it
  from the local disk.
- **Checks only read the name, size and date** of local files, so "online-only" files are never
  downloaded back from OneDrive.
- **Paths longer than 260 characters** are supported.

**When the disk is not big enough** (for example 260 GB to download and 100 GB free), SPVault
**downloads in batches**, as long as the backup folder is inside OneDrive and the "online-only"
option is on:

1. it downloads while at least 3 GB stay free, checking the hash of every file;
2. every copied file is marked "Free up space": OneDrive uploads it and, only once it is **in sync
   with the cloud**, removes it from the disk. A file that becomes "online-only" is the signal that
   it has been uploaded and that the space is really free;
3. when the disk is full it waits, with the status line
   `Waiting for OneDrive: N files to upload, X free on disk...`, and resumes as soon as there is room
   for the next file;
4. if OneDrive frees nothing for 30 minutes (for example because it is closed or paused), the
   backup stops with a clear message. The next backup resumes from there, without downloading again
   what is already there;
5. a file larger than all the space that can be freed is reported as `MISSING`.

OneDrive folders are recognized also when they are synced SharePoint or Teams libraries, because
OneDrive lists them in the Windows registry. If the backup folder is not in OneDrive and the space is
not enough, SPVault stops before it starts downloading and explains what to do.

### 9. New folders

The **What to back up** list is re-read every time SPVault opens (in the background, without opening
the browser), on every **Connect** and on every backup, including the scheduled one. A folder (or a
file) that appeared on SharePoint after the last read:

- shows up in the window marked `- NEW` and is written to the log:
  `New folder on SharePoint: <name>`;
- with the **Also back up new folders that appear on SharePoint** option (on by default) it is added
  to the selection automatically, so it is already in the next backup, the scheduled one included.

New subfolders inside folders that are already selected are always copied: they are part of the
chosen folder.

### 10. Scheduled backup

- **Schedule** creates the daily `SPVault` task in Windows Task Scheduler, for your user and
  **without administrator rights**. The task runs `SPVault.exe --run` with the window's settings
  (link, backup folder, selection, options, language). **Remove** deletes it; next to the buttons
  you see `(active)` or `(not scheduled)`.
- **The task survives shutdowns and restarts.** If the PC was off or asleep at the scheduled time,
  the backup starts **as soon as possible** once it is back on. It also runs on battery, has no time
  limit and waits for the network to be available. It runs in your Windows session, so it starts
  once you have signed in.
- **In `--run` mode** SPVault opens no windows and never shows the browser. If the session has
  expired, a Windows notice asks you to open SPVault and press **Connect**; if the verification
  fails, a notice shows the summary. The result of every run is in
  `%LOCALAPPDATA%\SPVault\scheduled_backup.log`, as well as in the log in `_Logs\`.
- **Two backups at the same time** (window and scheduled task) are not possible: the second one stops
  immediately with `A backup is already running`.
- **Uninstalling SPVault installed from the MSI** also removes the scheduled task.

## Installation and usage

### Requirements

- Windows 10 or 11, 64-bit;
- Google Chrome or Microsoft Edge installed (used for signing in);
- an account that can open the library or folder in the browser.

### Download

From the latest **[release](https://github.com/TarducciM/SPVault/releases/latest)**, download one of
the two files:

| File                                   | What it is                                                  |
|----------------------------------------|-------------------------------------------------------------|
| `SPVault_<version>_x64_en-US.msi`      | **Installer (recommended)**, per-user, no admin             |
| `SPVault_<version>_x64-portable.exe`   | Portable: no installation, run it from wherever you like    |

The **installer** puts the program in `%LOCALAPPDATA%\Programs\SPVault` and lets you choose:

- the **Start menu shortcut** (on by default);
- the **desktop shortcut**;
- **start at Windows sign-in** (on by default): SPVault opens minimized and immediately refreshes
  folders and sizes;
- the **app language**: automatic, Italian or English (you can change it later in the window).

Uninstall it from "Apps & features"; uninstalling also removes the scheduled backup. The app's data
(settings, session, state) is kept, so a reinstall picks up where you left off; to remove it, delete
`%LOCALAPPDATA%\SPVault`.

The **portable version** is fine for trying it out. However, if you schedule the backup and then move
or delete the file, the scheduled task stops working, because it points to where the exe used to
be.

### First run

1. Launch SPVault. The first time, the fields are empty.
2. Paste into the **SharePoint library or folder** field the link of the library or folder to back
   up (see [The link decides what to back up](#1-the-link-decides-what-to-back-up)) and choose the
   **Backup folder** with **Browse...**.
3. Press **Connect**. The first time, the browser opens: sign in and answer **Yes** to "Stay signed
   in?". Next to **Connect** you see `Connected as <account>` and the source (`Source: ...`), and
   **What to back up** lists the items of the link, each with its size.
4. Tick what to back up. Below you see the selected total, the free disk space and the time the sizes
   were last updated; they are refreshed automatically when SPVault opens and on every backup.
5. Press **Run backup**. The progress bar and the status line always show the current phase and the
   elapsed seconds:

   ```
   Connecting to SharePoint → reading the changes → checking the file list → download (percentage)
   → checking the files on disk → cleanup and versions → ✓ VERIFICATION OK
   ```

   **Stop** interrupts the backup; the next one resumes where it stopped.
6. For automatic backups, set the time in **Automatic backup every day at** and press **Schedule**.

The **first backup** reads the full list and downloads everything you selected. Later backups
download only the differences: a backup with no changes takes a few seconds. To give an idea: on a
library of about 260 GB and 228,000 items the first full listing took about 12 minutes, later ones a
few seconds, and downloads ran at about 25 MB/s.

### Options

- **Versions to keep**: how many version folders to keep in `_Versions\` (10 by default).
- **After the upload to OneDrive keep the files online-only (they use no space on this PC)**: see
  [OneDrive and disk space](#8-onedrive-and-disk-space). It has no effect outside OneDrive.
- **Also back up new folders that appear on SharePoint**: see [New folders](#9-new-folders).
- **Lingua / Language**: `Automatica / Automatic` (Italian if Windows is in Italian, English
  otherwise), `Italiano` or `English`. The change is immediate, even during a backup, and also
  applies to the scheduled backup, the logs and `_FileList.csv`.

SPVault handles one link and one backup folder at a time: the ones in the window, which the scheduled
backup uses too.

## App files

In `%LOCALAPPDATA%\SPVault`:

| File                     | Contents                                                           |
|--------------------------|--------------------------------------------------------------------|
| `config.json`            | window settings                                                    |
| `browser_profile\`       | dedicated browser profile: contains the sign-in session            |
| `state_*.sqlite`         | library tree and backup state                                      |
| `scheduled_backup.log`   | results of scheduled backups                                       |
| `tmp\`                   | downloads in progress                                              |

`browser_profile\` gives access to your SharePoint files just like a password: don't share it.
Deleting it is the same as signing out; the next **Connect** asks you to sign in again.

If `state_*.sqlite` is lost, nothing is downloaded from scratch: SPVault recognizes the files already
in `Current\` by size and date.

## FAQ

**`Not connected: press "Connect"`.** The session has expired, or your organization requires you to
sign in again after a while. Press **Connect** and sign in again in the browser window. Answering
**Yes** to "Stay signed in?" makes the session last longer.

**The link is not accepted.** SPVault explains why:

- `This link is to a site, not a library`: open the library or folder to back up in the browser and
  copy the link from the address bar;
- `The link is to a file, not a folder`: copy the link of the folder that contains the file;
- `Sharing link not valid, expired or not accessible with this account`: open the link in the
  browser with the same account; if it doesn't open, ask whoever shared it for a new link.

**`VERIFICATION FAILED`.** Some files were not downloaded (network errors, full disk, server
errors…). The list is in the log in `_Logs\` and in `_FileList.csv` (status `MISSING`). The next
backup tries them again.

**`NOT ACCESSIBLE`.** SharePoint counts items that your account cannot see, for example folders with
different permissions. No program can copy them with your account: to get them, ask whoever manages
the site for access.

**`Not enough disk space`.** It only appears if the backup folder is not inside OneDrive, or if the
"online-only" option is off. The solutions: put the backup folder in OneDrive with "online-only" on,
so SPVault downloads in batches; select fewer folders; free up some space.

**`OneDrive has not freed any space in the last 30 minutes`.** While downloading in batches,
OneDrive has to upload the files to free the disk. Check that OneDrive is running, signed in and not
paused, then run the backup again: it resumes where it stopped.

**An Office file shows `WARNING: the downloaded file does not match the SharePoint hash`.** Some
libraries modify Office documents at download time (for example to write the library's columns into
the file). The file is kept and flagged in the log.

**OneNote notebooks are not copied.** They are not files but special collections: they are skipped
and reported in the log (`Skipping ... (OneNote notebook, not a file)`).

**`Cannot start Chrome or Edge`.** SPVault uses the Chrome or Edge installed on the PC: install one
of them. It doesn't need to be the default browser.

**The antivirus flags the exe.** Executables built with PyInstaller are sometimes flagged by mistake.
You can check that the file comes from this repository's releases page, or run SPVault from source
(see [Development](#development)).

**Does SPVault get around my organization's permissions or rules?** No. It uses your sign-in and
sees only what you see in the browser. Before keeping a copy of other people's data, make sure the
rules of whoever manages it allow it.

**How do I report a bug?** Open an issue on
[GitHub Issues](https://github.com/TarducciM/SPVault/issues) with the SPVault version (it's in the
window title), the Windows version, what you were doing, the message you saw and the relevant lines
of the log (`_Logs\<date>_r<n>.log` or `scheduled_backup.log`). Before attaching a log, remove any
file, folder and account names you don't want to make public, and never paste sharing links or the
contents of `browser_profile\`.

## Development

```
spvault.py                     the whole app: window, sign-in, backup, verification, --run, --minimized, --selftest
tests/fakes.py                 simulated SharePoint server (drives, children, delta, download, faults)
tests/conftest.py              fixtures: isolated data folder, simulated server, window
tests/test_*.py                tests: hash, utilities, full backup scenarios, disk space, window, languages
requirements.txt               app dependencies (playwright, requests)
requirements-dev.txt           plus: pytest, ruff, pyinstaller, pillow
build.ps1                      builds dist\SPVault.exe and runs its self-test
build_msi.ps1                  builds dist\SPVault_<version>_x64_en-US.msi
installer/SPVault.wxs          per-user MSI installer (WiX 5)
assets/make_icon.py            draws the icon (spvault.ico, spvault.png) and the social preview
.github/workflows/ci.yml       lint, tests and build of exe and MSI
.github/workflows/release.yml  draft release from a vX.Y.Z tag
```

You need Python 3.12 or later on Windows. There is no need for `playwright install`: SPVault uses the
Chrome or Edge already installed.

```powershell
python -m pip install -r requirements-dev.txt
python spvault.py                                   # run from source
python -m ruff check .
python -m pytest                                    # no Internet access: uses the simulated server
.\build.ps1                                         # dist\SPVault.exe + self-test (--selftest)
dotnet tool install --global wix --version 5.0.2    # one time only (requires the .NET SDK)
.\build_msi.ps1                                     # MSI installer
```

Command-line options:

| Option         | Effect                                                                  |
|----------------|-------------------------------------------------------------------------|
| *(none)*       | opens the window                                                        |
| `--run`        | backup without a window (used by the scheduled task)                    |
| `--minimized`  | opens the window minimized (start at Windows sign-in)                   |
| `--selftest`   | checks that the exe contains everything it needs (used by CI)           |

- **The tests** simulate a complete SharePoint server, including faults: the connection dropping
  mid-download, an expired session, a wrong hash, files missing from the delta list, "ghost" files,
  downloads that cannot succeed, inaccessible content, an expired delta token, paths over 260
  characters, a disk that is too small with a simulated OneDrive that frees space (or doesn't). The
  hash is checked against a faithful port of Microsoft's reference implementation.
- **UI texts** are written in Italian inside `tr("...")`; the English translation goes into the `EN`
  dictionary in `spvault.py`. The tests check that every text has its translation, with the same
  placeholders, and that there are no unused translations.
- **CI** (`ci.yml`, GitHub Actions on Windows) runs on every push to `main` and on every pull
  request: lint and tests on Python 3.12 and 3.14, then it builds the exe and the MSI, runs the exe's
  self-test and publishes both as artifacts.
- **The release** (`release.yml`) is triggered by a `vX.Y.Z` tag:
  - checks that the tag matches `__version__` in `spvault.py`;
  - runs lint and tests again;
  - builds `SPVault_<version>_x64-portable.exe` and `SPVault_<version>_x64_en-US.msi`;
  - creates a **draft release** with the two files and the notes (download table plus the list of
    changes prepared by GitHub);
  - deletes the draft if anything goes wrong (the tag stays: just re-run the workflow).

  The draft is reviewed and published manually on GitHub:

  ```powershell
  # update __version__ in spvault.py and CHANGELOG.md, commit, then:
  git tag v0.1.0
  git push origin v0.1.0
  ```

## License

[MIT](LICENSE) © 2026 Michele Tarducci. The release executables include third-party components
(Python, Tcl/Tk, Playwright with Node.js, requests and others), each under its own license: see
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

SPVault is an independent project, not affiliated with Microsoft. SharePoint, OneDrive and Microsoft
Edge are trademarks of Microsoft; Google Chrome is a trademark of Google.
