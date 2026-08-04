# Installa il CLI globale di Atlas: irm <raw-url>/install.ps1 | iex
#
# Gemello di install.sh, per Windows nativo (nessun WSL, nessuna Git Bash richiesta).
# Nessun parsing JSON: l'URL "releases/latest/download/<asset>" di GitHub risolve
# sempre all'asset dell'ultima release, senza passare dall'API.
# ATLAS_INSTALL_DIR/ATLAS_INSTALL_URL sono override per i test, non per l'uso normale.

$ErrorActionPreference = "Stop"

$Repo = "strawberry-code/atlas"
$Dir = if ($env:ATLAS_INSTALL_DIR) { $env:ATLAS_INSTALL_DIR } else { Join-Path $HOME ".local\bin" }
$Url = if ($env:ATLAS_INSTALL_URL) { $env:ATLAS_INSTALL_URL } else { "https://github.com/$Repo/releases/latest/download/atlas" }

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "  atlas richiede python sul PATH: installalo prima di riprovare." -ForegroundColor Yellow
}

New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$Target = Join-Path $Dir "atlas"
$Tmp = "$Target.tmp"

try {
    Invoke-WebRequest -Uri $Url -OutFile $Tmp -UseBasicParsing
    Move-Item -Force $Tmp $Target
} finally {
    if (Test-Path $Tmp) { Remove-Item -Force $Tmp }
}

# atlas e' uno zipapp senza estensione: PATHEXT non lo trova mai come comando nudo.
# Il lanciatore .cmd e' statico e non versionato: 'atlas update' sostituisce solo
# $Target, non deve mai toccare questo file.
$Wrapper = Join-Path $Dir "atlas.cmd"
Set-Content -Path $Wrapper -Value "@echo off`r`npython `"%~dp0atlas`" %*" -Encoding ASCII -NoNewline

Write-Host "  atlas installato in $Target"

$PathDirs = $env:Path -split ";"
if ($PathDirs -notcontains $Dir) {
    Write-Host "  $Dir non e' nel PATH. Aggiungilo per l'utente corrente con:"
    Write-Host "    [Environment]::SetEnvironmentVariable('Path', `"`$env:Path;$Dir`", 'User')"
    Write-Host "  poi apri una shell nuova."
}
