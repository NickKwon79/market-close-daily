"""Fetch global stock indices via yfinance with last/prev close and 5-day sparkline."""
from __future__ import annotations

import logging
from typing import Optional

import yfinance as yf

log = logging.getLogger(__name__)

INDEX_MAP = {
    "sp500":    {"symbol": "^GSPC",     "name": "S&P 500",          "region": "USA",       "kind": "broad"},
    "nasdaq":   {"symbol": "^IXIC",     "name": "NASDAQ Composite", "region": "USA",       "kind": "tech"},
    "dow":      {"symbol": "^DJI",      "name": "Dow Jones 30",     "region": "USA",       "kind": "value"},
    "kospi":    {"symbol": "^KS11",     "name": "KOSPI",            "region": "KOREA",     "kind": "broad"},
    "nikkei":   {"symbol": "^N225",     "name": "Nikkei 225",       "region": "JAPAN",     "kind": "broad"},
    "hangseng": {"symbol": "^HSI",      "name": "Hang Seng",        "region": "HONG KONG", "kind": "broad"},
    "csi300":   {"symbol": "000300.SS", "name": "CSI 300",          "region": "CHINA",     "kind": "broad"},
    "ftse":     {"symbol": "^FTSE",     "name": "FTSE 100",         "region": "UK",        "kind": "broad"},
    "dax":      {"symbol": "^GDAXI",    "name": "DAX",              "region": "GERMANY",   "kind": "broad"},
}


def _fetch_one(key: str, meta: dict) -> Optional[dict]:
    try:
        ticker = yf.Ticker(meta["symbol"])
        hist = ticker.history(period="10d", interval="1d", auto_adjust=False)
        if hist.empty or len(hist) < 2:
            log.warning("indexes:%s insufficient history (%d rows)", key, len(hist))
            return None
        closes = hist["Close"].dropna().tolist()
        if len(closes) < 2:
            return None
        last = float(closes[-1])
        prev = float(closes[-2])
        change = last - prev
        change_pct = (change / prev) * 100.0 if prev else 0.0
        spark = [round(float(c), 2) for c in closes[-5:]]
        as_of = str(hist.index[-1].date())
        return {
            "key": key,
            "symbol": meta["symbol"],
            "name": meta["name"],
            "region": meta["region"],
            "kind": meta["kind"],
            "price": round(last, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "spark": spark,
            "as_of": as_of,
        }
    except Exception as e:
        log.warning("indexes:%s fetch failed: %s", key, e)
        return None


def fetch_all() -> dict:
    out: dict = {}
    for key, meta in INDEX_MAP.items():
        row = _fetch_one(key, meta)
        if row is not None:
            out[key] = row
    log.info("indexes: %d/%d fetched", len(out), len(INDEX_MAP))
    return out
