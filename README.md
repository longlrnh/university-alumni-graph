# Mạng lưới Trường Đại học và Cựu Sinh viên (Wikipedia Graph)

Dự án xây dựng **mạng tri thức** giữa các **trường đại học** và **cựu sinh viên tiêu biểu** dựa trên dữ liệu từ **Wikipedia tiếng Việt**.  
**Phạm vi**: các trường đại học tại **Hoa Kỳ**.  
**Dạng quan hệ chính**: `Person` —[:GRADUATED_FROM]-> `University`.

## Mục tiêu
- Thu thập dữ liệu từ Wikipedia tiếng Việt (infobox + liên kết nội bộ).
- Thiết kế mạng theo mô hình node–edge rõ ràng, có thuộc tính.
- Đạt tối thiểu ~1000 nút (Person + University) khi mở rộng.
- Lưu trữ/hiển thị trong Neo4j, đồng thời xuất CSV/JSON.

## Công nghệ
- Python 3.11
- requests, beautifulsoup4, mwparserfromhell, pandas
- Neo4j (tùy chọn)
  
## Cấu trúc dự án
```
university-alumni-graph/
├── data/
│   ├── universities.csv
│   ├── persons.csv
│   ├── alumni_edges.csv
│   └── seed_nodes.txt
├── docs/
│   ├── network_design.md
│   ├── seed_selection.md
│   └── dataset_description.md
├── src/
│   ├── crawler.py
│   ├── parse_infobox.py
│   └── build_graph.py
└── README.md
```

## Cách chạy nhanh (demo)
```bash
pip install -r requirements.txt
python src/crawler.py           # Tạo dữ liệu mẫu từ seed_nodes.txt
python src/build_graph.py       # Gộp dữ liệu và xuất network.json
```
Kết quả sẽ nằm trong thư mục `data/` và file `network.json` ở thư mục gốc.

## Thành viên & phân công (ví dụ)
| Họ tên | Nhiệm vụ |
|---|---|
| Thành viên A | Thu thập dữ liệu Wikipedia |
| Thành viên B | Thiết kế mô hình node–edge, seed & mở rộng |
| Thành viên C | Lưu trữ Neo4j, thống kê, trực quan hóa |

> Tài liệu yêu cầu: *Yêu cầu bài tập lớn* (mạng chất lượng, ≥1000 nút, Wikipedia tiếng Việt, báo cáo ≥10 trang, v.v.).
