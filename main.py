# -*- coding: utf-8 -*-
"""每日市场观察 - 主程序：抓数据 → 点评 → PDF → 邮箱推送。"""
import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DEPS = PROJECT_ROOT / "deps"
DEPS2 = PROJECT_ROOT / "deps2"
if DEPS2.exists():
    sys.path.insert(0, str(DEPS2))
elif DEPS.exists():
    sys.path.insert(0, str(DEPS))

os.environ.setdefault("TQDM_DISABLE", "1")

import yaml  # noqa: E402

from analysis import build_commentary, build_morning_commentary  # noqa: E402
from data_fetch import fetch_all  # noqa: E402
from email_sender import send_email, build_morning_body  # noqa: E402
from pdf_report import build_pdf, build_morning_pdf  # noqa: E402

log = logging.getLogger("main")
STATE_DIR = PROJECT_ROOT / "output" / "state"


def _state_file(mode):
    return STATE_DIR / f"{mode}.txt"


def _already_done(mode, date_str):
    f = _state_file(mode)
    if not f.exists():
        return False
    try:
        return f.read_text(encoding="utf-8").strip() == date_str
    except Exception:  # noqa: BLE001
        return False


def _mark_done(mode, date_str):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_file(mode).write_text(date_str, encoding="utf-8")


def setup_logging(run_dir):
    run_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(run_dir / f"run_{datetime.now():%Y%m%d}.log",
                                encoding="utf-8"),
        ],
    )


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="每日市场观察生成器")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"),
                        help="配置文件路径")
    parser.add_argument("--no-email", action="store_true",
                        help="只生成 PDF，不发送邮件")
    parser.add_argument("--out", default=None, help="PDF 输出路径")
    parser.add_argument("--mode", choices=["evening", "morning"], default="evening",
                        help="evening=收盘报告；morning=盘前推荐执行报告")
    parser.add_argument("--force", action="store_true",
                        help="忽略'今日已生成'记录，强制重新生成")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        log.error("找不到配置文件 %s。请先执行："
                  "copy config.example.yaml config.yaml（Windows）或 "
                  "cp config.example.yaml config.yaml（Linux），然后填写配置。", cfg_path)
        return
    cfg = load_config(cfg_path)
    if not cfg.get("watchlist", {}).get("stocks") and not cfg.get("watchlist", {}).get("sectors"):
        log.error("config.yaml 里的 watchlist 为空。请参考 README，"
                  "在 config.yaml 中填写关注的板块和股票。")
        return
    out_dir = PROJECT_ROOT / cfg["report"].get("output_dir", "output")
    logs_dir = PROJECT_ROOT / "output" / "logs"
    setup_logging(logs_dir)
    log.info("==== 每日市场观察 开始 ====")

    today = datetime.now().strftime("%Y-%m-%d")
    if not args.force and _already_done(args.mode, today):
        log.info("今日 %s 报告已生成过，跳过（如需重跑请加 --force）", args.mode)
        return

    t0 = datetime.now()
    data = fetch_all(cfg)
    data["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if data.get("errors"):
        log.warning("部分数据异常: %s", "; ".join(data["errors"]))

    is_morning = args.mode == "morning"
    if is_morning:
        commentary = build_morning_commentary(data)
    else:
        commentary = build_commentary(data)
    for line in commentary["stocks"]:
        log.info("点评: %s", line)

    out_dir.mkdir(parents=True, exist_ok=True)
    if is_morning:
        pdf_name = f"今日股市推荐执行报告_{data['date']}.pdf"
        build_morning_pdf(data, commentary, cfg, str(args.out or (out_dir / pdf_name)))
    else:
        pdf_name = f"每日市场观察_{data['date']}.pdf"
        build_pdf(data, commentary, cfg, str(args.out or (out_dir / pdf_name)))
    pdf_path = Path(args.out) if args.out else out_dir / pdf_name
    log.info("PDF 已生成: %s", pdf_path)

    sent = False
    if not args.no_email:
        if is_morning:
            sent = send_email(
                cfg, pdf_path, commentary, data["date"],
                subject_prefix=cfg["email"].get("morning_subject_prefix"),
                body_builder=build_morning_body)
        else:
            sent = send_email(cfg, pdf_path, commentary, data["date"])

    elapsed = (datetime.now() - t0).total_seconds()
    log.info("完成，耗时 %.1f 秒，邮件发送=%s", elapsed, sent)
    if sent or args.no_email:
        _mark_done(args.mode, data["date"])
        log.info("已记录 %s 报告生成日期：%s", args.mode, data["date"])
    else:
        log.warning("邮件未发送成功，未标记完成状态，下次运行会重试")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    main()
