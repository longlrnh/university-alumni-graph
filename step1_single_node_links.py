# -*- coding: utf-8 -*-
import csv, json, argparse, os
from utils_wiki import fetch_parse_html, soup_from_html, extract_page_links, normalize

def append_links(outdir, src_title, targets, dedupe=False):
    path = os.path.join(outdir, "links.csv")
    write_header = not os.path.exists(path)

    existing = set()
    if dedupe and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                existing.add((r["source_title"], r["target_title"]))

    new_rows = []
    for t in targets:
        row = (normalize(src_title), t)
        if not dedupe or row not in existing:
            new_rows.append(row)

    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["source_title", "target_title"])
        for a, b in new_rows:
            w.writerow([a, b])

    return len(new_rows)

def append_info(outdir, title, links_count):
    path = os.path.join(outdir, "info.json")
    info_obj = []

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    info_obj = loaded
                elif isinstance(loaded, dict):
                    # chuyển dict cũ → list
                    info_obj = [loaded]
            except Exception:
                info_obj = []

    norm = normalize(title)
    # nếu đã có, cập nhật links_count; nếu chưa, append
    updated = False
    for item in info_obj:
        if isinstance(item, dict) and item.get("title") == norm:
            item["links_count"] = links_count
            updated = True
            break
    if not updated:
        info_obj.append({"title": norm, "links_count": links_count})

    with open(path, "w", encoding="utf-8") as f:
        json.dump(info_obj, f, ensure_ascii=False, indent=2)

def main():
    ap = argparse.ArgumentParser(description="Bước 1 — BỔ SUNG liên kết vào 1 file chung (links.csv, info.json).")
    ap.add_argument("--title", required=True, help="Ví dụ: 'Đại học Harvard' hoặc 'Barack Obama'")
    ap.add_argument("--outdir", required=True, help="Thư mục chứa links.csv & info.json (dùng chung cho mọi title)")
    ap.add_argument("--dedupe", action="store_true", help="Khử trùng khi bổ sung links")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    html, _ = fetch_parse_html(args.title)
    soup = soup_from_html(html)
    links = extract_page_links(soup)

    added = append_links(args.outdir, args.title, links, dedupe=args.dedupe)
    append_info(args.outdir, args.title, links_count=len(links))

    print(f"✅ {normalize(args.title)}: scraped={len(links)} | appended={added} → {args.outdir}/links.csv")

if __name__ == "__main__":
    main()
