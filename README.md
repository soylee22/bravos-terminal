# Bravos Terminal // Tactical Intelligence HUD

A live automated intelligence feed and portfolio regime terminal scanning Author Nicolas (`author: 21391`) and Bravos Research publications via the WordPress REST API.

Design inspired by the **USAvionix** Awwwards Site of the Day: dark aerospace tactical aesthetic, Geist / Geist Mono typography, high-contrast status readouts, and slide-over article reader.

Live Terminal: https://soylee22.github.io/bravos-terminal/

## Mission Directives & Active Regimes

1. **Equity Model Portfolio (QQQ / TQQQ / Cash)**
   - Pre-computed current regime based on latest model signals.
   - Live asset allocation and execution directives.
2. **Gold Portfolio (GLD / Cash)**
   - 4-tier posture tracking (Cash, Moderate 50/50, Aggressive).
   - Real-time entry/exit alerts.
3. **Trade Alerts Radar**
   - Live ticker tracker for individual equity breakout, breakdown, and profit-booking alerts.
4. **Publication Archive**
   - 377+ indexed publications spanning Signals, Macro Reports, Educational Guides, and Newsletters.
   - Built-in slide-over HUD reader for viewing complete articles with embedded charts.

## Automated Scanner Cadence

The GitHub Actions workflow (`.github/workflows/scanner.yml`) triggers every 2 hours:
1. Queries `/wp-json/wp/v2/posts?author=21391` on `bravosresearch.com`.
2. Ingests any new trade signals, alerts, macro reports, or educational guides.
3. Updates `data.json` and compiles the lightweight `index.html`.
4. Commits and deploys automatically to GitHub Pages.

## Local Running

```bash
# Run scanner locally
python3 scanner.py

# Preview in browser
python3 -m http.server 8000
# Open http://localhost:8000
```
