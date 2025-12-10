# Enrichment v3 - Improved Extraction

## Overview

**Data Enrichment Pipeline v3** - Xử lý kỹ lưỡng hơn với:
- ✅ Multiple data sources (Sinh, Mat, Quốc tịch, Vị trí, etc.)
- ✅ Province-aware country extraction (China, Vietnam, India)
- ✅ Historical country names (British India, Dutch East Indies)
- ✅ Career extraction từ 15+ position fields
- ✅ Diacritics normalization (Vietnamese characters)
- ✅ Overlapping match detection (avoid extracting "Tuong" từ "Pho Thu tuong")

## Issues Fixed

### 1. Multiple Birth Country Sources
**Before**: Chỉ lấy từ "Sinh" field
**Now**: Lấy từ "Sinh", "Mất", "Quốc tịch", "Vị trí", "Cư trú", etc.

### 2. Career Extraction - Wrong Field Names
**Before**: Tìm "Chuc vu" (romanized)
**Now**: Tìm "Chức vụ" (with Vietnamese diacritics)
- Thêm 15+ position fields: Thủ tướng, Tổng thống, Bộ trưởng, Bí thư, etc.

### 3. Country Extraction - Multiple Strategies  
**Before**: Simple string matching → false positives (Y=England, Anh=England)
**Now**: Hierarchical extraction:
1. Chinese provinces FIRST (Tu Xuyen → Trung Quoc)
2. Vietnamese provinces
3. Indian states (Tamil Nadu → An Do)
4. Historical names (Ấn Độ thuộc Anh → An Do, không Anh)
5. Country names

### 4. Career Overlapping Matches
**Before**: Extracting both "Pho Thu tuong" AND "Tuong" separately
**Now**: Track matched ranges, skip overlapping matches

### 5. Diacritics Normalization
**Before**: Incomplete (missing uppercase Ấ)
**Now**: Complete mapping for all Vietnamese diacritics

## Data Extraction Examples

### ✅ Đặng Tiểu Bình
```
Sinh: ['(', '1904-08-22', ')', '22 tháng 8, 1904', 'Quảng An', ',', 'Tứ Xuyên', ',', 'Đại Thanh']
```
**Extraction**: Trung Quoc ✅ (từ Chinese provinces: Tứ Xuyên, Đại Thanh)

### ✅ A. P. J. Abdul Kalam  
```
Sinh: [...'Tỉnh Madras', ',', 'Ấn Độ thuộc Anh']
```
**Extraction**: An Do ✅ (từ Madras → Tamil Nadu state)

### ✅ Abdurrahman Wahid
```
Sinh: [...'Đông Java', ',', 'Đông Ấn thuộc Hà Lan']
```
**Extraction**: Dong An ✅ (từ "Đông Ấn thuộc Hà Lan" = Dutch East Indies)

## Statistics

| Metric | v2 | v3 | Change |
|--------|----|----|--------|
| Nodes | 2114 | 2168 | +54 |
| Total Edges | 6111 | 42768 | +36657 |
| has_career | 0 | 181 | +181 |
| born_in | 660 | 943 | +283 |
| from_country | 0 | 348 | +348 |
| same_career | 0 | 1339 | +1339 |
| same_birth_country | 3194 | 39957 | +36763 |
| Career Nodes | 60+ | 24 | deduplicated |
| Country Nodes | 37 | 67 | +30 |

## Key Improvements

### 1. **Province-Aware Country Matching**
- ✅ Sichuan (Tứ Xuyên, Tu Xuyen) → Trung Quoc
- ✅ Tamil Nadu (Madras) → An Do  
- ✅ Dutch East Indies (Đông Ấn thuộc Hà Lan) → Dong An/Indonesia
- ✅ 63+ provinces across China, Vietnam, India

### 2. **Career Fields - Now Captures Positions**
- "Thủ tướng" (Prime Minister) → 181 edges
- "Tổng thống" (President)
- "Bộ trưởng" (Minister)
- "Giao sư" (Professor)
- "Nha bao" (Journalist)
- etc.

### 3. **Relationship Edges**
- **same_birth_country**: 39,957 edges (people born in same country)
- **same_career**: 1,339 edges (people with same career)

### 4. **Historical Name Support**
```python
# British India → "An Do" not "Anh"
"Ấn Độ thuộc Anh" → "An Do"

# Dutch East Indies → "Dong An" 
"Đông Ấn thuộc Hà Lan" → "Dong An"
```

## Algorithm Details

### Country Extraction Strategy
```
1. Check China provinces (most specific)
   if "Tu Xuyen" in text → "Trung Quoc"
   
2. Check Vietnam provinces
   if "Ha Noi" in text → "Viet Nam"
   
3. Check India states
   if "Tamil Nadu" in text → "An Do"
   
4. Check historical names
   if "An Do thuoc Anh" in text → "An Do"
   
5. Check country names
   if "Hoa Ky" in text → "Hoa Ky"
```

### Career Overlapping Match Detection
```python
# Sort by length DESC: longest matches first
# "Pho Thu tuong" (13) before "Thu tuong" (10) before "Tuong" (5)

# Track matched ranges to avoid overlaps
matched_ranges = [(start, end), ...]

# For each match, check if overlaps with previous matches
```

## Files Generated

- `nodes_vi_v3.json` - 2168 nodes (persons, universities, careers, countries)
- `edges_vi_v3.json` - 42768 edges with 6 types
- `edges_vi_v3.csv` - CSV export for analysis
- Properties dictionary with metadata

## Usage

```bash
python run_enrichment_vi_v3.py
```

Results in `graph_out/` directory:
- `nodes_vi_v3.json` / `.csv`
- `edges_vi_v3.json` / `.csv`
- `properties_vi_v3.json`

## Next Steps

1. **Visualization**: Use Gephi or NetworkX to visualize social networks
2. **Analysis**: 
   - Community detection
   - Centrality measures
   - Shortest paths
3. **Export**: Convert to Neo4j Cypher for database import
4. **Validation**: Spot-check more records for accuracy

---

**Status**: ✅ COMPLETE - Ready for social network analysis
**Version**: v3 (Improved)
**Generated**: December 10, 2025
