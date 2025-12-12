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
    
    def extract_entities_and_intent(self, query: str) -> Dict:
        """
        LLM nhận diện thực thể và ý định từ câu hỏi
        Return: {entities: [], intent: 'relationship|comparison|property|general'}
        """
        if not self.ready:
            return {'entities': [], 'intent': 'general', 'filtered_query': query}
        
        prompt = f"""Phân tích câu hỏi sau và trích xuất:
1. Các thực thể (entity): tên người, trường học, quốc gia, v.v.
2. Ý định (intent): 
   - relationship: hỏi về mối quan hệ/kết nối
   - comparison: hỏi so sánh (cùng, khác)
   - property: hỏi về thuộc tính (là gì, có gì, ở đâu)
   - general: hỏi thông tin chung

Câu hỏi: "{query}"

Trả lời định dạng:
ENTITIES: [entity1, entity2, ...]
INTENT: relationship|comparison|property|general
"""
        
        import torch
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=128,
                temperature=0.1,
                top_p=0.9,
                do_sample=True
            )
        
        response = self.tokenizer.decode(output[0], skip_special_tokens=True)
        
        # Parse response
        entities = []
        intent = 'general'
        
        try:
            if "ENTITIES:" in response:
                ent_part = response.split("ENTITIES:")[-1].split("INTENT:")[0].strip()
                entities = [e.strip() for e in ent_part.strip('[]').split(',') if e.strip()]
            
            if "INTENT:" in response:
                intent_part = response.split("INTENT:")[-1].strip().lower()
                for intent_type in ['relationship', 'comparison', 'property', 'general']:
                    if intent_type in intent_part:
                        intent = intent_type
                        break
        except:
            pass
        
        import sys
        print(f"[LOG] LLM NER: entities={entities}, intent={intent}", file=sys.stderr, flush=True)
        
        return {'entities': entities, 'intent': intent, 'filtered_query': query}
    
    def classify_query(self, query: str) -> str:
        """
        LLM phân loại loại câu hỏi
        Return: 'yes_no' | 'multiple_choice' | 'property_query' | 'general'
        """
        if not self.ready:
            return 'general'
        
        prompt = f"""Phân loại câu hỏi sau thành một trong các loại:
- yes_no: câu hỏi có/không, hỏi có cùng (cùng trường, cùng nước)
- multiple_choice: có tùy chọn A, B, C, D
- property_query: hỏi về thuộc tính (là gì, có gì, ở đâu, bao nhiêu)
- general: hỏi thông tin chung

Câu hỏi: "{query}"

Loại: """
        
        import torch
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=256)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=32,
                temperature=0.1,
                top_p=0.9,
                do_sample=True
            )
        
        response = self.tokenizer.decode(output[0], skip_special_tokens=True).lower()
        
        if 'yes_no' in response or 'có/không' in response:
            return 'yes_no'
        elif 'multiple' in response or 'tùy chọn' in response:
            return 'multiple_choice'
        elif 'property' in response or 'thuộc tính' in response:
            return 'property_query'
        else:
            return 'general'
    
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
        print("=" * 70)
        
        # Khởi tạo LLM ngay lập tức thay vì lazy load
        print("⏳ Đang khởi tạo Qwen LLM...")
        self.llm = QwenLLM()
        print("✓ Qwen OWen3 LLM: Tạo câu trả lời thông minh")
        print("=" * 70)
    
    def answer(self, query: str) -> Dict:
        """
        KIẾN TRÚC GRAPHRAG:
        1. LLM nhận diện thực thể + ý định từ câu hỏi (NER + Intent)
        2. Lọc subgraph/node_details liên quan từ graph + DB
        3. LLM sinh response dựa trên dữ liệu đã lọc
        """
        import re
        import sys
        
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
        
        # ═══════════════════════════════════════════════════════════════
        # BƯỚC 1: NHẬN DIỆN THỰC THỂ (DÙNG REASONER - RULE-BASED)
        # ═══════════════════════════════════════════════════════════════
        
        norm_query = self._normalize_text(query)
        entities = self.reasoner._extract_entities(query)
        
        print(f"[LOG] Entities extracted: {entities}", file=sys.stderr, flush=True)
        
        # ═══════════════════════════════════════════════════════════════
        # BƯỚC 2: PHÂN LOẠI LOẠI CÂU HỎI (RULE-BASED)
        # ═══════════════════════════════════════════════════════════════
        
        is_multiple_choice = bool(re.search(r'\b[A-D]\.\s*', query))
        query_type = self._classify_query(query)
        print(f"[LOG] Query type: {query_type}", file=sys.stderr, flush=True)
        
        # ═══════════════════════════════════════════════════════════════
        # BƯỚC 3: LỌC SUBGRAPH + NODE_DETAILS LIÊN QUAN
        # ═══════════════════════════════════════════════════════════════
        
        # Lọc thông tin từ graph dựa trên entities được nhận diện
        context_info = ""
        for entity in entities:
            node_id = self.reasoner.kg.title_to_node.get(entity)
            if node_id:
                # Lấy neighbors (liên kết trong graph)
                neighbors = list(self.reasoner.kg.G.neighbors(node_id))[:5]  # Limit 5
                relations = [self.reasoner.kg.G[node_id][nbr].get('relation', 'link') for nbr in neighbors]
                neighbor_names = [self.reasoner.kg.node_to_title.get(nbr, nbr) for nbr in neighbors]
                
                context_info += f"\n{entity} có liên kết với: "
                context_info += ", ".join([f"{name} (cạnh: {rel})" for name, rel in zip(neighbor_names, relations)])
        
        # Lấy thông tin chi tiết từ node_details
        node_details_context = ""
        for entity in entities:
            if entity in self.node_details:
                detail = self.node_details[entity]
                desc = detail.get('description', '')[:200]  # Lấy 200 ký tự đầu
                props = detail.get('properties', {})
                
                if isinstance(props, dict):
                    props_str = "; ".join([f"{k}: {str(v)[:50]}" for k, v in list(props.items())[:3]])  # 3 properties
                else:
                    props_str = ""
                
                node_details_context += f"\n{entity}: {desc}"
                if props_str:
                    node_details_context += f"\nThuộc tính: {props_str}"
        
        print(f"[LOG] Filtered context: {context_info[:100]}... | details: {node_details_context[:100]}...", file=sys.stderr, flush=True)
        
        # ═══════════════════════════════════════════════════════════════
        # BƯỚC 4: XỬ LÝ THEO LOẠI CÂU HỎI
        # ═══════════════════════════════════════════════════════════════
        
        # LOẠI 1: MULTIPLE CHOICE - Sử dụng LLM để chọn đáp án
        if is_multiple_choice:
            print(f"[LOG] Handling multiple choice question", file=sys.stderr, flush=True)
            reasoning = None
            answer_text = self.llm.generate(
                query, 
                context_info, 
                reasoning, 
                max_tokens=64,
                node_details_context=node_details_context
            )
            return {
                'query': query,
                'type': 'multiple_choice',
                'context': context_info[:200],
                'reasoning': reasoning,
                'answer': replace_thankyou(answer_text)
            }
        
        # LOẠI 2: YES/NO - Sử dụng _handle_yes_no với logic đặc biệt
        # Chỉ xử lý yes/no khi không phải câu hỏi liệt kê/danh sách
        aggregate_list_trigger = any(kw in norm_query for kw in ['liet ke', 'liệt kê', 'danh sach', 'danh sách', 'nhung', 'những', 'ai', 'ke', 'sinh vien', 'cuu sinh vien'])
        if query_type in ['yes_no', 'connection', 'birth_place', 'profession'] or (query_type == 'university' and not aggregate_list_trigger):
            print(f"[LOG] Handling yes/no question (type: {query_type})", file=sys.stderr, flush=True)
            return self._handle_yes_no(query, query_type, entities, norm_query, replace_thankyou)
        
        # LOẠI 3: PROPERTY QUERY - Lấy thuộc tính từ node_details + LLM sinh lời trả lời
        if query_type == 'property_query' and len(entities) == 1:
            print(f"[LOG] Handling property query for {entities[0]}", file=sys.stderr, flush=True)
            answer_text = self.llm.generate(
                query,
                context_info,
                None,
                max_tokens=128,
                node_details_context=node_details_context
            )
            return {
                'query': query,
                'type': 'property_query',
                'context': '',
                'reasoning': None,
                'answer': replace_thankyou(answer_text)
            }

        # LOẠI 3b: AGGREGATE - Liệt kê cựu sinh viên của một trường (ví dụ: "liệt kê sinh viên Harvard")
        # Ưu tiên dữ liệu đồ thị thay vì gọi LLM để tránh bịa.
        aggregate_list_trigger = any(kw in norm_query for kw in ['liet ke', 'danh sach', 'nhung', 'những', 'ai', 'ke', 'liệt kê', 'sinh vien', 'cuu sinh vien'])
        if aggregate_list_trigger or query_type == 'university':
            # Tìm tên trường trong câu hỏi
            uni_hit = self._find_node_by_type_in_query(norm_query, 'university')
            # Heuristic: nếu người dùng chỉ nói "Harvard" thì map về "Đại học Harvard"
            if not uni_hit and ('harvard' in norm_query):
                uni_hit = 'Đại học Harvard'
            # Nếu câu hỏi có cả country và university: ưu tiên truy vấn kết hợp
            country_hit = self._find_node_by_type_in_query(norm_query, 'country')
            if not country_hit and any(tok in norm_query for tok in ['trung quoc','trung quốc','china']):
                country_hit = 'country_Trung_Quoc'
            if uni_hit and country_hit and len(entities) == 0:
                print(f"[LOG] Handling aggregate country+university: {country_hit} + {uni_hit}", file=sys.stderr, flush=True)
                agg = self.reasoner.find_people_by_country_and_university(country_hit, uni_hit, limit=200)
                if agg.get('missing'):
                    return {
                        'query': query,
                        'type': 'aggregate_country_university_alumni',
                        'context': '',
                        'reasoning': None,
                        'answer': f"❌ Không tìm thấy node: {', '.join(agg['missing'])}"
                    }
                people = agg.get('people', [])
                if people:
                    unique_people = sorted(list(dict.fromkeys(people)))
                    show = unique_people[:50]
                    more = len(unique_people) - len(show)
                    extra_note = f" (và {more} người khác)" if more > 0 else ""
                    return {
                        'query': query,
                        'type': 'aggregate_country_university_alumni',
                        'context': '',
                        'reasoning': None,
                        'answer': f"Các cựu sinh viên từ {country_hit} học tại {uni_hit}:\n- " + "\n- ".join(show) + extra_note
                    }
                else:
                    return {
                        'query': query,
                        'type': 'aggregate_country_university_alumni',
                        'context': '',
                        'reasoning': None,
                        'answer': f"Không tìm thấy cựu sinh viên từ {country_hit} học {uni_hit} trong đồ thị."
                    }
            if uni_hit and len(entities) == 0:
                print(f"[LOG] Handling aggregate university alumni for {uni_hit}", file=sys.stderr, flush=True)
                agg = self.reasoner.find_people_by_university(uni_hit, limit=200)
                if agg.get('missing'):
                    return {
                        'query': query,
                        'type': 'aggregate_university_alumni',
                        'context': '',
                        'reasoning': None,
                        'answer': f"❌ Không tìm thấy node trường: {', '.join(agg['missing'])}"
                    }
                people = agg.get('people', [])
                if people:
                    # Loại trùng và sắp xếp
                    unique_people = sorted(list(dict.fromkeys(people)))
                    # Giới hạn hiển thị để tránh quá dài
                    show = unique_people[:50]
                    more = len(unique_people) - len(show)
                    extra_note = f" (và {more} người khác)" if more > 0 else ""
                    return {
                        'query': query,
                        'type': 'aggregate_university_alumni',
                        'context': '',
                        'reasoning': None,
                        'answer': f"Dưới đây là danh sách các cựu sinh viên của {uni_hit}:\n- " + "\n- ".join(show) + extra_note
                    }
                else:
                    return {
                        'query': query,
                        'type': 'aggregate_university_alumni',
                        'context': '',
                        'reasoning': None,
                        'answer': f"Không tìm thấy cựu sinh viên của {uni_hit} trong đồ thị."
                    }
        
        # LOẠI 4: AGGREGATE WITH COUNTRY/UNIVERSITY - Ưu tiên dữ liệu đồ thị
        reasoning = None
        answer_text = None
        country_hit = self._find_node_by_type_in_query(norm_query, 'country')
        uni_hit = self._find_node_by_type_in_query(norm_query, 'university')
        aggregate_trigger = any(kw in norm_query for kw in [
            'cuu sinh vien', 'alumni', 'hoc tai', 'hoc o', 'tung hoc', 'hoc tai harvard', 'hoc tai', 'hoc tai ', 'học tại', 'cựu sinh viên', 'sinh vien', 'liet ke', 'liệt kê', 'danh sach', 'danh sách'
        ])

        # Country + University: ví dụ "đến từ Trung Quốc mà học Harvard"
        if aggregate_trigger and country_hit and uni_hit:
            print(f"[LOG] Handling aggregate country+university: {country_hit} & {uni_hit}", file=sys.stderr, flush=True)
            agg = self.reasoner.find_people_by_country_and_university(country_hit, uni_hit, limit=50)
            if agg.get('missing'):
                answer_text = f"❌ Không tìm thấy node: {', '.join(agg['missing'])}"
            elif agg['people']:
                # loại trùng, sắp xếp, giới hạn hiển thị
                unique_people = sorted(list(dict.fromkeys(agg['people'])))
                show = unique_people[:50]
                more = len(unique_people) - len(show)
                extra_note = f" (và {more} người khác)" if more > 0 else ""
                answer_text = f"Các cựu sinh viên từ {country_hit} học tại {uni_hit}:\n- " + "\n- ".join(show) + extra_note
            else:
                # Fallback: nếu đồ thị không có kết quả, thử node_details nếu hàm tồn tại
                try:
                    fallback_people = self._fallback_people_by_country_and_university(country_hit, uni_hit, limit=50)
                except Exception:
                    fallback_people = []
                if fallback_people:
                    unique_people = sorted(list(dict.fromkeys(fallback_people)))
                    answer_text = (
                        f"Các cựu sinh viên từ {country_hit} học tại {uni_hit} (suy ra từ node_details): "
                        f"{', '.join(unique_people)}"
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

        # Chỉ university: liệt kê cựu sinh viên của trường
        if (aggregate_trigger or query_type == 'university') and uni_hit and not country_hit:
            print(f"[LOG] Handling aggregate university alumni for {uni_hit}", file=sys.stderr, flush=True)
            agg = self.reasoner.find_people_by_university(uni_hit, limit=100)
            if agg.get('missing'):
                answer_text = f"❌ Không tìm thấy node: {', '.join(agg['missing'])}"
            elif agg['people']:
                unique_people = sorted(list(dict.fromkeys(agg['people'])))
                show = unique_people[:50]
                more = len(unique_people) - len(show)
                extra_note = f" (và {more} người khác)" if more > 0 else ""
                answer_text = f"Dưới đây là danh sách các cựu sinh viên của {uni_hit}:\n- " + "\n- ".join(show) + extra_note
            else:
                answer_text = f"Không tìm thấy cựu sinh viên của {uni_hit} trong đồ thị."
            return {
                'query': query,
                'type': 'aggregate_alumni_university',
                'context': '',
                'reasoning': None,
                'answer': replace_thankyou(answer_text)
            }

        # Chỉ country: liệt kê người đến từ một quốc gia
        if aggregate_trigger and country_hit and not uni_hit:
            print(f"[LOG] Handling aggregate country people for {country_hit}", file=sys.stderr, flush=True)
            agg = self.reasoner.find_people_by_country(country_hit, limit=100)
            if agg.get('missing'):
                answer_text = f"❌ Không tìm thấy node: {', '.join(agg['missing'])}"
            elif agg['people']:
                unique_people = sorted(list(dict.fromkeys(agg['people'])))
                show = unique_people[:50]
                more = len(unique_people) - len(show)
                extra_note = f" (và {more} người khác)" if more > 0 else ""
                answer_text = f"Dưới đây là danh sách những người đến từ {country_hit}:\n- " + "\n- ".join(show) + extra_note
            else:
                answer_text = f"Không tìm thấy người đến từ {country_hit} trong đồ thị."
            return {
                'query': query,
                'type': 'aggregate_people_country',
                'context': '',
                'reasoning': None,
                'answer': replace_thankyou(answer_text)
            }

        # LOẠI 5: GENERAL - LLM sinh response từ filtered context
        print(f"[LOG] Handling general question with LLM", file=sys.stderr, flush=True)
        answer_text = self.llm.generate(
            query,
            context_info,
            None,
            max_tokens=256,
            node_details_context=node_details_context
        )
        return {
            'query': query,
            'type': 'general',
            'context': context_info[:200],
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

        # Xử lý câu hỏi về nơi sinh của một người
        if any(kw in norm_query for kw in ['sinh', 'nơi sinh', 'sinh ra', 'sinh ở', 'từ đâu']) and len(entities) == 1:
            person = entities[0]
            node_detail = self.node_details.get(person)
            
            if node_detail:
                props = node_detail.get('properties', {})
                if isinstance(props, dict):
                    # Tìm thông tin "Sinh" trong properties
                    birth_info = props.get('Sinh', '') or props.get('sinh', '')
                    if birth_info:
                        # Xử lý string - nó có dạng "Name Date Place"
                        # Ví dụ: "Elon Reeve Musk 28 tháng 6, 1971 (54 tuổi) Pretoria , Transvaal , Nam Phi"
                        if isinstance(birth_info, list):
                            birth_info = ' '.join(str(v) for v in birth_info if v)
                        
                        # Cắt phần nơi sinh - thường ở sau ngày tháng năm
                        # Tìm từ các ký tự số cuối cùng (tuổi) hoặc năm sinh
                        birth_str = str(birth_info)
                        # Tìm chuỗi chứa địa chỉ (thường có dấu phẩy hoặc quốc gia)
                        # Cách đơn giản: lấy từ sau năm sinh hoặc (tuổi)
                        import re
                        # Pattern: (XX tuổi) và lấy phần sau
                        match = re.search(r'\(\d+\s+tuổi\)\s*(.+?)(?:\s+[a-z]+)?$', birth_str, re.IGNORECASE)
                        if match:
                            location = match.group(1).strip()
                            answer_text = f"{person} sinh ra ở {location}."
                        else:
                            # Fallback: lấy tất cả sau năm sinh
                            year_match = re.search(r'(\d{4})\s*(.+?)(?:\s+[a-z]{2,})?$', birth_str, re.IGNORECASE)
                            if year_match:
                                location = year_match.group(2).strip()
                                if location:
                                    answer_text = f"{person} sinh ra ở {location}."
                                else:
                                    answer_text = f"Không tìm thấy thông tin nơi sinh của {person}."
                            else:
                                answer_text = f"Không tìm thấy thông tin nơi sinh của {person}."
                        
                        return {
                            'query': query,
                            'type': 'birthplace_single',
                            'context': '',
                            'reasoning': None,
                            'answer': replace_thankyou(answer_text)
                        }
            
            # Nếu không có trong node_details, thử lấy từ graph
            node_id = self.reasoner.kg.title_to_node.get(person)
            if node_id:
                birth_rels = {'from_country', 'born_in', 'birth_place'}
                countries = set()
                
                for nbr in self.reasoner.kg.G.successors(node_id):
                    if self.reasoner.kg.G[node_id][nbr].get('relation') in birth_rels:
                        country_name = self.reasoner.kg.node_to_title.get(nbr, nbr)
                        country_name = country_name.replace('country_', '').replace('_', ' ')
                        countries.add(country_name)
                for nbr in self.reasoner.kg.G.predecessors(node_id):
                    if self.reasoner.kg.G[nbr][node_id].get('relation') in birth_rels:
                        country_name = self.reasoner.kg.node_to_title.get(nbr, nbr)
                        country_name = country_name.replace('country_', '').replace('_', ' ')
                        countries.add(country_name)
                
                if countries:
                    answer_text = f"{person} sinh ra ở {', '.join(sorted(countries))}."
                else:
                    answer_text = f"Không tìm thấy thông tin nơi sinh của {person}."
                
                return {
                    'query': query,
                    'type': 'birthplace_single',
                    'context': '',
                    'reasoning': None,
                    'answer': replace_thankyou(answer_text)
                }
        
        # Xử lý câu hỏi về quốc gia của trường học
        if any(kw in norm_query for kw in ['quốc gia', 'nước', 'ở đâu', 'ở']) and len(entities) >= 1:
            entity = entities[0]
            node_id = self.reasoner.kg.title_to_node.get(entity)
            
            # Kiểm tra xem có phải là trường học không
            is_university = False
            if node_id:
                node_type = self.reasoner.kg.G.nodes[node_id].get('node_type', '').lower()
                is_university = 'university' in node_type or 'trường' in entity.lower()
            
            if is_university and node_id:
                # Tìm quốc gia từ graph edges
                countries = set()
                for nbr in self.reasoner.kg.G.successors(node_id):
                    rel = self.reasoner.kg.G[node_id][nbr].get('relation', '')
                    if rel in ['located_in', 'from_country', 'in_country', 'country']:
                        country_name = self.reasoner.kg.node_to_title.get(nbr, nbr)
                        country_name = country_name.replace('country_', '').replace('_', ' ')
                        countries.add(country_name)
                for nbr in self.reasoner.kg.G.predecessors(node_id):
                    rel = self.reasoner.kg.G[nbr][node_id].get('relation', '')
                    if rel in ['located_in', 'from_country', 'in_country', 'country']:
                        country_name = self.reasoner.kg.node_to_title.get(nbr, nbr)
                        country_name = country_name.replace('country_', '').replace('_', ' ')
                        countries.add(country_name)
                
                if countries:
                    answer_text = f"{entity} ở {', '.join(sorted(countries))}."
                else:
                    # Fallback: dùng LLM lọc từ node_details
                    node_detail = self.node_details.get(entity)
                    if node_detail:
                        props = node_detail.get('properties', {})
                        if isinstance(props, dict):
                            # Tìm các properties liên quan đến quốc gia
                            location_info = []
                            for key in ['Quốc gia', 'Đất nước', 'Vị trí', 'Địa điểm', 'Nước', 'Location', 'Country']:
                                if key in props:
                                    location_info.append(str(props[key]))
                            if location_info:
                                answer_text = f"{entity} ở {'; '.join(location_info)}."
                            else:
                                answer_text = f"Không tìm thấy thông tin quốc gia/vị trí của {entity}."
                        else:
                            answer_text = f"Không tìm thấy thông tin quốc gia/vị trí của {entity}."
                    else:
                        answer_text = f"Không tìm thấy thông tin quốc gia/vị trí của {entity}."
                
                return {
                    'query': query,
                    'type': 'location_query',
                    'context': '',
                    'reasoning': None,
                    'answer': replace_thankyou(answer_text)
                }
        
        # Xử lý câu hỏi về thuộc tính của một người (nghề nghiệp, chức vụ, v.v.)
        if any(kw in norm_query for kw in ['có gì', 'là gì', 'nghề nghiệp', 'công việc', 'chức vụ', 'tư cách', 'học vấn']) and len(entities) == 1:
            entity = entities[0]
            node_detail = self.node_details.get(entity)
            
            if node_detail:
                props = node_detail.get('properties', {})
                if isinstance(props, dict):
                    # Xác định loại thuộc tính cần lấy
                    target_keys = []
                    if any(kw in norm_query for kw in ['nghề', 'công việc', 'làm']):
                        target_keys = ['Nghề nghiệp', 'Công việc', 'Career', 'Profession', 'Nghề']
                    elif any(kw in norm_query for kw in ['chức vụ', 'vị trí', 'vai trò']):
                        target_keys = ['Chức vụ', 'Vị trí', 'Position', 'Title', 'Role', 'Vai trò']
                    elif any(kw in norm_query for kw in ['học vấn', 'bằng', 'độ']):
                        target_keys = ['Học vị', 'Bằng cấp', 'Education', 'Degree', 'Alma mater']
                    elif any(kw in norm_query for kw in ['tư cách', 'công dân']):
                        target_keys = ['Tư cách công dân', 'Quốc tịch', 'Citizenship', 'Nationality']
                    else:
                        target_keys = list(props.keys())
                    
                    # Tìm thông tin
                    found_info = None
                    for key in target_keys:
                        if key in props:
                            found_info = props[key]
                            break
                    
                    if found_info:
                        # Cắt ngắn nếu quá dài (> 500 ký tự)
                        if isinstance(found_info, list):
                            found_info = '\n• '.join(str(v) for v in found_info if v)
                        
                        answer_text = f"{entity}: {found_info}"
                        if len(answer_text) > 500:
                            answer_text = answer_text[:500] + "..."
                    else:
                        answer_text = f"Không tìm thấy thông tin về {norm_query.split()[-1]} của {entity}."
                    
                    return {
                        'query': query,
                        'type': 'property_query',
                        'context': '',
                        'reasoning': None,
                        'answer': replace_thankyou(answer_text)
                    }
        
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
        # Chuẩn hóa khoảng trắng
        query_normalized = ' '.join(query_lower.split())
        
        # Câu hỏi liệt kê/danh sách
        if any(w in query_normalized for w in ['liệt kê', 'liet ke', 'danh sách', 'danh sach']):
            return 'list'
        
        # Trắc nghiệm lựa chọn (multiple choice)
        if re.search(r'\b[A-D]\.', query_lower) or re.search(r'\b[a-d]\.', query_lower):
            return 'multiple_choice'
        
        # Câu hỏi về nơi sinh
        if any(w in query_normalized for w in ['nơi sinh', 'sinh ở', 'sinh tại', 'cùng nơi sinh', 'cùng sinh', 'từ đâu', 'quê quán', 'quê']):
            return 'birth_place'
        
        # Câu hỏi so sánh việc làm/nghề nghiệp
        if any(w in query_normalized for w in ['cùng việc làm', 'cùng công việc', 'cùng nghề', 'cùng nghề nghiệp', 'cùng tư cách', 'cùng chức vụ']):
            return 'profession'
        
        if any(w in query_normalized for w in ['kết nối', 'liên kết', 'quan hệ', 'có mối', 'được kết nối']):
            return 'connection'
        elif any(w in query_normalized for w in ['trường', 'đại học', 'cùng trường', 'cùng học', 'cùng đại học', 'học ', 'hoc ', 'alumni', 'học tại', 'hoc tai']):
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
        # Thay thế thủ công các ký tự tiếng Việt để tránh mất chữ Đ/đ
        replacements = {
            'đ': 'd', 'Đ': 'D',
            'ă': 'a', 'Ă': 'A',
            'â': 'a', 'Â': 'A',
            'ê': 'e', 'Ê': 'E',
            'ô': 'o', 'Ô': 'O',
            'ơ': 'o', 'Ơ': 'O',
            'ư': 'u', 'Ư': 'U'
        }
        for vn_char, latin_char in replacements.items():
            text = text.replace(vn_char, latin_char)

        s = unicodedata.normalize('NFD', text)
        s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
        s = s.lower().replace('_', ' ').replace('-', ' ')
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        return " ".join(s.split())

    def _find_node_by_type_in_query(self, norm_query: str, node_type: str) -> Optional[str]:
        """Tìm node theo loại nếu tiêu đề xuất hiện trong câu hỏi (lỏng)"""
        query_tokens = set(norm_query.split())
        generic = {'country', 'dai', 'hoc', 'university', 'truong', 'o', 'dau', 'nao', 'nhung', 'sinh', 'vien', 'nguoi', 'tung', 'lam', 'tai', 'truong', 'dai', 'hoc', 'alumni', 'co', 'khong', 'ai', 'la', 'gi', 'cac', 'liet', 'ke', 'danh', 'sach', 'den'}
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

        # Direct fallback for country: try hard-coded country name matching
        if node_type == 'country' and not best_title:
            country_mapping = {
                'trung quoc': 'country_Trung_Quoc',
                'trung quoc': 'Trung Quốc',
                'viet nam': 'country_Viet_Nam',
                'hoa ky': 'country_Hoa_Ky',
                'my': 'country_Hoa_Ky',
                'anh': 'country_Anh',
                'phap': 'country_Phap',
                'duc': 'country_Duc',
            }
            for query_keyword, node_title_or_id in country_mapping.items():
                if query_keyword in norm_query:
                    # Check if this node exists in graph
                    for node_id, node_data in self.reasoner.kg.G.nodes(data=True):
                        candidate_title = node_data.get('title', '')
                        if candidate_title == node_title_or_id or candidate_title.lower() == node_title_or_id.lower() or node_id == node_title_or_id:
                            return candidate_title
                    # If exact not found, return the mapped value anyway
                    return node_title_or_id

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
        
        # Trường hợp hỏi 2 người có học cùng trường không -> dùng graph trực tiếp
        if query_type == 'university' and len(entities) == 2:
            person1, person2 = entities[0], entities[1]
            result = self.reasoner.check_same_university(person1, person2)
            if result.get('answer') == 'CÓ':
                msg = result.get('description', f"{person1} và {person2} cùng học tại một số trường")
                answer_text = f"CÓ. {msg}"
            else:
                msg = result.get('description', f"{person1} và {person2} không học cùng trường")
                answer_text = f"KHÔNG. {msg}"
            return {
                'query': query,
                'type': query_type,
                'context': '',
                'reasoning': result,
                'answer': replace_thankyou(answer_text)
            }

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
        
        # Xử lý câu hỏi so sánh việc làm/nghề nghiệp giữa 2 người
        if query_type == 'profession' and len(entities) == 2:
            person1, person2 = entities[0], entities[1]
            
            # Kiểm tra xem cả hai entity có tồn tại trong node_details không
            prof1 = None
            prof2 = None
            
            # Lấy thông tin nghề nghiệp của người thứ nhất
            detail1 = self.node_details.get(person1)
            if detail1:
                props1 = detail1.get('properties', {})
                if isinstance(props1, dict):
                    # Tìm các khóa liên quan đến nghề
                    for key in ['Nghề nghiệp', 'Công việc', 'Career', 'Profession', 'Nghề', 'Chức vụ', 'Position']:
                        if key in props1:
                            prof1 = props1[key]
                            break
            
            # Lấy thông tin nghề nghiệp của người thứ hai
            detail2 = self.node_details.get(person2)
            if detail2:
                props2 = detail2.get('properties', {})
                if isinstance(props2, dict):
                    for key in ['Nghề nghiệp', 'Công việc', 'Career', 'Profession', 'Nghề', 'Chức vụ', 'Position']:
                        if key in props2:
                            prof2 = props2[key]
                            break
            
            # So sánh kết quả
            if prof1 and prof2:
                # Chuyển đổi danh sách thành string để so sánh
                prof1_str = str(prof1).lower() if prof1 else ""
                prof2_str = str(prof2).lower() if prof2 else ""
                
                # Kiểm tra xem có cùng nghề không
                same_profession = False
                if prof1_str and prof2_str:
                    # Nếu là danh sách, chuyển thành string
                    if isinstance(prof1, list):
                        prof1_str = ' '.join(str(x).lower() for x in prof1 if x)
                    if isinstance(prof2, list):
                        prof2_str = ' '.join(str(x).lower() for x in prof2 if x)
                    
                    # So sánh: nếu có từ chung nào thì coi là cùng nghề
                    prof1_words = set(prof1_str.split())
                    prof2_words = set(prof2_str.split())
                    common = prof1_words.intersection(prof2_words)
                    
                    # Bỏ các từ quá ngắn
                    common = {w for w in common if len(w) > 3}
                    
                    same_profession = len(common) > 0
                    
                    if same_profession:
                        answer_text = f"Có. {person1}: {prof1}; {person2}: {prof2}"
                    else:
                        answer_text = f"Không. {person1}: {prof1}; {person2}: {prof2}"
                else:
                    answer_text = f"Không thể xác định. {person1}: {prof1}; {person2}: {prof2}"
            else:
                # Nếu không tìm thấy thông tin nghề của ít nhất một người
                missing_info = []
                if not prof1:
                    missing_info.append(f"{person1}")
                if not prof2:
                    missing_info.append(f"{person2}")
                
                answer_text = f"Không thể xác định. Không tìm thấy thông tin nghề nghiệp của: {', '.join(missing_info)}"
            
            return {
                'query': query,
                'type': 'profession',
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
        
        # Xử lý birth_place (2 người)
        if query_type == 'birth_place' and len(entities) >= 2:
            node1 = self.reasoner.kg.title_to_node.get(entities[0])
            node2 = self.reasoner.kg.title_to_node.get(entities[1])
            
            birth_rels = {'from_country', 'born_in'}
            countries1, countries2 = set(), set()
            
            # Lấy quốc gia/nơi sinh của người thứ nhất
            if node1:
                for nbr in self.reasoner.kg.G.successors(node1):
                    if self.reasoner.kg.G[node1][nbr].get('relation') in birth_rels:
                        country_name = self.reasoner.kg.node_to_title.get(nbr, nbr)
                        country_name = country_name.replace('country_', '').replace('_', ' ')
                        countries1.add(country_name)
                for nbr in self.reasoner.kg.G.predecessors(node1):
                    if self.reasoner.kg.G[nbr][node1].get('relation') in birth_rels:
                        country_name = self.reasoner.kg.node_to_title.get(nbr, nbr)
                        country_name = country_name.replace('country_', '').replace('_', ' ')
                        countries1.add(country_name)
            
            # Lấy quốc gia/nơi sinh của người thứ hai
            if node2:
                for nbr in self.reasoner.kg.G.successors(node2):
                    if self.reasoner.kg.G[node2][nbr].get('relation') in birth_rels:
                        country_name = self.reasoner.kg.node_to_title.get(nbr, nbr)
                        country_name = country_name.replace('country_', '').replace('_', ' ')
                        countries2.add(country_name)
                for nbr in self.reasoner.kg.G.predecessors(node2):
                    if self.reasoner.kg.G[nbr][node2].get('relation') in birth_rels:
                        country_name = self.reasoner.kg.node_to_title.get(nbr, nbr)
                        country_name = country_name.replace('country_', '').replace('_', ' ')
                        countries2.add(country_name)
            
            # So sánh
            common_countries = countries1 & countries2
            if common_countries:
                answer_text = f"Có. {entities[0]} và {entities[1]} cùng sinh tại {', '.join(sorted(common_countries))}."
            else:
                # Không cùng nơi sinh - liệt kê nơi sinh của mỗi người
                parts = []
                if countries1:
                    parts.append(f"{entities[0]} sinh tại {', '.join(sorted(countries1))}")
                if countries2:
                    parts.append(f"{entities[1]} sinh tại {', '.join(sorted(countries2))}")
                
                if parts:
                    answer_text = "Không. " + "; ".join(parts) + "."
                else:
                    answer_text = "Không. Không tìm thấy thông tin nơi sinh của cả hai."
            
            return {
                'query': query,
                'type': 'birth_place',
                'context': '',
                'reasoning': None,
                'answer': replace_thankyou(answer_text)
            }
        
        # Xử lý connection
        if query_type == 'connection' and len(entities) >= 2:
            # Kiểm tra xem có hỏi về loại kết nối cụ thể không (có từ "nào", "gì")
            ask_what_connection = any(kw in query.lower() for kw in ['nào', 'gì', 'loại nào', 'quan hệ nào', 'mối quan hệ nào'])
            
            reasoning = self.reasoner.check_connection(entities[0], entities[1])
            if reasoning.get('missing_entities'):
                missing = reasoning['missing_entities']
                answer_text = f"Không. Không tìm thấy: {', '.join(missing)}"
            elif reasoning.get('connected'):
                hops = reasoning.get('hops', 0)
                path = reasoning.get('path', [])
                
                # Nếu hỏi "kết nối nào?" thì liệt kê các cạnh/quan hệ
                if ask_what_connection:
                    node1 = self.reasoner.kg.title_to_node.get(entities[0])
                    node2 = self.reasoner.kg.title_to_node.get(entities[1])
                    
                    relations = []
                    relation_names = set()
                    # Kiểm tra cạnh trực tiếp cả 2 chiều
                    if node1 and node2:
                        if self.reasoner.kg.G.has_edge(node1, node2):
                            rel = self.reasoner.kg.G[node1][node2].get('relation', 'connected')
                            relation_names.add(rel)
                            relations.append(f"{entities[0]} --[{rel}]--> {entities[1]}")
                        if self.reasoner.kg.G.has_edge(node2, node1):
                            rel = self.reasoner.kg.G[node2][node1].get('relation', 'connected')
                            relation_names.add(rel)
                            relations.append(f"{entities[1]} --[{rel}]--> {entities[0]}")

                    # Nếu có quan hệ same_birth_country, cố gắng nêu tên quốc gia
                    birth_rels = {'from_country', 'born_in'}
                    countries1, countries2 = set(), set()
                    if node1:
                        for nbr in self.reasoner.kg.G.successors(node1):
                            if self.reasoner.kg.G[node1][nbr].get('relation') in birth_rels:
                                countries1.add(self.reasoner.kg.node_to_title.get(nbr, nbr))
                        for nbr in self.reasoner.kg.G.predecessors(node1):
                            if self.reasoner.kg.G[nbr][node1].get('relation') in birth_rels:
                                countries1.add(self.reasoner.kg.node_to_title.get(nbr, nbr))
                    if node2:
                        for nbr in self.reasoner.kg.G.successors(node2):
                            if self.reasoner.kg.G[node2][nbr].get('relation') in birth_rels:
                                countries2.add(self.reasoner.kg.node_to_title.get(nbr, nbr))
                        for nbr in self.reasoner.kg.G.predecessors(node2):
                            if self.reasoner.kg.G[nbr][node2].get('relation') in birth_rels:
                                countries2.add(self.reasoner.kg.node_to_title.get(nbr, nbr))
                    common_countries = countries1 & countries2

                    if 'same_birth_country' in relation_names or common_countries:
                        if common_countries:
                            answer_text = f"Có. {entities[0]} và {entities[1]} cùng sinh tại {', '.join(sorted(common_countries))}."
                        else:
                            answer_text = f"Có. {entities[0]} và {entities[1]} cùng sinh tại cùng một quốc gia."
                    elif relations:
                        answer_text = "Có. " + "; ".join(relations) + "."
                    else:
                        # Kết nối gián tiếp, mô tả đường đi
                        path_desc = reasoning.get('description', '')
                        answer_text = f"Có kết nối gián tiếp qua {hops} bước. {path_desc}"
                else:
                    # Chỉ hỏi có/không
                    if hops == 1:
                        answer_text = f"Có. {entities[0]} và {entities[1]} có kết nối trực tiếp."
                    else:
                        answer_text = f"Có. {entities[0]} và {entities[1]} có kết nối qua {hops} bước."
            else:
                # Không có kết nối
                answer_text = "Không."
            
            return {
                'query': query,
                'type': 'connection',
                'context': '',
                'reasoning': reasoning,
                'answer': replace_thankyou(answer_text)
            }
        
        # Xử lý university (2 người)
        if query_type == 'university' and len(entities) >= 2:
            # Ưu tiên kiểm tra từ graph edges
            reasoning = self.reasoner.check_same_university(entities[0], entities[1])

            if reasoning.get('missing_entities'):
                missing = reasoning['missing_entities']
                answer_text = f"Không. Không tìm thấy: {', '.join(missing)}"
            elif reasoning.get('answer') == 'CÓ':
                # Có trường chung từ graph
                unis = reasoning.get('universities', [])
                if unis:
                    answer_text = f"Có. {entities[0]} và {entities[1]} cùng học tại {', '.join(unis)}."
                else:
                    answer_text = f"Có. {entities[0]} và {entities[1]} cùng học một trường."
            else:
                # Không tìm thấy trong graph, thử kiểm tra từ node_details
                alma_result = self._compare_alma_mater(entities[0], entities[1])
                if alma_result == "Có":
                    answer_text = f"Có. {entities[0]} và {entities[1]} cùng học một trường."
                else:
                    answer_text = f"Không. {entities[0]} và {entities[1]} không học cùng trường."

            return {
                'query': query,
                'type': 'university',
                'context': '',
                'reasoning': reasoning,
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
