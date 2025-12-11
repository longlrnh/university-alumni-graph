# -*- coding: utf-8 -*-
"""
3_evaluation_dataset.py
Sinh bộ dữ liệu đánh giá ≥ 2000 câu hỏi (Yes/No, True/False, Trắc nghiệm)
"""
import json
import random
from typing import List, Dict
import importlib

KnowledgeGraph = None  # Sẽ được import khi cần

class EvaluationDatasetGenerator:
    """Sinh bộ dữ liệu đánh giá Multi-hop"""
    
    def __init__(self, kg, seed: int = 42):
        self.kg = kg
        random.seed(seed)
        self.person_nodes = [n for n, d in kg.G.nodes(data=True) if d['node_type'] == 'person']
        self.uni_nodes = [n for n, d in kg.G.nodes(data=True) if d['node_type'] == 'university']
    
    def generate_yesno_questions(self, n: int = 700) -> List[Dict]:
        """Sinh câu hỏi Yes/No về kết nối"""
        questions = []
        for i in range(n):
            if len(self.person_nodes) < 2:
                break
            
            p1, p2 = random.sample(self.person_nodes, 2)
            title1 = self.kg.node_to_title[p1]
            title2 = self.kg.node_to_title[p2]
            
            # Kiểm tra kết nối
            try:
                import networkx as nx
                path = nx.shortest_path(self.kg.G, p1, p2)
                connected = True
                hops = len(path) - 1
            except:
                connected = False
                hops = 0
            
            questions.append({
                'id': i + 1,
                'type': 'yes_no',
                'category': f"{hops}_hop",
                'question': f"Có kết nối nào giữa {title1} và {title2} trong mạng alumni không?",
                'answer': 'CÓ' if connected else 'KHÔNG',
                'hops': hops
            })
        
        return questions[:n]
    
    def generate_university_questions(self, n: int = 700) -> List[Dict]:
        """Sinh câu hỏi về đại học chung"""
        questions = []
        for i in range(n):
            if len(self.person_nodes) < 2:
                break
            
            p1, p2 = random.sample(self.person_nodes, 2)
            title1 = self.kg.node_to_title[p1]
            title2 = self.kg.node_to_title[p2]
            
            # Kiểm tra trường chung
            unis1 = {n['id'] for n in self.kg.get_neighbors(p1, 'alumni_of')}
            unis2 = {n['id'] for n in self.kg.get_neighbors(p2, 'alumni_of')}
            same_uni = bool(unis1.intersection(unis2))
            
            questions.append({
                'id': i + 1 + n,
                'type': 'yes_no',
                'category': 'university',
                'question': f"{title1} và {title2} có học cùng trường đại học không?",
                'answer': 'CÓ' if same_uni else 'KHÔNG'
            })
        
        return questions[:n]
    
    def generate_mcq_questions(self, n: int = 600) -> List[Dict]:
        """Sinh câu hỏi trắc nghiệm"""
        questions = []
        for i in range(n):
            person = random.choice(self.person_nodes)
            title = self.kg.node_to_title[person]
            
            # Lấy trường học
            unis = [m['id'] for m in self.kg.get_neighbors(person, 'alumni_of')]
            
            if not unis or not self.uni_nodes:
                continue
            
            correct_uni = self.kg.node_to_title[unis[0]]
            
            # Tạo phương án sai
            other_unis = [self.kg.node_to_title[u] for u in random.sample(self.uni_nodes, min(3, len(self.uni_nodes))) if u not in unis]
            
            if len(other_unis) < 3:
                continue
            
            choices = [correct_uni] + other_unis[:3]
            random.shuffle(choices)
            
            questions.append({
                'id': i + 1 + 1400,
                'type': 'mcq',
                'category': 'university_mcq',
                'question': f"{title} đã học tại trường nào?",
                'choices': {'A': choices[0], 'B': choices[1], 'C': choices[2], 'D': choices[3]},
                'answer': ['A', 'B', 'C', 'D'][choices.index(correct_uni)]
            })
        
        return questions[:n]
    
    def generate_full_dataset(self, output_file: str = 'eval_dataset_2000.json') -> Dict:
        """Sinh toàn bộ tập dữ liệu"""
        print("\n📊 SINH BỘ DỮ LIỆU ĐÁNH GIÁ")
        print("=" * 60)
        
        print("   📝 Yes/No (kết nối)...", end="", flush=True)
        yesno = self.generate_yesno_questions(700)
        print(f" ✓ {len(yesno)}")
        
        print("   📝 Yes/No (trường học)...", end="", flush=True)
        uni = self.generate_university_questions(700)
        print(f" ✓ {len(uni)}")
        
        print("   📝 Trắc nghiệm...", end="", flush=True)
        mcq = self.generate_mcq_questions(600)
        print(f" ✓ {len(mcq)}")
        
        dataset = {
            'metadata': {
                'total': len(yesno) + len(uni) + len(mcq),
                'yesno': len(yesno),
                'mcq': len(mcq),
                'language': 'Vietnamese'
            },
            'questions': yesno + uni + mcq
        }
        
        # Lưu file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Lưu vào {output_file}")
        print(f"   Tổng: {dataset['metadata']['total']} câu hỏi")
        print("=" * 60)
        
        return dataset


if __name__ == "__main__":
    KnowledgeGraph = importlib.import_module('1_knowledge_graph').KnowledgeGraph
    kg = KnowledgeGraph('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')
    gen = EvaluationDatasetGenerator(kg)
    dataset = gen.generate_full_dataset()
