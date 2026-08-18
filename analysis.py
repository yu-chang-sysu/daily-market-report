# -*- coding: utf-8 -*-
"""专业点评模块：基于量价、趋势、资金流、新闻要点的规则化综合分析。"""


def _fmt_amount(v):
    """金额格式化：亿/万。"""
    if v is None:
        return "—"
    av = abs(v)
    sign = "" if v >= 0 else "-"
    if av >= 1e8:
        return f"{sign}{av / 1e8:.2f}亿"
    if av >= 1e4:
        return f"{sign}{av / 1e4:.0f}万"
    return f"{v:.0f}元"


def _trend_label(hist):
    """近5日走势判断。"""
    if not hist or len(hist) < 3:
        return ""
    closes = [h["close"] for h in hist]
    last5 = closes[-5:] if len(closes) >= 5 else closes
    if all(last5[i + 1] > last5[i] for i in range(len(last5) - 1)):
        return "连续走高"
    if all(last5[i + 1] < last5[i] for i in range(len(last5) - 1)):
        return "连续走低"
    up = sum(1 for i in range(len(last5) - 1) if last5[i + 1] > last5[i])
    return "震荡上行" if up >= len(last5) - 1 - up else "震荡整理"


def _volume_note(hist):
    if not hist or len(hist) < 6:
        return ""
    vol = hist[-1]["volume"]
    avg5 = sum(h["volume"] for h in hist[-6:-1]) / 5.0
    if avg5 <= 0:
        return ""
    ratio = vol / avg5
    if ratio >= 1.8:
        return "显著放量"
    if ratio >= 1.3:
        return "温和放量"
    if ratio <= 0.6:
        return "明显缩量"
    if ratio <= 0.85:
        return "有所缩量"
    return "量能平稳"


def market_tone(indices):
    sh = next((i for i in indices if i["name"] == "上证指数"), None)
    if not sh:
        return "数据不足，暂不评级"
    p = sh["change_pct"]
    if p >= 1.5:
        return "强势上涨"
    if p >= 0.5:
        return "震荡上行"
    if p > -0.5:
        return "窄幅整理"
    if p > -1.5:
        return "震荡偏弱"
    return "明显回调"


def _news_flags(stock):
    """新闻要点标记：利好/利空/异动关键词。"""
    bull = ["回购", "增持", "中标", "预增", "超预期", "创新高", "涨停",
            "签约", "获批", "放量"]
    bear = ["减持", "质押", "处罚", "立案", "亏损", "下调", "跌停",
            "商誉减值", "监管函", "问询"]
    hits = {"bull": [], "bear": []}
    for n in stock.get("news", []):
        text = n["title"]
        for k in bull:
            if k in text:
                hits["bull"].append(text[:60])
                break
        for k in bear:
            if k in text:
                hits["bear"].append(text[:60])
                break
    return hits


def build_commentary(data):
    """生成报告各章节的专业总结文字。"""
    indices = data.get("indices", [])
    tone = market_tone(indices)

    # ---- 市场点评 ----
    parts = [f"今日大盘整体呈现“{tone}”格局。"]
    if indices:
        desc = "、".join(f"{i['name']}{i['change_pct']:+.2f}%" for i in indices)
        parts.append(f"主要指数：{desc}。")
    up = [i for i in indices if i.get("change_pct", 0) >= 0]
    down = [i for i in indices if i.get("change_pct", 0) < 0]
    if up and not down:
        parts.append("主要指数全线收涨，市场风险偏好回升，做多情绪占优。")
    elif down and not up:
        parts.append("主要指数集体收跌，短线情绪偏谨慎，需关注支撑位与量能变化。")
    else:
        parts.append("指数涨跌互现，结构性行情特征明显，注意板块间的分化与轮动。")
    market_text = "".join(parts)

    # ---- 板块点评 ----
    sector_texts = []
    sector_rows = []
    for sec in data.get("sectors", []):
        s = sec.get("summary")
        hist = sec.get("hist", [])
        if not s:
            sector_texts.append(
                f"【{sec['name']}】今日数据未获取，请检查板块名称是否与同花顺一致。")
            continue
        chg = s["change_pct"]
        if chg >= 1.0:
            label = "领涨"
        elif chg >= 0.3:
            label = "走强"
        elif chg > -0.3:
            label = "震荡"
        elif chg > -1.0:
            label = "走弱"
        else:
            label = "领跌"
        trend = _trend_label(hist) if hist else ""
        leader = ""
        if s.get("leader"):
            leader = f"，领涨股 {s['leader']}（{s['leader_chg']:+.2f}%）"
        trend_txt = f"，近5日{trend}" if trend else ""
        net = s.get("net_inflow")
        net_txt = ""
        if net and abs(net) >= 0.5:
            direction = "净流入" if net > 0 else "净流出"
            net_txt = f"，主力资金{direction} {abs(net):.1f}亿"
        sector_texts.append(
            f"【{sec['name']}】今日{label}，涨跌幅 {chg:+.2f}%{net_txt}{leader}{trend_txt}。")
        sector_rows.append({
            "name": sec["name"], "change_pct": chg,
            "leader": s.get("leader", ""), "leader_chg": s.get("leader_chg", 0.0),
            "trend": trend,
            "net_inflow": s.get("net_inflow", 0.0),
        })

    summary = sorted(data.get("sector_summary", []),
                     key=lambda x: x["change_pct"], reverse=True)
    top3 = summary[:3]
    bot3 = summary[-3:] if len(summary) >= 3 else summary
    if top3:
        sector_texts.append("今日领涨板块：" +
                            "、".join(f"{s['name']}({s['change_pct']:+.2f}%)" for s in top3) + "。")
    if bot3:
        sector_texts.append("今日领跌板块：" +
                            "、".join(f"{s['name']}({s['change_pct']:+.2f}%)" for s in bot3) + "。")

    # ---- 个股点评 ----
    stock_texts = []
    stock_rows = []
    for st in data.get("stocks", []):
        hist = st.get("hist", [])
        fund = st.get("fund")
        if not hist:
            stock_texts.append(f"【{st['name']}】行情数据未获取。")
            continue
        last = hist[-1]
        last_date = str(last.get("date"))[:10]
        when_label = "今日" if last_date == data.get("date") else f"截至 {last_date}"
        chg = last.get("change_pct")
        chg_txt = f"{chg:+.2f}%" if chg is not None else "—"
        if chg is None:
            cls = "数据缺失"
        elif chg >= 5:
            cls = "强势上攻"
        elif chg >= 2:
            cls = "明显走强"
        elif chg >= 0.3:
            cls = "小幅走强"
        elif chg > -0.3:
            cls = "窄幅整理"
        elif chg > -2:
            cls = "小幅回调"
        elif chg > -5:
            cls = "明显走弱"
        else:
            cls = "大幅下挫"
        trend = _trend_label(hist)
        vol_note = _volume_note(hist)
        closes = [h["close"] for h in hist]
        chg5 = None
        if len(closes) >= 6 and closes[-6]:
            chg5 = (closes[-1] / closes[-6] - 1) * 100
        chg5_txt = f"{chg5:+.2f}%" if chg5 is not None else "—"
        seg = (f"【{st['name']}（{st['code']}）】{when_label}{cls}，涨跌幅 {chg_txt}，"
               f"近5日 {chg5_txt}，{trend}，{vol_note}。")
        if fund and fund.get("net") not in (None, 0.0):
            seg += f"主力资金净{('流入' if fund['net'] > 0 else '流出')} " \
                   f"{_fmt_amount(abs(fund['net']))}。"
        flags = _news_flags(st)
        if flags["bull"]:
            seg += " 消息面偏暖（" + "；".join(f"「{t}」" for t in flags["bull"][:2]) + "）。"
        if flags["bear"]:
            seg += " 消息面存在扰动（" + "；".join(f"「{t}」" for t in flags["bear"][:2]) + "）。"
        stock_texts.append(seg)
        stock_rows.append({
            "code": st["code"], "name": st["name"], "close": last["close"],
            "change_pct": chg, "chg5": chg5, "turnover": last.get("turnover"),
            "net": fund.get("net") if fund else None,
            "news_count": len(st.get("news", [])),
        })

    # ---- 要闻提示 ----
    news_highlights = []
    for n in data.get("market_news", [])[:3]:
        news_highlights.append(f"{n['time']} {n['title']}")

    return {
        "market": market_text,
        "tone": tone,
        "sectors": sector_texts,
        "sector_rows": sector_rows,
        "stocks": stock_texts,
        "stock_rows": stock_rows,
        "news_highlights": news_highlights,
    }


GLOSSARY = [
    ("支撑位", "股价跌到某个价位附近容易止跌反弹，就像地板；跌破则可能继续往下走。"),
    ("压力位", "股价涨到某个价位附近容易遇阻回落，就像天花板；放量突破则可能打开上方空间。"),
    ("5日均线", "最近5天收盘价的平均价，短线强弱的分界线：站上偏强，跌破偏弱。"),
    ("放量/缩量", "成交量比前几天明显放大/缩小，反映资金参与热情的高低。"),
    ("主力资金净流入", "当天大单买入金额减去卖出金额的差额，正数说明大资金整体在买。"),
    ("换手率", "当天成交量占流通股本的比例，换手越高说明交易越活跃。"),
]


def _ma(closes, n):
    if len(closes) < n:
        return None
    return sum(closes[-n:]) / n


def build_morning_commentary(data):
    """生成盘前推荐执行报告的点评内容（通俗+专业）。"""
    indices = data.get("indices", [])
    tone = market_tone(indices)

    # ---- 核心建议（通俗版，先说结论） ----
    if tone in ("强势上涨", "震荡上行"):
        core_advice = "今天市场情绪偏暖，可以优先关注强势股回踩支撑位的机会，但别追高；"
    elif tone == "窄幅整理":
        core_advice = "今天大盘方向不明朗，建议以观察为主，等成交量放大选出方向再动手；"
    else:
        core_advice = "今天大盘偏弱，建议稳一点：只跟踪资金净流入、站稳均线的个股，弱势股不急着介入；"
    sector_chg = {s["name"]: s["summary"]["change_pct"]
                  for s in data.get("sectors", []) if s.get("summary")}
    hot = [n for n, c in sector_chg.items() if c >= 0.5]
    cold = [n for n, c in sector_chg.items() if c <= -0.5]
    if hot:
        core_advice += "板块上" + "、".join(hot[:3]) + "偏强，可多看一眼；"
    if cold:
        core_advice += "而" + "、".join(cold[:3]) + "偏弱，先谨慎。"
    if not hot and not cold:
        core_advice += "板块表现分化不大，重点看个股资金流向。"

    # ---- 重点推荐关注（规则打分） ----
    recommendations = []
    for st in data.get("stocks", []):
        hist = st.get("hist", [])
        if len(hist) < 11:
            continue
        closes = [h["close"] for h in hist]
        close = closes[-1]
        ma5 = _ma(closes, 5)
        ma10 = _ma(closes, 10)
        score = 0
        reasons = []
        if ma5 and close >= ma5:
            score += 2
            reasons.append("站稳5日均线")
        if ma10 and close >= ma10:
            score += 1
            reasons.append("10日均线上方")
        chg = hist[-1].get("change_pct") or 0
        if chg > 0:
            score += 1
            reasons.append("昨日收涨")
        if len(closes) >= 6 and closes[-6]:
            chg5 = (closes[-1] / closes[-6] - 1) * 100
            if chg5 > 3:
                score += 1
                reasons.append("近5日累计上涨")
        if _volume_note(hist) == "温和放量":
            score += 1
            reasons.append("温和放量")
        fund = st.get("fund")
        if fund and fund.get("net", 0) > 0:
            score += 2
            reasons.append("主力资金净流入")
        flags = _news_flags(st)
        if flags["bull"]:
            score += 1
            reasons.append("消息面偏暖")
        if flags["bear"]:
            score -= 2
        if chg < -3:
            score -= 2
        if score >= 3:
            recommendations.append({
                "code": st["code"], "name": st["name"], "score": score,
                "reason": "、".join(reasons[:4]) or "走势相对稳健",
            })
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    recommendations = recommendations[:5]
    if not recommendations:
        recommendations = [{
            "code": "", "name": "暂无明显强势股", "score": 0,
            "reason": "今日数据偏弱，建议先观望，等待资金进场信号",
        }]

    # ---- 通俗分析（大白话） ----
    sh = next((i for i in indices if i["name"] == "上证指数"), None)
    if sh:
        plain_analysis = (f"简单说，昨天大盘{'跌了' if sh['change_pct'] < 0 else '涨了'} "
                          f"{abs(sh['change_pct']):.2f}%，整体偏{'弱' if sh['change_pct'] < 0 else '强'}。")
    else:
        plain_analysis = "简单说，昨天大盘整体波动不大。"
    plain_analysis += ("今天开盘先盯两件事：一看成交量，放量上涨才算真强，缩量反弹容易回落；"
                       "二看科技主线里的资金，钱往哪几个板块流，机会往往就在哪。"
                       "推荐观察的股票不是让直接买，而是先加入重点跟踪名单，"
                       "等它们满足报告里的执行条件再考虑。")

    # ---- 昨日回顾 ----
    summary_parts = [f"昨日大盘整体呈“{tone}”格局。"]
    if indices:
        desc = "、".join(f"{i['name']}{i['change_pct']:+.2f}%" for i in indices)
        summary_parts.append(f"主要指数：{desc}。")
    summary_parts.append("今日开盘前重点观察科技主线能否延续、量能是否配合。")
    summary = "".join(summary_parts)

    # ---- 板块聚焦 ----
    sector_focus = []
    for sec in data.get("sectors", []):
        s = sec.get("summary")
        hist = sec.get("hist", [])
        if not s:
            continue
        chg = s["change_pct"]
        trend = _trend_label(hist) if hist else ""
        leader = f"，板块龙头 {s['leader']}" if s.get("leader") else ""
        if chg >= 1.0:
            heat = "昨日强势领涨，今日留意能否延续"
        elif chg >= 0:
            heat = "昨日小幅上涨，人气平稳"
        elif chg > -1.0:
            heat = "昨日小幅回调，属正常波动"
        else:
            heat = "昨日明显走弱，今日谨慎对待"
        sector_focus.append(
            f"【{sec['name']}】昨涨跌 {chg:+.2f}%，近5日{trend or '—'}。{heat}{leader}。")

    # ---- 个股执行清单 ----
    stock_actions = []
    stock_table_rows = []
    for st in data.get("stocks", []):
        hist = st.get("hist", [])
        if not hist:
            continue
        closes = [h["close"] for h in hist]
        lows = [h["low"] for h in hist[-10:]]
        highs = [h["high"] for h in hist[-10:]]
        close = closes[-1]
        support = min(lows)
        resistance = max(highs)
        ma5 = _ma(closes, 5)
        ma10 = _ma(closes, 10)
        ma20 = _ma(closes, 20)

        parts = [f"【{st['name']}（{st['code']}）】昨收 {close:.2f} 元。"]
        if ma5 and close >= ma5:
            parts.append(f"股价站上5日均线（{ma5:.2f}），短线偏强。")
        elif ma10 and close >= ma10:
            parts.append(f"股价位于5日（{ma5:.2f}）与10日（{ma10:.2f}）均线之间，短线震荡。")
        elif ma10:
            parts.append(f"股价跌破10日均线（{ma10:.2f}），短线偏弱，关注能否收复。")
        parts.append(
            f"近10日支撑位约 {support:.2f}（地板），压力位约 {resistance:.2f}（天花板）。")

        # 情景式执行清单
        parts.append("执行参考：")
        parts.append(
            f"① 若开盘放量站上 {resistance:.2f}，视为强势信号，可跟踪量能持续性；")
        parts.append(
            f"② 若回踩 {support:.2f} 附近缩量企稳，属正常整理，可观察承接；")
        parts.append(
            f"③ 若跌破 {support:.2f}，短线转弱，建议以观望为主。")

        vol_note = _volume_note(hist)
        if vol_note:
            parts.append(f"量能：昨日{vol_note}。")
        fund = st.get("fund")
        if fund and fund.get("net") not in (None, 0.0):
            direction = "流入" if fund["net"] > 0 else "流出"
            parts.append(f"主力资金昨净{direction} {_fmt_amount(abs(fund['net']))}。")
        flags = _news_flags(st)
        if flags["bull"]:
            parts.append("消息面偏暖：" + "；".join(f"「{t}」" for t in flags["bull"][:2]) + "。")
        if flags["bear"]:
            parts.append("消息面有扰动：" + "；".join(f"「{t}」" for t in flags["bear"][:2]) + "。")
        stock_actions.append("".join(parts))
        stock_table_rows.append({
            "code": st["code"], "name": st["name"], "close": close,
            "support": support, "resistance": resistance,
            "ma5": ma5, "ma10": ma10,
            "change_pct": hist[-1].get("change_pct"),
        })

    # ---- 今日盘前要点 ----
    watch_points = []
    for n in data.get("market_news", [])[:5]:
        watch_points.append(f"{n['time']} {n['title']}")
    if not watch_points:
        watch_points.append("暂无新增重要消息，以昨日收盘数据为参考。")

    return {
        "summary": summary,
        "tone": tone,
        "core_advice": core_advice,
        "recommendations": recommendations,
        "plain_analysis": plain_analysis,
        "sectors": sector_focus,
        "stocks": stock_actions,
        "stock_rows": stock_table_rows,
        "watch_points": watch_points,
        "glossary": GLOSSARY,
    }
