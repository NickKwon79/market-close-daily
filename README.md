# market-close-daily

매일 자동으로 갱신되는 글로벌 증시 장마감 랜딩페이지. GitHub Pages에 무료 호스팅, GitHub Actions 스케줄로 하루 2회 빌드.

## 무엇이 들어있나

| 영역 | 소스 |
|---|---|
| 지수 (미·유·아 9개) | Yahoo Finance (yfinance) |
| 환율 (USD/KRW·JPY·CNY, EUR/USD, DXY) | ExchangeRate.host + yfinance |
| 원자재·채권·VIX | yfinance (CL=F, GC=F, BTC-USD, ^TNX, ^VIX) |
| 뉴스 헤드라인 | 8개 RSS 피드 + Claude Haiku로 한국어 5-7개 요약 |
| 디자인 | 블룸버그 다크 톤 단일 HTML (인라인 CSS) |

## 빠른 시작

### 1) 로컬 드라이런 (네트워크 + LLM 없이 더미 데이터로 렌더)

```bash
cd market-close-daily
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python build.py --offline                # data/latest.json 시드만 사용
open dist/index.html
```

### 2) 로컬 실데이터 빌드 (네트워크 사용, LLM 옵션)

```bash
# LLM 없이 — 수치만 갱신
python build.py --no-llm

# LLM 요약 포함
export ANTHROPIC_API_KEY=sk-ant-...
python build.py
open dist/index.html
```

### 3) GitHub Pages에 올리기

1. GitHub 웹 UI에서 **public** 리포지토리 `market-close-daily` 생성
2. 로컬에서 git push:
   ```bash
   cd market-close-daily
   git init -b main
   git add .
   git commit -m "initial: daily market-close auto-update pipeline"
   git remote add origin https://github.com/<YOUR_USER>/market-close-daily.git
   git push -u origin main
   ```
3. Repo **Settings → Pages → Source: "GitHub Actions"** 선택
4. Repo **Settings → Secrets and variables → Actions** 에서 `ANTHROPIC_API_KEY` 등록
5. **Actions** 탭 → "Daily Update" 워크플로 → **Run workflow** 수동 실행
6. 빌드 그린 후 `https://<YOUR_USER>.github.io/market-close-daily/` 접속

## 스케줄

- **KST 06:30** (UTC 21:30 전일) — 매일, 미장 마감 직후
- **KST 16:30** (UTC 07:30) — 평일, 한·아·유럽장 정리 후

`workflow_dispatch`로 언제든 수동 트리거 가능.

## 비용

| 항목 | 비용 |
|---|---|
| GitHub Pages | 무료 (public repo 무제한 대역폭) |
| GitHub Actions | 무료 (public repo cron 무제한) |
| Claude Haiku 4 LLM (60회/월) | 약 $0.42/월 |
| 데이터 API | 무료 (yfinance, ExchangeRate.host, RSS) |
| **총 운영비** | **$1 미만/월** |

LLM을 끄려면 워크플로의 `python build.py`를 `python build.py --no-llm`으로 바꾸면 됩니다.

## 폴백 동작

- 어떤 fetcher가 실패해도 `data/latest.json`의 직전 성공본을 섹션별로 재사용
- 한국 휴장 등으로 `idx.as_of`가 오늘 날짜와 다르면 카드에 **"최근거래일"** 배지가 자동으로 붙음
- LLM 호출 실패 시 어제 요약 유지 (지수·환율은 정상 갱신)

## 디렉토리

```
market-close-daily/
├── .github/workflows/daily-update.yml   # cron 2개 + Pages 배포
├── build.py                             # 오케스트레이터
├── summarize.py                         # Claude 호출 + 할루시 가드
├── fetchers/
│   ├── indexes.py                       # 9개 지수
│   ├── fx.py                            # 환율 + DXY
│   ├── commodities.py                   # WTI/Gold/BTC/UST10Y/VIX
│   └── news.py                          # RSS 8개 통합
├── templates/index.html.j2              # 디자인 단일 진실원
├── data/
│   ├── latest.json                      # 폴백 소스 (main에 자동 커밋됨)
│   └── history/YYYY-MM-DD.json          # 매 빌드 스냅샷
├── dist/                                # Pages 아티팩트 (gitignored)
├── legacy/market-close-2026-05-14.html  # 참조용 원본
└── requirements.txt
```

## 운영 팁

- **첫 빌드**가 실패하면 `data/latest.json` 시드를 그대로 렌더하므로 페이지는 뜸. 두 번째 빌드부터 실데이터.
- **DST/주말 cron 검증**: 워크플로 로그 첫 줄에 "KST now: ..."가 찍힘. 첫 1주일은 주기적으로 확인.
- **API 차단**: yfinance는 비공식이므로 가끔 막힐 수 있음. `fetchers/*.py`는 각자 try/except로 격리되어 부분 실패만 발생.
- **수동 백필**: `python build.py --no-llm`을 로컬에서 돌리고 `data/`를 커밋해도 됨.

## 디자인 변경

`templates/index.html.j2` 한 파일만 수정하면 됩니다. 인라인 CSS이므로 외부 자산은 Google Fonts 하나뿐.

## 라이선스 / 면책

본 페이지는 공개 데이터 자동 요약이며 투자 자문이 아닙니다. yfinance / ExchangeRate.host / RSS 출처별 약관을 따릅니다.
