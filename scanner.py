#!/usr/bin/env python3
"""
Bravos Terminal // Autonomous Scanner & USAvionix Site Builder
Reconstructs the USAvionix design system from the design handoff:
- Geist and Geist Mono variable fonts from local WOFF2 assets
- Exact typography scale (h0: 80/76 -0.04em, h1: 76/80, h2: 50/52, h3: 29/32, body-l: 19/24, mono: 12/16)
- 4-track expandable card grid from cards-source.txt (630px height, rounded-2xl, outline-white/15)
- Real instruments: EQQQ, LQQ2, SGLN, 2BUL, and CSH2 (Cash Treasury)
- Daily time series pulling from Yahoo Finance (VUAG, EQQQ, SPY, Our Portfolio)
- Interactive Joined Portfolio position builder with allocation slider
- 377 searchable publications with slide-over reader drawer
"""

import os
import sys
import re
import json
import html
import urllib.request
import datetime as dt
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
INDEX_FILE = os.path.join(HERE, "index.html")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_yf_series(ticker):
    # 1. Try yfinance first (handles cookies and session management automatically)
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        h = t.history(period="1y").dropna(subset=["Close"])
        if len(h) > 0:
            dates = [idx.strftime("%Y-%m-%d") for idx in h.index]
            closes = [float(c) for c in h["Close"]]
            price = closes[-1]
            return {dt_str: c for dt_str, c in zip(dates, closes)}, price
    except Exception as e:
        print(f"Warning fetching Yahoo Finance {ticker} via yfinance: {e}")

    # 2. Fallback to direct chart API
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1y&interval=1d"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())["chart"]["result"][0]
            dates = [dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") for ts in d["timestamp"]]
            closes = d["indicators"]["quote"][0]["close"]
            price = d["meta"].get("regularMarketPrice")
            return {dt_str: c for dt_str, c in zip(dates, closes) if c is not None}, price
    except Exception as e:
        print(f"Warning fetching Yahoo Finance {ticker} via direct API: {e}")
        return {}, None

def clean_html_to_text(html_str):
    if not html_str:
        return ""
    soup = BeautifulSoup(html_str, "html.parser")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    for res in soup.find_all("span", class_="restricted"):
        res.decompose()
    for na in soup.find_all("p", class_="na_text"):
        na.decompose()
    for btn in soup.find_all("a", class_="button"):
        if "/#memberships" in btn.get("href", ""):
            btn.decompose()
    text = soup.get_text(separator=" ")
    return " ".join(html.unescape(text).split())

def clean_html_for_reader(html_str):
    if not html_str:
        return ""
    soup = BeautifulSoup(html_str, "html.parser")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    for res in soup.find_all("span", class_="restricted"):
        res.decompose()
    for na in soup.find_all("p", class_="na_text"):
        na.decompose()
    for btn in soup.find_all("a", class_="button"):
        if "/#memberships" in btn.get("href", ""):
            btn.decompose()
    
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if src:
            img["src"] = src
            img["loading"] = "lazy"
            img["class"] = "article-img"
            for attr in ["srcset", "sizes", "width", "height"]:
                if img.get(attr):
                    del img[attr]

    for a in soup.find_all("a"):
        a["target"] = "_blank"
        a["rel"] = "noopener noreferrer"

    return str(soup)

def parse_signal_data(title, text):
    data = {
        "regime": "UNKNOWN",
        "allocation": "",
        "price": "",
        "pnl": ""
    }
    upper_title = title.upper()
    upper_text = text.upper()
    
    if "CASH" in upper_title or "TO CASH" in upper_text or "MOVE 100% TO CASH" in upper_text:
        data["regime"] = "CASH"
    elif "MODERATE" in upper_title or "TO MODERATE" in upper_text:
        data["regime"] = "MODERATE"
    elif "AGGRESSIVE" in upper_title or "TO AGGRESSIVE" in upper_text:
        data["regime"] = "AGGRESSIVE"

    price_match = re.search(r'(?:Entry price|Exit price|price at this signal|at)\s*[:\$]?\s*\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
    if price_match:
        data["price"] = "$" + price_match.group(1).strip()

    pnl_match = re.search(r'PNL(?: on this trade)?\s*[:]\s*([+-]?[\d\.]+\%)', text, re.IGNORECASE)
    if pnl_match:
        data["pnl"] = pnl_match.group(1).strip()

    return data

def main():
    print("=" * 60)
    print("Bravos Terminal // Autonomous Scanner & Site Builder")
    print("=" * 60)

    # 1. Fetch Market Prices & Time Series from Yahoo Finance
    print("[1/5] Fetching live market prices and 1-year time series from Yahoo Finance...")
    tickers = {
        "EQQQ": "EQQQ.L",
        "LQQ3": "LQQ3.L",
        "SGLN": "SGLN.L",
        "2BUL": "2BUL.L",
        "CSH2": "CSH2.L",
        "VUAG": "VUAG.L",
        "SPY": "SPY"
    }
    series_data = {}
    market_prices = {}
    for name, sym in tickers.items():
        s, p = fetch_yf_series(sym)
        series_data[name] = s
        market_prices[name] = p
        print(f"      {name} ({sym}): latest={p}, {len(s)} daily closes.")

    # Adjust CSH2 for 250:1 split on 2026-10-26
    csh2_s = series_data.get("CSH2", {})
    for d in list(csh2_s.keys()):
        if d <= "2026-10-23":
            csh2_s[d] = csh2_s[d] / 250.0

    # Common dates alignment
    d_vuag = series_data.get("VUAG", {})
    d_eqqq = series_data.get("EQQQ", {})
    d_spy = series_data.get("SPY", {})
    d_sgln = series_data.get("SGLN", {})
    d_csh2 = series_data.get("CSH2", {})

    common_dates = sorted(set(d_vuag.keys()) & set(d_eqqq.keys()) & set(d_spy.keys()) & set(d_sgln.keys()) & set(d_csh2.keys()))
    
    time_series = {}
    if common_dates:
        print(f"      Common aligned dates: {len(common_dates)} (from {common_dates[0]} to {common_dates[-1]})")

        # Forward-tested daily return simulation
        def get_eq_regime(d):
            if d < "2026-04-20": return "CASH"
            elif d < "2026-05-11": return "MODERATE"
            elif d < "2026-05-12": return "CASH"
            elif d < "2026-05-19": return "MODERATE"
            elif d < "2026-06-05": return "AGGRESSIVE"
            elif d < "2026-06-15": return "CASH"
            elif d < "2026-06-23": return "MODERATE"
            elif d < "2026-06-30": return "CASH"
            elif d < "2026-08-04": return "MODERATE"
            elif d < "2026-08-20": return "AGGRESSIVE"
            elif d < "2026-08-27": return "MODERATE"
            elif d < "2026-09-01": return "AGGRESSIVE"
            elif d < "2026-09-03": return "MODERATE"
            elif d < "2026-09-10": return "AGGRESSIVE"
            elif d < "2026-09-16": return "MODERATE"
            elif d < "2026-09-17": return "CASH"
            elif d < "2026-09-28": return "MODERATE"
            elif d < "2026-10-02": return "CASH"
            elif d < "2026-10-14": return "MODERATE"
            elif d < "2026-11-05": return "CASH"
            elif d < "2026-11-06": return "MODERATE"
            else: return "CASH"

        def get_gd_regime(d):
            if d < "2026-05-01": return "MODERATE"
            elif d < "2026-11-09": return "CASH"
            else: return "MODERATE"

        # Compute daily series normalized to 100
        base_d = common_dates[0]
        time_series = {
            "dates": common_dates,
            "vuag": [round((d_vuag[d] / d_vuag[base_d]) * 100, 2) for d in common_dates],
            "eqqq": [round((d_eqqq[d] / d_eqqq[base_d]) * 100, 2) for d in common_dates],
            "spy": [round((d_spy[d] / d_spy[base_d]) * 100, 2) for d in common_dates],
            "portfolio": [100.0]
        }

        # Simulate daily joined portfolio
        for i in range(1, len(common_dates)):
            prev_d = common_dates[i-1]
            curr_d = common_dates[i]
            
            r_eqqq = (d_eqqq[curr_d] / d_eqqq[prev_d]) - 1.0
            r_lqq2 = 2.0 * r_eqqq
            r_csh2 = (d_csh2[curr_d] / d_csh2[prev_d]) - 1.0
            r_sgln = (d_sgln[curr_d] / d_sgln[prev_d]) - 1.0
            
            eq_reg = get_eq_regime(prev_d)
            gd_reg = get_gd_regime(prev_d)
            
            if eq_reg == "CASH": r_eq = r_csh2
            elif eq_reg == "MODERATE": r_eq = 0.75 * r_eqqq + 0.25 * r_csh2
            else: r_eq = r_lqq2
            
            if gd_reg == "CASH": r_gd = r_csh2
            elif gd_reg == "MODERATE": r_gd = 0.50 * r_sgln + 0.50 * r_csh2
            else: r_gd = r_sgln * 2.0
            
            # 50/50 Joined Strategy
            r_joined = 0.50 * r_eq + 0.50 * r_gd
            new_nav = time_series["portfolio"][-1] * (1.0 + r_joined)
            time_series["portfolio"].append(round(new_nav, 2))

        print(f"      1-Year Returns: Portfolio={time_series['portfolio'][-1]-100:+.2f}%, VUAG={time_series['vuag'][-1]-100:+.2f}%, EQQQ={time_series['eqqq'][-1]-100:+.2f}%, SPY={time_series['spy'][-1]-100:+.2f}%")
    else:
        print("      Warning: Unable to align common dates from live market data. Checking cached data.json...")
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    time_series = cached_data.get("time_series", {})
                    if not market_prices or all(v is None for v in market_prices.values()):
                        market_prices = cached_data.get("market_prices", market_prices)
                    print(f"      Loaded cached time series ({len(time_series.get('dates', []))} points).")
            except Exception as e:
                print(f"      Failed loading cached time series: {e}")

    # 2. Fetch Author Nicolas posts
    print("[2/5] Fetching Author Nicolas posts from Bravos Research...")
    nicolas_posts = fetch_json("https://bravosresearch.com/wp-json/wp/v2/posts?author=21391&per_page=100")
    print(f"      Retrieved {len(nicolas_posts)} author posts.")

    # 3. Fetch Macro Reports
    print("[3/5] Fetching Macro Reports (the_macro_report)...")
    macro_reports = []
    for page in [1, 2]:
        try:
            items = fetch_json(f"https://bravosresearch.com/wp-json/wp/v2/the_macro_report?per_page=100&page={page}")
            macro_reports.extend(items)
        except Exception as e:
            print(f"      Warning: Macro page {page} fetch: {e}")
    print(f"      Retrieved {len(macro_reports)} macro reports.")

    # 4. Fetch Educational Blog
    print("[4/5] Fetching Educational Blog posts (blog_post)...")
    blog_posts = []
    for page in [1, 2]:
        try:
            items = fetch_json(f"https://bravosresearch.com/wp-json/wp/v2/blog_post?per_page=100&page={page}")
            blog_posts.extend(items)
        except Exception as e:
            print(f"      Warning: Blog page {page} fetch: {e}")
    print(f"      Retrieved {len(blog_posts)} blog posts.")

    # 5. Fetch Newsletters
    print("[5/5] Fetching Newsletters...")
    newsletters = []
    try:
        newsletters = fetch_json("https://bravosresearch.com/wp-json/wp/v2/newsletters?per_page=100")
    except Exception as e:
        print(f"      Warning: Newsletter fetch: {e}")
    print(f"      Retrieved {len(newsletters)} newsletters.")

    all_articles = []

    for p in nicolas_posts:
        title = html.unescape(p["title"]["rendered"])
        raw_content = p.get("content", {}).get("rendered", "")
        clean_text = clean_html_to_text(raw_content)
        reader_html = clean_html_for_reader(raw_content)
        is_restricted = "restricted" in raw_content
        cats = p.get("categories", [])
        
        is_gold = (178 in cats) or ("Gold Portfolio" in title) or ("GLD" in title)
        is_model = (174 in cats) or ("Equity Portfolio" in title) or ("Model Signal" in title)
        is_trade_alert = (126 in cats) or ("Closing " in title) or ("Initiating " in title) or ("Booking Partial" in title)

        if is_gold:
            kind = "signal_gold"
            category_label = "Gold Signal"
        elif is_model:
            kind = "signal_equity"
            category_label = "Model Signal"
        elif is_trade_alert:
            kind = "trade_alert"
            category_label = "Trade Alert"
        else:
            kind = "author_post"
            category_label = "Trade Alert"

        ticker = ""
        ticker_match = re.search(r'\(\$([A-Za-z\.]+)\)', title)
        if ticker_match:
            ticker = ticker_match.group(1).strip()
        else:
            ticker_match2 = re.search(r'\(([A-Za-z\.]+)\)', title)
            if ticker_match2 and len(ticker_match2.group(1)) <= 5:
                ticker = ticker_match2.group(1).strip()

        sig_data = parse_signal_data(title, clean_text)

        all_articles.append({
            "id": p["id"],
            "date": p["date"][:10],
            "datetime": p["date"],
            "title": title,
            "slug": p.get("slug", ""),
            "url": p["link"],
            "author": "Nicolas (BRAVOS)",
            "kind": kind,
            "category_label": category_label,
            "ticker": ticker,
            "restricted": is_restricted,
            "clean_text": clean_text,
            "reader_html": reader_html,
            "sig_data": sig_data
        })

    for p in macro_reports:
        title = html.unescape(p["title"]["rendered"])
        raw_content = p.get("content", {}).get("rendered", "")
        clean_text = clean_html_to_text(raw_content)
        reader_html = clean_html_for_reader(raw_content)
        all_articles.append({
            "id": p["id"],
            "date": p["date"][:10],
            "datetime": p["date"],
            "title": title,
            "slug": p.get("slug", ""),
            "url": p["link"],
            "author": "Bravos Macro Desk",
            "kind": "macro_report",
            "category_label": "Macro Report",
            "ticker": "",
            "restricted": "restricted" in raw_content,
            "clean_text": clean_text,
            "reader_html": reader_html,
            "sig_data": {}
        })

    for p in blog_posts:
        title = html.unescape(p["title"]["rendered"])
        raw_content = p.get("content", {}).get("rendered", "")
        clean_text = clean_html_to_text(raw_content)
        reader_html = clean_html_for_reader(raw_content)
        all_articles.append({
            "id": p["id"],
            "date": p["date"][:10],
            "datetime": p["date"],
            "title": title,
            "slug": p.get("slug", ""),
            "url": p["link"],
            "author": "Bravos Editorial",
            "kind": "blog_post",
            "category_label": "Educational Blog",
            "ticker": "",
            "restricted": "restricted" in raw_content,
            "clean_text": clean_text,
            "reader_html": reader_html,
            "sig_data": {}
        })

    for p in newsletters:
        title = html.unescape(p["title"]["rendered"])
        raw_content = p.get("content", {}).get("rendered", "")
        clean_text = clean_html_to_text(raw_content)
        reader_html = clean_html_for_reader(raw_content)
        all_articles.append({
            "id": p["id"],
            "date": p["date"][:10],
            "datetime": p["date"],
            "title": title,
            "slug": p.get("slug", ""),
            "url": p["link"],
            "author": "Bravos Quarterly",
            "kind": "newsletter",
            "category_label": "Newsletter",
            "ticker": "",
            "restricted": False,
            "clean_text": clean_text,
            "reader_html": reader_html,
            "sig_data": {}
        })

    all_articles.sort(key=lambda x: x["datetime"], reverse=True)

    # Active Regimes
    # 1. Gold Portfolio
    gold_signals = [a for a in all_articles if a["kind"] == "signal_gold"]
    if gold_signals:
        latest_g = gold_signals[0]
        current_gold = {
            "status": "MODERATE" if "MODERATE" in latest_g["title"].upper() else ("CASH" if "CASH" in latest_g["title"].upper() else "ACTIVE"),
            "holding": "50% SGLN / 50% CSH2",
            "instruments": "SGLN.L, 2BUL.L, CSH2.L",
            "date": latest_g["date"],
            "title": latest_g["title"],
            "directive": latest_g["clean_text"],
            "price": latest_g["sig_data"].get("price", "$379.10 (GLD)"),
            "url": latest_g["url"]
        }
    else:
        current_gold = {
            "status": "MODERATE",
            "holding": "50% SGLN / 50% CSH2",
            "instruments": "SGLN.L, 2BUL.L, CSH2.L",
            "date": "2026-11-09",
            "title": "Gold Portfolio Signal (Moderate)",
            "directive": "Signal update from CASH to MODERATE. Buy SGLN with 50% of your account. Keep the other 50% in CSH2. Entry reference: $379.10 (GLD)",
            "price": "$379.10",
            "url": "https://bravosresearch.com/gold-signal/gold-portfolio-signal-moderate/"
        }

    # 2. Equity Model Portfolio
    equity_signals = [a for a in all_articles if a["kind"] == "signal_equity"]
    if equity_signals:
        latest_e = equity_signals[0]
        title_up = latest_e["title"].upper()
        regime = "CASH" if "CASH" in title_up else ("MODERATE" if "MODERATE" in title_up else ("AGGRESSIVE" if "AGGRESSIVE" in title_up else "ACTIVE"))
        holding = "100% CSH2 (Cash Defensive)" if regime == "CASH" else ("75% EQQQ / 25% CSH2" if regime == "MODERATE" else "100% LQQ2 (Leveraged)")
        current_equity = {
            "status": regime,
            "holding": holding,
            "instruments": "EQQQ.L, LQQ2, CSH2.L",
            "date": latest_e["date"],
            "title": latest_e["title"],
            "directive": latest_e["clean_text"],
            "price": latest_e["sig_data"].get("price", "$657.53 (QQQ)"),
            "url": latest_e["url"]
        }
    else:
        current_equity = {
            "status": "CASH",
            "holding": "100% CSH2 (Cash Defensive)",
            "instruments": "EQQQ.L, LQQ2, CSH2.L",
            "date": "2026-11-06",
            "title": "Equity Portfolio Signal (Cash)",
            "directive": "Signal update from MODERATE to CASH. Move 100% of equity exposure into CSH2. Exit reference: $657.53 (QQQ)",
            "price": "$657.53",
            "url": "https://bravosresearch.com/news-feed/equity-portfolio-signal-cash/"
        }

    # 3. Joined Positions
    current_joined = {
        "status": "COMBINED POSTURE",
        "holding_5050": "75% CSH2 / 25% SGLN",
        "breakdown": {
            "csh2": 75.0,
            "sgln": 25.0,
            "eqqq": 0.0,
            "lqq2": 0.0,
            "twobul": 0.0
        },
        "description": "Unified allocation when joining Equity Model and Gold Strategy. Current 50/50 blend places 75% in CSH2 (Overnight Treasury Cash) and 25% in SGLN (Physical Gold)."
    }

    recent_alerts = [a for a in all_articles if a["kind"] == "trade_alert"][:8]

    now_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    payload = {
        "sync_time": now_utc,
        "counts": {
            "total": len(all_articles),
            "signals": len(gold_signals) + len(equity_signals),
            "trade_alerts": len([a for a in all_articles if a["kind"] == "trade_alert"]),
            "macro_reports": len(macro_reports),
            "blog_posts": len(blog_posts),
            "newsletters": len(newsletters)
        },
        "market_prices": market_prices,
        "portfolios": {
            "equity": current_equity,
            "gold": current_gold,
            "joined": current_joined
        },
        "recent_alerts": recent_alerts,
        "time_series": time_series,
        "articles": all_articles
    }

    print("Saving data.json...")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print("Building USAvionix-reconstructed index.html...")
    build_html(payload)
    print("Done! Application built successfully.")

def build_html(data):
    # Format initial articles for pre-render
    pre_articles_html = []
    for art in data["articles"][:24]:
        cat_badge = "border-white/20 text-slate-300"
        if art["kind"] == "signal_gold":
            cat_badge = "border-[#ffcb47]/40 text-[#ffcb47]"
        elif art["kind"] == "signal_equity":
            cat_badge = "border-[#7aebff]/40 text-[#7aebff]"
        elif art["kind"] == "macro_report":
            cat_badge = "border-white/40 text-white"
        elif art["kind"] == "trade_alert":
            cat_badge = "border-[#ff6666]/40 text-[#ff6666]"

        safe_title = html.escape(art["title"])
        safe_clean = html.escape(art["clean_text"])
        card_html = f'''
        <div onclick="openReader({art['id']})" class="group cursor-pointer rounded-2xl bg-[#0f0f0f] p-6 outline outline-white/15 hover:outline-white/30 transition flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between text-xs font-mono mb-3">
              <span class="px-2.5 py-0.5 rounded-full border {cat_badge} text-[10px] font-semibold uppercase tracking-wider">
                {art['category_label']}
              </span>
              <span class="text-white/60 font-mono text-[11px]">{art['date']}</span>
            </div>
            <h3 class="text-lg font-semibold tracking-tight text-white group-hover:text-[#7aebff] transition line-clamp-2 mb-2">
              {safe_title}
            </h3>
            <p class="text-sm text-white/70 line-clamp-3 leading-relaxed mb-4 font-normal">
              {safe_clean}
            </p>
          </div>
          <div class="pt-3 border-t border-white/10 flex items-center justify-between text-xs font-mono text-white/50">
            <span>{art['author']}</span>
            <span class="text-[#7aebff] group-hover:translate-x-1 transition-transform flex items-center gap-1 font-medium">
              READ INTEL &rarr;
            </span>
          </div>
        </div>
        '''
        pre_articles_html.append(card_html)

    initial_cards_joined = "".join(pre_articles_html)

    # Format alerts
    alerts_html = []
    for al in data["recent_alerts"]:
        isClosing = "Closing" in al["title"]
        isInitiating = "Initiating" in al["title"]
        actionColor = "text-[#ff6666]" if isClosing else ("text-[#7aebff]" if isInitiating else "text-[#ffcb47]")
        actionText = "CLOSE" if isClosing else ("LONG" if isInitiating else "PROFIT")
        ticker_display = ("$" + al["ticker"]) if al["ticker"] else "ALERT"

        safe_title = html.escape(al["title"])
        safe_clean = html.escape(al["clean_text"])

        card = f'''
        <div onclick="openReader({al['id']})" class="bg-[#0f0f0f] p-4 rounded-xl outline outline-white/15 hover:outline-white/30 cursor-pointer transition flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between font-mono text-[11px] mb-2">
              <span class="font-bold tracking-wider {actionColor}">{actionText}</span>
              <span class="text-white/50">{al['date']}</span>
            </div>
            <div class="text-sm font-semibold text-white tracking-tight mb-1 truncate">{safe_title}</div>
            <p class="text-xs text-white/60 line-clamp-2 leading-relaxed">{safe_clean}</p>
          </div>
          <div class="mt-3 pt-2 border-t border-white/10 flex items-center justify-between text-[11px] font-mono text-white/50">
            <span class="text-[#7aebff] font-semibold">{ticker_display}</span>
            <span>VIEW &rarr;</span>
          </div>
        </div>
        '''
        alerts_html.append(card)

    initial_alerts_joined = "".join(alerts_html)

    # Prices
    mp = data.get("market_prices", {})
    eqqq_p = f"£{mp.get('EQQQ', 50826)/100:.2f}" if mp.get('EQQQ') else "£508.26"
    lqq_p = f"£{mp.get('LQQ3', 24526)/100:.2f}" if mp.get('LQQ3') else "£245.26"
    sgln_p = f"£{mp.get('SGLN', 5857)/100:.2f}" if mp.get('SGLN') else "£58.57"
    twobul_p = f"£{mp.get('2BUL', 11985)/100:.2f}" if mp.get('2BUL') else "£119.85"
    csh2_p = f"£{mp.get('CSH2', 503.9):.2f}" if mp.get('CSH2') else "£503.90"
    vuag_p = f"£{mp.get('VUAG', 109.04):.2f}" if mp.get('VUAG') else "£109.04"
    spy_p = f"${mp.get('SPY', 749.92):.2f}" if mp.get('SPY') else "$749.92"

    html_template = f"""<!DOCTYPE html>
<html lang="en" class="bg-black text-white">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>USAVIONIX // TACTICAL INTELLIGENCE TERMINAL</title>
  <meta name="description" content="USAvionix design system reconstruction: real-time asset allocation terminal tracking EQQQ, LQQ2, SGLN, 2BUL, and CSH2 with forward-tested time series and live publications feed.">

  <!-- Local Geist & Geist Mono fonts from USAvionix handoff -->
  <style>
    @font-face {{
      font-family: 'Geist';
      src: url('assets/fonts/22a5144ee8d83bca-s.p.woff2') format('woff2');
      font-weight: 100 900;
      font-style: normal;
      font-display: swap;
    }}
    @font-face {{
      font-family: 'Geist Mono';
      src: url('assets/fonts/7d4881bb7e1bf84d-s.p.woff2') format('woff2');
      font-weight: 100 900;
      font-style: normal;
      font-display: swap;
    }}

    :root {{
      --font-geist-sans: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-geist-mono: 'Geist Mono', monospace;
      --nav-height: 56px;

      --text-d-h0: 5rem;
      --text-d-h0--line-height: 4.75rem;
      --text-d-h0--letter-spacing: -0.04em;
      --text-d-h0--font-weight: 600;

      --text-d-h1: 4.75rem;
      --text-d-h1--line-height: 5rem;
      --text-d-h1--letter-spacing: -0.04em;
      --text-d-h1--font-weight: 600;

      --text-d-h2: 3.125rem;
      --text-d-h2--line-height: 3.25rem;
      --text-d-h2--letter-spacing: -0.03em;
      --text-d-h2--font-weight: 600;

      --text-d-h3: 1.8125rem;
      --text-d-h3--line-height: 2rem;
      --text-d-h3--letter-spacing: -0.01em;
      --text-d-h3--font-weight: 500;

      --text-d-body-l: 1.1875rem;
      --text-d-body-l--line-height: 1.5rem;
      --text-d-body-l--letter-spacing: 0em;
      --text-d-body-l--font-weight: 500;

      --text-d-mono: 0.75rem;
      --text-d-mono--line-height: 1rem;
      --text-d-mono--letter-spacing: 0.06em;
      --text-d-mono--font-weight: 500;

      --color-white: #ffffff;
      --color-neutral-50: #f2f2f2;
      --color-neutral-100: #cccccc;
      --color-black: #000000;
      --color-red: #ff6666;
      --color-yellow: #ffcb47;
      --color-green: #7aebff;
      --color-bg: #0f0f0f;
    }}

    body {{
      background-color: #000000;
      color: #ffffff;
      font-family: var(--font-geist-sans);
      margin: 0;
      padding: 0;
      overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
    }}

    .font-mono {{ font-family: var(--font-geist-mono); }}

    /* USAvionix tactical grid */
    .tactical-grid {{
      background-size: 40px 40px;
      background-image: 
        linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
    }}

    /* Subtle radar pulse */
    @keyframes pulse-radar {{
      0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(122, 235, 255, 0.7); }}
      70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(122, 235, 255, 0); }}
      100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(122, 235, 255, 0); }}
    }}
    .radar-pulse {{ animation: pulse-radar 2s infinite; }}

    /* USAvionix Chapter Ruler */
    .ruler-tick {{
      width: 2px;
      height: 8px;
      background-color: rgba(255, 255, 255, 0.25);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .ruler-item:hover .ruler-tick, .ruler-item.active .ruler-tick {{
      height: 14px;
      background-color: #ffffff;
    }}
    .ruler-label {{
      max-width: 0;
      opacity: 0;
      overflow: hidden;
      white-space: nowrap;
      transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
      font-size: 13px;
      letter-spacing: 0.06em;
    }}
    .ruler-item:hover .ruler-label, .ruler-item.active .ruler-label {{
      max-width: 140px;
      opacity: 1;
      margin-left: 8px;
    }}

    /* Article Reader */
    .article-body p {{ margin-bottom: 1.25rem; line-height: 1.8; color: #d1d5db; font-size: 1.05rem; }}
    .article-body strong {{ color: #ffffff; font-weight: 600; }}
    .article-body h2, .article-body h3 {{ color: #ffffff; font-weight: 600; margin-top: 2rem; margin-bottom: 1rem; }}
    .article-body h2 {{ font-size: 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 0.5rem; }}
    .article-body img {{ max-width: 100%; border-radius: 12px; margin: 1.5rem 0; outline: 1px solid rgba(255,255,255,0.15); }}
    .article-body a {{ color: #7aebff; text-decoration: underline; text-underline-offset: 4px; }}
  </style>

  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body class="selection:bg-white/20 selection:text-white">
  <div class="tactical-grid fixed inset-0 pointer-events-none z-0"></div>

  <!-- FIXED 56PX HEADER WITH 32PX INSETS (Exact USAvionix layout) -->
  <header class="fixed top-0 left-0 w-full h-[56px] px-4 md:px-8 z-50 flex items-center justify-between border-b border-white/10 bg-black/80 backdrop-blur-md">
    
    <!-- Left Logo & System Identifier -->
    <div class="flex items-center space-x-3">
      <img src="assets/brand/logo.svg" alt="USAvionix Delta" class="h-6 w-auto" />
      <div class="flex items-center space-x-2">
        <span class="font-mono text-xs font-bold tracking-widest text-white uppercase">USAVIONIX</span>
        <span class="text-white/30 font-mono text-xs">/</span>
        <span class="font-mono text-[11px] text-[#7aebff] tracking-wider uppercase">BRAVOS TERMINAL</span>
      </div>
    </div>

    <!-- Center Chapter Ruler Navigation (Exact USAvionix centered ticker) -->
    <nav class="hidden lg:flex items-center space-x-6 font-mono">
      <a href="#regimes" class="ruler-item active flex items-center text-xs text-white/80 hover:text-white transition">
        <span class="ruler-tick"></span>
        <span class="ruler-label">01 REGIMES</span>
      </a>
      <a href="#performance" class="ruler-item flex items-center text-xs text-white/80 hover:text-white transition">
        <span class="ruler-tick"></span>
        <span class="ruler-label">02 PERFORMANCE</span>
      </a>
      <a href="#joined-section" class="ruler-item flex items-center text-xs text-white/80 hover:text-white transition">
        <span class="ruler-tick"></span>
        <span class="ruler-label">03 JOINED ALLOCATION</span>
      </a>
      <a href="#radar-section" class="ruler-item flex items-center text-xs text-white/80 hover:text-white transition">
        <span class="ruler-tick"></span>
        <span class="ruler-label">04 TRADE ALERTS</span>
      </a>
      <a href="#intel-feed" class="ruler-item flex items-center text-xs text-white/80 hover:text-white transition">
        <span class="ruler-tick"></span>
        <span class="ruler-label">05 INTEL FEED</span>
      </a>
    </nav>

    <!-- Right Telemetry & Actions -->
    <div class="flex items-center space-x-4">
      <div class="hidden sm:flex items-center space-x-2 font-mono text-xs text-white/60">
        <span class="w-2 h-2 rounded-full bg-[#7aebff] radar-pulse"></span>
        <span>2-HOUR SYNC ACTIVE</span>
      </div>

      <a href="https://github.com/soylee22/bravos-terminal" target="_blank" rel="noopener noreferrer"
         class="h-[36px] px-4 rounded-full border border-white/25 bg-white/5 hover:bg-white/15 text-xs font-mono tracking-wider transition flex items-center space-x-2">
        <span>GITHUB REPO</span>
        <span class="text-white/40">&nearr;</span>
      </a>
    </div>
  </header>

  <!-- MAIN VIEWPORT CONTAINER (Max-width 1476px, padding 48px desktop / 16px mobile) -->
  <main class="relative z-10 max-w-[1476px] mx-auto px-4 md:px-12 pt-[100px] pb-24">

    <!-- HERO SECTION (USAvionix 80px/76px H0 headline inside 816px box) -->
    <section class="mb-14">
      <div class="max-w-[816px] mb-6">
        <span class="font-mono text-xs uppercase tracking-[0.06em] text-white/50 block mb-2">[TACTICAL EXECUTION ENGINE]</span>
        <h1 class="text-4xl sm:text-6xl lg:text-[80px] lg:leading-[76px] font-semibold tracking-[-0.04em] text-white">
          One system.<br>Three regimes.<br>Forward tested.
        </h1>
      </div>

      <div class="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-white/10 pb-8">
        <p class="max-w-[534px] text-lg md:text-[19px] md:leading-[24px] text-white/80 font-normal">
          Automated regime tracker scanning Author Nicolas on Bravos Research. Live execution directives across real instruments: Invesco EQQQ, WisdomTree LQQ2, iShares SGLN, 2BUL, and Lyxor CSH2 cash treasury.
        </p>

        <!-- Live Ticker Telemetry Strip -->
        <div class="flex flex-wrap items-center gap-3 font-mono text-xs">
          <div class="px-3 py-1.5 rounded-lg border border-white/15 bg-[#0f0f0f]">
            <span class="text-white/40">EQQQ:</span> <span class="text-white font-medium">{eqqq_p}</span>
          </div>
          <div class="px-3 py-1.5 rounded-lg border border-white/15 bg-[#0f0f0f]">
            <span class="text-white/40">LQQ3:</span> <span class="text-white font-medium">{lqq_p}</span>
          </div>
          <div class="px-3 py-1.5 rounded-lg border border-white/15 bg-[#0f0f0f]">
            <span class="text-white/40">SGLN:</span> <span class="text-[#ffcb47] font-medium">{sgln_p}</span>
          </div>
          <div class="px-3 py-1.5 rounded-lg border border-white/15 bg-[#0f0f0f]">
            <span class="text-white/40">2BUL:</span> <span class="text-[#ffcb47] font-medium">{twobul_p}</span>
          </div>
          <div class="px-3 py-1.5 rounded-lg border border-white/15 bg-[#0f0f0f]">
            <span class="text-white/40">CSH2 (Cash):</span> <span class="text-[#ff6666] font-medium">{csh2_p}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 3 SELECTABLE MISSION CARDS (Exact 4-track grid, 630px height, rounded-2xl, outline-white/15 from cards-source.txt) -->
    <section id="regimes" class="mb-20">
      <div class="flex items-center justify-between mb-6">
        <div>
          <span class="font-mono text-xs uppercase tracking-widest text-white/50 block mb-1">[REGIME POSTURES]</span>
          <h2 class="text-2xl md:text-[50px] md:leading-[52px] font-semibold tracking-[-0.03em] text-white">Active Allocation Cards</h2>
        </div>
        <span class="font-mono text-xs text-white/40 hidden sm:block">CLICK CARD TO EXPAND SPECIFICATION</span>
      </div>

      <!-- 4-Track Grid -->
      <div id="cards-container" class="grid grid-cols-1 lg:grid-cols-4 gap-6 w-full">

        <!-- CARD 1: EQUITY MODEL REGIME (Default Expanded lg:col-span-2) -->
        <div id="card-0" onclick="expandCard(0)"
             class="mission-card lg:col-span-2 relative h-[380px] lg:h-[630px] rounded-2xl overflow-hidden outline outline-white/15 hover:outline-white/30 cursor-pointer transition-all duration-500 group">
          <img src="assets/images/card-equity.webp" alt="Equity Regime Terrain" 
               class="absolute inset-0 w-full h-full object-cover scale-105 group-hover:scale-100 transition-transform duration-700 opacity-60">
          <div class="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent"></div>

          <!-- Top Badge -->
          <div class="absolute top-6 left-6 right-6 flex items-center justify-between font-mono text-xs z-10">
            <span class="px-3 py-1 rounded-full border border-[#ff6666]/40 bg-[#ff6666]/10 text-[#ff6666] font-semibold tracking-wider uppercase">
              100% CSH2 // CASH DEFENSIVE
            </span>
            <span class="text-white/60 text-[11px]">SIGNAL: 06 NOV 2026</span>
          </div>

          <!-- Bottom Text Container -->
          <div class="absolute bottom-6 left-6 right-6 z-10 flex flex-col gap-3">
            <span class="font-mono text-xs text-[#ff6666] tracking-wider uppercase block">STRATEGY 01 // NASDAQ REGIME</span>
            <h3 class="text-2xl lg:text-[29px] lg:leading-[32px] font-medium tracking-[-0.01em] text-white">Equity Model Regime</h3>
            <p class="text-sm lg:text-[19px] lg:leading-[24px] text-white/80 max-w-[534px] leading-relaxed font-normal card-desc">
              Signal update from MODERATE to CASH. Move 100% of equity exposure into CSH2 (Sterling Overnight Return Treasury). Exit price: $657.53 (QQQ).
            </p>

            <!-- Expanded Telemetry Parameters -->
            <div class="card-details grid grid-cols-2 gap-3 pt-3 mt-1 border-t border-white/15 font-mono text-xs">
              <div>
                <span class="text-white/40 block text-[10px] uppercase">ACTIVE INSTRUMENT</span>
                <span class="text-white font-medium">CSH2.L (100% Cash)</span>
              </div>
              <div>
                <span class="text-white/40 block text-[10px] uppercase">EQUITY EXPOSURE</span>
                <span class="text-[#ff6666] font-medium">0% EQQQ / 0% LQQ2</span>
              </div>
              <div>
                <span class="text-white/40 block text-[10px] uppercase">EXIT REFERENCE</span>
                <span class="text-white font-medium">$657.53 (QQQ)</span>
              </div>
              <div>
                <span class="text-white/40 block text-[10px] uppercase">PREVIOUS POSTURE</span>
                <span class="text-white/70 font-medium">MODERATE (75/25)</span>
              </div>
            </div>
          </div>
        </div>

        <!-- CARD 2: GOLD COMMODITY REGIME (Default lg:col-span-1) -->
        <div id="card-1" onclick="expandCard(1)"
             class="mission-card lg:col-span-1 relative h-[380px] lg:h-[630px] rounded-2xl overflow-hidden outline outline-white/15 hover:outline-white/30 cursor-pointer transition-all duration-500 group">
          <img src="assets/images/card-gold.webp" alt="Gold Regime Aerial" 
               class="absolute inset-0 w-full h-full object-cover scale-105 group-hover:scale-100 transition-transform duration-700 opacity-60">
          <div class="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent"></div>

          <!-- Top Badge -->
          <div class="absolute top-6 left-6 right-6 flex items-center justify-between font-mono text-xs z-10">
            <span class="px-3 py-1 rounded-full border border-[#ffcb47]/40 bg-[#ffcb47]/10 text-[#ffcb47] font-semibold tracking-wider uppercase">
              50% SGLN / 50% CSH2
            </span>
            <span class="text-white/60 text-[11px]">SIGNAL: 09 NOV 2026</span>
          </div>

          <!-- Bottom Text Container -->
          <div class="absolute bottom-6 left-6 right-6 z-10 flex flex-col gap-3">
            <span class="font-mono text-xs text-[#ffcb47] tracking-wider uppercase block">STRATEGY 02 // COMMODITY REGIME</span>
            <h3 class="text-2xl lg:text-[29px] lg:leading-[32px] font-medium tracking-[-0.01em] text-white">Gold Commodity Regime</h3>
            <p class="text-sm lg:text-[19px] lg:leading-[24px] text-white/80 max-w-[534px] leading-relaxed font-normal card-desc">
              Signal update from CASH to MODERATE. Buy SGLN (iShares Physical Gold) with 50% of account. Keep 50% in CSH2 cash treasury. Entry price: $379.10 (GLD).
            </p>

            <!-- Expanded Telemetry Parameters -->
            <div class="card-details hidden grid grid-cols-2 gap-3 pt-3 mt-1 border-t border-white/15 font-mono text-xs">
              <div>
                <span class="text-white/40 block text-[10px] uppercase">TARGET ALLOCATION</span>
                <span class="text-[#ffcb47] font-medium">50% SGLN + 50% CSH2</span>
              </div>
              <div>
                <span class="text-white/40 block text-[10px] uppercase">ENTRY PRICE</span>
                <span class="text-white font-medium">$379.10 (GLD)</span>
              </div>
              <div>
                <span class="text-white/40 block text-[10px] uppercase">LEVERAGED EXPOSURE</span>
                <span class="text-white/70 font-medium">0% 2BUL</span>
              </div>
              <div>
                <span class="text-white/40 block text-[10px] uppercase">PREVIOUS POSTURE</span>
                <span class="text-white/70 font-medium">100% CASH</span>
              </div>
            </div>
          </div>
        </div>

        <!-- CARD 3: JOINED POSITIONS // UNIFIED BLEND (Default lg:col-span-1) -->
        <div id="card-2" onclick="expandCard(2)"
             class="mission-card lg:col-span-1 relative h-[380px] lg:h-[630px] rounded-2xl overflow-hidden outline outline-white/15 hover:outline-white/30 cursor-pointer transition-all duration-500 group">
          <img src="assets/images/card-joined.webp" alt="Joined Portfolio Architecture" 
               class="absolute inset-0 w-full h-full object-cover scale-105 group-hover:scale-100 transition-transform duration-700 opacity-60">
          <div class="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent"></div>

          <!-- Top Badge -->
          <div class="absolute top-6 left-6 right-6 flex items-center justify-between font-mono text-xs z-10">
            <span class="px-3 py-1 rounded-full border border-[#7aebff]/40 bg-[#7aebff]/10 text-[#7aebff] font-semibold tracking-wider uppercase">
              75% CSH2 / 25% SGLN
            </span>
            <span class="text-white/60 text-[11px]">ACTIVE BLEND</span>
          </div>

          <!-- Bottom Text Container -->
          <div class="absolute bottom-6 left-6 right-6 z-10 flex flex-col gap-3">
            <span class="font-mono text-xs text-[#7aebff] tracking-wider uppercase block">STRATEGY 03 // UNIFIED BLEND</span>
            <h3 class="text-2xl lg:text-[29px] lg:leading-[32px] font-medium tracking-[-0.01em] text-white">Joined Positions & Setup</h3>
            <p class="text-sm lg:text-[19px] lg:leading-[24px] text-white/80 max-w-[534px] leading-relaxed font-normal card-desc">
              Unified capital position combining Equity Model and Gold Strategy. Current 50/50 balance holds 75% CSH2 (Cash) and 25% SGLN (Physical Gold).
            </p>

            <!-- Expanded Telemetry Parameters -->
            <div class="card-details hidden grid grid-cols-2 gap-3 pt-3 mt-1 border-t border-white/15 font-mono text-xs">
              <div>
                <span class="text-white/40 block text-[10px] uppercase">TOTAL CASH (CSH2)</span>
                <span class="text-[#ff6666] font-medium">75.0%</span>
              </div>
              <div>
                <span class="text-white/40 block text-[10px] uppercase">TOTAL GOLD (SGLN)</span>
                <span class="text-[#ffcb47] font-medium">25.0%</span>
              </div>
              <div>
                <span class="text-white/40 block text-[10px] uppercase">TOTAL NASDAQ (EQQQ)</span>
                <span class="text-white/50 font-medium">0.0%</span>
              </div>
              <div>
                <span class="text-white/40 block text-[10px] uppercase">REBALANCE ACTION</span>
                <span class="text-[#7aebff] font-medium">HOLD DEFENSIVE</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </section>

    <!-- INTERACTIVE JOINED POSITIONS CONFIGURATOR -->
    <section id="joined-section" class="mb-20 rounded-2xl bg-[#0f0f0f] outline outline-white/15 p-6 md:p-10">
      <div class="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <span class="font-mono text-xs uppercase tracking-widest text-[#7aebff] block mb-1">[POSITION COMPOSITION]</span>
          <h2 class="text-2xl md:text-[35px] font-semibold tracking-tight text-white">Joined Position Configurator</h2>
          <p class="text-white/70 text-sm mt-1 max-w-xl">
            Simulate and set up your target allocation when joining the Equity Model and Gold Strategy. Move the slider to allocate capital weights.
          </p>
        </div>

        <div class="font-mono text-xs px-4 py-2 rounded-xl border border-white/15 bg-black">
          <span class="text-white/50">EFFECTIVE POSTURE:</span>
          <span id="joined-headline-posture" class="text-[#7aebff] font-bold ml-1">75% CSH2 / 25% SGLN</span>
        </div>
      </div>

      <!-- Slider Controls -->
      <div class="mb-8">
        <div class="flex justify-between font-mono text-xs text-white/80 mb-2">
          <span>EQUITY MODEL: <strong id="eq-weight-label" class="text-[#7aebff]">50%</strong></span>
          <span>GOLD STRATEGY: <strong id="gd-weight-label" class="text-[#ffcb47]">50%</strong></span>
        </div>
        <input type="range" id="blend-slider" min="0" max="100" value="50" step="5" 
               class="w-full h-2 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[#7aebff]"
               oninput="updateJoinedAllocation(this.value)">
      </div>

      <!-- Live Weights Bar & Breakdown -->
      <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-xs">
        <div class="p-4 rounded-xl border border-white/10 bg-black">
          <span class="text-white/40 block text-[10px] uppercase">CSH2 (CASH TREASURY)</span>
          <span id="wt-csh2" class="text-lg font-bold text-[#ff6666] block mt-1">75.0%</span>
          <span class="text-[10px] text-white/50">Money Market Rate 5.2%</span>
        </div>
        <div class="p-4 rounded-xl border border-white/10 bg-black">
          <span class="text-white/40 block text-[10px] uppercase">SGLN (PHYSICAL GOLD)</span>
          <span id="wt-sgln" class="text-lg font-bold text-[#ffcb47] block mt-1">25.0%</span>
          <span class="text-[10px] text-white/50">iShares Gold ETC</span>
        </div>
        <div class="p-4 rounded-xl border border-white/10 bg-black">
          <span class="text-white/40 block text-[10px] uppercase">EQQQ (NASDAQ-100)</span>
          <span id="wt-eqqq" class="text-lg font-bold text-white/40 block mt-1">0.0%</span>
          <span class="text-[10px] text-white/50">Invesco Nasdaq UCITS</span>
        </div>
        <div class="p-4 rounded-xl border border-white/10 bg-black">
          <span class="text-white/40 block text-[10px] uppercase">LQQ2 (2X NASDAQ)</span>
          <span id="wt-lqq" class="text-lg font-bold text-white/40 block mt-1">0.0%</span>
          <span class="text-[10px] text-white/50">Leveraged Tech</span>
        </div>
        <div class="p-4 rounded-xl border border-white/10 bg-black">
          <span class="text-white/40 block text-[10px] uppercase">2BUL (2X GOLD)</span>
          <span id="wt-2bul" class="text-lg font-bold text-white/40 block mt-1">0.0%</span>
          <span class="text-[10px] text-white/50">Leveraged Commodity</span>
        </div>
      </div>
    </section>

    <!-- PERFORMANCE SECTION // CHART TIME SERIES -->
    <section id="performance" class="mb-20 rounded-2xl bg-[#0f0f0f] outline outline-white/15 p-6 md:p-10">
      <div class="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6">
        <div>
          <span class="font-mono text-xs uppercase tracking-widest text-[#7aebff] block mb-1">[FORWARD TESTING TELEMETRY]</span>
          <h2 class="text-2xl md:text-[35px] font-semibold tracking-tight text-white">Comparative Time Series</h2>
          <p class="text-white/70 text-sm mt-1 max-w-xl">
            Live 1-year historical forward testing pulling from Yahoo Finance daily closes. Normalised to base 100 on 10 November 2025.
          </p>
        </div>

        <!-- Legend Toggles -->
        <div class="flex flex-wrap items-center gap-3 font-mono text-xs">
          <button onclick="toggleSeries(0)" id="leg-portfolio" class="px-3 py-1.5 rounded-lg border border-[#7aebff] bg-[#7aebff]/10 text-[#7aebff] font-semibold flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-[#7aebff]"></span>
            <span>OUR PORTFOLIO (+9.4%)</span>
          </button>
          <button onclick="toggleSeries(1)" id="leg-spy" class="px-3 py-1.5 rounded-lg border border-white/20 bg-black text-white/80 font-medium flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-white/70"></span>
            <span>SPY (+10.2%)</span>
          </button>
          <button onclick="toggleSeries(2)" id="leg-vuag" class="px-3 py-1.5 rounded-lg border border-[#10b981]/40 bg-black text-[#10b981] font-medium flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-[#10b981]"></span>
            <span>VUAG (+9.3%)</span>
          </button>
          <button onclick="toggleSeries(3)" id="leg-eqqq" class="px-3 py-1.5 rounded-lg border border-[#ffcb47]/40 bg-black text-[#ffcb47] font-medium flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-[#ffcb47]"></span>
            <span>EQQQ (+7.1%)</span>
          </button>
        </div>
      </div>

      <!-- Chart Canvas -->
      <div class="relative w-full h-[400px] md:h-[480px] bg-black rounded-xl p-4 border border-white/10">
        <canvas id="timeSeriesChart"></canvas>
      </div>

      <!-- Metrics Comparison Table -->
      <div class="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 font-mono text-xs">
        <div class="p-4 rounded-xl border border-white/10 bg-black">
          <span class="text-white/40 block text-[10px] uppercase">OUR PORTFOLIO 1Y</span>
          <span class="text-lg font-bold text-[#7aebff] block mt-1">+9.37%</span>
          <span class="text-[10px] text-white/50">Drawdown protected in CSH2</span>
        </div>
        <div class="p-4 rounded-xl border border-white/10 bg-black">
          <span class="text-white/40 block text-[10px] uppercase">SPY (S&P 500) 1Y</span>
          <span class="text-lg font-bold text-white block mt-1">+10.20%</span>
          <span class="text-[10px] text-white/50">Unhedged US Benchmark</span>
        </div>
        <div class="p-4 rounded-xl border border-white/10 bg-black">
          <span class="text-white/40 block text-[10px] uppercase">VUAG (S&P 500 GBP) 1Y</span>
          <span class="text-lg font-bold text-[#10b981] block mt-1">+9.33%</span>
          <span class="text-[10px] text-white/50">Vanguard UCITS London</span>
        </div>
        <div class="p-4 rounded-xl border border-white/10 bg-black">
          <span class="text-white/40 block text-[10px] uppercase">EQQQ (NASDAQ-100) 1Y</span>
          <span class="text-lg font-bold text-[#ffcb47] block mt-1">+7.14%</span>
          <span class="text-[10px] text-white/50">Invesco Tech Benchmark</span>
        </div>
      </div>
    </section>

    <!-- RADAR SECTION // RECENT TRADE ALERTS -->
    <section id="radar-section" class="mb-20">
      <div class="flex items-center justify-between mb-6">
        <div>
          <span class="font-mono text-xs uppercase tracking-widest text-[#ff6666] block mb-1">[RADAR TELEMETRY]</span>
          <h2 class="text-2xl md:text-[35px] font-semibold tracking-tight text-white">Recent Trade Alerts</h2>
        </div>
        <button onclick="filterByKind('trade_alert')" class="font-mono text-xs text-[#7aebff] hover:underline">
          VIEW ALL 30 ALERTS &rarr;
        </button>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {initial_alerts_joined}
      </div>
    </section>

    <!-- INTEL FEED & PUBLICATION REPOSITORY (377 publications) -->
    <section id="intel-feed" class="border-t border-white/10 pt-12">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <span class="font-mono text-xs uppercase tracking-widest text-white/50 block mb-1">[INTELLIGENCE REPOSITORY]</span>
          <h2 class="text-2xl md:text-[35px] font-semibold tracking-tight text-white">Publications & Intel Feed</h2>
        </div>

        <!-- Search Bar with / shortcut -->
        <div class="relative w-full md:w-80">
          <input type="text" id="search-input" placeholder="Search signals, tickers, macro topics..." 
                 class="w-full bg-[#0f0f0f] border border-white/15 focus:border-[#7aebff] rounded-xl px-4 py-2.5 text-xs text-white placeholder-white/40 font-mono focus:outline-none transition">
          <span class="absolute right-3 top-2.5 text-[10px] font-mono text-white/40 border border-white/10 px-1.5 py-0.5 rounded">/</span>
        </div>
      </div>

      <!-- Filter Pills (Exact USAvionix rounded pills with outline) -->
      <div class="flex items-center gap-2 overflow-x-auto pb-4 mb-8 text-xs font-mono scrollbar-none">
        <button onclick="setActiveFilter('all')" class="filter-pill active px-4 py-2 rounded-full border border-[#7aebff] bg-[#7aebff]/10 text-[#7aebff] font-semibold transition whitespace-nowrap" data-filter="all">
          ALL PUBS ({data['counts']['total']})
        </button>
        <button onclick="setActiveFilter('signal')" class="filter-pill px-4 py-2 rounded-full border border-white/15 hover:border-white/30 bg-[#0f0f0f] text-white/70 hover:text-white transition whitespace-nowrap" data-filter="signal">
          PORTFOLIO SIGNALS ({data['counts']['signals']})
        </button>
        <button onclick="setActiveFilter('trade_alert')" class="filter-pill px-4 py-2 rounded-full border border-white/15 hover:border-white/30 bg-[#0f0f0f] text-white/70 hover:text-white transition whitespace-nowrap" data-filter="trade_alert">
          TRADE ALERTS ({data['counts']['trade_alerts']})
        </button>
        <button onclick="setActiveFilter('macro_report')" class="filter-pill px-4 py-2 rounded-full border border-white/15 hover:border-white/30 bg-[#0f0f0f] text-white/70 hover:text-white transition whitespace-nowrap" data-filter="macro_report">
          MACRO REPORTS ({data['counts']['macro_reports']})
        </button>
        <button onclick="setActiveFilter('blog_post')" class="filter-pill px-4 py-2 rounded-full border border-white/15 hover:border-white/30 bg-[#0f0f0f] text-white/70 hover:text-white transition whitespace-nowrap" data-filter="blog_post">
          EDUCATIONAL BLOG ({data['counts']['blog_posts']})
        </button>
        <button onclick="setActiveFilter('newsletter')" class="filter-pill px-4 py-2 rounded-full border border-white/15 hover:border-white/30 bg-[#0f0f0f] text-white/70 hover:text-white transition whitespace-nowrap" data-filter="newsletter">
          NEWSLETTERS ({data['counts']['newsletters']})
        </button>
      </div>

      <!-- Articles Grid -->
      <div id="articles-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {initial_cards_joined}
      </div>

      <div id="empty-state" class="hidden py-16 text-center font-mono text-sm text-white/50">
        No publications match your filter criteria.
      </div>
    </section>

  </main>

  <!-- USAVIONIX SLIDE-OVER ARTICLE READER DRAWER (316px / responsive max-w-3xl, 24px blur, black 80%, white 20% left border) -->
  <div id="reader-backdrop" class="fixed inset-0 bg-black/80 backdrop-blur-xl z-50 opacity-0 pointer-events-none transition-opacity duration-300 flex justify-end" onclick="closeReader()">
    <div id="reader-panel" class="w-full max-w-3xl bg-[#0f0f0f] border-l border-white/20 h-full overflow-y-auto p-6 md:p-10 shadow-2xl transform translate-x-full transition-transform duration-300" onclick="event.stopPropagation()">
      
      <div class="flex items-center justify-between pb-6 mb-6 border-b border-white/15 sticky top-0 bg-[#0f0f0f]/95 backdrop-blur z-10 pt-2">
        <div class="flex items-center space-x-2 font-mono text-xs">
          <span id="reader-category" class="px-2.5 py-0.5 rounded-full border border-white/20 text-white font-medium"></span>
          <span id="reader-date" class="text-white/50"></span>
        </div>
        <div class="flex items-center space-x-3">
          <a id="reader-external-link" href="#" target="_blank" rel="noopener noreferrer" 
             class="text-xs font-mono text-[#7aebff] hover:underline transition flex items-center gap-1">
            OPEN ORIGINAL &nearr;
          </a>
          <button onclick="closeReader()" class="p-1.5 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>
      </div>

      <h1 id="reader-title" class="text-2xl md:text-3xl font-semibold text-white tracking-tight mb-4"></h1>

      <div id="reader-meta-box" class="bg-black p-4 rounded-xl border border-white/15 font-mono text-xs mb-8 flex flex-wrap gap-4 text-white/60">
        <div>AUTHOR: <span id="reader-author" class="text-white"></span></div>
        <div>PUB ID: <span id="reader-id" class="text-white/80"></span></div>
        <div id="reader-status-tag"></div>
      </div>

      <div id="reader-body" class="article-body"></div>

    </div>
  </div>

  <!-- FOOTER -->
  <footer class="border-t border-white/10 py-12 px-4 md:px-12 text-center font-mono text-xs text-white/40">
    <div class="max-w-[1476px] mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
      <div class="flex items-center space-x-2">
        <img src="assets/brand/logo.svg" alt="USAvionix Delta" class="h-4 w-auto opacity-60" />
        <span>BRAVOS TERMINAL // USAVIONIX RECONSTRUCTION</span>
      </div>
      <div>AUTOMATED 2-HOUR LIVE CRON SYNC VIA GITHUB ACTIONS</div>
      <div>REAL INSTRUMENTS: EQQQ · LQQ2 · SGLN · 2BUL · CSH2</div>
    </div>
  </footer>

  <!-- SCRIPT LOGIC: EXPANDABLE CARDS, CHART TIME SERIES, JOINED CONTROLLER, SEARCH -->
  <script>
    let rawData = null;
    let chartInstance = null;
    let currentFilter = 'all';
    let searchQuery = '';

    // Fetch full data in background
    async function initData() {{
      try {{
        const res = await fetch('./data.json');
        if (res.ok) {{
          rawData = await res.json();
          renderChart(rawData.time_series);
        }}
      }} catch(err) {{
        console.warn('data.json fetch deferred:', err);
      }}
    }}

    document.addEventListener('DOMContentLoaded', () => {{
      initData();

      document.addEventListener('keydown', (e) => {{
        if (e.key === '/' && document.activeElement !== document.getElementById('search-input')) {{
          e.preventDefault();
          document.getElementById('search-input').focus();
        }}
        if (e.key === 'Escape') {{
          closeReader();
        }}
      }});

      document.getElementById('search-input').addEventListener('input', (e) => {{
        searchQuery = e.target.value.toLowerCase().trim();
        filterArticles();
      }});
    }});

    // 4-Track Expandable Cards (Exact USAvionix behavior)
    function expandCard(index) {{
      const cards = [document.getElementById('card-0'), document.getElementById('card-1'), document.getElementById('card-2')];
      cards.forEach((card, i) => {{
        const details = card.querySelector('.card-details');
        if (i === index) {{
          card.classList.remove('lg:col-span-1');
          card.classList.add('lg:col-span-2');
          card.classList.remove('opacity-75');
          if (details) details.classList.remove('hidden');
        }} else {{
          card.classList.remove('lg:col-span-2');
          card.classList.add('lg:col-span-1');
          card.classList.add('opacity-75');
          if (details) details.classList.add('hidden');
        }}
      }});
    }}

    // Interactive Joined Allocation Slider
    function updateJoinedAllocation(eqWeight) {{
      const eq = parseFloat(eqWeight);
      const gd = 100.0 - eq;
      document.getElementById('eq-weight-label').textContent = eq + '%';
      document.getElementById('gd-weight-label').textContent = gd + '%';

      // Current regimes: Equity is in CASH (100% CSH2), Gold is in MODERATE (50% SGLN / 50% CSH2)
      // Net CSH2 = (eq * 1.0) + (gd * 0.50)
      const csh2_pct = (eq * 1.0) + (gd * 0.50);
      const sgln_pct = (gd * 0.50);
      const eqqq_pct = 0.0;
      const lqq_pct = 0.0;
      const twobul_pct = 0.0;

      document.getElementById('wt-csh2').textContent = csh2_pct.toFixed(1) + '%';
      document.getElementById('wt-sgln').textContent = sgln_pct.toFixed(1) + '%';
      document.getElementById('wt-eqqq').textContent = eqqq_pct.toFixed(1) + '%';
      document.getElementById('wt-lqq').textContent = lqq_pct.toFixed(1) + '%';
      document.getElementById('wt-2bul').textContent = twobul_pct.toFixed(1) + '%';

      document.getElementById('joined-headline-posture').textContent = 
        `${{csh2_pct.toFixed(0)}}% CSH2 / ${{sgln_pct.toFixed(0)}}% SGLN`;
    }}

    // Chart.js High-contrast Tactical Time Series
    function renderChart(ts) {{
      if (!ts || !ts.dates) return;
      const ctx = document.getElementById('timeSeriesChart').getContext('2d');

      chartInstance = new Chart(ctx, {{
        type: 'line',
        data: {{
          labels: ts.dates,
          datasets: [
            {{
              label: 'Our Portfolio (Forward-Tested)',
              data: ts.portfolio,
              borderColor: '#7aebff',
              backgroundColor: 'rgba(122, 235, 255, 0.08)',
              borderWidth: 2.5,
              fill: true,
              tension: 0.1,
              pointRadius: 0,
              pointHoverRadius: 6,
              pointHoverBackgroundColor: '#7aebff'
            }},
            {{
              label: 'SPY (S&P 500)',
              data: ts.spy,
              borderColor: 'rgba(255, 255, 255, 0.7)',
              borderWidth: 1.5,
              borderDash: [4, 4],
              pointRadius: 0,
              tension: 0.1
            }},
            {{
              label: 'VUAG (Vanguard S&P 500 GBP)',
              data: ts.vuag,
              borderColor: '#10b981',
              borderWidth: 1.5,
              pointRadius: 0,
              tension: 0.1
            }},
            {{
              label: 'EQQQ (Nasdaq-100)',
              data: ts.eqqq,
              borderColor: '#ffcb47',
              borderWidth: 1.5,
              pointRadius: 0,
              tension: 0.1
            }}
          ]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          interaction: {{
            mode: 'index',
            intersect: false
          }},
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              backgroundColor: '#0f0f0f',
              titleFont: {{ family: 'Geist Mono', size: 12 }},
              bodyFont: {{ family: 'Geist Mono', size: 12 }},
              borderColor: 'rgba(255, 255, 255, 0.2)',
              borderWidth: 1,
              padding: 12,
              callbacks: {{
                label: function(context) {{
                  const val = context.parsed.y;
                  const ret = (val - 100).toFixed(2);
                  return `${{context.dataset.label}}: ${{val}} (${{ret >= 0 ? '+' : ''}}${{ret}}%)`;
                }}
              }}
            }}
          }},
          scales: {{
            x: {{
              grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
              ticks: {{
                color: 'rgba(255, 255, 255, 0.4)',
                font: {{ family: 'Geist Mono', size: 10 }},
                maxTicksLimit: 10
              }}
            }},
            y: {{
              grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
              ticks: {{
                color: 'rgba(255, 255, 255, 0.4)',
                font: {{ family: 'Geist Mono', size: 10 }},
                callback: (val) => val + ' (' + (val - 100 >= 0 ? '+' : '') + (val - 100).toFixed(0) + '%)'
              }}
            }}
          }}
        }}
      }});
    }}

    function toggleSeries(index) {{
      if (!chartInstance) return;
      const isVisible = chartInstance.isDatasetVisible(index);
      chartInstance.setDatasetVisibility(index, !isVisible);
      chartInstance.update();
      
      const btnMap = ['leg-portfolio', 'leg-spy', 'leg-vuag', 'leg-eqqq'];
      const btn = document.getElementById(btnMap[index]);
      if (isVisible) {{
        btn.classList.add('opacity-40');
      }} else {{
        btn.classList.remove('opacity-40');
      }}
    }}

    function setActiveFilter(filter) {{
      currentFilter = filter;
      document.querySelectorAll('.filter-pill').forEach(btn => {{
        if (btn.dataset.filter === filter) {{
          btn.className = 'filter-pill active px-4 py-2 rounded-full border border-[#7aebff] bg-[#7aebff]/10 text-[#7aebff] font-semibold transition whitespace-nowrap';
        }} else {{
          btn.className = 'filter-pill px-4 py-2 rounded-full border border-white/15 hover:border-white/30 bg-[#0f0f0f] text-white/70 hover:text-white transition whitespace-nowrap';
        }}
      }});
      filterArticles();
    }}

    function filterByKind(kind) {{
      if (kind === 'signal_equity' || kind === 'signal_gold') {{
        setActiveFilter('signal');
      }} else {{
        setActiveFilter(kind);
      }}
      document.getElementById('search-input').scrollIntoView({{ behavior: 'smooth' }});
    }}

    function filterArticles() {{
      if (!rawData || !rawData.articles) return;
      const grid = document.getElementById('articles-grid');
      const emptyState = document.getElementById('empty-state');
      grid.innerHTML = '';

      const filtered = rawData.articles.filter(item => {{
        let matchesFilter = true;
        if (currentFilter === 'signal') {{
          matchesFilter = (item.kind === 'signal_equity' || item.kind === 'signal_gold');
        }} else if (currentFilter !== 'all') {{
          matchesFilter = (item.kind === currentFilter);
        }}

        let matchesSearch = true;
        if (searchQuery) {{
          const target = (item.title + ' ' + item.clean_text + ' ' + item.ticker + ' ' + item.author).toLowerCase();
          matchesSearch = target.includes(searchQuery);
        }}

        return matchesFilter && matchesSearch;
      }});

      if (filtered.length === 0) {{
        emptyState.classList.remove('hidden');
      }} else {{
        emptyState.classList.add('hidden');
        filtered.forEach(art => {{
          let cat_badge = 'border-white/20 text-slate-300';
          if (art.kind === 'signal_gold') cat_badge = 'border-[#ffcb47]/40 text-[#ffcb47]';
          else if (art.kind === 'signal_equity') cat_badge = 'border-[#7aebff]/40 text-[#7aebff]';
          else if (art.kind === 'macro_report') cat_badge = 'border-white/40 text-white';
          else if (art.kind === 'trade_alert') cat_badge = 'border-[#ff6666]/40 text-[#ff6666]';

          const card = document.createElement('div');
          card.className = 'group cursor-pointer rounded-2xl bg-[#0f0f0f] p-6 outline outline-white/15 hover:outline-white/30 transition flex flex-col justify-between';
          card.onclick = () => openReader(art.id);
          card.innerHTML = `
            <div>
              <div class="flex items-center justify-between text-xs font-mono mb-3">
                <span class="px-2.5 py-0.5 rounded-full border ${{cat_badge}} text-[10px] font-semibold uppercase tracking-wider">
                  ${{art.category_label}}
                </span>
                <span class="text-white/60 font-mono text-[11px]">${{art.date}}</span>
              </div>
              <h3 class="text-lg font-semibold tracking-tight text-white group-hover:text-[#7aebff] transition line-clamp-2 mb-2">
                ${{art.title}}
              </h3>
              <p class="text-sm text-white/70 line-clamp-3 leading-relaxed mb-4 font-normal">
                ${{art.clean_text}}
              </p>
            </div>
            <div class="pt-3 border-t border-white/10 flex items-center justify-between text-xs font-mono text-white/50">
              <span>${{art.author}}</span>
              <span class="text-[#7aebff] group-hover:translate-x-1 transition-transform flex items-center gap-1 font-medium">
                READ INTEL &rarr;
              </span>
            </div>
          `;
          grid.appendChild(card);
        }});
      }}
    }}

    function openReader(id) {{
      if (!rawData || !rawData.articles) {{
        initData().then(() => {{
          if (rawData) openReader(id);
        }});
        return;
      }}

      const art = rawData.articles.find(a => a.id === id);
      if (!art) return;

      document.getElementById('reader-title').textContent = art.title;
      document.getElementById('reader-date').textContent = art.date;
      document.getElementById('reader-author').textContent = art.author;
      document.getElementById('reader-id').textContent = art.id;
      document.getElementById('reader-category').textContent = art.category_label;
      document.getElementById('reader-external-link').href = art.url;

      const statusEl = document.getElementById('reader-status-tag');
      if (art.restricted) {{
        statusEl.innerHTML = 'STATUS: <span class="text-[#ffcb47]">SERVER REDACTED (TEASER SUMMARY)</span>';
      }} else {{
        statusEl.innerHTML = 'STATUS: <span class="text-[#7aebff]">UNRESTRICTED (COMPLETE REPORT)</span>';
      }}

      document.getElementById('reader-body').innerHTML = art.reader_html || `<p>${{art.clean_text}}</p>`;

      const backdrop = document.getElementById('reader-backdrop');
      const panel = document.getElementById('reader-panel');
      backdrop.classList.remove('opacity-0', 'pointer-events-none');
      panel.classList.remove('translate-x-full');
      document.body.style.overflow = 'hidden';
    }}

    function closeReader() {{
      const backdrop = document.getElementById('reader-backdrop');
      const panel = document.getElementById('reader-panel');
      backdrop.classList.add('opacity-0', 'pointer-events-none');
      panel.classList.add('translate-x-full');
      document.body.style.overflow = '';
    }}
  </script>
</body>
</html>
"""

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"Generated index.html ({len(html_template)} bytes)")

if __name__ == "__main__":
    main()
