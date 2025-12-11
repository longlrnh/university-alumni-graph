import csv
import json

# Đường dẫn file
csv_path = 'graph_out/nodes_unified.csv'
json_path = 'graph_out/node_details.json'
out_path = 'graph_out/nodes_unified_with_properties.csv'

# Đọc node details
with open(json_path, 'r', encoding='utf-8') as f:
    details = json.load(f)
    details_map = {node['title']: node.get('properties', {}) for node in details}

# Đọc CSV, thêm cột properties
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

for row in rows:
    title = row['title']
    props = details_map.get(title, {})
    row['properties'] = json.dumps(props, ensure_ascii=False)

# Ghi ra file mới
with open(out_path, 'w', encoding='utf-8', newline='') as f:
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"✓ Đã thêm cột properties vào {out_path}")
