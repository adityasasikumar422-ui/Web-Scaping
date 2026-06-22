"""
dump_html.py
─────────────────────────────────────────────────────────────────────────────
Fetches the CUSAT academics page and saves the raw HTML to disk so we can
inspect the real element/class names and fix the scraper selectors.

Usage:
    python dump_html.py
Output:
    cusat_raw.html   — open this in VS Code or a browser to inspect markup
    cusat_links.txt  — every <a> href on the page (for finding notice/faculty
                       sub-pages)
"""

import sys
import time
import urllib3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL   = "https://www.cusat.ac.in"
TARGET_URL = "https://www.cusat.ac.in/academics"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=20,
                        verify=False, allow_redirects=True)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


print(f"Fetching {TARGET_URL} ...")
html = fetch(TARGET_URL)

# ── 1. Save raw HTML ──────────────────────────────────────────────────────────
with open("cusat_raw.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"Saved raw HTML → cusat_raw.html  ({len(html):,} bytes)")

# ── 2. Parse and report all unique class names on the page ───────────────────
soup = BeautifulSoup(html, "lxml")

all_classes = set()
for tag in soup.find_all(True):
    for cls in tag.get("class", []):
        all_classes.add(cls)

print(f"\nAll CSS class names found on page ({len(all_classes)} unique):")
for cls in sorted(all_classes):
    print(f"  .{cls}")

# ── 3. Show every <div> and <section> with its class ─────────────────────────
print("\nAll <div> / <section> elements and their classes:")
for tag in soup.find_all(["div", "section"]):
    classes = " ".join(tag.get("class", []))
    tag_id  = tag.get("id", "")
    if classes or tag_id:
        snippet = tag.get_text()[:60].replace("\n", " ").strip()
        print(f"  <{tag.name}  class='{classes}'  id='{tag_id}'> → {snippet!r}")

# ── 4. Save all links to a text file ─────────────────────────────────────────
links = []
for a in soup.find_all("a", href=True):
    text = " ".join(a.get_text().split())
    href = urljoin(BASE_URL, a["href"])
    links.append(f"{text:<50s}  {href}")

with open("cusat_links.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(links))
print(f"\nSaved all {len(links)} links → cusat_links.txt")

# ── 5. Look for notice/faculty keywords in class names ───────────────────────
print("\nClass names containing notice / news / faculty / staff / announce:")
keywords = ["notice", "news", "faculty", "staff", "announce", "update",
            "scroll", "ticker", "marq", "slider"]
for cls in sorted(all_classes):
    if any(kw in cls.lower() for kw in keywords):
        print(f"  FOUND → .{cls}")

# ── 6. Look for <marquee> (common for CUSAT notices) ─────────────────────────
marquees = soup.find_all("marquee")
print(f"\n<marquee> elements: {len(marquees)}")
for m in marquees:
    print(f"  Content snippet: {m.get_text()[:100]!r}")

# ── 7. Check for iframes (notices sometimes loaded in iframes) ───────────────
iframes = soup.find_all("iframe")
print(f"\n<iframe> elements: {len(iframes)}")
for iframe in iframes:
    print(f"  src = {iframe.get('src', '(no src)')}")

print("\nDone. Share the output above so selectors can be tuned.")
