# -*- coding: utf-8 -*-
"""
Xây dựng mạng lưới Trường đại học - Cựu sinh viên (Wikipedia tiếng Việt)
- Lấy wikitext + links của 1 node
- Tạo seed set từ danh sách trường
- Tìm category "Cựu sinh viên <Trường>" => liệt kê cá nhân
- Trích Infobox person để xác nhận alma_mater/education ~ tên trường
- Tạo edges: (University)-[:GRADUATED {year?}]->(Person)
- Xuất CSV: universities.csv, persons.csv, alumni_edges.csv
"""

import re, time, json, csv
import requests
import mwparserfromhell as mw
import pandas as pd
from slugify import slugify

WIKI_API = "https://vi.wikipedia.org/w/api.php"
UA = "UET-UnivAlumniGraph/0.1 (contact: your_email@example.com)"
SLEEP = 0.25
# === knobs để mở rộng nhanh ===
LINKS_PER_PAGE_LIMIT = 120   # tối đa bao nhiêu link xử lý mỗi trang
PERSON_MODE = "person"       # "student" (chặt) hoặc "person" (nới)
TARGET_TOTAL_NODES = 1000    # dừng khi Persons + Universities >= mốc này
VERBOSE = True               # in tiến độ

session = requests.Session()
session.headers.update({"User-Agent": UA})

# ------------------------------
# 1) Helpers: MediaWiki access
# ------------------------------
def api(params):
    r = session.get(WIKI_API, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def get_pageid_and_title(title):
    data = api({
        "action":"query","format":"json","prop":"info","titles":title,"redirects":1
    })
    page = next(iter(data["query"]["pages"].values()))
    if "missing" in page: return None, None
    return page["pageid"], page["title"]

def get_wikitext(title):
    data = api({
        "action":"query","format":"json","prop":"revisions","rvprop":"content",
        "titles":title,"redirects":1
    })
    page = next(iter(data["query"]["pages"].values()))
    if "revisions" not in page: return None
    # Handle legacy content slot
    rev = page["revisions"][0]
    return rev.get("*") or rev.get("slots",{}).get("main",{}).get("*")

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
    if LINKS_PER_PAGE_LIMIT:
        out = out[:LINKS_PER_PAGE_LIMIT]
    return out

def is_person_page(wtxt):
    if not wtxt: return False
    code = mw.parse(wtxt)
    for t in code.filter_templates():
        nm = t.name.strip().lower()
        if "infobox" in nm and any(k in nm for k in ["person","nhân vật","biography","người","people"]):
            return True
    return False

def list_category_members(cat_title, limit=5000):
    """cat_title: ví dụ 'Thể loại:Cựu sinh viên Đại học Harvard' """
    out, cont = [], {}
    while True:
        params = {
            "action":"query","format":"json","list":"categorymembers","cmtitle":cat_title,
            "cmlimit":min(500, limit),"cmnamespace":"0", **cont
        }
        data = api(params)
        cms = data.get("query",{}).get("categorymembers",[])
        out += [cm["title"] for cm in cms]
        if "continue" in data and len(out) < limit:
            cont = data["continue"]; time.sleep(SLEEP); continue
        break
    return out

# ------------------------------
# 2) Parse infobox (person/university)
# ------------------------------
def extract_infobox(wikitext):
    if not wikitext: return {}
    code = mw.parse(wikitext)
    for t in code.filter_templates():
        name = t.name.strip().lower()
        if name.startswith("infobox") or "hộp thông tin" in name or "infobox" in name:
            info={}
            for p in t.params:
                k = str(p.name).strip()
                v = str(p.value).strip()
                info[k]=v
            return info
    return {}

def text_clean(s):
    if not s: return ""
    # loại bỏ markup đơn giản
    s = re.sub(r"\{\{.*?\}\}", " ", s)
    s = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"<.*?>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def guess_grad_year(info):
    """
    Tìm năm tốt nghiệp từ vài khóa phổ biến; nếu không có, bắt số có 4 chữ số trong education.
    """
    candidates = []
    for key in info.keys():
        low = key.lower()
        if any(k in low for k in ["tốt nghiệp","graduat","degree","bằng cấp","học vị"]):
            candidates.append(text_clean(info[key]))
    if "education" in info: candidates.append(text_clean(info["education"]))
    if "alma_mater" in info: candidates.append(text_clean(info["alma_mater"]))
    if "giáo dục" in info: candidates.append(text_clean(info["giáo dục"]))
    blob = " ; ".join([c for c in candidates if c])
    m = re.search(r"(19|20)\d{2}", blob)
    return int(m.group(0)) if m else None

def info_blob(info):
    """Ghép key và value để tiện tìm kiếm chuỗi."""
    pairs = []
    for k,v in info.items():
        pairs.append(f"{k}: {text_clean(v)}")
    return " | ".join(pairs).lower()

# ------------------------------
# 3) Matching University <-> Person
# ------------------------------
def normalize_title(t):
    # để so khớp mềm, dùng slug nhưng vẫn giữ bản gốc để xuất CSV
    return slugify(t.replace("Đại học","").replace("Trường đại học","").strip())

def person_has_university(person_info, uni_title):
    """
    Heuristic: kiểm tra xem trong các field education/alma_mater/... có chứa tên trường.
    Dùng 2 lớp: (1) so khớp chuỗi thô; (2) so khớp slug rút gọn.
    """
    blob = info_blob(person_info)
    if not blob: return False
    uni_variants = set()
    uni_variants.add(uni_title)
    # thêm vài biến thể tiếng Anh nếu trang trường có
    # (tối giản: tách ngoặc, cắt 'Đại học', tạo slug)
    base = re.sub(r"\(.*?\)", "", uni_title).strip()
    uni_variants.add(base)
    uni_variants.add(base.replace("Đại học","").strip())
    uni_variants_slugs = {normalize_title(u) for u in uni_variants}

    # lớp 1: tìm chuỗi thô (không dấu chính xác 100% nhưng hữu ích)
    for u in uni_variants:
        if u.lower() in blob: 
            return True
    # lớp 2: slug matching
    blob_slug = slugify(blob)
    for us in uni_variants_slugs:
        if us and us in blob_slug:
            return True
    return False

# ------------------------------
# 4) Main pipeline
# ------------------------------
def crawl_university(uni_title):
    """
    - Lấy pageid, title chuẩn
    - Lấy liên kết (links) của trang trường (để bạn có 'truy cập 1 node & các liên kết')
    - Tìm Category "Cựu sinh viên <Trường>" (và biến thể) => danh sách ứng viên alumni
    """
    pageid, norm_title = get_pageid_and_title(uni_title)
    if not pageid:
        print(f"[WARN] Không tìm thấy trang '{uni_title}'")
        return None

    links = get_links(norm_title, pllimit=500)

    # Heuristics cho tên category alumni (tiếng Việt & Anh)
    cat_titles = [
        f"Thể loại:Cựu sinh viên {norm_title}",
        f"Thể loại:Cựu sinh viên của {norm_title}",
        f"Category:Alumni of {norm_title}",                    # đôi khi có category EN được liên kết
        f"Thể loại:Người từng học tại {norm_title}",
    ]
    candidates = set()
    for cat in cat_titles:
        try:
            members = list_category_members(cat, limit=2000)
            candidates.update(members)
            time.sleep(SLEEP)
        except Exception:
            pass

    return {
        "pageid": pageid,
        "title": norm_title,
        "links": links,
        "alumni_candidates": sorted(candidates)
    }

def build_graph(universities, max_people_per_uni=200):
    univ_rows, person_rows, edge_rows = [], [], []
    seen_person = set()

    for uni in universities:
        pack = crawl_university(uni)
        if not pack:
            continue

        # lưu university node
        univ_rows.append({
            "university_title": pack["title"],
            "university_pageid": pack["pageid"],
            "out_links_count": len(pack["links"]),
        })

        # xác nhận alumni theo infobox
        count_ok = 0
        for person_title in pack["alumni_candidates"]:
            if count_ok >= max_people_per_uni: break
            wtxt = get_wikitext(person_title)
            if not wtxt: 
                time.sleep(SLEEP); continue
            info = extract_infobox(wtxt)
            if not info:
                time.sleep(SLEEP); continue

            # chế độ chọn node
            if PERSON_MODE == "student":
                if not is_student_like(wtxt, info):
                    time.sleep(SLEEP); continue
            else:  # PERSON_MODE == "person"
                if not is_person_page(wtxt):
                    time.sleep(SLEEP); continue
            if person_has_university(info, pack["title"]):
                # person node (unique)
                if person_title not in seen_person:
                    seen_person.add(person_title)
                    person_rows.append({
                        "person_title": person_title
                    })

                # edge
                year = guess_grad_year(info)
                edge_rows.append({
                    "university_title": pack["title"],
                    "person_title": person_title,
                    "relation": "GRADUATED",
                    "year": year if year else ""
                })
                count_ok += 1

            time.sleep(SLEEP)

        print(f"[OK] {pack['title']}: {count_ok}/{len(pack['alumni_candidates'])} alumni matched")

    return pd.DataFrame(univ_rows), pd.DataFrame(person_rows), pd.DataFrame(edge_rows)

# ------------------------------
# 5) Run
# ------------------------------
if __name__ == "__main__":
    # ======= (A) “Truy cập 1 node & các liên kết” — ví dụ minh họa =======
    EXAMPLE_NODE = "Đại học Harvard"
    wtxt = get_wikitext(EXAMPLE_NODE)
    links = get_links(EXAMPLE_NODE, pllimit=200)
    print(f"[Node] {EXAMPLE_NODE} có {len(links)} liên kết nội bộ. Ví dụ 10 link đầu:")
    print(links[:10])

    # ======= (B) “Tập hạt giống & danh sách ban đầu” cho mạng =======
    # Bạn có thể mở rộng danh sách này để đạt >= 1000 nút ở giai đoạn sau.
    seed_universities = [
        "Đại học Harvard",
        "Đại học Stanford",
        "Đại học Oxford",
        "Đại học Cambridge",
        "Viện Công nghệ Massachusetts",
        "Đại học Quốc gia Seoul",
        "Đại học Tokyo",
        "Đại học Quốc gia Singapore",
        "Đại học Melbourne",
        "Đại học Toronto",
    ]

    df_uni, df_person, df_edge = build_graph(seed_universities, max_people_per_uni=200)

    # Xuất CSV
    df_uni.to_csv("universities.csv", index=False, encoding="utf-8-sig")
    df_person.drop_duplicates().to_csv("persons.csv", index=False, encoding="utf-8-sig")
    df_edge.to_csv("alumni_edges.csv", index=False, encoding="utf-8-sig")

    # Lưu “danh sách ban đầu” (seed + hàng xóm đầu) cho kiểm tra nhanh
    init_list = {
        "seed_universities": seed_universities,
        "example_node_links": links[:50],
    }
    with open("initial_list.json","w",encoding="utf-8") as f:
        json.dump(init_list, f, ensure_ascii=False, indent=2)

    print("[DONE] Xuất universities.csv, persons.csv, alumni_edges.csv, initial_list.json")
