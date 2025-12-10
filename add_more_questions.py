"""
Bổ sung thêm câu hỏi Multi-hop phức tạp để đạt 2000+ câu hỏi
"""

import json
import random
import pandas as pd
import networkx as nx

print("="*80)
print("BỔ SUNG CÂU HỎI MULTI-HOP PHỨC TẠP")
print("="*80)

# Load existing dataset
with open('benchmark_dataset_multihop_2000.json', 'r', encoding='utf-8') as f:
    dataset = json.load(f)

existing_questions = dataset['questions']
print(f"\n📊 Dataset hiện tại: {len(existing_questions)} câu hỏi")

# Load graph
print("📊 Đang load Knowledge Graph...")
nodes_df = pd.read_csv('graph_out/nodes_unified.csv')
edges_df = pd.read_csv('graph_out/edges_unified.csv')

G = nx.DiGraph()
for _, row in nodes_df.iterrows():
    G.add_node(row['id'], title=row['title'], node_type=row['type'])

for _, row in edges_df.iterrows():
    G.add_edge(row['from'], row['to'], relation=row['type'], weight=row.get('weight', 1))

node_to_title = {node: data['title'] for node, data in G.nodes(data=True)}
title_to_node = {data['title']: node for node, data in G.nodes(data=True)}

person_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'person']
uni_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'university']

print(f"✅ Graph loaded")

# =============================================================================
# ADDITIONAL CATEGORY: Path Length Questions (True/False)
# =============================================================================

def generate_path_length_questions(n: int = 100) -> list:
    """
    Câu hỏi về độ dài đường đi:
    'The shortest path between X and Y is N hops' - True/False
    """
    print("\n[+] Generating Path Length Questions...")
    questions = []
    
    attempts = 0
    while len(questions) < n and attempts < n * 5:
        attempts += 1
        
        p1, p2 = random.sample(person_nodes, 2)
        title1 = node_to_title[p1]
        title2 = node_to_title[p2]
        
        try:
            path = nx.shortest_path(G, p1, p2)
            actual_hops = len(path) - 1
            
            # Random đúng/sai
            if random.random() < 0.5:
                # Câu hỏi đúng
                stated_hops = actual_hops
                answer = 'True'
                answer_vi = 'Đúng'
            else:
                # Câu hỏi sai
                stated_hops = actual_hops + random.choice([-1, 1, 2])
                if stated_hops < 1:
                    stated_hops = actual_hops + 1
                answer = 'False'
                answer_vi = 'Sai'
            
            question = {
                'id': len(existing_questions) + len(questions) + 1,
                'category': 'path_length',
                'type': 'true_false',
                'difficulty': 'hard',
                'hops': actual_hops,
                'question': f"The shortest path between {title1} and {title2} is {stated_hops} hops.",
                'question_vi': f"Đường đi ngắn nhất giữa {title1} và {title2} là {stated_hops} bước.",
                'answer': answer,
                'answer_vi': answer_vi,
                'entity1': title1,
                'entity2': title2,
                'actual_hops': actual_hops,
                'stated_hops': stated_hops,
                'explanation': f"Actual shortest path is {actual_hops} hops"
            }
            
            questions.append(question)
        except:
            continue
    
    print(f"  ✅ Generated {len(questions)} path length questions")
    return questions

# =============================================================================
# ADDITIONAL CATEGORY: Shared Connection Count (MCQ)
# =============================================================================

def generate_shared_connection_mcq(n: int = 100) -> list:
    """
    Câu hỏi trắc nghiệm: X và Y có bao nhiêu mối kết nối chung?
    """
    print("\n[+] Generating Shared Connection MCQ...")
    questions = []
    
    attempts = 0
    while len(questions) < n and attempts < n * 5:
        attempts += 1
        
        p1, p2 = random.sample(person_nodes, 2)
        title1 = node_to_title[p1]
        title2 = node_to_title[p2]
        
        # Tính số connections chung
        neighbors1 = set(G.successors(p1)) | set(G.predecessors(p1))
        neighbors2 = set(G.successors(p2)) | set(G.predecessors(p2))
        common = neighbors1.intersection(neighbors2)
        
        actual_count = len(common)
        
        if actual_count == 0:
            continue
        
        # Tạo choices
        choices_nums = [actual_count]
        
        # Add wrong choices
        for _ in range(3):
            wrong = actual_count + random.randint(-10, 10)
            if wrong < 0:
                wrong = 0
            if wrong not in choices_nums:
                choices_nums.append(wrong)
        
        if len(choices_nums) < 4:
            continue
        
        random.shuffle(choices_nums)
        correct_letter = ['A', 'B', 'C', 'D'][choices_nums.index(actual_count)]
        
        question = {
            'id': len(existing_questions) + len(questions) + 1,
            'category': 'shared_connections',
            'type': 'multiple_choice',
            'difficulty': 'hard',
            'hops': 2,
            'question': f"How many common connections do {title1} and {title2} have?",
            'question_vi': f"{title1} và {title2} có bao nhiêu mối kết nối chung?",
            'choices': {
                'A': str(choices_nums[0]),
                'B': str(choices_nums[1]),
                'C': str(choices_nums[2]),
                'D': str(choices_nums[3])
            },
            'answer': correct_letter,
            'answer_vi': correct_letter,
            'entity1': title1,
            'entity2': title2,
            'explanation': f"They have {actual_count} common connections"
        }
        
        questions.append(question)
    
    print(f"  ✅ Generated {len(questions)} shared connection questions")
    return questions

# =============================================================================
# Generate additional questions
# =============================================================================

new_questions = []
new_questions.extend(generate_path_length_questions(50))
new_questions.extend(generate_shared_connection_mcq(50))

# Combine
all_questions = existing_questions + new_questions

# Re-index
for i, q in enumerate(all_questions, 1):
    q['id'] = i

# Update statistics
print("\n" + "="*80)
print("THỐNG KÊ DATASET MỚI")
print("="*80)

print(f"\n📊 Tổng số câu hỏi: {len(all_questions)}")

# By category
categories = {}
for q in all_questions:
    cat = q['category']
    categories[cat] = categories.get(cat, 0) + 1

print("\n📌 Phân loại theo category:")
for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
    print(f"  • {cat:25s}: {count:4d} câu hỏi")

# By type
types = {}
for q in all_questions:
    qtype = q['type']
    types[qtype] = types.get(qtype, 0) + 1

print("\n📌 Phân loại theo loại câu hỏi:")
for qtype, count in sorted(types.items()):
    print(f"  • {qtype:20s}: {count:4d} câu hỏi")

# Multi-hop
hops_dist = {}
for q in all_questions:
    hops = q.get('hops', 0)
    if hops:
        hops_dist[hops] = hops_dist.get(hops, 0) + 1

print("\n📌 Phân loại theo số bước Multi-hop:")
for hops, count in sorted(hops_dist.items()):
    print(f"  • {hops}-hop: {count:4d} câu hỏi")

# Save
dataset['questions'] = all_questions
dataset['metadata']['total_questions'] = len(all_questions)
dataset['metadata']['categories'] = categories
dataset['metadata']['types'] = types
dataset['metadata']['hops_distribution'] = hops_dist

with open('benchmark_dataset_multihop_2000.json', 'w', encoding='utf-8') as f:
    json.dump(dataset, f, indent=2, ensure_ascii=False)

print("\n" + "="*80)
print("✅ ĐÃ CẬP NHẬT DATASET")
print("="*80)

if len(all_questions) >= 2000:
    print(f"\n🎉 ĐẠT MỤC TIÊU: {len(all_questions)} câu hỏi (>= 2000)")
else:
    print(f"\n⚠️  Còn thiếu: {2000 - len(all_questions)} câu hỏi")

print("="*80)
