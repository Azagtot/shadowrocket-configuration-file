# PowerShell Uninstaller / Rollback for Antigravity Selective Local MITM Proxy on Windows Workstation

[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host " Antigravity PC MITM Proxy Uninstaller / Rollback" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow

$taskName = "AntigravityMitmProxy"

# 1. Stop and remove scheduled task
Write-Host "[1/4] Stopping and removing Scheduled Task '$taskName'..." -ForegroundColor Yellow
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "  -> Task removed." -ForegroundColor Green
} else {
    Write-Host "  -> Task not registered." -ForegroundColor Gray
}

# 2. Terminate any running pythonw instances running mitm_proxy.py
Write-Host "[2/4] Terminating running proxy processes..." -ForegroundColor Yellow
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*mitm_proxy.py*" } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "  -> Terminated PID $($_.ProcessId)" -ForegroundColor Gray
}

# 3. Clean Environment Variables
Write-Host "[3/4] Cleaning User Environment Variables..." -ForegroundColor Yellow
[Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS", $null, "User")
[Environment]::SetEnvironmentVariable("HTTP_PROXY", $null, "User")
[Environment]::SetEnvironmentVariable("HTTPS_PROXY", $null, "User")
Write-Host "  -> NODE_EXTRA_CA_CERTS, HTTP_PROXY, HTTPS_PROXY cleared." -ForegroundColor Green

# 4. Remove Root CA from Windows Store
Write-Host "[4/4] Removing Root CA from Windows Certificate Store..." -ForegroundColor Yellow
& certutil -user -delstore "ROOT" "Antigravity Local Bypass CA"
Write-Host "  -> Root CA deleted." -ForegroundColor Green

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " [DONE] PC MITM Proxy has been completely uninstalled." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
