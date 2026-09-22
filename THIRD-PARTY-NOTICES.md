# Third-party notices

SPVault is [MIT licensed](LICENSE). The source code in this repository is SPVault's own; the release
executables, however, bundle third-party software, each component under its own license.

The executables (`SPVault_<version>_x64-portable.exe`, and the `SPVault.exe` installed by
`SPVault_<version>_x64_en-US.msi`) are built with [PyInstaller](https://pyinstaller.org) as a single
file that contains the Python runtime and the packages listed below. **No web browser is bundled**:
SPVault uses the Google Chrome or Microsoft Edge already installed on the PC.

## Bundled in the release executables

| Component | Used for | License | Project |
|---|---|---|---|
| Python runtime and standard library | runs SPVault | PSF License Agreement | <https://www.python.org> |
| Tcl/Tk (through `tkinter`) | the window | Tcl/Tk License (BSD-style) | <https://www.tcl-lang.org> |
| Playwright for Python | starts Chrome/Edge for the sign-in | Apache-2.0 | <https://github.com/microsoft/playwright-python> |
| Playwright driver (`playwright-core`) | same, bundled with Playwright for Python | Apache-2.0 | <https://github.com/microsoft/playwright> |
| Node.js | runs the Playwright driver | MIT, with its own third-party notices | <https://nodejs.org> |
| greenlet | used by Playwright | MIT AND PSF-2.0 | <https://github.com/python-greenlet/greenlet> |
| pyee | used by Playwright | MIT | <https://github.com/jfhbrook/pyee> |
| typing_extensions | used by pyee | PSF-2.0 | <https://github.com/python/typing_extensions> |
| requests | HTTP calls to SharePoint | Apache-2.0 | <https://github.com/psf/requests> |
| urllib3 | used by requests | MIT | <https://github.com/urllib3/urllib3> |
| idna | used by requests | BSD-3-Clause | <https://github.com/kjd/idna> |
| charset-normalizer | used by requests | MIT | <https://github.com/jawah/charset_normalizer> |
| certifi | CA certificates for HTTPS | MPL-2.0 | <https://github.com/certifi/python-certifi> |
| PyInstaller bootloader and runtime hooks | starts the single-file executable | GPL-2.0-or-later with the Bootloader Exception; runtime hooks Apache-2.0 | <https://github.com/pyinstaller/pyinstaller> |

### Python runtime

Python is distributed under the Python Software Foundation License Agreement. The Windows build of
Python, which the executables are made from, also contains third-party libraries under their own
licenses, among others OpenSSL (Apache-2.0), SQLite (public domain), libffi (MIT), zlib (zlib
License), bzip2 (BSD-style), XZ Utils / liblzma, Expat (MIT), mpdecimal (BSD-2-Clause) and Zstandard
(BSD-3-Clause), plus the Microsoft Visual C++ runtime files that Python for Windows ships with. The
full texts are in Python's documentation: [History and License](https://docs.python.org/3/license.html).

### Tcl/Tk

Tcl and Tk, used by Python's `tkinter` module for the window, are distributed under the Tcl/Tk
license, a BSD-style license: <https://www.tcl-lang.org/software/tcltk/license.html>.

### Playwright and Node.js

Playwright for Python and the Playwright driver (`playwright-core`) are © Microsoft Corporation and
licensed under the Apache License 2.0. Playwright's `NOTICE` file states that it contains code
derived from the [Puppeteer](https://github.com/puppeteer/puppeteer) project, also under the Apache
License 2.0.

The driver runs on Node.js, which is licensed under the MIT License and includes further components
under their own licenses, all listed in Node.js's `LICENSE` file. `playwright-core` also bundles npm
packages, listed with their licenses in its `ThirdPartyNotices.txt` and `lib/*.js.LICENSE` files.

The build includes the whole Playwright package (`--collect-all playwright`), so these files ship
unchanged inside the executable: `playwright/driver/LICENSE` (Node.js) and
`playwright/driver/package/` (`LICENSE`, `NOTICE`, `ThirdPartyNotices.txt`). They are also available
in the projects' repositories.

Playwright is only used to start the installed Chrome or Edge; the browsers Playwright can download
are not part of SPVault.

### certifi

certifi provides Mozilla's collection of root certificates and is licensed under the Mozilla Public
License 2.0. SPVault uses it unmodified; its source code, including the certificate bundle, is
available at <https://github.com/certifi/python-certifi>.

### PyInstaller

PyInstaller is licensed under the GNU General Public License, version 2 or later, with the
**Bootloader Exception**: the bootloader and related files that PyInstaller embeds in the executable
may be distributed as part of the bundled application under any license, so the Bootloader Exception
places no requirements on SPVault itself. PyInstaller's run-time hooks, also embedded in the
executable, are licensed under the Apache License 2.0. PyInstaller itself is a build tool and is not
distributed.

## MSI installer

The MSI installer is built with the [WiX Toolset](https://github.com/wixtoolset/wix) 5 and contains
parts of it: the standard installer dialogs and the custom-action library used to remove the
scheduled backup on uninstall. They are licensed under the Microsoft Reciprocal License (MS-RL); their
source code is available in the WiX Toolset repository.

## Source repository

`tests/fakes.py` contains a Python port of the QuickXorHash reference implementation published by
Microsoft in the [OneDrive API documentation](https://github.com/OneDrive/onedrive-api-docs) (MIT
License, Copyright (c) 2017 Microsoft Corporation). It is used only by the tests, to check SPVault's
own implementation, and is not part of the executables.

The development tools (pytest, Ruff, PyInstaller, Pillow, WiX Toolset) are used to test and build SPVault and,
apart from the parts listed above, are not distributed with it.
