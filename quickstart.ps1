# 每日股市观察报告（Daily Market Report）- 小白一步到位脚本
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\quickstart.ps1
#   powershell -ExecutionPolicy Bypass -File .\quickstart.ps1 -InstallTask
#   powershell -ExecutionPolicy Bypass -File .\quickstart.ps1 -TestRun
param(
    [switch]$InstallTask,
    [switch]$TestRun,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Find-Python {
    if ($env:DMR_PYTHON -and (Test-Path $env:DMR_PYTHON)) { return $env:DMR_PYTHON }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $v = & $py.Source -3 -c "import sys; print(sys.executable)" 2>$null
        if ($v) { return $v.Trim() }
    }
    return $null
}

$Python = Find-Python
if (-not $Python) {
    Write-Host ""
    Write-Host "[错误] 未检测到 Python。请先安装 Python 3.10+ 并勾选 'Add python to PATH'："
    Write-Host "  winget install Python.Python.3.13"
    Write-Host "  或到 https://www.python.org/downloads/ 下载安装。"
    exit 1
}
Write-Host "[1/5] 检测到 Python: $Python"

$VenvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Write-Host "[2/5] 创建虚拟环境 .venv ..."
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "创建虚拟环境失败" }
}
Write-Host "[2/5] 使用虚拟环境 Python: $VenvPy"

if (-not $SkipInstall) {
    Write-Host "[3/5] 安装依赖 (pip install -r requirements.txt) ..."
    & $VenvPy -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "升级 pip 失败" }
    & $VenvPy -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "依赖安装失败" }
}

$Config = Join-Path $ProjectRoot "config.yaml"
if (-not (Test-Path $Config)) {
    Write-Host "[4/5] 生成 config.yaml ..."
    Copy-Item (Join-Path $ProjectRoot "config.example.yaml") $Config

        $Email = Read-Host "发件邮箱（例如 your@qq.com；直接回车可跳过，稍后手动编辑）"
    if ($Email) {
        $Auth = Read-Host "SMTP 授权码（不是登录密码）"
        $To = Read-Host "收件邮箱（回车默认与发件邮箱相同）"
        if (-not $To) { $To = $Email }
        $Raw = Get-Content -Raw -Encoding UTF8 $Config
        $Raw = $Raw -replace '(?m)^(\s*username:\s*)"[^"]*"', ('$1"' + $Email + '"')
        $Raw = $Raw -replace '(?m)^(\s*from_addr:\s*)"[^"]*"', ('$1"' + $Email + '"')
        $Raw = $Raw -replace '(?m)^(\s*to_addr:\s*)"[^"]*"', ('$1"' + $To + '"')
        $Raw = $Raw -replace '(?m)^(\s*password:\s*)"[^"]*"', ('$1"' + $Auth + '"')
        [System.IO.File]::WriteAllText($Config, $Raw, (New-Object System.Text.UTF8Encoding $false))
        Write-Host "[4/5] 已写入邮箱配置（授权码仅保存在本地 config.yaml）"
    } else {
        Write-Host "[4/5] 已复制 config.example.yaml → config.yaml，请手动编辑邮箱与自选股"
    }
} else {
    Write-Host "[4/5] 检测到 config.yaml，跳过配置生成"
}

if ($InstallTask) {
    Write-Host "[5/5] 注册定时任务（收盘 18:00 / 盘前 09:00）..."
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "install_task.ps1")
    if ($LASTEXITCODE -ne 0) { throw "定时任务注册失败" }
} else {
    Write-Host "[5/5] 跳过定时任务（需要时：powershell -ExecutionPolicy Bypass -File .\quickstart.ps1 -InstallTask）"
}

if ($TestRun) {
    Write-Host "试跑：生成一份收盘报告 PDF（不发送邮件）..."
    & $VenvPy (Join-Path $ProjectRoot "main.py") --mode evening --no-email --force
    if ($LASTEXITCODE -ne 0) { throw "试跑失败，请查看上方日志" }
    Write-Host "试跑完成，PDF 在 output\ 目录。"
}

Write-Host ""
Write-Host "完成！下一步："
if (-not $InstallTask) { Write-Host "  1) 注册定时任务：powershell -ExecutionPolicy Bypass -File .\quickstart.ps1 -InstallTask" }
Write-Host "  2) 手动运行：python main.py（收盘）/ python main.py --mode morning（盘前）"
Write-Host "  3) 记得检查 config.yaml 里的关注板块和自选股"
