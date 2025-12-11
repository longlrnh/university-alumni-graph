# -*- coding: utf-8 -*-
"""
1_knowledge_graph.py
Xây dựng và quản lý Knowledge Graph (Đồ thị tri thức) từ dữ liệu alumni
"""
import pandas as pd
import networkx as nx
from typing import List, Dict, Optional

class KnowledgeGraph:
    """Biểu diễn mạng xã hội alumni dưới dạng Knowledge Graph"""
    
    def __init__(self, nodes_file: str, edges_file: str):
        self.G = nx.DiGraph()
        self.nodes_df = pd.read_csv(nodes_file)
        self.edges_df = pd.read_csv(edges_file)
        self._build_graph()
        self._create_indexes()
    
    def _build_graph(self):
        """Xây dựng đồ thị từ file CSV"""
        print("[+] 🔨 Xây dựng Knowledge Graph...")
        
        # Thêm nodes với attributes
        for _, row in self.nodes_df.iterrows():
            # Một số file có thể thiếu cột hoặc giá trị rỗng, nên dùng fallback an toàn
            node_id = row.get('id')
            title_raw = row.get('title')

            # Nếu id trống, thử dùng title làm id; nếu cả hai đều trống thì bỏ qua
            if (pd.isna(node_id) or node_id == '') and (pd.isna(title_raw) or title_raw == ''):
                continue  # không có id/title, bỏ qua

            if pd.isna(node_id) or node_id == '':
                node_id = title_raw  # fallback id = title

            title = title_raw if not (pd.isna(title_raw) or title_raw == '') else node_id

            node_type = row.get('type', 'unknown')

            attrs = {
                'title': title,
                'node_type': node_type
            }
            # Thêm properties nếu có
            if 'properties' in self.nodes_df.columns and pd.notnull(row.get('properties')):
                try:
                    import json
                    props = json.loads(row['properties']) if isinstance(row['properties'], str) else row['properties']
                    attrs['properties'] = props
                except:
                    attrs['properties'] = None
            
            self.G.add_node(node_id, **attrs)
        
        # Thêm edges với relation types
        for _, row in self.edges_df.iterrows():
            src = row['from']
            dst = row['to']
            rel = row['type']
            if isinstance(rel, str):
                rel = rel.strip()

            # Nếu đã có cạnh, ưu tiên giữ cạnh chuyên biệt hơn (alumni_of > link_to)
            if self.G.has_edge(src, dst):
                existing_rel = self.G[src][dst].get('relation')
                # Nếu cạnh mới là alumni_of và cạnh cũ không phải, thay thế
                if rel == 'alumni_of' and existing_rel != 'alumni_of':
                    self.G[src][dst]['relation'] = rel
                # Ngược lại giữ nguyên cạnh cũ để tránh ghi đè thông tin
                continue

            self.G.add_edge(
                src,
                dst,
                relation=rel
            )

        # Đảm bảo mọi node đều có title và node_type tối thiểu
        for node_id, data in self.G.nodes(data=True):
            if not data.get('title'):
                data['title'] = node_id
            if not data.get('node_type'):
                data['node_type'] = 'unknown'
        
        print(f"    ✓ {self.G.number_of_nodes()} nút, {self.G.number_of_edges()} cạnh")
    
    def _create_indexes(self):
        """Tạo index cho tra cứu nhanh"""
        self.node_to_title = {n: d.get('title', n) for n, d in self.G.nodes(data=True)}
        self.title_to_node = {d.get('title', n): n for n, d in self.G.nodes(data=True) if d.get('title', n)}
        self.node_types = {n: d.get('node_type', 'unknown') for n, d in self.G.nodes(data=True)}
    
    def find_paths(self, src_id: str, dst_id: str, max_hops: int = 3) -> List[List[str]]:
        """Tìm tất cả đường đi giữa hai nút (Multi-hop)"""
        try:
            paths = list(nx.all_simple_paths(self.G, src_id, dst_id, cutoff=max_hops))
            return paths
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return []
    
    def get_neighbors(self, node_id: str, relation_type: Optional[str] = None) -> List[Dict]:
        """Lấy láng giềng của một nút (kiểm tra cả cạnh ra và vào)"""
        neighbors = []
        # Cạnh ra
        for nbr in self.G.successors(node_id):
            edge_data = self.G[node_id][nbr]
            if relation_type is None or edge_data['relation'] == relation_type:
                neighbors.append({
                    'id': nbr,
                    'title': self.node_to_title.get(nbr, nbr),
                    'relation': edge_data['relation']
                })
        # Cạnh vào (phòng khi dữ liệu đảo chiều)
        for src in self.G.predecessors(node_id):
            edge_data = self.G[src][node_id]
            if relation_type is None or edge_data['relation'] == relation_type:
                neighbors.append({
                    'id': src,
                    'title': self.node_to_title.get(src, src),
                    'relation': edge_data['relation']
                })
        return neighbors
    
    def get_node_info(self, node_id: str) -> Optional[Dict]:
        """Lấy thông tin chi tiết về một nút"""
        if node_id not in self.G:
            return None
        data = self.G.nodes[node_id]
        return {
            'id': node_id,
            'title': data['title'],
            'type': data['node_type'],
            'out_degree': len(list(self.G.successors(node_id))),
            'in_degree': len(list(self.G.predecessors(node_id)))
        }
    
    def search_nodes(self, query: str, node_type: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Tìm kiếm nút theo tên"""
        query_lower = query.lower()
        results = []
        for node, data in self.G.nodes(data=True):
            if query_lower in data['title'].lower():
                if node_type is None or data['node_type'] == node_type:
                    results.append({
                        'id': node,
                        'title': data['title'],
                        'type': data['node_type']
                    })
                    if len(results) >= limit:
                        break
        return results
    
    def get_statistics(self) -> Dict:
        """Lấy thống kê tổng quan"""
        node_types = {}
        for _, d in self.G.nodes(data=True):
            t = d['node_type']
            node_types[t] = node_types.get(t, 0) + 1
        
        edge_types = {}
        for _, _, d in self.G.edges(data=True):
            t = d['relation']
            edge_types[t] = edge_types.get(t, 0) + 1
        
        return {
            'nodes': self.G.number_of_nodes(),
            'edges': self.G.number_of_edges(),
            'node_types': node_types,
            'edge_types': edge_types
        }
    
    def print_stats(self):
        """In ra thống kê"""
        stats = self.get_statistics()
        print("\n📊 THỐNG KÊ KNOWLEDGE GRAPH")
        print("=" * 60)
        print(f"🔵 Nút: {stats['nodes']}")
        for ntype, cnt in sorted(stats['node_types'].items(), key=lambda x: x[1], reverse=True):
            print(f"   • {ntype}: {cnt}")
        print(f"\n🔗 Cạnh: {stats['edges']}")
        for etype, cnt in sorted(stats['edge_types'].items(), key=lambda x: x[1], reverse=True):
            print(f"   • {etype}: {cnt}")
        print("=" * 60)


if __name__ == "__main__":
    kg = KnowledgeGraph('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')
    kg.print_stats()
