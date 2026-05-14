"""FX rates: ExchangeRate.host for spot, yfinance for DXY (Dollar Index)."""
from __future__ import annotations

import logging
from typing import Optional

import requests
import yfinance as yf

log = logging.getLogger(__name__)

PAIRS_USD_BASE = ["KRW", "JPY", "EUR", "CNY"]


def _fetch_spot_rates() -> dict:
    out: dict = {}
    try:
        r = requests.get(
            "https://api.exchangerate.host/latest",
            params={"base": "USD", "symbols": ",".join(PAIRS_USD_BASE)},
            timeout=10,
        )
        r.raise_for_status()
        rates = r.json().get("rates", {}) or {}
    except Exception as e:
        log.warning("fx:exchangerate.host failed: %s — falling back to yfinance", e)
        rates = {}

    for code in PAIRS_USD_BASE:
        rate = rates.get(code)
        if rate is None:
            rate = _yf_fx_fallback(code)
        if rate is None:
            continue
        if code == "EUR":
            out["EURUSD"] = {
                "key": "EURUSD",
                "pair": "EUR/USD",
                "rate": round(1.0 / rate, 4),
                "kind": "inverse",
            }
        else:
            decimals = 2 if code == "JPY" else 4
            out[f"USD{code}"] = {
                "key": f"USD{code}",
                "pair": f"USD/{code}",
                "rate": round(rate, decimals),
                "kind": "direct",
            }
    return out


def _yf_fx_fallback(code: str) -> Optional[float]:
    try:
        sym = f"USD{code}=X"
        hist = yf.Ticker(sym).history(period="3d", interval="1d", auto_adjust=False)
        if hist.empty:
            return None
        return float(hist["Close"].dropna().iloc[-1])
    except Exception as e:
        log.warning("fx:yfinance %s fallback failed: %s", code, e)
        return None


def _fetch_dxy() -> Optional[dict]:
    try:
        hist = yf.Ticker("DX-Y.NYB").history(period="5d", interval="1d", auto_adjust=False)
        closes = hist["Close"].dropna().tolist() if not hist.empty else []
        if len(closes) < 2:
            return None
        last, prev = float(closes[-1]), float(closes[-2])
        change = last - prev
        change_pct = (change / prev) * 100.0 if prev else 0.0
        return {
            "key": "DXY",
            "pair": "DXY",
            "rate": round(last, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "kind": "index",
        }
    except Exception as e:
        log.warning("fx:dxy failed: %s", e)
        return None


def fetch_all() -> dict:
    out = _fetch_spot_rates()
    dxy = _fetch_dxy()
    if dxy:
        out["DXY"] = dxy
    log.info("fx: %d pairs fetched", len(out))
    return out
