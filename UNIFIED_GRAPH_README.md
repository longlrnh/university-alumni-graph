# Alumni Knowledge Graph - Unified Graph

## Tổng quan

Graph tổng hợp toàn bộ từ:
1. **Original graph** (alumni, mentions, same_uni)
2. **Enrichment v3** (career, country, relationships)

## 📊 Thống kê

### Nodes: 2,162
- **person**: 1,229
- **university**: 842 
- **country**: 67
- **career**: 24

### Edges: 53,063
- **same_birth_country**: 39,957 (người cùng nước sinh)
- **mentions**: 8,707 (mention trong Wikipedia)
- **alumni_of**: 1,629 (người → đại học)
- **same_career**: 1,298 (người cùng nghề)
- **born_in**: 943 (người → nước sinh)
- **from_country**: 348 (người → quốc tịch)
- **has_career**: 181 (người → nghề nghiệp)

## 🔗 Loại quan hệ (Edge Types)

### 1. **alumni_of** (Người → Đại học)
Alumni relationship từ original graph
```csv
Barack Obama,Đại học Harvard,alumni_of,1
Bill Clinton,Đại học Yale,alumni_of,1
```

### 2. **mentions** (Người → Người/Đại học)
Co-occurrence trong Wikipedia articles
```csv
Barack Obama,Michelle Obama,mentions,5
```

### 3. **same_uni** (Người ↔ Người)
Học cùng trường đại học
```csv
Barack Obama,Michelle Obama,same_uni,1
```

### 4. **born_in** (Người → Quốc gia)
Nơi sinh từ field "Sinh"
```csv
Đặng Tiểu Bình,Trung Quoc,born_in,1
A. P. J. Abdul Kalam,An Do,born_in,1
```

### 5. **from_country** (Người → Quốc gia)
Quốc tịch từ fields "Quốc tịch", "Vị trí", etc.
```csv
Barack Obama,Hoa Ky,from_country,1
```

### 6. **has_career** (Người → Nghề nghiệp)
Nghề nghiệp từ fields "Chức vụ", "Nghề nghiệp", etc.
```csv
Barack Obama,Tong thong,has_career,1
```

### 7. **same_birth_country** (Người ↔ Người)
Sinh cùng quốc gia
```csv
Barack Obama,Bill Clinton,same_birth_country,1
```

### 8. **same_career** (Người ↔ Người)
Cùng nghề nghiệp
```csv
Barack Obama,Bill Clinton,same_career,1
```

## 📁 Files

### Nodes
- `nodes_unified.json` - JSON format với metadata
- `nodes_unified.csv` - CSV format (id, title, type)

### Edges
- `edges_unified.json` - JSON format với weight
- `edges_unified.csv` - CSV format (from, to, type, weight)

## 🚀 Sử dụng

### Tạo unified graph
```bash
python create_unified_graph.py
```

### Load vào Python
```python
import json

# Load nodes
with open('graph_out/nodes_unified.json', 'r', encoding='utf-8') as f:
    nodes = json.load(f)

# Load edges
with open('graph_out/edges_unified.json', 'r', encoding='utf-8') as f:
    edges = json.load(f)

print(f"Nodes: {len(nodes)}")
print(f"Edges: {len(edges)}")
```

### Load vào NetworkX
```python
import json
import networkx as nx

# Create graph
G = nx.Graph()

# Load nodes
with open('graph_out/nodes_unified.json', 'r', encoding='utf-8') as f:
    nodes = json.load(f)
    for node in nodes:
        G.add_node(node['id'], **node)

# Load edges
with open('graph_out/edges_unified.json', 'r', encoding='utf-8') as f:
    edges = json.load(f)
    for edge in edges:
        G.add_edge(edge['from'], edge['to'], 
                   type=edge['type'], 
                   weight=edge.get('weight', 1))

print(f"Nodes: {G.number_of_nodes()}")
print(f"Edges: {G.number_of_edges()}")

# Analyze
print(f"Density: {nx.density(G):.6f}")
print(f"Connected components: {nx.number_connected_components(G)}")
```

### Import vào Neo4j
```cypher
// Load nodes
LOAD CSV WITH HEADERS FROM 'file:///nodes_unified.csv' AS row
CREATE (n:Node {id: row.id, title: row.title, type: row.type});

// Create index
CREATE INDEX node_id FOR (n:Node) ON (n.id);

// Load edges
LOAD CSV WITH HEADERS FROM 'file:///edges_unified.csv' AS row
MATCH (from:Node {id: row.from})
MATCH (to:Node {id: row.to})
CREATE (from)-[r:RELATED_TO {type: row.type, weight: toInteger(row.weight)}]->(to);
```

### Export to Gephi
CSV files có thể import trực tiếp vào Gephi:
1. Data Laboratory → Import Spreadsheet → Nodes table → `nodes_unified.csv`
2. Data Laboratory → Import Spreadsheet → Edges table → `edges_unified.csv`

## 🎯 Use Cases

### 1. Social Network Analysis
```python
# Find most connected people
degree = dict(G.degree())
top_10 = sorted(degree.items(), key=lambda x: -x[1])[:10]

# Community detection
import community
communities = community.best_partition(G)
```

### 2. Alumni Network Analysis
```python
# Filter alumni edges
alumni_edges = [e for e in edges if e['type'] == 'alumni_of']

# Universities with most alumni
uni_count = {}
for e in alumni_edges:
    uni = e['to']
    uni_count[uni] = uni_count.get(uni, 0) + 1

top_unis = sorted(uni_count.items(), key=lambda x: -x[1])[:10]
```

### 3. Career Network Analysis
```python
# Filter career edges
career_edges = [e for e in edges if e['type'] == 'has_career']

# Most common careers
career_count = {}
for e in career_edges:
    career = e['to']
    career_count[career] = career_count.get(career, 0) + 1
```

### 4. Country Analysis
```python
# Filter birth country edges
birth_edges = [e for e in edges if e['type'] == 'born_in']

# Countries with most people
country_count = {}
for e in birth_edges:
    country = e['to']
    country_count[country] = country_count.get(country, 0) + 1
```

## 🔍 Data Quality

### Node Types Fixed ✅
- Universities không còn bị mark là "person"
- Tất cả 842 universities có type="university"

### Edge Integration ✅
- Original graph: 1,629 alumni + 8,707 mentions
- Enrichment v3: 42,768 edges (career, country, relationships)
- Total: 53,063 edges

### Deduplication ✅
- Dùng (from, to, type) tuple để deduplicate
- Không có duplicate edges

## 📈 Statistics by Node Type

### Universities (842)
- Alumni edges: 1,629
- Mention edges: varies
- Top universities: Harvard, Yale, Oxford, Stanford

### Persons (1,229)
- Have careers: 181
- Have birth country: 943
- Have nationality: 348
- Connected by same_birth_country: 39,957 edges

### Countries (67)
- From birth locations, nationalities, residences
- Improved extraction with provinces (China, Vietnam, India)

### Careers (24)
- Extracted from position fields
- Examples: Tổng thống, Thủ tướng, Giáo sư, Nhà báo

## 🛠️ Technical Details

### Graph Format
- **Nodes**: `{id, title, type, link}`
- **Edges**: `{from, to, type, weight}`

### Encoding
- UTF-8 encoding for Vietnamese text
- Proper diacritics handling

### Performance
- Loading: ~2 seconds
- Processing: ~5 seconds
- Total: ~7 seconds for full pipeline

---

**Generated**: December 10, 2025
**Version**: Unified v1.0
**Status**: ✅ Production ready
