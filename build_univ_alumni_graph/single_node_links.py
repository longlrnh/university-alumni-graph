# -*- coding: utf-8 -*-
"""
Bước 1 — Lấy liên kết nội bộ của 1 trang Wikipedia (vi).
- Input: --title "Tên trang" (VD: "Đại học Harvard")
- Output:
  - links.csv  : (source_title, target_title)
  - info.json  : {title, infobox, links_count}
"""
import argparse, json, time, csv
import requests, requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import mwparserfromhell as mw

WIKI_API = "https://vi.wikipedia.org/w/api.php"
UA = "UET-OneNodeLinks/0.1 (contact: your_email@example.com)"
REQ_TIMEOUT = 8
SLEEP = 0.25

# Session có cache + retry
session = requests_cache.CachedSession(
    'viwiki_cache',
    expire_after=7*24*3600,
    allowable_methods=('GET',),
    stale_if_error=True,
)
session.headers.update({"User-Agent": UA})
retry = Retry(total=5, backoff_factor=0.6,
              status_forcelist=[429, 500, 502, 503, 504],
              allowed_methods=["GET"])
adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
session.mount("https://", adapter)
session.mount("http://", adapter)

def api(params):
    r = session.get(WIKI_API, params=params, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    return r.json()

def canonical_title(title):
    data = api({"action":"query","format":"json","prop":"info","titles":title,"redirects":1})
    page = next(iter(data["query"]["pages"].values()))
    return None if "missing" in page else page["title"]

def get_links(title, namespace="0", limit_per_call=500):
    links, cont = [], {}
    while True:
        params = {
            "action":"query","format":"json",
            "prop":"links","titles":title,
            "plnamespace":namespace,"pllimit":limit_per_call,
            **cont
        }
        data = api(params)
        page = next(iter(data["query"]["pages"].values()))
        if "links" in page:
            links.extend([it["title"] for it in page["links"]])
        if "continue" in data:
            cont = data["continue"]; time.sleep(SLEEP); continue
        break
    return links

def get_wikitext(title):
    data = api({"action":"query","format":"json","prop":"revisions","rvprop":"content",
                "titles":title,"redirects":1})
    page = next(iter(data["query"]["pages"].values()))
    if "revisions" not in page: return None
    rev = page["revisions"][0]
    return rev.get("*") or rev.get("slots",{}).get("main",{}).get("*")

def detect_infobox_name(wikitext):
    if not wikitext: return None
    code = mw.parse(wikitext)
    for t in code.filter_templates():
        nm = t.name.strip()
        if "infobox" in nm.lower() or "hộp thông tin" in nm.lower():
            return nm
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True, help="Tên trang Wikipedia (vi)")
    ap.add_argument("--namespace", default="0", help="Namespace liên kết (mặc định 0)")
    ap.add_argument("--out-links", default="links.csv", help="File CSV xuất link")
    ap.add_argument("--out-info", default="info.json", help="File JSON mô tả node")
    args = ap.parse_args()

    title = canonical_title(args.title)
    if not title:
        print(f"[ERR] Không tìm thấy trang: {args.title}")
        return

    links = get_links(title, namespace=args.namespace)
    print(f"[OK] '{title}' có {len(links)} liên kết nội bộ (ns={args.namespace}). Ví dụ 10 link đầu:")
    print(links[:10])

    wtxt = get_wikitext(title)
    infobox_name = detect_infobox_name(wtxt)

    # Xuất CSV
    with open(args.out_links, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["source_title", "target_title"])
        for t in links:
            w.writerow([title, t])

    # Xuất JSON
    info = {"title": title, "infobox": infobox_name, "links_count": len(links)}
    with open(args.out_info, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Lưu {args.out_links} và {args.out_info}")

if __name__ == "__main__":
    main()
    