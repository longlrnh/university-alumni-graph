# -*- coding: utf-8 -*-
"""
run_pipeline_clean.py — bản tối ưu & ổn định
Tự động làm sạch output, ép Step2 chạy lại, gộp root_nodes.csv, đảm bảo Step3 luôn có seeds.
"""

import os, sys, subprocess, json, tempfile, shutil
import pandas as pd
from utils_wiki import normalize

# =============================
# ===== GLOBAL CONFIG ========
# =============================
OUT = "graph_out"
ROOTS = [
  # People
  "Barack Obama","Elon Musk","Mark Zuckerberg","Bill Gates","Jeff Bezos",
  "Satya Nadella","Sundar Pichai","Tim Cook","Sheryl Sandberg","Peter Thiel",
  "Malala Yousafzai","Angela Merkel","Emmanuel Macron","Taylor Swift",
  # Universities
  "Đại học Harvard", "Đại học Stanford", "Đại học Oxford",
  "Đại học Cambridge", "Viện Công nghệ Massachusetts", "Đại học Yale"
]

FORCE_CLEAN = True      # Xóa sạch graph_out mỗi lần chạy
FORCE_STEP2 = True      # Ép Step2 chạy lại dù file đã tồn tại

# =============================
# ====== ENV SETTINGS =========
# =============================
ENV = os.environ.copy()
ENV["PYTHONUNBUFFERED"] = "1"

def slug(s: str):
    import re
    s = re.sub(r"\s+", "_", s.strip())
    return re.sub(r"[^\w\-\.]", "", s, flags=re.UNICODE)

def load_links_df():
    fp = os.path.join(OUT, "links.csv")
    if os.path.exists(fp):
        try:
            return pd.read_csv(fp)
        except Exception:
            return pd.DataFrame(columns=["source_title","target_title"])
    return pd.DataFrame(columns=["source_title","target_title"])

def load_info_list():
    fp = os.path.join(OUT, "info.json")
    if os.path.exists(fp):
        try:
            data = json.load(open(fp, encoding="utf-8"))
            if isinstance(data, list): return data
            if isinstance(data, dict): return [data]
        except Exception:
            pass
    return []

def info_has_root(info_list, norm_title):
    for it in info_list:
        if normalize(it.get("title","")) == norm_title:
            return True
    return False

# =============================
# ====== START PIPELINE ======
# =============================

print("=== CLEAN PIPELINE: Step1 → Step2 → Step3 ===")

# 🧹 CLEAN OUTPUT
if FORCE_CLEAN and os.path.exists(OUT):
    print(f"\n🧹 Xóa sạch thư mục {OUT}/ để chạy lại từ đầu ...")
    shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)

# ---------- PHASE 1 ----------
print("\n[PHASE 1/3] Step 1 — Crawl links & info (append nếu thiếu)")

links_df = load_links_df()
info_list = load_info_list()

for i, title in enumerate(ROOTS, 1):
    norm = normalize(title)
    has_links = False
    if not links_df.empty and "source_title" in links_df.columns:
        has_links = (links_df["source_title"].map(str) == norm).any()
    has_info = info_has_root(info_list, norm)
    if has_links and has_info:
        print(f"  [{i}/{len(ROOTS)}] ⏭️ Skip: '{title}' đã có trong links.csv & info.json")
        continue

    print(f"  [{i}/{len(ROOTS)}] step1: {title} (crawl + append)")
    subprocess.run(
        [sys.executable, "-u", "step1_single_node_links.py", "--title", title, "--outdir", OUT],
        check=True, env=ENV
    )
    links_df = load_links_df()
    info_list = load_info_list()

print(f"  ✓ links.csv rows = {links_df.shape[0]} | info.json roots = {len(info_list)}")

# ---------- PHASE 2 ----------
print("\n[PHASE 2/3] Step 2 — Build seeds & edges (multi-root)")

all_seeds = []
all_person_edges = []
all_edu_edges = []
all_root_nodes = []

for i, title in enumerate(ROOTS, 1):
    norm = normalize(title)
    root_links = links_df[links_df["source_title"].map(str) == norm]
    if root_links.empty:
        print(f"  [{i}/{len(ROOTS)}] ⚠️ Không có links cho '{title}' → bỏ qua Step2")
        continue

    tmpdir = tempfile.mkdtemp(prefix=f"_tmp_{slug(title)}_", dir=OUT)
    tmp_links_fp = os.path.join(tmpdir, "links.csv")
    root_links.to_csv(tmp_links_fp, index=False, encoding="utf-8")

    is_uni = any(k.lower() in title.lower() for k in ["đại học","university","học viện","institute","college"])
    print(f"  [{i}/{len(ROOTS)}] Step2: {title} → {'UNI' if is_uni else 'PERSON'}")

    args2 = [sys.executable, "-u", "step2_build_seeds.py",
             "--links-csv", tmp_links_fp, "--outdir", tmpdir, "--dedupe"]
    if is_uni: args2 += ["--assume-university"]
    else: args2 += ["--include-root-seed"]

    subprocess.run(args2 + ["--progress-every", "50"], check=True, env=ENV)

    for fn, col in [("seeds.csv", "person_title"), ("person_edges.csv", "src_root"),
                    ("edu_edges.csv", "src_university"), ("root_nodes.csv", "title")]:
        fp = os.path.join(tmpdir, fn)
        if os.path.exists(fp):
            df = pd.read_csv(fp)
            if fn == "seeds.csv": all_seeds.append(df)
            elif fn == "person_edges.csv": all_person_edges.append(df)
            elif fn == "edu_edges.csv": all_edu_edges.append(df)
            elif fn == "root_nodes.csv": all_root_nodes.append(df)

    shutil.rmtree(tmpdir, ignore_errors=True)

# gộp & ghi
def safe_concat(lst, cols):
    return (pd.concat(lst, ignore_index=True) if lst else pd.DataFrame(columns=cols)).drop_duplicates()

seeds_df = safe_concat(all_seeds, ["person_title"])
person_edges_df = safe_concat(all_person_edges, ["src_root","dst_person","relation"])
edu_edges_df = safe_concat(all_edu_edges, ["src_university","dst_person","relation","year"])
root_nodes_df = safe_concat(all_root_nodes, ["title","type"])

seeds_fp = os.path.join(OUT, "seeds.csv")
person_edges_fp = os.path.join(OUT, "person_edges.csv")
edu_edges_fp = os.path.join(OUT, "edu_edges.csv")
root_nodes_fp = os.path.join(OUT, "root_nodes.csv")

seeds_df.to_csv(seeds_fp, index=False, encoding="utf-8")
person_edges_df.to_csv(person_edges_fp, index=False, encoding="utf-8")
edu_edges_df.to_csv(edu_edges_fp, index=False, encoding="utf-8")
root_nodes_df.to_csv(root_nodes_fp, index=False, encoding="utf-8")

print(f"  ✓ seeds={len(seeds_df)} | person_edges={len(person_edges_df)} | edu_edges={len(edu_edges_df)} | roots={len(root_nodes_df)}")

# rescue nếu seeds trống
if seeds_df.empty and not person_edges_df.empty:
    dst = (person_edges_df.loc[person_edges_df["relation"]=="LINK_FROM_START","dst_person"]
           .dropna().drop_duplicates())
    if not dst.empty:
        pd.DataFrame({"person_title": dst}).to_csv(seeds_fp, index=False, encoding="utf-8")
        print(f"  🔁 rescued seeds.csv from person_edges: {len(dst)} rows")

# rescue root_nodes nếu thiếu
if root_nodes_df.empty:
    rows = []
    for info in load_info_list():
        t = info.get("title"); 
        if not t: continue
        tl = t.lower()
        ty = "university" if any(k in tl for k in ["đại học","university","học viện","institute","college"]) else "person"
        rows.append((t, ty))
    if rows:
        pd.DataFrame(rows, columns=["title","type"]).to_csv(root_nodes_fp, index=False, encoding="utf-8")
        print(f"  🔁 rescued root_nodes.csv with {len(rows)} rows")

# ---------- PHASE 3 ----------
print("\n[PHASE 3/3] Step 3 — BFS mở rộng → graph_out/")

step3_cmd = [
    sys.executable, "-u", "step3_bfs_expand.py",
    "--seeds", os.path.join(OUT, "seeds.csv"),
    "--config", "config_example.json",
    "--outdir", OUT,
    "--checkpoint-every", "500",
    "--flush-every", "500",
    "--roots-csv", os.path.join(OUT, "root_nodes.csv"),
    "--expand-from-university",
    "--uni-candidate-cap", "200",
    "--info-json", os.path.join(OUT, "info.json"),
]
subprocess.run(step3_cmd, check=True, env=ENV)

print("\n✅ DONE. Tất cả file cuối cùng nằm trong graph_out/:")
print("   - links.csv, info.json, seeds.csv, person_edges.csv, edu_edges.csv, root_nodes.csv")
print("   - nodes_*.csv, edges_*.csv, graph.json, nodes_people_detail.json")
