# 每日定时任务的启动脚本（Windows 任务计划程序调用）
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = $env:DMR_PYTHON
if (-not $Python) { $Python = "python" }
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python not found. Install Python and add it to PATH, or set DMR_PYTHON."
    exit 1
}

$env:PYTHONPATH = "$ProjectRoot\deps2;$ProjectRoot\deps;$ProjectRoot"
$env:PYTHONIOENCODING = "utf-8"
$env:TQDM_DISABLE = "1"

$LogDir = Join-Path $ProjectRoot "output\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("task_" + (Get-Date -Format "yyyyMMdd") + ".log")

& $Python (Join-Path $ProjectRoot "main.py") *>> $LogFile
exit $LASTEXITCODE
