# -*- coding: utf-8 -*-
"""
Step 4 — Enrich (include roots) + Node Details export
- Node details (merged persons + universities) → node_details.csv / node_details.json
  Fields: title, type, link, related, properties
- Edges (no LINKS_TO):
    1) Person -> Person : MENTIONS_PERSON
    2) Person -> Univ.  : MENTIONS_UNIVERSITY
    3) Univ.  -> Person : UNI_MENTIONS_PERSON
    4) Univ.  -> Univ.  : UNIVERSITY_MENTIONS_UNIVERSITY   [NEW]
    5) Person -> Univ.  : ALUMNI_OF (year?)
    6) Person <-> Person: SHARED_UNI (count)
"""

import os, csv, json, argparse, re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils_wiki import (
    fetch_parse_html, soup_from_html, extract_page_links,
    extract_person_education, is_person_page, normalize
)

try:
    from tqdm import tqdm
    HAS_TQDM = True
except Exception:
    HAS_TQDM = False

YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# ---------- helpers ----------
def wiki_link(title: str) -> str:
    # Link Wikipedia tiếng Việt
    from urllib.parse import quote
    return f"https://vi.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"

def safe_fetch(title, sleep=0.06, http_timeout=6.0):
    try:
        return fetch_parse_html(title, sleep=sleep, timeout=http_timeout)  # (html, final_title)
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
            if ty == "person":       persons.append(t)
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

def extract_infobox_json(soup):
    import re as _re
    infobox = {}
    try:
        box = soup.find("table", {"class": _re.compile(r"\binfobox\b", _re.I)})
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
    return json.dumps(infobox, ensure_ascii=False)

# ---------- workers ----------
def worker_person(seed_title, people_norm_seed, uni_norm_seed, sleep, http_timeout):
    """
    Return:
      - title_final
      - edges: mentions_pp, mentions_pu, alumni_pu
      - props: infobox_json
      - anchors_intersect: titles (people or unis) from anchors ∩ seed sets
    """
    out = {
        "title_final": seed_title,
        "mentions_pp": [],     # (P,P,"MENTIONS_PERSON")
        "mentions_pu": [],     # (P,U,"MENTIONS_UNIVERSITY")
        "alumni_pu": [],       # (P,U,"ALUMNI_OF", year|"" )
        "infobox_json": "{}",
        "anchors_intersect": []
    }
    try:
        html, final_title = safe_fetch(seed_title, sleep=sleep, http_timeout=http_timeout)
        if final_title: out["title_final"] = final_title
        soup = soup_from_html(html)
        if not soup: return out

        tperson = out["title_final"]
        out["infobox_json"] = extract_infobox_json(soup)

        anchors = extract_page_links(soup) or []
        # collect related = anchors that are known persons/unis (by seed sets)
        related = set()
        for lk in anchors:
            n = normalize(lk)
            if n in people_norm_seed:
                out["mentions_pp"].append((tperson, lk, "MENTIONS_PERSON"))
                related.add(lk)
            elif n in uni_norm_seed:
                out["mentions_pu"].append((tperson, lk, "MENTIONS_UNIVERSITY"))
                related.add(lk)

        out["anchors_intersect"] = sorted(related)

        if is_person_page(soup):
            edu = extract_person_education(soup) or []
            for u, y in edu:
                yy = y if y is not None else infer_year_from_text(u)
                if normalize(u) in uni_norm_seed:
                    out["alumni_pu"].append((tperson, u, "ALUMNI_OF", "" if yy is None else str(yy)))

        return out
    except Exception:
        return out

def worker_university(seed_title, people_norm, uni_norm, sleep, http_timeout):
    """
    Return:
      - title_final
      - edges: uni_mentions_p, uni_mentions_u
      - props: infobox_json
      - anchors_intersect: titles (people or unis) from anchors ∩ known sets
    """
    out = {
        "title_final": seed_title,
        "uni_mentions_p": [],  # (U,P,"UNI_MENTIONS_PERSON")
        "uni_mentions_u": [],  # (U,U,"UNIVERSITY_MENTIONS_UNIVERSITY") [NEW]
        "infobox_json": "{}",
        "anchors_intersect": []
    }
    try:
        html, final_title = safe_fetch(seed_title, sleep=sleep, http_timeout=http_timeout)
        if final_title: out["title_final"] = final_title
        soup = soup_from_html(html)
        if not soup: return out

        tuniv = out["title_final"]
        out["infobox_json"] = extract_infobox_json(soup)

        anchors = extract_page_links(soup) or []
        related = set()
        for lk in anchors:
            n = normalize(lk)
            if n in people_norm:
                out["uni_mentions_p"].append((tuniv, lk, "UNI_MENTIONS_PERSON"))
                related.add(lk)
            elif n in uni_norm:
                out["uni_mentions_u"].append((tuniv, lk, "UNIVERSITY_MENTIONS_UNIVERSITY"))
                related.add(lk)

        out["anchors_intersect"] = sorted(related)
        return out
    except Exception:
        return out

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Step 4 — Re-crawl to add edges, node details (include roots).")
    ap.add_argument("--outdir", default="graph_out")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--http-timeout", type=float, default=6.0)
    ap.add_argument("--sleep", type=float, default=0.06)

    ap.add_argument("--limit-persons", type=int, default=None)
    ap.add_argument("--limit-universities", type=int, default=None)

    ap.add_argument("--persons-csv", default="nodes_persons.csv")
    ap.add_argument("--universities-csv", default="nodes_universities.csv")
    ap.add_argument("--roots-csv", default="root_nodes.csv")
    args = ap.parse_args()

    odir = args.outdir
    os.makedirs(odir, exist_ok=True)

    # 1) Load nodes + roots
    persons_nodes = load_titles_from_csv(os.path.join(odir, args.persons_csv), "title")
    unis_nodes    = load_titles_from_csv(os.path.join(odir, args.universities_csv), "title")
    roots_p, roots_u = load_roots(os.path.join(odir, args.roots_csv))

    persons_all = []
    persons_all.extend(persons_nodes)
    persons_all.extend(roots_p)
    seen = set(); persons_all = [x for x in persons_all if not (x in seen or seen.add(x))]

    unis_all = []
    unis_all.extend(unis_nodes)
    unis_all.extend(roots_u)
    seen = set(); unis_all = [x for x in unis_all if not (x in seen or seen.add(x))]

    if args.limit_persons:      persons_all = persons_all[:args.limit_persons]
    if args.limit_universities: unis_all    = unis_all[:args.limit_universities]

    print(f"Persons to crawl     : {len(persons_all)}")
    print(f"Universities to crawl: {len(unis_all)}")

    # seed normalization (before canonical titles)
    people_norm_seed = {normalize(t) for t in persons_all}
    uni_norm_seed    = {normalize(t) for t in unis_all}

    # Edge buckets (NO LINKS_TO)
    mentions_pp, mentions_pu = [], []
    uni_mentions_p, uni_mentions_u = [], []
    alumni_pu = []
    person_props, uni_props = [], []

    # Node details (we build later after we know per-node related)
    node_details_tmp = []  # list of dicts, then we merge

    # 2) crawl persons
    print("🧭 Crawling PERSON pages…")
    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as ex:
        futs = {ex.submit(worker_person, p, people_norm_seed, uni_norm_seed, args.sleep, args.http_timeout): p
                for p in persons_all}
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                continue
            t_final = r.get("title_final")
            # edges
            mentions_pp.extend(r.get("mentions_pp", []))
            mentions_pu.extend(r.get("mentions_pu", []))
            alumni_pu.extend(r.get("alumni_pu", []))
            # props
            infobox_json = r.get("infobox_json", "{}")
            person_props.append((t_final, infobox_json))
            # node details (person)
            node_details_tmp.append({
                "title": t_final,
                "type": "person",
                "link": wiki_link(t_final),
                "related": r.get("anchors_intersect", []),
                "properties": json.loads(infobox_json) if infobox_json else {}
            })

    # canonical sets after person crawl
    people_norm = {normalize(t) for (t, _) in person_props}

    # 3) crawl universities
    print("🏛️ Crawling UNIVERSITY pages…")
    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as ex:
        futs = {ex.submit(worker_university, u, people_norm, uni_norm_seed, args.sleep, args.http_timeout): u
                for u in unis_all}
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception:
                continue
            t_final = r.get("title_final")
            uni_mentions_p.extend(r.get("uni_mentions_p", []))
            uni_mentions_u.extend(r.get("uni_mentions_u", []))   # NEW
            infobox_json = r.get("infobox_json", "{}")
            uni_props.append((t_final, infobox_json))
            # node details (university)
            node_details_tmp.append({
                "title": t_final,
                "type": "university",
                "link": wiki_link(t_final),
                "related": r.get("anchors_intersect", []),
                "properties": json.loads(infobox_json) if infobox_json else {}
            })

    # 4) dedupe edges
    mentions_pp     = dedupe_norm(mentions_pp)
    mentions_pu     = dedupe_norm(mentions_pu)
    uni_mentions_p  = dedupe_norm(uni_mentions_p)
    uni_mentions_u  = dedupe_norm(uni_mentions_u)  # NEW
    alumni_pu       = dedupe_norm(alumni_pu)

    # 5) SHARED_UNI
    edu_map = defaultdict(set)  # person -> set(unis)
    for (p, u, rel, y) in alumni_pu:
        if rel == "ALUMNI_OF":
            edu_map[p].add(u)

    shared_uni = []  # (p1, p2, "SHARED_UNI", count)
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

    # 6) write edges (NO edges_links_pp.csv)
    n1 = write_csv(os.path.join(odir, "edges_mentions_pp.csv"),     ["src_person","dst_person","relation"], mentions_pp)
    n2 = write_csv(os.path.join(odir, "edges_mentions_pu.csv"),     ["src_person","dst_university","relation"], mentions_pu)
    n3 = write_csv(os.path.join(odir, "edges_uni_mentions_p.csv"),  ["src_university","dst_person","relation"], uni_mentions_p)
    n4 = write_csv(os.path.join(odir, "edges_uni_mentions_u.csv"),  ["src_university","dst_university","relation"], uni_mentions_u)  # NEW
    n5 = write_csv(os.path.join(odir, "edges_alumni_pu.csv"),       ["src_person","dst_university","relation","year"], alumni_pu)
    n6 = write_csv(os.path.join(odir, "edges_shared_uni_pp.csv"),   ["src_person","dst_person","relation","count"], shared_uni)

    # 7) write node properties (unchanged, for convenience)
    write_csv(os.path.join(odir, "nodes_persons_props.csv"),        ["title","infobox_json"], person_props)
    write_csv(os.path.join(odir, "nodes_universities_props.csv"),   ["title","infobox_json"], uni_props)

    # 8) write node details (CSV + JSON)
    # CSV: title,type,link,related,properties (related/properties are JSON strings)
    nd_csv_rows = []
    for nd in node_details_tmp:
        nd_csv_rows.append([
            nd["title"],
            nd["type"],
            nd["link"],
            json.dumps(nd["related"], ensure_ascii=False),
            json.dumps(nd["properties"], ensure_ascii=False),
        ])
    write_csv(os.path.join(odir, "node_details.csv"),
              ["title","type","link","related","properties"],
              nd_csv_rows)

    with open(os.path.join(odir, "node_details.json"), "w", encoding="utf-8") as f:
        json.dump(node_details_tmp, f, ensure_ascii=False, indent=2)

    summary = {
        "persons_crawled": len(person_props),
        "universities_crawled": len(uni_props),
        "edges_mentions_pp": n1,
        "edges_mentions_pu": n2,
        "edges_uni_mentions_p": n3,
        "edges_uni_mentions_u": n4, 
        "edges_alumni_pu": n5,
        "edges_shared_uni_pp": n6,
        "node_props_persons": len(person_props),
        "node_props_universities": len(uni_props),
        "node_details": len(node_details_tmp),
    }
    with open(os.path.join(odir, "step4_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n✅ STEP 4 DONE")
    for k,v in summary.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
