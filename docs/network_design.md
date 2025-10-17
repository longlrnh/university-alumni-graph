# Network Design — University–Alumni Graph (VI/EN)

## 1) Phạm vi & Nguồn dữ liệu  
- **Nguồn**: Wikipedia tiếng Việt, gốc từ *“Thể loại:Cựu sinh viên trường đại học và cao đẳng ở Hoa Kỳ”* (ROOT_CAT). Script gọi Wikipedia API, duyệt subcategory để lấy danh sách nhân vật và sinh cạnh University→Person.  
- **Chuẩn hoá & xuất dữ liệu**: chuẩn hoá khoá Infobox, làm sạch giá trị, lọc key hiếm, và xuất CSV/Excel.

## 2) Kiểu nút (Nodes)
**Person (Alumni)**  
- Trường chính: `person`, `person_url`. Thuộc tính từ Infobox sau chuẩn hoá: `alma_mater`, `degree`, `major`, `field`, `nationality`, `occupation`, `awards`, `institution`, `known_for`, … (tạo ở dạng LONG/WIDE).  

**University**  
- Trường chính: `university`, `university_url`. Sinh từ tên subcategory (mẫu “Thể loại:Cựu sinh viên <Trường>”). Danh sách suy ra từ `edges_category.csv`.

## 3) Kiểu cạnh (Edges)
**University —(ALUMNI_OF)→ Person**  
- Sinh trực tiếp từ quan hệ category: mỗi nhân vật trong subcategory của một trường tạo một cạnh University→Person, mang các trường: `person`, `person_url`, `university`, `university_url`, `source="category"`.

## 4) Chuẩn hoá & Làm sạch thuộc tính Infobox  
- **Chuẩn hoá khoá**: map nhiều biến thể (VI/EN) về dạng thống nhất (`alma_mater`, `degree`, `major`, `field`, `nationality`, `occupation`, `awards`, `institution`, `known_for`, …).  
- **Làm sạch giá trị**: bỏ `[[link|text]]` → `text`, thay `<br>` bằng `;`, bỏ `{{...}}`, chuẩn hoá phân tách `; / xuống dòng / • / , và`.  
- **Lọc key hiếm**: chỉ giữ các key xuất hiện ở **≥ 50 người** (`KEY_MIN_PEOPLE=50`).

## 5) Đầu ra tệp  
- `people_all.csv`: danh sách Person (`person_title`, `person_url`).  
- `edges_category.csv`: cạnh University→Person.  
- `infobox_long.csv`: bảng LONG (Person–Key–Value).  
- `key_frequent.csv`: tần suất key theo số người.  
- `final_long.csv`: LONG sau lọc + merge `universities_category`.  
- `final_wide.csv` & `final_wide.xlsx`: pivot mỗi key thành cột; kèm `universities_category`.

## 6) Tập hạt giống (Seed Set)  
**Seed tự động từ Category (hiện có trong pipeline)**  
- Tập seed = toàn bộ **Person** xuất hiện trong các subcategory của ROOT_CAT (mỗi subcategory tương ứng 1 trường). Đây là seed “chính thống”, đảm bảo gắn nhãn cựu sinh viên theo từng trường.

## 7) Mở rộng từ seed (định hướng tương lai)  
- **BFS qua liên kết nội bộ Person→Person**; chỉ nhận node mới nếu có Infobox Person và trường học hợp lệ; dừng theo depth/ngưỡng.  
- Tạo thêm cạnh **LINKS_TO**, **SHARED_UNI** (dựa `universities_category`), **SAME_GRAD_YEAR** (nếu trích xuất được năm).

## 8) Mô hình dữ liệu (tóm tắt)  
```
(University {name, url})
   -[:ALUMNI_OF {source:"category"}]->
(Person {name, url, alma_mater?, degree?, major?, field?, nationality?, occupation?, awards?, institution?, known_for?, ...})

final_wide:  mỗi thuộc tính Infobox là 1 cột; có cột 'universities_category' tổng hợp từ edges.
```

