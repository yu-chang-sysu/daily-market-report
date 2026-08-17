# 开机自启的后台循环：每天 16:30 收盘报告 + 次日 09:00 盘前执行报告
# 配合 install_autopilot.ps1 使用（放入启动文件夹）
$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# 从 config.yaml 读取运行时间
$cfg = Get-Content (Join-Path $ProjectRoot "config.yaml") -Raw
$RunTime = "16:30"
if ($cfg -match 'run_time:\s*"([^"]+)"') { $RunTime = $Matches[1] }
$MorningTime = "09:00"
if ($cfg -match 'morning_time:\s*"([^"]+)"') { $MorningTime = $Matches[1] }

function Test-Done([string]$mode) {
    $stateFile = Join-Path $ProjectRoot ("output\state\" + $mode + ".txt")
    if (Test-Path -LiteralPath $stateFile) {
        $content = (Get-Content -LiteralPath $stateFile -Raw).Trim()
        return $content -eq (Get-Date -Format "yyyy-MM-dd")
    }
    return $false
}

while ($true) {
    $now = Get-Date
    $jobs = @(
        @{ Time = $RunTime; Script = "run_daily.ps1"; Mode = "evening" },
        @{ Time = $MorningTime; Script = "run_morning.ps1"; Mode = "morning" }
    )
    $candidates = @()
    foreach ($j in $jobs) {
        # 今天这份报告已经生成过（含补跑），不再重复
        if (Test-Done $j.Mode) { continue }
        $parts = $j.Time.Split(":")
        $t = Get-Date -Year $now.Year -Month $now.Month -Day $now.Day `
                      -Hour ([int]$parts[0]) -Minute ([int]$parts[1]) -Second 0
        # 到点已过且今天还没跑 -> 立即补跑（只补最近一天，不补历史多天）
        if ($t -le $now) {
            $t = $now
        }
        $candidates += [pscustomobject]@{ At = $t; Script = $j.Script }
    }
    if ($candidates.Count -eq 0) {
        # 今天两份都已完成，直接睡到明天最早的那个时间
        foreach ($j in $jobs) {
            $parts = $j.Time.Split(":")
            $t = Get-Date -Year $now.Year -Month $now.Month -Day $now.Day `
                          -Hour ([int]$parts[0]) -Minute ([int]$parts[1]) -Second 0
            $candidates += [pscustomobject]@{ At = $t.AddDays(1); Script = $j.Script }
        }
    }
    $next = ($candidates | Sort-Object At | Select-Object -First 1)
    $sleepSec = ($next.At - (Get-Date)).TotalSeconds
    if ($sleepSec -gt 0) { Start-Sleep -Seconds $sleepSec }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot $next.Script)
    Start-Sleep -Seconds 120   # 防止异常导致快速重复
}
