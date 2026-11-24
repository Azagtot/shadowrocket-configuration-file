# PowerShell 5.1+ / 7+ Installer for Antigravity Selective Local MITM Proxy on Windows Workstation
# Idempotent: safe to run multiple times.

[CmdletBinding()]
param(
    [string]$SourceDir = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Antigravity PC MITM Proxy Installer for Windows" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$TargetDir = Join-Path $env:USERPROFILE ".antigravity\proxy"
if (-not (Test-Path $TargetDir)) {
    Write-Host "[1/6] Creating directory: $TargetDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
} else {
    Write-Host "[1/6] Target directory exists: $TargetDir" -ForegroundColor Green
}

# 2. Copy proxy script and certificates
$RequiredFiles = @("mitm_proxy.py", "ca.pem", "leaf.pem", "leaf.key")
foreach ($file in $RequiredFiles) {
    $srcPath = Join-Path $SourceDir $file
    if (-not (Test-Path $srcPath)) {
        Write-Error "Required file not found: $srcPath. Ensure all files are placed in the installer directory."
    }
    Copy-Item -Path $srcPath -Destination (Join-Path $TargetDir $file) -Force
    Write-Host "  -> Installed $file" -ForegroundColor Gray
}
Write-Host "[2/6] Files copied successfully." -ForegroundColor Green

# 3. Locate Python / pythonw
$pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Error "python.exe was not found in PATH! Please install Python 3.10+ and add it to PATH."
}
$pythonDir = Split-Path $pythonCmd.Source
$pythonwPath = Join-Path $pythonDir "pythonw.exe"
if (-not (Test-Path $pythonwPath)) {
    $pythonwPath = $pythonCmd.Source
    Write-Host "  Notice: pythonw.exe not found, falling back to python.exe" -ForegroundColor Yellow
}
Write-Host "[3/6] Python interpreter detected: $pythonwPath" -ForegroundColor Green

# 4. Import Root CA into CurrentUser Root Store
$caPath = Join-Path $TargetDir "ca.pem"
Write-Host "[4/6] Installing Root CA to Windows Certificate Store..." -ForegroundColor Yellow
$certUtilOutput = & certutil -user -addstore -f "ROOT" "$caPath"
if ($LASTEXITCODE -eq 0) {
    Write-Host "  -> Root CA 'Antigravity Local Bypass CA' installed into CurrentUser ROOT store." -ForegroundColor Green
} else {
    Write-Warning "certutil warning/output: $certUtilOutput"
}

# 5. Set Environment Variables
Write-Host "[5/6] Configuring User Environment Variables..." -ForegroundColor Yellow
[Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS", "$caPath", "User")
[Environment]::SetEnvironmentVariable("HTTP_PROXY", "http://127.0.0.1:18888", "User")
[Environment]::SetEnvironmentVariable("HTTPS_PROXY", "http://127.0.0.1:18888", "User")
Write-Host "  -> NODE_EXTRA_CA_CERTS = $caPath" -ForegroundColor Gray
Write-Host "  -> HTTP_PROXY / HTTPS_PROXY = http://127.0.0.1:18888" -ForegroundColor Gray

# 6. Configure Windows Scheduled Task (Autostart on Logon without console window)
Write-Host "[6/6] Configuring Scheduled Task 'AntigravityMitmProxy'..." -ForegroundColor Yellow
$taskName = "AntigravityMitmProxy"
$scriptPath = Join-Path $TargetDir "mitm_proxy.py"

$action = New-ScheduledTaskAction -Execute "$pythonwPath" -Argument "`"$scriptPath`"" -WorkingDirectory "$TargetDir"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Google Antigravity Selective Local MITM Proxy (127.0.0.1:18888)" | Out-Null
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2

# Verify Port Listening
$portCheck = Test-NetConnection -ComputerName 127.0.0.1 -Port 18888 -InformationLevel Quiet
if ($portCheck) {
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " [SUCCESS] Antigravity MITM Proxy is ACTIVE on 127.0.0.1:18888!" -ForegroundColor Green
    Write-Host " Autostart configured for logon as '$taskName'." -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
} else {
    Write-Warning "Proxy port 18888 is not yet responding. Check log at $env:TEMP\antigravity_mitm_proxy.log"
}
