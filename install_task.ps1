# Register Windows scheduled tasks:
#   MarketDailyReport    -> daily at schedule.run_time      (evening report)
#   MarketMorningReport  -> daily at schedule.morning_time  (pre-market report)
# Usage: powershell -ExecutionPolicy Bypass -File install_task.ps1
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunScript = Join-Path $ProjectRoot "run_daily.ps1"
$MorningScript = Join-Path $ProjectRoot "run_morning.ps1"

# Read run times from config.yaml
$cfg = Get-Content (Join-Path $ProjectRoot "config.yaml") -Raw
$Time = "16:30"
if ($cfg -match 'run_time:\s*"([^"]+)"') { $Time = $Matches[1] }
$MorningTime = "09:00"
if ($cfg -match 'morning_time:\s*"([^"]+)"') { $MorningTime = $Matches[1] }

$tr1 = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$RunScript`""
$tr2 = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$MorningScript`""

# 优先用 PowerShell ScheduledTasks 注册（可启用"错过后尽快运行"，即电脑开机/唤醒后补跑）
$regOk = $true
try {
    $action1 = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`""
    $action2 = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$MorningScript`""
    $trigger1 = New-ScheduledTaskTrigger -Daily -At $Time
    $trigger2 = New-ScheduledTaskTrigger -Daily -At $MorningTime
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
    Register-ScheduledTask -TaskName "MarketDailyReport" -Action $action1 -Trigger $trigger1 `
                           -Settings $settings -Description "Daily evening market report" -Force | Out-Null
    Register-ScheduledTask -TaskName "MarketMorningReport" -Action $action2 -Trigger $trigger2 `
                           -Settings $settings -Description "Daily pre-market execution report" -Force | Out-Null
    $catchUp = $true
} catch {
    $regOk = $false
    $catchUp = $false
}

if (-not $regOk) {
    Write-Host "[!] Register-ScheduledTask unavailable, falling back to schtasks (no catch-up)."
    schtasks /Create /F /TN "MarketDailyReport" /SC DAILY /ST $Time /TR $tr1
    if ($LASTEXITCODE -ne 0) {
        throw "schtasks failed for MarketDailyReport (exit $LASTEXITCODE). Run this script from a normal (non-sandboxed) PowerShell window."
    }
    schtasks /Create /F /TN "MarketMorningReport" /SC DAILY /ST $MorningTime /TR $tr2
    if ($LASTEXITCODE -ne 0) {
        throw "schtasks failed for MarketMorningReport (exit $LASTEXITCODE). Run this script from a normal (non-sandboxed) PowerShell window."
    }
}

Write-Host ""
Write-Host "[OK] MarketDailyReport scheduled: daily $Time  ->  $RunScript"
Write-Host "[OK] MarketMorningReport scheduled: daily $MorningTime  ->  $MorningScript"
if ($catchUp) {
    Write-Host "[OK] Catch-up enabled: missed runs will execute when the PC is next turned on / wakes up."
} else {
    Write-Host "[!] Catch-up NOT enabled (task will be skipped if the PC is off at the scheduled time)."
}
Write-Host ""
Write-Host "Verify with:"
Write-Host "  schtasks /Query /TN MarketDailyReport /V /FO LIST"
Write-Host "  schtasks /Query /TN MarketMorningReport /V /FO LIST"
Write-Host ""
Write-Host "Remove with:"
Write-Host "  schtasks /Delete /TN MarketDailyReport /F"
Write-Host "  schtasks /Delete /TN MarketMorningReport /F"
Write-Host ""
Write-Host "Manual test: powershell -ExecutionPolicy Bypass -File `"$RunScript`""
