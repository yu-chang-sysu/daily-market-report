# -*- coding: utf-8 -*-
"""数据采集模块：行情、板块、新闻、资金流（公开接口，只读）。"""
import datetime as dt
import logging
import time

import akshare as ak
import pandas as pd
import re

log = logging.getLogger("fetch")

INDEX_WATCH = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300"]


def _retry(fn, tries=3, delay=1.0):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(delay * (i + 1))
    raise last


def _sina_symbol(code: str) -> str:
    code = code.strip()
    if code.startswith(("sh", "sz", "bj")):
        return code
    if code.startswith(("60", "68", "90")):
        return "sh" + code
    if code.startswith(("00", "30", "20")):
        return "sz" + code
    if code.startswith(("43", "83", "87", "88", "92")):
        return "bj" + code
    return "sh" + code


def _pick_col(df, candidates):
    """按候选列名模糊匹配（接口列名可能随版本变化）。"""
    for col in df.columns:
        cs = str(col)
        if any(k in cs for k in candidates):
            return col
    return None


def _to_float(value):
    """把 '1305.32万' / '1.2亿' 之类转为数值。"""
    if value is None:
        return 0.0
    s = str(value).strip().replace(",", "").replace("+", "")
    if s in ("", "-", "--", "nan", "None"):
        return 0.0
    mult = 1.0
    if s.endswith("万亿"):
        mult, s = 1e12, s[:-2]
    elif s.endswith("亿"):
        mult, s = 1e8, s[:-1]
    elif s.endswith("万"):
        mult, s = 1e4, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


def _parse_time(value):
    """解析常见时间字符串/对象，失败返回 None。"""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    if isinstance(value, dt.time):
        return dt.datetime.combine(dt.date.today(), value)
    s = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _sanitize(text):
    """去除无法用中文字体渲染的符号（emoji、特殊图标等）。"""
    if not text:
        return ""
    allowed = (r"\u4e00-\u9fff"        # 中日韩统一表意文字
               r"\u3000-\u303f"        # 中日韩标点
               r"\uff00-\uffef"        # 全角形式
               r"\u2000-\u206f"        # 通用标点
               r"\u0020-\u007e"        # ASCII 可打印
               r"\u00a0-\u024f")       # 拉丁扩展等
    cleaned = re.sub(f"[^{allowed}]", "", str(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def fetch_indices():
    """主要大盘指数（新浪）。"""
    df = _retry(ak.stock_zh_index_spot_sina)
    name_col = _pick_col(df, ["名称", "指数名称"])
    if name_col is None:
        return []
    out = []
    seen = set()
    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        if name in INDEX_WATCH and name not in seen:
            try:
                out.append({
                    "name": name,
                    "close": float(row["最新价"]),
                    "change": float(row["涨跌额"]),
                    "change_pct": float(row["涨跌幅"]),
                    "amount": float(row["成交额"]) if pd.notna(row["成交额"]) else 0.0,
                })
                seen.add(name)
            except (TypeError, ValueError, KeyError):
                continue
    return out


def fetch_sector_summary():
    """同花顺全部行业板块实时汇总。"""
    df = _retry(ak.stock_board_industry_summary_ths)
    name_col = _pick_col(df, ["板块", "名称"])
    chg_col = _pick_col(df, ["涨跌幅"])
    lead_col = _pick_col(df, ["领涨股"]) or _pick_col(df, ["领涨股-名称"])
    lead_chg_col = _pick_col(df, ["领涨股-涨跌幅"])
    up_col = _pick_col(df, ["上涨家数"])
    down_col = _pick_col(df, ["下跌家数"])
    amount_col = _pick_col(df, ["总成交额"])
    net_col = _pick_col(df, ["净流入"])
    rows = []
    for _, r in df.iterrows():
        try:
            rows.append({
                "name": str(r[name_col]).strip(),
                "change_pct": float(r[chg_col]),
                "leader": str(r[lead_col]).strip() if lead_col else "",
                "leader_chg": float(r[lead_chg_col]) if lead_chg_col else 0.0,
                "up_count": int(r[up_col]) if up_col else None,
                "down_count": int(r[down_col]) if down_col else None,
                "amount": float(r[amount_col]) if amount_col else 0.0,
                "net_inflow": float(r[net_col]) if net_col else 0.0,
            })
        except (TypeError, ValueError, KeyError):
            continue
    return rows


def fetch_sector_hist(name, days=8):
    """某板块近 N 日收盘走势（同花顺行业指数，概念板块自动回退）。"""
    end = dt.date.today()
    start = end - dt.timedelta(days=days * 2 + 10)
    try:
        df = _retry(lambda: ak.stock_board_industry_index_ths(
            symbol=name, start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d")))
    except Exception:  # noqa: BLE001
        df = _retry(lambda: ak.stock_board_concept_index_ths(
            symbol=name, start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d")))
    date_col = _pick_col(df, ["日期"])
    close_col = _pick_col(df, ["收盘价"])
    if date_col is None or close_col is None:
        return []
    df = df.sort_values(date_col).tail(days)
    return [{"date": str(r[date_col])[:10], "close": float(r[close_col])} for _, r in df.iterrows()]


def fetch_concept_hot_map():
    """同花顺热门概念（概念名称 -> 龙头股）。"""
    try:
        df = _retry(lambda: ak.stock_board_concept_summary_ths(), tries=2)
    except Exception as e:  # noqa: BLE001
        log.warning("概念热点获取失败: %s", e)
        return {}
    name_col = _pick_col(df, ["概念名称", "名称", "板块"])
    lead_col = _pick_col(df, ["龙头股", "领涨股"])
    if name_col is None or lead_col is None:
        return {}
    return {str(r[name_col]).strip(): str(r[lead_col]).strip()
            for _, r in df.iterrows()}


def _quote_from_hist(hist):
    """从板块指数历史推算今日涨跌幅（概念板块无实时汇总时用）。"""
    if not hist or len(hist) < 2 or not hist[-2]["close"]:
        return None
    chg = (hist[-1]["close"] / hist[-2]["close"] - 1.0) * 100.0
    return {"name": "", "change_pct": chg, "leader": "", "leader_chg": 0.0,
            "up_count": None, "down_count": None, "amount": 0.0,
            "net_inflow": 0.0}


def _check_hist_date(hist, expected_date, label):
    """校验日K最后一根K线日期是否等于预期报告日期，返回告警文本或 None。"""
    if not hist:
        return f"{label} 无日K数据"
    last_date = str(hist[-1]["date"])[:10]
    if last_date != expected_date:
        return f"{label} 日K数据截至 {last_date}，非报告日期 {expected_date}"
    return None


def _fetch_hist_fresh(fetch_fn, expected_date, label, retries=3, delay=60):
    """拉取日K并校验日期新鲜度；未刷新时在 18:30 前重试。返回 (rows, warning)。"""
    rows = fetch_fn()
    warning = _check_hist_date(rows, expected_date, label)
    if warning:
        now = dt.datetime.now()
        if now.hour * 60 + now.minute < 18 * 60 + 30:
            for _ in range(retries):
                time.sleep(delay)
                try:
                    rows = fetch_fn()
                except Exception:  # noqa: BLE001
                    continue
                warning = _check_hist_date(rows, expected_date, label)
                if not warning:
                    break
    return rows, warning


def fetch_stock_hist(code, days=30):
    """个股日线（新浪），返回最近 days 行。"""
    end = dt.date.today()
    start = end - dt.timedelta(days=days * 2 + 20)
    df = _retry(lambda: ak.stock_zh_a_daily(
        symbol=_sina_symbol(code), start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d")))
    df = df.sort_values("date").tail(days)
    rows = []
    prev_close = None
    for _, r in df.iterrows():
        close = float(r["close"])
        pct = ((close / prev_close) - 1.0) * 100.0 if prev_close else None
        rows.append({
            "date": str(r["date"])[:10],
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": close,
            "volume": float(r["volume"]),
            "amount": float(r["amount"]),
            "turnover": float(r["turnover"]) * 100.0,
            "change_pct": pct,
        })
        prev_close = close
    return rows


def fetch_stock_news(code, days_back=3, limit=6):
    """个股新闻（东方财富），按时间倒序。"""
    try:
        df = _retry(lambda: ak.stock_news_em(symbol=code), tries=2)
    except Exception as e:  # noqa: BLE001
        log.warning("新闻获取失败 %s: %s", code, e)
        return []
    cutoff = dt.datetime.now() - dt.timedelta(days=days_back)
    out = []
    title_col = _pick_col(df, ["新闻标题"])
    content_col = _pick_col(df, ["新闻内容"])
    time_col = _pick_col(df, ["发布时间"])
    source_col = _pick_col(df, ["文章来源"])
    url_col = _pick_col(df, ["新闻链接"])
    for _, r in df.iterrows():
        t = _parse_time(r[time_col]) if time_col else None
        if t is not None and t.replace(tzinfo=None) < cutoff:
            continue
        content = str(r[content_col]).strip() if content_col is not None else ""
        title = _sanitize(r[title_col]) if title_col is not None else ""
        if not title:
            continue
        out.append({
            "title": title,
            "time": t.strftime("%m-%d %H:%M") if t else "",
            "source": str(r[source_col]).strip() if source_col else "",
            "url": str(r[url_col]).strip() if url_col else "",
            "snippet": (content[:110] + "…") if len(content) > 110 else content,
        })
        if len(out) >= limit:
            break
    return out


def fetch_fund_flow_map():
    """全市场个股资金流（同花顺即时），返回 {code: {...}}。"""
    try:
        df = _retry(lambda: ak.stock_fund_flow_individual(symbol="即时"), tries=2)
    except Exception as e:  # noqa: BLE001
        log.warning("资金流获取失败: %s", e)
        return {}
    code_col = _pick_col(df, ["股票代码"])
    name_col = _pick_col(df, ["股票简称"])
    net_col = _pick_col(df, ["净额"])
    inflow_col = _pick_col(df, ["流入资金"])
    outflow_col = _pick_col(df, ["流出资金"])
    chg_col = _pick_col(df, ["涨跌幅"])
    out = {}
    for _, r in df.iterrows():
        code = str(r[code_col]).strip().zfill(6)
        try:
            out[code] = {
                "name": str(r[name_col]).strip(),
                "net": _to_float(r[net_col]) if net_col else 0.0,
                "inflow": _to_float(r[inflow_col]) if inflow_col else 0.0,
                "outflow": _to_float(r[outflow_col]) if outflow_col else 0.0,
                "change_pct": float(str(r[chg_col]).replace("%", "")) if chg_col else None,
            }
        except (TypeError, ValueError, KeyError):
            continue
    return out


def fetch_cls_news(count=10):
    """财联社电报（市场要闻）。"""
    try:
        df = _retry(lambda: ak.stock_info_global_cls(symbol="全部"), tries=2)
    except Exception as e:  # noqa: BLE001
        log.warning("财联社要闻获取失败: %s", e)
        return []
    title_col = _pick_col(df, ["标题"])
    content_col = _pick_col(df, ["内容"])
    time_col = _pick_col(df, ["发布时间"])
    out = []
    for _, r in df.head(count).iterrows():
        t = _parse_time(r[time_col]) if time_col else None
        content = str(r[content_col]).strip() if content_col is not None else ""
        title = _sanitize(r[title_col]) if title_col is not None else ""
        if not title:
            title = content[:60]
        if not title:
            continue
        out.append({
            "title": _sanitize(title),
            "time": t.strftime("%H:%M") if t else "",
            "snippet": (content[:100] + "…") if len(content) > 100 else content,
        })
    return out


def fetch_all(cfg, mode="evening"):
    """汇总抓取所有数据，单项失败不影响整体。"""
    wl = cfg["watchlist"]
    rpt = cfg["report"]
    data = {"date": dt.date.today().strftime("%Y-%m-%d"), "errors": [],
            "data_date": None, "mode": mode}

    try:
        data["indices"] = fetch_indices()
    except Exception as e:  # noqa: BLE001
        data["indices"] = []
        data["errors"].append(f"大盘指数: {e}")

    try:
        data["sector_summary"] = fetch_sector_summary()
    except Exception as e:  # noqa: BLE001
        data["sector_summary"] = []
        data["errors"].append(f"板块汇总: {e}")

    concept_map = fetch_concept_hot_map()

    data["sectors"] = []
    for name in wl.get("sectors", []):
        item = {"name": name, "summary": None, "hist": []}
        try:
            if mode == "evening":
                item["hist"], warn = _fetch_hist_fresh(
                    lambda: fetch_sector_hist(name, days=6),
                    data["date"], f"板块 {name}")
                if warn:
                    data["errors"].append(warn)
            else:
                item["hist"] = fetch_sector_hist(name, days=6)
        except Exception as e:  # noqa: BLE001
            data["errors"].append(f"板块历史 {name}: {e}")
        item["summary"] = next(
            (s for s in data["sector_summary"] if s["name"] == name), None)
        if item["summary"] is None:
            item["summary"] = _quote_from_hist(item["hist"])
            if item["summary"] and name in concept_map:
                item["summary"]["leader"] = concept_map[name]
        data["sectors"].append(item)

    try:
        fund_map = fetch_fund_flow_map()
    except Exception as e:  # noqa: BLE001
        fund_map = {}
        data["errors"].append(f"资金流: {e}")

    data["stocks"] = []
    for s in wl.get("stocks", []):
        code = str(s["code"]).strip()
        name = s.get("name", code)
        item = {"code": code, "name": name, "hist": [], "news": [], "fund": None}
        try:
            if mode == "evening":
                item["hist"], warn = _fetch_hist_fresh(
                    lambda: fetch_stock_hist(code, days=rpt.get("hist_days", 30)),
                    data["date"], f"个股 {name}")
                if warn:
                    data["errors"].append(warn)
            else:
                item["hist"] = fetch_stock_hist(code, days=rpt.get("hist_days", 30))
        except Exception as e:  # noqa: BLE001
            data["errors"].append(f"个股行情 {name}: {e}")
        try:
            item["news"] = fetch_stock_news(
                code, days_back=rpt.get("news_days", 3),
                limit=rpt.get("max_news_per_stock", 6))
        except Exception:  # noqa: BLE001
            pass
        if code in fund_map:
            item["fund"] = fund_map[code]
        data["stocks"].append(item)

    try:
        data["market_news"] = fetch_cls_news(rpt.get("market_news_count", 10))
    except Exception as e:  # noqa: BLE001
        data["market_news"] = []
        data["errors"].append(f"财联社要闻: {e}")

    all_last = []
    for item in data.get("stocks", []) + data.get("sectors", []):
        if item.get("hist"):
            all_last.append(str(item["hist"][-1]["date"])[:10])
    data["data_date"] = min(all_last) if all_last else data["date"]
    return data
