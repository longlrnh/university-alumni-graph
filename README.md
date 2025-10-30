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
```

=======
# Mạng lưới Cựu Sinh viên Quốc tế — Pipeline

Cách chạy dự án
🔹 — Chạy tự động toàn bộ
python run_pipeline_clean.py

File này tự động:
Gọi lần lượt các bước Step1 → Step4
Xuất toàn bộ file .csv và .json vào thư mục graph_out/
