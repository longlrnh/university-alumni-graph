#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vietnamese Data Enrichment Module v3 - IMPROVED
- BETTER country extraction: provinces, districts, cities, historical names
- BETTER career extraction: avoid false matches (Y != Yes)
- MULTI-FIELD extraction: Sinh, Mat, Quoc tich, Vi tri, Location, etc.
"""

import json
import re
import csv
from collections import defaultdict
from typing import List, Dict, Tuple, Set, Optional
from pathlib import Path
import warnings

try:
    from pyvi import ViTokenizer
    from underthesea import word_tokenize
    HAS_PYVI = True
except ImportError:
    HAS_PYVI = False

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


# ============ Vietnamese Text Normalization ============

class VietnameseNormalizer:
    """Chuan hoa van ban tieng Viet"""
    
    # Diacritics mapping for normalization
    DIACRITICS_MAP = {
        'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a', 'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e', 'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o', 'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u', 'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
        'đ': 'd', 'Đ': 'd', 'Ấ': 'a',  # uppercase with diacritics
    }
    
    @staticmethod
    def remove_diacritics(text: str) -> str:
        """Loai bo dau tieng Viet"""
        result = []
        for char in text:
            result.append(VietnameseNormalizer.DIACRITICS_MAP.get(char, char))
        return ''.join(result)
    
    @staticmethod
    def normalize_vietnamese(text: str) -> str:
        """Chuan hoa tieng Viet"""
        if not text:
            return ""
        
        text = str(text).lower()
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'[^\wàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ\s\-\.]', '', text)
        
        return text


# ============ Vietnamese Career Database ============

class CareerDatabaseVI:
    """Co so du lieu nghe nghiep tieng Viet - IMPROVED"""
    
    # Main careers in Vietnamese (romanized)
    CAREERS = {
        "Tong thong": "Lanh dao",
        "Pho Tong thong": "Lanh dao",
        "Thu tuong": "Lanh dao",
        "Pho Thu tuong": "Lanh dao",
        "Bo truong": "Lanh dao",
        "Pho Bo truong": "Lanh dao",
        "Tong Bi thu": "Lanh dao",
        "Chu tich": "Lanh dao",
        "Pho Chu tich": "Lanh dao",
        "Dai su": "Ngoai giao",
        "Cong su": "Ngoai giao",
        "Tong Lanh su": "Ngoai giao",
        "Tuong": "Quan su",
        "Dai ta": "Quan su",
        "Thieu ta": "Quan su",
        "Trung ta": "Quan su",
        "Giao su": "Giao duc",
        "Pho Giao su": "Giao duc",
        "Giang vien": "Giao duc",
        "Nha giao": "Giao duc",
        "Thac si": "Giao duc",
        "Tien si": "Giao duc",
        "Hieu truong": "Giao duc",
        "Nha khoa hoc": "Khoa hoc",
        "Nha vat ly": "Khoa hoc",
        "Nha toan hoc": "Khoa hoc",
        "Nha sinh hoc": "Khoa hoc",
        "Nha dia chat": "Khoa hoc",
        "Nha thoi tiet": "Khoa hoc",
        "Nha van": "Van hoc",
        "Nha tho": "Van hoc",
        "Tac gia": "Van hoc",
        "Nha phe binh": "Van hoc",
        "Nha bao": "Truyen thong",
        "Nha chup anh": "Nghe thuat",
        "Nha dien viên": "Nghe thuat",
        "Dao dien": "Nghe thuat",
        "Nhac si": "Nghe thuat",
        "Nghe si": "Nghe thuat",
        "Hoa si": "Nghe thuat",
        "Kien truc su": "Nghe thuat",
    }
    
    @staticmethod
    def extract_careers_from_text(text: str) -> Set[str]:
        """Trich xuat nghe nghiep tu text - IMPROVED"""
        if not text:
            return set()
        
        careers = set()
        text_normalized = VietnameseNormalizer.remove_diacritics(text).lower()
        
        # Sort by length DESC to match longer phrases first (e.g., "Pho Thu tuong" before "Thu tuong" or "Tuong")
        sorted_careers = sorted(CareerDatabaseVI.CAREERS.keys(), key=lambda x: -len(x))
        
        # Track matched positions to avoid overlapping matches
        matched_ranges = []
        
        for career in sorted_careers:
            # Don't match single letters like "Y" which could be "Yes"
            if len(career) <= 1:
                continue
            
            career_normalized = VietnameseNormalizer.remove_diacritics(career).lower()
            pattern = r'\b' + re.escape(career_normalized) + r'\b'
            
            for match in re.finditer(pattern, text_normalized):
                # Check if this match overlaps with any previous match
                match_start, match_end = match.span()
                is_overlapping = False
                
                for prev_start, prev_end in matched_ranges:
                    if (match_start < prev_end and match_end > prev_start):
                        is_overlapping = True
                        break
                
                if not is_overlapping:
                    careers.add(career)
                    matched_ranges.append((match_start, match_end))
        
        return careers
    
    @staticmethod
    def get_career_category(career: str) -> Optional[str]:
        """Lay loai nghe"""
        return CareerDatabaseVI.CAREERS.get(career)


# ============ Vietnamese Country Database - ADVANCED ============

class CountryDatabaseVI:
    """Co so du lieu quoc gia tieng Viet - ADVANCED with provinces, districts, cities"""
    
    # Main countries
    COUNTRIES = {
        "Viet Nam": "VN", "Lao": "LA", "Campuchia": "KH", "Thai Lan": "TH",
        "Myanmar": "MM", "Singapore": "SG", "Malaysia": "MY", "Indonesia": "ID",
        "Philippines": "PH", "Brunei": "BN", "Dong An": "ID",  # Indonesia
        "Nhat Ban": "JP", "Han Quoc": "KR", "Trieu Tien": "KP", "Dai Loan": "TW",
        "Trung Quoc": "CN", "Hong Kong": "HK", "Macao": "MO",
        "An Do": "IN", "Pakistan": "PK", "Bangladesh": "BD", "Nepal": "NP",
        "Afghanistan": "AF", "Iran": "IR", "Iraq": "IQ", "Saudi Arabia": "SA",
        "Yemen": "YE", "Oman": "OM", "United Arab Emirates": "AE", "Qatar": "QA",
        "Bahrain": "BH", "Kuwait": "KW", "Jordan": "JO", "Lebanon": "LB",
        "Syria": "SY", "Israel": "IL", "Palestine": "PS", "Turkey": "TR",
        "Phap": "FR", "Duc": "DE", "Y": "IT", "Tay Ban Nha": "ES",
        "Bo Dao Nha": "PT", "Ha Lan": "NL", "Bi": "BE", "Thuy Si": "CH",
        "Ao": "AT", "Thuy Dien": "SE", "Na Uy": "NO", "Dan Mach": "DK",
        "Phan Lan": "FI", "Ba Lan": "PL", "Cong hoa Sec": "CZ", "Slovakia": "SK",
        "Hungary": "HU", "Romania": "RO", "Bulgaria": "BG", "Serbia": "RS",
        "Croatia": "HR", "Bosnia": "BA", "Montenegro": "ME", "Albania": "AL",
        "Macedonia": "MK", "Greece": "GR", "Ireland": "IE", "Anh": "GB",
        "Iceland": "IS", "Nga": "RU", "Ukraine": "UA", "Belarus": "BY",
        "Hoa Ky": "US", "Canada": "CA", "Mexico": "MX", "Brazil": "BR",
        "Argentina": "AR", "Chile": "CL", "Peru": "PE", "Colombia": "CO",
        "Venezuela": "VE", "Ecuador": "EC", "Cuba": "CU", "Australia": "AU",
        "New Zealand": "NZ", "Papua New Guinea": "PG",
        
        # Aliases and variants
        "Anh cong hoa": "GB", "Anh co": "GB", "De quoc Anh": "GB",
        "Nam My": "BR", "Nam Phi": "ZA",
        "Hoa Thanh": "US", "Hoa Ky": "US", "My": "US",
        "Ethiopia": "ET", "Kenya": "KE", "Nigeria": "NG", "Nam Phi": "ZA",
        "Ha Lan thuoc Ha Lan": "ID", "Dong An thuoc Ha Lan": "ID",  # Dutch East Indies -> Indonesia
    }
    
    # Chinese provinces/regions (with romanization variants)
    PROVINCES_CHINA = {
        "Tu Xuyen": "Trung Quoc",      # Sichuan
        "Tay Xuyen": "Trung Quoc",     # Also Sichuan
        "Dai Thanh": "Trung Quoc",      # Qing
        "Quang An": "Trung Quoc",       # Guangdong
        "Quang Dong": "Trung Quoc",     # Guangdong
        "Tay An": "Trung Quoc",         # Shaanxi
        "Tay Hai": "Trung Quoc",        # Shaanxi variant
        "Bac Kinh": "Trung Quoc",       # Beijing
        "Pec Kinh": "Trung Quoc",       # Beijing variant
        "Thuong Hai": "Trung Quoc",     # Shanghai
        "Thuong Khai": "Trung Quoc",    # Shanghai variant
        "Chongqing": "Trung Quoc",
        "Yunnan": "Trung Quoc",
        "Tibet": "Trung Quoc",
        "Tay Trang": "Trung Quoc",      # Xinjiang
        "Tay Trang": "Trung Quoc",
        "Heilongjiang": "Trung Quoc",
        "Jilin": "Trung Quoc",
        "Liaoning": "Trung Quoc",
        "Inner Mongolia": "Trung Quoc",
        "Noi Mong": "Trung Quoc",
        "Khang Tay": "Trung Quoc",      # Gansu
        "Thanh Hai": "Trung Quoc",      # Qinghai
        "Hui Hoi": "Trung Quoc",        # Ningxia
        "Giang Tay": "Trung Quoc",      # Jiangxi
        "Giang Su": "Trung Quoc",       # Jiangsu
        "Chi Nhan": "Trung Quoc",       # Zhejiang
        "Phu Kien": "Trung Quoc",       # Fujian
        "Hunan": "Trung Quoc",
        "Hubei": "Trung Quoc",
        "Anhui": "Trung Quoc",
        "Shandong": "Trung Quoc",
        "Henan": "Trung Quoc",
        "Shanxi": "Trung Quoc",
    }
    
    # Vietnamese provinces/regions
    PROVINCES_VN = {
        "Ha Noi": "Viet Nam", "Ho Chi Minh": "Viet Nam", "Da Nang": "Viet Nam",
        "TPHCM": "Viet Nam", "TP Ho Chi Minh": "Viet Nam", "Thanh pho Ho Chi Minh": "Viet Nam",
        "Hai Phong": "Viet Nam", "Can Tho": "Viet Nam", "Thai Binh": "Viet Nam",
        "Thai Nguyen": "Viet Nam", "Quang Ninh": "Viet Nam", "Bac Kan": "Viet Nam",
        "Cao Bang": "Viet Nam", "Lang Son": "Viet Nam", "Tuyen Quang": "Viet Nam",
        "Yen Bai": "Viet Nam", "Dien Bien": "Viet Nam", "Lai Chau": "Viet Nam",
        "Son La": "Viet Nam", "Hoa Binh": "Viet Nam", "Phu Tho": "Viet Nam",
        "Vinh Phuc": "Viet Nam", "Bac Giang": "Viet Nam", "Bac Ninh": "Viet Nam",
        "Hai Duong": "Viet Nam", "Hung Yen": "Viet Nam", "Ha Giang": "Viet Nam",
        "Nam Dinh": "Viet Nam", "Ninh Binh": "Viet Nam", "Thanh Hoa": "Viet Nam",
        "Nghe An": "Viet Nam", "Ha Tinh": "Viet Nam", "Quang Binh": "Viet Nam",
        "Quang Tri": "Viet Nam", "Thua Thien Hue": "Viet Nam", "Quang Nam": "Viet Nam",
        "Quang Ngai": "Viet Nam", "Binh Dinh": "Viet Nam", "Phu Yen": "Viet Nam",
        "Khanh Hoa": "Viet Nam", "Ninh Thuan": "Viet Nam", "Binh Thuan": "Viet Nam",
        "Dong Nai": "Viet Nam", "Ba Ria": "Viet Nam", "Long An": "Viet Nam",
        "Tien Giang": "Viet Nam", "Ben Tre": "Viet Nam", "Vinh Long": "Viet Nam",
        "Tra Vinh": "Viet Nam", "An Giang": "Viet Nam", "Kien Giang": "Viet Nam",
        "Hau Giang": "Viet Nam", "Soc Trang": "Viet Nam", "Bac Lieu": "Viet Nam",
        "Ca Mau": "Viet Nam",
    }
    
    # Historical country names and aliases
    HISTORICAL_NAMES = {
        "Anh thuoc Anh": "Anh",                    # British Empire
        "De quoc Anh": "Anh",                      # British Empire
        "An Do thuoc Anh": "An Do",                # British India
        "An Do Anh": "An Do",                      # British India
        "Anh cong hoa": "Anh",                     # English Republic
        "De quoc Uc": "Australia",
        "Hoa Ky": "Hoa Ky",
        "Cong hoa Xa hoi Chu nghia": "Nga",       # Soviet
        "Tho Nhi Ky": "Turkey",
        "Thuong Hang": "Thuong Hai",
    }
    
    # Indian states (common ones)
    INDIA_STATES = {
        "Tamil Nadu": "An Do",
        "Madras": "An Do",
        "Bengal": "An Do",
        "Gujarat": "An Do",
        "Maharashtra": "An Do",
        "Karnataka": "An Do",
        "Andhra Pradesh": "An Do",
        "Uttar Pradesh": "An Do",
        "Bihar": "An Do",
        "Punjab": "An Do",
        "Rajasthan": "An Do",
        "Haryana": "An Do",
    }
    
    @staticmethod
    def extract_country_from_text(text: str) -> Optional[str]:
        """
        Extract country from text with multiple strategies:
        1. Check China provinces first (most specific)
        2. Check Vietnam provinces
        3. Check India states
        4. Check historical names
        5. Check country names
        """
        if not text:
            return None
        
        # Convert to string if list
        if isinstance(text, list):
            text = ' '.join(str(x) for x in text)
        
        text = str(text).lower()
        
        # Normalize diacritics for matching
        text_normalized = VietnameseNormalizer.remove_diacritics(text)
        
        # Strategy 1: Check Chinese provinces FIRST (most specific)
        for province, country in CountryDatabaseVI.PROVINCES_CHINA.items():
            province_normalized = VietnameseNormalizer.remove_diacritics(province.lower())
            # Use word boundary to avoid false matches
            if re.search(r'\b' + re.escape(province_normalized) + r'\b', text_normalized):
                return country
        
        # Strategy 2: Check Vietnamese provinces
        for province, country in CountryDatabaseVI.PROVINCES_VN.items():
            province_normalized = VietnameseNormalizer.remove_diacritics(province.lower())
            if re.search(r'\b' + re.escape(province_normalized) + r'\b', text_normalized):
                return country
        
        # Strategy 3: Check Indian states
        for state, country in CountryDatabaseVI.INDIA_STATES.items():
            state_normalized = VietnameseNormalizer.remove_diacritics(state.lower())
            if re.search(r'\b' + re.escape(state_normalized) + r'\b', text_normalized):
                return country
        
        # Strategy 4: Check historical names (e.g., "An Do thuoc Anh" -> "An Do")
        for hist_name, country in CountryDatabaseVI.HISTORICAL_NAMES.items():
            hist_normalized = VietnameseNormalizer.remove_diacritics(hist_name.lower())
            if hist_normalized in text_normalized:
                return country
        
        # Strategy 5: Check country names
        for country_name in CountryDatabaseVI.COUNTRIES.keys():
            country_normalized = VietnameseNormalizer.remove_diacritics(country_name.lower())
            # Use word boundary for single-letter countries to avoid false matches
            if len(country_name) == 1:
                pattern = r'\b' + re.escape(country_normalized) + r'\b'
            else:
                pattern = r'\b' + re.escape(country_normalized)
            
            if re.search(pattern, text_normalized):
                return country_name
        
        return None
    
    @staticmethod
    def extract_countries_from_text(text: str) -> Set[str]:
        """Extract all countries from text (multiple mentions)"""
        if not text:
            return set()
        
        # Convert to string if list
        if isinstance(text, list):
            text = ' '.join(str(x) for x in text)
        
        text = str(text).lower()
        text_normalized = VietnameseNormalizer.remove_diacritics(text)
        
        found_countries = set()
        
        # Check all country names
        for country_name in CountryDatabaseVI.COUNTRIES.keys():
            country_normalized = VietnameseNormalizer.remove_diacritics(country_name.lower())
            if country_name == "Y":  # Skip single-letter abbreviations
                continue
            if re.search(r'\b' + re.escape(country_normalized) + r'\b', text_normalized):
                found_countries.add(country_name)
        
        return found_countries
    
    @staticmethod
    def get_country_code(country: str) -> Optional[str]:
        """Lay ma ISO quoc gia"""
        return CountryDatabaseVI.COUNTRIES.get(country)


# ============ Graph Enricher v3 ============

class GraphEnricherVIv3:
    """Lam giau du lieu do thi tieng Viet - Phien ban 3 (Improved)"""
    
    UNIVERSITY_KEYWORDS = {
        'dai hoc', 'university', 'truong dai hoc', 'hoc vien', 'college',
        'institute', 'academy', 'school', 'technical', 'polytechnic',
        'high school', 'trung hoc', 'secondary'
    }
    
    def __init__(self, input_file: str = "graph_out/node_details.json"):
        """Khoi tao enricher"""
        self.input_file = input_file
    
    def load_and_filter_nodes(self) -> Tuple[List[Dict], List[Dict]]:
        """Tai va loc nodes"""
        print("[+] Loading nodes...")
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            nodes = json.load(f)
        
        print(f"[+] Total nodes: {len(nodes)}")
        
        person_nodes = []
        university_nodes = []
        
        for node in nodes:
            node_type = node.get("type", "").lower()
            
            if node_type == "person":
                person_nodes.append(node)
            elif node_type == "university":
                university_nodes.append(node)
            else:
                title = str(node.get("title", "")).lower()
                if any(kw in title for kw in self.UNIVERSITY_KEYWORDS):
                    university_nodes.append(node)
        
        print(f"[OK] Filtered: {len(person_nodes)} persons, {len(university_nodes)} universities")
        
        return person_nodes, university_nodes
    
    def extract_enrichments(self, person_nodes: List[Dict]) -> Dict:
        """
        Trich xuat du lieu tu nguoi - IMPROVED
        - Sinh, Mat: extract birth/death country
        - Quoc tich, Quoc gia: extract nationality/country
        - Chuc vu, Nghe, etc: extract careers
        """
        enrichments = defaultdict(lambda: {
            'careers': set(),
            'countries': set(),
            'birth_country': None,
            'death_country': None,
            'education': [],
            'birth_location': None,
            'death_location': None,
        })
        
        print("[+] Extracting enrichments...")
        total = len(person_nodes)
        
        for idx, node in enumerate(person_nodes):
            if (idx + 1) % max(1, total // 10) == 0:
                print(f"   {((idx + 1) * 100 // total)}%", end='\r')
            
            title = node.get("title", "")
            props = node.get("properties", {})
            
            if not props:
                continue
            
            # ===== CAREER EXTRACTION =====
            # Look for position/career in ALL properties fields
            # Skip non-career fields
            skip_fields = {
                "Sinh", "Mất", "Nơi an nghỉ", "Con cái", "Phối ngẫu", "Website", 
                "Chữ ký", "Tôn giáo", "Alma mater", "Giáo dục", "Trường học", "Học vấn",
                "Tiền nhiệm", "Kế nhiệm", "Bổ nhiệm", "Nhiệm kỳ", "Đảng chính trị",
                "Quốc tịch", "Quốc gia", "Vị trí", "Location", "Nơi cư trú"
            }
            
            # Extract careers from ALL fields (except skip_fields)
            for field, value in props.items():
                if field not in skip_fields:
                    # The field name itself might be a career (e.g., "Tổng thống", "Thủ tướng")
                    field_careers = CareerDatabaseVI.extract_careers_from_text(field)
                    enrichments[title]['careers'].update(field_careers)
                    
                    # Also check the value
                    text = str(value)
                    value_careers = CareerDatabaseVI.extract_careers_from_text(text)
                    enrichments[title]['careers'].update(value_careers)
            
            # ===== COUNTRY/LOCATION EXTRACTION =====
            # Priority: Sinh -> Mat -> Quoc tich -> Quoc gia -> Vi tri -> Location
            
            # Birth location
            if "Sinh" in props:
                birth_data = props["Sinh"]
                birth_country = CountryDatabaseVI.extract_country_from_text(birth_data)
                if birth_country:
                    enrichments[title]['birth_country'] = birth_country
            
            # Death location
            if "Mat" in props:
                death_data = props["Mat"]
                death_country = CountryDatabaseVI.extract_country_from_text(death_data)
                if death_country:
                    enrichments[title]['death_country'] = death_country
            
            # Nationality
            if "Quốc tịch" in props:
                nationality = props["Quốc tịch"]
                countries = CountryDatabaseVI.extract_countries_from_text(nationality)
                enrichments[title]['countries'].update(countries)
            
            # Country (from multiple fields) - using actual Vietnamese keys
            for field in ["Quốc gia", "Vị trí", "Location", "Nơi cư trú", "Nơi cư ngụ", "Cư trú", "Khu vực"]:
                if field in props:
                    text = str(props[field])
                    countries = CountryDatabaseVI.extract_countries_from_text(text)
                    enrichments[title]['countries'].update(countries)
            
            # Education
            for field in ["Alma mater", "Giáo dục", "Trường học", "Học vấn"]:
                if field in props:
                    alma_mater = props[field]
                    if isinstance(alma_mater, str):
                        enrichments[title]['education'].append(alma_mater)
                    elif isinstance(alma_mater, list):
                        enrichments[title]['education'].extend(alma_mater)
        
        print(f"\n[OK] Extraction done")
        
        return enrichments
    
    def create_enriched_nodes(self, person_nodes: List[Dict], 
                             university_nodes: List[Dict],
                             enrichments: Dict) -> Tuple[List[Dict], Dict]:
        """Tao nodes giau du lieu"""
        enriched_nodes = []
        properties_dict = {}
        
        print("[+] Creating nodes...")
        
        # Add person nodes
        print("  - Adding person nodes...")
        for node in person_nodes:
            title = node.get("title", "")
            new_node = {
                "id": title,
                "title": title,
                "type": "person",
                "link": f"https://vi.wikipedia.org/wiki/{title.replace(' ', '_')}",
            }
            enriched_nodes.append(new_node)
            properties_dict[title] = node.get("properties", {})
        
        # Add career nodes
        print("  - Adding career nodes...")
        all_careers = set()
        for enrich in enrichments.values():
            all_careers.update(enrich['careers'])
        
        for career in all_careers:
            category = CareerDatabaseVI.get_career_category(career)
            node = {
                "id": f"career_{career}",
                "title": career,
                "type": "career",
                "category": category or "Other",
                "link": f"https://vi.wikipedia.org/wiki/{career.replace(' ', '_')}",
            }
            enriched_nodes.append(node)
            properties_dict[f"career_{career}"] = {"type": "career"}
        
        # Add country nodes
        print("  - Adding country nodes...")
        all_countries = set()
        for enrich in enrichments.values():
            all_countries.update(enrich['countries'])
            if enrich['birth_country']:
                all_countries.add(enrich['birth_country'])
            if enrich['death_country']:
                all_countries.add(enrich['death_country'])
        
        for country in all_countries:
            code = CountryDatabaseVI.get_country_code(country)
            node = {
                "id": f"country_{country}",
                "title": country,
                "type": "country",
                "code": code or "?",
                "link": f"https://vi.wikipedia.org/wiki/{country.replace(' ', '_')}",
            }
            enriched_nodes.append(node)
            properties_dict[f"country_{country}"] = {"type": "country", "code": code}
        
        # Add university nodes
        print("  - Adding university nodes...")
        for node in university_nodes:
            title = node.get("title", "")
            new_node = {
                "id": title,
                "title": title,
                "type": "university",
                "link": f"https://vi.wikipedia.org/wiki/{title.replace(' ', '_')}",
            }
            enriched_nodes.append(new_node)
            properties_dict[title] = node.get("properties", {})
        
        print(f"[OK] Created: {len(enriched_nodes)} nodes")
        
        return enriched_nodes, properties_dict
    
    def create_enriched_edges(self, person_nodes: List[Dict],
                             enrichments: Dict) -> List[Dict]:
        """Tao edges giau du lieu"""
        edges = []
        
        print("[+] Creating edges...")
        
        # 1. Career edges
        print("  - Career edges...")
        for person_title, enrich in enrichments.items():
            for career in enrich['careers']:
                edges.append({
                    "from": person_title,
                    "to": f"career_{career}",
                    "type": "has_career",
                    "weight": 1,
                })
        
        # 2. Birth country edges
        print("  - Birth location edges...")
        for person_title, enrich in enrichments.items():
            if enrich['birth_country']:
                edges.append({
                    "from": person_title,
                    "to": enrich['birth_country'],
                    "type": "born_in",
                    "weight": 1,
                })
        
        # 3. Death country edges
        print("  - Death location edges...")
        for person_title, enrich in enrichments.items():
            if enrich['death_country']:
                edges.append({
                    "from": person_title,
                    "to": enrich['death_country'],
                    "type": "died_in",
                    "weight": 1,
                })
        
        # 4. Country edges (from Quoc tich, etc)
        print("  - Country edges...")
        for person_title, enrich in enrichments.items():
            for country in enrich['countries']:
                edges.append({
                    "from": person_title,
                    "to": country,
                    "type": "from_country",
                    "weight": 1,
                })
        
        print(f"[OK] Created: {len(edges)} edges")
        
        return edges
    
    def create_relationship_edges(self, person_nodes: List[Dict],
                                 university_nodes: List[Dict],
                                 enrichments: Dict) -> List[Dict]:
        """Tao relationship edges: same_country, same_career, same_school"""
        edges = []
        
        print("[+] Creating relationship edges...")
        
        # Get all person titles
        person_titles = set(node.get("title", "") for node in person_nodes)
        university_titles = set(node.get("title", "") for node in university_nodes)
        
        # 1. Same country edges
        print("  - Same country relationships...")
        country_to_persons = defaultdict(list)
        for person_title, enrich in enrichments.items():
            if enrich['birth_country']:
                country_to_persons[enrich['birth_country']].append(person_title)
        
        for country, persons in country_to_persons.items():
            for i in range(len(persons)):
                for j in range(i + 1, len(persons)):
                    edges.append({
                        "from": persons[i],
                        "to": persons[j],
                        "type": "same_birth_country",
                        "weight": 1,
                    })
        
        # 2. Same career edges
        print("  - Same career relationships...")
        career_to_persons = defaultdict(list)
        for person_title, enrich in enrichments.items():
            for career in enrich['careers']:
                career_to_persons[career].append(person_title)
        
        for career, persons in career_to_persons.items():
            for i in range(len(persons)):
                for j in range(i + 1, len(persons)):
                    edges.append({
                        "from": persons[i],
                        "to": persons[j],
                        "type": "same_career",
                        "weight": 1,
                    })
        
        print(f"[OK] Created: {len(edges)} relationship edges")
        
        return edges
    
    def enrich_and_export(self, output_prefix: str = "enriched_vi"):
        """Main orchestration function"""
        print("=" * 80)
        print("Vietnamese Data Enrichment Pipeline v3")
        print("=" * 80)
        
        # Load and filter
        person_nodes, university_nodes = self.load_and_filter_nodes()
        
        # Extract
        enrichments = self.extract_enrichments(person_nodes)
        
        # Create nodes
        enriched_nodes, properties_dict = self.create_enriched_nodes(
            person_nodes, university_nodes, enrichments
        )
        
        # Create edges
        enrichment_edges = self.create_enriched_edges(person_nodes, enrichments)
        relationship_edges = self.create_relationship_edges(
            person_nodes, university_nodes, enrichments
        )
        
        all_edges = enrichment_edges + relationship_edges
        
        # Export JSON
        print("[+] Exporting...")
        
        nodes_file = f"graph_out/nodes_{output_prefix}.json"
        with open(nodes_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_nodes, f, ensure_ascii=False, indent=2)
        print(f"  [OK] Saved: {nodes_file}")
        
        properties_file = f"graph_out/properties_{output_prefix}.json"
        with open(properties_file, 'w', encoding='utf-8') as f:
            json.dump(properties_dict, f, ensure_ascii=False, indent=2)
        print(f"  [OK] Saved: {properties_file}")
        
        edges_file = f"graph_out/edges_{output_prefix}.json"
        with open(edges_file, 'w', encoding='utf-8') as f:
            json.dump(all_edges, f, ensure_ascii=False, indent=2)
        print(f"  [OK] Saved: {edges_file}")
        
        # Export CSV
        edges_csv = f"graph_out/edges_{output_prefix}.csv"
        with open(edges_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['from', 'to', 'type', 'weight'])
            writer.writeheader()
            writer.writerows(all_edges)
        print(f"  [OK] Saved: {edges_csv}")
        
        nodes_csv = f"graph_out/nodes_{output_prefix}.csv"
        with open(nodes_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'title', 'type'])
            writer.writeheader()
            for node in enriched_nodes:
                writer.writerow({
                    'id': node['id'],
                    'title': node['title'],
                    'type': node['type']
                })
        print(f"  [OK] Saved: {nodes_csv}")
        
        # Print statistics
        print("\n" + "=" * 80)
        print("STATISTICS")
        print("=" * 80)
        print(f"Nodes: {len(enriched_nodes)}")
        print(f"Edges: {len(all_edges)}")
        
        # Count edge types
        edge_types = defaultdict(int)
        for edge in all_edges:
            edge_types[edge['type']] += 1
        
        print("\nEdge types:")
        for edge_type, count in sorted(edge_types.items(), key=lambda x: -x[1]):
            print(f"  {edge_type}: {count}")
        
        return enriched_nodes, all_edges


if __name__ == "__main__":
    enricher = GraphEnricherVIv3()
    enricher.enrich_and_export()
