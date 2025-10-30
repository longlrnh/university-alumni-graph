# -*- coding: utf-8 -*-
import csv, argparse, json, os, re
from collections import defaultdict
from utils_wiki import (
    fetch_parse_html, soup_from_html, is_person_page,
    extract_person_education, normalize
)

# ========== tqdm ==========
try:
    from tqdm import tqdm
    HAS_TQDM = True
except Exception:
    HAS_TQDM = False


# ========== IO helpers ==========
def load_candidates_grouped(links_csv, filter_title=None):
    """
    Đọc links.csv (gộp) và gom các target theo từng source_title.
    Nếu filter_title != None thì chỉ lấy đúng nhóm đó.
    Trả về: dict {root_title_norm: [target_title_raw,...]}
    """
    groups = defaultdict(list)
    with open(links_csv, "r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            s = normalize(r["source_title"])
            t = r["target_title"]
            if filter_title is not None and normalize(filter_title) != s:
                continue
            groups[s].append(t)
    return groups


def ensure_parent(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def open_csv_writer(path, header, append=False):
    mode = "a" if append and os.path.exists(path) else "w"
    f = open(path, mode, encoding="utf-8", newline="")
    w = csv.writer(f)
    if mode == "w":
        w.writerow(header)
    return f, w


# ========== DEDUPE helpers ==========
def _norm_tuple(*cols):
    """Tạo khóa dedupe đã chuẩn hoá (lower/strip/normalize cho chuỗi)."""
    return tuple(normalize(x) if isinstance(x, str) else x for x in cols)


def load_existing_pairs_norm(path, cols):
    """
    Đọc file hiện có và trả về set khóa CHUẨN HOÁ theo danh sách cột.
    Dùng cho so khớp dedupe theo _norm_tuple.
    """
    s = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                s.add(_norm_tuple(*(r[c] for c in cols)))
    return s


# ========== Heuristics: xác định 'university' ==========
def looks_like_university_title(txt: str) -> bool:
    if not txt:
        return False
    t = (txt or "").strip().lower()

    keywords = [
        "đại học", "học viện", "trường ", " viện ", "khoa ",
        "university", "college", "institute", "academy", "faculty", "school", "law school", "business school"
    ]
    return any(k in t for k in keywords)


def looks_like_university_infobox(soup) -> bool:
    """
    Suy luận 'trang tổ chức/đại học' dựa trên các khóa thường gặp trong infobox.
    Phân biệt với person khi tiêu đề mơ hồ.
    """
    try:
        box = soup.find("table", {"class": re.compile(r"\binfobox\b", re.I)})
        if not box:
            return False
        keys = set()
        for tr in box.find_all("tr"):
            th = tr.find("th")
            if th:
                k = th.get_text(strip=True)
                if k:
                    keys.add(k.lower())
        orgish = {
            "loại hình", "thành lập", "trụ sở", "số lượng sinh viên", "khoa",
            "trang web", "hiệu trưởng", "hiệu phó", "cơ sở", "viện", "khoa"
        }
        return len(keys & orgish) >= 2
    except Exception:
        return False


# ========== MAIN ==========
def main():
    ap = argparse.ArgumentParser(
        description="Bước 2 — Multi-root: đọc 1 links.csv GỘP, xử lý từng source_title và xuất seeds/person_edges/edu_edges + root_nodes."
    )
    ap.add_argument("--links-csv", required=True, help="links.csv đã gộp (từ Bước 1 append)")
    ap.add_argument("--outdir", required=True, help="Thư mục xuất DUY NHẤT (không tạo subfolder)")
    ap.add_argument("--filter-title", help="Chỉ xử lý 1 root (source_title) trong file gộp")
    ap.add_argument("--assume-university", action="store_true",
                    help="Nếu root là trường, tạo cạnh ALUMNI_OF cho các person có học trường đó")
    ap.add_argument("--include-root-seed", action="store_true",
                    help="Nếu root là người, thêm chính root vào seeds.csv (nếu trang đó là person)")
    ap.add_argument("--append", action="store_true",
                    help="Bật chế độ bổ sung (append) vào các file seeds/person_edges/edu_edges hiện có")
    ap.add_argument("--dedupe", action="store_true",
                    help="Khử trùng khi append (đọc file hiện có để loại bỏ bản ghi trùng)")
    ap.add_argument("--progress-every", type=int, default=50,
                    help="(fallback) In tiến độ mỗi N trang khi không có tqdm")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Chuẩn bị writer (một lần, ghi chung)
    seeds_path   = os.path.join(args.outdir, "seeds.csv")
    p_edges_path = os.path.join(args.outdir, "person_edges.csv")
    u_edges_path = os.path.join(args.outdir, "edu_edges.csv")
    roots_path   = os.path.join(args.outdir, "root_nodes.csv")

    f_seeds,  w_seeds  = open_csv_writer(seeds_path,   ["person_title"], append=args.append)
    f_pedges, w_pedges = open_csv_writer(p_edges_path, ["src_root","dst_person","relation"], append=args.append)
    f_uedges, w_uedges = open_csv_writer(u_edges_path, ["src_university","dst_person","relation","year"], append=args.append)
    f_roots,  w_roots  = open_csv_writer(roots_path,   ["title","type"], append=args.append)

    # Dedupe sets (dùng bản chuẩn hoá để so sánh)
    if args.dedupe:
        seen_seed  = load_existing_pairs_norm(seeds_path,   ["person_title"])
        seen_pedge = load_existing_pairs_norm(p_edges_path, ["src_root","dst_person","relation"])
        seen_uedge = load_existing_pairs_norm(u_edges_path, ["src_university","dst_person","relation","year"])
        seen_roots = load_existing_pairs_norm(roots_path,   ["title","type"])
    else:
        seen_seed = seen_pedge = seen_uedge = seen_roots = set()

    # Gom ứng viên theo từng source_title
    groups = load_candidates_grouped(args.links_csv, filter_title=args.filter_title)
    roots = list(groups.keys())

    total_roots = len(roots)
    print(f"🔹 Tổng root cần xử lý: {total_roots}")

    for idx, root_norm in enumerate(roots, 1):
        candidates = groups[root_norm]  # list of raw target titles
        print(f"\n[{idx}/{total_roots}] ROOT = {root_norm} | candidates = {len(candidates)}")

        # Lấy lại tiêu đề 'đẹp' để ghi ra (root_norm là đã normalize)
        # Ở links.csv, source_title là normalized, nên root_norm chính là bản chuẩn.
        root_title = root_norm

        # --- Xác định loại trang root (person / university) ---
        root_is_person = False
        soup0 = None
        try:
            h0, _ = fetch_parse_html(root_title)
            soup0 = soup_from_html(h0)
            if soup0 and is_person_page(soup0):
                root_is_person = True
        except Exception:
            soup0 = None

        # Ghi root vào root_nodes.csv với heuristic an toàn
        if root_is_person:
            root_type = "person"
        else:
            # Heuristic: tiêu đề + infobox
            if looks_like_university_title(root_title) or (soup0 and looks_like_university_infobox(soup0)):
                root_type = "university"
            else:
                # fallback cuối cùng
                root_type = "university" if looks_like_university_title(root_title) else "person"

        row_root = (root_title, root_type)
        k_root = _norm_tuple(*row_root)
        if k_root not in seen_roots:
            w_roots.writerow(list(row_root))
            seen_roots.add(k_root)
            print(f"    ↳ root_nodes: '{root_title}' → type={root_type}")

        # Nếu root là person:
        # - thêm chính root vào seeds (depth 1 ở Step 2)
        # - trích học vấn của root và ghi edu_edges (ALUMNI_OF)
        if root_is_person:
            try:
                if args.include_root_seed:
                    row_seed = (root_title,)
                    k_seed = _norm_tuple(*row_seed)
                    if k_seed not in seen_seed:
                        w_seeds.writerow([root_title]); seen_seed.add(k_seed)

                if soup0 is None:
                    # fetch lại nếu cần
                    h0, _ = fetch_parse_html(root_title)
                    soup0 = soup_from_html(h0)

                if soup0 is not None:
                    edu_root = extract_person_education(soup0) or []
                    for uni, year in edu_root:
                        row = (uni, root_title, "ALUMNI_OF", str(year) if year is not None else "")
                        k_ue = _norm_tuple(*row)
                        if k_ue not in seen_uedge:
                            w_uedges.writerow(list(row)); seen_uedge.add(k_ue)
            except Exception:
                pass

        # --- Duyệt các candidate link của root ---
        processed = 0
        ok_people = 0
        made_edu_edges = 0
        errors = 0

        iterator = tqdm(candidates, total=len(candidates), desc=f"Scanning@{root_title}", unit="page") if HAS_TQDM else iter(candidates)

        for cand in iterator:
            processed += 1
            try:
                ch_html, _ = fetch_parse_html(cand)
                ch_soup = soup_from_html(ch_html)
                if not ch_soup or not is_person_page(ch_soup):
                    if not HAS_TQDM and processed % args.progress_every == 0:
                        print(f"  [{processed}/{len(candidates)}] seeds={ok_people} edu={made_edu_edges} err={errors}")
                    continue

                edu = extract_person_education(ch_soup) or []
                if not edu:
                    if not HAS_TQDM and processed % args.progress_every == 0:
                        print(f"  [{processed}/{len(candidates)}] seeds={ok_people} edu={made_edu_edges} err={errors}")
                    continue

                # giữ seed (người) — định nghĩa: depth 1 ở Step 2
                row_seed = (cand,)
                k_seed = _norm_tuple(*row_seed)
                if (not args.dedupe) or (k_seed not in seen_seed):
                    w_seeds.writerow([cand]); seen_seed.add(k_seed)
                ok_people += 1

                # cạnh root -> person (LINK_FROM_START)
                row_pe = (root_title, cand, "LINK_FROM_START")
                k_pe = _norm_tuple(*row_pe)
                if (not args.dedupe) or (k_pe not in seen_pedge):
                    w_pedges.writerow(list(row_pe)); seen_pedge.add(k_pe)

                # nếu chọn assume_university và root là trường → tạo ALUMNI_OF nếu phù hợp
                if args.assume_university and (root_type == "university") and (not root_is_person):
                    added = 0
                    root_norm = normalize(root_title)
                    for uni, year in edu:
                        if normalize(uni) == root_norm:
                            row = (uni, cand, "ALUMNI_OF", str(year) if year is not None else "")
                            k_ue = _norm_tuple(*row)
                            if (not args.dedupe) or (k_ue not in seen_uedge):
                                w_uedges.writerow(list(row)); seen_uedge.add(k_ue)
                                added += 1
                    made_edu_edges += added

                if HAS_TQDM:
                    try:
                        iterator.set_postfix(seeds=ok_people, edu=made_edu_edges, err=errors)
                    except Exception:
                        pass
                else:
                    if processed % args.progress_every == 0:
                        print(f"  [{processed}/{len(candidates)}] seeds={ok_people} edu={made_edu_edges} err={errors}")

            except Exception:
                errors += 1
                if not HAS_TQDM and processed % args.progress_every == 0:
                    print(f"  [{processed}/{len(candidates)}] seeds={ok_people} edu={made_edu_edges} err={errors}")
                continue

        print(f"  ✅ root done: seeds+={ok_people}, edu_edges+={made_edu_edges}, errors={errors}")

    # đóng file
    for fh in (f_seeds, f_pedges, f_uedges, f_roots):
        fh.close()

    print("\n🎉 Done. Đầu ra DUY NHẤT tại:", args.outdir)
    print("  - root_nodes.csv       (root + type; phục vụ Step 3 set depth 0)")
    print("  - seeds.csv            (depth 1)")
    print("  - person_edges.csv     (LINK_FROM_START)")
    print("  - edu_edges.csv")


if __name__ == "__main__":
    main()
