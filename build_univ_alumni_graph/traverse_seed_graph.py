# -*- coding: utf-8 -*-
"""
Mở rộng tập hạt giống thông qua DUYỆT (BFS) chỉ bằng LIÊN KẾT nội bộ.
Không dùng Category/List.
- Bắt đầu từ 1 sinh viên gốc (root_person)
- Person đủ điều kiện = có Infobox Person + có field học tập (education/alma_mater/giáo dục/...)
- Mỗi Person -> trích universities + (năm) nếu có
- Thu thập edges:
    U-[:ALUMNI_OF {year?}]->P
    P-[:LINKS_TO]->P            (nếu A liên kết sang B)
    P-[:SHARED_UNI {count}]->P  (>=1 trường chung)
    P-[:SAME_GRAD_YEAR]->P      (>=1 năm tốt nghiệp trùng)
- Duyệt BFS theo depth, với giới hạn để tránh bùng nổ

Đầu ra:
- nodes_persons.csv
- nodes_universities.csv
- edges_up.csv     (University -> Person)
- edges_pp.csv     (Person -> Person: LINKS_TO / SHARED_UNI / SAME_GRAD_YEAR)
"""

import re, time, os, json, collections
from collections import deque, defaultdict
import requests, requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import mwparserfromhell as mw
import pandas as pd

WIKI_API = "https://vi.wikipedia.org/w/api.php"
UA = "UET-TraverseGraph/0.1 (contact: your_email@example.com)"
REQ_TIMEOUT = 8
SLEEP = 0.25

# ------------ session: cache + retry ------------
session = requests_cache.CachedSession(
    'viwiki_traverse_cache',
    expire_after=7*24*3600,
    allowable_methods=('GET',),
    stale_if_error=True,
)
session.headers.update({"User-Agent": UA})
retry = Retry(total=5, backoff_factor=0.6,
              status_forcelist=[429,500,502,503,504],
              allowed_methods=["GET"])
adapter = HTTPAdapter(max_retries=retry, pool_connections=32, pool_maxsize=32)
session.mount("https://", adapter)
session.mount("http://", adapter)

def api(params):
    r = session.get(WIKI_API, params=params, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    return r.json()

# ------------ wiki helpers ------------
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

# ------------ parsing ------------
def is_list_page(title:str)->bool:
    t = title.lower().strip()
    return t.startswith("danh sách ") or "danh sách" in t or "list of " in t

def extract_infobox(wikitext):
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

def clean(s):
    if not s: return ""
    s = re.sub(r"\{\{.*?\}\}", " ", s)
    s = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"<.*?>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def universities_from_info(info:dict):
    keys = ["education","alma_mater","giáo dục","trường","trường học","đào tạo"]
    vals = []
    for k,v in info.items():
        if any(kk in k.lower() for kk in keys):
            vals.append(clean(v))
    blob = " ; ".join(vals)
    parts = re.split(r"[;/•|,–—\-]+", blob)
    tokens = ["Đại học","Trường đại học","University","College","Institut","Institute","Polytechnic","Universität","Universidade","Université"]
    out, seen = [], set()
    for p in parts:
        pp = re.sub(r"\(.*?\)","",p).strip()
        if any(tok in pp for tok in tokens) and len(pp)>=3:
            if pp not in seen:
                seen.add(pp); out.append(pp)
    return out

def guess_grad_years(info:dict):
    keys = ["tốt nghiệp","graduat","degree","bằng","học vị","education","alma_mater","giáo dục"]
    text = []
    for k,v in info.items():
        if any(kk in k.lower() for kk in keys):
            text.append(clean(v))
    blob = " ; ".join(text)
    years = re.findall(r"\b(19|20)\d{2}\b", blob)
    # years dạng chuỗi "19"/"20" bị bắt bởi nhóm — sửa:
    years_full = re.findall(r"\b(19\d{2}|20\d{2})\b", blob)
    return sorted(set(int(y) for y in years_full))

def is_student_like(wtxt, info):
    if not is_person_infobox(wtxt):
        return False
    keyblob = " ".join(k.lower() for k in info.keys())
    return ("education" in keyblob) or ("alma_mater" in keyblob) or ("giáo dục" in keyblob) or ("trường" in keyblob)

# ------------ traversal ------------
def traverse_from_person(root_person,
                         max_depth=2,
                         max_persons=1500,
                         max_edges=8000,
                         out_dir="graph_out"):
    os.makedirs(out_dir, exist_ok=True)

    root = canonical_title(root_person)
    if not root:
        raise ValueError(f"Không tìm thấy trang: {root_person}")

    # hàng đợi BFS: (depth, person_title)
    Q = deque([(0, root)])
    visitedP = set([root])

    # Kết quả
    persons = {}           # title -> {universities:[], years:[]}
    universities = set()   # tên trường
    edges_up = []          # University -> Person
    edges_pp = []          # Person -> Person  (LINKS_TO / SHARED_UNI / SAME_GRAD_YEAR)

    # Khởi tạo từ root
    root_w = get_wikitext(root)
    root_info = extract_infobox(root_w)
    if root_info and is_student_like(root_w, root_info):
        root_unis = universities_from_info(root_info)
        root_years = guess_grad_years(root_info)
        persons[root] = {"universities": root_unis, "years": root_years}
        for u in root_unis:
            universities.add(u)
            edges_up.append({"university_title": u, "person_title": root, "relation": "ALUMNI_OF", "year": ""})
    else:
        persons[root] = {"universities": [], "years": []}

    total_edges = 0

    while Q and len(persons) < max_persons and total_edges < max_edges:
        depth, p = Q.popleft()
        # lấy links từ p (namespace=0), bỏ trang danh sách
        try:
            links = [t for t in get_links(p, ns="0") if not is_list_page(t)]
        except Exception:
            links = []
        # duyệt các target
        for t in links:
            if total_edges >= max_edges:
                break

            # P -> P (LINKS_TO): trước hết tạo cạnh điều hướng
            edges_pp.append({"src_person": p, "dst_person": t, "relation": "LINKS_TO", "shared_universities": "", "same_grad_year": 0})
            total_edges += 1

            # lấy info của t
            wtxt = get_wikitext(t)
            if not wtxt:
                time.sleep(SLEEP); continue
            info = extract_infobox(wtxt)
            if not info or not is_student_like(wtxt, info):
                time.sleep(SLEEP); continue

            # nếu là "người học", lưu node & cạnh U->P
            unis = universities_from_info(info)
            years = guess_grad_years(info)
            if t not in persons:
                persons[t] = {"universities": unis, "years": years}
            for u in unis:
                universities.add(u)
                edges_up.append({"university_title": u, "person_title": t, "relation": "ALUMNI_OF", "year": ""})

            # P-P phụ thuộc nội dung:
            shared = sorted(set(unis) & set(persons[p]["universities"]))
            if shared:
                edges_pp.append({"src_person": p, "dst_person": t, "relation": "SHARED_UNI", "shared_universities": "; ".join(shared), "same_grad_year": 0})
                total_edges += 1
            if persons[p]["years"] and years and set(persons[p]["years"]) & set(years):
                edges_pp.append({"src_person": p, "dst_person": t, "relation": "SAME_GRAD_YEAR", "shared_universities": "", "same_grad_year": 1})
                total_edges += 1

            # mở rộng BFS nếu chưa quá depth
            if depth + 1 <= max_depth and t not in visitedP:
                visitedP.add(t)
                Q.append((depth+1, t))

            time.sleep(SLEEP)

        # checkpoint nhẹ
        if len(persons) % 50 == 0:
            dump_partial(out_dir, persons, universities, edges_up, edges_pp)

    # xuất kết quả cuối
    return dump_final(out_dir, persons, universities, edges_up, edges_pp)

def dump_partial(out_dir, persons, universities, edges_up, edges_pp):
    dfP = pd.DataFrame([{"person_title": k,
                         "universities": "; ".join(v["universities"]),
                         "years": "; ".join(map(str, v["years"]))} for k,v in persons.items()])
    dfU = pd.DataFrame([{"university_title": u} for u in sorted(universities)])
    dfUP = pd.DataFrame(edges_up)
    dfPP = pd.DataFrame(edges_pp)
    dfP.to_csv(os.path.join(out_dir,"nodes_persons.tmp.csv"), index=False, encoding="utf-8-sig")
    dfU.to_csv(os.path.join(out_dir,"nodes_universities.tmp.csv"), index=False, encoding="utf-8-sig")
    dfUP.to_csv(os.path.join(out_dir,"edges_up.tmp.csv"), index=False, encoding="utf-8-sig")
    dfPP.to_csv(os.path.join(out_dir,"edges_pp.tmp.csv"), index=False, encoding="utf-8-sig")

def dump_final(out_dir, persons, universities, edges_up, edges_pp):
    dfP = pd.DataFrame([{"person_title": k,
                         "universities": "; ".join(v["universities"]),
                         "years": "; ".join(map(str, v["years"]))} for k,v in persons.items()]).drop_duplicates(subset=["person_title"])
    dfU = pd.DataFrame([{"university_title": u} for u in sorted(universities)]).drop_duplicates(subset=["university_title"])
    dfUP = pd.DataFrame(edges_up).drop_duplicates()
    dfPP = pd.DataFrame(edges_pp).drop_duplicates()

    dfP.to_csv(os.path.join(out_dir,"nodes_persons.csv"), index=False, encoding="utf-8-sig")
    dfU.to_csv(os.path.join(out_dir,"nodes_universities.csv"), index=False, encoding="utf-8-sig")
    dfUP.to_csv(os.path.join(out_dir,"edges_up.csv"), index=False, encoding="utf-8-sig")
    dfPP.to_csv(os.path.join(out_dir,"edges_pp.csv"), index=False, encoding="utf-8-sig")

    print("[DONE] Xuất:")
    print(f"  - {out_dir}/nodes_persons.csv")
    print(f"  - {out_dir}/nodes_universities.csv")
    print(f"  - {out_dir}/edges_up.csv   (University -> Person)")
    print(f"  - {out_dir}/edges_pp.csv   (Person -> Person)")

    return dfP, dfU, dfUP, dfPP

if __name__ == "__main__":
    # ví dụ root: 1 nhân vật có trang viwiki (dạng tiếng Việt)
    # Bạn nên đổi thành người bạn muốn.
    dfP, dfU, dfUP, dfPP = traverse_from_person(
        root_person="Mark Zuckerberg",
        max_depth=2,          # 0:root -> 1-hop -> 2-hop
        max_persons=1000,
        max_edges=6000,
        out_dir="graph_out"
    )
