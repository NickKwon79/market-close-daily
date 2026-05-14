"""Commodities + bond yields via yfinance: WTI, Gold, BTC, US10Y, VIX."""
from __future__ import annotations

import logging
from typing import Optional

import yfinance as yf

log = logging.getLogger(__name__)

COMMODITY_MAP = {
    "wti":    {"symbol": "CL=F",   "name": "WTI Crude",    "unit": "$"},
    "gold":   {"symbol": "GC=F",   "name": "Gold",         "unit": "$"},
    "btc":    {"symbol": "BTC-USD","name": "Bitcoin",      "unit": "$"},
    "ust10y": {"symbol": "^TNX",   "name": "10Y UST Yield","unit": "%"},
    "vix":    {"symbol": "^VIX",   "name": "VIX",          "unit": ""},
}


def _fetch_one(key: str, meta: dict) -> Optional[dict]:
    try:
        hist = yf.Ticker(meta["symbol"]).history(period="5d", interval="1d", auto_adjust=False)
        closes = hist["Close"].dropna().tolist() if not hist.empty else []
        if len(closes) < 2:
            return None
        last, prev = float(closes[-1]), float(closes[-2])
        change = last - prev
        change_pct = (change / prev) * 100.0 if prev else 0.0
        # UST10Y from yfinance comes scaled (^TNX = yield * 10), but typically already in % units. Keep as-is.
        return {
            "key": key,
            "symbol": meta["symbol"],
            "name": meta["name"],
            "unit": meta["unit"],
            "price": round(last, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as e:
        log.warning("commodity:%s failed: %s", key, e)
        return None


def fetch_all() -> dict:
    out: dict = {}
    for key, meta in COMMODITY_MAP.items():
        row = _fetch_one(key, meta)
        if row is not None:
            out[key] = row
    log.info("commodities: %d/%d fetched", len(out), len(COMMODITY_MAP))
    return out
