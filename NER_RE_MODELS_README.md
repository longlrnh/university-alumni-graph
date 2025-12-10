# Entity Recognition & Relation Extraction Models
## Alumni Knowledge Graph - NER & RE System

### 📋 Giới thiệu

Jupyter notebook này triển khai **Mô hình Nhận dạng Thực thể (NER)** và **Mô hình Trích xuất Mối Quan hệ (RE)** cho bài tập lớn về xây dựng **Entity-Relation Graph** từ dữ liệu Alumni.

### 🎯 Mục tiêu

1. **Named Entity Recognition (NER)** - Phân loại 4 loại thực thể (Entity Types)
   - **PERSON** (1,229): Cá nhân, nhân vật lịch sử
   - **UNIVERSITY** (842): Tổ chức giáo dục
   - **COUNTRY** (67): Quốc gia, vùng lãnh thổ
   - **CAREER** (24): Nghề nghiệp, vị trí công việc

2. **Relation Extraction (RE)** - Phân loại 8 loại mối quan hệ (Relation Types)
   - **alumni_of** (1,629): Cá nhân tốt nghiệp từ đại học
   - **same_uni** (8,707): Hai cá nhân cùng trường
   - **link_to** (15,319): Cá nhân A nói/nhắc tới B
   - **has_career** (181): Cá nhân có nghề nghiệp
   - **born_in** (943): Sinh ở quốc gia/vùng
   - **from_country** (348): Quốc tịch
   - **same_birth_country** (39,957): Hai cá nhân sinh cùng quốc gia
   - **same_career** (1,298): Hai cá nhân có cùng nghề

3. **Entity-Relation Graph** - Xây dựng và phân tích
   - 2,162 nodes + 68,382 edges
   - Hỗ trợ complex queries và graph algorithms

### 📁 Cấu trúc Notebook

```
entity_relation_models.ipynb
│
├── Cell 1: Import Libraries
│   └── pandas, networkx, matplotlib, seaborn
│
├── Cell 2: Load & Explore Data
│   └── Load unified graph (nodes_unified.json, edges_unified.json)
│
├── Cell 3: NER Model Implementation
│   ├── EntityRecognitionModel class
│   ├── Entity type classification
│   └── Statistics & summary
│
├── Cell 4: RE Model Implementation
│   ├── RelationExtractionModel class
│   ├── Relation type classification
│   └── Statistics & summary
│
├── Cell 5: Build Entity-Relation Graph
│   ├── EntityRelationGraph class (NetworkX-based)
│   ├── Graph building & queries
│   └── Graph statistics
│
├── Cell 6: Visualizations
│   ├── Entity type distribution (bar chart)
│   ├── Relation type distribution (horizontal bar chart)
│   └── Entity-relation patterns (top 8 patterns)
│
├── Cell 7: Entity Analysis
│   ├── Top 5 most connected people
│   ├── Degree statistics
│   └── Neighbor analysis by relation type
│
├── Cell 8: Relation Pattern Analysis
│   ├── Top 10 entity-relation patterns
│   ├── Co-occurrence patterns
│   └── Pattern visualization
│
├── Cell 9: Model Evaluation
│   ├── NER evaluation (coverage, distribution)
│   ├── RE evaluation (coverage, distribution)
│   ├── Graph metrics (density, connectivity)
│   └── Degree statistics
│
├── Cell 10: Summary & Insights
│   ├── Key findings
│   ├── Coverage analysis
│   └── Potential applications
│
└── Cell 11: Advanced Queries
    ├── Query 1: Network around specific person
    ├── Query 2: All alumni from university
    └── Query 3: People with same career
```

### 🚀 Cách chạy

1. **Mở notebook**:
```bash
jupyter notebook entity_relation_models.ipynb
```

2. **Chạy từng cell lần lượt** hoặc chạy toàn bộ (`Ctrl+Shift+Enter`)

3. **Kết quả output**:
   - Console output: Statistics, summaries, analysis
   - Visualizations: Distribution charts, pattern charts
   - Saved files: `graph_out/entity_relation_distribution.png`, `graph_out/entity_relation_patterns.png`

### 📊 Kết quả Chính

#### NER Model Performance
- ✓ 2,162 entities recognized
- ✓ 100% coverage (all nodes classified)
- ✓ Balanced distribution: 56.8% persons, 39% universities, 3% countries, 1% careers

#### RE Model Performance
- ✓ 68,382 relations extracted
- ✓ 100% coverage (all edges classified)
- ✓ Diverse relation types: 58% same_birth_country, 22% link_to, 13% same_uni

#### Graph Topology
- **Density**: 0.0135 (sparse graph - typical for large networks)
- **Average Degree**: 60.7 (highly connected hub nodes)
- **Max Degree**: 510 (Barack Obama - most connected)
- **Components**: 97 weakly connected components

### 💡 Insights

1. **Hub Nodes** (Most Connected):
   - Barack Obama (510 connections)
   - George W. Bush (469 connections)
   - Donald Trump (460 connections)

2. **Dominant Relations**:
   - `same_birth_country`: 58% - Người cùng quốc gia tạo thành cộng đồng lớn
   - `link_to`: 22% - Mối liên hệ được mention trong văn bản
   - `same_uni`: 13% - Co-alumni network khá dày đặc

3. **Entity Patterns**:
   - `person --same_birth_country--> person`: 39,957 (chủ yếu)
   - `person --link_to--> person`: 12,711 (mention-based)
   - `person --same_uni--> person`: 8,707 (co-alumni)

### 🔧 Classes & Methods

#### EntityRecognitionModel
```python
ner_model = EntityRecognitionModel(nodes_data)
ner_model.recognize_entity(entity_id)  # Get entity type & properties
ner_model.get_entities_by_type(type)   # Filter entities by type
ner_model.get_statistics()              # Get count by type
```

#### RelationExtractionModel
```python
re_model = RelationExtractionModel(edges_data, ner_model)
re_model.extract_relation(from_id, to_id)  # Extract single relation
re_model.get_relations_by_type(type)       # Filter relations by type
re_model.get_statistics()                   # Get count by type
```

#### EntityRelationGraph
```python
erg = EntityRelationGraph(nodes_data, edges_data)
erg.analyze_entity(entity_id)           # Analyze entity neighbors
erg.get_entity_neighbors(entity_id)     # Get direct neighbors
erg.get_entity_degree(entity_id)        # Get degree statistics
```

### 📈 Ứng dụng Tiếp theo

1. **Link Prediction**: Dự đoán các mối quan hệ chưa được khám phá
2. **Community Detection**: Sử dụng Louvain/Girvan-Newman algorithm
3. **Knowledge Base Completion**: Bổ sung missing relations
4. **Entity Disambiguation**: Phân biệt entities cùng tên
5. **Semantic Reasoning**: Suy luận các quan hệ gián tiếp (e.g., A --has_career--> Career, B --has_career--> Career → A & B co-workers?)

### 📚 References

- [spaCy NER Documentation](https://spacy.io/usage/named-entities)
- [Transformers for NER](https://huggingface.co/docs/transformers/tasks/token_classification)
- [Relation Extraction Surveys](https://paperswithcode.com/task/relation-extraction)
- [NetworkX Documentation](https://networkx.org/)

### 📝 Notes

- Notebook sử dụng **heuristic-based NER** thay vì deep learning (vì data đã structured)
- **RE module** tập hợp relations từ 3 sources: original graph + enrichment + mentions
- **Deduplication logic** xử lý undirected edges để tránh A↔B duplicates
- Tất cả Vietnamese text được xử lý với UTF-8 encoding

---

**Author**: Generated for Alumni Knowledge Graph Analysis  
**Date**: December 2025  
**Status**: ✓ Complete & Tested
