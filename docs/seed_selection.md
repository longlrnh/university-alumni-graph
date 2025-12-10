# Seed Selection & BFS Expansion (VI/EN)

## 1) Mục tiêu
Xác định cách **khởi tạo tập hạt giống (seed set)** và **mở rộng** để bao phủ mạng lưới Alumni–University có chất lượng, hạn chế spam/noise.

## 2) Seed theo Category (Hiện có)
- Lấy tất cả **Person** nằm trong các subcategory của ROOT_CATEGORY = “Cựu sinh viên <Trường X>”.
- Ưu điểm: to/có kiểm định bởi cộng đồng.
- Nhược điểm: có thể **thiếu** nhân vật chưa được gắn category đúng.
