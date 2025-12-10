# Dự Án Alumni Network - Cấu Trúc Sạch

## 📊 Cấu Trúc Thư Mục

```
university-alumni-graph/
├── graph_out/                          # Output chính
│   ├── node_details.json               # ✅ JSON duy nhất (chi tiết tất cả nodes)
│   ├── nodes_unified.csv               # ✅ Tất cả nodes (2,162)
│   ├── edges_unified.csv               # ✅ Tất cả edges (66,910)
│   ├── node_details.csv                # ✅ Chi tiết extended của nodes
│   ├── nodes_persons_props.csv         # ✅ Thuộc tính người
│   ├── nodes_universities_props.csv    # ✅ Thuộc tính đại học
│   ├── entity_relation_distribution.png
│   └── entity_relation_patterns.png
│
├── docs/                               # Tài liệu
│   ├── network_design.md
│   └── seed_selection.md
│
├── entity_relation_models.ipynb        # 📓 Notebook chính (NER/RE models)
│
├── Python Scripts
│   ├── create_unified_graph.py         # Build unified graph (lọc orphan edges)
│   ├── data_enrichment_vi_v3.py        # Enrichment pipeline
│   ├── run_pipeline_clean.py           # Pipeline runner
│   ├── shortest_path_demo.py           # Demo queries
│   └── step1-5_*.py                    # Pipeline steps
│
├── config_example.json                 # Config template
├── requirements.txt                    # Dependencies
├── utils_wiki.py                       # Utilities
│
└── README.md                           # Main documentation
    ├── NER_RE_MODELS_README.md         # NER/RE models docs
    ├── UNIFIED_GRAPH_README.md         # Graph integration docs
    └── ENRICHMENT_V3_SUMMARY.md        # Enrichment docs
```

## 📝 Dữ Liệu Chính

### Nodes (2,162 total)
- **person**: 1,229
- **university**: 842
- **country**: 67
- **career**: 24

### Edges (66,910 total)
- **same_birth_country**: 39,957
- **link_to**: 15,319
- **same_uni**: 8,707
- **alumni_of**: 1,629
- **same_career**: 1,298

## 🔄 Pipeline Chính

```
1. create_unified_graph.py
   ↓ (Load original + enrichment + mentions)
   ↓ (Filter orphan edges: 1,472 removed)
   ↓ Output: nodes_unified.csv, edges_unified.csv

2. entity_relation_models.ipynb
   ↓ (NER Model + RE Model + EntityRelationGraph)
   ↓ (Visualizations + Analysis + Queries)
   ↓ Output: Charts + Statistics + Insights
```

## 🎯 Sử Dụng

### Chạy Graph Integration
```bash
python create_unified_graph.py
```

### Chạy Analysis Notebook
```bash
jupyter notebook entity_relation_models.ipynb
```

### Chạy Pipeline Enrichment
```bash
python run_pipeline_clean.py
```
