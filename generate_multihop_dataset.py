"""
Xây dựng Dataset Đánh Giá Multi-hop Reasoning
2000+ câu hỏi: Yes/No, Đúng/Sai, và Trắc nghiệm
"""

import pandas as pd
import networkx as nx
import random
import json
from typing import List, Dict, Tuple
from itertools import combinations
import numpy as np

print("="*80)
print("XÂY DỰNG TẬP DỮ LIỆU ĐÁNH GIÁ MULTI-HOP REASONING")
print("="*80)

# Load Knowledge Graph
print("\n📊 Đang load Knowledge Graph...")
nodes_df = pd.read_csv('graph_out/nodes_unified.csv')
edges_df = pd.read_csv('graph_out/edges_unified.csv')

G = nx.DiGraph()
for _, row in nodes_df.iterrows():
    G.add_node(row['id'], title=row['title'], node_type=row['type'])

for _, row in edges_df.iterrows():
    G.add_edge(row['from'], row['to'], relation=row['type'], weight=row.get('weight', 1))

print(f"✅ Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Helper functions
node_to_title = {node: data['title'] for node, data in G.nodes(data=True)}
title_to_node = {data['title']: node for node, data in G.nodes(data=True)}

person_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'person']
uni_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'university']
career_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'career']
country_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'country']

print(f"  • Persons: {len(person_nodes)}")
print(f"  • Universities: {len(uni_nodes)}")
print(f"  • Careers: {len(career_nodes)}")
print(f"  • Countries: {len(country_nodes)}")

# =============================================================================
# CATEGORY 1: YES/NO QUESTIONS - CONNECTION (1-hop, 2-hop, 3-hop)
# =============================================================================

def generate_connection_questions(n: int = 700) -> List[Dict]:
    """
    Tạo câu hỏi Yes/No về kết nối giữa 2 người
    Multi-hop: 1-hop (direct), 2-hop, 3-hop
    """
    print("\n[1/5] Generating Connection Questions (Multi-hop)...")
    questions = []
    
    # Lấy sample persons có nhiều connections
    person_degrees = [(p, G.degree(p)) for p in person_nodes]
    person_degrees.sort(key=lambda x: x[1], reverse=True)
    top_persons = [p for p, _ in person_degrees[:300]]  # Top 300 connected persons
    
    attempts = 0
    max_attempts = n * 5
    
    while len(questions) < n and attempts < max_attempts:
        attempts += 1
        
        # Random chọn 2 người
        p1, p2 = random.sample(top_persons, 2)
        title1 = node_to_title[p1]
        title2 = node_to_title[p2]
        
        # Check connection
        try:
            path = nx.shortest_path(G, p1, p2)
            connected = True
            hops = len(path) - 1
            
            # Lấy relation path
            path_relations = []
            for i in range(len(path) - 1):
                rel = G[path[i]][path[i+1]]['relation']
                path_relations.append(rel)
            
        except nx.NetworkXNoPath:
            connected = False
            hops = None
            path_relations = []
        
        # Tạo câu hỏi
        question = {
            'id': len(questions) + 1,
            'category': 'connection',
            'type': 'yes_no',
            'difficulty': 'medium' if connected and hops <= 2 else 'hard',
            'hops': hops,
            'question': f"Are {title1} and {title2} connected in the alumni network?",
            'question_vi': f"{title1} và {title2} có kết nối trong mạng lưới alumni không?",
            'answer': 'Yes' if connected else 'No',
            'answer_vi': 'Có' if connected else 'Không',
            'entity1': title1,
            'entity2': title2,
            'explanation': f"Path: {' → '.join([node_to_title[n] for n in path])}" if connected else "No path found",
            'relations': path_relations if connected else []
        }
        
        questions.append(question)
    
    print(f"  ✅ Generated {len(questions)} connection questions")
    return questions

# =============================================================================
# CATEGORY 2: YES/NO QUESTIONS - SAME UNIVERSITY (Multi-hop via alumni_of)
# =============================================================================

def generate_same_university_questions(n: int = 500) -> List[Dict]:
    """
    Tạo câu hỏi Yes/No về việc học cùng trường
    Multi-hop: Person → alumni_of → University ← alumni_of ← Person
    """
    print("\n[2/5] Generating Same University Questions (Multi-hop via alumni_of)...")
    questions = []
    
    attempts = 0
    max_attempts = n * 3
    
    while len(questions) < n and attempts < max_attempts:
        attempts += 1
        
        p1, p2 = random.sample(person_nodes, 2)
        title1 = node_to_title[p1]
        title2 = node_to_title[p2]
        
        # Get universities
        unis1 = set()
        for neighbor in G.successors(p1):
            if G[p1][neighbor]['relation'] == 'alumni_of':
                unis1.add(neighbor)
        
        unis2 = set()
        for neighbor in G.successors(p2):
            if G[p2][neighbor]['relation'] == 'alumni_of':
                unis2.add(neighbor)
        
        if not unis1 or not unis2:
            continue
        
        common_unis = unis1.intersection(unis2)
        same_uni = len(common_unis) > 0
        
        question = {
            'id': len(questions) + 1,
            'category': 'same_university',
            'type': 'yes_no',
            'difficulty': 'easy',
            'hops': 2,  # Person → University ← Person
            'question': f"Did {title1} and {title2} attend the same university?",
            'question_vi': f"{title1} và {title2} có học cùng trường không?",
            'answer': 'Yes' if same_uni else 'No',
            'answer_vi': 'Có' if same_uni else 'Không',
            'entity1': title1,
            'entity2': title2,
            'common_universities': [node_to_title[u] for u in common_unis] if same_uni else [],
            'explanation': f"Common: {', '.join([node_to_title[u] for u in common_unis])}" if same_uni else "No common university"
        }
        
        questions.append(question)
    
    print(f"  ✅ Generated {len(questions)} same university questions")
    return questions

# =============================================================================
# CATEGORY 3: YES/NO QUESTIONS - SAME CAREER (Multi-hop)
# =============================================================================

def generate_same_career_questions(n: int = 300) -> List[Dict]:
    """
    Tạo câu hỏi Yes/No về việc có cùng nghề nghiệp không
    Multi-hop: Person → has_career → Career ← has_career ← Person
    """
    print("\n[3/5] Generating Same Career Questions (Multi-hop via has_career)...")
    questions = []
    
    # Lấy persons có career
    persons_with_career = []
    for p in person_nodes:
        has_career = False
        for neighbor in G.successors(p):
            if G[p][neighbor]['relation'] == 'has_career':
                has_career = True
                break
        if has_career:
            persons_with_career.append(p)
    
    print(f"  • Found {len(persons_with_career)} persons with career info")
    
    attempts = 0
    max_attempts = n * 3
    
    while len(questions) < n and attempts < max_attempts:
        attempts += 1
        
        if len(persons_with_career) < 2:
            break
        
        p1, p2 = random.sample(persons_with_career, 2)
        title1 = node_to_title[p1]
        title2 = node_to_title[p2]
        
        # Get careers
        careers1 = set()
        for neighbor in G.successors(p1):
            if G[p1][neighbor]['relation'] == 'has_career':
                careers1.add(neighbor)
        
        careers2 = set()
        for neighbor in G.successors(p2):
            if G[p2][neighbor]['relation'] == 'has_career':
                careers2.add(neighbor)
        
        if not careers1 or not careers2:
            continue
        
        common_careers = careers1.intersection(careers2)
        same_career = len(common_careers) > 0
        
        question = {
            'id': len(questions) + 1,
            'category': 'same_career',
            'type': 'yes_no',
            'difficulty': 'medium',
            'hops': 2,  # Person → Career ← Person
            'question': f"Do {title1} and {title2} have the same career?",
            'question_vi': f"{title1} và {title2} có cùng nghề nghiệp không?",
            'answer': 'Yes' if same_career else 'No',
            'answer_vi': 'Có' if same_career else 'Không',
            'entity1': title1,
            'entity2': title2,
            'common_careers': [node_to_title[c] for c in common_careers] if same_career else [],
            'explanation': f"Common: {', '.join([node_to_title[c] for c in common_careers])}" if same_career else "Different careers"
        }
        
        questions.append(question)
    
    print(f"  ✅ Generated {len(questions)} same career questions")
    return questions

# =============================================================================
# CATEGORY 4: MULTIPLE CHOICE - WHICH UNIVERSITY (Multi-hop query)
# =============================================================================

def generate_mcq_university_questions(n: int = 400) -> List[Dict]:
    """
    Tạo câu hỏi trắc nghiệm: Người X học trường nào?
    Multi-hop: Tìm University từ Person qua edge alumni_of
    """
    print("\n[4/5] Generating Multiple Choice - University Questions...")
    questions = []
    
    attempts = 0
    max_attempts = n * 3
    
    while len(questions) < n and attempts < max_attempts:
        attempts += 1
        
        person = random.choice(person_nodes)
        title = node_to_title[person]
        
        # Get actual universities
        actual_unis = []
        for neighbor in G.successors(person):
            if G[person][neighbor]['relation'] == 'alumni_of':
                actual_unis.append(neighbor)
        
        if not actual_unis:
            continue
        
        correct_uni = random.choice(actual_unis)
        correct_title = node_to_title[correct_uni]
        
        # Generate distractors (wrong universities)
        other_unis = [u for u in uni_nodes if u not in actual_unis]
        if len(other_unis) < 3:
            continue
        
        distractors = random.sample(other_unis, 3)
        distractor_titles = [node_to_title[u] for u in distractors]
        
        # Shuffle choices
        all_choices = [correct_title] + distractor_titles
        random.shuffle(all_choices)
        
        correct_letter = ['A', 'B', 'C', 'D'][all_choices.index(correct_title)]
        
        question = {
            'id': len(questions) + 1,
            'category': 'university_mcq',
            'type': 'multiple_choice',
            'difficulty': 'easy',
            'hops': 1,  # Person → University
            'question': f"Which university did {title} attend?",
            'question_vi': f"{title} đã học trường nào?",
            'choices': {
                'A': all_choices[0],
                'B': all_choices[1],
                'C': all_choices[2],
                'D': all_choices[3]
            },
            'answer': correct_letter,
            'answer_vi': correct_letter,
            'entity': title,
            'explanation': f"{title} attended {correct_title}"
        }
        
        questions.append(question)
    
    print(f"  ✅ Generated {len(questions)} MCQ university questions")
    return questions

# =============================================================================
# CATEGORY 5: MULTIPLE CHOICE - CAREER (Multi-hop query)
# =============================================================================

def generate_mcq_career_questions(n: int = 300) -> List[Dict]:
    """
    Tạo câu hỏi trắc nghiệm: Người X có nghề nghiệp gì?
    Multi-hop: Tìm Career từ Person qua edge has_career
    """
    print("\n[5/5] Generating Multiple Choice - Career Questions...")
    questions = []
    
    # Get persons with careers
    persons_with_career = []
    for p in person_nodes:
        for neighbor in G.successors(p):
            if G[p][neighbor]['relation'] == 'has_career':
                persons_with_career.append(p)
                break
    
    if len(persons_with_career) < n:
        n = len(persons_with_career)
    
    attempts = 0
    max_attempts = n * 3
    
    while len(questions) < n and attempts < max_attempts:
        attempts += 1
        
        person = random.choice(persons_with_career)
        title = node_to_title[person]
        
        # Get actual careers
        actual_careers = []
        for neighbor in G.successors(person):
            if G[person][neighbor]['relation'] == 'has_career':
                actual_careers.append(neighbor)
        
        if not actual_careers:
            continue
        
        correct_career = random.choice(actual_careers)
        correct_title = node_to_title[correct_career].replace('career_', '')
        
        # Generate distractors
        other_careers = [c for c in career_nodes if c not in actual_careers]
        if len(other_careers) < 3:
            continue
        
        distractors = random.sample(other_careers, 3)
        distractor_titles = [node_to_title[c].replace('career_', '') for c in distractors]
        
        # Shuffle
        all_choices = [correct_title] + distractor_titles
        random.shuffle(all_choices)
        
        correct_letter = ['A', 'B', 'C', 'D'][all_choices.index(correct_title)]
        
        question = {
            'id': len(questions) + 1,
            'category': 'career_mcq',
            'type': 'multiple_choice',
            'difficulty': 'medium',
            'hops': 1,  # Person → Career
            'question': f"What is {title}'s career?",
            'question_vi': f"Nghề nghiệp của {title} là gì?",
            'choices': {
                'A': all_choices[0],
                'B': all_choices[1],
                'C': all_choices[2],
                'D': all_choices[3]
            },
            'answer': correct_letter,
            'answer_vi': correct_letter,
            'entity': title,
            'explanation': f"{title}'s career is {correct_title}"
        }
        
        questions.append(question)
    
    print(f"  ✅ Generated {len(questions)} MCQ career questions")
    return questions

# =============================================================================
# GENERATE ALL QUESTIONS
# =============================================================================

print("\n" + "="*80)
print("BẮT ĐẦU TẠO DATASET")
print("="*80)

all_questions = []

# Generate each category
all_questions.extend(generate_connection_questions(700))
all_questions.extend(generate_same_university_questions(500))
all_questions.extend(generate_same_career_questions(300))
all_questions.extend(generate_mcq_university_questions(400))
all_questions.extend(generate_mcq_career_questions(300))

# Re-index
for i, q in enumerate(all_questions, 1):
    q['id'] = i

# =============================================================================
# STATISTICS
# =============================================================================

print("\n" + "="*80)
print("THỐNG KÊ DATASET")
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

# By difficulty
difficulties = {}
for q in all_questions:
    diff = q.get('difficulty', 'unknown')
    difficulties[diff] = difficulties.get(diff, 0) + 1

print("\n📌 Phân loại theo độ khó:")
for diff, count in sorted(difficulties.items()):
    print(f"  • {diff:20s}: {count:4d} câu hỏi")

# Multi-hop statistics
hops_dist = {}
for q in all_questions:
    hops = q.get('hops', 0)
    if hops:
        hops_dist[hops] = hops_dist.get(hops, 0) + 1

print("\n📌 Phân loại theo số bước Multi-hop:")
for hops, count in sorted(hops_dist.items()):
    print(f"  • {hops}-hop: {count:4d} câu hỏi")

# =============================================================================
# SAVE DATASET
# =============================================================================

output_file = 'benchmark_dataset_multihop_2000.json'

dataset = {
    'metadata': {
        'total_questions': len(all_questions),
        'categories': categories,
        'types': types,
        'difficulties': difficulties,
        'hops_distribution': hops_dist,
        'created_date': '2025-12-10',
        'description': 'Multi-hop reasoning evaluation dataset for Alumni Knowledge Graph'
    },
    'questions': all_questions
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(dataset, f, indent=2, ensure_ascii=False)

print("\n" + "="*80)
print(f"✅ ĐÃ LƯU DATASET VÀO: {output_file}")
print("="*80)

# Sample questions
print("\n📝 MỘT SỐ CÂU HỎI MẪU:\n")

for i, q in enumerate(random.sample(all_questions, 5), 1):
    print(f"{i}. [{q['category']}] {q['question_vi']}")
    print(f"   Answer: {q['answer_vi']}")
    if q['type'] == 'multiple_choice':
        print(f"   Choices: {q['choices']}")
    print(f"   Hops: {q.get('hops', 'N/A')}, Difficulty: {q.get('difficulty', 'N/A')}")
    print()

print("="*80)
print("🎉 HOÀN THÀNH TẠO DATASET ĐÁNH GIÁ MULTI-HOP REASONING!")
print("="*80)
