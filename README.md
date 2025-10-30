<<<<<<< HEAD
# Mạng lưới Trường Đại học và Cựu Sinh viên Quốc tế

Dự án xây dựng **mạng tri thức** giữa các **trường đại học** và **cựu sinh viên tiêu biểu** dựa trên dữ liệu từ **Wikipedia tiếng Việt**.  


## Mục tiêu
- Thu thập dữ liệu từ Wikipedia tiếng Việt (liên kết + infobox).
- Thiết kế mạng theo mô hình node–edge.
- Đạt tối thiểu ~1000 nút (Person + University) khi mở rộng.
- Lưu trữ/trực quan dữ liệu, đồng thời xuất CSV/JSON.

## Công nghệ
- Python 3.11
- requests, mwparserfromhell, pandas, Unidecode, xlsxwriter, BeautifulSoup
- Neo4j (tùy chọn)
  
## Cấu trúc dự án
```
university-alumni-graph/
├── step1_single_node_links.py
├── step2_build_seeds.py
├── step3_bfs_expand.py
├── step4_enrich_full.py
├── run_pipeline_clean.py
├── utils_wiki.py
├── requirements.txt
├── graph_out/               # Kết quả đầu ra (CSV, JSON)
│   ├── nodes_persons_props.csv
│   ├── nodes_universities_props.csv
│   └── ...
└── docs/
    ├── example_graph.png
    └── report.pdf
```

## Thành viên & phân công (ví dụ)
| Họ tên | Nhiệm vụ |
|---|---|
| Đỗ Tuấn Thành - 22024539 | Coding, xây dựng thuật toán mở rộng tập hạt giống |
| Vũ Hải Long - 22024539 | Thu thập dữ liệu Wikipedia, thiết kế mô hình node–edge |

=======
# Mạng lưới Cựu Sinh viên Quốc tế — Pipeline

Cách chạy toàn bộ pipeline
🔹 Tùy chọn 1 — Chạy tự động toàn bộ
python run_pipeline_clean.py

File này tự động:

Xóa dữ liệu cũ trong graph_out/

Gọi lần lượt các bước Step1 → Step4

Xuất toàn bộ file .csv và .json vào thư mục graph_out/
