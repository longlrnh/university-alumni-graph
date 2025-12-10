import pandas as pd
import json

# Đọc dữ liệu
nodes = pd.read_csv('graph_out/nodes_unified.csv')
edges = pd.read_csv('graph_out/edges_unified.csv')

# Lấy danh sách person
persons = nodes[nodes['type'] == 'person']['id'].tolist()

# Lấy danh sách person có alumni_of
alumni_edges = edges[edges['type'] == 'alumni_of']
persons_with_alumni = set(alumni_edges['from'].unique())

# Tìm person thiếu alumni_of
persons_without = set(persons) - persons_with_alumni

print(f'Tổng số person: {len(persons)}')
print(f'Person có alumni_of: {len(persons_with_alumni)}')
print(f'Person THIẾU alumni_of: {len(persons_without)}')

if len(persons_without) > 0:
    print(f'\nDanh sách person thiếu alumni_of (top 20):')
    for i, p in enumerate(list(persons_without)[:20], 1):
        print(f'  {i}. {p}')
    
    # Lưu danh sách đầy đủ
    with open('persons_missing_alumni.json', 'w', encoding='utf-8') as f:
        json.dump(list(persons_without), f, indent=2, ensure_ascii=False)
    print(f'\n✓ Đã lưu danh sách đầy đủ vào: persons_missing_alumni.json')
