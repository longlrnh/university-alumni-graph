# -*- coding: utf-8 -*-
"""
4_chatbot_graphrag.py
Chatbot kết hợp GraphRAG + LLM Qwen OWen3 0.6B
"""
import os
import re
import unicodedata
from typing import Dict, Optional, List


class QwenLLM:
    """LLM Qwen OWen3 0.6B + GraphRAG"""
    
    def __init__(self, model_name: str = "Qwen/Qwen2-0.5B-Instruct"):
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM
            
            print(f"\n⏳ Khởi tạo Qwen OWen3 + GraphRAG...")
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"   Thiết bị: {self.device.upper()}")
            
            print(f"   📥 Tokenizer...", end="", flush=True)
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            print(f" ✓")
            
            print(f"   📥 Model (≈1.2 GB)...", end="", flush=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None
            )
            if self.device == "cpu":
                self.model = self.model.to(self.device)
            print(f" ✓")
            print("✅ Qwen OWen3 sẵn sàng với GraphRAG!")
            self.ready = True
        except Exception as e:
            print(f"\n❌ Lỗi tải Qwen: {e}")
            self.ready = False
    
    def generate(self, query: str, context: str, reasoning: Optional[Dict] = None, max_tokens: int = 256, node_details_context: str = "") -> str:
        """Sinh câu trả lời từ Qwen + GraphRAG"""
        if not self.ready:
            raise RuntimeError("Qwen LLM không sẵn sàng. Vui lòng kiểm tra cài đặt.")
        
        # Xây dựng prompt với GraphRAG context
        reasoning_info = ""
        if reasoning and reasoning.get('connected'):
            reasoning_info = f"Từ suy luận đồ thị qua các cạnh/kết nối: {reasoning.get('description', '')}\n"
        
        # Instruction rõ ràng
        instruction = "Hãy trả lời dựa trên context được cung cấp. Trả lời ngắn gọn, chính xác, chỉ dùng tiếng Việt."
        instruction += " Lưu ý: Trong đồ thị, 'quan hệ' là các cạnh (edges) kết nối giữa các node/thực thể."
        if "những" in query.lower() or "nào" in query.lower() or "tất cả" in query.lower():
            instruction += " Liệt kê tất cả thông tin liên quan."
        
        # Thêm chi tiết node nếu có
        detailed_context = f"{context}"
        if node_details_context:
            detailed_context += f"\n\n=== CHI TIẾT THÔNG TIN CÁ NHÂN ===\n{node_details_context}"
        
        prompt = f"""Bạn là chatbot thông minh về mạng alumni. {instruction}

CONTEXT:
{detailed_context}

{reasoning_info}

QUESTION: {query}

ANSWER:"""
        
        import torch
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=0.2,  # Giảm từ 0.7 → 0.2 (ổn định hơn)
                top_p=0.9,
                do_sample=True
            )
        
        response = self.tokenizer.decode(output[0], skip_special_tokens=True)
        
        # Extract answer từ response
        if "ANSWER:" in response:
            response = response.split("ANSWER:")[-1].strip()
        
        # Làm sạch response
        response = response.strip().strip('"').strip()
        
        return response


class GraphRAGChatbot:
    """Chatbot kết hợp GraphRAG + Qwen OWen3 LLM"""
    
    def __init__(self, kg, reasoner, node_details_path='../graph_out/node_details.json'):
        self.kg = kg
        self.reasoner = reasoner
        self._llm = None  # Lazy load
        
        # Load node details
        self.node_details = {}
        import json
        try:
            with open(node_details_path, 'r', encoding='utf-8') as f:
                details_list = json.load(f)
                for detail in details_list:
                    title = detail.get('title', '')
                    self.node_details[title] = detail
            print(f"   📚 Đã load {len(self.node_details)} node details")
        except Exception as e:
            print(f"   ⚠️  Không thể load node_details.json: {e}")
            self.node_details = {}
        
        print("\n" + "🤖 CHATBOT GRAPHRAG + QWEN OWEN3 ".center(70, "="))
        print("✓ Knowledge Graph: Đồ thị tri thức mạng alumni")
        print("✓ Node Details: Thông tin chi tiết từ Wikipedia")
        print("✓ GraphRAG: Truy xuất thông tin từ đồ thị")
        print("✓ Multi-hop Reasoning: Suy luận kết nối phức tạp")
        print("✓ Qwen OWen3 LLM: Tạo câu trả lời thông minh")
        print("=" * 70)
    
    @property
    def llm(self):
        if self._llm is None:
            self._llm = QwenLLM()
        return self._llm
    
    def answer(self, query: str) -> Dict:
        import re
        def replace_thankyou(text):
            thank_patterns = [
                r"thank you for your time and concern[.!]*",
                r"thank you[.!]*",
                r"thanks[.!]*",
                r"thank you very much[.!]*"
            ]
            for pat in thank_patterns:
                text = re.sub(pat, "Cảm ơn bạn đã quan tâm!", text, flags=re.IGNORECASE)
            return text

        norm_query = self._normalize_text(query)
        entities = self.reasoner._extract_entities(query)
        
        # ═══════════════════════════════════════════════════════════════
        # BƯỚC 1: PHÂN LOẠI CÂU HỎI NGAY TỪ ĐẦU (3 LOẠI)
        # ═══════════════════════════════════════════════════════════════
        
        # 1. MULTIPLE CHOICE - Câu hỏi lựa chọn (có A. B. C. D.)
        is_multiple_choice = bool(re.search(r'\b[A-D]\.\s*', query))
        
        # 2. YES/NO - Câu hỏi có/không
        has_university_keyword = any(w in norm_query for w in ['trường', 'hoc', 'học', 'alumni', 'cùng học', 'cùng trường'])
        query_type = self._classify_query(query)
        if has_university_keyword and query_type == 'yes_no':
            query_type = 'university'
        is_yes_no = (query_type in ['yes_no', 'university', 'connection'])
        
        # 3. GENERAL - Câu hỏi còn lại
        
        # ═══════════════════════════════════════════════════════════════
        # BƯỚC 2: XỬ LÝ THEO LOẠI CÂU HỎI
        # ═══════════════════════════════════════════════════════════════
        
        # ───────────────────────────────────────────────────────────────
        # LOẠI 1: MULTIPLE CHOICE - Chỉ trả lời đáp án
        # ───────────────────────────────────────────────────────────────
        if is_multiple_choice:
            return self._handle_multiple_choice(query, entities, norm_query)
        
        # ───────────────────────────────────────────────────────────────
        # LOẠI 2: YES/NO - Trả lời Có/Không đầu tiên
        # ───────────────────────────────────────────────────────────────
        if is_yes_no:
            return self._handle_yes_no(query, query_type, entities, norm_query, replace_thankyou)
        
        # ───────────────────────────────────────────────────────────────
        # LOẠI 3: GENERAL - Các câu hỏi còn lại
        # ───────────────────────────────────────────────────────────────
        
        reasoning = None
        answer_text = None
        
        # Truy vấn tổng hợp: lọc person theo country + university (alumni)
        country_hit = self._find_node_by_type_in_query(norm_query, 'country')
        uni_hit = self._find_node_by_type_in_query(norm_query, 'university')
        aggregate_trigger = any(kw in norm_query for kw in [
            'cuu sinh vien', 'alumni', 'hoc tai', 'hoc o', 'tung hoc', 'hoc tai harvard', 'hoc tai', 'học tại', 'cựu sinh viên', 'sinh vien'
        ])
        
        # Trường hợp country + university
        if aggregate_trigger and country_hit and uni_hit:
            agg = self.reasoner.find_people_by_country_and_university(country_hit, uni_hit, limit=50)
            if agg.get('missing'):
                answer_text = f"❌ Không tìm thấy node: {', '.join(agg['missing'])}"
            elif agg['people']:
                answer_text = f"Các cựu sinh viên từ {country_hit} học tại {uni_hit}: {', '.join(agg['people'])}"
            else:
                answer_text = f"Không tìm thấy cựu sinh viên từ {country_hit} học {uni_hit} trong đồ thị."
            return {
                'query': query,
                'type': 'aggregate_alumni_country_university',
                'context': '',
                'reasoning': None,
                'answer': replace_thankyou(answer_text)
            }
                # Trường hợp country + university
        if aggregate_trigger and country_hit and uni_hit:
            agg = self.reasoner.find_people_by_country_and_university(country_hit, uni_hit, limit=50)
            if agg.get('missing'):
                answer_text = f"❌ Không tìm thấy node: {', '.join(agg['missing'])}"
            elif agg['people']:
                # ✅ Nếu KG đã có dữ liệu, dùng luôn
                answer_text = f"Các cựu sinh viên từ {country_hit} học tại {uni_hit}: {', '.join(agg['people'])}"
            else:
                # ✅ FALLBACK: dùng node_details nếu KG không trả được người nào
                fallback_people = self._fallback_people_by_country_and_university(country_hit, uni_hit, limit=50)
                if fallback_people:
                    answer_text = (
                        f"Các cựu sinh viên từ {country_hit} học tại {uni_hit} (suy ra từ node_details): "
                        f"{', '.join(sorted(set(fallback_people)))}"
                    )
                else:
                    answer_text = f"Không tìm thấy cựu sinh viên từ {country_hit} học {uni_hit} trong đồ thị."
            return {
                'query': query,
                'type': 'aggregate_alumni_country_university',
                'context': '',
                'reasoning': None,
                'answer': replace_thankyou(answer_text)
            }

        # Trường hợp chỉ university: liệt kê cựu sinh viên của trường
        if aggregate_trigger and uni_hit and not country_hit:
            agg = self.reasoner.find_people_by_university(uni_hit, limit=100)
            if agg.get('missing'):
                answer_text = f"❌ Không tìm thấy node: {', '.join(agg['missing'])}"
            elif agg['people']:
                answer_text = f"Các cựu sinh viên của {uni_hit}: {', '.join(sorted(agg['people']))}"
            else:
                answer_text = f"Không tìm thấy cựu sinh viên của {uni_hit} trong đồ thị."
            return {
                'query': query,
                'type': 'aggregate_alumni_university',
                'context': '',
                'reasoning': None,
                'answer': replace_thankyou(answer_text)
            }

        # Nhận diện câu hỏi liệt kê chức vụ/career/country
        match = re.search(r"phó tổng thống|pho_tong_thong|vice president|career|country|chức vụ|position", query.lower())
        if match:
            result = []
            keywords = ['phó tổng thống', 'pho_tong_thong', 'vice president', 'career', 'country', 'chức vụ', 'position']
            for node_id, data in self.reasoner.kg.G.nodes(data=True):
                props = data.get('properties')
                if props and isinstance(props, dict):
                    for k, v in props.items():
                        if any(kw in str(k).lower() for kw in keywords):
                            result.append(data['title'])
                        if isinstance(v, str) and any(kw in v.lower() for kw in keywords):
                            result.append(data['title'])
                        elif isinstance(v, list) and any(any(kw in str(x).lower() for kw in keywords) for x in v):
                            result.append(data['title'])
            if result:
                answer_text = f"Các node liên quan đến chức vụ/country/career: {', '.join(sorted(set(result)))}"
            else:
                answer_text = "Không tìm thấy node nào phù hợp trong mạng lưới."
            return {
                'query': query,
                'type': 'list_career_country',
                'context': '',
                'reasoning': None,
                'answer': replace_thankyou(answer_text)
            }

        # Xử lý câu hỏi về thông tin chi tiết một node cụ thể
        uni_hint = self._find_node_by_type_in_query(norm_query, 'university')
        if len(entities) == 1 and query_type == 'general' and not uni_hint and 'hoc' not in norm_query and 'học' not in query.lower():
            entity_name = entities[0]
            node_detail = self.node_details.get(entity_name)
            
            # Nếu có thông tin chi tiết từ node_details
            if node_detail:
                info_text = self._format_node_detail(node_detail)
                return {
                    'query': query,
                    'type': 'node_detail',
                    'context': info_text[:500],
                    'reasoning': None,
                    'answer': replace_thankyou(info_text)
                }

        # Nhận diện câu hỏi liệt kê mối quan hệ/cạnh/kết nối
        if any(kw in query.lower() for kw in ['liệt kê', 'kể tên', 'các mối quan hệ', 'những mối quan hệ', 'relationship', 'connections', 'cạnh', 'kết nối']) and len(entities) >= 2:
            node1 = self.reasoner.kg.title_to_node.get(entities[0])
            node2 = self.reasoner.kg.title_to_node.get(entities[1])
            edges = []
            connected_flag = False
            # Cạnh thuận (edge from node1 to node2)
            if node1 and node2 and node2 in self.reasoner.kg.G[node1]:
                rel = self.reasoner.kg.G[node1][node2]['relation']
                edges.append(f"🔗 {entities[0]} --[cạnh: {rel}]--> {entities[1]}")
                connected_flag = True
            # Cạnh ngược (edge from node2 to node1)
            if node1 and node2 and node1 in self.reasoner.kg.G[node2]:
                rel = self.reasoner.kg.G[node2][node1]['relation']
                edges.append(f"🔗 {entities[1]} --[cạnh: {rel}]--> {entities[0]}")
                connected_flag = True

            # Kiểm tra properties của mỗi node
            info1 = self.reasoner.kg.get_node_info(node1) if node1 else None
            info2 = self.reasoner.kg.get_node_info(node2) if node2 else None
            def check_properties(info_a, name_b):
                rels = []
                if info_a and info_a.get('properties'):
                    props = info_a['properties']
                    if isinstance(props, dict):
                        for k, v in props.items():
                            if isinstance(v, str) and name_b in v:
                                rels.append(f"{info_a['title']} --[{k}]--> {name_b}")
                            elif isinstance(v, list) and any(name_b in str(x) for x in v):
                                rels.append(f"{info_a['title']} --[{k}]--> {name_b}")
                return rels
            edges += check_properties(info1, entities[1])
            edges += check_properties(info2, entities[0])

            if edges:
                # luôn trả lời bắt đầu bằng Có/Không
                prefix = "Có, "
                answer_text = prefix + f"Các cạnh/quan hệ/kết nối giữa {entities[0]} và {entities[1]}:\n" + "\n".join(edges)
            else:
                answer_text = f"Không, không tìm thấy cạnh/quan hệ trực tiếp giữa {entities[0]} và {entities[1]} trong đồ thị.\n💡 Giải thích: Hai thực thể này không có kết nối trực tiếp (cạnh) trong knowledge graph."
            
            return {
                'query': query,
                'type': 'list_relationships',
                'context': '',
                'reasoning': None,
                'answer': answer_text
            }

        # Nếu chưa có answer, dùng LLM
        context = self.reasoner.retrieve_context(query)
        # Thêm node details context để LLM có info chi tiết hơn
        node_details_ctx = self._build_node_details_context(entities)
        answer_text = self.llm.generate(query, context, reasoning, node_details_context=node_details_ctx)

        return {
            'query': query,
            'type': query_type,
            'context': self.reasoner.retrieve_context(query)[:300] + "...",
            'reasoning': reasoning,
            'answer': replace_thankyou(answer_text)
        }
    
    def _classify_query(self, query: str) -> str:
        """Phân loại loại câu hỏi"""
        query_lower = query.lower()
        
        # Trắc nghiệm lựa chọn (multiple choice)
        if re.search(r'\b[A-D]\.', query_lower) or re.search(r'\b[a-d]\.', query_lower):
            return 'multiple_choice'
        
        if any(w in query_lower for w in ['kết nối', 'liên kết', 'quan hệ', 'có mối', 'được kết nối']):
            return 'connection'
        elif any(w in query_lower for w in ['trường', 'đại học', 'cùng trường', 'cùng học', 'cùng đại học', 'học ', 'hoc ', 'alumni', 'học tại', 'hoc tai']):
            return 'university'
        
        # Câu hỏi Đúng/Sai hoặc Yes/No
        # Chỉ match yes/no patterns, không match "có học" hoặc "có kết nối"
        if (query_lower.startswith(('có phải', 'có khác', 'không phải ', 'không ', 'đúng ', 'sai ')) or
            any(phrase in query_lower for phrase in ['đúng không', 'phải không', 'sai không', 'có phải', 'không phải']) or
            query_lower.endswith(('không?', 'phải?'))):
            return 'yes_no'
        else:
            return 'general'

    def _normalize_text(self, text: str) -> str:
        """Chuẩn hóa để so khớp tự do trong câu hỏi"""
        import re
        s = unicodedata.normalize('NFD', text)
        s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
        s = s.lower().replace('_', ' ').replace('-', ' ')
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        return " ".join(s.split())

    def _find_node_by_type_in_query(self, norm_query: str, node_type: str) -> Optional[str]:
        """Tìm node theo loại nếu tiêu đề xuất hiện trong câu hỏi (lỏng)"""
        query_tokens = set(norm_query.split())
        generic = {'country', 'dai', 'hoc', 'university', 'truong', 'o', 'dau', 'nao', 'nhung', 'sinh', 'vien', 'nguoi', 'tung', 'lam', 'tai', 'truong', 'dai', 'hoc', 'alumni', 'co', 'khong', 'ai', 'la', 'gi', 'cac'}
        best_title = None
        best_len = -1

        for _, data in self.reasoner.kg.G.nodes(data=True):
            if data.get('node_type') != node_type:
                continue
            title = data.get('title', '')
            norm_title = self._normalize_text(title)
            tokens = [t for t in norm_title.split() if t not in generic and len(t) >= 3]
            if not tokens:
                continue
            # match if all significant tokens appear in query
            if all(t in query_tokens for t in tokens):
                if len(norm_title) > best_len:
                    best_title = title
                    best_len = len(norm_title)
                continue
            # or full substring match
            if norm_title in norm_query and len(norm_title) > best_len:
                best_title = title
                best_len = len(norm_title)

        # Fallback: một số node country có node_type 'unknown' nhưng id dạng country_*
        if node_type == 'country' and not best_title:
            for _, data in self.reasoner.kg.G.nodes(data=True):
                title = data.get('title', '')
                if not title.lower().startswith('country_'):
                    continue
                norm_title = self._normalize_text(title)
                tokens = [t for t in norm_title.split() if t not in generic and len(t) >= 3]
                if tokens and all(t in query_tokens for t in tokens):
                    if len(norm_title) > best_len:
                        best_title = title
                        best_len = len(norm_title)
                elif norm_title in norm_query and len(norm_title) > best_len:
                    best_title = title
                    best_len = len(norm_title)

        # Heuristic aliases for phổ biến
        if not best_title and node_type == 'university':
            aliases = {
                'harvard': 'Đại học Harvard',
                'stanford': 'Đại học Stanford',
                'mit': 'Viện Công nghệ Massachusetts',
                'yale': 'Đại học Yale',
                'oxford': 'Đại học Oxford',
                'cambridge': 'Đại học Cambridge'
            }
            for key, title in aliases.items():
                if key in query_tokens:
                    return title
        if not best_title and node_type == 'country':
            country_aliases = {
                'trung quoc': 'country_Trung_Quoc',
                'viet nam': 'country_Viet_Nam',
                'hoa ky': 'country_Hoa_Ky',
                'my': 'country_Hoa_Ky'
            }
            for key, title in country_aliases.items():
                if all(tok in query_tokens for tok in key.split()):
                    return title

        return best_title
    
    def _format_node_detail(self, node_detail: Dict) -> str:
        """Định dạng thông tin chi tiết node từ node_details.json"""
        lines = []
        
        # Title
        title = node_detail.get('title', '')
        lines.append(f"📌 {title}")
        lines.append("=" * 60)
        
        # Type
        node_type = node_detail.get('type', '')
        if node_type:
            lines.append(f"Loại: {node_type}")
        
        # Link
        link = node_detail.get('link', '')
        if link:
            lines.append(f"Nguồn: {link}")
        
        # Properties
        properties = node_detail.get('properties', {})
        if properties and isinstance(properties, dict):
            lines.append("\n📋 Thông tin chi tiết:")
            for key, value in properties.items():
                if isinstance(value, list):
                    # Nếu là list, ghép thành chuỗi
                    val_str = ' '.join(str(v) for v in value if v)
                else:
                    val_str = str(value)
                lines.append(f"  • {key}: {val_str}")
        
        # Related nodes
        related = node_detail.get('related', [])
        if related:
            lines.append(f"\n🔗 Người liên quan: {', '.join(related)}")
        
        return "\n".join(lines)
    
    def _build_node_details_context(self, entities: List[str], max_properties: int = 10) -> str:
        """
        Xây dựng context từ node_details cho LLM
        Lấy chi tiết từng properties của entities để cung cấp info toàn diện hơn
        """
        if not entities:
            return ""
        
        import json
        details_parts = []
        
        for entity in entities[:5]:  # Giới hạn 5 entities để không quá dài
            node_detail = self.node_details.get(entity)
            if not node_detail:
                continue
            
            # Format simplified version for LLM
            entity_info = f"\n📌 {entity}:"
            
            # Type
            if node_detail.get('type'):
                entity_info += f"\n  Loại: {node_detail.get('type')}"
            
            # Properties - lấy từng cái chi tiết
            properties = node_detail.get('properties', {})
            if properties and isinstance(properties, dict):
                entity_info += "\n  Thông tin:"
                for key, value in list(properties.items())[:max_properties]:
                    if isinstance(value, list):
                        val_str = ' '.join(str(v) for v in value if v)
                    else:
                        val_str = str(value)
                    # Truncate dài quá
                    if len(val_str) > 150:
                        val_str = val_str[:150] + "..."
                    entity_info += f"\n    - {key}: {val_str}"
            
            # Related people
            related = node_detail.get('related', [])
            if related:
                entity_info += f"\n  Liên quan đến: {', '.join(related[:5])}"
            
            details_parts.append(entity_info)
        
        return "".join(details_parts) if details_parts else ""
    def _fallback_people_by_country_and_university(self, country_title: str, university_title: str, limit: int = 50):
        """
        Fallback khi đồ thị không đủ cạnh from_country/born_in và alumni_of.
        Dùng node_details.properties để suy ra người thuộc country + học university.
        ƯU TIÊN node_details hơn đồ thị.
        """
        norm_country = self._normalize_text(
            country_title.replace('country_', '').replace('_', ' ')
        )
        norm_uni = self._normalize_text(university_title)

        # Alias cơ bản cho country
        country_aliases = {
            'trung quoc': ['trung quoc', 'trung quốc', 'china', 'people s republic of china'],
            'viet nam': ['viet nam', 'vietnam'],
            'hoa ky': ['hoa ky', 'my', 'usa', 'united states', 'united states of america'],
        }
        country_keys = country_aliases.get(norm_country, [norm_country])

        people = []

        for title, detail in self.node_details.items():
            if len(people) >= limit:
                break
            if detail.get('type') != 'person':
                continue

            props = detail.get('properties', {})
            if not isinstance(props, dict):
                continue

            # Ghép mọi value thành một chuỗi rồi chuẩn hoá
            values = []
            for v in props.values():
                if isinstance(v, list):
                    values.append(' '.join(str(x) for x in v if x))
                else:
                    values.append(str(v))
            all_props_text = ' '.join(values)
            norm_props = self._normalize_text(all_props_text)

            # 1) Check country (Trung Quốc / China / …)
            if not any(ck in norm_props for ck in country_keys):
                continue

            # 2) Check university (Harvard, Stanford,…)
            if norm_uni not in norm_props:
                continue

            people.append(title)

        return people

    def _search_by_properties(self, query: str) -> Optional[Dict]:
        """
        Tìm kiếm từ node_details dựa trên keywords trong properties
        Hỗ trợ câu hỏi phức tạp như "Ai là Phó Tổng thống của Abdulrahman Wahid?"
        """
        query_lower = query.lower()
        
        # Patterns để nhận diện câu hỏi
        property_patterns = [
            ('phó tổng thống|pho tong thong|vice president', 'Phó Tổng thống'),
            ('tổng thống|tong thong|president', 'Tổng thống'),
            ('sinh|born|ngày sinh|date of birth', 'Sinh'),
            ('mất|died|ngày mất|date of death', 'Mất'),
            ('kế nhiệm|successor|ke niem', 'Kế nhiệm'),
            ('tiền nhiệm|predecessor|tien niem', 'Tiền nhiệm'),
            ('đảng|party|dang', 'Đảng chính trị'),
            ('alma mater|trường|học', 'Alma mater'),
        ]
        
        for pattern, prop_key in property_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                # Tìm entities trong query
                entities = self.reasoner._extract_entities(query)
                if not entities:
                    continue
                
                results = []
                for entity in entities[:3]:
                    node_detail = self.node_details.get(entity)
                    if node_detail:
                        properties = node_detail.get('properties', {})
                        if isinstance(properties, dict):
                            for key, value in properties.items():
                                # So khớp property key
                                if prop_key.lower() in key.lower():
                                    if isinstance(value, list):
                                        val_str = ' '.join(str(v) for v in value if v)
                                    else:
                                        val_str = str(value)
                                    results.append({
                                        'entity': entity,
                                        'property': key,
                                        'value': val_str
                                    })
                
                if results:
                    return {
                        'type': 'property_search',
                        'results': results,
                        'pattern': prop_key
                    }
        
        return None
    
    def _compare_alma_mater(self, entity1: str, entity2: str) -> Optional[str]:
        """
        So sánh alma mater của 2 người từ node_details
        Trả về "Có" nếu cùng trường, "Không" nếu khác hoặc không tìm thấy
        """
        detail1 = self.node_details.get(entity1)
        detail2 = self.node_details.get(entity2)
        
        if not detail1 or not detail2:
            return None
        
        props1 = detail1.get('properties', {})
        props2 = detail2.get('properties', {})
        
        if not isinstance(props1, dict) or not isinstance(props2, dict):
            return None
        
        # Lấy alma mater
        alma1 = props1.get('Alma mater', '')
        alma2 = props2.get('Alma mater', '')
        
        if not alma1 or not alma2:
            return None
        
        # Convert list to string nếu cần
        if isinstance(alma1, list):
            alma1 = ' '.join(str(v) for v in alma1 if v)
        if isinstance(alma2, list):
            alma2 = ' '.join(str(v) for v in alma2 if v)
        
        alma1_str = str(alma1).lower()
        alma2_str = str(alma2).lower()
        
        # Tìm trường chung
        # Extract tên trường từ alma mater string
        def extract_universities(alma_str: str):
            """Extract danh sách các trường từ alma mater string"""
            # Loại bỏ parenthesis content like "(BA)", "(JD)"
            cleaned = re.sub(r'\([^)]+\)', '', alma_str).strip()
            
            # Split bởi các dấu phân cách phổ biến
            parts = re.split(r'[;,\s{2,}]+', cleaned)  # Split by ; , hoặc nhiều space
            
            unis = []
            for part in parts:
                part = part.strip()
                if part and ('đại học' in part.lower() or 'university' in part.lower() or 
                             'institute' in part.lower() or 'college' in part.lower()):
                    # Bình thường hóa tên trường bằng cách loại bỏ dấu
                    import unicodedata
                    normalized = unicodedata.normalize('NFD', part.lower())
                    normalized = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
                    # Loại bỏ "đại học" prefix để so sánh đơn giản hơn
                    normalized = normalized.replace('đai hoc', '').replace('university', '').strip()
                    if normalized:
                        unis.append(normalized)
            return unis
        
        unis1 = extract_universities(alma1_str)
        unis2 = extract_universities(alma2_str)
        
        # Kiểm tra có trường chung không
        common = set(unis1) & set(unis2)
        
        if common:
            return "Có"
        else:
            return "Không"
    
    def _handle_multiple_choice(self, query: str, entities: List[str], norm_query: str) -> Dict:
        """Xử lý câu hỏi lựa chọn (multiple choice) - chỉ trả về đáp án"""
        import re
        import unicodedata
        
        # 1. Câu hỏi về COUNTRY
        if 'nước nào' in query.lower() or ('country' in query.lower() and 'quốc gia' in query.lower()):
            if entities:
                entity = entities[0]
                node_id = self.reasoner.kg.title_to_node.get(entity)
                if node_id:
                    # Tìm country từ edges
                    for neighbor in self.reasoner.kg.G.successors(node_id):
                        edge_data = self.reasoner.kg.G[node_id][neighbor]
                        rel = edge_data.get('relation', '')
                        if rel in ['from_country', 'born_in']:
                            country_title = self.reasoner.kg.node_to_title.get(neighbor, '')
                            country_name = country_title.replace('country_', '').replace('_', ' ')
                            
                            # Map country name to options
                            country_map = {
                                'Anh': ['Anh', 'Vương quốc Anh', 'UK', 'England'],
                                'Hoa Ky': ['Mỹ', 'Hoa Kỳ', 'USA', 'America'],
                                'Phap': ['Pháp', 'France'],
                                'Duc': ['Đức', 'Germany'],
                                'Y': ['Ý', 'Italy']
                            }
                            
                            # Find matching option in query
                            for std_name, variants in country_map.items():
                                if std_name.lower() in country_name.lower():
                                    for variant in variants:
                                        pattern = r'([A-D])\.\s*' + re.escape(variant)
                                        match = re.search(pattern, query, re.IGNORECASE)
                                        if match:
                                            option = match.group(1)
                                            return {
                                                'query': query,
                                                'type': 'multiple_choice',
                                                'context': '',
                                                'reasoning': None,
                                                'answer': f"Đáp án: {option}"
                                            }
        
        # 2. Câu hỏi về UNIVERSITY/ALMA MATER
        if any(kw in query.lower() for kw in ['đại học', 'trường', 'university', 'alma mater', 'cựu sinh viên']):
            if entities:
                entity = entities[0]
                # Tìm alma mater từ node_details
                node_detail = self.node_details.get(entity)
                if node_detail:
                    props = node_detail.get('properties', {})
                    
                    # Tìm trong nhiều properties có thể chứa thông tin trường học
                    education_info = ''
                    for key in ['Alma mater', 'alma mater', 'Trường lớp', 'Education', 'education', 'Học vấn']:
                        if key in props:
                            value = props[key]
                            if isinstance(value, list):
                                education_info += ' '.join(str(v) for v in value if v) + ' '
                            else:
                                education_info += str(value) + ' '
                    
                    if education_info:
                        education_str = education_info.lower()
                        
                        # Extract các options từ query
                        options = re.findall(r'([A-D])\.\s*([^A-D]+?)(?=[A-D]\.|$)', query, re.IGNORECASE)
                        
                        # Tìm option khớp với education info
                        for option_letter, option_text in options:
                            option_clean = option_text.strip().lower()
                            # Normalize for comparison
                            option_normalized = unicodedata.normalize('NFD', option_clean)
                            option_normalized = ''.join(ch for ch in option_normalized if unicodedata.category(ch) != 'Mn')
                            
                            edu_normalized = unicodedata.normalize('NFD', education_str)
                            edu_normalized = ''.join(ch for ch in edu_normalized if unicodedata.category(ch) != 'Mn')
                            
                            # Check if option appears in education info
                            # Tìm các từ chính trong option (bỏ "đại học", "university")
                            option_keywords = [w for w in option_normalized.split() if w not in ['dai', 'hoc', 'university', 'college'] and len(w) > 3]
                            
                            if option_normalized in edu_normalized or \
                               (option_keywords and all(kw in edu_normalized for kw in option_keywords)):
                                return {
                                    'query': query,
                                    'type': 'multiple_choice',
                                    'context': '',
                                    'reasoning': None,
                                    'answer': f"Đáp án: {option_letter}"
                                }
                
                # Fallback: tìm từ graph edges (alumni_of)
                node_id = self.reasoner.kg.title_to_node.get(entity)
                if node_id:
                    for neighbor in self.reasoner.kg.G.successors(node_id):
                        edge_data = self.reasoner.kg.G[node_id][neighbor]
                        rel = edge_data.get('relation', '')
                        if rel == 'alumni_of':
                            uni_title = self.reasoner.kg.node_to_title.get(neighbor, '')
                            
                            # Find matching option
                            options = re.findall(r'([A-D])\.\s*([^A-D]+?)(?=[A-D]\.|$)', query, re.IGNORECASE)
                            for option_letter, option_text in options:
                                option_clean = option_text.strip().lower()
                                uni_lower = uni_title.lower()
                                if option_clean in uni_lower or any(word in uni_lower for word in option_clean.split() if len(word) > 4):
                                    return {
                                        'query': query,
                                        'type': 'multiple_choice',
                                        'context': '',
                                        'reasoning': None,
                                        'answer': f"Đáp án: {option_letter}"
                                    }
        
        # 3. Fallback: KHÔNG TÌM THẤY TRONG DATA
        return {
            'query': query,
            'type': 'multiple_choice',
            'context': '',
            'reasoning': None,
            'answer': "Không tìm thấy thông tin chính xác trong dữ liệu để trả lời câu hỏi này."
        }
    
    def _handle_yes_no(self, query: str, query_type: str, entities: List[str], norm_query: str, replace_thankyou) -> Dict:
        """Xử lý câu hỏi Yes/No - luôn bắt đầu với Có/Không"""
        import re
        
        # Kiểm tra entities có tồn tại trong đồ thị không
        if entities:
            missing_entities = [e for e in entities if e not in self.reasoner.kg.title_to_node]
            if missing_entities and len(entities) > 0:
                if len(missing_entities) == len(entities):
                    return {
                        'query': query,
                        'type': 'entity_not_found',
                        'context': '',
                        'reasoning': None,
                        'answer': f"❌ Không tìm thấy các thực thể sau trong đồ thị: {', '.join(missing_entities)}"
                    }
                elif query_type in ['connection', 'university']:
                    return {
                        'query': query,
                        'type': 'partial_entity_found',
                        'context': '',
                        'reasoning': None,
                        'answer': f"⚠️ Cảnh báo: Không tìm thấy các thực thể sau trong đồ thị: {', '.join(missing_entities)}"
                    }
        
        # Xử lý câu hỏi về một người + trường
        if query_type == 'university' and len(entities) == 1:
            person = entities[0]
            uni_hint = None
            for title in self.reasoner.kg.title_to_node.keys():
                if self.reasoner.kg.G.nodes[self.reasoner.kg.title_to_node[title]].get('node_type') == 'university':
                    norm_title = self._normalize_text(title)
                    if norm_title in norm_query:
                        uni_hint = title
                        break
            
            uni_hit = None
            if not any(kw in norm_query for kw in ['nhung', 'nao']):
                uni_hit = uni_hint or self._find_node_by_type_in_query(norm_query, 'university')
            node_id = self.reasoner.kg.title_to_node.get(person)
            
            if node_id:
                alumni = set()
                # Lấy từ node_details.Alma mater
                detail = self.node_details.get(person)
                if detail:
                    props = detail.get('properties', {})
                    if isinstance(props, dict):
                        alma = props.get('Alma mater') or props.get('alma mater')
                        if alma:
                            if isinstance(alma, list):
                                alma_str = ' '.join(str(v) for v in alma if v)
                            else:
                                alma_str = str(alma)
                            parts = [p.strip() for p in re.split(r'[;,]', alma_str) if p.strip()]
                            if parts:
                                alumni |= set(parts)
                
                # Từ KG: alumni_of outbound
                if not alumni:
                    alumni |= {n['title'] for n in self.reasoner.kg.get_neighbors(node_id, 'alumni_of')}
                
                # Nếu câu hỏi hỏi danh sách
                if not uni_hit and any(kw in norm_query for kw in ['nhung', 'nao']):
                    if alumni:
                        answer_text = f"Có. {person} học tại các trường: {', '.join(sorted(alumni))}."
                    else:
                        answer_text = f"Không. Không tìm thấy thông tin trường học của {person}."
                elif uni_hit:
                    if any(self._normalize_text(uni_hit) in self._normalize_text(a) for a in alumni):
                        answer_text = f"Có. {person} học tại {uni_hit}."
                    else:
                        answer_text = f"Không. Không thấy {uni_hit} trong thông tin trường học của {person}."
                else:
                    if alumni:
                        answer_text = f"Có. {person} học tại: {', '.join(sorted(alumni))}."
                    else:
                        answer_text = f"Không. Không tìm thấy thông tin trường học của {person}."
                
                return {
                    'query': query,
                    'type': 'university_single_person',
                    'context': '',
                    'reasoning': None,
                    'answer': replace_thankyou(answer_text)
                }
        
        # Xử lý Yes/No thông thường
        if query_type == 'yes_no':
            if len(entities) >= 2:
                reasoning = self.reasoner.check_connection(entities[0], entities[1])
                if reasoning.get('missing_entities'):
                    answer_text = f"Không. Không tìm thấy: {', '.join(reasoning['missing_entities'])}"
                elif reasoning.get('connected'):
                    answer_text = "Có."
                    path_desc = reasoning.get('description') or reasoning.get('explanation', '')
                    if path_desc:
                        answer_text += f" {path_desc}"
                else:
                    answer_text = "Không."
                    reason = reasoning.get('reason', '')
                    if reason:
                        answer_text += f" {reason}"
            else:
                context = self.reasoner.retrieve_context(query)
                prompt = f"Trả lời Có/Không cho câu hỏi sau: {query}\nThông tin: {context[:300]}"
                answer_text = self.llm.generate(prompt, "", None, node_details_context="").strip()
                if answer_text.lower() not in ['có', 'không', 'yes', 'no', 'đúng', 'sai']:
                    answer_text = "Không thể xác định"
            
            return {
                'query': query,
                'type': 'yes_no',
                'context': '',
                'reasoning': reasoning if len(entities) >= 2 else None,
                'answer': replace_thankyou(answer_text)
            }
        
        # Xử lý connection
        if query_type == 'connection' and len(entities) >= 2:
            reasoning = self.reasoner.check_connection(entities[0], entities[1])
            if reasoning.get('missing_entities'):
                missing = reasoning['missing_entities']
                answer_text = f"Không. Không tìm thấy: {', '.join(missing)}"
            elif reasoning.get('connected'):
                hops = reasoning.get('hops', 0)
                explanation = reasoning.get('explanation', '')
                answer_text = f"Có. {explanation}"
            else:
                reason = reasoning.get('reason', '')
                answer_text = f"Không. {reason}"
            
            return {
                'query': query,
                'type': 'connection',
                'context': '',
                'reasoning': reasoning,
                'answer': replace_thankyou(answer_text)
            }
        
        # Xử lý university (2 người)
        if query_type == 'university' and len(entities) >= 2:
            alma_result = self._compare_alma_mater(entities[0], entities[1])
            if alma_result:
                if alma_result == "Có":
                    answer_text = f"Có. {entities[0]} và {entities[1]} cùng học một trường."
                else:
                    answer_text = f"Không. {entities[0]} và {entities[1]} không học cùng trường."
            else:
                reasoning = self.reasoner.check_same_university(entities[0], entities[1])
                if reasoning.get('missing_entities'):
                    missing = reasoning['missing_entities']
                    answer_text = f"Không. Không tìm thấy: {', '.join(missing)}"
                elif reasoning.get('same_university'):
                    answer_text = f"Có. {entities[0]} và {entities[1]} cùng học tại {reasoning['university']}."
                else:
                    answer_text = f"Không. {entities[0]} và {entities[1]} không học cùng trường."
            
            return {
                'query': query,
                'type': 'university',
                'context': '',
                'reasoning': None,
                'answer': replace_thankyou(answer_text)
            }
        
        # Fallback
        return {
            'query': query,
            'type': query_type,
            'context': '',
            'reasoning': None,
            'answer': "Không thể xác định câu trả lời."
        }


if __name__ == "__main__":
    import importlib
    
    KnowledgeGraph = importlib.import_module('1_knowledge_graph').KnowledgeGraph
    GraphRAGReasoner = importlib.import_module('2_graphrag_reasoner').GraphRAGReasoner
    
    kg = KnowledgeGraph('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')
    reasoner = GraphRAGReasoner(kg)
    chatbot = GraphRAGChatbot(kg, reasoner)
    
    # Test
    result = chatbot.answer("Barack Obama và Bill Clinton có kết nối không?")
    print(f"\n❓ {result['query']}")
    print(f"💬 {result['answer']}")
