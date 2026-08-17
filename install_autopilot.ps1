# 备用方案：把后台循环脚本加入"启动"文件夹（开机自动运行，每天到点出报告）
# 用法：powershell -ExecutionPolicy Bypass -File install_autopilot.ps1
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartupDir = [Environment]::GetFolderPath("Startup")
$CmdPath = Join-Path $StartupDir "MarketDailyReport.cmd"

$line = "@echo off`r`nstart `"MarketDailyReport`" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ProjectRoot\autopilot_loop.ps1`""
Set-Content -Path $CmdPath -Value $line -Encoding ASCII

Write-Host "已安装开机自启：$CmdPath"
Write-Host "删除：Remove-Item `"$CmdPath`""
