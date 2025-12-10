"""
Đánh Giá Chatbot Multi-hop Reasoning với Dataset 2000+ câu hỏi
"""

import json
import pandas as pd
import networkx as nx
from typing import Dict, List
import random
from tqdm import tqdm

print("="*80)
print("ĐÁNH GIÁ CHATBOT MULTI-HOP REASONING")
print("="*80)

# =============================================================================
# Load Knowledge Graph
# =============================================================================

print("\n📊 Đang load Knowledge Graph...")
nodes_df = pd.read_csv('graph_out/nodes_unified.csv')
edges_df = pd.read_csv('graph_out/edges_unified.csv')

G = nx.DiGraph()
for _, row in nodes_df.iterrows():
    G.add_node(row['id'], title=row['title'], node_type=row['type'])

for _, row in edges_df.iterrows():
    G.add_edge(row['from'], row['to'], relation=row['type'])

node_to_title = {node: data['title'] for node, data in G.nodes(data=True)}
title_to_node = {data['title']: node for node, data in G.nodes(data=True)}

print(f"✅ Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# =============================================================================
# Multi-hop Reasoner (same as in notebook)
# =============================================================================

class MultiHopReasoner:
    """Multi-hop reasoning engine"""
    
    def __init__(self, graph, node_to_title_map, title_to_node_map):
        self.G = graph
        self.node_to_title = node_to_title_map
        self.title_to_node = title_to_node_map
    
    def check_connection(self, entity1: str, entity2: str, max_hops: int = 5) -> Dict:
        """Check if two entities are connected"""
        node1 = self.title_to_node.get(entity1)
        node2 = self.title_to_node.get(entity2)
        
        if not node1 or not node2:
            return {'connected': False, 'reason': 'Entity not found'}
        
        try:
            path = nx.shortest_path(self.G, node1, node2)
            return {
                'connected': True,
                'hops': len(path) - 1,
                'path': [self.node_to_title[n] for n in path]
            }
        except nx.NetworkXNoPath:
            return {'connected': False, 'reason': 'No path found'}
    
    def check_same_university(self, person1: str, person2: str) -> Dict:
        """Check if two people attended the same university"""
        node1 = self.title_to_node.get(person1)
        node2 = self.title_to_node.get(person2)
        
        if not node1 or not node2:
            return {'answer': 'Unknown'}
        
        unis1 = set()
        for neighbor in self.G.successors(node1):
            if self.G[node1][neighbor]['relation'] == 'alumni_of':
                unis1.add(neighbor)
        
        unis2 = set()
        for neighbor in self.G.successors(node2):
            if self.G[node2][neighbor]['relation'] == 'alumni_of':
                unis2.add(neighbor)
        
        common = unis1.intersection(unis2)
        
        return {
            'answer': 'Yes' if common else 'No',
            'universities': [self.node_to_title[u] for u in common] if common else []
        }
    
    def check_same_career(self, person1: str, person2: str) -> Dict:
        """Check if two people have same career"""
        node1 = self.title_to_node.get(person1)
        node2 = self.title_to_node.get(person2)
        
        if not node1 or not node2:
            return {'answer': 'Unknown'}
        
        careers1 = set()
        for neighbor in self.G.successors(node1):
            if self.G[node1][neighbor]['relation'] == 'has_career':
                careers1.add(neighbor)
        
        careers2 = set()
        for neighbor in self.G.successors(node2):
            if self.G[node2][neighbor]['relation'] == 'has_career':
                careers2.add(neighbor)
        
        common = careers1.intersection(careers2)
        
        return {
            'answer': 'Yes' if common else 'No',
            'careers': [self.node_to_title[c] for c in common] if common else []
        }
    
    def get_university(self, person: str) -> List[str]:
        """Get universities for a person"""
        node = self.title_to_node.get(person)
        if not node:
            return []
        
        unis = []
        for neighbor in self.G.successors(node):
            if self.G[node][neighbor]['relation'] == 'alumni_of':
                unis.append(self.node_to_title[neighbor])
        
        return unis
    
    def get_career(self, person: str) -> List[str]:
        """Get careers for a person"""
        node = self.title_to_node.get(person)
        if not node:
            return []
        
        careers = []
        for neighbor in self.G.successors(node):
            if self.G[node][neighbor]['relation'] == 'has_career':
                careers.append(self.node_to_title[neighbor].replace('career_', ''))
        
        return careers
    
    def count_common_connections(self, entity1: str, entity2: str) -> int:
        """Count common connections"""
        node1 = self.title_to_node.get(entity1)
        node2 = self.title_to_node.get(entity2)
        
        if not node1 or not node2:
            return 0
        
        neighbors1 = set(self.G.successors(node1)) | set(self.G.predecessors(node1))
        neighbors2 = set(self.G.successors(node2)) | set(self.G.predecessors(node2))
        
        return len(neighbors1.intersection(neighbors2))

reasoner = MultiHopReasoner(G, node_to_title, title_to_node)
print("✅ Multi-hop Reasoner initialized")

# =============================================================================
# Load Dataset
# =============================================================================

print("\n📊 Đang load dataset...")
with open('benchmark_dataset_multihop_2000.json', 'r', encoding='utf-8') as f:
    dataset = json.load(f)

questions = dataset['questions']
print(f"✅ Loaded {len(questions)} questions")

# =============================================================================
# Evaluation Function
# =============================================================================

def evaluate_question(q: Dict, reasoner: MultiHopReasoner) -> Dict:
    """Evaluate a single question"""
    category = q['category']
    qtype = q['type']
    
    try:
        # CONNECTION questions
        if category == 'connection':
            result = reasoner.check_connection(q['entity1'], q['entity2'])
            predicted = 'Yes' if result['connected'] else 'No'
            correct = (predicted == q['answer'])
            
            return {
                'correct': correct,
                'predicted': predicted,
                'actual': q['answer'],
                'category': category
            }
        
        # SAME_UNIVERSITY questions
        elif category == 'same_university':
            result = reasoner.check_same_university(q['entity1'], q['entity2'])
            predicted = result['answer']
            correct = (predicted == q['answer'])
            
            return {
                'correct': correct,
                'predicted': predicted,
                'actual': q['answer'],
                'category': category
            }
        
        # SAME_CAREER questions
        elif category == 'same_career':
            result = reasoner.check_same_career(q['entity1'], q['entity2'])
            predicted = result['answer']
            correct = (predicted == q['answer'])
            
            return {
                'correct': correct,
                'predicted': predicted,
                'actual': q['answer'],
                'category': category
            }
        
        # UNIVERSITY MCQ
        elif category == 'university_mcq':
            unis = reasoner.get_university(q['entity'])
            
            if not unis:
                return {'correct': False, 'predicted': None, 'actual': q['answer'], 'category': category}
            
            # Check which choice matches
            for letter, choice in q['choices'].items():
                if choice in unis:
                    predicted = letter
                    break
            else:
                predicted = 'A'  # Default guess
            
            correct = (predicted == q['answer'])
            
            return {
                'correct': correct,
                'predicted': predicted,
                'actual': q['answer'],
                'category': category
            }
        
        # CAREER MCQ
        elif category == 'career_mcq':
            careers = reasoner.get_career(q['entity'])
            
            if not careers:
                return {'correct': False, 'predicted': None, 'actual': q['answer'], 'category': category}
            
            # Check which choice matches
            for letter, choice in q['choices'].items():
                if choice in careers or choice.replace(' ', '') in [c.replace(' ', '') for c in careers]:
                    predicted = letter
                    break
            else:
                predicted = 'A'
            
            correct = (predicted == q['answer'])
            
            return {
                'correct': correct,
                'predicted': predicted,
                'actual': q['answer'],
                'category': category
            }
        
        # PATH_LENGTH questions
        elif category == 'path_length':
            result = reasoner.check_connection(q['entity1'], q['entity2'])
            
            if not result['connected']:
                predicted = 'False'
            else:
                actual_hops = result['hops']
                stated_hops = q['stated_hops']
                predicted = 'True' if actual_hops == stated_hops else 'False'
            
            correct = (predicted == q['answer'])
            
            return {
                'correct': correct,
                'predicted': predicted,
                'actual': q['answer'],
                'category': category
            }
        
        # SHARED_CONNECTIONS questions
        elif category == 'shared_connections':
            count = reasoner.count_common_connections(q['entity1'], q['entity2'])
            
            # Find closest choice
            min_diff = float('inf')
            predicted = 'A'
            
            for letter, choice_str in q['choices'].items():
                choice_val = int(choice_str)
                diff = abs(choice_val - count)
                if diff < min_diff:
                    min_diff = diff
                    predicted = letter
            
            correct = (predicted == q['answer'])
            
            return {
                'correct': correct,
                'predicted': predicted,
                'actual': q['answer'],
                'category': category
            }
        
        else:
            return {'correct': False, 'predicted': None, 'actual': q['answer'], 'category': category}
    
    except Exception as e:
        return {'correct': False, 'predicted': None, 'actual': q.get('answer'), 'category': category, 'error': str(e)}

# =============================================================================
# Run Evaluation
# =============================================================================

print("\n" + "="*80)
print("BẮT ĐẦU ĐÁNH GIÁ")
print("="*80)

# Sample for faster evaluation (comment out to evaluate all)
sample_size = 500  # Change to len(questions) for full evaluation
sampled_questions = random.sample(questions, min(sample_size, len(questions)))

print(f"\n📊 Đánh giá trên {len(sampled_questions)} câu hỏi mẫu...")

results = []
for q in tqdm(sampled_questions, desc="Evaluating"):
    result = evaluate_question(q, reasoner)
    results.append(result)

# =============================================================================
# Calculate Metrics
# =============================================================================

print("\n" + "="*80)
print("KẾT QUẢ ĐÁNH GIÁ")
print("="*80)

total_correct = sum(1 for r in results if r['correct'])
total_questions = len(results)
overall_accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0

print(f"\n📊 TỔNG QUAN:")
print(f"  • Tổng số câu hỏi đánh giá: {total_questions}")
print(f"  • Trả lời đúng: {total_correct}")
print(f"  • Accuracy tổng thể: {overall_accuracy:.2f}%")

# By category
print(f"\n📌 KẾT QUẢ THEO CATEGORY:")
categories = {}
for r in results:
    cat = r['category']
    if cat not in categories:
        categories[cat] = {'correct': 0, 'total': 0}
    
    categories[cat]['total'] += 1
    if r['correct']:
        categories[cat]['correct'] += 1

for cat in sorted(categories.keys()):
    stats = categories[cat]
    acc = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"  • {cat:25s}: {stats['correct']:3d}/{stats['total']:3d} = {acc:6.2f}%")

# By hops (if available)
print(f"\n📌 KẾT QUẢ THEO SỐ BƯỚC MULTI-HOP:")

# Match results with original questions to get hops
hops_stats = {}
for i, q in enumerate(sampled_questions):
    if i < len(results):
        hops = q.get('hops', 0)
        if hops > 0:
            if hops not in hops_stats:
                hops_stats[hops] = {'correct': 0, 'total': 0}
            
            hops_stats[hops]['total'] += 1
            if results[i]['correct']:
                hops_stats[hops]['correct'] += 1

for hops in sorted(hops_stats.keys()):
    stats = hops_stats[hops]
    acc = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"  • {hops}-hop: {stats['correct']:3d}/{stats['total']:3d} = {acc:6.2f}%")

# Save results
output_file = 'evaluation_results_multihop.json'

eval_report = {
    'total_questions': total_questions,
    'correct': total_correct,
    'overall_accuracy': overall_accuracy,
    'by_category': {cat: {
        'correct': stats['correct'],
        'total': stats['total'],
        'accuracy': (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
    } for cat, stats in categories.items()},
    'by_hops': {hops: {
        'correct': stats['correct'],
        'total': stats['total'],
        'accuracy': (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
    } for hops, stats in hops_stats.items()},
    'sample_size': len(sampled_questions),
    'full_dataset_size': len(questions)
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(eval_report, f, indent=2, ensure_ascii=False)

print(f"\n✅ Đã lưu kết quả đánh giá vào: {output_file}")

print("\n" + "="*80)
print("🎉 HOÀN THÀNH ĐÁNH GIÁ!")
print("="*80)

print("\n💡 Ghi chú:")
print("  - Đánh giá trên", len(sampled_questions), "câu hỏi mẫu")
print("  - Để đánh giá toàn bộ 2000+ câu, thay sample_size = len(questions)")
print("  - Multi-hop reasoning đã được test với 1-hop đến 5-hop")
print("="*80)
