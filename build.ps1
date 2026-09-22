# Compila dist\SPVault.exe (un solo file, senza console) e ne verifica il contenuto.
# Uso:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Playwright non ha un hook PyInstaller: --collect-all include il suo driver (node + cli.js).
# Il browser non viene incluso: il tool usa Chrome o Edge già installati.
# --copy-metadata porta nell'exe i metadati delle librerie, compresi i testi delle loro licenze
# (vedi THIRD-PARTY-NOTICES.md); la licenza di Python finisce in licenses\.
$metadata = "requests", "urllib3", "idna", "charset-normalizer", "certifi", "greenlet", "pyee", "typing_extensions" |
    ForEach-Object { "--copy-metadata", $_ }
$pythonLicense = python -c "import sys, pathlib; print(pathlib.Path(sys.base_prefix, 'LICENSE.txt'))"
# Icona: --icon per l'exe (Esplora file, collegamenti); png e ico anche dentro, per la finestra.
# Percorsi assoluti perché con --specpath build PyInstaller li cercherebbe in build\.
$assets = "$PSScriptRoot\assets"
python -m PyInstaller --noconfirm --clean --onefile --windowed --name SPVault `
    --collect-all playwright @metadata --add-data "$pythonLicense;licenses/python" `
    --icon "$assets\spvault.ico" --add-data "$assets\spvault.ico;assets" --add-data "$assets\spvault.png;assets" `
    --workpath build --specpath build --distpath dist `
    "$PSScriptRoot\spvault.py"
if ($LASTEXITCODE) { exit $LASTEXITCODE }

# Autotest dell'exe: driver di Playwright, Tk e hash devono funzionare nella versione compilata
$p = Start-Process "dist\SPVault.exe" -ArgumentList "--selftest" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "Autotest di SPVault.exe fallito (codice $($p.ExitCode))" }
$mb = [math]::Round((Get-Item "dist\SPVault.exe").Length / 1MB, 1)
Write-Host "OK: dist\SPVault.exe ($mb MB)"
