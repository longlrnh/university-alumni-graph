# -*- coding: utf-8 -*-
"""
step5_clean.py — Dọn thư mục output, chỉ giữ whitelist để import Neo4j.
"""

import os, argparse, shutil

# === Danh sách file cần giữ lại ===
KEEP_FILES = {
    # edges
    "edges_alumni_pu.csv",
    "edges_mentions_pp.csv",
    "edges_mentions_pu.csv",
    "edges_shared_uni_pp.csv",
    "edges_uni_mentions_p.csv",
    "edges_uni_mentions_u.csv",
    # graph + node details
    "graph.json",
    "node_details.csv",
    "node_details.json",
    # node props
    "nodes_persons_props.csv",
    "nodes_universities_props.csv",
}

def clean_keep_only(outdir: str, keep_files: set, dry_run: bool = False):
    removed, kept = [], []
    if not os.path.isdir(outdir):
        print(f"[Step5] Folder không tồn tại: {outdir}")
        return kept, removed

    # Xóa toàn bộ thư mục con (checkpoints/logs tạm)
    for root, dirs, files in os.walk(outdir):
        for d in list(dirs):
            full = os.path.join(root, d)
            if dry_run:
                print(f"[DRY] rmtree {full}")
            else:
                shutil.rmtree(full, ignore_errors=True)
            removed.append(os.path.relpath(full, outdir).replace("\\", "/") + "/")
        # Chỉ xử lý level 1
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, outdir).replace("\\", "/")
            if rel in keep_files:
                kept.append(rel)
            else:
                if dry_run:
                    print(f"[DRY] rm {full}")
                else:
                    try: os.remove(full)
                    except Exception: pass
                removed.append(rel)
        break
    return kept, removed

def main():
    ap = argparse.ArgumentParser(description="Step 5 — Clean output folder for Neo4j import.")
    ap.add_argument("--outdir", default="graph_out")
    ap.add_argument("--dry-run", action="store_true", help="Chỉ in, không xóa.")
    args = ap.parse_args()

    kept, removed = clean_keep_only(args.outdir, KEEP_FILES, dry_run=args.dry_run)

    print("\n✓ Đã giữ lại:")
    for k in sorted(kept): print("  •", k)
    print("🗑️  Đã xoá:")
    for r in sorted(removed): print("  •", r)

if __name__ == "__main__":
    main()
