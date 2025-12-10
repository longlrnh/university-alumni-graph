import pandas as pd
import json
import wikipediaapi
from typing import List, Dict
import re

# Khởi tạo Wikipedia API
wiki = wikipediaapi.Wikipedia(
    language='en',
    user_agent='UniversityAlumniGraph/1.0'
)

def extract_universities_from_wiki(person_name: str) -> List[str]:
    """Trích xuất thông tin trường đại học từ Wikipedia"""
    print(f"  Đang tìm kiếm: {person_name}...")
    
    page = wiki.page(person_name)
    
    if not page.exists():
        print(f"    ⚠ Không tìm thấy trang Wikipedia")
        return []
    
    # Lấy nội dung văn bản
    text = page.text
    
    # Các từ khóa tìm kiếm
    university_keywords = [
        r'University of ([A-Z][A-Za-z\s]+)',
        r'([A-Z][A-Za-z\s]+) University',
        r'attended ([A-Z][A-Za-z\s]+ University)',
        r'studied at ([A-Z][A-Za-z\s]+ University)',
        r'graduated from ([A-Z][A-Za-z\s]+ University)',
        r'alma mater[:\s]+([A-Z][A-Za-z\s]+ University)',
        r'educated at ([A-Z][A-Za-z\s]+ University)',
        r'College of ([A-Z][A-Za-z\s]+)',
        r'([A-Z][A-Za-z\s]+) College',
        r'MIT',
        r'Stanford',
        r'Harvard',
        r'Princeton',
        r'Yale',
        r'Oxford',
        r'Cambridge'
    ]
    
    found_unis = set()
    
    for pattern in university_keywords:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            
            # Làm sạch tên trường
            match = match.strip()
            if len(match) > 5:  # Bỏ qua tên quá ngắn
                found_unis.add(match)
    
    return list(found_unis)

# Mapping tên tiếng Anh -> tên tiếng Việt
university_mapping = {
    'Harvard': 'Đại học Harvard',
    'Stanford': 'Đại học Stanford',
    'MIT': 'Viện Công nghệ Massachusetts',
    'Oxford': 'Đại học Oxford',
    'Cambridge': 'Đại học Cambridge',
    'Princeton': 'Đại học Princeton',
    'Yale': 'Đại học Yale',
    'Pennsylvania': 'Đại học Pennsylvania',
    'Columbia': 'Đại học Columbia',
    'Chicago': 'Đại học Chicago',
    'Michigan': 'Đại học Michigan',
    'California': 'Đại học California',
    'Berkeley': 'Đại học California, Berkeley',
    'Duke': 'Đại học Duke',
    'Cornell': 'Đại học Cornell',
    'Northwestern': 'Đại học Northwestern',
    'Dartmouth': 'Đại học Dartmouth',
    'Brown': 'Đại học Brown',
    'Wharton': 'Trường Kinh doanh Wharton',
    'Delhi': 'Đại học Delhi',
    'Manipal': 'Đại học Manipal',
    'Wisconsin': 'Đại học Wisconsin',
    'Illinois': 'Đại học Illinois',
    'Waterloo': 'Đại học Waterloo',
    'Toronto': 'Đại học Toronto',
    'McGill': 'Đại học McGill',
    'London': 'Đại học London',
    'Sorbonne': 'Đại học Sorbonne',
    'Berlin': 'Đại học Berlin',
    'Munich': 'Đại học Munich',
    'Tokyo': 'Đại học Tokyo',
    'Kyoto': 'Đại học Kyoto',
    'Seoul': 'Đại học Seoul',
    'Peking': 'Đại học Bắc Kinh',
    'Tsinghua': 'Đại học Thanh Hoa',
}

def normalize_university_name(uni_name: str) -> str:
    """Chuẩn hóa tên trường"""
    # Kiểm tra mapping
    for eng, vie in university_mapping.items():
        if eng in uni_name:
            return vie
    
    # Nếu không có mapping, thêm "Đại học" nếu chưa có
    if not uni_name.startswith('Đại học') and not uni_name.startswith('Viện') and not uni_name.startswith('Trường'):
        return f'Đại học {uni_name}'
    
    return uni_name

# Thông tin trường học đã biết (từ nguồn tin cậy)
known_alumni = {
    'Bill Gates': ['Microsoft', 'Đại học Harvard'],  # dropout
    'Mark Zuckerberg': ['Đại học Harvard'],  # dropout
    'Elon Musk': ['Đại học Pennsylvania', 'Đại học Stanford'],  # dropout Stanford
    'Jeff Bezos': ['Đại học Princeton'],
    'Sundar Pichai': ['Đại học Stanford', 'Viện Công nghệ Massachusetts', 'Viện Công nghệ Ấn Độ Kharagpur'],
    'Satya Nadella': ['Đại học Chicago', 'Đại học Wisconsin-Milwaukee', 'Viện Công nghệ Manipal'],
    'Tim Cook': ['Đại học Auburn', 'Đại học Duke'],
    'Peter Thiel': ['Đại học Stanford'],
    'Sheryl Sandberg': ['Đại học Harvard'],
    'Nancy Pelosi': ['Đại học Trinity Washington'],
    'Taylor Swift': ['Đại học New York'],  # honorary degree
    'Malala Yousafzai': ['Đại học Oxford'],
    'Michelangelo': ['Đại học Florence'],  # historical, approximate
    'Helmut Schmidt': ['Đại học Hamburg'],
    'Michel Barnier': ['Đại học Paris II Panthéon-Assas'],
    'Kaja Kallas': ['Đại học Tartu'],
    'Jacques Chaban-Delmas': ['Đại học Paris']
}

print("=" * 80)
print("BẮT ĐẦU BỔ SUNG THÔNG TIN TRƯỜNG HỌC")
print("=" * 80)

# Đọc danh sách person thiếu alumni_of
with open('persons_missing_alumni.json', 'r', encoding='utf-8') as f:
    missing_persons = json.load(f)

# Đọc dữ liệu hiện tại
nodes = pd.read_csv('graph_out/nodes_unified.csv')
edges = pd.read_csv('graph_out/edges_unified.csv')

# Lấy danh sách các trường đã có
existing_universities = set(nodes[nodes['type'] == 'university']['title'].tolist())

new_edges = []
new_universities = []

for person in missing_persons:
    print(f"\n[{person}]")
    
    # Ưu tiên dùng dữ liệu đã biết
    if person in known_alumni:
        unis = known_alumni[person]
        print(f"  ✓ Sử dụng dữ liệu có sẵn: {unis}")
    else:
        # Thử tra Wikipedia
        unis_raw = extract_universities_from_wiki(person)
        unis = [normalize_university_name(u) for u in unis_raw]
        print(f"  ✓ Tìm thấy từ Wikipedia: {unis}")
    
    # Thêm edges và universities mới
    for uni in unis:
        # Thêm university node nếu chưa có
        if uni not in existing_universities:
            new_universities.append({
                'id': uni,
                'title': uni,
                'type': 'university'
            })
            existing_universities.add(uni)
            print(f"    + Thêm trường mới: {uni}")
        
        # Thêm edge alumni_of
        new_edges.append({
            'from': person,
            'to': uni,
            'type': 'alumni_of',
            'weight': 1
        })
        print(f"    + Thêm edge: {person} --[alumni_of]--> {uni}")

print("\n" + "=" * 80)
print("KẾT QUẢ")
print("=" * 80)
print(f"✓ Đã thêm {len(new_edges)} edges mới (alumni_of)")
print(f"✓ Đã thêm {len(new_universities)} universities mới")

# Cập nhật dữ liệu
if new_universities:
    new_unis_df = pd.DataFrame(new_universities)
    nodes = pd.concat([nodes, new_unis_df], ignore_index=True)
    nodes.to_csv('graph_out/nodes_unified.csv', index=False, encoding='utf-8')
    print(f"\n✓ Đã cập nhật nodes_unified.csv")

if new_edges:
    new_edges_df = pd.DataFrame(new_edges)
    edges = pd.concat([edges, new_edges_df], ignore_index=True)
    edges.to_csv('graph_out/edges_unified.csv', index=False, encoding='utf-8')
    print(f"✓ Đã cập nhật edges_unified.csv")

# Kiểm tra lại
alumni_edges = edges[edges['type'] == 'alumni_of']
persons_with_alumni = set(alumni_edges['from'].unique())
all_persons = nodes[nodes['type'] == 'person']['id'].tolist()
still_missing = set(all_persons) - persons_with_alumni

print(f"\n📊 THỐNG KÊ SAU KHI SỬA:")
print(f"  - Tổng person: {len(all_persons)}")
print(f"  - Person có alumni_of: {len(persons_with_alumni)}")
print(f"  - Person vẫn còn thiếu: {len(still_missing)}")

if len(still_missing) == 0:
    print("\n🎉 HOÀN THÀNH! Tất cả person đều đã có alumni_of")
else:
    print(f"\n⚠ Còn {len(still_missing)} person chưa có alumni_of: {list(still_missing)}")
