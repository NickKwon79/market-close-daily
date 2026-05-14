"""LLM summarizer: RSS headlines -> Korean JSON summary via Claude.

Prevents hallucination by requiring every output headline to map back to a
source-supplied URL. Headlines whose URLs are not in the input pool are dropped.
"""
from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior markets editor for a Korean financial dashboard.
You receive a list of raw English/Korean headlines from market news RSS feeds.

Your job:
1. Select 5-7 most market-moving headlines (macro, central banks, mega-cap equities, geopolitics affecting markets).
2. For each, write a one-line Korean summary (한 문장, 60자 이내, 팩트 위주).
3. Write a 2-3 sentence Korean market summary (시장 전반 분위기).
4. Tag overall risk sentiment: one of [RISK-ON, RISK-OFF, MIXED].

Constraints:
- Output STRICT JSON only, no markdown fences, no commentary.
- Every headline MUST reuse the original `url` field verbatim from input. Do not invent URLs.
- Do NOT invent prices, percentages, or facts not present in headlines.
- If headlines are insufficient, return fewer (minimum 3).

Output schema:
{
  "headlines": [
    {"title_ko": "...", "source": "...", "url": "https://...", "time_label": "HH:MM" or ""}
  ],
  "market_summary_ko": "...",
  "risk_sentiment": "RISK-ON" | "RISK-OFF" | "MIXED"
}
"""


def _build_user_prompt(headlines: List[dict]) -> str:
    lines = ["다음은 오늘 수집된 시장 뉴스 헤드라인입니다. 위 지침에 따라 JSON으로 답하세요.\n"]
    for i, h in enumerate(headlines, 1):
        lines.append(f"{i}. [{h.get('source','')}] {h.get('title','')}  <{h.get('url','')}>")
    return "\n".join(lines)


def _call_claude(system: str, user: str, model: str) -> Optional[str]:
    try:
        import anthropic
    except ImportError:
        log.error("summarize: anthropic SDK not installed")
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("summarize: ANTHROPIC_API_KEY missing — skipping LLM call")
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text if resp.content else None
    except Exception as e:
        log.error("summarize: Claude call failed: %s", e)
        return None


def _validate(parsed: dict, valid_urls: set) -> dict:
    """Drop headlines whose URL is not in the source pool (hallucination guard)."""
    cleaned = []
    for item in parsed.get("headlines", []):
        url = (item.get("url") or "").strip()
        if not url or url not in valid_urls:
            log.warning("summarize: dropping headline with invalid url: %s", url)
            continue
        cleaned.append({
            "title_ko":   (item.get("title_ko") or "").strip()[:200],
            "source":     (item.get("source") or "").strip()[:60],
            "url":        url,
            "time_label": (item.get("time_label") or "").strip()[:10],
        })
    sentiment = parsed.get("risk_sentiment", "MIXED")
    if sentiment not in ("RISK-ON", "RISK-OFF", "MIXED"):
        sentiment = "MIXED"
    return {
        "headlines": cleaned,
        "market_summary_ko": (parsed.get("market_summary_ko") or "").strip()[:600],
        "risk_sentiment": sentiment,
    }


def summarize(
    headlines: List[dict],
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    """Return a validated summary dict; on failure returns an empty fallback."""
    fallback = {
        "headlines": [],
        "market_summary_ko": "",
        "risk_sentiment": "MIXED",
    }
    if not headlines:
        log.warning("summarize: no headlines to summarize")
        return fallback

    valid_urls = {h.get("url", "") for h in headlines if h.get("url")}
    user_prompt = _build_user_prompt(headlines)
    raw = _call_claude(SYSTEM_PROMPT, user_prompt, model)
    if not raw:
        return fallback

    try:
        # Strip accidental markdown fences just in case.
        raw_clean = raw.strip()
        if raw_clean.startswith("```"):
            raw_clean = raw_clean.split("```", 2)[1]
            if raw_clean.startswith("json"):
                raw_clean = raw_clean[4:].strip()
        parsed = json.loads(raw_clean)
    except Exception as e:
        log.error("summarize: JSON parse failed: %s | raw=%s", e, raw[:200] if raw else "")
        return fallback

    return _validate(parsed, valid_urls)
