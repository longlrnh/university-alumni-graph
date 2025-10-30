# -*- coding: utf-8 -*-
"""
Step 3 — BFS mở rộng (nhanh, đa luồng)
- Chỉ chấp nhận node PERSON có >=1 trường (alumni).
- Ghi đầy đủ:
    nodes_persons.csv        (bao gồm: root-person depth=0, seeds depth=1, alumni BFS >1)
    nodes_universities.csv   (bao gồm universities BFS + root universities)
    edges_up.csv             (UNI -> PERSON, ALUMNI_OF {year?})
    edges_shared.csv         (P <-> P, SHARED_UNI {count})
    edges_same_grad.csv      (P <-> P, SAME_GRAD_YEAR {year})
    nodes_people_detail.json (depth + học vấn + quan hệ same_*)

Tối ưu / Sửa lỗi:
- ĐÃ SỬA: không tăng depth quá sớm; quét hết node của depth hiện tại trước khi sang depth+1.
- ThreadPoolExecutor với --workers N
- visited được chuẩn hoá normalize để tránh crawl trùng
- Option bật/tắt expand-from-university
"""

import csv, json, argparse, os
import re, urllib.parse
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from utils_wiki import (
    fetch_parse_html, soup_from_html, is_person_page,
    extract_person_education, extract_page_links, normalize
)

# tqdm
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

MAX_DEBUG = 80
debug_skips = 0

LOCK = Lock()  # bảo vệ visited trong môi trường đa luồng

# =========================
# ---- Small utilities ----
# =========================
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
        if anchors:
            for a in anchors:
                t = a.get("title") or a.get_text(strip=True)
                if not t: 
                    continue
                t = normalize(t)
                if looks_like_university(t) and t not in DEGREE_KEYWORDS:
                    out.append((t, None))
        else:
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
            t = (row.get(key) or '').strip()
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
# ---- Safe fetch wrapper ----
# ===========================
def safe_fetch_html(title, sleep=0.08, http_timeout=6.0):
    """Gọi fetch_parse_html với timeout nếu có, fallback nếu utils_wiki không hỗ trợ."""
    try:
        return fetch_parse_html(title, sleep=sleep, timeout=http_timeout)
    except TypeError:
        return fetch_parse_html(title, sleep=sleep)

# ===========================
# ------- Worker task -------
# ===========================
def process_title(title, depth, http_timeout, sleep):
    """Worker: tải & phân tích một title. Trả về dict kết quả."""
    result = {
        "accepted": False,         # có phải alumni node không
        "title": title,
        "depth": depth,
        "edu_clean": [],           # [(uni, year)]
        "expand_links": []         # list link để mở rộng
    }
    try:
        if looks_like_system(title) or looks_like_date_or_year(title):
            return result

        html, _ = safe_fetch_html(title, sleep=sleep, http_timeout=http_timeout)
        soup = soup_from_html(html)
        if not soup:
            return result

        # strict person check
        is_p = False
        try:
            is_p = is_person_page(soup)
        except Exception:
            is_p = False

        if not is_p:
            # heuristic fallback
            ib = parse_infobox_person(soup) or {}
            keys = set(ib.keys())
            person_keys = {"Sinh","Nghề nghiệp","Quốc tịch","Alma mater","Học vấn","Giáo dục","Năm sinh","Tên khai sinh"}
            org_keys = {"Thành lập","Sáng lập","Trụ sở","Trang web","Loại hình","Ngôn ngữ","Quốc gia","Khu vực phục vụ","Thủ đô","Diện tích","Dân số"}
            if (keys & person_keys) and not (keys & org_keys):
                is_p = True

        # Nếu không phải người → chỉ trả về expand_links (nếu còn depth)
        if not is_p:
            result["expand_links"] = extract_page_links(soup) if soup else []
            return result

        # Person ⇒ trích học vấn
        edu = extract_person_education(soup) or []
        if sum(1 for (u,_) in edu if looks_like_university(u)) < 1:
            fb = fallback_extract_universities_from_infobox(soup)
            known = {normalize(u) for (u,_) in edu}
            for u,y in fb:
                if normalize(u) not in known:
                    edu.append((u,y))

        cleaned = []
        for u, year in edu:
            u = clean_wiki_title(u)
            if not looks_like_university(u):
                continue
            u = canonicalize_university(u)
            if year is None:
                y2 = infer_year_from_text(u)
                year = year if year is not None else y2
            cleaned.append((u, year))

        if cleaned:
            result["accepted"] = True
            result["edu_clean"] = cleaned

        result["expand_links"] = extract_page_links(soup) if soup else []
        return result

    except Exception:
        return result

# ===========================
# ---------- Main -----------
# ===========================
def main():
    ap = argparse.ArgumentParser(description="Bước 3 — BFS nhanh (đa luồng, quét hết node theo từng depth).")
    ap.add_argument("--seeds", required=True, help="seeds.csv từ Step 2 (cột person_title/title/name)")
    ap.add_argument("--config", required=True, help="config JSON")
    ap.add_argument("--outdir", required=True)

    ap.add_argument("--expand-from-university", action="store_true",
                    help="Nếu bật, lấy liên kết từ trang TRƯỜNG để seed depth=2")
    ap.add_argument("--root-university", action="append",
                    help="Tên trường; có thể truyền nhiều lần (khi không dùng info/roots-csv)")
    ap.add_argument("--info-json", default=None,
                    help="Đường dẫn info.json (để suy ra root nếu không truyền --root-university)")
    ap.add_argument("--roots-csv", default=None,
                    help="root_nodes.csv từ Step 2 (title,type) để include root-person depth=0 + root-university")

    ap.add_argument("--uni-candidate-cap", type=int, default=300,
                    help="Giới hạn số liên kết lấy từ mỗi trang TRƯỜNG khi expand")
    ap.add_argument("--progress-every", type=int, default=100)
    ap.add_argument("--checkpoint-every", type=int, default=0)
    ap.add_argument("--flush-every", type=int, default=0)

    # tốc độ & song song
    ap.add_argument("--workers", type=int, default=8, help="Số luồng song song (khuyến nghị 8–16)")
    ap.add_argument("--http-timeout", type=float, default=6.0, help="Timeout HTTP mỗi request")
    ap.add_argument("--sleep", type=float, default=0.06, help="Delay nhỏ giữa các request")

    # debug
    ap.add_argument("--debug-skip", action="store_true", help="In log các tiêu đề bị bỏ qua (<=80 dòng)")

    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    # đọc config
    with open(args.config, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    max_person_nodes = int(cfg.get("max_person_nodes", 1300))
    per_depth_limit  = int(cfg.get("per_depth_limit", 120))   # số link expand tối đa / page & batch size
    max_depth        = int(cfg.get("max_depth", 3))
    candidate_cap    = int(cfg.get("candidate_cap", 500))
    sleep            = float(cfg.get("sleep", args.sleep))

    # ===== Load roots (person/university) nếu có roots-csv =====
    roots_persons, roots_unis = set(), set()
    if args.roots_csv and os.path.exists(args.roots_csv):
        with open(args.roots_csv, "r", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                t  = (r.get("title") or "").strip()
                ty = (r.get("type")  or "").strip().lower()
                if not t:
                    continue
                if ty == "person":      roots_persons.add(t)
                elif ty == "university": roots_unis.add(t)

    # ===== Init structures =====
    queue = deque()
    visited = set()

    alumni_persons   = set()                # CHỈ người có ≥1 trường
    universities     = set()
    edu_map          = defaultdict(list)    # person -> list[(university, year)]

    edges_up         = []                   # (uni, person, "ALUMNI_OF", year)
    edges_shared     = []                   # (p1, p2, "SHARED_UNI", count)
    edges_same_grad  = []                   # (p1, p2, "SAME_GRAD_YEAR", year)

    person_depth     = {}                   # depth theo BFS
    stats            = defaultdict(int)

    # ===== Seeds (depth = 1) =====
    seeds_list = load_seeds(args.seeds)
    seeds_set  = set(seeds_list)
    for s in seeds_list:
        s_norm = normalize(s)
        queue.append((s, 1))
        visited.add(s_norm)
        person_depth.setdefault(s, 1)

    # ===== Expand from universities (đặt depth = 2) =====
    if args.expand_from_university:
        root_unis = []
        if args.root_university:
            root_unis = [normalize(x) for x in args.root_university]
        elif roots_unis:
            root_unis = [normalize(x) for x in roots_unis]
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
        rseen = set()
        root_unis = [u for u in root_unis if u and not (u in rseen or rseen.add(u))]

        for uni in root_unis:
            try:
                html, _ = safe_fetch_html(uni, sleep=sleep, http_timeout=args.http_timeout)
                sp = soup_from_html(html)
                if not sp:
                    continue
                links = extract_page_links(sp)[:args.uni_candidate_cap]
                take = 0
                for lk in links:
                    if looks_like_system(lk) or looks_like_date_or_year(lk):
                        continue
                    lk_norm = normalize(lk)
                    if lk_norm in visited:
                        continue
                    visited.add(lk_norm)
                    queue.append((lk, 2))
                    take += 1
                    if take >= per_depth_limit:
                        break
                stats['seed_from_university_links'] += take
            except Exception:
                continue

    processed = 0
    depth_stats = defaultdict(int)
    progress_bar = tqdm(total=max_person_nodes, desc="BFS alumni persons", unit="node") if HAS_TQDM else None

    # ===== BFS theo tầng (quét hết depth hiện tại trước khi sang depth+1) =====
    current_depth = 1
    while queue and len(alumni_persons) < max_person_nodes and current_depth <= max_depth:

        # Nếu hàng đợi hiện không có node ở depth hiện tại, nhảy sang depth nhỏ nhất còn lại
        depths_in_queue = set(d for _, d in queue)
        if current_depth not in depths_in_queue:
            if depths_in_queue:
                current_depth = min(depths_in_queue)
                if current_depth > max_depth:
                    break
            else:
                break

        # Xử lý theo BATCH các node có đúng depth = current_depth
        while len(alumni_persons) < max_person_nodes:
            # Lấy một batch cùng depth
            batch = []
            # scan nhanh để gom batch đúng depth
            tmp = deque()
            while queue and len(batch) < max(1, per_depth_limit):
                t, d = queue.popleft()
                if d == current_depth:
                    batch.append((t, d))
                else:
                    tmp.append((t, d))
            # đẩy lại các phần tử depth khác
            while tmp:
                queue.appendleft(tmp.pop())

            if not batch:
                break  # hết node ở depth này → thoát vòng while(batch), chuyển depth

            # chạy song song batch
            with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as ex:
                futures = [ex.submit(process_title, t, d, args.http_timeout, sleep) for (t, d) in batch]
                for fut in as_completed(futures):
                    res = fut.result()
                    title = res["title"]
                    depth = res["depth"]

                    # alumni node?
                    if res["accepted"] and title not in alumni_persons:
                        alumni_persons.add(title)
                        person_depth[title] = depth
                        processed += 1
                        depth_stats[depth] += 1
                        for u, year in res["edu_clean"]:
                            universities.add(u)
                            edu_map[title].append((u, year))
                            edges_up.append((u, title, "ALUMNI_OF", year if year is not None else ""))

                        if HAS_TQDM:
                            progress_bar.update(1)
                            progress_bar.set_postfix(nodes=len(alumni_persons), depth=depth)

                    # mở rộng (enqueue depth+1)
                    if depth < max_depth and res["expand_links"]:
                        added = 0
                        for lk in res["expand_links"][:candidate_cap]:
                            if looks_like_system(lk) or looks_like_date_or_year(lk):
                                continue
                            lk_norm = normalize(lk)
                            with LOCK:
                                if lk_norm in visited:
                                    continue
                                visited.add(lk_norm)
                            queue.append((lk, depth+1))
                            added += 1
                            if added >= per_depth_limit:
                                break

            if args.checkpoint_every > 0 and processed > 0 and (processed % args.checkpoint_every == 0):
                save_checkpoint(args.outdir, alumni_persons, universities, edges_up, edges_shared, edges_same_grad)

            if not HAS_TQDM and (processed % max(1, args.progress_every) == 0):
                print(f"[BFS] alumni={len(alumni_persons)} depth={current_depth} | UP={len(edges_up)}", flush=True)

        # xong toàn bộ depth hiện tại → sang depth kế tiếp
        current_depth += 1

    # ===== AUGMENT edu_map từ Step 2 (edu_edges.csv) để root-person/seeds cũng có học vấn =====
    ee_fp = os.path.join(args.outdir, "edu_edges.csv")
    if os.path.exists(ee_fp):
        with open(ee_fp, "r", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                if (r.get("relation") or "").strip().upper() != "ALUMNI_OF":
                    continue
                u = (r.get("src_university") or "").strip()
                p = (r.get("dst_person") or "").strip()
                y = (r.get("year") or "").strip()
                if not p or not u:
                    continue
                try:
                    y_val = int(y) if y and y.isdigit() else None
                except Exception:
                    y_val = None
                edu_map[p].append((u, y_val))
                universities.add(u)

    # ===== Hậu xử lý edges_shared / same_grad chỉ dựa vào edu_map =====
    inv_unis = defaultdict(set)       # uni -> set(person)
    inv_grad_year = defaultdict(set)  # year -> set(person)
    for p, pairs in edu_map.items():
        yrs = set()
        for u,y in pairs:
            inv_unis[u].add(p)
            if y is not None:
                yrs.add(y)
        for y in yrs:
            inv_grad_year[y].add(p)

    # shared_uni
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

    # same_grad_year
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

    # ===== Ghi file =====
    # persons_out = alumni + seeds + root-person (đúng depth 0/1)
    persons_out = set(alumni_persons) | set(seeds_set) | set(roots_persons)
    universities |= set(roots_unis)

    write_nodes_people(persons_out, os.path.join(args.outdir, "nodes_persons.csv"))
    write_nodes_unis(universities, os.path.join(args.outdir, "nodes_universities.csv"))

    write_edges(os.path.join(args.outdir, "edges_up.csv"),
                ["src_university","dst_person","relation","year"], edges_up)
    write_edges(os.path.join(args.outdir, "edges_shared.csv"),
                ["src_person","dst_person","relation","count"], edges_shared)
    write_edges(os.path.join(args.outdir, "edges_same_grad.csv"),
                ["src_person","dst_person","relation","year"], edges_same_grad)

    # graph.json (thông tin tóm tắt)
    graph = {
        "persons": sorted(list(persons_out)),
        "universities": sorted(list(universities)),
        "edges_up": edges_up,
        "edges_shared": edges_shared,
        "edges_same_grad": edges_same_grad,
        "depth_stats": dict(sorted(depth_stats.items()))
    }
    with open(os.path.join(args.outdir, "graph.json"), "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    # nodes_people_detail.json (depth + học vấn + quan hệ)
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
    for p in sorted(persons_out):
        # depth: root-person =0; seed=1; còn lại lấy từ BFS
        if p in roots_persons:
            d = 0
        elif p in seeds_set:
            d = 1
        else:
            d = person_depth.get(p)

        hv = [{"trường": u, "năm": y} for (u,y) in edu_map.get(p, [])]
        base = {
            "depth": d,
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

    if HAS_TQDM and progress_bar is not None:
        try:
            progress_bar.close()
        except Exception:
            pass

    print(f"✅ BFS done. Persons(out)={len(persons_out)} | Alumni={len(alumni_persons)} | Universities={len(universities)}")
    print(f"   UP={len(edges_up)} | Shared={len(edges_shared)} | SameGrad={len(edges_same_grad)}")
    print(f"ℹ️ Depth stats: {dict(sorted(depth_stats.items()))}")
    print(f"ℹ️ Counters: {dict(stats)}")

if __name__ == "__main__":
    main()
