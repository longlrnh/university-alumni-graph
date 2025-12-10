import os
import csv
import argparse
from collections import deque
import heapq

GRAPH_DIR = "graph_out"


# ========================= UTILITIES =============================

def normalize_title(s):
    """Chuẩn hoá tên node để so khớp."""
    if s is None:
        return ""
    return " ".join(s.strip().split()).lower()


def ensure_node(graph, title):
    """Đảm bảo node tồn tại trong graph (nếu chưa thì tạo dict rỗng)."""
    if title and title not in graph:
        graph[title] = {}   # neighbor -> weight


def add_edge(graph, a, b, weight):
    """
    Thêm cạnh vô hướng có trọng số.
    Nếu cạnh đã tồn tại, giữ trọng số NHỎ hơn (đường 'rẻ' hơn).
    """
    if not a or not b:
        return

    ensure_node(graph, a)
    ensure_node(graph, b)

    # a -> b
    if b in graph[a]:
        graph[a][b] = min(graph[a][b], weight)
    else:
        graph[a][b] = weight

    # b -> a
    if a in graph[b]:
        graph[b][a] = min(graph[b][a], weight)
    else:
        graph[b][a] = weight


# ======================== LOAD NODES =============================

def load_nodes_generic(path, graph):
    """Load mọi file nodes_*.csv, thêm node vào graph (chưa có cạnh)."""
    print(f"[INFO] Load NODES: {path}")

    with open(path, "r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)

        title_col = None
        for col in rdr.fieldnames:
            if col.lower() == "title":
                title_col = col
                break
        if title_col is None:
            if len(rdr.fieldnames) >= 2:
                title_col = rdr.fieldnames[1]
            else:
                print("[WARN] Không tìm thấy cột title trong", path)
                return

        for row in rdr:
            t = (row.get(title_col) or "").strip()
            if t:
                ensure_node(graph, t)


# ======================== LOAD EDGES =============================

def load_edges_generic(path, graph):
    """
    Load mọi file edges_*.csv:
    - Tự tìm 2 cột node bằng cách tìm các cột có chữ 'person' hoặc 'university'
    - Nếu có cột 'count' => weight = 1 / (1 + count)
      (dùng cho edges_shared_uni_pp.csv)
    - Ngược lại => weight = 1.0
    """
    print(f"[INFO] Load EDGES: {path}")

    with open(path, "r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)

        possible_cols = [c for c in rdr.fieldnames
                         if "person" in c.lower() or "university" in c.lower()]
        if len(possible_cols) < 2:
            print("[WARN] Không tìm thấy 2 cột node trong", path)
            return
        col_a, col_b = possible_cols[:2]

        has_count = "count" in [c.lower() for c in rdr.fieldnames]

        for row in rdr:
            a = (row.get(col_a) or "").strip()
            b = (row.get(col_b) or "").strip()
            if not a or not b:
                continue

            weight = 1.0
            if has_count:
                count_col = None
                for c in rdr.fieldnames:
                    if c.lower() == "count":
                        count_col = c
                        break
                cnt_raw = row.get(count_col)
                try:
                    cnt = int(cnt_raw) if cnt_raw is not None and cnt_raw != "" else 1
                except Exception:
                    cnt = 1
                weight = 1.0 / (1 + cnt)

            add_edge(graph, a, b, weight)


# ======================== BUILD GRAPH =============================

def build_graph(graph_dir):
    graph = {}

    print("\n========== LOAD ALL NODES ==========")
    for fn in os.listdir(graph_dir):
        if fn.startswith("nodes_") and fn.endswith(".csv"):
            load_nodes_generic(os.path.join(graph_dir, fn), graph)

    print("\n========== LOAD ALL EDGES ==========")
    for fn in os.listdir(graph_dir):
        if fn.startswith("edges_") and fn.endswith(".csv"):
            load_edges_generic(os.path.join(graph_dir, fn), graph)

    print("\n========== SUMMARY ==========")
    print(f"[INFO] Tổng số node: {len(graph)}")
    total_edges = sum(len(v) for v in graph.values()) // 2
    print(f"[INFO] Tổng số cạnh (vô hướng): {total_edges}")

    return graph


# ======================== SHORTEST PATH ===========================

def find_node(graph, name):
    """Tìm node bằng fuzzy match."""
    if name in graph:
        return name

    name_norm = normalize_title(name)

    # match exact theo normalize
    for node in graph:
        if normalize_title(node) == name_norm:
            return node

    # substring
    candidates = [n for n in graph if name_norm in normalize_title(n)]
    if candidates:
        candidates.sort(key=len)
        return candidates[0]

    return None


def bfs_shortest_path(graph, start, goal):
    """BFS thuần (unweighted) tìm đường đi ngắn nhất theo số cạnh."""
    if start == goal:
        return [start]

    visited = set([start])
    q = deque([[start]])

    while q:
        path = q.popleft()
        u = path[-1]

        for v in graph.get(u, {}).keys():
            if v in visited:
                continue

            new_path = path + [v]
            if v == goal:
                return new_path

            visited.add(v)
            q.append(new_path)

    return None


def dijkstra_shortest_path(graph, start, goal):
    """Dijkstra tìm đường đi có tổng trọng số nhỏ nhất."""
    if start == goal:
        return [start], 0.0

    INF = float("inf")
    dist = {node: INF for node in graph}
    dist[start] = 0.0
    prev = {}

    heap = [(0.0, start)]  # (dist, node)

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        if u == goal:
            break

        for v, w in graph.get(u, {}).items():
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if dist[goal] == INF:
        return None, None

    # reconstruct path
    path = []
    cur = goal
    while True:
        path.append(cur)
        if cur == start:
            break
        cur = prev[cur]
    path.reverse()
    return path, dist[goal]


# ======================== MAIN PROGRAM ===========================

def main():
    parser = argparse.ArgumentParser(
        description="Shortest path (BFS / Dijkstra) trên graph_out/, không dùng thư viện ngoài."
    )
    parser.add_argument("--src", required=True, help="Tên node nguồn")
    parser.add_argument("--dst", required=True, help="Tên node đích")
    parser.add_argument("--graph-dir", default=GRAPH_DIR, help="Thư mục graph_out")
    parser.add_argument(
        "--weighted",
        action="store_true",
        help="Nếu bật: dùng Dijkstra (có trọng số). Nếu không: dùng BFS (không trọng số)."
    )

    args = parser.parse_args()

    print("======================================")
    print("      SHORTEST PATH DEMO (NO LIB)     ")
    print("======================================")
    print(f"SRC       = {args.src}")
    print(f"DST       = {args.dst}")
    print(f"GRAPH_DIR = {args.graph_dir}")
    print(f"WEIGHTED  = {args.weighted}")

    graph = build_graph(args.graph_dir)

    if not graph:
        print("[ERROR] Đồ thị rỗng. Kiểm tra lại graph_out/ và các file CSV.")
        return

    src = find_node(graph, args.src)
    dst = find_node(graph, args.dst)

    if src is None:
        print(f"[ERROR] Không tìm thấy node tương ứng với '{args.src}'")
        return
    if dst is None:
        print(f"[ERROR] Không tìm thấy node tương ứng với '{args.dst}'")
        return

    print(f"[INFO] Node nguồn thực tế: {src}")
    print(f"[INFO] Node đích   thực tế: {dst}")

    if not args.weighted:
        path = bfs_shortest_path(graph, src, dst)
        if path is None:
            print("[WARN] Không tồn tại đường đi (BFS, unweighted).")
            return
        print("\n===== KẾT QUẢ (BFS – UNWEIGHTED) =====")
        print(f"Số bước (số cạnh): {len(path) - 1}")
        for i, n in enumerate(path):
            print(f" {i}. {n}")
    else:
        path, cost = dijkstra_shortest_path(graph, src, dst)
        if path is None:
            print("[WARN] Không tồn tại đường đi (Dijkstra, weighted).")
            return
        print("\n===== KẾT QUẢ (DIJKSTRA – WEIGHTED) =====")
        print(f"Số bước (số cạnh): {len(path) - 1}")
        print(f"Tổng trọng số (cost): {cost}")
        for i, n in enumerate(path):
            print(f" {i}. {n}")

if __name__ == "__main__":
    main()

