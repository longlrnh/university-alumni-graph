# -*- coding: utf-8 -*-
import re, time, requests
from bs4 import BeautifulSoup
from urllib.parse import quote

WIKI_HOST = "https://vi.wikipedia.org"
API_PARSE = WIKI_HOST + "/w/api.php?action=parse&page={title}&prop=text|links&format=json"
UA = "UET-AlumniGraph/1.0"
TIMEOUT = 10
HEADERS = {"User-Agent": UA}

EDU_KEYS = [
    "Giáo dục", "Học vấn", "Alma mater",
    "Trường theo học", "Đào tạo", "Trường", "Cơ sở đào tạo"
]

def fetch_parse_html(title, sleep=0.2):
    url = API_PARSE.format(title=quote(title))
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    html = next(iter(data["parse"]["text"].values())) if "parse" in data and "text" in data["parse"] else None
    links = [lk["*"] for lk in data["parse"].get("links", []) if lk.get("exists")]
    time.sleep(sleep)
    return html, links

def soup_from_html(html):
    return BeautifulSoup(html, "html.parser") if html else None

def normalize(t):
    if not t: return None
    return re.sub(r"\s+", " ", t).strip()

def is_person_page(soup):
    if not soup: return False
    infobox = soup.find("table", class_=lambda c: c and "infobox" in c)
    if not infobox: return False
    for tr in infobox.find_all("tr"):
        th = tr.find("th")
        if th and re.search(r"\bSinh\b", th.get_text(strip=True), flags=re.I):
            return True
    return False

def extract_page_links(soup):
    out = []
    if not soup: return out
    content = soup.find("div", id="mw-content-text") or soup
    seen = set()
    for a in content.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/wiki/") and not (":" in href or "#" in href):
            title = normalize(a.get("title") or a.get_text(strip=True))
            if title and title not in seen:
                seen.add(title)
                out.append(title)
    return out

def extract_person_education(soup):
    # Return list of (university_title, year?) from a person page.
    out = []
    if not soup: return out
    infobox = soup.find("table", class_=lambda c: c and "infobox" in c)
    if not infobox: return out

    for tr in infobox.find_all("tr"):
        th = tr.find("th"); td = tr.find("td")
        if not th or not td:
            continue
        key = th.get_text(" ", strip=True)
        if key not in EDU_KEYS:
            continue

        uni_titles = []
        for a in td.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/wiki/") and not (":" in href or "#" in href):
                uni_titles.append(normalize(a.get("title") or a.get_text(strip=True)))

        text = td.get_text(" ", strip=True)
        years = re.findall(r"\b(?:19|20)\d{2}\b", text)
        year = int(years[0]) if years else None

        for ut in uni_titles:
            if ut:
                out.append((ut, year))
    return out
