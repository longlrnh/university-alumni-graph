"""
Demo GraphRAG Implementation
Biểu diễn mạng xã hội alumni dưới dạng Knowledge Graph
"""

import pandas as pd
import networkx as nx
from typing import List, Dict

class SimpleGraphRAG:
    """Demo đơn giản về GraphRAG"""
    
    def __init__(self, nodes_file: str, edges_file: str):
        print("🚀 Khởi tạo Knowledge Graph...")
        self.G = nx.DiGraph()
        
        # Load data
        nodes_df = pd.read_csv(nodes_file)
        edges_df = pd.read_csv(edges_file)
        
        # Build graph
        for _, row in nodes_df.iterrows():
            self.G.add_node(row['id'], title=row['title'], node_type=row['type'])
        
        for _, row in edges_df.iterrows():
            self.G.add_edge(row['from'], row['to'], relation=row['type'])
        
        # Create indexes
        self.title_to_node = {data['title']: node for node, data in self.G.nodes(data=True)}
        self.node_to_title = {node: data['title'] for node, data in self.G.nodes(data=True)}
        
        print(f"✅ Graph đã sẵn sàng: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges\n")
    
    def get_node_context(self, person_name: str) -> Dict:
        """GraphRAG: Truy xuất context từ graph"""
        node_id = self.title_to_node.get(person_name)
        
        if not node_id:
            return None
        
        # Lấy thông tin node
        node_data = self.G.nodes[node_id]
        
        # Phân tích neighbors theo relation type
        relations = {}
        for neighbor in self.G.successors(node_id):
            rel_type = self.G[node_id][neighbor]['relation']
            neighbor_title = self.node_to_title[neighbor]
            
            if rel_type not in relations:
                relations[rel_type] = []
            
            relations[rel_type].append(neighbor_title)
        
        return {
            'name': person_name,
            'type': node_data['node_type'],
            'out_degree': self.G.out_degree(node_id),
            'in_degree': self.G.in_degree(node_id),
            'relations': relations
        }
    
    def find_connection(self, person1: str, person2: str, max_hops: int = 3) -> Dict:
        """Multi-hop reasoning: Tìm đường đi giữa 2 người"""
        node1 = self.title_to_node.get(person1)
        node2 = self.title_to_node.get(person2)
        
        if not node1 or not node2:
            return {'connected': False, 'reason': 'Không tìm thấy một trong hai người'}
        
        try:
            # Tìm đường đi ngắn nhất
            path = nx.shortest_path(self.G, node1, node2)
            
            # Build path description
            path_desc = []
            for i in range(len(path) - 1):
                n1, n2 = path[i], path[i+1]
                rel = self.G[n1][n2]['relation']
                path_desc.append(f"{self.node_to_title[n1]} --[{rel}]--> {self.node_to_title[n2]}")
            
            return {
                'connected': True,
                'hops': len(path) - 1,
                'path': [self.node_to_title[n] for n in path],
                'description': ' → '.join(path_desc)
            }
        except nx.NetworkXNoPath:
            return {'connected': False, 'reason': f'Không có đường đi trong vòng {max_hops} bước'}
    
    def check_same_university(self, person1: str, person2: str) -> Dict:
        """Kiểm tra có học cùng trường không"""
        node1 = self.title_to_node.get(person1)
        node2 = self.title_to_node.get(person2)
        
        if not node1 or not node2:
            return {'answer': 'Unknown'}
        
        # Lấy danh sách trường của mỗi người
        unis1 = set()
        for neighbor in self.G.successors(node1):
            if self.G[node1][neighbor]['relation'] == 'alumni_of':
                unis1.add(self.node_to_title[neighbor])
        
        unis2 = set()
        for neighbor in self.G.successors(node2):
            if self.G[node2][neighbor]['relation'] == 'alumni_of':
                unis2.add(self.node_to_title[neighbor])
        
        common = unis1.intersection(unis2)
        
        if common:
            return {
                'answer': 'Yes',
                'universities': list(common),
                'explanation': f"{person1} và {person2} cùng học tại: {', '.join(common)}"
            }
        else:
            return {
                'answer': 'No',
                'unis1': list(unis1),
                'unis2': list(unis2),
                'explanation': f"{person1} học {unis1}, {person2} học {unis2} - không trùng nhau"
            }

# =============================================================================
# DEMO
# =============================================================================

print("=" * 80)
print("DEMO: GraphRAG - Knowledge Graph cho Alumni Network")
print("=" * 80)

# Initialize
graph = SimpleGraphRAG('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')

# Demo 1: Truy xuất thông tin
print("\n📌 DEMO 1: Truy xuất thông tin từ Knowledge Graph (GraphRAG)")
print("-" * 80)
person = "Barack Obama"
context = graph.get_node_context(person)

if context:
    print(f"👤 Người: {context['name']}")
    print(f"📊 Kết nối: {context['in_degree']} incoming, {context['out_degree']} outgoing")
    print(f"\n🔗 Các mối quan hệ:")
    for rel_type, neighbors in context['relations'].items():
        print(f"   • {rel_type}: {', '.join(neighbors[:5])}")
        if len(neighbors) > 5:
            print(f"     ... và {len(neighbors) - 5} mối quan hệ khác")

# Demo 2: Multi-hop reasoning
print("\n\n📌 DEMO 2: Multi-hop Reasoning - Tìm mối liên kết")
print("-" * 80)
p1, p2 = "Barack Obama", "Bill Clinton"
connection = graph.find_connection(p1, p2)

print(f"❓ {p1} và {p2} có kết nối không?")
if connection['connected']:
    print(f"✅ Có kết nối!")
    print(f"   • Khoảng cách: {connection['hops']} bước")
    print(f"   • Đường đi: {' → '.join(connection['path'])}")
    print(f"\n   📍 Chi tiết:")
    print(f"   {connection['description']}")
else:
    print(f"❌ {connection['reason']}")

# Demo 3: Same university check
print("\n\n📌 DEMO 3: Kiểm tra học cùng trường (GraphRAG query)")
print("-" * 80)
p1, p2 = "Bill Gates", "Mark Zuckerberg"
result = graph.check_same_university(p1, p2)

print(f"❓ {p1} và {p2} có học cùng trường không?")
print(f"💬 {result['explanation']}")

# Demo 4: Another example
print("\n\n📌 DEMO 4: Ví dụ khác")
print("-" * 80)
p1, p2 = "Elon Musk", "Peter Thiel"
result = graph.check_same_university(p1, p2)

print(f"❓ {p1} và {p2} có học cùng trường không?")
print(f"💬 {result['explanation']}")

print("\n" + "=" * 80)
print("✅ HOÀN THÀNH DEMO")
print("=" * 80)
print("\n🔑 CÁC KỸ THUẬT GRAPHRAG ĐÃ SỬ DỤNG:")
print("  1. Knowledge Graph: Biểu diễn dữ liệu dưới dạng đồ thị có hướng")
print("  2. Context Retrieval: Truy xuất thông tin dựa trên cấu trúc graph")
print("  3. Multi-hop Reasoning: Tìm đường đi và phân tích quan hệ")
print("  4. Relation-aware: Phân tích theo loại quan hệ (alumni_of, same_uni, etc.)")
print("=" * 80)
