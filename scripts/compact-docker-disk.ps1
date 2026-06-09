# Compact Docker's WSL 2 virtual disk — returns freed space back to Windows.
# Run as Administrator after doing `docker system prune -a -f --volumes`.
# Docker Desktop must be fully quit before running this.

$vhdxPath = "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx"

Write-Host ""
Write-Host "=== Docker WSL Disk Compaction ===" -ForegroundColor Cyan
Write-Host ""

# Check running as admin
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Run this script as Administrator (right-click PowerShell -> Run as administrator)" -ForegroundColor Red
    exit 1
}

# Check vhdx exists
if (-not (Test-Path $vhdxPath)) {
    Write-Host "ERROR: vhdx not found at: $vhdxPath" -ForegroundColor Red
    Write-Host "Docker Desktop may not be installed or may use a different path." -ForegroundColor Yellow
    exit 1
}

$sizeBefore = (Get-Item $vhdxPath).Length / 1GB
Write-Host "Disk size before: $([math]::Round($sizeBefore, 2)) GB" -ForegroundColor Yellow

# Shut down WSL completely
Write-Host ""
Write-Host "Shutting down WSL..." -ForegroundColor White
wsl --shutdown
Start-Sleep -Seconds 3

# Run diskpart compaction
Write-Host "Compacting virtual disk (this takes 1-3 minutes)..." -ForegroundColor White

$diskpartScript = @"
select vdisk file="$vhdxPath"
attach vdisk readonly
compact vdisk
detach vdisk
exit
"@

$diskpartScript | diskpart | Out-Null

$sizeAfter = (Get-Item $vhdxPath).Length / 1GB
$saved = $sizeBefore - $sizeAfter

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Disk size before : $([math]::Round($sizeBefore, 2)) GB" -ForegroundColor Yellow
Write-Host "Disk size after  : $([math]::Round($sizeAfter,  2)) GB" -ForegroundColor Green
Write-Host "Space returned   : $([math]::Round($saved,      2)) GB" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now start Docker Desktop and run: docker compose up -d" -ForegroundColor White
