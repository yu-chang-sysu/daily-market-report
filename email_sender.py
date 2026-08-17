# -*- coding: utf-8 -*-
"""邮箱推送模块：把 PDF 作为附件发送到手机邮箱。"""
import logging
import smtplib
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

log = logging.getLogger("email")


def _placeholder(text):
    return (not text or "你的" in text or "@example.com" in text
            or text == "SMTP授权码")


def build_body(commentary, date_str):
    lines = [f"今日市场观察（{date_str}）", ""]
    lines.append("【市场】" + commentary.get("market", ""))
    lines.append("")
    lines.append("【板块】")
    lines.extend("· " + t for t in commentary.get("sectors", [])[:6])
    lines.append("")
    lines.append("【个股点评】")
    lines.extend("· " + t for t in commentary.get("stocks", [])[:8])
    if commentary.get("news_highlights"):
        lines.append("")
        lines.append("【要闻提示】")
        lines.extend("· " + t for t in commentary["news_highlights"][:3])
    lines.append("")
    lines.append("详细内容请查看附件 PDF。本邮件由自动化程序生成，不构成投资建议。")
    return "\n".join(lines)


def build_morning_body(commentary, date_str):
    lines = [f"今日股市推荐执行报告（{date_str} 盘前参考）", ""]
    lines.append("【今日核心建议】" + commentary.get("core_advice", ""))
    lines.append("")
    recs = commentary.get("recommendations", [])
    if recs:
        lines.append("【重点推荐关注】")
        for r in recs:
            lines.append(f"· {r['name']}（{r['code']}）：{r['reason']}")
        lines.append("")
    lines.append("【通俗分析】" + commentary.get("plain_analysis", ""))
    lines.append("")
    lines.append("【昨日回顾】" + commentary.get("summary", ""))
    lines.append("")
    lines.append("【板块聚焦】")
    lines.extend("· " + t for t in commentary.get("sectors", [])[:6])
    lines.append("")
    lines.append("【个股执行清单】")
    lines.extend("· " + t for t in commentary.get("stocks", [])[:8])
    if commentary.get("watch_points"):
        lines.append("")
        lines.append("【今日盘前要点】")
        lines.extend("· " + t for t in commentary["watch_points"][:4])
    lines.append("")
    lines.append("详细内容请查看附件 PDF（含支撑位、压力位和术语解释）。")
    lines.append("本报告由自动化程序生成，仅供个人参考，不构成投资建议。")
    return "\n".join(lines)


def send_email(cfg, pdf_path, commentary, date_str, subject_prefix=None,
               body_builder=build_body):
    mail = cfg.get("email", {})
    if not mail.get("enabled", True):
        log.info("邮箱推送未启用，跳过。")
        return False
    if _placeholder(mail.get("username", "")) or _placeholder(mail.get("password", "")):
        log.warning("邮箱未配置（缺少发件邮箱或授权码），跳过发送。"
                    "请在 config.yaml 中填写 email 部分。")
        return False
    if not Path(pdf_path).exists():
        log.error("PDF 不存在：%s", pdf_path)
        return False

    msg = MIMEMultipart()
    msg["From"] = formataddr((str(Header("每日市场观察", "utf-8")),
                              mail["from_addr"]))
    msg["To"] = mail["to_addr"]
    prefix = subject_prefix or mail.get("subject_prefix", "[每日市场观察]")
    subject = f"{prefix} {date_str}"
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(body_builder(commentary, date_str), "plain", "utf-8"))

    with open(pdf_path, "rb") as f:
        part = MIMEApplication(f.read(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment",
                    filename=("utf-8", "", Path(pdf_path).name))
    msg.attach(part)

    host = mail.get("smtp_host", "smtp.qq.com")
    port = int(mail.get("smtp_port", 465))
    use_ssl = mail.get("use_ssl", True)
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()
        server.login(mail["username"], mail["password"])
        server.sendmail(mail["from_addr"], [mail["to_addr"]], msg.as_string())
        server.quit()
        log.info("邮件已发送至 %s", mail["to_addr"])
        return True
    except Exception as e:  # noqa: BLE001
        log.error("邮件发送失败: %s", e)
        return False
