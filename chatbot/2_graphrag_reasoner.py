# -*- coding: utf-8 -*-
"""
2_graphrag_reasoner.py
Triển khai GraphRAG và suy luận Multi-hop trên đồ thị
"""
from typing import List, Dict, Optional
import importlib

KnowledgeGraph = None  # Sẽ được import khi cần

class GraphRAGReasoner:
    """Triển khai GraphRAG + Multi-hop Reasoning"""
    
    def __init__(self, kg):
        self.kg = kg
    
    def _normalize_text(self, text: str) -> str:
        """Chuẩn hóa để so khớp tự do trong câu hỏi"""
        import unicodedata
        import re
        s = unicodedata.normalize('NFD', text)
        s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
        s = s.lower().replace('_', ' ').replace('-', ' ')
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        return " ".join(s.split())
    
    def retrieve_context(self, query: str, max_hops: int = 2) -> str:
        """
        Truy xuất ngữ cảnh từ Knowledge Graph (GraphRAG)
        - Tích xuất entities từ query
        - Lấy thông tin từ đồ thị
        """
        entities = self._extract_entities(query)
        
        if not entities:
            return "Không tìm thấy thực thể nào trong đồ thị."
        
        context_parts = ["=== NGỮ CẢNH TỪ KNOWLEDGE GRAPH ===\n"]
        found_entities = []
        missing_entities = []
        
        for entity in entities[:5]:
            node_id = self.kg.title_to_node.get(entity)
            if node_id:
                found_entities.append(entity)
                info = self.kg.get_node_info(node_id)
                context_parts.append(self._format_node_info(info))
                
                # Thêm thông tin về các cạnh/quan hệ/kết nối
                neighbors = self.kg.get_neighbors(node_id)
                if neighbors:
                    context_parts.append(f"  🔗 Các cạnh kết nối ({len(neighbors)} quan hệ):")
                    for n in neighbors[:5]:
                        context_parts.append(f"     • {n['title']} [quan hệ: {n['relation']}]")
            else:
                missing_entities.append(entity)
        
        # Thông báo về entities không tìm thấy
        if missing_entities:
            context_parts.append(f"\n⚠️  Không tìm thấy các thực thể sau trong đồ thị: {', '.join(missing_entities)}")
        
        return "\n".join(context_parts)
    
    def _extract_entities(self, query: str) -> List[str]:
        """Trích xuất tên entities từ query"""
        entities = []
        norm_query = self._normalize_text(query)
        query_lower = norm_query
        
        # Keywords không phải entities (CHỈ skip khi đứng độc lập)
        skip_keywords = ['trường', 'học', 'những', 'nào', 'cơ', 'có', 'không', 'và', 'hay',
                        'được', 'cùng', 'liên quan', 'kết nối', 'mối', 'người', 'ai', 'là', 'gì',
                        'nơi', 'đâu', 'bao nhiêu', 'mấy', 'bao giờ', 'khi nào', 'tìm', 'lấy', 'sinh', 'vien']
        
        for title in self.kg.title_to_node.keys():
            title_normalized = self._normalize_text(title)
            # Chỉ lấy nếu title xuất hiện trong query
            # KHÔNG skip "đại học" vì nó là part của tên trường (Đại học Harvard, Đại học Stanford...)
            if title_normalized in query_lower and title_normalized not in skip_keywords:
                # Kiểm tra đó là person, university, hoặc country node
                node_id = self.kg.title_to_node[title]
                node_type = self.kg.node_types.get(node_id, '').lower()
                if node_type in ['person', 'university', 'country']:
                    entities.append(title)
        
        entities.sort(key=len, reverse=True)  # Ưu tiên tên dài hơn
        return entities
    
    def _format_node_info(self, info: Dict) -> str:
        """Format thông tin nút với mô tả rõ ràng về cạnh/kết nối"""
        s = f"\n📌 {info['title']} ({info['type']})\n"
        s += f"   Số cạnh vào (in-degree): {info['in_degree']}, Số cạnh ra (out-degree): {info['out_degree']}"
        s += f"\n   💡 Giải thích: Node này có {info['in_degree'] + info['out_degree']} kết nối/quan hệ trong đồ thị"
        # Thêm properties nếu có
        props = info.get('properties')
        if props:
            if isinstance(props, dict):
                for k, v in props.items():
                    s += f"\n   • {k}: {v}"
            else:
                s += f"\n   • Properties: {props}"
        return s
    
    def check_connection(self, entity1: str, entity2: str, max_hops: int = 3) -> Dict:
        """Kiểm tra kết nối giữa 2 entities qua các cạnh/quan hệ (Multi-hop Reasoning)"""
        node1 = self.kg.title_to_node.get(entity1)
        node2 = self.kg.title_to_node.get(entity2)
        
        # Kiểm tra entity có tồn tại không
        missing = []
        if not node1:
            missing.append(entity1)
        if not node2:
            missing.append(entity2)
        
        if missing:
            return {
                'connected': False, 
                'reason': f'Không tìm thấy các thực thể sau trong đồ thị: {", ".join(missing)}',
                'missing_entities': missing
            }
        
        # Dùng đồ thị vô hướng để bắt cả trường hợp cạnh chỉ có một chiều
        try:
            undirected = self.kg.G.to_undirected(as_view=True)
            import networkx as nx
            paths = list(nx.all_simple_paths(undirected, node1, node2, cutoff=max_hops))
        except Exception:
            paths = []
        
        if not paths:
            return {
                'connected': False, 
                'reason': f'Không có đường đi (chuỗi cạnh kết nối) giữa {entity1} và {entity2} trong {max_hops} bước'
            }
        
        shortest = min(paths, key=len)
        path_desc = self._describe_path(shortest)
        
        return {
            'connected': True,
            'hops': len(shortest) - 1,
            'path': [self.kg.node_to_title[n] for n in shortest],
            'description': path_desc,
            'num_paths': len(paths),
            'explanation': f'Tìm thấy {len(paths)} đường đi qua các cạnh/quan hệ. Đường ngắn nhất có {len(shortest) - 1} cạnh.'
        }
    
    def _describe_path(self, path: List[str]) -> str:
        """Mô tả đường đi qua các cạnh/quan hệ dưới dạng text"""
        parts = []
        for i in range(len(path) - 1):
            src, dst = path[i], path[i + 1]
            src_title = self.kg.node_to_title[src]
            dst_title = self.kg.node_to_title[dst]
            # lấy relation cả hai chiều nếu có xung đột/khác nhau
            rels = []
            if self.kg.G.has_edge(src, dst):
                rels.append(self.kg.G[src][dst].get('relation'))
            if self.kg.G.has_edge(dst, src):
                rels.append(self.kg.G[dst][src].get('relation'))
            rels = [r for r in rels if r]
            if rels:
                rel_txt = ", ".join(sorted(set(rels)))
            else:
                rel_txt = "connected"
            parts.append(f"{src_title} --[cạnh: {rel_txt}]--> {dst_title}")
        return " → ".join(parts)
    
    def find_common_connections(self, entity1: str, entity2: str) -> Dict:
        """Tìm điểm chung giữa 2 entities"""
        node1 = self.kg.title_to_node.get(entity1)
        node2 = self.kg.title_to_node.get(entity2)
        
        if not node1 or not node2:
            return {'common': [], 'count': 0}
        
        # Lấy láng giềng
        neighbors1 = set(self.kg.G.successors(node1)) | set(self.kg.G.predecessors(node1))
        neighbors2 = set(self.kg.G.successors(node2)) | set(self.kg.G.predecessors(node2))
        
        common = neighbors1.intersection(neighbors2)
        
        common_list = [{
            'title': self.kg.node_to_title[n],
            'type': self.kg.node_types[n]
        } for n in list(common)[:10]]
        
        return {'common': common_list, 'count': len(common)}
    
    def check_same_university(self, person1: str, person2: str) -> Dict:
        """Kiểm tra 2 người có học cùng trường không qua cạnh alumni_of"""
        node1 = self.kg.title_to_node.get(person1)
        node2 = self.kg.title_to_node.get(person2)
        
        # Kiểm tra entity có tồn tại không
        missing = []
        if not node1:
            missing.append(person1)
        if not node2:
            missing.append(person2)
        
        if missing:
            return {
                'answer': 'KHÔNG', 
                'reason': f'Không tìm thấy các thực thể sau trong đồ thị: {", ".join(missing)}',
                'missing_entities': missing
            }
        
        # Lấy universities
        unis1 = {n['id'] for n in self.kg.get_neighbors(node1, 'alumni_of')}
        unis2 = {n['id'] for n in self.kg.get_neighbors(node2, 'alumni_of')}
        
        common = unis1.intersection(unis2)
        
        if common:
            uni_names = [self.kg.node_to_title[u] for u in common]
            return {
                'answer': 'CÓ',
                'universities': uni_names,
                'description': f"{person1} và {person2} cùng học tại: {', '.join(uni_names)}"
            }
        else:
            return {'answer': 'KHÔNG', 'description': f"{person1} và {person2} không học cùng trường"}

    def find_people_by_country_and_university(self, country_title: str, university_title: str, limit: int = 50) -> Dict:
        """Tìm các person có cạnh from_country/born_in tới country và alumni_of tới university"""
        def _resolve(title: str):
            """Tìm node id theo title với so khớp mềm (bỏ dấu, bỏ gạch dưới/khoảng trắng)"""
            import unicodedata, re
            def norm(s):
                s = unicodedata.normalize('NFD', s)
                s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
                s = s.lower().replace('_', '').replace(' ', '')
                # loại tiền tố country để so khớp linh hoạt (Trung Quoc vs country_Trung_Quoc)
                if s.startswith('country'):
                    s = s[len('country'):]
                s = re.sub(r"[^a-z0-9]+", "", s)
                return s

            t_lower = title.lower()
            # 1) So khớp exact (case-insensitive)
            for t, n in self.kg.title_to_node.items():
                if t.lower() == t_lower:
                    return n
            # 2) So khớp normalized (bỏ dấu, bỏ _ và space)
            target = norm(title)
            for t, n in self.kg.title_to_node.items():
                if norm(t) == target:
                    return n
            return None

        country_id = _resolve(country_title)
        uni_id = _resolve(university_title)

        missing = []
        if not country_id:
            missing.append(country_title)
        if not uni_id:
            missing.append(university_title)
        if missing:
            return {'people': [], 'missing': missing}

        people = []
        for node, data in self.kg.G.nodes(data=True):
            if data.get('node_type') != 'person':
                continue
            # Kiểm tra cả cạnh ra và vào (phòng khi dữ liệu đảo chiều)
            has_country = any(
                (nbr == country_id and self.kg.G[node][nbr].get('relation') in ['from_country', 'born_in'])
                for nbr in self.kg.G.successors(node)
            ) or any(
                (nbr == country_id and self.kg.G[nbr][node].get('relation') in ['from_country', 'born_in'])
                for nbr in self.kg.G.predecessors(node)
            )
            if not has_country:
                continue
            has_uni = any(
                (nbr == uni_id and self.kg.G[node][nbr].get('relation') == 'alumni_of')
                for nbr in self.kg.G.successors(node)
            ) or any(
                (nbr == uni_id and self.kg.G[nbr][node].get('relation') == 'alumni_of')
                for nbr in self.kg.G.predecessors(node)
            )
            if has_uni:
                people.append(data.get('title', node))
            if len(people) >= limit:
                break

        return {'people': people, 'missing': []}

    def find_people_by_university(self, university_title: str, limit: int = 100) -> Dict:
        """Liệt kê các person có cạnh alumni_of tới một university"""
        def _resolve(title: str):
            import unicodedata, re
            def norm(s):
                s = unicodedata.normalize('NFD', s)
                s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
                s = s.lower().replace('_', '').replace(' ', '')
                s = re.sub(r"[^a-z0-9]+", "", s)
                return s

            t_lower = title.lower()
            for t, n in self.kg.title_to_node.items():
                if t.lower() == t_lower:
                    return n
            target = norm(title)
            for t, n in self.kg.title_to_node.items():
                if norm(t) == target:
                    return n
            return None

        uni_id = _resolve(university_title)
        if not uni_id:
            return {'people': [], 'missing': [university_title]}

        people = []
        for node, data in self.kg.G.nodes(data=True):
            if data.get('node_type') != 'person':
                continue
            # alumni_of có thể là cạnh ra (person -> uni) hoặc cạnh vào (uni -> person) tùy dữ liệu
            has_uni = any(
                (nbr == uni_id and self.kg.G[node][nbr].get('relation') == 'alumni_of')
                for nbr in self.kg.G.successors(node)
            ) or any(
                (nbr == uni_id and self.kg.G[nbr][node].get('relation') == 'alumni_of')
                for nbr in self.kg.G.predecessors(node)
            )
            if has_uni:
                people.append(data.get('title', node))
            if len(people) >= limit:
                break

        return {'people': people, 'missing': []}

    def find_people_by_country(self, country_title: str, limit: int = 100) -> Dict:
        """Tìm các person có cạnh from_country/born_in tới country (không yêu cầu trường)"""
        country_id = None
        # Dùng cùng _resolve của hàm trên
        def _resolve(title: str):
            import unicodedata, re
            def norm(s):
                s = unicodedata.normalize('NFD', s)
                s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
                s = s.lower().replace('_', '').replace(' ', '')
                s = re.sub(r"[^a-z0-9]+", "", s)
                return s
            t_lower = title.lower()
            for t, n in self.kg.title_to_node.items():
                if t.lower() == t_lower:
                    return n
            target = norm(title)
            for t, n in self.kg.title_to_node.items():
                if norm(t) == target:
                    return n
            return None

        country_id = _resolve(country_title)
        if not country_id:
            return {'people': [], 'missing': [country_title]}

        people = []
        for node, data in self.kg.G.nodes(data=True):
            if data.get('node_type') != 'person':
                continue
            has_country = any(
                (nbr == country_id and self.kg.G[node][nbr].get('relation') in ['from_country', 'born_in'])
                for nbr in self.kg.G.successors(node)
            ) or any(
                (nbr == country_id and self.kg.G[nbr][node].get('relation') in ['from_country', 'born_in'])
                for nbr in self.kg.G.predecessors(node)
            )
            if has_country:
                people.append(data.get('title', node))
            if len(people) >= limit:
                break

        return {'people': people, 'missing': []}


if __name__ == "__main__":
    KnowledgeGraph = importlib.import_module('1_knowledge_graph').KnowledgeGraph
    kg = KnowledgeGraph('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')
    reasoner = GraphRAGReasoner(kg)
    
    # Test
    print("🧪 Test GraphRAG:")
    print(reasoner.retrieve_context("Barack Obama"))
