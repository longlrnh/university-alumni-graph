# -*- coding: utf-8 -*-
import os, sys, subprocess, json, tempfile, shutil
import pandas as pd
from utils_wiki import normalize

OUT = "graph_out"
os.makedirs(OUT, exist_ok=True)

# ======= ROOTS (trường + người) =======
ROOTS = [
    "Mark Zuckerberg",
    # có thể thêm nhiều root khác ở đây
]

# ép log realtime
ENV = os.environ.copy()
ENV["PYTHONUNBUFFERED"] = "1"

def slug(s: str) -> str:
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

print("=== PIPELINE (append 1 links.csv + 1 info.json + 1 seeds/person_edges/edu_edges) → graph_out/ ===")

# ---------- PHASE 1: STEP 1 APPEND (idempotent) ----------
print("\n[PHASE 1/3] Step 1 (append nếu thiếu)")
links_df = load_links_df()
info_list = load_info_list()

for i, title in enumerate(ROOTS, 1):
    norm = normalize(title)
    has_links = False
    if not links_df.empty and "source_title" in links_df.columns:
        has_links = (links_df["source_title"].map(str) == norm).any()
    has_info = info_has_root(info_list, norm)
    if has_links and has_info:
        print(f"  [{i}/{len(ROOTS)}] ⏭️ Skip step1: '{title}' đã có trong links.csv & info.json")
        continue

    print(f"  [{i}/{len(ROOTS)}] step1: {title} (append)")
    subprocess.run(
        [sys.executable, "-u", "step1_single_node_links.py",
         "--title", title, "--outdir", OUT],  # step1 sẽ tự append/dedupe theo code bạn đã chỉnh
        check=True, env=ENV
    )
    # reload sau khi append
    links_df = load_links_df()
    info_list = load_info_list()

print(f"  ✓ links.csv rows = {links_df.shape[0]} | info.json roots = {len(info_list)}")

# ---------- PHASE 2: STEP 2 PER-ROOT (không crawl lại) ----------
print("\n[PHASE 2/3] Step 2 cho từng root, dựa trên links.csv đã gộp (NO re-crawl)")

# bộ nhớ gộp
all_seeds = []
all_person_edges = []
all_edu_edges = []

for i, title in enumerate(ROOTS, 1):
    norm = normalize(title)
    # lọc links cho riêng root này
    root_links = links_df[links_df["source_title"].map(str) == norm]
    if root_links.empty:
        print(f"  [{i}/{len(ROOTS)}] ⚠️ Không có links cho '{title}' trong links.csv → bỏ qua Step2 root này")
        continue

    # nếu person_edges.csv đã có LINK_FROM_START cho root này → bỏ qua
    person_edges_fp = os.path.join(OUT, "person_edges.csv")
    if os.path.exists(person_edges_fp):
        try:
            pe = pd.read_csv(person_edges_fp)
            if not pe.empty and "relation" in pe.columns and "src_root" in pe.columns:
                if ((pe["relation"] == "LINK_FROM_START") & (pe["src_root"].map(str) == norm)).any():
                    print(f"  [{i}/{len(ROOTS)}] ⏭️ Skip step2: '{title}' đã có LINK_FROM_START trong person_edges.csv")
                    continue
        except Exception:
            pass

    # ghi một CSV tạm chỉ chứa links của root này để step2 xử lý
    tmpdir = tempfile.mkdtemp(prefix=f"_tmp_{slug(title)}_", dir=OUT)
    tmp_links_fp = os.path.join(tmpdir, "links.csv")
    root_links.to_csv(tmp_links_fp, index=False, encoding="utf-8")

    # đoán loại root (trường hay người) theo tên (heuristic nhẹ)
    is_uni = any(k.lower() in title.lower() for k in ["đại học","university","học viện","institute","college"])

    print(f"  [{i}/{len(ROOTS)}] step2: {title} → {'UNI' if is_uni else 'PERSON'}")
    args2 = [sys.executable, "-u", "step2_build_seeds.py", "--links-csv", tmp_links_fp, "--outdir", tmpdir]
    if is_uni:
        args2 += ["--assume-university"]
    else:
        args2 += ["--include-root-seed"]

    subprocess.run(args2 + ["--progress-every", "50"], check=True, env=ENV)

    # đọc kết quả tạm và gộp vào bộ nhớ
    fp_seeds = os.path.join(tmpdir, "seeds.csv")
    fp_pe    = os.path.join(tmpdir, "person_edges.csv")
    fp_ee    = os.path.join(tmpdir, "edu_edges.csv")

    if os.path.exists(fp_seeds):
        all_seeds.append(pd.read_csv(fp_seeds))
    if os.path.exists(fp_pe):
        all_person_edges.append(pd.read_csv(fp_pe))
    if os.path.exists(fp_ee):
        all_edu_edges.append(pd.read_csv(fp_ee))

    # dọn tmp
    shutil.rmtree(tmpdir, ignore_errors=True)

# gộp & dedupe → ghi ra graph_out
seeds_df = (pd.concat(all_seeds, ignore_index=True) if all_seeds else pd.DataFrame(columns=["person_title"])).drop_duplicates()
person_edges_df = (pd.concat(all_person_edges, ignore_index=True) if all_person_edges else pd.DataFrame(columns=["src_root","dst_person","relation"])).drop_duplicates()
edu_edges_df = (pd.concat(all_edu_edges, ignore_index=True) if all_edu_edges else pd.DataFrame(columns=["src_university","dst_person","relation","year"])).drop_duplicates()

# (tuỳ chọn) nếu muốn giới hạn 10 seed ban đầu:
# seeds_df = seeds_df.head(10)

seeds_fp = os.path.join(OUT, "seeds.csv")
person_edges_fp = os.path.join(OUT, "person_edges.csv")
edu_edges_fp = os.path.join(OUT, "edu_edges.csv")

seeds_df.to_csv(seeds_fp, index=False, encoding="utf-8")
person_edges_df.to_csv(person_edges_fp, index=False, encoding="utf-8")
edu_edges_df.to_csv(edu_edges_fp, index=False, encoding="utf-8")

print(f"  ✓ seeds.csv rows = {seeds_df.shape[0]} | person_edges.csv = {person_edges_df.shape[0]} | edu_edges.csv = {edu_edges_df.shape[0]}")

# ---------- PHASE 3: STEP 3 (BFS) ----------
print("\n[PHASE 3/3] Step 3 (BFS mở rộng) → graph_out/")

# dùng info.json để tự động expand-from-university (nếu bạn đã thêm cờ này trong step3)
step3_cmd = [
    sys.executable, "-u", "step3_bfs_expand.py",
    "--seeds", seeds_fp,
    "--config", "config_example.json",
    "--outdir", OUT,
    "--checkpoint-every", "500",
    "--flush-every", "500"
]

# nếu step3 của bạn có hỗ trợ 2 cờ này thì bật:
step3_cmd += ["--expand-from-university", "--info-json", os.path.join(OUT, "info.json")]

subprocess.run(step3_cmd, check=True, env=ENV)

print("\n✅ DONE. Tất cả file cuối cùng nằm trong graph_out/:")
print("   - links.csv, info.json, seeds.csv, person_edges.csv, edu_edges.csv, nodes_*.csv, edges_*.csv, graph.json")
