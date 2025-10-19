# -*- coding: utf-8 -*-
"""
Đọc các CSV trong graph_out/ và xuất JSON:
- graph.json   : {nodes: [...], links: [...] } (schema kiểu D3)
- edges_up.json  (U->P), edges_pp.json (P->P)
- nodes_persons.json, nodes_universities.json
"""
import json, os, argparse, pandas as pd

def to_node_id_map(dfP, dfU):
    ids = {}
    k = 0
    for t in dfP["person_title"]:
        if t not in ids:
            ids[t] = {"id": k, "title": t, "type": "Person"}; k += 1
    for t in dfU["university_title"]:
        if t not in ids:
            ids[t] = {"id": k, "title": t, "type": "University"}; k += 1
    return ids

def main(indir="graph_out", out="graph.json"):
    # đọc CSV
    dfP = pd.read_csv(os.path.join(indir, "nodes_persons.csv"), encoding="utf-8-sig")
    dfU = pd.read_csv(os.path.join(indir, "nodes_universities.csv"), encoding="utf-8-sig")
    dfUP = pd.read_csv(os.path.join(indir, "edges_up.csv"), encoding="utf-8-sig")      # U->P
    dfPP = pd.read_csv(os.path.join(indir, "edges_pp.csv"), encoding="utf-8-sig")      # P->P

    # map node -> id
    idmap = to_node_id_map(dfP, dfU)

    # nodes (D3 schema)
    nodes = list(idmap.values())

    # links: U->P
    links = []
    for _, r in dfUP.iterrows():
        u, p = r["university_title"], r["person_title"]
        if u in idmap and p in idmap:
            links.append({
                "source": idmap[u]["id"],
                "target": idmap[p]["id"],
                "type": "ALUMNI_OF",
                "year": (None if (str(r.get("year",""))=="" or pd.isna(r.get("year"))) else int(r["year"]))
            })

    # links: P->P (LINKS_TO / SHARED_UNI / SAME_GRAD_YEAR)
    for _, r in dfPP.iterrows():
        a, b, rel = r["src_person"], r["dst_person"], r["relation"]
        if a in idmap and b in idmap:
            prop = {}
            if "shared_universities" in r and isinstance(r["shared_universities"], str):
                prop["shared_universities"] = [x.strip() for x in r["shared_universities"].split(";") if x.strip()]
            if "same_grad_year" in r and not pd.isna(r["same_grad_year"]):
                prop["same_grad_year"] = bool(int(r["same_grad_year"]))
            links.append({
                "source": idmap[a]["id"],
                "target": idmap[b]["id"],
                "type": rel,
                **prop
            })

    # ghi JSON chính
    g = {"nodes": nodes, "links": links}
    with open(os.path.join(indir, out), "w", encoding="utf-8") as f:
        json.dump(g, f, ensure_ascii=False, indent=2)

    # ghi JSON riêng lẻ (nếu cần)
    dfP.to_json(os.path.join(indir, "nodes_persons.json"), orient="records", force_ascii=False, indent=2)
    dfU.to_json(os.path.join(indir, "nodes_universities.json"), orient="records", force_ascii=False, indent=2)
    dfUP.to_json(os.path.join(indir, "edges_up.json"), orient="records", force_ascii=False, indent=2)
    dfPP.to_json(os.path.join(indir, "edges_pp.json"), orient="records", force_ascii=False, indent=2)

    print(f"[DONE] Saved {os.path.join(indir, out)} + JSON phụ")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="graph_out")
    ap.add_argument("--out", default="graph.json")
    args = ap.parse_args()
    main(args.indir, args.out)
