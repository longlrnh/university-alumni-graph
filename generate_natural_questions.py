"""
Tái sinh Dataset với Câu Hỏi Tự Nhiên
Không gọi trực tiếp edge - câu hỏi giống như con người hỏi
"""

import json
import pandas as pd
import networkx as nx
import random
from typing import List, Dict

print("="*80)
print("TÁI SINH DATASET VỚI CÂU HỎI TỰ NHIÊN (NATURAL QUESTIONS)")
print("="*80)

# Load graph
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

person_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'person']
uni_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'university']
career_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'career']

print(f"✅ Graph loaded: {G.number_of_nodes()} nodes")

# =============================================================================
# CATEGORY 1: CONNECTION QUESTIONS - TỰ NHIÊN (Câu hỏi con người hỏi)
# =============================================================================

def generate_natural_connection_questions(n: int = 700) -> List[Dict]:
    """
    Tạo câu hỏi về kết nối - dạng TỰ NHIÊN
    Không nhắc đến "alumni_of", "same_uni" - hỏi theo kiểu con người
    """
    print("\n[1/7] Generating Natural Connection Questions...")
    
    connection_templates = [
        "Có liên quan gì giữa {entity1} và {entity2}?",
        "{entity1} và {entity2} có quan hệ như thế nào?",
        "Bạn có biết {entity1} và {entity2} có kết nối nào không?",
        "Tìm mối liên kết giữa {entity1} và {entity2}.",
        "{entity1} có thể kết nối đến {entity2} qua ai?",
        "Giữa {entity1} và {entity2}, có đường nào không?",
        "Làm sao để liên kết {entity1} với {entity2}?",
        "{entity1} và {entity2} có mối quan hệ gì trong mạng lưới này?",
        "Tìm hiểu xem {entity1} và {entity2} có kết nối không?",
        "{entity1} liên quan đến {entity2} như thế nào?"
    ]
    
    questions = []
    person_degrees = [(p, G.degree(p)) for p in person_nodes]
    person_degrees.sort(key=lambda x: x[1], reverse=True)
    top_persons = [p for p, _ in person_degrees[:300]]
    
    for _ in range(n):
        try:
            p1, p2 = random.sample(top_persons, 2)
            title1 = node_to_title[p1]
            title2 = node_to_title[p2]
            
            try:
                path = nx.shortest_path(G, p1, p2)
                connected = True
                hops = len(path) - 1
                path_titles = [node_to_title[n] for n in path]
            except:
                connected = False
                hops = None
                path_titles = []
            
            # Sử dụng template tự nhiên
            template = random.choice(connection_templates)
            question = template.format(entity1=title1, entity2=title2)
            
            answer = 'Có' if connected else 'Không'
            
            q_obj = {
                'id': len(questions) + 1,
                'category': 'connection',
                'type': 'yes_no',
                'difficulty': 'medium' if connected and hops <= 2 else 'hard',
                'hops': hops,
                'question': question,
                'answer': answer,
                'entity1': title1,
                'entity2': title2,
                'internal_path': path_titles if connected else [],
            }
            questions.append(q_obj)
        except:
            continue
    
    print(f"  ✅ Generated {len(questions)} natural connection questions")
    return questions

# =============================================================================
# CATEGORY 2: EDUCATION BACKGROUND - TỰ NHIÊN
# =============================================================================

def generate_natural_education_questions(n: int = 350) -> List[Dict]:
    """
    Câu hỏi về nền tảng giáo dục - dạng TỰ NHIÊN
    Không nhắc "alumni_of" - hỏi kiểu "Người này học ở đâu?"
    """
    print("\n[2/7] Generating Natural Education Questions...")
    
    education_templates = [
        "Bạn có biết {person} đã học ở đâu không?",
        "{person} có trình độ học vấn từ trường nào?",
        "Nơi học của {person} là ở đâu?",
        "Giáo dục của {person} từ các trường nào?",
        "{person} từng học tại những trường nào?",
        "{person} và {person2} có học cùng trường không?",
        "Cả {person} và {person2} đều từ trường {university} phải không?",
        "{person} học tại {university}, đúng hay sai?",
    ]
    
    questions = []
    
    attempts = 0
    while len(questions) < n and attempts < n * 3:
        attempts += 1
        
        try:
            # Type 1: Single person - university
            if random.random() < 0.6 and len(questions) < n * 0.6:
                person = random.choice(person_nodes)
                person_title = node_to_title[person]
                
                unis = []
                for neighbor in G.successors(person):
                    if G[person][neighbor]['relation'] == 'alumni_of':
                        unis.append(node_to_title[neighbor])
                
                if unis:
                    template = random.choice([
                        "Bạn có biết {person} đã học ở đâu không?",
                        "{person} có trình độ học vấn từ trường nào?",
                        "Nơi học của {person} là ở đâu?",
                    ])
                    question = template.format(person=person_title)
                    
                    # Answer format: list of universities
                    q_obj = {
                        'id': len(questions) + 1,
                        'category': 'education_lookup',
                        'type': 'open_ended',
                        'difficulty': 'easy',
                        'hops': 1,
                        'question': question,
                        'entity': person_title,
                        'correct_answers': unis,
                        'internal_info': 'person → alumni_of → universities'
                    }
                    questions.append(q_obj)
            
            # Type 2: Two persons - same university
            else:
                p1, p2 = random.sample(person_nodes, 2)
                title1 = node_to_title[p1]
                title2 = node_to_title[p2]
                
                unis1 = set()
                for neighbor in G.successors(p1):
                    if G[p1][neighbor]['relation'] == 'alumni_of':
                        unis1.add(neighbor)
                
                unis2 = set()
                for neighbor in G.successors(p2):
                    if G[p2][neighbor]['relation'] == 'alumni_of':
                        unis2.add(neighbor)
                
                if unis1 and unis2:
                    common = unis1.intersection(unis2)
                    
                    template = random.choice([
                        "{person1} và {person2} có học cùng trường không?",
                        "Cả {person1} và {person2} đều học từ trường {university} phải không?",
                    ])
                    
                    if common and "trường" in template:
                        uni_name = node_to_title[list(common)[0]]
                        question = template.format(
                            person1=title1,
                            person2=title2,
                            university=uni_name
                        )
                        answer = 'Đúng'
                    else:
                        question = template.format(person1=title1, person2=title2)
                        answer = 'Có' if common else 'Không'
                    
                    q_obj = {
                        'id': len(questions) + 1,
                        'category': 'education_comparison',
                        'type': 'yes_no',
                        'difficulty': 'easy',
                        'hops': 2,
                        'question': question,
                        'answer': answer,
                        'entity1': title1,
                        'entity2': title2,
                        'common_universities': [node_to_title[u] for u in common] if common else [],
                    }
                    questions.append(q_obj)
        except:
            continue
    
    print(f"  ✅ Generated {len(questions)} natural education questions")
    return questions

# =============================================================================
# CATEGORY 3: CAREER & PROFESSION - TỰ NHIÊN
# =============================================================================

def generate_natural_career_questions(n: int = 350) -> List[Dict]:
    """
    Câu hỏi về sự nghiệp - dạng TỰ NHIÊN
    Hỏi kiểu "Người này làm gì?", không nhắc đến "has_career"
    """
    print("\n[3/7] Generating Natural Career Questions...")
    
    career_templates = [
        "Bạn biết {person} làm nghề gì không?",
        "Sự nghiệp của {person} là gì?",
        "{person} hiện tại có chức vụ/nghề nào?",
        "{person} và {person2} có cùng nghề không?",
        "Cả {person} và {person2} đều làm {career} phải không?",
        "{person} có phải là {career} không?",
    ]
    
    questions = []
    persons_with_career = [p for p in person_nodes if any(
        G[p][n]['relation'] == 'has_career' for n in G.successors(p)
    )]
    
    attempts = 0
    while len(questions) < n and attempts < n * 3:
        attempts += 1
        
        try:
            if random.random() < 0.6 and len(persons_with_career) > 0:
                # Single person career
                person = random.choice(persons_with_career)
                person_title = node_to_title[person]
                
                careers = []
                for neighbor in G.successors(person):
                    if G[person][neighbor]['relation'] == 'has_career':
                        careers.append(node_to_title[neighbor].replace('career_', ''))
                
                if careers:
                    template = random.choice([
                        "Bạn biết {person} làm nghề gì không?",
                        "Sự nghiệp của {person} là gì?",
                    ])
                    question = template.format(person=person_title)
                    
                    q_obj = {
                        'id': len(questions) + 1,
                        'category': 'career_lookup',
                        'type': 'open_ended',
                        'difficulty': 'easy',
                        'hops': 1,
                        'question': question,
                        'entity': person_title,
                        'correct_answers': careers,
                    }
                    questions.append(q_obj)
            
            else:
                # Two persons career comparison
                p1, p2 = random.sample(persons_with_career, 2)
                title1 = node_to_title[p1]
                title2 = node_to_title[p2]
                
                careers1 = []
                for neighbor in G.successors(p1):
                    if G[p1][neighbor]['relation'] == 'has_career':
                        careers1.append(node_to_title[neighbor].replace('career_', ''))
                
                careers2 = []
                for neighbor in G.successors(p2):
                    if G[p2][neighbor]['relation'] == 'has_career':
                        careers2.append(node_to_title[neighbor].replace('career_', ''))
                
                if careers1 and careers2:
                    common = set(careers1) & set(careers2)
                    
                    if common:
                        career = list(common)[0]
                        template = random.choice([
                            "{person1} và {person2} có cùng nghề không?",
                            "Cả {person1} và {person2} đều là {career} phải không?",
                        ])
                        if "{career}" in template:
                            question = template.format(person1=title1, person2=title2, career=career)
                            answer = 'Đúng'
                        else:
                            question = template.format(person1=title1, person2=title2)
                            answer = 'Có'
                    else:
                        question = f"{title1} và {title2} có cùng nghề không?"
                        answer = 'Không'
                    
                    q_obj = {
                        'id': len(questions) + 1,
                        'category': 'career_comparison',
                        'type': 'yes_no',
                        'difficulty': 'medium',
                        'hops': 2,
                        'question': question,
                        'answer': answer,
                        'entity1': title1,
                        'entity2': title2,
                    }
                    questions.append(q_obj)
        except:
            continue
    
    print(f"  ✅ Generated {len(questions)} natural career questions")
    return questions

# =============================================================================
# CATEGORY 4: PROFILE & BACKGROUND - TỰ NHIÊN
# =============================================================================

def generate_natural_profile_questions(n: int = 300) -> List[Dict]:
    """
    Câu hỏi tổng quát về hồ sơ - dạng TỰ NHIÊN
    """
    print("\n[4/7] Generating Natural Profile Questions...")
    
    profile_templates = [
        "Bạn có thông tin gì về {person}?",
        "Giới thiệu một chút về {person}.",
        "Ai là {person}? Hãy cho biết thêm thông tin.",
        "{person} nổi tiếng vì điều gì?",
        "Bạn biết gì về {person}?",
    ]
    
    questions = []
    sample_persons = random.sample(person_nodes, min(n, len(person_nodes)))
    
    for person in sample_persons:
        person_title = node_to_title[person]
        
        # Gather info
        info = {
            'universities': [],
            'careers': [],
            'connections': 0
        }
        
        for neighbor in G.successors(person):
            rel = G[person][neighbor]['relation']
            if rel == 'alumni_of':
                info['universities'].append(node_to_title[neighbor])
            elif rel == 'has_career':
                info['careers'].append(node_to_title[neighbor].replace('career_', ''))
        
        info['connections'] = G.degree(person)
        
        template = random.choice(profile_templates)
        question = template.format(person=person_title)
        
        q_obj = {
            'id': len(questions) + 1,
            'category': 'profile_info',
            'type': 'open_ended',
            'difficulty': 'medium',
            'hops': 1,
            'question': question,
            'entity': person_title,
            'profile_info': info,
        }
        questions.append(q_obj)
    
    print(f"  ✅ Generated {len(questions)} natural profile questions")
    return questions

# =============================================================================
# CATEGORY 5: INFERENCE QUESTIONS - CẦN LLM REASONING
# =============================================================================

def generate_natural_inference_questions(n: int = 200) -> List[Dict]:
    """
    Câu hỏi yêu cầu LLM suy luận - không chỉ truy cập graph
    """
    print("\n[5/7] Generating Natural Inference Questions...")
    
    inference_templates = [
        "Theo bạn, {person1} và {person2} có thể có những điểm chung nào?",
        "Tại sao {person} lại nổi tiếng? Hãy phân tích.",
        "Nếu {person1} gặp {person2}, họ có thể bàn luận về cái gì?",
        "So sánh nền tảng giáo dục của {person1} và {person2}.",
        "Bạn nghĩ {person} sẽ phù hợp làm gì?",
        "Những thứ {person1} và {person2} có thể học hỏi từ nhau là gì?",
    ]
    
    questions = []
    sample_persons = random.sample(person_nodes, min(n * 2, len(person_nodes)))
    
    for i in range(0, min(n, len(sample_persons) - 1), 2):
        p1, p2 = sample_persons[i], sample_persons[i + 1]
        title1 = node_to_title[p1]
        title2 = node_to_title[p2]
        
        template = random.choice(inference_templates)
        if "{person1}" in template and "{person2}" in template:
            question = template.format(person1=title1, person2=title2)
        elif "{person}" in template:
            question = template.format(person=title1)
        else:
            continue
        
        q_obj = {
            'id': len(questions) + 1,
            'category': 'inference',
            'type': 'open_ended',
            'difficulty': 'hard',
            'question': question,
            'requires_llm_reasoning': True,
            'note': 'LLM cần suy luận, không chỉ tra cứu graph'
        }
        questions.append(q_obj)
    
    print(f"  ✅ Generated {len(questions)} natural inference questions")
    return questions

# =============================================================================
# CATEGORY 6: COMPARISON & ANALYSIS - CẦN LLM
# =============================================================================

def generate_natural_comparison_questions(n: int = 200) -> List[Dict]:
    """
    Câu hỏi so sánh & phân tích - LLM sử dụng graph context
    """
    print("\n[6/7] Generating Natural Comparison Questions...")
    
    comparison_templates = [
        "Ai là người có ảnh hưởng lớn hơn: {person1} hay {person2}?",
        "{person1} và {person2}, ai có nền tảng giáo dục tốt hơn?",
        "Tìm điểm khác biệt giữa {person1} và {person2}.",
        "Ai là người có nhiều mối liên kết hơn: {person1} hay {person2}?",
        "So sánh thành tích của {person1} và {person2}.",
    ]
    
    questions = []
    sample_pairs = []
    for _ in range(n):
        p1, p2 = random.sample(person_nodes, 2)
        sample_pairs.append((p1, p2))
    
    for p1, p2 in sample_pairs[:n]:
        title1 = node_to_title[p1]
        title2 = node_to_title[p2]
        
        template = random.choice(comparison_templates)
        question = template.format(person1=title1, person2=title2)
        
        q_obj = {
            'id': len(questions) + 1,
            'category': 'comparison',
            'type': 'open_ended',
            'difficulty': 'hard',
            'question': question,
            'requires_llm_reasoning': True,
            'context_sources': [title1, title2],
        }
        questions.append(q_obj)
    
    print(f"  ✅ Generated {len(questions)} natural comparison questions")
    return questions

# =============================================================================
# CATEGORY 7: REASONING PATH - GRAPH + LLM
# =============================================================================

def generate_natural_reasoning_path_questions(n: int = 100) -> List[Dict]:
    """
    Câu hỏi yêu cầu tìm path và LLM giải thích
    """
    print("\n[7/7] Generating Natural Reasoning Path Questions...")
    
    reasoning_templates = [
        "Làm sao bạn có thể kết nối {person1} với {person2}? Hãy giải thích.",
        "Tìm mối liên kết giữa {person1} và {person2} và hãy phân tích.",
        "Đường đi từ {person1} đến {person2} qua những ai?",
        "Liệu có cách nào để liên kết {person1} và {person2}?",
    ]
    
    questions = []
    top_persons = [p for p, _ in sorted(
        [(p, G.degree(p)) for p in person_nodes],
        key=lambda x: x[1],
        reverse=True
    )[:200]]
    
    for _ in range(n):
        try:
            p1, p2 = random.sample(top_persons, 2)
            title1 = node_to_title[p1]
            title2 = node_to_title[p2]
            
            try:
                path = nx.shortest_path(G, p1, p2)
                hops = len(path) - 1
                
                template = random.choice(reasoning_templates)
                question = template.format(person1=title1, person2=title2)
                
                q_obj = {
                    'id': len(questions) + 1,
                    'category': 'reasoning_path',
                    'type': 'open_ended',
                    'difficulty': 'hard',
                    'hops': hops,
                    'question': question,
                    'requires_graph_search': True,
                    'requires_llm_explanation': True,
                    'entity1': title1,
                    'entity2': title2,
                }
                questions.append(q_obj)
            except:
                continue
        except:
            continue
    
    print(f"  ✅ Generated {len(questions)} natural reasoning path questions")
    return questions

# =============================================================================
# Generate All Questions
# =============================================================================

print("\n" + "="*80)
print("BẮT ĐẦU TẠO DATASET VỚI CÂU HỎI TỰ NHIÊN")
print("="*80)

all_questions = []
all_questions.extend(generate_natural_connection_questions(700))
all_questions.extend(generate_natural_education_questions(350))
all_questions.extend(generate_natural_career_questions(350))
all_questions.extend(generate_natural_profile_questions(200))
all_questions.extend(generate_natural_inference_questions(200))
all_questions.extend(generate_natural_comparison_questions(200))
all_questions.extend(generate_natural_reasoning_path_questions(100))

# Re-index
for i, q in enumerate(all_questions, 1):
    q['id'] = i

# =============================================================================
# Statistics
# =============================================================================

print("\n" + "="*80)
print("THỐNG KÊ DATASET MỚI - CÂU HỎI TỰ NHIÊN")
print("="*80)

print(f"\n📊 Tổng số câu hỏi: {len(all_questions)}")

categories = {}
for q in all_questions:
    cat = q['category']
    categories[cat] = categories.get(cat, 0) + 1

print("\n📌 Phân loại theo category:")
for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
    print(f"  • {cat:30s}: {count:4d} câu")

types_count = {}
for q in all_questions:
    qtype = q.get('type', 'unknown')
    types_count[qtype] = types_count.get(qtype, 0) + 1

print("\n📌 Phân loại theo loại câu hỏi:")
for qtype, count in sorted(types_count.items()):
    print(f"  • {qtype:20s}: {count:4d} câu")

llm_dependent = sum(1 for q in all_questions if q.get('requires_llm_reasoning', False))
print(f"\n📌 Câu hỏi cần LLM suy luận: {llm_dependent}")
print(f"   (Cộng với GraphRAG context retrieval)")

# =============================================================================
# Save
# =============================================================================

output_file = 'benchmark_dataset_natural_questions.json'

dataset = {
    'metadata': {
        'total_questions': len(all_questions),
        'categories': categories,
        'types': types_count,
        'llm_dependent_questions': llm_dependent,
        'created_date': '2025-12-10',
        'description': 'Natural language questions for Alumni Knowledge Graph - combines GraphRAG retrieval with LLM reasoning',
        'note': 'Questions are written naturally (not calling graph edges directly) to simulate real user queries'
    },
    'questions': all_questions
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(dataset, f, indent=2, ensure_ascii=False)

print("\n" + "="*80)
print(f"✅ ĐÃ LƯU DATASET VÀO: {output_file}")
print("="*80)

# Sample
print("\n📝 MỘT SỐ CÂU HỎI MẪU:\n")
for q in random.sample(all_questions, min(5, len(all_questions))):
    print(f"[{q['category']}] {q['question']}")
    if 'answer' in q:
        print(f"  → Answer: {q['answer']}")
    print()

print("="*80)
print("🎉 HOÀN THÀNH TẠO DATASET VỚI CÂU HỎI TỰ NHIÊN!")
print("="*80)
