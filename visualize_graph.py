"""
Tạo visualization cho Knowledge Graph
Minh họa cấu trúc đồ thị tri thức
"""

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from collections import Counter

# Load data
print("📊 Đang phân tích Knowledge Graph...")
nodes = pd.read_csv('graph_out/nodes_unified.csv')
edges = pd.read_csv('graph_out/edges_unified.csv')

# Thống kê nodes
node_types = nodes['type'].value_counts()
print("\n" + "="*80)
print("📌 THỐNG KÊ NODES")
print("="*80)
for ntype, count in node_types.items():
    print(f"  {ntype:20s}: {count:5d} nodes")
print(f"  {'TOTAL':20s}: {len(nodes):5d} nodes")

# Thống kê edges
edge_types = edges['type'].value_counts()
print("\n" + "="*80)
print("📌 THỐNG KÊ EDGES")
print("="*80)
for etype, count in edge_types.items():
    print(f"  {etype:25s}: {count:6d} edges")
print(f"  {'TOTAL':25s}: {len(edges):6d} edges")

# Vẽ biểu đồ
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Chart 1: Node distribution
axes[0].bar(node_types.index, node_types.values, color=['#3498db', '#e74c3c', '#2ecc71', '#f39c12'])
axes[0].set_title('Node Distribution in Knowledge Graph', fontsize=14, fontweight='bold')
axes[0].set_xlabel('Node Type', fontsize=12)
axes[0].set_ylabel('Count', fontsize=12)
axes[0].grid(axis='y', alpha=0.3)
for i, (idx, val) in enumerate(node_types.items()):
    axes[0].text(i, val + 30, str(val), ha='center', fontweight='bold')

# Chart 2: Edge distribution
colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']
axes[1].bar(range(len(edge_types)), edge_types.values, color=colors[:len(edge_types)])
axes[1].set_title('Edge (Relation) Distribution', fontsize=14, fontweight='bold')
axes[1].set_xlabel('Relation Type', fontsize=12)
axes[1].set_ylabel('Count', fontsize=12)
axes[1].set_xticks(range(len(edge_types)))
axes[1].set_xticklabels(edge_types.index, rotation=45, ha='right')
axes[1].grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('knowledge_graph_stats.png', dpi=300, bbox_inches='tight')
print("\n✅ Đã lưu biểu đồ: knowledge_graph_stats.png")

# Tạo visualization của một phần graph
print("\n📊 Đang tạo visualization cho subgraph...")

# Tạo graph nhỏ để visualization
G = nx.DiGraph()

# Chọn một số nodes quan trọng
sample_persons = ['Barack Obama', 'Bill Clinton', 'Elon Musk', 'Bill Gates', 'Mark Zuckerberg']
sample_unis = ['Đại học Harvard', 'Đại học Stanford', 'Đại học Yale']

# Add nodes
for person in sample_persons:
    G.add_node(person, node_type='person')

for uni in sample_unis:
    G.add_node(uni, node_type='university')

# Add edges từ data
for _, row in edges.iterrows():
    if row['from'] in sample_persons and row['to'] in sample_unis:
        G.add_edge(row['from'], row['to'], relation=row['type'])

# Visualization
plt.figure(figsize=(12, 8))
pos = nx.spring_layout(G, k=2, iterations=50)

# Màu sắc nodes
node_colors = []
for node in G.nodes():
    if node in sample_persons:
        node_colors.append('#3498db')  # Blue for persons
    else:
        node_colors.append('#e74c3c')  # Red for universities

# Vẽ graph
nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=2000, alpha=0.9)
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')
nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True, 
                        arrowsize=20, arrowstyle='->', width=2, alpha=0.6)

# Edge labels
edge_labels = nx.get_edge_attributes(G, 'relation')
nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=8)

plt.title('Knowledge Graph - Sample Subgraph\n(Blue: Person, Red: University)', 
          fontsize=14, fontweight='bold')
plt.axis('off')
plt.tight_layout()
plt.savefig('knowledge_graph_visualization.png', dpi=300, bbox_inches='tight')
print("✅ Đã lưu visualization: knowledge_graph_visualization.png")

print("\n" + "="*80)
print("✅ HOÀN THÀNH TẠO BIỂU ĐỒ")
print("="*80)
print("\nFiles đã tạo:")
print("  1. knowledge_graph_stats.png - Thống kê nodes và edges")
print("  2. knowledge_graph_visualization.png - Visualization của subgraph")
print("="*80)
