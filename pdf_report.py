# -*- coding: utf-8 -*-
"""PDF 生成模块（reportlab + 中文字体）。"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                Paragraph, PageTemplate, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import Flowable

def _font_dir():
    env = os.environ.get("DMR_FONT_DIR")
    if env:
        return env
    return r"C:\Windows\Fonts" if os.name == "nt" else "/usr/share/fonts"


FONT_DIR = _font_dir()
RED = colors.HexColor("#D03028")     # 涨（中国市场惯例：红涨绿跌）
GREEN = colors.HexColor("#1A7F37")   # 跌
GRAY = colors.HexColor("#5F6B7A")
NAVY = colors.HexColor("#1F3864")
LIGHT = colors.HexColor("#EEF3FA")
LINE = colors.HexColor("#C9D4E4")
TEXT = colors.HexColor("#222222")


def _hex(c):
    return "#" + c.hexval()[2:] if hasattr(c, "hexval") else "#D03028"


class Sparkline(Flowable):
    """迷你走势图（近5日收盘价）。"""

    def __init__(self, values, width=100, height=22, color=RED):
        super().__init__()
        self.values = [v for v in values if v is not None]
        self.width = width
        self.height = height
        self.color = color

    def draw(self):
        if len(self.values) < 2:
            return
        vmin, vmax = min(self.values), max(self.values)
        span = (vmax - vmin) or 1.0
        n = len(self.values)
        pts = []
        for i, v in enumerate(self.values):
            x = 2 + i * (self.width - 4) / (n - 1)
            y = 2 + (v - vmin) / span * (self.height - 4)
            pts.append((x, y))
        c = self.canv
        c.setStrokeColor(self.color)
        c.setLineWidth(1.2)
        p = c.beginPath()
        p.moveTo(*pts[0])
        for pt in pts[1:]:
            p.lineTo(*pt)
        c.drawPath(p)
        c.setFillColor(self.color)
        c.circle(pts[-1][0], pts[-1][1], 1.6, stroke=0, fill=1)


def _register_fonts():
    fonts = {}
    candidates = [
        ("SimHei", os.path.join(FONT_DIR, "simhei.ttf")),
        ("MSYaHei", os.path.join(FONT_DIR, "msyh.ttc")),
        ("SimSun", os.path.join(FONT_DIR, "simsun.ttc")),
    ]
    for name, path in candidates:
        if not os.path.exists(path):
            continue
        try:
            if path.lower().endswith(".ttc"):
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
            else:
                pdfmetrics.registerFont(TTFont(name, path))
            fonts[name] = path
        except Exception:  # noqa: BLE001
            continue
    return fonts


def _fmt(v, nd=2):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def _pct(v):
    return "—" if v is None else f"{float(v):+.2f}%"


def _col(v):
    """涨跌颜色。"""
    if v is None:
        return GRAY
    return RED if v >= 0 else GREEN


def _amt(v):
    if v is None:
        return "—"
    av = abs(v)
    sign = "-" if v < 0 else ""
    if av >= 1e8:
        return f"{sign}{av / 1e8:.2f}亿"
    if av >= 1e4:
        return f"{sign}{av / 1e4:.0f}万"
    return f"{sign}{av:.0f}"


def build_pdf(data, commentary, cfg, out_path):
    fonts = _register_fonts()
    if not fonts:
        raise RuntimeError("未找到可用的中文字体（C:\\Windows\\Fonts\\simhei.ttf）")
    hei = "SimHei" if "SimHei" in fonts else next(iter(fonts))

    S_TITLE = ParagraphStyle("title", fontName=hei, fontSize=22, leading=28,
                             alignment=TA_CENTER, textColor=NAVY, spaceAfter=2)
    S_SUB = ParagraphStyle("sub", fontName=hei, fontSize=10.5, leading=15,
                           alignment=TA_CENTER, textColor=GRAY, spaceAfter=4)
    S_TONE = ParagraphStyle("tone", fontName=hei, fontSize=11, leading=16,
                            alignment=TA_CENTER, spaceBefore=2, spaceAfter=4)
    S_H1 = ParagraphStyle("h1", fontName=hei, fontSize=14, leading=20,
                          textColor=NAVY, spaceBefore=14, spaceAfter=6,
                          keepWithNext=1)
    S_BODY = ParagraphStyle("body", fontName=hei, fontSize=9.8, leading=15.5,
                            textColor=TEXT, wordWrap="CJK")
    S_JUST = ParagraphStyle("just", parent=S_BODY, alignment=TA_JUSTIFY)
    S_CELL = ParagraphStyle("cell", fontName=hei, fontSize=9.2, leading=13,
                            wordWrap="CJK", textColor=TEXT)
    S_CELL_C = ParagraphStyle("cellc", parent=S_CELL, alignment=TA_CENTER)
    S_CELL_R = ParagraphStyle("cellr", parent=S_CELL, alignment=2)
    S_HEAD = ParagraphStyle("head", fontName=hei, fontSize=9.2, leading=13,
                            textColor=colors.white, alignment=TA_CENTER)
    S_NEWS = ParagraphStyle("news", fontName=hei, fontSize=9.3, leading=14.5,
                            textColor=TEXT, wordWrap="CJK",
                            leftIndent=12, spaceAfter=2)
    S_NOTE = ParagraphStyle("note", fontName=hei, fontSize=8.2, leading=12,
                            textColor=GRAY, wordWrap="CJK")
    S_DISC = ParagraphStyle("disc", fontName=hei, fontSize=8.8, leading=14,
                            textColor=GRAY, wordWrap="CJK", alignment=TA_JUSTIFY)

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(hei, 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(20 * mm, A4[1] - 12 * mm,
                          cfg["report"].get("title", "每日市场观察"))
        canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, data["date"])
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, A4[1] - 14 * mm, A4[0] - 20 * mm, A4[1] - 14 * mm)
        canvas.line(20 * mm, 13 * mm, A4[0] - 20 * mm, 13 * mm)
        canvas.drawCentredString(
            A4[0] / 2, 9 * mm,
            f"第 {canvas.getPageNumber()} 页  |  仅供个人参考，不构成投资建议")
        canvas.restoreState()

    doc = BaseDocTemplate(out_path, pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=20 * mm, bottomMargin=18 * mm,
                          title=cfg["report"].get("title", "每日市场观察"),
                          author="Daily Market Report")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=header_footer)])

    story = []

    # ===== 封面区 =====
    story.append(Paragraph(cfg["report"].get("title", "每日市场观察"), S_TITLE))
    story.append(Paragraph(
        f"交易日：{data['date']}  ·  生成时间：{data.get('generated_at', '')}", S_SUB))
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"今日市场：{commentary['tone']}", S_TONE))
    story.append(Spacer(1, 2))

    # ===== 一、市场概览 =====
    story.append(Paragraph("一、市场概览", S_H1))
    idx = data.get("indices", [])
    if idx:
        tdata = [[Paragraph("指数", S_HEAD), Paragraph("最新点位", S_HEAD),
                  Paragraph("涨跌", S_HEAD), Paragraph("涨跌幅", S_HEAD),
                  Paragraph("成交额", S_HEAD)]]
        for i in idx:
            tdata.append([
                Paragraph(i["name"], S_CELL),
                Paragraph(_fmt(i["close"]), S_CELL_C),
                Paragraph(_fmt(i["change"]), S_CELL_R),
                Paragraph(f'<font color="{_hex(_col(i["change_pct"]))}">'
                          f'{_pct(i["change_pct"])}</font>', S_CELL_C),
                Paragraph(_amt(i["amount"]), S_CELL_R),
            ])
        tbl = Table(tdata, colWidths=[doc.width * 0.26] + [doc.width * 0.17] * 4,
                    repeatRows=1, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("指数数据获取失败。", S_BODY))
    story.append(Spacer(1, 6))
    story.append(Paragraph(commentary["market"], S_JUST))

    # ===== 二、板块表现 =====
    story.append(Paragraph("二、板块表现", S_H1))
    if commentary["sector_rows"]:
        tdata = [[Paragraph("板块", S_HEAD), Paragraph("涨跌幅", S_HEAD),
                  Paragraph("主力净额(亿)", S_HEAD), Paragraph("近5日", S_HEAD),
                  Paragraph("领涨股", S_HEAD),
                  Paragraph("领涨股涨幅", S_HEAD)]]
        for r in commentary["sector_rows"]:
            tdata.append([
                Paragraph(r["name"], S_CELL),
                Paragraph(f'<font color="{_hex(_col(r["change_pct"]))}">'
                          f'{r["change_pct"]:+.2f}%</font>', S_CELL_C),
                Paragraph(f"{r.get('net_inflow', 0.0):+.1f}亿", S_CELL_R),
                Paragraph(r["trend"] or "—", S_CELL_C),
                Paragraph(r["leader"] or "—", S_CELL),
                Paragraph(_pct(r["leader_chg"]), S_CELL_C),
            ])
        tbl = Table(tdata, colWidths=[doc.width * 0.16, doc.width * 0.13,
                                      doc.width * 0.15, doc.width * 0.13,
                                      doc.width * 0.29, doc.width * 0.14],
                    repeatRows=1, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 3))
        story.append(Paragraph("注：主力净额单位为亿元（正=净流入，负=净流出）。", S_NOTE))
        story.append(Spacer(1, 6))
    for t in commentary["sectors"]:
        story.append(Paragraph("· " + t, S_BODY))

    # ===== 三、自选股速览 =====
    story.append(Paragraph("三、自选股速览", S_H1))
    rows = commentary["stock_rows"]
    if rows:
        colw = [doc.width * 0.11, doc.width * 0.14, doc.width * 0.13,
                doc.width * 0.14, doc.width * 0.12, doc.width * 0.15,
                doc.width * 0.21]
        tdata = [[Paragraph("代码", S_HEAD), Paragraph("名称", S_HEAD),
                  Paragraph("收盘价", S_HEAD), Paragraph("涨跌幅", S_HEAD),
                  Paragraph("近5日", S_HEAD), Paragraph("主力净额", S_HEAD),
                  Paragraph("近5日走势", S_HEAD)]]
        for r in rows:
            hist = next((s for s in data["stocks"] if s["code"] == r["code"]),
                        {}).get("hist", [])
            closes = [h["close"] for h in hist[-6:]]
            spark = Sparkline(closes, width=colw[6] - 4, height=20,
                              color=RED if r["change_pct"] is None or r["change_pct"] >= 0 else GREEN)
            tdata.append([
                Paragraph(r["code"], S_CELL_C),
                Paragraph(r["name"], S_CELL),
                Paragraph(_fmt(r["close"]), S_CELL_C),
                Paragraph(f'<font color="{_hex(_col(r["change_pct"]))}">'
                          f'{_pct(r["change_pct"])}</font>', S_CELL_C),
                Paragraph(_pct(r["chg5"]), S_CELL_C),
                Paragraph(_amt(r["net"]), S_CELL_R),
                spark,
            ])
        tbl = Table(tdata, colWidths=colw, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 3))
        story.append(Paragraph("注：主力净额自动适配单位（万/亿）；近5日走势为收盘价迷你图。", S_NOTE))

    # ===== 四、个股点评与新闻 =====
    story.append(Paragraph("四、个股点评与新闻", S_H1))
    for st, txt in zip(data.get("stocks", []), commentary["stocks"]):
        block = [Paragraph(txt, S_JUST), Spacer(1, 4)]
        if st.get("news"):
            block.append(Paragraph(f"近期要闻（{len(st['news'])}条）：", S_BODY))
            for n in st["news"]:
                src = f" · {n['source']}" if n.get("source") else ""
                block.append(Paragraph(f"● {n['time']} {n['title']}{src}", S_NEWS))
        else:
            block.append(Paragraph("近期暂无相关新闻。", S_NOTE))
        story.append(KeepTogether(block))
        story.append(Spacer(1, 8))

    # ===== 五、市场要闻 =====
    story.append(Paragraph("五、市场要闻（财联社电报）", S_H1))
    if data.get("market_news"):
        for n in data["market_news"]:
            story.append(Paragraph(f"● [{n['time']}] {n['title']}", S_NEWS))
    else:
        story.append(Paragraph("市场要闻获取失败。", S_BODY))

    # ===== 风险提示 =====
    story.append(PageBreak())
    story.append(Paragraph("风险提示与说明", S_H1))
    story.append(Paragraph(
        "1. 本报告由自动化程序基于公开数据整理生成，数据来源包括新浪财经、同花顺、"
        "东方财富、财联社等公开接口，可能存在延迟、缺失或错误，请以交易所及官方公告为准。",
        S_DISC))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "2. 报告中的点评为基于行情、资金流与新闻关键词的规则化客观描述，"
        "不构成任何投资建议或收益承诺。", S_DISC))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "3. 股市有风险，入市需谨慎。投资者应结合自身风险承受能力独立判断，"
        "据此操作风险自担。", S_DISC))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "4. 本报告仅供个人参考，请勿用于商业用途或对外传播。", S_DISC))
    story.append(Spacer(1, 10))
    if data.get("errors"):
        story.append(Paragraph("本次生成中的数据异常记录：", S_H1))
        for e in data["errors"]:
            story.append(Paragraph("· " + str(e), S_NOTE))
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f"生成工具：自动化行情聚合系统 · {data.get('generated_at', '')}", S_NOTE))

    doc.build(story)
    return out_path


def _trend_text(hist):
    closes = [h["close"] for h in hist]
    last5 = closes[-5:] if len(closes) >= 5 else closes
    if len(last5) < 2:
        return ""
    up = sum(1 for i in range(len(last5) - 1) if last5[i + 1] > last5[i])
    if up == len(last5) - 1:
        return "连续走高"
    if up == 0:
        return "连续走低"
    return "震荡上行" if up * 2 >= len(last5) - 1 else "震荡整理"


def build_morning_pdf(data, commentary, cfg, out_path):
    fonts = _register_fonts()
    if not fonts:
        raise RuntimeError("未找到可用的中文字体（C:\\Windows\\Fonts\\simhei.ttf）")
    hei = "SimHei" if "SimHei" in fonts else next(iter(fonts))

    S_TITLE = ParagraphStyle("mtitle", fontName=hei, fontSize=22, leading=28,
                             alignment=TA_CENTER, textColor=NAVY, spaceAfter=2)
    S_SUB = ParagraphStyle("msub", fontName=hei, fontSize=10.5, leading=15,
                           alignment=TA_CENTER, textColor=GRAY, spaceAfter=4)
    S_TONE = ParagraphStyle("mtone", fontName=hei, fontSize=11, leading=16,
                            alignment=TA_CENTER, spaceBefore=2, spaceAfter=4)
    S_H1 = ParagraphStyle("mh1", fontName=hei, fontSize=14, leading=20,
                          textColor=NAVY, spaceBefore=14, spaceAfter=6,
                          keepWithNext=1)
    S_BODY = ParagraphStyle("mbody", fontName=hei, fontSize=9.8, leading=15.5,
                            textColor=TEXT, wordWrap="CJK")
    S_JUST = ParagraphStyle("mjust", parent=S_BODY, alignment=TA_JUSTIFY)
    S_CELL = ParagraphStyle("mcell", fontName=hei, fontSize=9.2, leading=13,
                            wordWrap="CJK", textColor=TEXT)
    S_CELL_C = ParagraphStyle("mcellc", parent=S_CELL, alignment=TA_CENTER)
    S_CELL_R = ParagraphStyle("mcellr", parent=S_CELL, alignment=2)
    S_HEAD = ParagraphStyle("mhead", fontName=hei, fontSize=9.2, leading=13,
                            textColor=colors.white, alignment=TA_CENTER)
    S_NEWS = ParagraphStyle("mnews", fontName=hei, fontSize=9.3, leading=14.5,
                            textColor=TEXT, wordWrap="CJK",
                            leftIndent=12, spaceAfter=2)
    S_NOTE = ParagraphStyle("mnote", fontName=hei, fontSize=8.2, leading=12,
                            textColor=GRAY, wordWrap="CJK")
    S_DISC = ParagraphStyle("mdisc", fontName=hei, fontSize=8.8, leading=14,
                            textColor=GRAY, wordWrap="CJK", alignment=TA_JUSTIFY)

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(hei, 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(20 * mm, A4[1] - 12 * mm,
                          cfg["report"].get("morning_title", "今日股市推荐执行报告"))
        canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, data["date"])
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, A4[1] - 14 * mm, A4[0] - 20 * mm, A4[1] - 14 * mm)
        canvas.line(20 * mm, 13 * mm, A4[0] - 20 * mm, 13 * mm)
        canvas.drawCentredString(
            A4[0] / 2, 9 * mm,
            f"第 {canvas.getPageNumber()} 页  |  仅供个人参考，不构成投资建议")
        canvas.restoreState()

    doc = BaseDocTemplate(out_path, pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=20 * mm, bottomMargin=18 * mm,
                          title=cfg["report"].get("morning_title", "今日股市推荐执行报告"),
                          author="Daily Market Report")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=header_footer)])

    story = []

    # ===== 封面区 =====
    story.append(Paragraph(cfg["report"].get("morning_title", "今日股市推荐执行报告"), S_TITLE))
    story.append(Paragraph(
        f"盘前参考：{data['date']}  ·  生成时间：{data.get('generated_at', '')}", S_SUB))
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"昨日市场：{commentary['tone']}  ·  今日关注科技主线", S_TONE))
    story.append(Spacer(1, 2))

    # ===== 一、今日速览（先说结论） =====
    story.append(Paragraph("一、今日速览（先说结论）", S_H1))
    advice_box = Table(
        [[Paragraph("今日核心建议：" + commentary.get("core_advice", ""), S_BODY)]],
        colWidths=[doc.width])
    advice_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF6E5")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#D9A441")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(advice_box)
    story.append(Spacer(1, 6))

    recs = commentary.get("recommendations", [])
    if recs:
        story.append(Paragraph("重点推荐关注（按综合强度排序）：", S_BODY))
        tdata = [[Paragraph("股票", S_HEAD), Paragraph("代码", S_HEAD),
                  Paragraph("为什么值得关注（通俗版）", S_HEAD)]]
        for r in recs:
            tdata.append([
                Paragraph(r["name"], S_CELL),
                Paragraph(r["code"], S_CELL_C),
                Paragraph(r["reason"], S_CELL),
            ])
        tbl = Table(tdata, colWidths=[doc.width * 0.16, doc.width * 0.14,
                                      doc.width * 0.70],
                    repeatRows=1, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 4))
        story.append(Paragraph("注：推荐依据为站上均线、资金流入、量能、消息面等客观指标，"
                               "仅供跟踪参考，不代表买入建议。", S_NOTE))
    story.append(Spacer(1, 3))
    story.append(Paragraph("通俗分析：" + commentary.get("plain_analysis", ""), S_JUST))

    # ===== 二、昨日行情回顾 =====
    story.append(Paragraph("二、昨日行情回顾", S_H1))
    idx = data.get("indices", [])
    if idx:
        tdata = [[Paragraph("指数", S_HEAD), Paragraph("最新点位", S_HEAD),
                  Paragraph("涨跌幅", S_HEAD), Paragraph("成交额", S_HEAD)]]
        for i in idx:
            tdata.append([
                Paragraph(i["name"], S_CELL),
                Paragraph(_fmt(i["close"]), S_CELL_C),
                Paragraph(f'<font color="{_hex(_col(i["change_pct"]))}">'
                          f'{_pct(i["change_pct"])}</font>', S_CELL_C),
                Paragraph(_amt(i["amount"]), S_CELL_R),
            ])
        tbl = Table(tdata, colWidths=[doc.width * 0.26] + [doc.width * 0.2] * 3,
                    repeatRows=1, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
    story.append(Spacer(1, 6))
    story.append(Paragraph(commentary["summary"], S_JUST))

    # ===== 三、今日板块聚焦 =====
    story.append(Paragraph("三、今日板块聚焦", S_H1))
    sec_rows = []
    for sec in data.get("sectors", []):
        s = sec.get("summary")
        if not s:
            continue
        hist = sec.get("hist", [])
        closes = [h["close"] for h in hist]
        chg5 = None
        if len(closes) >= 6 and closes[-6]:
            chg5 = (closes[-1] / closes[-6] - 1) * 100
        sec_rows.append((sec["name"], s["change_pct"], chg5,
                         s.get("leader", ""), _trend_text(hist)))
    if sec_rows:
        tdata = [[Paragraph("板块", S_HEAD), Paragraph("昨涨跌幅", S_HEAD),
                  Paragraph("近5日", S_HEAD), Paragraph("龙头股", S_HEAD)]]
        for name, chg, chg5, leader, trend in sec_rows:
            tdata.append([
                Paragraph(name, S_CELL),
                Paragraph(f'<font color="{_hex(_col(chg))}">{chg:+.2f}%</font>', S_CELL_C),
                Paragraph(f"{chg5:+.2f}%" if chg5 is not None else "—", S_CELL_C),
                Paragraph(leader or "—", S_CELL),
            ])
        tbl = Table(tdata, colWidths=[doc.width * 0.3, doc.width * 0.22,
                                      doc.width * 0.18, doc.width * 0.30],
                    repeatRows=1, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 6))
    for t in commentary["sectors"]:
        story.append(Paragraph("· " + t, S_BODY))

    # ===== 四、个股执行清单 =====
    story.append(Paragraph("四、个股执行清单（盘前参考）", S_H1))
    rows = commentary.get("stock_rows", [])
    if rows:
        tdata = [[Paragraph("代码", S_HEAD), Paragraph("名称", S_HEAD),
                  Paragraph("昨收", S_HEAD), Paragraph("昨涨跌幅", S_HEAD),
                  Paragraph("支撑位", S_HEAD), Paragraph("压力位", S_HEAD),
                  Paragraph("5日均线", S_HEAD), Paragraph("10日均线", S_HEAD)]]
        for r in rows:
            tdata.append([
                Paragraph(r["code"], S_CELL_C),
                Paragraph(r["name"], S_CELL),
                Paragraph(_fmt(r["close"]), S_CELL_C),
                Paragraph(f'<font color="{_hex(_col(r["change_pct"]))}">'
                          f'{_pct(r["change_pct"])}</font>', S_CELL_C),
                Paragraph(_fmt(r["support"]), S_CELL_C),
                Paragraph(_fmt(r["resistance"]), S_CELL_C),
                Paragraph(_fmt(r["ma5"]), S_CELL_C),
                Paragraph(_fmt(r["ma10"]), S_CELL_C),
            ])
        tbl = Table(tdata, colWidths=[doc.width * 0.11, doc.width * 0.13,
                                      doc.width * 0.10, doc.width * 0.13,
                                      doc.width * 0.12, doc.width * 0.12,
                                      doc.width * 0.13, doc.width * 0.13],
                    repeatRows=1, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "注：支撑/压力位为近10日高低点估算，均线取收盘价均值，仅供参考。", S_NOTE))
    for t in commentary["stocks"]:
        story.append(KeepTogether([Paragraph(t, S_JUST), Spacer(1, 6)]))

    # ===== 五、今日盘前要点 =====
    story.append(Paragraph("五、今日盘前要点", S_H1))
    for w in commentary.get("watch_points", []):
        story.append(Paragraph("● " + w, S_NEWS))

    # ===== 六、术语小词典 =====
    story.append(PageBreak())
    story.append(Paragraph("六、术语小词典（通俗版）", S_H1))
    for term, explain in commentary.get("glossary", []):
        story.append(Paragraph(f"● <b>{term}</b>：{explain}", S_BODY))

    # ===== 风险提示 =====
    story.append(Paragraph("风险提示", S_H1))
    story.append(Paragraph(
        "1. 本报告基于公开数据自动化生成，数据可能存在延迟或错误，请以交易所及官方公告为准。",
        S_DISC))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "2. 报告中的支撑/压力位与执行参考为技术分析规则的客观描述，不构成投资建议。",
        S_DISC))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "3. 股市有风险，入市需谨慎。请结合自身风险承受能力独立判断，据此操作风险自担。",
        S_DISC))
    story.append(Spacer(1, 10))
    if data.get("errors"):
        story.append(Paragraph("本次生成中的数据异常记录：", S_H1))
        for e in data["errors"]:
            story.append(Paragraph("· " + str(e), S_NOTE))
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f"生成工具：自动化行情聚合系统 · {data.get('generated_at', '')}", S_NOTE))

    doc.build(story)
    return out_path
