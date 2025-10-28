<<<<<<< HEAD
# Mạng lưới Trường Đại học và Cựu Sinh viên Quốc tế

Dự án xây dựng **mạng tri thức** giữa các **trường đại học** và **cựu sinh viên tiêu biểu** dựa trên dữ liệu từ **Wikipedia tiếng Việt**.  
**Phạm vi**: các trường đại học tại **Hoa Kỳ**.  
**Dạng quan hệ chính**: `Person` —[:GRADUATED_FROM]-> `University`.

## Mục tiêu
- Thu thập dữ liệu từ Wikipedia tiếng Việt (liên kết + infobox).
- Thiết kế mạng theo mô hình node–edge.
- Đạt tối thiểu ~1000 nút (Person + University) khi mở rộng.
- Lưu trữ/trực quan dữ liệu, đồng thời xuất CSV/JSON.

## Công nghệ
- Python 3.11
- requests, mwparserfromhell, pandas, Unidecode, xlsxwriter
- Neo4j (tùy chọn)
  
## Cấu trúc dự án
```
university-alumni-graph/
├── data/
│   ├── edges_category.csv
│   ├── final_long.csv
│   ├── final_wide.csv
│   └── infobox_long.txt
│   └── key_frequent.txt
│   └── people_all.txt
├── docs/
│   ├── network_design.md
│   ├── seed_selection.md
├── README.md
├── requirements.txt
└── run_pipeline.py
```

## Thành viên & phân công (ví dụ)
| Họ tên | Nhiệm vụ |
|---|---|
| Đỗ Tuấn Thành - 22024539 | Coding, xây dựng thuật toán mở rộng tập hạt giống |
| Vũ Hải Long - 22024539 | Thu thập dữ liệu Wikipedia, thiết kế mô hình node–edge |

=======
# Mạng lưới Cựu Sinh viên Quốc tế — Pipeline 3 bước (Wikipedia VI)

Pipeline này thực hiện đúng yêu cầu của giáo viên:
1) **Truy cập 1 node & liên kết** → **Bước 1**: lấy liên kết nội bộ của 1 trang (ví dụ *Đại học Harvard* hoặc 1 cá nhân)
2) **Tạo tập hạt giống + danh sách ban đầu** → **Bước 2**: từ các liên kết của Bước 1, lọc ra **trang cá nhân** có mục giáo dục trong Infobox
3) **Mở rộng tập hạt giống qua thuật toán duyệt (BFS)** → **Bước 3**: lặp theo depth/giới hạn để đạt **≥ 1000 nút**; định nghĩa cạnh & xuất **CSV/JSON**

## Cấu trúc tệp
```
alumni_pipeline/
├─ utils_wiki.py                  # Hàm dùng chung: tải trang, parse, nhận diện person, trích EDUCATION
├─ step1_single_node_links.py     # Bước 1: lấy links từ 1 trang -> links.csv, info.json
├─ step2_build_seeds.py           # Bước 2: tạo seeds.csv, person_edges.csv, edu_edges.csv
├─ step3_bfs_expand.py            # Bước 3: mở rộng BFS -> nodes_*.csv, edges_*.csv, graph.json
├─ config_example.json            # Tham số mẫu cho BFS (depth, giới hạn, v.v.)
└─ README.md
```

## Cài đặt
```bash
pip install requests beautifulsoup4 pandas
```

## Chạy thử (ví dụ):
### Bước 1 — lấy liên kết từ 1 trang gốc (node ban đầu)
```bash
python step1_single_node_links.py --title "Đại học Harvard" --outdir out_harvard
```
Tạo ra:
- `out_harvard/links.csv`    : danh sách (source_title, target_title)
- `out_harvard/info.json`    : tóm tắt trang gốc (title, links_count)

### Bước 2 — tạo **tập hạt giống** & **danh sách ban đầu**
```bash
python step2_build_seeds.py --links-csv out_harvard/links.csv --outdir seeds_harvard
```
Tạo ra:
- `seeds_harvard/seeds.csv`         : danh sách trang **cá nhân** đủ điều kiện
- `seeds_harvard/person_edges.csv`  : edges trang gốc → person (LINK_FROM_START)
- `seeds_harvard/edu_edges.csv`     : edges University → Person (ALUMNI_OF {year?}) nếu gốc là trường

> Nếu node gốc là **trang cá nhân**, dùng `--title "Tên cá nhân"` thay vì `--links-csv`:
```bash
python step2_build_seeds.py --title "Barack Obama" --outdir seeds_obama
```

### Bước 3 — mở rộng tập hạt giống bằng **BFS**
```bash
python step3_bfs_expand.py --seeds seeds_harvard/seeds.csv --config config_example.json --outdir graph_out
```
Tạo ra:
- `graph_out/nodes_persons.csv`
- `graph_out/nodes_universities.csv`
- `graph_out/edges_up.csv`           (U→P, ALUMNI_OF {year?})
- `graph_out/edges_pp.csv`           (P→P, LINKS_TO)
- `graph_out/edges_shared.csv`       (P↔P, SHARED_UNI {count}) — suy luận từ EDUCATION
- `graph_out/edges_same_grad.csv`    (P↔P, SAME_GRAD_YEAR)
- `graph_out/graph.json`             (tổng hợp nodes/edges)

> **Mục tiêu ≥ 1000 nút**: chỉnh `max_person_nodes` và `per_depth_limit` trong `config_example.json` cho phù hợp.

## Import Neo4j (gợi ý)
```cypher
// Persons
LOAD CSV WITH HEADERS FROM 'file:///nodes_persons.csv' AS row
MERGE (:Person {title: trim(row.title)});

// Universities
LOAD CSV WITH HEADERS FROM 'file:///nodes_universities.csv' AS row
MERGE (:University {title: trim(row.title)}});

// ALUMNI_OF
LOAD CSV WITH HEADERS FROM 'file:///edges_up.csv' AS row
MATCH (u:University {title: trim(row.src_university)}),
      (p:Person {title: trim(row.dst_person)})
MERGE (u)-[r:ALUMNI_OF]->(p)
SET r.year = CASE WHEN row.year <> '' THEN toInteger(row.year) ELSE NULL END;

// LINKS_TO
LOAD CSV WITH HEADERS FROM 'file:///edges_pp.csv' AS row
MATCH (a:Person {title: trim(row.src_person)}),
      (b:Person {title: trim(row.dst_person)})
MERGE (a)-[:LINKS_TO]->(b);

// SHARED_UNI
LOAD CSV WITH HEADERS FROM 'file:///edges_shared.csv' AS row
MATCH (a:Person {title: trim(row.src_person)}),
      (b:Person {title: trim(row.dst_person)})
MERGE (a)-[r:SHARED_UNI]->(b)
SET r.count = toInteger(row.count);

// SAME_GRAD_YEAR
LOAD CSV WITH HEADERS FROM 'file:///edges_same_grad.csv' AS row
MATCH (a:Person {title: trim(row.src_person)}),
      (b:Person {title: trim(row.dst_person)})
MERGE (a)-[:SAME_GRAD_YEAR]->(b);
```
>>>>>>> 6bcaa52 (initial upload alumni_pipeline)
