# GraphRAG Implementation - Biểu diễn Mạng Xã Hội dưới dạng Knowledge Graph

## 🎯 Tổng Quan

Dự án này thực hiện **GraphRAG** (Graph-based Retrieval Augmented Generation) để xây dựng chatbot trả lời câu hỏi về mạng lưới alumni. Mạng xã hội được biểu diễn dưới dạng **Knowledge Graph** (đồ thị tri thức) với các nodes và edges có ý nghĩa.

## 📊 Knowledge Graph Structure

### Nodes (Đỉnh)
Hệ thống có 4 loại nodes:

1. **Person** (1,229 nodes)
   - Các cá nhân nổi tiếng (chính trị gia, doanh nhân, nghệ sĩ, v.v.)
   - Attributes: `id`, `title`, `type='person'`

2. **University** (848 nodes)
   - Các trường đại học trên thế giới
   - Attributes: `id`, `title`, `type='university'`

3. **Country** (67 nodes)
   - Các quốc gia
   - Attributes: `id`, `title`, `type='country'`

4. **Career** (34 nodes)
   - Các nghề nghiệp/chức vụ
   - Attributes: `id`, `title`, `type='career'`

### Edges (Cạnh)
Hệ thống có 6 loại quan hệ:

1. **alumni_of** (1,653 edges)
   - Person → University
   - Biểu diễn mối quan hệ "học tại"

2. **same_uni** (8,707 edges)
   - Person ↔ Person
   - Hai người học cùng trường

3. **same_birth_country** (39,957 edges)
   - Person ↔ Person
   - Cùng quốc gia sinh

4. **link_to** (15,319 edges)
   - Wikipedia hyperlinks
   - Các bài viết có liên kết với nhau

5. **has_career** (1,542 edges)
   - Person → Career
   - Nghề nghiệp của cá nhân

6. **same_career** (1,298 edges)
   - Person ↔ Person
   - Cùng nghề nghiệp

**Tổng cộng: 68,476 edges**

## 🔧 GraphRAG Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER QUERY                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ENTITY EXTRACTION                             │
│  • Parse query để tìm entities (person, university, etc.)       │
│  • Fuzzy matching với nodes trong graph                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GRAPH TRAVERSAL (GraphRAG Core)               │
│  • Retrieve node information                                    │
│  • Multi-hop reasoning (tìm paths)                              │
│  • Analyze neighbors và relation types                          │
│  • Find common connections                                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CONTEXT ASSEMBLY                              │
│  • Format node details                                          │
│  • Build relation context                                       │
│  • Create structured knowledge                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LLM GENERATION                                │
│  • Use retrieved context                                        │
│  • Generate natural answer                                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                         ANSWER                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Key Features

### 1. Knowledge Graph Representation
```python
# Ví dụ: Barack Obama trong graph
Node: "Barack Obama"
  - Type: person
  - Edges:
    • alumni_of → "Đại học Harvard"
    • alumni_of → "Đại học Columbia"
    • same_uni ↔ "Michelle Obama"
    • has_career → "career_President"
    • link_to → "Joe Biden"
```

### 2. Multi-hop Reasoning
Hệ thống có thể tìm mối quan hệ qua nhiều bước:

```python
Query: "Barack Obama có kết nối với Bill Clinton không?"

Graph Traversal:
Barack Obama → [same_uni] → Michelle Obama → [link_to] → Hillary Clinton → [same_uni] → Bill Clinton

Result: Có kết nối (3 hops)
Path: Barack Obama → Michelle Obama → Hillary Clinton → Bill Clinton
```

### 3. Relation-aware Context
GraphRAG phân tích theo loại quan hệ:

```python
Query: "Barack Obama"

Context from Graph:
• alumni_of: Harvard, Columbia
• same_uni: 15 người (Michelle Obama, ...)
• has_career: President, Senator
• link_to: Joe Biden, Donald Trump, ...
```

### 4. Common Connection Detection
Tìm điểm chung giữa các entities:

```python
Query: "Barack Obama và Donald Trump"

Common Connections:
• same_uni: Yale (indirect)
• link_to: 5 người chung
• same_career: President
```

## 💻 Implementation Details

### GraphRAGRetriever Class
```python
class GraphRAGRetriever:
    def retrieve_context(self, query: str) -> str:
        """
        Truy xuất context từ Knowledge Graph
        
        Steps:
        1. Extract entities từ query
        2. Lấy node information từ graph
        3. Phân tích neighbors và relations
        4. Tìm connections giữa entities
        5. Format context cho LLM
        """
```

### MultiHopReasoner Class
```python
class MultiHopReasoner:
    def check_connection(self, entity1: str, entity2: str, max_hops: int = 3):
        """
        Tìm đường đi giữa 2 entities trong graph
        
        Uses:
        - NetworkX all_simple_paths
        - BFS/DFS traversal
        - Shortest path algorithm
        """
```

### KnowledgeGraph Class
```python
class KnowledgeGraph:
    def __init__(self, nodes_file: str, edges_file: str):
        """
        Xây dựng đồ thị từ CSV files
        
        Data structures:
        - G: NetworkX DiGraph (directed graph)
        - node_to_title: Fast lookup dict
        - title_to_node: Reverse index
        """
```

## 📈 Performance Metrics

### Graph Statistics
- **Nodes**: 2,178 (4 types)
- **Edges**: 68,476 (6 relation types)
- **Average degree**: ~31.5 edges/node
- **Graph density**: Medium (well-connected)
- **Largest component**: 99.8% of nodes

### Query Performance
- **Entity extraction**: < 50ms
- **Graph traversal**: < 100ms (for 3-hop)
- **Context retrieval**: < 200ms
- **Total response time**: < 500ms (without LLM)

## 🎯 GraphRAG vs Traditional RAG

| Feature | Traditional RAG | GraphRAG (Our Implementation) |
|---------|----------------|-------------------------------|
| Data Structure | Flat documents | Structured graph |
| Relationships | Not explicit | Explicit edges with types |
| Multi-hop | Difficult | Native support |
| Context Quality | Text chunks | Structured knowledge |
| Scalability | Token-limited | Graph-based (scales well) |

## 🔍 Example Queries

### Query 1: Direct Information
```
Query: "Barack Obama học trường nào?"
GraphRAG Process:
  1. Extract: "Barack Obama"
  2. Find node in graph
  3. Get alumni_of edges
  4. Return: Harvard, Columbia
```

### Query 2: Connection Finding
```
Query: "Bill Gates và Mark Zuckerberg có học cùng trường không?"
GraphRAG Process:
  1. Extract: "Bill Gates", "Mark Zuckerberg"
  2. Get alumni_of for both
  3. Find intersection: Harvard (both studied there)
  4. Return: Yes, cùng học Harvard
```

### Query 3: Multi-hop Reasoning
```
Query: "Elon Musk có quan hệ gì với Peter Thiel?"
GraphRAG Process:
  1. Extract: "Elon Musk", "Peter Thiel"
  2. Find paths in graph
  3. Shortest path: Elon Musk → Stanford → Peter Thiel
  4. Common: Same university, same career (entrepreneur)
```

## 🛠️ Technical Stack

- **Graph Library**: NetworkX (Python)
- **Data Storage**: CSV (nodes, edges)
- **LLM**: Qwen 0.5B / TinyLlama 1.1B / SimpleLLM
- **Query Processing**: Custom entity extraction + graph algorithms
- **Interface**: Gradio UI

## 📚 Key Files

- `kg_chatbot.ipynb`: Main implementation notebook
- `graph_out/nodes_unified.csv`: Graph nodes
- `graph_out/edges_unified.csv`: Graph edges
- `fix_missing_alumni.py`: Data quality improvement script
- `chatbot_ui.py`: Gradio interface

## 🎓 Benefits of GraphRAG

1. **Structured Knowledge**: Relationships are explicit and typed
2. **Multi-hop Reasoning**: Natural support for complex queries
3. **Explainability**: Can show the path/reasoning
4. **Accuracy**: Less hallucination than pure text RAG
5. **Scalability**: Graph operations scale well

## 🔮 Future Enhancements

1. **Graph Embeddings**: Add node2vec or GraphSAGE for similarity search
2. **Temporal Edges**: Add time dimension to relationships
3. **Confidence Scores**: Weight edges by reliability
4. **Subgraph Extraction**: Focus on relevant subgraphs for efficiency
5. **Graph Neural Networks**: Use GNN for better node representations

---

**Tóm lại**: Hệ thống này biểu diễn mạng xã hội alumni dưới dạng Knowledge Graph và áp dụng GraphRAG để truy xuất thông tin có cấu trúc, hỗ trợ multi-hop reasoning và cung cấp câu trả lời chính xác dựa trên mối quan hệ trong đồ thị.
