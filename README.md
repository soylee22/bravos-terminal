# Bravos Terminal // USAvionix Tactical Intelligence

A live automated tactical terminal and regime monitor scanning Author Nicolas (`author: 21391`) and Bravos Research publications via the WordPress REST API.

The visual design reconstructs the **USAvionix** Awwwards Site of the Day: pitch-black background (`#000000`), Geist Sans and Geist Mono typography, 4-track expandable card layout (630px card height, `outline-white/15`), centered chapter ruler navigation, and technical telemetry readouts.

Live Deployment: https://soylee22.github.io/bravos-terminal/

## Tactical Allocation Regimes & Real Instruments

1. **Strategy 01: Equity Model Regime**
   - Active posture: 100% Cash (Defensive)
   - Real UK execution instrument: `CSH2.L` (Lyxor Sterling Overnight Return Treasury MMF)
   - Nasdaq-100 equity exposure: `EQQQ.L` (0%) / `LQQ3.L` (0%)
   - Reference benchmark exit price: $657.53 (QQQ) on 6 November 2026

2. **Strategy 02: Gold Commodity Regime**
   - Active posture: 50% Gold / 50% Cash (Moderate)
   - Real UK execution instruments: `SGLN.L` (iShares Physical Gold ETC) and `CSH2.L` (Cash Treasury)
   - Leveraged instrument: `2BUL.L` (WisdomTree Gold 2x)
   - Reference entry price: $379.10 (GLD) on 9 November 2026

3. **Strategy 03: Joined Positions & Setup**
   - Unified blend combining Equity Model and Gold Strategy
   - Current balanced posture: 75% CSH2 (Cash) + 25% SGLN (Physical Gold)
   - Interactive allocation slider allows dynamic rebalancing between Equity Model and Gold allocations (0% to 100%)

4. **Comparative Time Series Performance**
   - 1-year historical forward testing pulling daily closes from Yahoo Finance
   - Normalised to base 100 on 10 November 2025
   - Benchmark comparison: `Our Portfolio` (+9.4%), `SPY` (+11.4%), `VUAG` (+9.3%), and `EQQQ` (+7.1%)

5. **Intel Archive & Slide-Over Reader**
   - 377 indexed publications spanning Signals, Macro Reports, Educational Guides, and Newsletters
   - Instant search, filter chips, and slide-over telemetry reader drawer

## Automated Outside Scanner Cadence

The GitHub Actions workflow (`.github/workflows/scanner.yml`) runs independently every two hours:
1. Installs Python dependencies (`beautifulsoup4`, `yfinance`).
2. Fetches 1-year market series and live quotes for all five execution instruments.
3. Ingests any new publications from `bravosresearch.com`.
4. Rebuilds `data.json` and compiles static `index.html`.
5. Commits and redeploys to GitHub Pages automatically.

## Local Execution

```bash
# Run scanner locally
python3 scanner.py

# Preview in browser
python3 -m http.server 8000
# Open http://localhost:8000
```
