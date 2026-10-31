"""S3b test crawl: metadata only (no audio download, no Whisper).

Sends the same kind of AJAX request the archive page's own JavaScript sends:
  1. GET the archive page, read the WordPress nonce (field `security`) fresh from the page JS.
  2. POST to https://newsonair.gov.in/wp-admin/admin-ajax.php (no "www") with the browser's headers.

Usage:
  python crawl_test_metadata.py --categories-only
  python crawl_test_metadata.py --from 2026-10-19 --to 2026-10-25 [--category <slug>]

Full mode writes data/test_crawl_metadata.csv and prints a report.
"""
import argparse
import csv
import os
import re
import sys
import urllib.robotparser
from collections import Counter

import requests
from bs4 import BeautifulSoup

from air_bulletins_scraper import DEFAULT_UA, parse_bulletins, sleep_jitter

BASE = "https://newsonair.gov.in"
PAGE_URL = BASE + "/audio-archive-search/"
AJAX_URL = BASE + "/wp-admin/admin-ajax.php"
AJAX_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE,
    "Referer": PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "*/*",
}
MIN_DELAY, MAX_DELAY = 1.0, 3.0


def robots_allows(session: requests.Session, url: str) -> bool:
    rp = urllib.robotparser.RobotFileParser()
    resp = session.get(BASE + "/robots.txt", timeout=15)
    if resp.status_code != 200:
        print(f"robots.txt returned {resp.status_code}; treating as unverified, stopping")
        return False
    rp.parse(resp.text.splitlines())
    ok = rp.can_fetch(session.headers.get("User-Agent", "*"), url)
    print(f"robots.txt check for {url}: {'allowed' if ok else 'DISALLOWED'}")
    return ok


def extract_nonce(page_html: str, action: str) -> tuple[str, str]:
    """Return (nonce, where_found). Prefer the `security` value inside the given action's call."""
    m = re.search(r"action:\s*['\"]" + re.escape(action) + r"['\"]\s*,\s*security:\s*['\"]([^'\"]+)['\"]",
                  page_html)
    if m:
        return m.group(1), f"inline JS, next to action '{action}'"
    m = re.search(r"security:\s*['\"]([0-9a-fA-F]+)['\"]", page_html)
    if m:
        return m.group(1), "inline JS, first `security:` field on the page"
    raise RuntimeError("no `security` nonce found in the archive page")


def ajax_post(session: requests.Session, payload: dict) -> requests.Response:
    return session.post(AJAX_URL, data=payload, headers=AJAX_HEADERS, timeout=30)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows console is cp1252; titles may be Hindi
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from")
    ap.add_argument("--to", dest="date_to")
    ap.add_argument("--language", default="english")
    ap.add_argument("--category", default="")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--probe", action="store_true",
                    help="S3c: 4 listing requests (first page only) to test how date bounds behave")
    ap.add_argument("--categories-only", action="store_true",
                    help="send exactly one AJAX request (get_listen_news_categories) and stop")
    ap.add_argument("--out", default=os.path.join("data", "test_crawl_metadata.csv"))
    a = ap.parse_args()

    s = requests.Session()
    s.headers["User-Agent"] = DEFAULT_UA
    if not robots_allows(s, AJAX_URL):
        return 1
    sleep_jitter(MIN_DELAY, MAX_DELAY)

    page = s.get(PAGE_URL, timeout=30)
    print(f"GET {PAGE_URL} -> {page.status_code}, {len(page.text)} chars")
    page.raise_for_status()
    nonce, where = extract_nonce(page.text, "get_listen_news_categories")
    print(f"nonce read from page ({where}): length {len(nonce)}")
    sleep_jitter(MIN_DELAY, MAX_DELAY)

    resp = ajax_post(s, {"action": "get_listen_news_categories", "security": nonce,
                         "language": a.language})
    print(f"POST categories -> HTTP {resp.status_code}")
    print("first 300 chars:", resp.text[:300].replace("\n", " "))
    if resp.status_code != 200:
        return 1
    options = [(o.get("value", "").strip(), o.get_text(strip=True))
               for o in BeautifulSoup(resp.text, "html.parser").select("option")]
    print("categories:", options)
    if a.categories_only:
        return 0

    if a.probe:
        for df, dt in [("2026-10-19", "2026-10-19"), ("2026-10-18", "2026-10-20"),
                       ("2026-10-24", "2026-10-26"), ("2026-10-30", "2026-10-31")]:
            sleep_jitter(MIN_DELAY, MAX_DELAY)
            r = ajax_post(s, {"action": "filter_bulletins_audio", "security": nonce,
                              "language": a.language, "category": "",
                              "date_from": df, "date_to": dt, "paged": "1"})
            print(f"\n--- date_from={df} date_to={dt} -> HTTP {r.status_code}")
            if r.status_code != 200:
                print("body:", r.text[:300])
                return 1
            items, has_next = parse_bulletins(r.text)
            soup = BeautifulSoup(r.text, "html.parser")
            nav = soup.select_one("nav.pagination")
            nums = [int(x.get_text(strip=True)) for x in (nav.select("a, span") if nav else [])
                    if x.get_text(strip=True).isdigit()]
            print(f"items on page 1: {len(items)} | has_next={has_next} | "
                  f"max page number in pagination: {max(nums) if nums else None}")
            print("dates on page 1:", dict(sorted(Counter(i.date_iso or i.date_text for i in items).items())))
            if not items:
                print("body head:", r.text[:200].replace("\n", " "))
        return 0

    if not (a.date_from and a.date_to):
        ap.error("--from and --to are required unless --categories-only")

    rows, per_page = [], []
    pg = 1
    while pg <= a.max_pages:
        sleep_jitter(MIN_DELAY, MAX_DELAY)
        r = ajax_post(s, {"action": "filter_bulletins_audio", "security": nonce,
                          "language": a.language, "category": a.category,
                          "date_from": a.date_from, "date_to": a.date_to, "paged": str(pg)})
        if r.status_code != 200:
            print(f"page {pg}: HTTP {r.status_code}: {r.text[:300]}")
            return 1
        items, has_next = parse_bulletins(r.text)
        per_page.append(len(items))
        for it in items:
            rows.append({"page": pg, "title": it.title, "date_text": it.date_text,
                         "date_iso": it.date_iso or "", "audio_url": it.audio_url,
                         "time_hint": "" if it.time_hint is None else it.time_hint})
        print(f"page {pg}: {len(items)} items, has_next={has_next}")
        if not items or not has_next:
            break
        pg += 1

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["page", "title", "date_text", "date_iso",
                                          "audio_url", "time_hint"])
        w.writeheader()
        w.writerows(rows)

    dates = Counter(r["date_iso"] for r in rows)
    print("\n=== REPORT ===")
    print("range:", a.date_from, "->", a.date_to, "| category:", repr(a.category))
    print("total items:", len(rows), "| pages fetched:", len(per_page), "| per page:", per_page)
    print("distinct urls:", len({r['audio_url'] for r in rows}))
    print("date range seen:", min(dates) if dates else None, "->", max(dates) if dates else None)
    print("unparsed dates:", dates.get("", 0))
    print("items per date:", dict(sorted(dates.items())))
    print("time_hint parsed:", sum(1 for r in rows if r["time_hint"] != ""), "/", len(rows))
    print("titles:", Counter(r["title"] for r in rows).most_common(8))
    print("sample urls:")
    for r in rows[:5]:
        print("  ", r["date_iso"], r["time_hint"], r["audio_url"])
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
