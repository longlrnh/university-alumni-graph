# Seed Selection & BFS Expansion (VI/EN)

## 1) Mục tiêu
Xác định cách **khởi tạo tập hạt giống (seed set)** và **mở rộng** để bao phủ mạng lưới Alumni–University có chất lượng, hạn chế spam/noise.

## 2) Seed theo Category (Hiện có)
- Lấy tất cả **Person** nằm trong các subcategory của ROOT_CATEGORY = “Cựu sinh viên <Trường X>”.
- Ưu điểm: to/có kiểm định bởi cộng đồng.
- Nhược điểm: có thể **thiếu** nhân vật chưa được gắn category đúng.

## 3) Seed thủ công 10–20 người (Manual Top-K)
- Chọn 10–20 nhân vật **tiêu biểu** (profile rõ, có Infobox tốt), mỗi người thuộc **nhiều trường** hoặc trường top.
- Ghi seed vào `data/seeds_manual.csv` (đề xuất cấu trúc: `person,person_url,source_note`).

## 4) Chiến lược Mở rộng (BFS/Layered Crawl)
> **Lưu ý**: Phần này là hướng mở rộng, chưa có trong pipeline hiện tại.

### 4.1 BFS qua Liên kết Nội bộ (Person → Person)
- Từ mỗi `Person` seed, duyệt các **liên kết nội bộ** ra các `Person` khác.
- Điều kiện giữ lại ứng viên:
  - Trang có **Infobox Person**.
  - Có trường `alma_mater`/`education`/tương tự với giá trị hợp lệ.
- Dừng theo **độ sâu (depth)** và **ngưỡng số node** để tránh bùng nổ.

### 4.2 Khuếch đại theo “shared features”
- **SHARED_UNI**: nếu hai Person có trường chung trong `universities_category`.
- **SAME_GRAD_YEAR** *(nếu trích xuất được năm)*.
- **LINKS_TO weight**: ưu tiên các node được nhiều seed liên kết tới.

### 4.3 Ưu tiên/Chấm điểm (Scoring)
Ví dụ công thức:
```
score(P) = w1 * links_from_seed(P) + w2 * shared_uni(P) + w3 * same_grad_year(P)
```
Chỉ nhận vào BFS-frontier các node có `score >= τ` và nằm trong whitelist điều kiện Infobox.

## 5) Kiểm soát Chất lượng (QC)
- **Whitelist** trường (US universities list) để giảm nhiễu.
- Bỏ trùng tên/đồng âm qua **Wikidata QID** (tùy chọn).
- Log sự kiện: cho biết vì sao một Person được thêm (RULE, DEPTH, SCORE…).

## 6) Đầu ra Mong đợi
- **`edges_pp.csv`** *(tùy chọn)*: Person–Person (LINKS_TO/SHARED_UNI/SAME_GRAD_YEAR)
- **`nodes_universities.csv`** *(tùy chọn)*: danh sách University chuẩn hóa
- **`seeds_manual.csv`**: seed do người dùng cung cấp
- **`seeds_from_category.csv`**: seed tự động từ category

## 7) Kịch bản Chạy (Gợi ý)
1. Chạy bước **category → people/edges** để có base.
2. Chạy **infobox parser** để lấy thuộc tính.
3. (Tùy chọn) Chạy **BFS mở rộng** (module riêng) với tham số `max_depth`, `max_nodes`, `min_score`.
4. Hợp nhất & xuất các bảng **final_long/final_wide** + các cạnh mở rộng.

## 8) Hạn chế & Rủi ro
- BFS có thể kéo vào **nhân vật ngoài phạm vi** nếu liên kết quá rộng.
- Infobox không đồng nhất, tên trường thiếu chuẩn có thể gây sai khác.
- Cần giám sát thủ công ở vòng đầu để hiệu chỉnh ngưỡng/score.
