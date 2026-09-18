$ErrorActionPreference = 'Stop'

if (-not $env:PERSONAL_AI_UPDATE_URL) {
    throw 'Set PERSONAL_AI_UPDATE_URL to a release manifest URL before updating.'
}

$manifest = Invoke-RestMethod -Uri $env:PERSONAL_AI_UPDATE_URL -Headers @{ 'User-Agent' = 'Personal-AI-Updater' }
if (-not $manifest.url) {
    throw 'The release manifest does not contain a download URL.'
}

$download = Join-Path $env:TEMP 'PersonalAI-update.exe'
Invoke-WebRequest -Uri $manifest.url -OutFile $download
Write-Host "Downloaded Personal AI $($manifest.version) to $download"
Start-Process -FilePath $download
