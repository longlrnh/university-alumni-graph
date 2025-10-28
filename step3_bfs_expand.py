# -*- coding: utf-8 -*-
import csv, json, argparse, os
import re, urllib.parse
from collections import deque, defaultdict

from utils_wiki import (
    fetch_parse_html, soup_from_html, is_person_page,
    extract_person_education, extract_page_links, normalize
)

# tqdm (nếu có)
try:
    from tqdm import tqdm
    HAS_TQDM = True
except Exception:
    HAS_TQDM = False

# =========================
# ---- Filtering rules ----
# =========================
UNI_PREFIXES = (
    "Đại học", "Trường", "Học viện", "Viện",                     # VI
    "University", "College", "Institute", "Academy", "Faculty",  # EN
    "School", "Law School", "Business School",
    "École", "Universität", "Universidade", "Università", "Universidad", "Polytechnic"
)

UNI_SUFFIXES = (
    "University", "College", "Institute", "Academy",
    "School", "Law School", "Business School", "Faculty",
    "Đại học", "Học viện", "Viện", "Trường", "Khoa"
)

DEGREE_KEYWORDS = {
    # văn bằng / nhãn không phải tên cơ sở
    "Cử nhân", "Cử nhân Nghệ thuật", "Cử nhân Khoa học",
    "Bachelor", "Bachelor of Arts", "Bachelor of Science", "B.A.", "BA", "BSc", "B.Sc.",
    "Master", "Thạc sĩ", "M.A.", "MA", "MSc", "M.Sc.",
    "Doctor", "Tiến sĩ", "PhD", "Ph.D.", "JD", "LLB", "LLM",
    "Alma mater"
}

NS_BLACKLIST = re.compile(
    r"^(Danh sách|Thể loại|Wikipedia|Trợ giúp|Bản mẫu|Portal|Chủ đề|Tập tin|File)\b",
    flags=re.I
)

YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
NONEXIST_SUFFIX = re.compile(r"\s*\(trang không tồn tại\)\s*$", re.I)

def clean_wiki_title(t: str) -> str:
    return NONEXIST_SUFFIX.sub("", t or "").strip()

def looks_like_university(title: str) -> bool:
    if not title:
        return False
    t = title.strip()
    if t in DEGREE_KEYWORDS:
        return False
    if t.startswith(UNI_PREFIXES):
        return True
    for suf in UNI_SUFFIXES:
        if t.endswith(suf):
            return True
    if re.search(r"\b(University|College|Institute|Academy|École|Universit[aä]t|Universidad|Universidade|Polytechnic)\b", t, re.I):
        return True
    if "Đại học" in t:
        return True
    return False

def looks_like_system(title: str) -> bool:
    if not title:
        return True
    if ":" in title:
        return True
    if NS_BLACKLIST.match(title):
        return True
    return False

def looks_like_date_or_year(title: str) -> bool:
    if not title:
        return True
    if re.fullmatch(r"\d{4}", title):
        return True
    if re.fullmatch(r"\d{1,2}\s+tháng\s+\d{1,2}", title, flags=re.I):
        return True
    return False

# ===========================
# ---- Canonicalize unis ----
# ===========================
CANON_RULES = [
    (r".*\bHarvard\b.*(Law|Luật|Business|Kinh doanh).*", "Đại học Harvard"),
    (r".*\bHarvard\b.*", "Đại học Harvard"),
    (r".*\bStanford\b.*", "Đại học Stanford"),
    (r".*\bOxford\b.*", "Đại học Oxford"),
    (r".*\bCambridge\b.*", "Đại học Cambridge"),
    (r".*\b(MIT|Massachusetts Institute of Technology|Viện Công nghệ Massachusetts)\b.*", "Viện Công nghệ Massachusetts"),
    (r".*\bColumbia\b.*", "Đại học Columbia"),
    (r".*\bPrinceton\b.*", "Đại học Princeton"),
    (r".*\b(Pennsylvania|UPenn)\b.*", "Đại học Pennsylvania"),
    (r".*\bYale\b.*", "Đại học Yale"),
]

def canonicalize_university(u: str) -> str:
    if not u:
        return u
    s = u.strip()
    for pat, rep in CANON_RULES:
        if re.search(pat, s, flags=re.I):
            return rep
    return s

def infer_year_from_text(val):
    if isinstance(val, str):
        m = YEAR_RE.search(val)
        return int(m.group(0)) if m else None
    if isinstance(val, list):
        for x in val:
            m = YEAR_RE.search(str(x))
            if m:
                return int(m.group(0))
    return None

# ===========================
# ---- Infobox helpers  -----
# ===========================
def _textify(td):
    if td is None:
        return None
    h = td.find("div", {"class": "hlist"})
    if h:
        items = [li.get_text(strip=True) for li in h.find_all("li")]
        return [x for x in items if x]
    ul = td.find("ul")
    if ul:
        items = [li.get_text(strip=True) for li in ul.find_all("li")]
        return [x for x in items if x]
    if td.find("br"):
        parts = [t.strip() for t in td.stripped_strings]
        return [p for p in parts if p]
    val = td.get_text(separator=" ", strip=True)
    return val or None

def parse_infobox_person(soup):
    box = soup.find("table", {"class": re.compile(r"\binfobox\b", re.I)})
    if not box:
        return {}
    out = {}
    for tr in box.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        key = th.get_text(strip=True)
        val = _textify(td)
        if key and val:
            out[key] = val
    return out

# các khóa infobox thường chứa học vấn ở viwiki
EDU_KEYS = [
    "Học vấn", "Giáo dục", "Trường", "Trường học", "Trường theo học",
    "Alma mater", "Tốt nghiệp", "Đào tạo", "Cựu sinh viên", "Cơ sở đào tạo"
]

def fallback_extract_universities_from_infobox(soup):
    box = soup.find("table", {"class": re.compile(r"\binfobox\b", re.I)})
    if not box:
        return []
    out = []
    for tr in box.find_all("tr"):
        th = tr.find("th"); td = tr.find("td")
        if not th or not td:
            continue
        key = th.get_text(strip=True)
        if key not in EDU_KEYS:
            continue
        anchors = td.find_all("a", href=True)
        for a in anchors:
            t = a.get("title") or a.get_text(strip=True)
            if not t: 
                continue
            t = normalize(t)
            if looks_like_university(t) and t not in DEGREE_KEYWORDS:
                out.append((t, None))
        if not anchors:
            val = td.get_text(separator=" ", strip=True)
            for chunk in re.split(r"[;•\|,]", val):
                ct = normalize(chunk)
                if looks_like_university(ct) and ct not in DEGREE_KEYWORDS:
                    out.append((ct, None))
    # unique
    seen, uniq = set(), []
    for u,y in out:
        if u not in seen:
            seen.add(u); uniq.append((u,y))
    return uniq

def to_wiki_url(title):
    return "https://vi.wikipedia.org/wiki/" + urllib.parse.quote((title or "").replace(" ", "_"))

# ===========================
# -------- IO helpers -------
# ===========================
def load_seeds(path):
    seeds = []
    with open(path, "r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        # chấp nhận person_title | title | name
        key = None
        if 'person_title' in rdr.fieldnames: key = 'person_title'
        elif 'title' in rdr.fieldnames:      key = 'title'
        elif 'name' in rdr.fieldnames:       key = 'name'
        else:
            raise SystemExit("seeds.csv thiếu cột person_title/title/name")
        for row in rdr:
            t = row.get(key, '').strip()
            if t: 
                seeds.append(t)
    if not seeds:
        raise SystemExit("seeds.csv rỗng — không có seed person.")
    return seeds

def write_nodes_people(persons, path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["id","title"])
        for i,t in enumerate(sorted(persons), start=1):
            w.writerow([i,t])

def write_nodes_unis(universities, path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["id","title"])
        for i,t in enumerate(sorted(universities), start=1):
            w.writerow([i,t])

def write_edges(filename, header, rows):
    with open(filename, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(header)
        for r in rows:
            w.writerow(list(r))

def save_checkpoint(outdir, persons, universities, edges_up, edges_shared, edges_same_grad):
    ck = {
        "persons": len(persons),
        "universities": len(universities),
        "edges_up": len(edges_up),
        "edges_shared": len(edges_shared),
        "edges_same_grad": len(edges_same_grad)
    }
    with open(os.path.join(outdir, "_bfs_checkpoint.json"), "w", encoding="utf-8") as f:
        json.dump(ck, f, ensure_ascii=False, indent=2)

# ===========================
# ---------- Main -----------
# ===========================
def main():
    ap = argparse.ArgumentParser(description="Bước 3 — BFS: chỉ lấy CỰU SINH VIÊN và TRƯỜNG (lọc trước).")
    ap.add_argument("--seeds", required=True, help="seeds.csv từ Bước 2 (cột person_title/title/name)")
    ap.add_argument("--config", required=True, help="json cấu hình BFS")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--expand-from-university", action="store_true",
                    help="Nếu bật, lấy liên kết từ trang TRƯỜNG để đưa vào hàng đợi duyệt")
    ap.add_argument("--root-university", action="append",
                    help="Tên trường; có thể truyền nhiều lần. Nếu không truyền, có thể suy ra từ --info-json")
    ap.add_argument("--info-json", default=None,
                    help="Đường dẫn info.json gộp (để suy ra danh sách root nếu không truyền --root-university)")
    ap.add_argument("--uni-candidate-cap", type=int, default=400,
                    help="Giới hạn số liên kết lấy từ mỗi trang TRƯỜNG khi expand")
    ap.add_argument("--progress-every", type=int, default=100,
                    help="In tiến độ mỗi N nút khi không có tqdm")
    ap.add_argument("--checkpoint-every", type=int, default=500,
                    help="Ghi checkpoint JSON mỗi N nút")
    ap.add_argument("--flush-every", type=int, default=0,
                    help="Ghi tạm CSV mỗi N nút (>0 thì bật)")
        # Debug flag
    ap.add_argument(
        "--debug-skip",
        dest="debug_skip",
        action="store_true",
        help="In log các tiêu đề bị bỏ qua (giới hạn ~80 dòng)"
    )
    ap.set_defaults(debug_skip=False)


    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # cấu hình BFS
    max_person_nodes = int(cfg.get("max_person_nodes", 1500))
    per_depth_limit  = int(cfg.get("per_depth_limit", 400))
    max_depth        = int(cfg.get("max_depth", 3))
    candidate_cap    = int(cfg.get("candidate_cap", 800))
    sleep            = float(cfg.get("sleep", 0.2))

    # structures
    queue = deque()
    visited = set()

    alumni_persons   = set()                # CHỈ người có ≥1 trường
    universities     = set()
    edu_map          = defaultdict(list)    # person -> list[(university, year)]

    edges_up         = []                   # (uni, person, "ALUMNI_OF", year)
    edges_shared     = []                   # (p1, p2, "SHARED_UNI", count)
    edges_same_grad  = []                   # (p1, p2, "SAME_GRAD_YEAR", year)

    person_depth     = {}                   # only for alumni persons
    stats            = defaultdict(int)

    # init seeds
    for s in load_seeds(args.seeds):
        queue.append((s, 0))
        visited.add(s)

    # optional: expand from root universities (to discover persons)
    if args.expand_from_university:
        root_unis = []
        if args.root_university:
            root_unis = [normalize(x) for x in args.root_university]
        elif args.info_json and os.path.exists(args.info_json):
            try:
                with open(args.info_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for it in data:
                            t = it.get("title")
                            if t:
                                root_unis.append(normalize(t))
            except Exception:
                pass
        # unique
        seen = set()
        root_unis = [u for u in root_unis if u and not (u in seen or seen.add(u))]

        for uni in root_unis:
            try:
                html, _ = fetch_parse_html(uni, sleep=sleep)
                sp = soup_from_html(html)
                if not sp:
                    continue
                links = extract_page_links(sp)[:args.uni_candidate_cap]
                take = 0
                for lk in links:
                    if looks_like_system(lk) or looks_like_date_or_year(lk):
                        continue
                    if lk in visited:
                        continue
                    visited.add(lk)
                    queue.append((lk, 0))
                    take += 1
                    if take >= per_depth_limit:
                        break
                stats['seed_from_university_links'] += take
            except Exception:
                continue

    processed = 0
    depth_stats = defaultdict(int)
    iterator = tqdm(total=max_person_nodes, desc="BFS alumni persons", unit="node") if HAS_TQDM else None

    while queue and len(alumni_persons) < max_person_nodes:
        title, depth = queue.popleft()
        try:
            if looks_like_system(title) or looks_like_date_or_year(title):
                stats['skip_ns_or_date'] += 1
                continue

            html, _ = fetch_parse_html(title, sleep=sleep)
            soup = soup_from_html(html)
            if not soup:
                stats['no_soup'] += 1
                continue

            # strict person check
            is_person = False
            try:
                is_person = is_person_page(soup)
            except Exception:
                is_person = False

            if not is_person:
                # heuristic: must have person-ish infobox keys but not org/geo keys
                ib = parse_infobox_person(soup) or {}
                keys = set(ib.keys())
                person_keys = {"Sinh","Nghề nghiệp","Quốc tịch","Alma mater","Học vấn","Giáo dục","Năm sinh","Tên khai sinh"}
                org_keys = {"Thành lập","Sáng lập","Trụ sở","Trang web","Loại hình","Ngôn ngữ","Quốc gia","Khu vực phục vụ","Thủ đô","Diện tích","Dân số"}
                if (keys & person_keys) and not (keys & org_keys):
                    is_person = True

            if not is_person:
                stats['non_person_skipped'] += 1
                continue

            # extract education with fallback
            edu = extract_person_education(soup) or []
            # if too few real unis, fallback scan infobox
            if sum(1 for (u,_) in edu if looks_like_university(u)) < 1:
                fb = fallback_extract_universities_from_infobox(soup)
                known = {normalize(u) for (u,_) in edu}
                for u,y in fb:
                    if normalize(u) not in known:
                        edu.append((u,y))

            # keep only real universities, canonicalize, and infer year if needed
            cleaned = []
            for u, year in edu:
                u = clean_wiki_title(u)
                if not looks_like_university(u):
                    continue
                u = canonicalize_university(u)
                if year is None:
                    # try parse year from string form if present
                    y2 = infer_year_from_text(u)
                    year = year if year is not None else y2
                cleaned.append((u, year))

            if not cleaned:
                # Not an alumnus ⇒ do NOT add to nodes/edges, but can still expand to find others
                if depth < max_depth:
                    links = extract_page_links(soup)[:candidate_cap]
                    added = 0
                    for lk in links:
                        if looks_like_system(lk) or looks_like_date_or_year(lk):
                            continue
                        if lk in visited:
                            continue
                        visited.add(lk)
                        queue.append((lk, depth+1))
                        added += 1
                        if added >= per_depth_limit:
                            break
                continue

            # At this point: title is PERSON WITH ≥1 UNIVERSITY ⇒ accept as alumni node
            if title in alumni_persons:
                stats['dup_alumni'] += 1
                continue

            alumni_persons.add(title)
            person_depth[title] = depth
            processed += 1
            depth_stats[depth] += 1
            if HAS_TQDM:
                iterator.update(1)
                iterator.set_postfix(nodes=len(alumni_persons), depth=depth)

            # record edu & edges_up
            for u, year in cleaned:
                universities.add(u)
                edu_map[title].append((u, year))
                edges_up.append((u, title, "ALUMNI_OF", year if year is not None else ""))

            # expand from this (alumni) person if depth allows (to find more candidates)
            if depth < max_depth:
                links = extract_page_links(soup)[:candidate_cap]
                added = 0
                for lk in links:
                    if looks_like_system(lk) or looks_like_date_or_year(lk):
                        continue
                    if lk in visited:
                        continue
                    visited.add(lk)
                    queue.append((lk, depth+1))
                    added += 1
                    if added >= per_depth_limit:
                        break

            if not HAS_TQDM and (processed % args.progress_every == 0):
                print(f"[BFS] alumni={len(alumni_persons)} depth≤{depth} | UP={len(edges_up)}", flush=True)

            if args.checkpoint_every > 0 and (processed % args.checkpoint_every == 0):
                save_checkpoint(args.outdir, alumni_persons, universities, edges_up, edges_shared, edges_same_grad)
            if args.flush_every > 0 and (processed % args.flush_every == 0):
                write_nodes_people(alumni_persons, os.path.join(args.outdir, "nodes_persons.csv"))
                write_nodes_unis(universities, os.path.join(args.outdir, "nodes_universities.csv"))
                write_edges(os.path.join(args.outdir, "edges_up.csv"),
                            ["src_university","dst_person","relation","year"], edges_up)

        except Exception:
            stats['exceptions'] += 1
            continue

    # post-process ONLY among alumni persons
    inv_unis = defaultdict(set)       # uni -> set(alumni)
    inv_grad_year = defaultdict(set)  # year -> set(alumni)
    for p, pairs in edu_map.items():
        yrs = set()
        for u,y in pairs:
            inv_unis[u].add(p)
            if y is not None:
                yrs.add(y)
        for y in yrs:
            inv_grad_year[y].add(p)

    # SHARED_UNI (count intersection size of universities)
    seen_pairs = set()
    for uni, plist in inv_unis.items():
        plist = list(plist)
        n = len(plist)
        for i in range(n):
            for j in range(i+1, n):
                a, b = sorted((plist[i], plist[j]))
                key = (a,b,uni)
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                set_a = set(u for u,_ in edu_map[a])
                set_b = set(u for u,_ in edu_map[b])
                cnt = len(set_a & set_b)
                if cnt > 0:
                    edges_shared.append((a,b,"SHARED_UNI",cnt))

    # SAME_GRAD_YEAR (same year among alumni)
    seen_year_pairs = set()
    for y, plist in inv_grad_year.items():
        plist = list(plist)
        n = len(plist)
        for i in range(n):
            for j in range(i+1, n):
                a, b = sorted((plist[i], plist[j]))
                key = (a,b,y)
                if key in seen_year_pairs:
                    continue
                seen_year_pairs.add(key)
                edges_same_grad.append((a,b,"SAME_GRAD_YEAR",y))

    # ---- write final nodes/edges (ONLY alumni + universities) ----
    write_nodes_people(alumni_persons, os.path.join(args.outdir, "nodes_persons.csv"))
    write_nodes_unis(universities, os.path.join(args.outdir, "nodes_universities.csv"))

    write_edges(os.path.join(args.outdir, "edges_up.csv"),
                ["src_university","dst_person","relation","year"], edges_up)
    write_edges(os.path.join(args.outdir, "edges_shared.csv"),
                ["src_person","dst_person","relation","count"], edges_shared)
    write_edges(os.path.join(args.outdir, "edges_same_grad.csv"),
                ["src_person","dst_person","relation","year"], edges_same_grad)

    # ---- graph.json ----
    graph = {
        "persons": sorted(list(alumni_persons)),
        "universities": sorted(list(universities)),
        "edges_up": edges_up,
        "edges_shared": edges_shared,
        "edges_same_grad": edges_same_grad,
        "depth_stats": dict(sorted(depth_stats.items()))
    }
    with open(os.path.join(args.outdir, "graph.json"), "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    # ---- nodes_people_detail.json (ONLY alumni) ----
    # Relations here only between alumni; we reuse edges_* we just built.
    same_uni_map = defaultdict(set)
    for a,b,rel,cnt in edges_shared:
        if rel == "SHARED_UNI":
            same_uni_map[a].add(b)
            same_uni_map[b].add(a)

    same_year_map = defaultdict(set)
    for a,b,rel,y in edges_same_grad:
        if rel == "SAME_GRAD_YEAR":
            same_year_map[a].add(b)
            same_year_map[b].add(a)

    person_json = []
    for p in sorted(alumni_persons):
        hv = [{"trường": u, "năm": y} for (u,y) in edu_map.get(p, [])]
        base = {
            "depth": person_depth.get(p),
            "name": p,
            "link": to_wiki_url(p),
            "Học vấn": hv,
        }
        rels = []
        for q in sorted(same_uni_map.get(p, [])):
            rels.append({"person_title": q, "person_link": to_wiki_url(q), "type": "same_university"})
        for q in sorted(same_year_map.get(p, [])):
            rels.append({"person_title": q, "person_link": to_wiki_url(q), "type": "same_grad_year"})
        base["relations"] = rels
        base["same_university_persons"] = [to_wiki_url(q) for q in sorted(same_uni_map.get(p, []))]
        base["same_grad_year_persons"]  = [to_wiki_url(q) for q in sorted(same_year_map.get(p, []))]
        person_json.append(base)

    with open(os.path.join(args.outdir, "nodes_people_detail.json"), "w", encoding="utf-8") as f:
        json.dump(person_json, f, ensure_ascii=False, indent=2)

    print(f"✅ BFS (ALUMNI-ONLY) done. Alumni={len(alumni_persons)} Universities={len(universities)} "
          f"UP={len(edges_up)} Shared={len(edges_shared)} SameGrad={len(edges_same_grad)}")
    print(f"ℹ️ Depth stats: {dict(sorted(depth_stats.items()))}")
    print(f"ℹ️ Counters: {dict(stats)}")

if __name__ == "__main__":
    main()
