"""
cusat_scraper.py
─────────────────────────────────────────────────────────────────────────────
One-off scraper for the CUSAT Academics page.
Target: https://www.cusat.ac.in/academics

IMPORTANT — read before running
─────────────────────────────────────────────────────────────────────────────
1. cusat.ac.in robots.txt disallows automated crawling. Use this only for
   personal/educational purposes with low-volume, rate-limited access.
2. SSL verification is disabled (verify=False) because CUSAT's server does
   not send its full certificate chain — this is a known server-side
   misconfiguration. The connection still uses TLS encryption; only the
   identity check is skipped. Do not transmit sensitive data over this
   connection.

What it extracts
─────────────────────────────────────────────────────────────────────────────
  - departments  : department/program names + links
  - faculty      : faculty member names + designation + profile link
  - notices      : announcement titles + links + dates
  - courses      : course/syllabus titles + links
  - all_text     : full visible text content of the page, cleaned

Output
─────────────────────────────────────────────────────────────────────────────
  Single JSON file: cusat_academics.json

Usage
─────────────────────────────────────────────────────────────────────────────
  pip install requests beautifulsoup4 lxml certifi
  python cusat_scraper.py
"""

import json
import re
import sys
import time
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_URL    = "https://www.cusat.ac.in"
TARGET_URL  = "https://www.cusat.ac.in/academics"
OUTPUT_FILE = "cusat_academics.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

REQUEST_TIMEOUT = 20   # seconds
REQUEST_DELAY   = 1.0  # seconds between requests (be polite)


# ── SSL note ──────────────────────────────────────────────────────────────────
# CUSAT's server omits intermediate certificates, causing verification to fail
# in both certifi and the OS trust store. We suppress the warning and disable
# verification. This is safe here because we are only reading public pages.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ── Fetch ─────────────────────────────────────────────────────────────────────
def fetch_page(url: str) -> BeautifulSoup | None:
    """GET a URL and return a BeautifulSoup object, or None on failure."""
    print(f"[INFO] Fetching: {url}")
    try:
        resp = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            verify=False,           # SSL chain incomplete on server side
            allow_redirects=True,
        )
        print(f"[INFO] HTTP {resp.status_code}")
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        return BeautifulSoup(resp.text, "lxml")
    except requests.exceptions.RequestException as exc:
        print(f"[ERROR] {url}: {exc}", file=sys.stderr)
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────
def clean(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()


def abs_url(href: str) -> str:
    """Turn a relative href into an absolute CUSAT URL."""
    return urljoin(BASE_URL, href)


# ── Extractors ────────────────────────────────────────────────────────────────
def extract_departments(soup: BeautifulSoup) -> list[dict]:
    """
    Extract department / program names and their links.

    Tries three patterns in order:
      A. Links whose href or text contains 'department', 'dept', 'school of',
         'college of'.
      B. <li> items inside any element with class containing 'dept' or
         'department'.
      C. Navigation menu items under a heading that mentions 'department'.
    """
    results = []
    seen: set[tuple] = set()

    dept_keywords = ["department", "dept", "school of", "college of", "centre"]

    # Pattern A — any <a> tag whose text or href looks like a department
    for a in soup.find_all("a", href=True):
        text = clean(a.get_text())
        href = a["href"]
        if not text:
            continue
        haystack = (href + " " + text).lower()
        if any(kw in haystack for kw in dept_keywords):
            key = (text, abs_url(href))
            if key not in seen:
                seen.add(key)
                results.append({"name": text, "url": abs_url(href)})

    # Pattern B — elements whose class mentions dept/department
    for tag in soup.select('[class*="dept"], [class*="department"]'):
        for a in tag.find_all("a", href=True):
            text = clean(a.get_text())
            if text:
                key = (text, abs_url(a["href"]))
                if key not in seen:
                    seen.add(key)
                    results.append({"name": text, "url": abs_url(a["href"])})

    # Pattern C — headings that say "departments", followed by a list
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        if "department" in clean(heading.get_text()).lower():
            sibling = heading.find_next_sibling(["ul", "ol"])
            if sibling:
                for li in sibling.find_all("li"):
                    a = li.find("a", href=True)
                    text = clean(li.get_text())
                    if text:
                        key = (text, abs_url(a["href"]) if a else "")
                        if key not in seen:
                            seen.add(key)
                            results.append({
                                "name": text,
                                "url": abs_url(a["href"]) if a else None,
                            })

    return results


def extract_faculty(soup: BeautifulSoup) -> list[dict]:
    """
    Extract faculty member names, designations, and profile links.

    Tries:
      A. Table rows whose first cell starts with a title like Dr./Prof./Mr./Ms.
      B. Elements with class containing 'faculty' or 'staff'.
    """
    results = []
    seen: set[str] = set()
    title_re = re.compile(r"\b(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.)\b")

    # Pattern A — table rows
    for row in soup.find_all("tr"):
        cells = [clean(c.get_text()) for c in row.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells and title_re.search(cells[0]):
            name = cells[0]
            if name in seen:
                continue
            seen.add(name)
            a = row.find("a", href=True)
            results.append({
                "name":        name,
                "designation": cells[1] if len(cells) > 1 else None,
                "department":  cells[2] if len(cells) > 2 else None,
                "url":         abs_url(a["href"]) if a else None,
            })

    # Pattern B — class-based containers
    for tag in soup.select('[class*="faculty"], [class*="staff"]'):
        text = clean(tag.get_text())
        if text and title_re.search(text) and text not in seen:
            seen.add(text)
            a = tag.find("a", href=True)
            results.append({
                "name":        text,
                "designation": None,
                "department":  None,
                "url":         abs_url(a["href"]) if a else None,
            })

    return results


def extract_notices(soup: BeautifulSoup) -> list[dict]:
    """
    Extract notices / announcements with title, URL, and date.

    Looks for containers whose class contains 'notice', 'news', 'announce',
    or for <marquee> elements (CUSAT uses marquee for scrolling notices).
    """
    results = []
    seen: set[str] = set()
    date_re = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")

    selectors = (
        '[class*="notice"], [class*="news"], '
        '[class*="announce"], [class*="update"], marquee'
    )
    for container in soup.select(selectors):
        for a in container.find_all("a", href=True):
            title = clean(a.get_text())
            url   = abs_url(a["href"])
            if not title or url in seen:
                continue
            seen.add(url)
            # Look for a date near the link
            parent = a.find_parent()
            parent_text = clean(parent.get_text()) if parent else ""
            date_hit = date_re.search(parent_text)
            results.append({
                "title": title,
                "url":   url,
                "date":  date_hit.group(0) if date_hit else None,
            })

    return results


def extract_courses(soup: BeautifulSoup) -> list[dict]:
    """
    Extract course / syllabus titles and links.

    Matches links whose text or href contains 'syllabus', 'curriculum',
    'course', or that end in .pdf (PDFs are commonly syllabus documents).
    """
    results  = []
    seen: set[tuple] = set()
    keywords = ["syllabus", "curriculum", "course", "programme", "program"]

    for a in soup.find_all("a", href=True):
        text = clean(a.get_text())
        href = a["href"]
        haystack = (href + " " + text).lower()
        is_match = (
            any(kw in haystack for kw in keywords)
            or href.lower().endswith(".pdf")
        )
        if is_match and text:
            key = (text, abs_url(href))
            if key not in seen:
                seen.add(key)
                results.append({"title": text, "url": abs_url(href)})

    return results


def extract_all_text(soup: BeautifulSoup) -> str:
    """Return the entire visible text of the page body, whitespace-collapsed."""
    for tag in soup(["script", "style", "noscript", "meta", "link"]):
        tag.decompose()
    body = soup.find("body") or soup
    return clean(body.get_text(separator=" "))


# ── Main pipeline ─────────────────────────────────────────────────────────────
def scrape() -> dict:
    soup = fetch_page(TARGET_URL)
    if soup is None:
        print("[FATAL] Could not retrieve the page. Aborting.", file=sys.stderr)
        sys.exit(1)

    time.sleep(REQUEST_DELAY)

    data = {
        "source_url":  TARGET_URL,
        "scraped_at":  time.strftime("%Y-%m-%d %H:%M:%S"),
        "departments": extract_departments(soup),
        "faculty":     extract_faculty(soup),
        "notices":     extract_notices(soup),
        "courses":     extract_courses(soup),
        "all_text":    extract_all_text(soup),
    }

    print(f"\n  Departments : {len(data['departments'])}")
    print(f"  Faculty     : {len(data['faculty'])}")
    print(f"  Notices     : {len(data['notices'])}")
    print(f"  Courses     : {len(data['courses'])}")
    print(f"  Text length : {len(data['all_text'])} chars")

    return data


def main():
    data = scrape()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()