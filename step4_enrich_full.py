# -*- coding: utf-8 -*-
"""
Step 4 — Enrich from vi.wikipedia (re-crawl persons & universities, include roots)
- Đọc:
    graph_out/nodes_persons.csv          (title)
    graph_out/nodes_universities.csv     (title)
    graph_out/root_nodes.csv             (title,type)
- Re-crawl để tạo QUAN HỆ:
    1) Person -> Person : LINKS_TO (anchor sang person)
    2) Person -> Person : MENTIONS_PERSON (anchor sang person; đồng nhất với links nhưng tách label theo yêu cầu)
    3) Person -> Univ.  : MENTIONS_UNIVERSITY (anchor sang trường)
    4) Univ.  -> Person : UNI_MENTIONS_PERSON (anchor sang person)
    5) Person -> Univ.  : ALUMNI_OF (từ education/infobox person, có year nếu suy ra)
    6) Person <-> Person: SHARED_UNI (>=1 trường chung; count = |intersection|)
- Node properties:
    - nodes_persons_props.csv(title, infobox_json)
    - nodes_universities_props.csv(title, infobox_json)
- Đa luồng, giới hạn để test nhanh.

Yêu cầu utils_wiki.py:
  fetch_parse_html, soup_from_html, extract_page_links,
  extract_person_education, is_person_page, normalize
"""

import os, csv, json, argparse, re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils_wiki import (
    fetch_parse_html, soup_from_html, extract_page_links,
    extract_person_education, is_person_page, normalize
)

# tqdm (nếu có)
try:
    from tqdm import tqdm
    HAS_TQDM = True
except Exception:
    HAS_TQDM = False

YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# ---------- helpers ----------
def safe_fetch(title, sleep=0.06, http_timeout=6.0):
    try:
        return fetch_parse_html(title, sleep=sleep, timeout=http_timeout)
    except TypeError:
        return fetch_parse_html(title, sleep=sleep)

def infer_year_from_text(val):
    if isinstance(val, str):
        m = YEAR_RE.search(val)
        return int(m.group(0)) if m else None
    if isinstance(val, list):
        for x in val:
            m = YEAR_RE.search(str(x))
            if m: return int(m.group(0))
    return None

def load_titles_from_csv(path, col, limit=None):
    out = []
    if not os.path.exists(path): return out
    with open(path, "r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            t = (r.get(col) or "").strip()
            if t: out.append(t)
            if limit and len(out) >= limit: break
    return out

def load_roots(path, limit_persons=None, limit_unis=None):
    persons, unis = [], []
    if not os.path.exists(path): return persons, unis
    with open(path, "r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            t  = (r.get("title") or "").strip()
            ty = (r.get("type")  or "").strip().lower()
            if not t: continue
            if ty == "person":      persons.append(t)
            elif ty == "university": unis.append(t)
    if limit_persons: persons = persons[:limit_persons]
    if limit_unis:    unis    = unis[:limit_unis]
    return persons, unis

def dedupe_norm(rows):
    seen, out = set(), []
    for r in rows:
        key = tuple(normalize(x) if isinstance(x, str) else x for x in r)
        if key in seen: continue
        seen.add(key)
        out.append(r)
    return out

def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(header)
        for r in rows: w.writerow(list(r))
    return len(rows)

# ---------- workers ----------
def worker_person(title, people_norm, uni_norm, sleep, http_timeout):
    """
    Crawl trang PERSON:
      - anchors → people: LINKS_TO + MENTIONS_PERSON
      - anchors → unis  : MENTIONS_UNIVERSITY
      - education       : ALUMNI_OF (P -> U) with year?
      - infobox         : lưu JSON
    """
    out = {
        "links_pp": [],        # (P,P,"LINKS_TO")
        "mentions_pp": [],     # (P,P,"MENTIONS_PERSON")
        "mentions_pu": [],     # (P,U,"MENTIONS_UNIVERSITY")
        "alumni_pu": [],       # (P,U,"ALUMNI_OF", year|"" )
        "infobox_json": "{}"
    }
    try:
        html, _ = safe_fetch(title, sleep=sleep, http_timeout=http_timeout)
        soup = soup_from_html(html)
        if not soup:
            return out

        # 0) collect infobox as JSON-ish dict (best-effort)
        infobox = {}
        try:
            box = soup.find("table", {"class": re.compile(r"\binfobox\b", re.I)})
            if box:
                for tr in box.find_all("tr"):
                    th = tr.find("th"); td = tr.find("td")
                    if not th or not td: continue
                    key = th.get_text(strip=True)
                    if not key: continue
                    if td.find("br"):
                        val = [t.strip() for t in td.stripped_strings]
                    else:
                        val = td.get_text(separator=" ", strip=True)
                    infobox[key] = val
        except Exception:
            pass
        out["infobox_json"] = json.dumps(infobox, ensure_ascii=False)

        # 1) anchors from page
        anchors = extract_page_links(soup) or []
        n_title = normalize(title)
        for lk in anchors:
            n = normalize(lk)
            if n in people_norm:
                out["links_pp"].append((title, lk, "LINKS_TO"))
                out["mentions_pp"].append((title, lk, "MENTIONS_PERSON"))
            elif n in uni_norm:
                out["mentions_pu"].append((title, lk, "MENTIONS_UNIVERSITY"))

        # 2) education -> alumni_of (P -> U)
        if is_person_page(soup):
            edu = extract_person_education(soup) or []
            cleaned = []
            for u,y in edu:
                yy = y if y is not None else infer_year_from_text(u)
                cleaned.append((u, yy))
            for u, yy in cleaned:
                if normalize(u) in uni_norm:
                    out["alumni_pu"].append((title, u, "ALUMNI_OF", "" if yy is None else str(yy)))

        return out
    except Exception:
        return out

def worker_university(title, people_norm, sleep, http_timeout):
    """
    Crawl trang UNIVERSITY:
      - anchors → people: UNI_MENTIONS_PERSON
      - infobox         : lưu JSON
    """
    out = {
        "uni_mentions_p": [],  # (U,P,"UNI_MENTIONS_PERSON")
        "infobox_json": "{}"
    }
    try:
        html, _ = safe_fetch(title, sleep=sleep, http_timeout=http_timeout)
        soup = soup_from_html(html)
        if not soup:
            return out

        # infobox
        infobox = {}
        try:
            box = soup.find("table", {"class": re.compile(r"\binfobox\b", re.I)})
            if box:
                for tr in box.find_all("tr"):
                    th = tr.find("th"); td = tr.find("td")
                    if not th or not td: continue
                    key = th.get_text(strip=True)
                    if not key: continue
                    if td.find("br"):
                        val = [t.strip() for t in td.stripped_strings]
                    else:
                        val = td.get_text(separator=" ", strip=True)
                    infobox[key] = val
        except Exception:
            pass
        out["infobox_json"] = json.dumps(infobox, ensure_ascii=False)

        # anchors
        anchors = extract_page_links(soup) or []
        for lk in anchors:
            if normalize(lk) in people_norm:
                out["uni_mentions_p"].append((title, lk, "UNI_MENTIONS_PERSON"))
        return out
    except Exception:
        return out

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Step 4 — Re-crawl to add edges & node properties (include roots).")
    ap.add_argument("--outdir", default="graph_out")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--http-timeout", type=float, default=6.0)
    ap.add_argument("--sleep", type=float, default=0.06)

    # testing limits
    ap.add_argument("--limit-persons", type=int, default=None)
    ap.add_argument("--limit-universities", type=int, default=None)

    # input file names (under outdir)
    ap.add_argument("--persons-csv", default="nodes_persons.csv")
    ap.add_argument("--universities-csv", default="nodes_universities.csv")
    ap.add_argument("--roots-csv", default="root_nodes.csv")
    args = ap.parse_args()

    odir = args.outdir
    os.makedirs(odir, exist_ok=True)

    # 1) Load current nodes + add roots
    persons_nodes = load_titles_from_csv(os.path.join(odir, args.persons_csv), "title")
    unis_nodes    = load_titles_from_csv(os.path.join(odir, args.universities_csv), "title")
    roots_p, roots_u = load_roots(os.path.join(odir, args.roots_csv))

    persons_all = []
    persons_all.extend(persons_nodes)
    persons_all.extend(roots_p)
    # unique, preserve order
    seen = set(); persons_all = [x for x in persons_all if not (x in seen or seen.add(x))]

    unis_all = []
    unis_all.extend(unis_nodes)
    unis_all.extend(roots_u)
    seen = set(); unis_all = [x for x in unis_all if not (x in seen or seen.add(x))]

    if args.limit_persons:     persons_all = persons_all[:args.limit_persons]
    if args.limit_universities: unis_all   = unis_all[:args.limit_universities]

    print(f"Persons to crawl     : {len(persons_all)}")
    print(f"Universities to crawl: {len(unis_all)}")

    people_norm = {normalize(t) for t in persons_all}
    uni_norm    = {normalize(t) for t in unis_all}

    # outputs
    links_pp, mentions_pp, mentions_pu, uni_mentions_p = [], [], [], []
    alumni_pu = []
    person_props, uni_props = [], []

    # 2) crawl persons
    print("🧭 Crawling PERSON pages…")
    iterable = tqdm(persons_all, desc="Persons", unit="p") if HAS_TQDM else persons_all
    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as ex:
        futs = {ex.submit(worker_person, p, people_norm, uni_norm, args.sleep, args.http_timeout): p
                for p in persons_all}
        for fut in as_completed(futs):
            r = fut.result()
            links_pp.extend(r.get("links_pp", []))
            mentions_pp.extend(r.get("mentions_pp", []))
            mentions_pu.extend(r.get("mentions_pu", []))
            alumni_pu.extend(r.get("alumni_pu", []))
            # capture infobox
            # title ở key của map: không có; ta không biết title khi join → bỏ qua ở đây.
            # Sửa: worker trả về infobox_json, nhưng không kèm title, nên chúng ta không append ở đây.
            # Cập nhật: gọi lại với title lấy infobox riêng.
        # lấy properties tách bước (đảm bảo có title)
    # lấy infobox (persons) riêng (ít tốn thời gian thêm)
    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as ex:
        futs = {ex.submit(safe_fetch, p, args.sleep, args.http_timeout): p for p in persons_all}
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                html, _ = fut.result()
                soup = soup_from_html(html)
                infobox = {}
                if soup:
                    box = soup.find("table", {"class": re.compile(r"\binfobox\b", re.I)})
                    if box:
                        for tr in box.find_all("tr"):
                            th = tr.find("th"); td = tr.find("td")
                            if not th or not td: continue
                            key = th.get_text(strip=True)
                            if not key: continue
                            if td.find("br"):
                                val = [t.strip() for t in td.stripped_strings]
                            else:
                                val = td.get_text(separator=" ", strip=True)
                            infobox[key] = val
                person_props.append((p, json.dumps(infobox, ensure_ascii=False)))
            except Exception:
                person_props.append((p, "{}"))

    # 3) crawl universities
    print("🏛️ Crawling UNIVERSITY pages…")
    iterable = tqdm(unis_all, desc="Universities", unit="u") if HAS_TQDM else unis_all
    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as ex:
        futs = {ex.submit(worker_university, u, people_norm, args.sleep, args.http_timeout): u
                for u in unis_all}
        for fut in as_completed(futs):
            r = fut.result()
            uni_mentions_p.extend(r.get("uni_mentions_p", []))
    # infobox (universities)
    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as ex:
        futs = {ex.submit(safe_fetch, u, args.sleep, args.http_timeout): u for u in unis_all}
        for fut in as_completed(futs):
            u = futs[fut]
            try:
                html, _ = fut.result()
                soup = soup_from_html(html)
                infobox = {}
                if soup:
                    box = soup.find("table", {"class": re.compile(r"\binfobox\b", re.I)})
                    if box:
                        for tr in box.find_all("tr"):
                            th = tr.find("th"); td = tr.find("td")
                            if not th or not td: continue
                            key = th.get_text(strip=True)
                            if not key: continue
                            if td.find("br"):
                                val = [t.strip() for t in td.stripped_strings]
                            else:
                                val = td.get_text(separator=" ", strip=True)
                            infobox[key] = val
                uni_props.append((u, json.dumps(infobox, ensure_ascii=False)))
            except Exception:
                uni_props.append((u, "{}"))

    # 4) dedupe theo normalize
    links_pp       = dedupe_norm(links_pp)
    mentions_pp    = dedupe_norm(mentions_pp)
    mentions_pu    = dedupe_norm(mentions_pu)
    uni_mentions_p = dedupe_norm(uni_mentions_p)
    alumni_pu      = dedupe_norm(alumni_pu)

    # 5) build SHARED_UNI từ alumni_pu (P->U)
    # edu_map: person -> set(unis)
    edu_map = defaultdict(set)
    for p, u_rel, rel, y in [(p,u,rel,y) for (p,u,rel,y) in alumni_pu]:
        if rel == "ALUMNI_OF":
            edu_map[p].add(u_rel)
    shared_uni = []  # (p1, p2, "SHARED_UNI", count)
    # pairwise by uni: invert then pairs
    inv_uni = defaultdict(list)  # U -> [P]
    for p, us in edu_map.items():
        for u in us:
            inv_uni[u].append(p)
    seen_pairs = set()
    for u, plist in inv_uni.items():
        n = len(plist)
        for i in range(n):
            for j in range(i+1, n):
                a, b = sorted((plist[i], plist[j]))
                key = (normalize(a), normalize(b))
                if key in seen_pairs: continue
                seen_pairs.add(key)
                cnt = len(edu_map[a] & edu_map[b])
                if cnt > 0:
                    shared_uni.append((a, b, "SHARED_UNI", cnt))

    # 6) write outputs
    n1 = write_csv(os.path.join(odir, "edges_links_pp.csv"),        ["src_person","dst_person","relation"], links_pp)
    n2 = write_csv(os.path.join(odir, "edges_mentions_pp.csv"),     ["src_person","dst_person","relation"], mentions_pp)
    n3 = write_csv(os.path.join(odir, "edges_mentions_pu.csv"),     ["src_person","dst_university","relation"], mentions_pu)
    n4 = write_csv(os.path.join(odir, "edges_uni_mentions_p.csv"),  ["src_university","dst_person","relation"], uni_mentions_p)
    n5 = write_csv(os.path.join(odir, "edges_alumni_pu.csv"),       ["src_person","dst_university","relation","year"], alumni_pu)
    n6 = write_csv(os.path.join(odir, "edges_shared_uni_pp.csv"),   ["src_person","dst_person","relation","count"], shared_uni)

    write_csv(os.path.join(odir, "nodes_persons_props.csv"),        ["title","infobox_json"], person_props)
    write_csv(os.path.join(odir, "nodes_universities_props.csv"),   ["title","infobox_json"], uni_props)

    summary = {
        "persons_crawled": len(persons_all),
        "universities_crawled": len(unis_all),
        "edges_links_pp": n1,
        "edges_mentions_pp": n2,
        "edges_mentions_pu": n3,
        "edges_uni_mentions_p": n4,
        "edges_alumni_pu": n5,
        "edges_shared_uni_pp": n6,
        "node_props_persons": len(person_props),
        "node_props_universities": len(uni_props)
    }
    with open(os.path.join(odir, "step4_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n✅ STEP 4 DONE")
    for k,v in summary.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
