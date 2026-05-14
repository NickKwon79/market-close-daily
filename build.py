#!/usr/bin/env python3
"""Build orchestrator: fetch -> summarize -> render -> persist.

Usage:
    python build.py                            # full pipeline
    python build.py --offline                  # skip network, use data/latest.json
    python build.py --no-llm                   # skip LLM (keep yesterday's summary)
    python build.py --output dist/index.html   # custom output path
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from fetchers import indexes as fx_indexes
from fetchers import fx as fx_fx
from fetchers import commodities as fx_commodities
from fetchers import news as fx_news
import summarize

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"
TEMPLATES_DIR = ROOT / "templates"
DIST_DIR = ROOT / "dist"
LATEST_JSON = DATA_DIR / "latest.json"

KST = ZoneInfo("Asia/Seoul")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("build")


def _now_kst() -> datetime:
    return datetime.now(KST)


def _load_previous() -> dict:
    if LATEST_JSON.exists():
        try:
            return json.loads(LATEST_JSON.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("previous latest.json unreadable: %s", e)
    return {}


def collect(use_network: bool, use_llm: bool) -> dict:
    """Run all fetchers, summarize news, return merged dict.

    Partial failures fall back per-section to previous values.
    """
    previous = _load_previous()
    now = _now_kst()

    if use_network:
        log.info("fetching indexes...")
        indexes = fx_indexes.fetch_all() or previous.get("indexes", {})
        log.info("fetching fx...")
        fx = fx_fx.fetch_all() or previous.get("fx", {})
        log.info("fetching commodities...")
        commodities = fx_commodities.fetch_all() or previous.get("commodities", {})
        log.info("fetching news...")
        headlines = fx_news.fetch_all() or previous.get("headlines_raw", [])
    else:
        log.info("offline mode — reusing previous data")
        indexes = previous.get("indexes", {})
        fx = previous.get("fx", {})
        commodities = previous.get("commodities", {})
        headlines = previous.get("headlines_raw", [])

    if use_llm and headlines:
        log.info("summarizing %d headlines via LLM...", len(headlines))
        summary = summarize.summarize(headlines)
        if not summary["headlines"]:
            log.warning("LLM returned no valid headlines — falling back to previous summary")
            summary = previous.get("summary") or summary
    else:
        log.info("skipping LLM — using previous summary")
        summary = previous.get("summary") or {
            "headlines": [],
            "market_summary_ko": "",
            "risk_sentiment": "MIXED",
        }

    merged = {
        "as_of_kst":        now.strftime("%Y-%m-%d %H:%M KST"),
        "as_of_date":       now.strftime("%Y-%m-%d"),
        "as_of_weekday":    ["MON","TUE","WED","THU","FRI","SAT","SUN"][now.weekday()],
        "build_unix":       int(now.timestamp()),
        "indexes":          indexes,
        "fx":               fx,
        "commodities":      commodities,
        "headlines_raw":    headlines,
        "summary":          summary,
    }
    return merged


def render(data: dict, output: Path) -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["fmt_num"] = lambda v, d=2: f"{v:,.{d}f}" if isinstance(v, (int, float)) else "—"
    env.filters["fmt_pct"] = lambda v: f"{v:+.2f}%" if isinstance(v, (int, float)) else "—"
    env.filters["fmt_chg"] = lambda v: f"{v:+,.2f}" if isinstance(v, (int, float)) else "—"

    def to_spark_path(spark, w=200, h=50):
        if not spark or len(spark) < 2:
            return "M0,25 L200,25"
        lo, hi = min(spark), max(spark)
        rng = (hi - lo) or 1.0
        n = len(spark)
        pts = []
        for i, v in enumerate(spark):
            x = (i / (n - 1)) * w
            y = h - 8 - ((v - lo) / rng) * (h - 16)
            pts.append(f"{x:.1f},{y:.1f}")
        return "M" + " L".join(pts)

    env.filters["spark_path"] = to_spark_path

    template = env.get_template("index.html.j2")
    html = template.render(**data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    log.info("rendered: %s (%d bytes)", output, len(html.encode("utf-8")))


def persist(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    hist = HISTORY_DIR / f"{data['as_of_date']}.json"
    hist.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("persisted: %s + %s", LATEST_JSON.name, hist.name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip all network calls")
    ap.add_argument("--no-llm",  action="store_true", help="skip LLM summarization")
    ap.add_argument("--output",  default=str(DIST_DIR / "index.html"))
    args = ap.parse_args()

    use_network = not args.offline
    use_llm = (not args.no_llm) and (not args.offline)

    data = collect(use_network=use_network, use_llm=use_llm)

    if use_network:
        persist(data)

    render(data, Path(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
