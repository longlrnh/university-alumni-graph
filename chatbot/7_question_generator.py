# -*- coding: utf-8 -*-
"""
7_question_generator.py
Sinh 2000+ câu hỏi theo logic + tiếng Việt tự nhiên
"""
import json
import random
import importlib
from typing import List, Dict

def import_module(name):
    return importlib.import_module(name)

class VietnameseQuestionGenerator:
    """Sinh câu hỏi tiếng Việt tự nhiên theo logic"""
    
    def __init__(self, kg, seed=42):
        self.kg = kg
        random.seed(seed)
        self.people = [n for n, d in kg.G.nodes(data=True) if d['node_type'] == 'person']
        self.universities = [n for n, d in kg.G.nodes(data=True) if d['node_type'] == 'university']
    
    def generate_connection_questions(self, n=400) -> List[Dict]:
        """Sinh câu hỏi về kết nối giữa 2 người"""
        questions = []
        templates = [
            "Có kết nối nào giữa {p1} và {p2} không?",
            "{p1} và {p2} có liên kết gì không?",
            "Giữa {p1} và {p2} có mối quan hệ gì không?",
            "{p1} có được kết nối với {p2} không?",
            "Làm sao để kết nối từ {p1} đến {p2}?",
            "{p1} và {p2} có thể kết nối được không?",
            "Tìm mối liên hệ giữa {p1} và {p2}",
            "{p1} và {p2} có mối liên kết nào không?",
        ]
        
        for i in range(n):
            if len(self.people) < 2:
                break
            
            p1_id, p2_id = random.sample(self.people, 2)
            p1 = self.kg.node_to_title[p1_id]
            p2 = self.kg.node_to_title[p2_id]
            
            # Check connection
            import networkx as nx
            try:
                path = nx.shortest_path(self.kg.G, p1_id, p2_id)
                connected = True
                hops = len(path) - 1
            except:
                connected = False
                hops = 0
            
            # Generate question
            template = random.choice(templates)
            question = template.format(p1=p1, p2=p2)
            
            # Generate natural answer
            if connected:
                answer = f"Có, {p1} và {p2} có kết nối qua {hops} bước."
            else:
                answer = f"Không, {p1} và {p2} không có kết nối trực tiếp."
            
            questions.append({
                'id': i + 1,
                'type': 'connection',
                'question': question,
                'answer': answer,
                'entities': [p1, p2],
                'connected': connected,
                'hops': hops
            })
        
        return questions[:n]
    
    def generate_university_questions(self, n=400) -> List[Dict]:
        """Sinh câu hỏi về trường học"""
        questions = []
        templates_same = [
            "{p1} và {p2} có học cùng trường không?",
            "{p1} và {p2} có học cùng một trường đại học không?",
            "Cả {p1} và {p2} đều học trường nào chung không?",
            "{p1} và {p2} có trường chung không?",
            "{p1} và {p2} từng học chung trường không?",
            "Giữa {p1} và {p2} có trường học chung không?",
        ]
        
        templates_list = [
            "{person} học những trường nào?",
            "{person} đã học tại những đại học nào?",
            "Danh sách các trường đã học của {person}",
            "{person} từng học tại những trường nào?",
            "Những trường nào có {person} học?",
        ]
        
        for i in range(n):
            if random.random() < 0.6 and len(self.people) >= 2:
                # Same university question
                p1_id, p2_id = random.sample(self.people, 2)
                p1 = self.kg.node_to_title[p1_id]
                p2 = self.kg.node_to_title[p2_id]
                
                # Get universities
                unis1 = {n['id'] for n in self.kg.get_neighbors(p1_id, 'alumni_of')}
                unis2 = {n['id'] for n in self.kg.get_neighbors(p2_id, 'alumni_of')}
                common = unis1.intersection(unis2)
                
                template = random.choice(templates_same)
                question = template.format(p1=p1, p2=p2)
                
                if common:
                    uni_names = [self.kg.node_to_title[u] for u in list(common)[:3]]
                    answer = f"Có, {p1} và {p2} cùng học tại: {', '.join(uni_names)}"
                else:
                    answer = f"Không, {p1} và {p2} không học cùng trường."
                
                questions.append({
                    'id': n + i + 1,
                    'type': 'university_same',
                    'question': question,
                    'answer': answer,
                    'entities': [p1, p2],
                    'same_university': bool(common)
                })
            else:
                # List universities question
                p_id = random.choice(self.people)
                p = self.kg.node_to_title[p_id]
                
                template = random.choice(templates_list)
                question = template.format(person=p)
                
                # Get universities
                unis = [self.kg.node_to_title[n['id']] for n in self.kg.get_neighbors(p_id, 'alumni_of')]
                
                if unis:
                    answer = f"{p} đã học tại: {', '.join(unis[:5])}"
                    if len(unis) > 5:
                        answer += f" và {len(unis) - 5} trường khác"
                else:
                    answer = f"Không có thông tin về trường học của {p}"
                
                questions.append({
                    'id': n + i + 1,
                    'type': 'university_list',
                    'question': question,
                    'answer': answer,
                    'entities': [p],
                    'universities': unis
                })
        
        return questions[:n]
    
    def generate_info_questions(self, n=300) -> List[Dict]:
        """Sinh câu hỏi thông tin thuần Việt"""
        questions = []
        
        templates = [
            "Ai là {person}?",
            "{person} là ai?",
            "Hãy nói về {person}",
            "Thông tin về {person}",
            "{person} nổi tiếng vì điều gì?",
            "Bạn biết gì về {person}?",
            "{person} có liên quan gì đến công nghệ không?",
            "Tìm hiểu về {person} từ mạng alumni",
        ]
        
        for i in range(n):
            p_id = random.choice(self.people)
            p = self.kg.node_to_title[p_id]
            
            template = random.choice(templates)
            question = template.format(person=p)
            
            # Get info
            node_info = self.kg.get_node_info(p_id)
            neighbors_out = self.kg.get_neighbors(p_id)
            
            # Generate natural answer
            answer = f"{p} là một thành viên quan trọng trong mạng alumni"
            if neighbors_out:
                related = [n['title'] for n in neighbors_out[:3]]
                answer += f". Liên kết với: {', '.join(related)}"
            
            questions.append({
                'id': n + i + 1,
                'type': 'info',
                'question': question,
                'answer': answer,
                'entities': [p]
            })
        
        return questions[:n]
    
    def generate_complex_questions(self, n=200) -> List[Dict]:
        """Sinh câu hỏi phức tạp hơn"""
        questions = []
        
        templates = [
            "Tìm tất cả mọi người liên kết với {person}",
            "Những người nào có kết nối gần với {person}?",
            "{person} có mối liên kết rộng như thế nào?",
            "Ai là những người quan trọng nhất trong mạng của {person}?",
            "Từ {person}, có thể kết nối đến những ai?",
            "Mạng lưới xung quanh {person} như thế nào?",
            "Những kết nối gần nhất của {person} là gì?",
        ]
        
        for i in range(n):
            p_id = random.choice(self.people)
            p = self.kg.node_to_title[p_id]
            
            template = random.choice(templates)
            question = template.format(person=p)
            
            # Get network info
            neighbors = self.kg.get_neighbors(p_id)
            
            answer = f"{p} có kết nối với {len(neighbors)} người/tổ chức khác"
            if neighbors:
                top3 = [n['title'] for n in neighbors[:3]]
                answer += f". Những kết nối chính: {', '.join(top3)}"
            
            questions.append({
                'id': n + i + 1,
                'type': 'complex',
                'question': question,
                'answer': answer,
                'entities': [p],
                'connection_count': len(neighbors)
            })
        
        return questions[:n]
    
    def generate_full_dataset(self, output_file='eval_dataset_vietnamese_2000.json'):
        """Sinh toàn bộ dataset 2000+ câu"""
        print(f"\n{'📊 SINH BỘ DỮ LIỆU 2000+ CÂU HỎI TIẾNG VIỆT TỰ NHIÊN'.center(70, '=')}")
        
        print("   📝 Câu hỏi kết nối (connection)...", end="", flush=True)
        q_connection = self.generate_connection_questions(400)
        print(f" ✓ {len(q_connection)}")
        
        print("   📝 Câu hỏi trường học (university)...", end="", flush=True)
        q_university = self.generate_university_questions(400)
        print(f" ✓ {len(q_university)}")
        
        print("   📝 Câu hỏi thông tin (info)...", end="", flush=True)
        q_info = self.generate_info_questions(300)
        print(f" ✓ {len(q_info)}")
        
        print("   📝 Câu hỏi phức tạp (complex)...", end="", flush=True)
        q_complex = self.generate_complex_questions(200)
        print(f" ✓ {len(q_complex)}")
        
        all_questions = q_connection + q_university + q_info + q_complex
        random.shuffle(all_questions)
        
        # Renumber
        for idx, q in enumerate(all_questions, 1):
            q['id'] = idx
        
        dataset = {
            'metadata': {
                'total': len(all_questions),
                'connection': len(q_connection),
                'university': len(q_university),
                'info': len(q_info),
                'complex': len(q_complex),
                'language': 'Vietnamese',
                'description': 'Pure Vietnamese + Logic-based QA dataset'
            },
            'questions': all_questions
        }
        
        # Save
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Lưu vào {output_file}")
        print(f"   Tổng: {dataset['metadata']['total']} câu hỏi")
        print("=" * 70)
        
        return dataset


if __name__ == "__main__":
    KnowledgeGraph = import_module('1_knowledge_graph').KnowledgeGraph
    kg = KnowledgeGraph('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')
    
    gen = VietnameseQuestionGenerator(kg)
    dataset = gen.generate_full_dataset()
    
    print(f"\n✅ Sinh xong {dataset['metadata']['total']} câu hỏi!")
    print(f"   • Connection: {dataset['metadata']['connection']}")
    print(f"   • University: {dataset['metadata']['university']}")
    print(f"   • Info: {dataset['metadata']['info']}")
    print(f"   • Complex: {dataset['metadata']['complex']}")
