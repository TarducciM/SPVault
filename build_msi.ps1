# Crea dist\SPVault_<versione>_x64_en-US.msi (installer per utente) da dist\SPVault.exe.
# Prima eseguire build.ps1. Richiede WiX 5:  dotnet tool install --global wix --version 5.0.2
# Uso:  powershell -ExecutionPolicy Bypass -File build_msi.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PATH += ";$env:USERPROFILE\.dotnet\tools"

$version = (Select-String -Path spvault.py -Pattern '^__version__ = "(.+)"').Matches[0].Groups[1].Value
$exe = "dist\SPVault.exe"
if (-not (Test-Path $exe)) { throw "Manca ${exe}: eseguire prima build.ps1" }
$icon = "assets\spvault.ico"  # collegamenti e "App installate"

foreach ($ext in "WixToolset.UI.wixext", "WixToolset.Util.wixext") {
    if (-not (wix extension list -g | Select-String $ext)) { wix extension add -g "$ext/5.0.2" }
}
$msi = "dist\SPVault_${version}_x64_en-US.msi"
wix build installer\SPVault.wxs -arch x64 -culture en-US `
    -ext WixToolset.UI.wixext -ext WixToolset.Util.wixext `
    -d "Version=$version" -d "ExePath=$exe" -d "IconPath=$icon" -o $msi
if ($LASTEXITCODE) { exit $LASTEXITCODE }
Remove-Item ($msi -replace '\.msi$', '.wixpdb') -ErrorAction SilentlyContinue
$mb = [math]::Round((Get-Item $msi).Length / 1MB, 1)
Write-Host "OK: $msi ($mb MB)"
