# -*- coding: utf-8 -*-
"""
Bước 2 — Tạo TẬP HẠT GIỐNG (seeds) & DANH SÁCH BAN ĐẦU từ node gốc và các liên kết của nó
KHÔNG dùng category/list/global index.

Đầu vào:
- Cách A: dùng file links.csv (tạo ở Bước 1) -> --links-csv links.csv
- Cách B: lấy trực tiếp từ --title "Tên trang" (sẽ tự gọi API lấy liên kết)

Đầu ra:
- seeds.csv             : danh sách sinh viên/người (bao gồm node gốc nếu hợp lệ)
- person_edges.csv      : cạnh root -> person (LINK_FROM_START), kèm shared_universities nếu có
- edu_edges.csv         : cạnh University -> Person (GRADUATED) trích từ infobox
"""

import argparse, re, time, os, csv
import pandas as pd
import requests, requests_cache
import mwparserfromhell as mw
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

WIKI_API = "https://vi.wikipedia.org/w/api.php"
UA = "UET-SeedInitialOnlyFromLinks/0.1 (contact: your_email@example.com)"
REQ_TIMEOUT = 8
SLEEP = 0.25

# ---------- session: cache + retry ----------
session = requests_cache.CachedSession(
    'viwiki_seed_from_links_cache',
    expire_after=7*24*3600,
    allowable_methods=('GET',),
    stale_if_error=True,
)
session.headers.update({"User-Agent": UA})
retry = Retry(total=5, backoff_factor=0.6, status_forcelist=[429,500,502,503,504], allowed_methods=["GET"])
adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
session.mount("https://", adapter)
session.mount("http://", adapter)

def api(params):
    r = session.get(WIKI_API, params=params, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    return r.json()

# ---------- MediaWiki helpers ----------
def canonical_title(title):
    data = api({"action":"query","format":"json","prop":"info","titles":title,"redirects":1})
    page = next(iter(data["query"]["pages"].values()))
    return None if "missing" in page else page["title"]

def get_links(title, ns="0", limit_per_call=500):
    out, cont = [], {}
    while True:
        params = {"action":"query","format":"json","prop":"links","titles":title,
                  "plnamespace":ns,"pllimit":limit_per_call, **cont}
        data = api(params)
        page = next(iter(data["query"]["pages"].values()))
        if "links" in page:
            out += [it["title"] for it in page["links"]]
        if "continue" in data:
            cont = data["continue"]; time.sleep(SLEEP); continue
        break
    return out

def get_wikitext(title):
    try:
        data = api({"action":"query","format":"json","prop":"revisions","rvprop":"content","titles":title,"redirects":1})
        page = next(iter(data["query"]["pages"].values()))
        if "revisions" not in page: return None
        rev = page["revisions"][0]
        return rev.get("*") or rev.get("slots",{}).get("main",{}).get("*")
    except Exception:
        return None

# ---------- parsing & rules (NO category/list) ----------
def is_list_page(title:str)->bool:
    tl = title.lower().strip()
    return tl.startswith("danh sách ") or "danh sách" in tl or "list of " in tl

def extract_infobox_dict(wikitext):
    if not wikitext: return {}
    code = mw.parse(wikitext)
    for t in code.filter_templates():
        nm = t.name.strip().lower()
        if "infobox" in nm or "hộp thông tin" in nm:
            d = {}
            for p in t.params:
                d[str(p.name).strip()] = str(p.value).strip()
            return d
    return {}

def is_person_infobox(wikitext):
    if not wikitext: return False
    code = mw.parse(wikitext)
    for t in code.filter_templates():
        nm = t.name.strip().lower()
        if "infobox" in nm and any(k in nm for k in ["nhân vật","person","biography","người","people"]):
            return True
    return False

def text_clean(s):
    if not s: return ""
    s = re.sub(r"\{\{.*?\}\}", " ", s)
    s = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"<.*?>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def universities_from_person_info(info:dict):
    keys = ["education","alma_mater","giáo dục","trường","trường học","đào tạo"]
    vals = []
    for k,v in info.items():
        if any(kk in k.lower() for kk in keys):
            vals.append(text_clean(v))
    blob = " ; ".join(vals)
    parts = re.split(r"[;/•|,–—\-]+", blob)
    uni_tokens = ["Đại học","Trường đại học","University","College","Institut","Institute","Universität","Universidade","Université","Polytechnic","MIT","Harvard","Oxford","Cambridge"]
    out=[]; seen=set()
    for p in parts:
        pp = re.sub(r"\(.*?\)","",p).strip()
        if any(tok in pp for tok in uni_tokens) and len(pp)>=3:
            if pp not in seen:
                seen.add(pp); out.append(pp)
    return out

def is_student_like_person(wikitext, info):
    # Định nghĩa “người cần tìm”: Có Infobox Person + có field học tập
    if not is_person_infobox(wikitext):
        return False
    keyblob = " ".join(k.lower() for k in info.keys())
    return ("education" in keyblob) or ("alma_mater" in keyblob) or ("giáo dục" in keyblob) or ("trường" in keyblob)

# ---------- main logic ----------
def build_seeds_from_links(root_title=None, links_csv=None, out_dir="data_seed"):
    os.makedirs(out_dir, exist_ok=True)

    if links_csv:
        df = pd.read_csv(links_csv, encoding="utf-8-sig")
        # xác định root từ cột source_title (giả sử file từ Bước 1)
        if "source_title" not in df.columns or "target_title" not in df.columns:
            raise ValueError("links.csv phải có cột source_title,target_title")
        root = df["source_title"].iloc[0]
        links = df["target_title"].tolist()
    else:
        if not root_title:
            raise ValueError("Cần --links-csv hoặc --title")
        root = canonical_title(root_title)
        if not root:
            raise ValueError(f"Không tìm thấy trang: {root_title}")
        links = get_links(root, ns="0", limit_per_call=500)

    # bỏ các trang kiểu “danh sách …”
    links = [t for t in links if not is_list_page(t)]
    print(f"[OK] root '{root}' -> {len(links)} link hợp lệ (bỏ List).")

    # lấy thông tin root
    seeds = []
    person_edges = []
    edu_edges = []

    root_wtxt = get_wikitext(root)
    root_info = extract_infobox_dict(root_wtxt)
    root_unis = universities_from_person_info(root_info) if root_info else []

    # nếu root là 1 Person có học tập -> cũng đưa vào seeds
    if is_student_like_person(root_wtxt, root_info):
        seeds.append({"person_title": root, "source": "root", "universities": "; ".join(root_unis)})
        for u in root_unis:
            edu_edges.append({"university_title": u, "person_title": root, "relation": "GRADUATED"})

    for i, t in enumerate(links, 1):
        wtxt = get_wikitext(t)
        if not wtxt:
            time.sleep(SLEEP); continue
        info = extract_infobox_dict(wtxt)
        if not info:
            time.sleep(SLEEP); continue

        if is_student_like_person(wtxt, info):
            unis = universities_from_person_info(info)
            seeds.append({"person_title": t, "source": "linked_from_root", "universities": "; ".join(unis)})

            shared = sorted(set(u for u in unis if u in root_unis))
            person_edges.append({
                "src_person": root,
                "dst_person": t,
                "relation": "LINK_FROM_START",
                "shared_universities": "; ".join(shared)
            })
            for u in unis:
                edu_edges.append({"university_title": u, "person_title": t, "relation": "GRADUATED"})

        if i % 25 == 0:
            print(f"  …đã xét {i}/{len(links)} link")
        time.sleep(SLEEP)

    # xuất
    df_seeds = pd.DataFrame(seeds).drop_duplicates(subset=["person_title"])
    df_pp    = pd.DataFrame(person_edges).drop_duplicates()
    df_up    = pd.DataFrame(edu_edges).drop_duplicates()

    df_seeds.to_csv(os.path.join(out_dir, "seeds.csv"), index=False, encoding="utf-8-sig")
    df_pp.to_csv(os.path.join(out_dir, "person_edges.csv"), index=False, encoding="utf-8-sig")
    df_up.to_csv(os.path.join(out_dir, "edu_edges.csv"), index=False, encoding="utf-8-sig")

    print("[DONE] Đã lưu:")
    print(f"  - {out_dir}/seeds.csv (tập hạt giống sinh viên, từ root & links)")
    print(f"  - {out_dir}/person_edges.csv (root -> người khác)")
    print(f"  - {out_dir}/edu_edges.csv (University -> Person)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--links-csv", help="Đường dẫn links.csv từ Bước 1")
    ap.add_argument("--title", help="Tên trang gốc nếu không dùng links.csv")
    ap.add_argument("--out-dir", default="data_seed")
    args = ap.parse_args()
    build_seeds_from_links(root_title=args.title, links_csv=args.links_csv, out_dir=args.out_dir)
