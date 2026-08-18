# 每日股市观察报告（Daily Market Report）

> *Catching Information Is All You Need —— 每天帮你抓住市场信息。*

每天自动抓取指定板块与个股的行情、新闻、资金流，生成两份带专业点评的 PDF 报告，
并通过邮件推送到你的手机：

1. **每日股市观察报告**（默认 18:00 收盘后）：大盘指数、板块表现、自选股行情速览、
   个股新闻与点评、财联社市场要闻。
2. **今日股市推荐执行报告**（默认次日 09:00 盘前）：顶部先说结论（核心建议、
   重点推荐关注、通俗分析），再给板块聚焦、个股支撑位/压力位、情景式执行清单
   和通俗版术语词典。

> 免责声明：本项目仅用于学习和个人研究。报告内容为基于公开数据的规则化客观描述，
> **不构成任何投资建议**。股市有风险，入市需谨慎。请勿用于商业用途或对外传播。

## 功能特性

- 行情：新浪（指数、个股日线）、同花顺（板块、资金流）、东方财富（个股新闻）、财联社（市场要闻）
- 专业点评：量价（放量/缩量）、趋势、主力资金流向、新闻利好/利空关键词综合分析
- 盘前执行清单：支撑位/压力位、均线位置、三档情景式操作参考（通俗版）
- PDF：中文字体排版、红涨绿跌配色、近 5 日迷你走势图
- 定时推送：Windows 任务计划程序一键注册；错过时间后开机自动补跑最近一天，不会重复发
- 数据新鲜度校验：生成前校验日 K 最后日期是否等于报告日期；18:30 前自动重试（每 60 秒 × 3）；
  仍不一致时报告/邮件会标注“数据截至 …”，也可用 `--strict` 拒绝生成与发送，
  避免“日期是今天、数据是昨天”

## 小白一步到位（Windows，推荐）

一条命令完成：检测 Python → 创建虚拟环境 → 安装依赖 → 生成配置并引导填写邮箱 →
（可选）注册定时任务 →（可选）试跑生成 PDF：

```powershell
powershell -ExecutionPolicy Bypass -File .\quickstart.ps1
```

常用参数：

```powershell
powershell -ExecutionPolicy Bypass -File .\quickstart.ps1 -InstallTask   # 顺手注册每日定时任务
powershell -ExecutionPolicy Bypass -File .\quickstart.ps1 -TestRun       # 试跑一次收盘报告（不发邮件）
```

脚本会提示你输入：发件邮箱、SMTP 授权码、收件邮箱。关注板块与自选股可以先保留
示例，之后手动编辑 `config.yaml`。

## 手动快速开始（Windows）

### 1. 安装 Python 和依赖

安装 Python 3.10+（安装时勾选 "Add python to PATH"），然后：

```powershell
pip install -r requirements.txt
```

### 2. 生成并填写配置文件

```powershell
copy config.example.yaml config.yaml
```

用文本编辑器打开 `config.yaml`，需要填 4 样东西：

| 配置项 | 说明 |
|---|---|
| `watchlist.sectors` | 关注的板块，同花顺行业/概念板块名，如 `"半导体"`、`"存储芯片"`、`"人工智能"` |
| `watchlist.stocks` | 关注的股票，格式 `- { code: "600519", name: "贵州茅台" }` |
| `email.username/password/from_addr/to_addr` | 发件邮箱、SMTP 授权码、收件邮箱 |
| `schedule.run_time / morning_time` | 两份报告的时间（默认 18:00 / 09:00） |

邮箱授权码说明（以 QQ 邮箱为例）：登录 QQ 邮箱网页版 → 设置 → 账号 → 开启 SMTP
服务 → 生成“授权码”，填入 `email.password`。163/126 邮箱把 `smtp_host` 改成
`smtp.163.com` 即可。

### 3. 手动测试一次

```powershell
python main.py                 # 收盘报告（会发邮件）
python main.py --mode morning  # 盘前执行报告（会发邮件）
python main.py --no-email      # 只生成 PDF 不发送
python main.py --strict        # 数据日期未刷新时拒绝生成/发送
```

### 4. 注册每日定时任务

```powershell
powershell -ExecutionPolicy Bypass -File .\install_task.ps1
```

会注册两个任务：`MarketDailyReport`（18:00）和 `MarketMorningReport`（09:00），
并启用“错过后尽快运行”——电脑错过时间后，下次开机/唤醒自动补跑最近一天。
删除任务：`schtasks /Delete /TN MarketDailyReport /F`（另一个同理）。

## 数据新鲜度校验说明

- 为什么需要：数据源（新浪/同花顺）的日 K 在 16:30 前后可能还没写入当天，容易导致
  “报告日期是今天、数据是昨天”。
- 程序怎么做：生成前校验最后一根日 K 的日期；18:30 前每 60 秒自动重试（最多 3 次）；
  仍不一致时，报告与邮件会标注“数据截至 …”，并记录到日志；`--strict` 可强制拒绝发送。
- 只有校验通过（或显式 `--force`）才会标记“今日已完成”，避免错误报告被跳过重跑。
- 手动重跑：`python main.py --mode evening --force`。

## 目录结构

```
daily-market-report/
├─ quickstart.ps1        # 小白一步到位脚本（推荐）
├─ config.example.yaml   # 配置模板（复制为 config.yaml 后填写）
├─ main.py               # 主程序入口（--mode evening / morning）
├─ data_fetch.py         # 数据采集
├─ analysis.py           # 专业点评与推荐打分
├─ pdf_report.py         # PDF 生成
├─ email_sender.py       # 邮箱推送
├─ run_daily.ps1         # 收盘报告启动脚本（Windows）
├─ run_morning.ps1       # 盘前报告启动脚本（Windows）
├─ install_task.ps1      # 注册 Windows 定时任务（一键）
├─ install_autopilot.ps1 # 备用：开机自启后台循环
├─ autopilot_loop.ps1    # 后台循环脚本
├─ requirements.txt      # Python 依赖
└─ output/               # 生成的 PDF、日志（自动创建，不入库）
```

## 路径说明（项目放在哪里都行）

- 本项目**不需要固定安装路径**，整个文件夹复制到任何位置都能运行；脚本全部使用
  相对路径定位自身。
- 启动脚本默认使用 PATH 里的 `python`。如果你的 Python 不在 PATH，设置环境变量
  `DMR_PYTHON` 指向完整路径即可：
  ```powershell
  $env:DMR_PYTHON = "C:\你的Python路径\python.exe"
  ```
- 中文字体：Windows 会自动使用 `C:\Windows\Fonts` 下的黑体/微软雅黑；
  其他系统请通过环境变量 `DMR_FONT_DIR` 指向包含中文字体（如思源黑体）的目录：
  ```bash
  export DMR_FONT_DIR=/usr/share/fonts/opentype/noto
  ```
- `config.yaml` 只保存在本地（已被 .gitignore 排除），不会上传到 GitHub。

## Linux / macOS

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
# 编辑 config.yaml ...
python main.py --no-email
```

定时任务用 cron（示例：每天 18:00 和 09:00）：

```cron
0 18 * * 1-5 cd /path/to/daily-market-report && /path/to/.venv/bin/python main.py >> output/logs/cron.log 2>&1
0  9  * * 1-5 cd /path/to/daily-market-report && /path/to/.venv/bin/python main.py --mode morning >> output/logs/cron.log 2>&1
```

（`1-5` 表示周一至周五，A 股交易日；如需节假日自动跳过，可再叠加交易日历判断。）

## 数据源与免责声明

- 数据来自新浪财经、同花顺、东方财富、财联社等公开接口，均为非官方接口，
  可能随对方调整而失效或改变字段，请勿用于商业用途。
- 报告中的“重点推荐关注”由客观规则打分产生（站上均线、资金净流入、量能、
  消息面等），仅供跟踪参考，不构成投资建议。
- 本项目按 MIT 协议开源，使用本项目造成的任何投资损失与作者无关。

## Roadmap

- [ ] 节假日自动跳过（交易日历）
- [ ] 支持更多券商/邮箱（Outlook、Gmail）
- [ ] AI 大模型点评接口（可选，需 API key）
- [ ] 板块自定义别名映射
