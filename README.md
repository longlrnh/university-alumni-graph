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

