    
    def get_person_careers(self, person: str) -> List[str]:
        """Get all careers for a person"""
        node_id = self.title_to_node.get(person)
        if not node_id:
            return []
        
        careers = []
        for neighbor in self.get_neighbors_by_relation(node_id, 'has_career'):
            career_title = neighbor['title'].replace('career_', '')
            careers.append(career_title)
        
        return careers
"""
Knowledge Graph Chatbot UI
Giao diện đơn giản để tương tác với chatbot
"""

import gradio as gr
import pandas as pd
import networkx as nx
from typing import Dict, List
import json

class KnowledgeGraph:
    """Knowledge Graph for Alumni Network"""
    
    def __init__(self, nodes_file: str, edges_file: str):
        self.G = nx.DiGraph()
        self.nodes_df = pd.read_csv(nodes_file)
        self.edges_df = pd.read_csv(edges_file)
        self._build_graph()
        self._create_indexes()
        
    def _build_graph(self):
        """Build NetworkX graph from CSV files"""
        # Add nodes
        for _, row in self.nodes_df.iterrows():
            self.G.add_node(
                row['id'],
                title=row['title'],
                node_type=row['type']
            )
        
        # Add edges
        for _, row in self.edges_df.iterrows():
            self.G.add_edge(
                row['from'],
                row['to'],
                relation=row['type']
            )
    
    def _create_indexes(self):
        """Create indexes for fast lookup"""
        self.node_to_title = {node: data['title'] for node, data in self.G.nodes(data=True)}
        self.title_to_node = {data['title']: node for node, data in self.G.nodes(data=True)}
        self.node_types = {node: data['node_type'] for node, data in self.G.nodes(data=True)}
    
    def get_node_info(self, node_id: str) -> Dict:
        """Get detailed information about a node"""
        if node_id not in self.G:
            return None
        
        node_data = self.G.nodes[node_id]
        neighbors_out = list(self.G.successors(node_id))
        neighbors_in = list(self.G.predecessors(node_id))
        
        return {
            'id': node_id,
            'title': node_data['title'],
            'type': node_data['node_type'],
            'out_degree': len(neighbors_out),
            'in_degree': len(neighbors_in),
            'neighbors_out': neighbors_out[:10],
            'neighbors_in': neighbors_in[:10]
        }
    
    def find_path(self, source: str, target: str, max_hops: int = 3) -> List[List[str]]:
        """Find all paths between two nodes"""
        try:
            paths = list(nx.all_simple_paths(
                self.G, 
                source, 
                target, 
                cutoff=max_hops
            ))
            return paths
        except:
            return []


class MultiHopReasoner:
    """Multi-hop reasoning on Knowledge Graph"""
    
    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg
    
    def check_connection(self, entity1: str, entity2: str, max_hops: int = 3) -> Dict:
        """Check if two entities are connected"""
        node1 = self.kg.title_to_node.get(entity1)
        node2 = self.kg.title_to_node.get(entity2)
        
        if not node1 or not node2:
            return {
                'connected': False,
                'reason': 'Một hoặc cả hai thực thể không tìm thấy'
            }
        
        paths = self.kg.find_path(node1, node2, max_hops)
        
        if not paths:
            return {
                'connected': False,
                'reason': f'Không tìm thấy đường đi trong {max_hops} bước'
            }
        
        shortest_path = min(paths, key=len)
        path_desc = self._describe_path(shortest_path)
        
        return {
            'connected': True,
            'hops': len(shortest_path) - 1,
            'path': [self.kg.node_to_title[n] for n in shortest_path],
            'description': path_desc,
            'num_paths': len(paths)
        }
    
    def _describe_path(self, path: List[str]) -> str:
        """Create human-readable path description"""
        desc_parts = []
        
        for i in range(len(path) - 1):
            node1 = path[i]
            node2 = path[i + 1]
            
            title1 = self.kg.node_to_title[node1]
            title2 = self.kg.node_to_title[node2]
            relation = self.kg.G[node1][node2]['relation']
            
            desc_parts.append(f"{title1} --[{relation}]--> {title2}")
        
        return " → ".join(desc_parts)
    
    def check_same_university(self, person1: str, person2: str) -> Dict:
        """Check if two people attended the same university"""
        node1 = self.kg.title_to_node.get(person1)
        node2 = self.kg.title_to_node.get(person2)
        
        if not node1 or not node2:
            return {'answer': 'Unknown', 'reason': 'Không tìm thấy người'}
        
        # Get universities
        unis1 = set()
        for neighbor in self.kg.G.successors(node1):
            if self.kg.G[node1][neighbor]['relation'] == 'alumni_of':
                unis1.add(neighbor)
        
        unis2 = set()
        for neighbor in self.kg.G.successors(node2):
            if self.kg.G[node2][neighbor]['relation'] == 'alumni_of':
                unis2.add(neighbor)
        
        common_unis = unis1.intersection(unis2)
        
        if common_unis:
            uni_names = [self.kg.node_to_title[u] for u in common_unis]
            return {
                'answer': 'Yes',
                'universities': uni_names,
                'explanation': f"{person1} và {person2} cùng học tại: {', '.join(uni_names)}"
            }
        else:
            return {
                'answer': 'No',
                'explanation': f"{person1} và {person2} không học chung trường"
            }


class GraphRAGRetriever:
    """RAG system using Graph structure"""
    
    def __init__(self, kg: KnowledgeGraph, reasoner: MultiHopReasoner):
        self.kg = kg
        self.reasoner = reasoner
    
    def retrieve_context(self, query: str, max_nodes: int = 5) -> str:
        """Retrieve relevant context from graph"""
        entities = self._extract_entities(query)
        
        if not entities:
            return "Không tìm thấy thông tin liên quan trong đồ thị tri thức."
        
        context_parts = []
        
        for entity in entities[:max_nodes]:
            node_id = self.kg.title_to_node.get(entity)
            if node_id:
                info = self.kg.get_node_info(node_id)
                context_parts.append(self._format_node_context(info))
        
        return "\n\n".join(context_parts)
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract entity names from query"""
        entities = []
        query_lower = query.lower()
        
        for title in self.kg.title_to_node.keys():
            if title.lower() in query_lower:
                entities.append(title)
        
        return entities
    
    def _format_node_context(self, info: Dict) -> str:
        """Format node information as context"""
        if not info:
            return ""
        
        context = f"**{info['title']}** (Loại: {info['type']})\n"
        context += f"- Kết nối: {info['in_degree']} vào, {info['out_degree']} ra\n"
        
        if info['neighbors_out']:
            neighbors_names = [self.kg.node_to_title.get(n, n) for n in info['neighbors_out'][:3]]
            context += f"- Liên quan: {', '.join(neighbors_names)}\n"
        
        return context


class SimpleLLM:
    """Template-based response system"""
    
    def generate(self, query: str, context: str, reasoning_result: Dict = None) -> str:
        """Generate response"""
        if reasoning_result:
            if 'connected' in reasoning_result:
                if reasoning_result['connected']:
                    return f"✅ CÓ KẾT NỐI!\n\n🔍 Chi tiết:\n- Số bước: {reasoning_result['hops']}\n- Đường đi: {' → '.join(reasoning_result['path'])}\n\n📝 Mô tả:\n{reasoning_result['description']}"
                else:
                    return f"❌ KHÔNG CÓ KẾT NỐI\n\n{reasoning_result['reason']}"
            
            if 'answer' in reasoning_result:
                return f"📌 {reasoning_result.get('explanation', reasoning_result['answer'])}"
        
        if context:
            return f"📚 Thông tin từ đồ thị tri thức:\n\n{context}"
        
        return "❓ Tôi không có đủ thông tin để trả lời câu hỏi này."


class KGChatbot:
    """Main Chatbot class"""
    
    def __init__(self, kg: KnowledgeGraph, reasoner: MultiHopReasoner, 
                 rag: GraphRAGRetriever, llm):
        self.kg = kg
        self.reasoner = reasoner
        self.rag = rag
        self.llm = llm
    
    def answer(self, query: str) -> str:
        """Main answer function"""
        query_type = self._classify_query(query)
        
        reasoning_result = None
        
        if query_type == 'connection':
            entities = self.rag._extract_entities(query)
            if len(entities) >= 2:
                reasoning_result = self.reasoner.check_connection(entities[0], entities[1])
        
        elif query_type == 'university':
            entities = self.rag._extract_entities(query)
            if len(entities) >= 2:
                reasoning_result = self.reasoner.check_same_university(entities[0], entities[1])
        
                elif query_type == 'career':
                    entities = self.rag._extract_entities(query)
                    if len(entities) >= 1:
                        person = entities[0]
                        careers = self.kg.get_person_careers(person)
                        if careers:
                            reasoning_result = {
                                'answer': 'Yes',
                                'careers': careers,
                                'explanation': f"{person} có các nghề nghiệp/chức vụ: {', '.join(careers)}"
                            }
                        else:
                            reasoning_result = {
                                'answer': 'No',
                                'explanation': f"Không tìm thấy thông tin nghề nghiệp của {person}"
                            }
        
        context = self.rag.retrieve_context(query)
        answer = self.llm.generate(query, context, reasoning_result)
        
        return answer
    
    def _classify_query(self, query: str) -> str:
        """Classify query type"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['connected', 'kết nối', 'liên kết', 'quan hệ']):
            return 'connection'
        elif any(word in query_lower for word in ['university', 'trường', 'học', 'alumni']):
            return 'university'
                elif any(word in query_lower for word in ['career', 'nghề', 'công việc', 'làm gì', 'chức vụ']):
                    return 'career'
        elif any(word in query_lower for word in ['who is', 'là ai', 'thông tin']):
            return 'info'
        else:
            return 'general'


# ================================
# INITIALIZE SYSTEM
# ================================
print("🚀 Đang khởi động Knowledge Graph Chatbot...")

kg = KnowledgeGraph(
    nodes_file='graph_out/nodes_unified.csv',
    edges_file='graph_out/edges_unified.csv'
)
print("✓ Knowledge Graph loaded")

reasoner = MultiHopReasoner(kg)
print("✓ Multi-hop Reasoner initialized")

rag_retriever = GraphRAGRetriever(kg, reasoner)
print("✓ GraphRAG Retriever initialized")

llm = SimpleLLM()
print("✓ LLM initialized")

chatbot = KGChatbot(kg, reasoner, rag_retriever, llm)
print("✓ Chatbot ready!")


# ================================
# GRADIO UI
# ================================
def chat_interface(message, history):
    """Gradio chat interface"""
    response = chatbot.answer(message)
    return response


# Example queries
examples = [
    "Barack Obama và Donald Trump có kết nối không?",
    "Bill Clinton và Joe Biden có học cùng trường không?",
        "Barack Obama làm nghề gì?",
    "Winston Churchill có liên quan đến ai?",
    "Thông tin về Đại học Harvard",
]

# Create Gradio interface
with gr.Blocks(title="Knowledge Graph Chatbot", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 🤖 Knowledge Graph Chatbot
    ### Chatbot dựa trên Đồ Thị Tri Thức Alumni Network
    
    **Tính năng:**
    - ✅ Multi-hop reasoning (Suy luận đa bước)
    - ✅ GraphRAG (Truy xuất dựa trên đồ thị)
    - ✅ Kiểm tra kết nối giữa các thực thể
    - ✅ Tìm đường đi ngắn nhất
    
    **Hỏi về:**
    - Kết nối giữa 2 người: "X và Y có kết nối không?"
    - Cùng trường: "X và Y có học cùng trường không?"
    - Thông tin: "Thông tin về X"
    """)
    
    chatbot_ui = gr.ChatInterface(
        chat_interface,
        examples=examples,
        title="",
        description="Nhập câu hỏi về mạng alumni...",
        theme="soft",
        retry_btn=None,
        undo_btn=None,
        clear_btn="Xóa lịch sử"
    )
    
    gr.Markdown("""
    ---
    ### 📊 Thống kê Đồ Thị:
    - **Nodes**: 2,172 (person, university, country, career)
    - **Edges**: 68,452 mối quan hệ
    - **Relations**: alumni_of, same_uni, same_birth_country, link_to, same_career, has_career
    """)

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🌐 Starting Gradio UI...")
    print("📍 URL: http://localhost:7860")
    print("="*60 + "\n")
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
