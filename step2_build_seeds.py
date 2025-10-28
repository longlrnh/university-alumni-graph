# -*- coding: utf-8 -*-
import csv, argparse, json, os
from collections import defaultdict
from utils_wiki import (
    fetch_parse_html, soup_from_html, is_person_page,
    extract_person_education, normalize
)

# tqdm: dùng nếu có
try:
    from tqdm import tqdm
    HAS_TQDM = True
except Exception:
    HAS_TQDM = False


def load_candidates_grouped(links_csv, filter_title=None):
    """
    Đọc links.csv (gộp) và gom các target theo từng source_title.
    Nếu filter_title != None thì chỉ lấy đúng nhóm đó.
    Trả về: Ordered-like dict {root_title: [targets...]}
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


def load_existing_pairs(path, cols):
    """để dedupe nhanh khi append"""
    s = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                s.add(tuple(r[c] for c in cols))
    return s


def main():
    ap = argparse.ArgumentParser(
        description="Bước 2 — Multi-root: đọc 1 links.csv GỘP, xử lý từng source_title và xuất 1 bộ seeds/person_edges/edu_edges."
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
    seeds_path = os.path.join(args.outdir, "seeds.csv")
    p_edges_path = os.path.join(args.outdir, "person_edges.csv")
    u_edges_path = os.path.join(args.outdir, "edu_edges.csv")

    f_seeds, w_seeds = open_csv_writer(seeds_path, ["person_title"], append=args.append)
    f_pedges, w_pedges = open_csv_writer(p_edges_path, ["src_root","dst_person","relation"], append=args.append)
    f_uedges, w_uedges = open_csv_writer(u_edges_path, ["src_university","dst_person","relation","year"], append=args.append)

    # Dedupe sets (chỉ dùng khi --dedupe)
    seen_seed = load_existing_pairs(seeds_path, ["person_title"]) if args.dedupe else set()
    seen_pedge = load_existing_pairs(p_edges_path, ["src_root","dst_person","relation"]) if args.dedupe else set()
    seen_uedge = load_existing_pairs(u_edges_path, ["src_university","dst_person","relation","year"]) if args.dedupe else set()

    # Gom ứng viên theo từng source_title
    groups = load_candidates_grouped(args.links_csv, filter_title=args.filter_title)
    roots = list(groups.keys())

    total_roots = len(roots)
    print(f"🔹 Tổng root cần xử lý: {total_roots}")

    for idx, root in enumerate(roots, 1):
        candidates = groups[root]
        print(f"\n[{idx}/{total_roots}] ROOT = {root} | candidates = {len(candidates)}")

        # kiểm tra loại trang root (person / university / unknown)
        root_is_person = False
        try:
            h0, _ = fetch_parse_html(root)
            s0 = soup_from_html(h0)
            if s0 and is_person_page(s0):
                root_is_person = True
                if args.include_root_seed:
                    if (root,) not in seen_seed:
                        w_seeds.writerow([root]); seen_seed.add((root,))
                # nếu root là người, trích edu của chính root và ghi ALUMNI_OF (nếu muốn giữ logic này)
                edu_root = extract_person_education(s0)
                for uni, year in edu_root:
                    row = (uni, root, "ALUMNI_OF", str(year) if year is not None else "")
                    if not args.dedupe or row not in seen_uedge:
                        w_uedges.writerow(list(row)); seen_uedge.add(row)
        except Exception:
            pass

        processed = 0
        ok_people = 0
        made_edu_edges = 0
        errors = 0

        iterator = tqdm(candidates, total=len(candidates), desc=f"Scanning@{root}", unit="page") if HAS_TQDM else candidates

        for cand in iterator:
            processed += 1
            try:
                ch_html, _ = fetch_parse_html(cand)
                ch_soup = soup_from_html(ch_html)
                if not ch_soup or not is_person_page(ch_soup):
                    if not HAS_TQDM and processed % args.progress_every == 0:
                        print(f"  [{processed}/{len(candidates)}] seeds={ok_people} edu={made_edu_edges} err={errors}")
                    continue

                edu = extract_person_education(ch_soup)
                if not edu:
                    if not HAS_TQDM and processed % args.progress_every == 0:
                        print(f"  [{processed}/{len(candidates)}] seeds={ok_people} edu={made_edu_edges} err={errors}")
                    continue

                # giữ seed (người)
                row_seed = (cand,)
                if not args.dedupe or row_seed not in seen_seed:
                    w_seeds.writerow([cand]); seen_seed.add(row_seed)
                ok_people += 1

                # cạnh root -> person
                row_pe = (root, cand, "LINK_FROM_START")
                if not args.dedupe or row_pe not in seen_pedge:
                    w_pedges.writerow(list(row_pe)); seen_pedge.add(row_pe)

                # nếu chọn assume_university và root là trường → tạo ALUMNI_OF nếu phù hợp
                if args.assume_university and not root_is_person:
                    added = 0
                    for uni, year in edu:
                        if uni == root:
                            row = (uni, cand, "ALUMNI_OF", str(year) if year is not None else "")
                            if not args.dedupe or row not in seen_uedge:
                                w_uedges.writerow(list(row)); seen_uedge.add(row)
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
    for fh in (f_seeds, f_pedges, f_uedges):
        fh.close()

    print("\n🎉 Done. Đầu ra DUY NHẤT tại:", args.outdir)
    print("  - seeds.csv")
    print("  - person_edges.csv")
    print("  - edu_edges.csv")


if __name__ == "__main__":
    main()
