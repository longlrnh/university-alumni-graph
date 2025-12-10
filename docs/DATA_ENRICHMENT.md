# 📊 Hướng Dẫn Làm Giàu Dữ Liệu Đồ Thị - Data Enrichment Guide

## 🎯 Tổng Quan

Dự án này xây dựng một hệ thống toàn diện để **làm giàu dữ liệu đồ thị** (Graph Data Enrichment) về cựu sinh viên và đại học quốc tế. Hệ thống sử dụng:

- **Named Entity Recognition (NER)** - Nhận dạng thực thể (Career, Country)
- **Relationship Extraction** - Trích xuất mối quan hệ giữa các thực thể
- **Knowledge Graph Construction** - Xây dựng đồ thị tri thức
- **Data Quality Validation** - Kiểm tra chất lượng dữ liệu

---

## 📁 Cấu Trúc Tệp Tin

```
university-alumni-graph-main/
├── data_enrichment.py                 # Module làm giàu dữ liệu chính
├── advanced_ner.py                    # Module NER nâng cao
├── data_enrichment_demo.ipynb         # Jupyter notebook demo
├── requirements.txt                   # Thư viện cần thiết
├── graph_out/                         # Thư mục kết quả
│   ├── node_details.json             # Dữ liệu node gốc
│   ├── nodes_enriched.json           # Nodes sau khi làm giàu
│   ├── nodes_careers.json            # Nodes về nghề nghiệp
│   ├── nodes_countries.json          # Nodes về quốc gia
│   ├── edges_enrichment.json         # Edges mới tạo
│   ├── ner_results.json              # Kết quả NER
│   └── ...
└── docs/
    ├── DATA_ENRICHMENT.md            # Hướng dẫn này
    └── ...
```

---

## 🚀 Cài Đặt và Sử Dụng

### 1. Cài Đặt Thư Viện

```bash
# Cài đặt tất cả dependencies
pip install -r requirements.txt

# (Optional) Cài spaCy model cho tiếng Việt
python -m spacy download vi_core_news_sm

# (Optional) Cài spaCy model cho tiếng Anh
python -m spacy download en_core_web_sm
```

### 2. Chạy Module Làm Giàu Dữ Liệu

#### Cách 1: Chạy từ Command Line

```bash
# Chạy với file mặc định (graph_out/node_details.json)
python data_enrichment.py

# Chạy với file tùy chỉnh
python data_enrichment.py --input path/to/node_details.json --output path/to/output_dir
```

#### Cách 2: Sử Dụng từ Code Python

```python
from data_enrichment import GraphEnricher

# Khởi tạo enricher
enricher = GraphEnricher("graph_out/node_details.json")

# Chạy enrichment
all_nodes, new_edges = enricher.save_enriched_graph("graph_out")

# In thống kê
from data_enrichment import print_enrichment_stats
print_enrichment_stats(all_nodes, new_edges)
```

#### Cách 3: Sử Dụng Jupyter Notebook

```bash
# Mở notebook
jupyter notebook data_enrichment_demo.ipynb

# Hoặc trong VS Code, mở file .ipynb trực tiếp
```

---

## 📊 Các Thành Phần Chính

### A. CountryDatabase (Cơ sở dữ liệu quốc gia)

Chứa danh sách 40+ quốc gia và cách viết tiếng Việt.

```python
from data_enrichment import CountryDatabase

# Trích xuất quốc gia từ text
countries = CountryDatabase.extract_countries(
    "Tổng thống Mỹ sinh tại New York"
)
# Output: ['Mỹ']
```

### B. CareerDatabase (Cơ sở dữ liệu nghề nghiệp)

Chứa 50+ loại nghề nghiệp với dịch tiếng Anh.

```python
from data_enrichment import CareerDatabase

# Trích xuất nghề nghiệp từ text
careers = CareerDatabase.extract_careers_from_text(
    "Giáo sư Đại học Harvard"
)
# Output: ['Giáo sư']

# Trích xuất từ properties
properties = {"Chức vụ": "Phó Giám đốc"}
careers = CareerDatabase.extract_careers(properties)
# Output: [('Phó Giám đốc', 'Executive')]
```

### C. EntityRelationshipExtractor (Trích xuất Thực thể - Mối quan hệ)

```python
from data_enrichment import EntityRelationshipExtractor

extractor = EntityRelationshipExtractor()

# Trích xuất từ properties của node
properties = {
    "Sinh": "1951, Việt Nam",
    "Mất": "2020, Pháp",
    "Chức vụ": "Giáo sư"
}

result = extractor.extract_from_properties("Người A", properties)
# Output:
# {
#   "person": "Người A",
#   "careers": [("Giáo sư", "Academic")],
#   "countries": ["Việt Nam", "Pháp"],
#   "birth_country": "Việt Nam",
#   "death_country": "Pháp"
# }
```

### D. GraphEnricher (Làm giàu Đồ thị)

```python
from data_enrichment import GraphEnricher

# Khởi tạo
enricher = GraphEnricher("graph_out/node_details.json")

# Chạy enrichment
all_nodes, new_edges = enricher.extract_all_enrichments()

# Lưu kết quả
enricher.save_enriched_graph("graph_out")
```

---

## 🔍 Kỹ Thuật Nhận Dạng Thực Thể

### 1. Rule-Based Extraction (Cơ bản)

- Tìm kiếm pattern trong text
- So khớp với danh sách từ vựng
- Nhanh, nhưng độ chính xác hạn chế

```python
# Được sử dụng mặc định trong data_enrichment.py
text = "Giáo sư Phạm Văn A sinh năm 1950 tại Hà Nội"

countries = CountryDatabase.extract_countries(text)
# ['Việt Nam']

careers = CareerDatabase.extract_careers_from_text(text)
# ['Giáo sư']
```

### 2. spaCy NER (Mâu hơn)

- Sử dụng pre-trained models
- Nhận dạng PERSON, ORG, GPE, etc.
- Cần cài `python -m spacy download vi_core_news_sm`

```python
from advanced_ner import AdvancedNER

ner = AdvancedNER()

entities = ner.extract_entities_spacy(
    "Giáo sư Phạm Văn A làm việc tại Đại học Quốc gia Hà Nội"
)
# Output:
# {
#   'PERSON': ['Phạm Văn A'],
#   'ORG': ['Đại học Quốc gia Hà Nội']
# }
```

### 3. Transformer-Based NER (Tốt nhất)

- Sử dụng deep learning models (BERT, RoBERTa, etc.)
- Độ chính xác cao
- Chậm hơn, cần GPU

```python
from advanced_ner import AdvancedNER

ner = AdvancedNER(model_name="xlm-roberta-large-finetuned-conll03-english")

entities = ner.extract_entities_transformers(
    "Albert Einstein was born in Germany"
)
```

---

## 🔗 Trích Xuất Mối Quan Hệ

### Relationship Types (Các loại mối quan hệ)

| Type | Mô Tả | Ví Dụ |
|------|-------|-------|
| HAS_CAREER | Người có nghề | Người A -> Giáo sư |
| ASSOCIATED_WITH_COUNTRY | Liên kết với quốc gia | Người A -> Việt Nam |
| BORN_IN | Sinh tại | Người A -> Việt Nam |
| DIED_IN | Mất tại | Người A -> Pháp |
| WORKS_IN | Làm việc tại | Người A -> Mỹ |
| EDUCATED_AT | Học tại | Người A -> Harvard |

### Pattern-Based Extraction

```python
from advanced_ner import RelationshipExtractor

text = "Giáo sư Phạm Văn A sinh tại Hà Nội, mất tại Paris"

relationships = RelationshipExtractor.extract_relationships(text, {})
# Output:
# [
#   {"type": "BORN_IN", "entity": "Hà Nội", "confidence": 0.8},
#   {"type": "DIED_IN", "entity": "Paris", "confidence": 0.8}
# ]
```

---

## 📈 Chất Lượng và Validation

### Quality Metrics

```python
from advanced_ner import EnrichmentQualityMetrics

# Coverage metrics
coverage = EnrichmentQualityMetrics.calculate_coverage(
    enriched_nodes, original_nodes
)
# Output:
# {
#   "original_nodes": 1000,
#   "enriched_nodes": 1350,
#   "growth_rate": 0.35,
#   "coverage_percentage": 135.0
# }

# Extraction quality
quality = EnrichmentQualityMetrics.calculate_extraction_quality(extractions)

# Relationship validation
validation = EnrichmentQualityMetrics.validate_relationships(
    relationships, all_node_titles
)
```

### Data Quality Checks

1. **Duplicate Detection** - Kiểm tra node trùng lặp
2. **Missing Fields** - Kiểm tra trường bắt buộc
3. **Orphaned Edges** - Kiểm tra edge không có endpoint
4. **Coverage Rate** - Tỷ lệ nodes có enrichment
5. **Confidence Scores** - Điểm tin cậy của extractions

---

## 💾 Output Files

### 1. nodes_enriched.json
Tất cả nodes (original + career + country) với metadata

```json
{
  "title": "Phạm Văn A",
  "type": "person",
  "link": "https://vi.wikipedia.org/wiki/Phạm_Văn_A",
  "related": [],
  "properties": {
    "Sinh": "1950, Hà Nội",
    "Mất": "2020, Paris"
  }
}
```

### 2. edges_enrichment.json
Tất cả edges làm giàu

```json
{
  "source": "Phạm Văn A",
  "target": "Giáo sư",
  "type": "HAS_CAREER",
  "weight": 1
}
```

### 3. nodes_careers.json
Chỉ career nodes

```json
{
  "title": "Giáo sư",
  "type": "career",
  "link": "https://en.wikipedia.org/wiki/Professor",
  "properties": {"category": "Occupation"}
}
```

### 4. nodes_countries.json
Chỉ country nodes

```json
{
  "title": "Việt Nam",
  "type": "country",
  "link": "https://en.wikipedia.org/wiki/Vietnam",
  "properties": {
    "english_name": "Vietnam",
    "country_code": "VN",
    "category": "Geographic"
  }
}
```

### 5. ner_results.json
Chi tiết kết quả NER cho mỗi person

```json
{
  "person": "Phạm Văn A",
  "careers": ["Giáo sư", "Nhà khoa học"],
  "countries": ["Việt Nam", "Pháp"]
}
```

---

## 🔧 Configuration & Customization

### 1. Thêm quốc gia mới

```python
# Trong data_enrichment.py, thêm vào CountryDatabase.COUNTRIES
COUNTRIES = {
    ...
    "Hy Lạp": {"en": "Greece", "code": "GR"},
    ...
}
```

### 2. Thêm nghề nghiệp mới

```python
# Trong data_enrichment.py, thêm vào CareerDatabase.CAREERS
CAREERS = {
    ...
    "Nhà khoa học máy tính": "Computer Scientist",
    ...
}
```

### 3. Điều chỉnh Extraction Logic

```python
# Tạo custom extractor
class CustomExtractor(EntityRelationshipExtractor):
    def extract_from_properties(self, person_title, properties):
        result = super().extract_from_properties(person_title, properties)
        
        # Thêm logic tùy chỉnh
        if "Custom_Field" in properties:
            result["custom_data"] = properties["Custom_Field"]
        
        return result
```

---

## 📊 Jupyter Notebook Walkthrough

Notebook `data_enrichment_demo.ipynb` gồm 8 bước:

1. **Import Libraries** - Cài đặt thư viện
2. **Load Data** - Tải JSON nodes
3. **Text Preprocessing** - Tiền xử lý văn bản
4. **NER** - Nhận dạng thực thể
5. **Relationship Extraction** - Trích xuất mối quan hệ
6. **Create Nodes** - Tạo nodes mới
7. **Build Graph** - Xây dựng đồ thị
8. **Export & Validate** - Xuất và kiểm tra

Chạy từng cell để thấy kết quả từng bước.

---

## 🎓 Ví Dụ Sử Dụng

### Ví dụ 1: Enrichment Đơn Giản

```python
from data_enrichment import GraphEnricher

enricher = GraphEnricher("graph_out/node_details.json")
nodes, edges = enricher.extract_all_enrichments()

print(f"Nodes: {len(nodes)}")
print(f"Edges: {len(edges)}")

enricher.save_enriched_graph("graph_out")
```

### Ví dụ 2: Advanced NER

```python
from advanced_ner import AdvancedNER

ner = AdvancedNER()

text = """
Giáo sư Phạm Văn A, người sáng lập Đại học Quốc gia Hà Nội,
sinh năm 1950 tại Hà Nội, Việt Nam. Ông tốt nghiệp tại 
Đại học Cambridge, Anh và làm việc tại Mỹ từ 1975-1990.
"""

# spaCy extraction
print(ner.extract_entities_spacy(text))

# Transformer extraction
print(ner.extract_entities_transformers(text))
```

### Ví dụ 3: Relationship Extraction

```python
from advanced_ner import RelationshipExtractor

text = "Tổng thống Hồ Chí Minh sinh năm 1890 tại Thái Bình"

relationships = RelationshipExtractor.extract_relationships(text, {})

for rel in relationships:
    print(f"{rel['type']}: {rel['entity']} (confidence: {rel['confidence']})")
```

---

## 🚨 Troubleshooting

### Lỗi: "ModuleNotFoundError: No module named 'spacy'"

```bash
pip install spacy
python -m spacy download vi_core_news_sm
```

### Lỗi: "FileNotFoundError: graph_out/node_details.json"

Đảm bảo bạn đã chạy `run_pipeline_clean.py` trước:

```bash
python run_pipeline_clean.py
```

### Lỗi: "CUDA out of memory"

Nếu chạy transformers models:

```python
# Giảm batch size hoặc sử dụng CPU
import torch
torch.cuda.empty_cache()

# Hoặc sử dụng CPU
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
```

### Độ chính xác thấp

- Thử dùng advanced NER models thay vì rule-based
- Thêm nhiều ví dụ training data
- Điều chỉnh confidence thresholds

---

## 📚 Tài Liệu Tham Khảo

### Papers & Concepts
- **Named Entity Recognition**: Named Entity Recognition using BERT
- **Knowledge Graph Construction**: Knowledge Graph Completion
- **Relationship Extraction**: Distant Supervision for Relation Extraction

### Libraries
- [spaCy](https://spacy.io) - Industrial-grade NLP
- [Transformers (Hugging Face)](https://huggingface.co/transformers/) - State-of-the-art models
- [NetworkX](https://networkx.org) - Graph analysis
- [pandas](https://pandas.pydata.org) - Data manipulation

---

## 🤝 Đóng Góp

Để cải thiện dự án:

1. Mở issue trên GitHub
2. Tạo pull request với cải thiện
3. Thêm test cases cho các loại dữ liệu mới

---

## 📝 Ghi Chú

- Data quality phụ thuộc vào chất lượng Wikipedia data gốc
- Một số người nổi tiếng có thông tin không đầy đủ
- Kết quả tốt nhất khi kết hợp nhiều NER methods
- Thường xuyên validate results với domain experts

---

**Last Updated**: December 2025
**Version**: 1.0
**Status**: Active Development
