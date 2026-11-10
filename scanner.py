#!/usr/bin/env python3
"""
Bravos Terminal Scanner & Site Builder
Reverse-Engineered Tactical Intelligence Terminal (inspired by USAvionix Awwwards SOTD)
Scans Bravos Research WordPress REST API for:
- Author Nicolas posts (Signals & Alerts)
- Macro Reports (the_macro_report)
- Educational Blog (blog_post)
- Newsletters
Pre-bakes the live Portfolio Postures and recent alerts into static HTML,
and outputs data.json for client-side search, filtering, and reading.
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
    print("Bravos Terminal Scanner: Starting ingest...")
    print("=" * 60)

    # 1. Fetch Author Nicolas posts
    print("[1/4] Fetching Author Nicolas posts...")
    nicolas_posts = fetch_json("https://bravosresearch.com/wp-json/wp/v2/posts?author=21391&per_page=100")
    print(f"      Retrieved {len(nicolas_posts)} author posts.")

    # 2. Fetch Macro Reports
    print("[2/4] Fetching Macro Reports (the_macro_report)...")
    macro_reports = []
    for page in [1, 2]:
        try:
            items = fetch_json(f"https://bravosresearch.com/wp-json/wp/v2/the_macro_report?per_page=100&page={page}")
            macro_reports.extend(items)
        except Exception as e:
            print(f"      Warning: Macro page {page} fetch: {e}")
    print(f"      Retrieved {len(macro_reports)} macro reports.")

    # 3. Fetch Educational Blog
    print("[3/4] Fetching Educational Blog posts (blog_post)...")
    blog_posts = []
    for page in [1, 2]:
        try:
            items = fetch_json(f"https://bravosresearch.com/wp-json/wp/v2/blog_post?per_page=100&page={page}")
            blog_posts.extend(items)
        except Exception as e:
            print(f"      Warning: Blog page {page} fetch: {e}")
    print(f"      Retrieved {len(blog_posts)} blog posts.")

    # 4. Fetch Newsletters
    print("[4/4] Fetching Newsletters...")
    newsletters = []
    try:
        newsletters = fetch_json("https://bravosresearch.com/wp-json/wp/v2/newsletters?per_page=100")
    except Exception as e:
        print(f"      Warning: Newsletter fetch: {e}")
    print(f"      Retrieved {len(newsletters)} newsletters.")

    all_articles = []

    # Process Author Nicolas posts
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

    # Macro reports
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

    # Educational Blog
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

    # Newsletters
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
    print(f"Total processed publications: {len(all_articles)}")

    # Extract Active Portfolio Postures
    # 1. Gold Portfolio
    gold_signals = [a for a in all_articles if a["kind"] == "signal_gold"]
    if gold_signals:
        latest_g = gold_signals[0]
        current_gold = {
            "status": "MODERATE" if "MODERATE" in latest_g["title"].upper() else ("CASH" if "CASH" in latest_g["title"].upper() else "ACTIVE"),
            "holding": "50% GLD / 50% CASH",
            "date": latest_g["date"],
            "title": latest_g["title"],
            "directive": latest_g["clean_text"],
            "price": latest_g["sig_data"].get("price", "$379.10"),
            "url": latest_g["url"]
        }
    else:
        current_gold = {
            "status": "MODERATE",
            "holding": "50% GLD / 50% CASH",
            "date": "2026-11-09",
            "title": "Gold Portfolio Signal (Moderate)",
            "directive": "Signal update from CASH to MODERATE. Buy GLD with 50% of your account. Keep the other 50% in cash. You will now hold 50% GLD and 50% cash. Entry price: $379.10 (GLD)",
            "price": "$379.10",
            "url": "https://bravosresearch.com/gold-signal/gold-portfolio-signal-moderate/"
        }

    # 2. Equity Model Portfolio
    equity_signals = [a for a in all_articles if a["kind"] == "signal_equity"]
    if equity_signals:
        latest_e = equity_signals[0]
        title_up = latest_e["title"].upper()
        regime = "CASH" if "CASH" in title_up else ("MODERATE" if "MODERATE" in title_up else ("AGGRESSIVE" if "AGGRESSIVE" in title_up else "ACTIVE"))
        holding = "100% CASH" if regime == "CASH" else ("75% QQQ / 25% TQQQ" if regime == "MODERATE" else "50% QQQ / 50% TQQQ")
        current_equity = {
            "status": regime,
            "holding": holding,
            "date": latest_e["date"],
            "title": latest_e["title"],
            "directive": latest_e["clean_text"],
            "price": latest_e["sig_data"].get("price", "$657.53"),
            "url": latest_e["url"]
        }
    else:
        current_equity = {
            "status": "CASH",
            "holding": "100% CASH",
            "date": "2026-11-06",
            "title": "Equity Portfolio Signal (Cash)",
            "directive": "Signal update from MODERATE to CASH. Sell your entire QQQ and TQQQ positions. Move 100% to cash. Exit price: $657.53",
            "price": "$657.53",
            "url": "https://bravosresearch.com/news-feed/equity-portfolio-signal-cash/"
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
        "portfolios": {
            "equity": current_equity,
            "gold": current_gold
        },
        "recent_alerts": recent_alerts,
        "articles": all_articles
    }

    print("Saving data.json...")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print("Building index.html (USAvionix design system)...")
    build_html(payload)
    print("Done! All assets generated successfully.")

def build_html(data):
    # Pre-render initial articles (first 24 items)
    pre_articles_html = []
    for art in data["articles"][:24]:
        catColor = "text-purple-400 border-purple-500/30 bg-purple-500/10"
        if art["kind"] == "signal_gold":
            catColor = "text-amber-400 border-amber-500/30 bg-amber-500/10"
        elif art["kind"] == "signal_equity":
            catColor = "text-cyan-400 border-cyan-500/30 bg-cyan-500/10"
        elif art["kind"] == "macro_report":
            catColor = "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
        elif art["kind"] == "trade_alert":
            catColor = "text-rose-400 border-rose-500/30 bg-rose-500/10"

        safe_title = html.escape(art["title"])
        safe_clean = html.escape(art["clean_text"])
        card_html = f'''
        <div onclick="openReader({art['id']})" class="group bg-tactical-card hover:bg-tactical-cardHover border border-tactical-border hover:border-tactical-borderHover p-5 rounded-xl transition duration-200 cursor-pointer flex flex-col justify-between shadow-lg">
          <div>
            <div class="flex items-center justify-between text-xs font-mono mb-2.5">
              <span class="px-2 py-0.5 rounded text-[10px] font-semibold uppercase border {catColor}">
                {art['category_label']}
              </span>
              <span class="text-tactical-subtle">{art['date']}</span>
            </div>
            <h3 class="text-base font-bold text-white tracking-tight group-hover:text-amber-300 transition line-clamp-2 mb-2">
              {safe_title}
            </h3>
            <p class="text-xs text-tactical-muted line-clamp-3 leading-relaxed mb-4">
              {safe_clean}
            </p>
          </div>
          <div class="pt-3 border-t border-white/5 flex items-center justify-between text-xs font-mono text-tactical-subtle">
            <span>{art['author']}</span>
            <span class="text-cyan-400 font-semibold group-hover:translate-x-0.5 transition-transform flex items-center gap-1">
              READ INTEL &rarr;
            </span>
          </div>
        </div>
        '''
        pre_articles_html.append(card_html)

    initial_cards_joined = "".join(pre_articles_html)

    # Pre-render alerts grid
    alerts_html = []
    for al in data["recent_alerts"]:
        isClosing = "Closing" in al["title"]
        isInitiating = "Initiating" in al["title"]
        isProfits = "Profit" in al["title"]

        borderClass = "border-white/10"
        actionBadge = '<span class="text-slate-400">ALERT</span>'
        if isClosing:
            borderClass = "border-red-500/20 hover:border-red-500/40"
            actionBadge = '<span class="text-red-400 font-bold">CLOSE</span>'
        elif isInitiating:
            borderClass = "border-emerald-500/20 hover:border-emerald-500/40"
            actionBadge = '<span class="text-emerald-400 font-bold">LONG</span>'
        elif isProfits:
            borderClass = "border-amber-500/20 hover:border-amber-500/40"
            actionBadge = '<span class="text-amber-400 font-bold">PROFIT</span>'

        ticker_display = ("$" + al["ticker"]) if al["ticker"] else "PORTFOLIO"
        safe_title = html.escape(al["title"])
        safe_clean = html.escape(al["clean_text"])

        card = f'''
        <div onclick="openReader({al['id']})" class="bg-tactical-card p-3.5 rounded-lg border {borderClass} cursor-pointer hover:bg-tactical-cardHover transition flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between font-mono text-[11px] mb-1.5">
              {actionBadge}
              <span class="text-tactical-subtle">{al['date']}</span>
            </div>
            <div class="text-sm font-bold text-white tracking-tight mb-1 truncate">{safe_title}</div>
            <p class="text-xs text-tactical-subtle line-clamp-2">{safe_clean}</p>
          </div>
          <div class="mt-3 pt-2 border-t border-white/5 flex items-center justify-between text-[11px] font-mono text-tactical-subtle">
            <span class="text-cyan-400 font-semibold">{ticker_display}</span>
            <span>READ &rarr;</span>
          </div>
        </div>
        '''
        alerts_html.append(card)

    initial_alerts_joined = "".join(alerts_html)

    # Pre-render Equity & Gold status
    eq = data["portfolios"]["equity"]
    gd = data["portfolios"]["gold"]

    eq_badge_class = "px-3.5 py-1.5 rounded-full text-xs font-mono font-bold tracking-wider uppercase border border-red-500/40 bg-red-500/10 text-red-400 radar-pulse" if eq["status"] == "CASH" else "px-3.5 py-1.5 rounded-full text-xs font-mono font-bold tracking-wider uppercase border border-amber-500/40 bg-amber-500/10 text-amber-300"
    eq_badge_text = "100% CASH // DEFENSIVE" if eq["status"] == "CASH" else f"{eq['status']} ({eq['holding']})"

    gd_badge_class = "px-3.5 py-1.5 rounded-full text-xs font-mono font-bold tracking-wider uppercase border border-amber-500/40 bg-amber-500/10 text-amber-300 radar-pulse-amber"
    gd_badge_text = f"{gd['status']} ({gd['holding']})"

    html_template = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BRAVOS // TACTICAL INTELLIGENCE TERMINAL</title>
  <meta name="description" content="Tactical asset allocation terminal, real-time model portfolios, gold regime posture, and research publications scanner.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Geist+Mono:wght@300;400;500;600;700&family=Geist:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          fontFamily: {{
            sans: ['Geist', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
            mono: ['Geist Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
          }},
          colors: {{
            tactical: {{
              bg: '#060709',
              surface: '#0B0D11',
              card: '#0F1218',
              cardHover: '#141822',
              border: 'rgba(255, 255, 255, 0.08)',
              borderHover: 'rgba(255, 255, 255, 0.22)',
              gold: '#F59E0B',
              goldGlow: 'rgba(245, 158, 11, 0.15)',
              emerald: '#10B981',
              emeraldGlow: 'rgba(16, 185, 129, 0.15)',
              crimson: '#EF4444',
              crimsonGlow: 'rgba(239, 68, 68, 0.15)',
              cyan: '#06B6D4',
              cyanGlow: 'rgba(6, 182, 212, 0.15)',
              muted: '#94A3B8',
              subtle: '#64748B'
            }}
          }}
        }}
      }}
    }}
  </script>
  <style>
    :root {{ color-scheme: dark; }}
    body {{
      background-color: #060709;
      color: #E2E8F0;
      font-family: 'Geist', 'Inter', sans-serif;
      overflow-x: hidden;
      background-image: 
        radial-gradient(circle at 50% 0%, rgba(245, 158, 11, 0.03) 0%, transparent 40%),
        radial-gradient(circle at 80% 20%, rgba(6, 182, 212, 0.02) 0%, transparent 35%);
    }}
    .bg-grid {{
      background-size: 40px 40px;
      background-image: 
        linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
    }}
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: #060709; }}
    ::-webkit-scrollbar-thumb {{ background: rgba(255, 255, 255, 0.15); border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: rgba(255, 255, 255, 0.3); }}

    @keyframes pulse-radar {{
      0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
      70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }}
      100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
    }}
    .radar-pulse {{ animation: pulse-radar 2s infinite; }}

    @keyframes pulse-radar-amber {{
      0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.7); }}
      70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(245, 158, 11, 0); }}
      100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }}
    }}
    .radar-pulse-amber {{ animation: pulse-radar-amber 2s infinite; }}

    .article-body p {{ margin-bottom: 1.25rem; line-height: 1.8; color: #CBD5E1; font-size: 1.05rem; }}
    .article-body strong {{ color: #F8FAFC; font-weight: 600; }}
    .article-body h2, .article-body h3, .article-body h4 {{ color: #F8FAFC; font-weight: 700; margin-top: 2rem; margin-bottom: 1rem; letter-spacing: -0.02em; }}
    .article-body h2 {{ font-size: 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 0.5rem; }}
    .article-body h3 {{ font-size: 1.25rem; }}
    .article-body img {{ max-width: 100%; height: auto; border-radius: 8px; margin: 1.75rem 0; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
    .article-body blockquote {{ border-left: 2px solid #F59E0B; padding-left: 1.25rem; margin: 1.5rem 0; color: #E2E8F0; font-style: italic; }}
    .article-body a {{ color: #38BDF8; text-decoration: underline; text-underline-offset: 4px; }}
  </style>
</head>
<body class="bg-tactical-bg text-slate-100 min-h-screen flex flex-col antialiased selection:bg-amber-500/30 selection:text-amber-200">
  <div class="bg-grid fixed inset-0 pointer-events-none z-0"></div>

  <!-- Top Tactical Telemetry Header -->
  <header class="relative z-20 border-b border-tactical-border bg-tactical-surface/80 backdrop-blur-md sticky top-0 px-4 md:px-8 py-3.5 flex items-center justify-between">
    <div class="flex items-center space-x-4">
      <div class="flex items-center space-x-2.5">
        <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 radar-pulse inline-block"></span>
        <span class="font-mono text-xs tracking-widest text-emerald-400 font-semibold uppercase">SCANNER ACTIVE</span>
      </div>
      <div class="h-4 w-px bg-white/10 hidden sm:block"></div>
      <a href="#" class="flex items-center space-x-2">
        <span class="text-xs font-mono font-bold tracking-wider text-slate-400 uppercase">SYS //</span>
        <span class="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
          BRAVOS TERMINAL
          <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-amber-400">v2.4 HUD</span>
        </span>
      </a>
    </div>

    <!-- Quick stats in header -->
    <div class="hidden lg:flex items-center space-x-6 text-xs font-mono">
      <div class="flex items-center space-x-2">
        <span class="text-tactical-subtle">INDEXED PUBS:</span>
        <span class="text-white font-semibold" id="head-total-count">{data['counts']['total']}</span>
      </div>
      <div class="flex items-center space-x-2">
        <span class="text-tactical-subtle">CADENCE:</span>
        <span class="text-cyan-400">2-HOUR CRON</span>
      </div>
      <div class="flex items-center space-x-2">
        <span class="text-tactical-subtle">TELEMETRY SYNC:</span>
        <span class="text-slate-300" id="head-sync-time">{data['sync_time']}</span>
      </div>
    </div>

    <!-- Action buttons -->
    <div class="flex items-center space-x-3">
      <a href="https://github.com/soylee22/bravos-terminal" target="_blank" rel="noopener noreferrer" 
         class="text-xs font-mono px-3 py-1.5 rounded-md bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 transition flex items-center space-x-1.5">
        <svg class="w-3.5 h-3.5 text-slate-300" fill="currentColor" viewBox="0 0 24 24"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"></path></svg>
        <span class="hidden sm:inline">REPO</span>
      </a>
      <button onclick="triggerRefresh()" title="Scan for latest updates" class="text-xs font-mono px-3 py-1.5 rounded-md bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 transition flex items-center space-x-1.5">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
        <span>SCAN NOW</span>
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <main class="relative z-10 max-w-7xl w-full mx-auto px-4 md:px-8 py-8 flex-1">

    <!-- Hero Title Banner (USAvionix flight typography) -->
    <div class="mb-8 flex flex-col md:flex-row md:items-end justify-between border-b border-tactical-border pb-6 gap-4">
      <div>
        <div class="flex items-center gap-2 mb-2">
          <span class="text-xs font-mono uppercase tracking-widest text-tactical-subtle">[MISSION DIRECTIVE]</span>
          <span class="text-xs font-mono text-amber-400">// TACTICAL ASSET POSTURE</span>
        </div>
        <h1 class="text-3xl md:text-5xl font-extrabold tracking-tight text-white">
          Real-time Portfolio Regimes
        </h1>
        <p class="text-tactical-muted mt-2 text-sm md:text-base max-w-2xl">
          Automated intelligence feed scanning Author Nicolas and Bravos Research publications via WordPress REST API. Instant allocation readouts for live accounts.
        </p>
      </div>

      <div class="flex items-center gap-2 font-mono text-xs text-tactical-subtle bg-tactical-card px-4 py-2.5 rounded-lg border border-tactical-border self-start md:self-auto">
        <span class="w-2 h-2 rounded-full bg-cyan-400"></span>
        <span>AUTHOR ID: 21391 (BRAVOS)</span>
      </div>
    </div>

    <!-- MAIN PORTFOLIO READOUTS (Two Tactical HUD Cards) -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">

      <!-- 1. EQUITY MODEL PORTFOLIO -->
      <div id="card-equity" class="relative group rounded-xl bg-tactical-card border border-tactical-border hover:border-tactical-borderHover p-6 transition-all duration-300 shadow-xl overflow-hidden">
        <div class="absolute top-0 right-0 w-32 h-32 bg-crimson-500/5 rounded-full blur-3xl pointer-events-none"></div>
        <div class="flex items-start justify-between mb-4">
          <div>
            <span class="text-[11px] font-mono tracking-widest text-tactical-subtle uppercase block mb-1">STRATEGY 01 // NASDAQ REGIME</span>
            <h2 class="text-xl md:text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              Equity Model Portfolio
            </h2>
          </div>
          <div id="equity-badge" class="{eq_badge_class}">
            {eq_badge_text}
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3 my-5 font-mono text-xs">
          <div class="bg-tactical-surface/60 p-3 rounded-lg border border-white/5">
            <span class="text-tactical-subtle block text-[10px] uppercase">TARGET ALLOCATION</span>
            <span id="equity-target" class="text-sm font-semibold text-white mt-0.5 block">{eq['holding']}</span>
          </div>
          <div class="bg-tactical-surface/60 p-3 rounded-lg border border-white/5">
            <span class="text-tactical-subtle block text-[10px] uppercase">SIGNAL DATE</span>
            <span id="equity-date" class="text-sm font-semibold text-slate-300 mt-0.5 block">{eq['date']}</span>
          </div>
          <div class="bg-tactical-surface/60 p-3 rounded-lg border border-white/5">
            <span class="text-tactical-subtle block text-[10px] uppercase">TRIGGER / EXIT PRICE</span>
            <span id="equity-price" class="text-sm font-semibold text-slate-300 mt-0.5 block">{eq['price'] or 'N/A'}</span>
          </div>
          <div class="bg-tactical-surface/60 p-3 rounded-lg border border-white/5">
            <span class="text-tactical-subtle block text-[10px] uppercase">INSTRUMENTS</span>
            <span class="text-sm font-semibold text-cyan-400 mt-0.5 block">QQQ / TQQQ / CASH</span>
          </div>
        </div>

        <div class="bg-tactical-surface/80 border border-white/5 rounded-lg p-3.5 mb-4">
          <span class="text-[10px] font-mono uppercase tracking-wider text-tactical-subtle block mb-1">OPERATIONAL DIRECTIVE</span>
          <p id="equity-directive" class="text-xs md:text-sm text-slate-300 leading-relaxed font-sans">
            {html.escape(eq['directive'])}
          </p>
        </div>

        <div class="flex items-center justify-between text-xs font-mono text-tactical-subtle pt-2 border-t border-white/5">
          <span id="equity-source-link">
            <a href="{eq['url']}" target="_blank" rel="noopener noreferrer" class="hover:text-slate-300 underline underline-offset-4">Source: {html.escape(eq['title'])}</a>
          </span>
          <button onclick="filterByKind('signal_equity')" class="text-cyan-400 hover:text-cyan-300 transition flex items-center gap-1">
            VIEW SIGNAL HISTORY &rarr;
          </button>
        </div>
      </div>

      <!-- 2. GOLD PORTFOLIO -->
      <div id="card-gold" class="relative group rounded-xl bg-tactical-card border border-tactical-border hover:border-tactical-borderHover p-6 transition-all duration-300 shadow-xl overflow-hidden">
        <div class="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-full blur-3xl pointer-events-none"></div>
        <div class="flex items-start justify-between mb-4">
          <div>
            <span class="text-[11px] font-mono tracking-widest text-tactical-subtle uppercase block mb-1">STRATEGY 02 // COMMODITY REGIME</span>
            <h2 class="text-xl md:text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              Gold Portfolio
            </h2>
          </div>
          <div id="gold-badge" class="{gd_badge_class}">
            {gd_badge_text}
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3 my-5 font-mono text-xs">
          <div class="bg-tactical-surface/60 p-3 rounded-lg border border-white/5">
            <span class="text-tactical-subtle block text-[10px] uppercase">TARGET ALLOCATION</span>
            <span id="gold-target" class="text-sm font-semibold text-amber-300 mt-0.5 block">{gd['holding']}</span>
          </div>
          <div class="bg-tactical-surface/60 p-3 rounded-lg border border-white/5">
            <span class="text-tactical-subtle block text-[10px] uppercase">SIGNAL DATE</span>
            <span id="gold-date" class="text-sm font-semibold text-slate-300 mt-0.5 block">{gd['date']}</span>
          </div>
          <div class="bg-tactical-surface/60 p-3 rounded-lg border border-white/5">
            <span class="text-tactical-subtle block text-[10px] uppercase">ENTRY PRICE</span>
            <span id="gold-price" class="text-sm font-semibold text-slate-300 mt-0.5 block">{gd['price'] or 'N/A'}</span>
          </div>
          <div class="bg-tactical-surface/60 p-3 rounded-lg border border-white/5">
            <span class="text-tactical-subtle block text-[10px] uppercase">INSTRUMENTS</span>
            <span class="text-sm font-semibold text-amber-400 mt-0.5 block">GLD / CASH</span>
          </div>
        </div>

        <div class="bg-tactical-surface/80 border border-white/5 rounded-lg p-3.5 mb-4">
          <span class="text-[10px] font-mono uppercase tracking-wider text-tactical-subtle block mb-1">OPERATIONAL DIRECTIVE</span>
          <p id="gold-directive" class="text-xs md:text-sm text-slate-300 leading-relaxed font-sans">
            {html.escape(gd['directive'])}
          </p>
        </div>

        <div class="flex items-center justify-between text-xs font-mono text-tactical-subtle pt-2 border-t border-white/5">
          <span id="gold-source-link">
            <a href="{gd['url']}" target="_blank" rel="noopener noreferrer" class="hover:text-slate-300 underline underline-offset-4">Source: {html.escape(gd['title'])}</a>
          </span>
          <button onclick="filterByKind('signal_gold')" class="text-amber-400 hover:text-amber-300 transition flex items-center gap-1">
            VIEW SIGNAL HISTORY &rarr;
          </button>
        </div>
      </div>

    </div>

    <!-- RECENT TRADE ALERTS RADAR -->
    <div class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <span class="text-xs font-mono uppercase tracking-wider text-tactical-subtle">[RADAR TELEMETRY]</span>
          <h3 class="text-lg font-bold text-white tracking-tight">Recent Trade Alerts & Actions</h3>
        </div>
        <button onclick="filterByKind('trade_alert')" class="text-xs font-mono text-tactical-muted hover:text-white transition">
          VIEW ALL 30 ALERTS &rarr;
        </button>
      </div>

      <div id="alerts-radar-grid" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5">
        {initial_alerts_joined}
      </div>
    </div>

    <!-- FEED & ARTICLE SEARCH EXPLORER -->
    <div class="pt-6 border-t border-tactical-border">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <span class="text-xs font-mono uppercase tracking-wider text-tactical-subtle">[DOCUMENT REPOSITORY]</span>
          <h2 class="text-2xl font-bold tracking-tight text-white">Publications & Intel Feed</h2>
        </div>

        <div class="relative w-full md:w-80">
          <input type="text" id="search-input" placeholder="Search signals, tickers, macro topics..." 
                 class="w-full bg-tactical-card border border-tactical-border focus:border-cyan-400/50 rounded-lg px-4 py-2.5 text-xs text-slate-200 placeholder-tactical-subtle font-mono focus:outline-none transition">
          <span class="absolute right-3 top-2.5 text-[10px] font-mono text-tactical-subtle border border-white/10 px-1.5 py-0.5 rounded">/</span>
        </div>
      </div>

      <!-- Filter Pills -->
      <div class="flex items-center gap-2 overflow-x-auto pb-4 mb-6 text-xs font-mono scrollbar-none">
        <button onclick="setActiveFilter('all')" class="filter-pill active px-3.5 py-1.5 rounded-lg border border-amber-500/50 bg-amber-500/10 text-amber-300 font-semibold transition whitespace-nowrap" data-filter="all">
          ALL PUBS (<span id="count-all">{data['counts']['total']}</span>)
        </button>
        <button onclick="setActiveFilter('signal')" class="filter-pill px-3.5 py-1.5 rounded-lg border border-white/10 hover:border-white/20 bg-tactical-card text-tactical-muted hover:text-white transition whitespace-nowrap" data-filter="signal">
          PORTFOLIO SIGNALS (<span id="count-signals">{data['counts']['signals']}</span>)
        </button>
        <button onclick="setActiveFilter('trade_alert')" class="filter-pill px-3.5 py-1.5 rounded-lg border border-white/10 hover:border-white/20 bg-tactical-card text-tactical-muted hover:text-white transition whitespace-nowrap" data-filter="trade_alert">
          TRADE ALERTS (<span id="count-alerts">{data['counts']['trade_alerts']}</span>)
        </button>
        <button onclick="setActiveFilter('macro_report')" class="filter-pill px-3.5 py-1.5 rounded-lg border border-white/10 hover:border-white/20 bg-tactical-card text-tactical-muted hover:text-white transition whitespace-nowrap" data-filter="macro_report">
          MACRO REPORTS (<span id="count-macro">{data['counts']['macro_reports']}</span>)
        </button>
        <button onclick="setActiveFilter('blog_post')" class="filter-pill px-3.5 py-1.5 rounded-lg border border-white/10 hover:border-white/20 bg-tactical-card text-tactical-muted hover:text-white transition whitespace-nowrap" data-filter="blog_post">
          EDUCATIONAL BLOG (<span id="count-blog">{data['counts']['blog_posts']}</span>)
        </button>
        <button onclick="setActiveFilter('newsletter')" class="filter-pill px-3.5 py-1.5 rounded-lg border border-white/10 hover:border-white/20 bg-tactical-card text-tactical-muted hover:text-white transition whitespace-nowrap" data-filter="newsletter">
          NEWSLETTERS (<span id="count-news">{data['counts']['newsletters']}</span>)
        </button>
      </div>

      <!-- Articles Grid -->
      <div id="articles-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {initial_cards_joined}
      </div>

      <div id="empty-state" class="hidden py-16 text-center font-mono text-sm text-tactical-subtle">
        No publications match your filter criteria.
      </div>
    </div>

  </main>

  <!-- Slide-over Full Article Reader Drawer (HUD style) -->
  <div id="reader-backdrop" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 opacity-0 pointer-events-none transition-opacity duration-300 flex justify-end" onclick="closeReader()">
    <div id="reader-panel" class="w-full max-w-3xl bg-tactical-surface border-l border-tactical-border h-full overflow-y-auto p-6 md:p-10 shadow-2xl transform translate-x-full transition-transform duration-300" onclick="event.stopPropagation()">
      
      <div class="flex items-center justify-between pb-6 mb-6 border-b border-tactical-border sticky top-0 bg-tactical-surface/95 backdrop-blur z-10 pt-2">
        <div class="flex items-center space-x-2 font-mono text-xs">
          <span id="reader-category" class="px-2 py-0.5 rounded border"></span>
          <span id="reader-date" class="text-tactical-subtle"></span>
        </div>
        <div class="flex items-center space-x-3">
          <a id="reader-external-link" href="#" target="_blank" rel="noopener noreferrer" 
             class="text-xs font-mono text-cyan-400 hover:text-cyan-300 transition flex items-center gap-1">
            OPEN ORIGINAL &nearr;
          </a>
          <button onclick="closeReader()" class="p-1.5 rounded-md hover:bg-white/10 text-tactical-muted hover:text-white transition">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>
      </div>

      <h1 id="reader-title" class="text-2xl md:text-3xl font-extrabold text-white tracking-tight mb-4"></h1>

      <div id="reader-meta-box" class="bg-tactical-card p-4 rounded-lg border border-white/5 font-mono text-xs mb-8 flex flex-wrap gap-4 text-tactical-subtle">
        <div>AUTHOR: <span id="reader-author" class="text-white"></span></div>
        <div>PUB ID: <span id="reader-id" class="text-slate-300"></span></div>
        <div id="reader-status-tag"></div>
      </div>

      <div id="reader-body" class="article-body"></div>

    </div>
  </div>

  <footer class="relative z-10 border-t border-tactical-border py-8 px-4 md:px-8 mt-16 text-center font-mono text-xs text-tactical-subtle">
    <div class="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
      <div>BRAVOS TERMINAL // REVERSE-ENGINEERED INTELLIGENCE FEED</div>
      <div>DATA SYNCED DIRECT FROM BRAVOSRESEARCH.COM REST API</div>
      <div>FOR RESEARCH AND PRIVATE TELEMETRY USE ONLY</div>
    </div>
  </footer>

  <script>
    let rawData = null;
    let currentFilter = 'all';
    let searchQuery = '';

    // Fetch full data in background for instant search and full reader
    async function initData() {{
      try {{
        const res = await fetch('./data.json');
        if (res.ok) {{
          rawData = await res.json();
          console.log('Full dataset loaded:', rawData.counts.total, 'articles.');
        }}
      }} catch(err) {{
        console.warn('Asynchronous data.json fetch deferred or restricted:', err);
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

    function setActiveFilter(filter) {{
      currentFilter = filter;
      document.querySelectorAll('.filter-pill').forEach(btn => {{
        if (btn.dataset.filter === filter) {{
          btn.className = 'filter-pill active px-3.5 py-1.5 rounded-lg border border-amber-500/50 bg-amber-500/10 text-amber-300 font-semibold transition whitespace-nowrap';
        }} else {{
          btn.className = 'filter-pill px-3.5 py-1.5 rounded-lg border border-white/10 hover:border-white/20 bg-tactical-card text-tactical-muted hover:text-white transition whitespace-nowrap';
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
          let catColor = 'text-purple-400 border-purple-500/30 bg-purple-500/10';
          if (art.kind === 'signal_gold') {{
            catColor = 'text-amber-400 border-amber-500/30 bg-amber-500/10';
          }} else if (art.kind === 'signal_equity') {{
            catColor = 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10';
          }} else if (art.kind === 'macro_report') {{
            catColor = 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10';
          }} else if (art.kind === 'trade_alert') {{
            catColor = 'text-rose-400 border-rose-500/30 bg-rose-500/10';
          }}

          const card = document.createElement('div');
          card.className = 'group bg-tactical-card hover:bg-tactical-cardHover border border-tactical-border hover:border-tactical-borderHover p-5 rounded-xl transition duration-200 cursor-pointer flex flex-col justify-between shadow-lg';
          card.onclick = () => openReader(art.id);
          card.innerHTML = `
            <div>
              <div class="flex items-center justify-between text-xs font-mono mb-2.5">
                <span class="px-2 py-0.5 rounded text-[10px] font-semibold uppercase border ${{catColor}}">
                  ${{art.category_label}}
                </span>
                <span class="text-tactical-subtle">${{art.date}}</span>
              </div>
              <h3 class="text-base font-bold text-white tracking-tight group-hover:text-amber-300 transition line-clamp-2 mb-2">
                ${{art.title}}
              </h3>
              <p class="text-xs text-tactical-muted line-clamp-3 leading-relaxed mb-4">
                ${{art.clean_text}}
              </p>
            </div>
            <div class="pt-3 border-t border-white/5 flex items-center justify-between text-xs font-mono text-tactical-subtle">
              <span>${{art.author}}</span>
              <span class="text-cyan-400 font-semibold group-hover:translate-x-0.5 transition-transform flex items-center gap-1">
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
        statusEl.innerHTML = 'STATUS: <span class="text-amber-400">SERVER REDACTED (TEASER SUMMARY)</span>';
      }} else {{
        statusEl.innerHTML = 'STATUS: <span class="text-emerald-400">UNRESTRICTED (COMPLETE REPORT)</span>';
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

    function triggerRefresh() {{
      const btn = event.currentTarget;
      btn.innerHTML = `<span class="radar-pulse inline-block w-2 h-2 rounded-full bg-amber-400"></span> <span>SCANNING...</span>`;
      setTimeout(() => {{
        window.location.reload();
      }}, 800);
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
