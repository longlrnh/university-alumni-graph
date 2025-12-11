# -*- coding: utf-8 -*-
"""
5_evaluate_compare.py
Đánh giá Chatbot GraphRAG + Qwen OWen3 LLM
"""
import json
from typing import Dict, List
import random
import importlib

def import_module(name):
    """Import module với tên bắt đầu số"""
    return importlib.import_module(name)


class ChatbotEvaluator:
    """Đánh giá Chatbot GraphRAG"""
    
    def __init__(self, graphrag_chatbot):
        self.graphrag = graphrag_chatbot
    
    def evaluate_on_dataset(self, dataset_file: str = 'eval_dataset_2000.json', sample_size: int = 100) -> Dict:
        """Đánh giá trên tập dữ liệu"""
        # Tải dataset
        with open(dataset_file, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
        
        questions = dataset['questions']
        sample = random.sample(questions, min(sample_size, len(questions)))
        
        results = {
            'graphrag': {'correct': 0, 'total': 0, 'by_type': {}},
            'questions_tested': len(sample)
        }
        
        print(f"\n📊 ĐÁNH GIÁ TRÊN {len(sample)} CÂU HỎI")
        print("=" * 60)
        
        for i, q in enumerate(sample):
            qtype = q.get('type', 'unknown')
            
            # Đánh giá GraphRAG
            gr_ans = self.graphrag.answer(q['question'])['answer'].lower()
            gr_score = self._check_answer(gr_ans, q.get('answer', ''))
            
            # Cập nhật thống kê
            results['graphrag']['total'] += 1
            
            if gr_score:
                results['graphrag']['correct'] += 1
            
            # Theo loại câu hỏi
            if qtype not in results['graphrag']['by_type']:
                results['graphrag']['by_type'][qtype] = {'correct': 0, 'total': 0}
            
            results['graphrag']['by_type'][qtype]['total'] += 1
            
            if gr_score:
                results['graphrag']['by_type'][qtype]['correct'] += 1
            
            if (i + 1) % 20 == 0:
                print(f"   Progress: {i + 1}/{len(sample)}...")
        
        return results
    
    def _check_answer(self, pred: str, gold: str) -> bool:
        """Kiểm tra câu trả lời (heuristic)"""
        pred_lower = pred.lower()
        gold_lower = gold.lower()
        
        if 'có' in gold_lower or 'yes' in gold_lower:
            return 'có' in pred_lower or 'yes' in pred_lower or 'kết nối' in pred_lower
        elif 'không' in gold_lower or 'no' in gold_lower:
            return 'không' in pred_lower or 'no' in pred_lower or 'không có' in pred_lower
        else:
            # MCQ: kiểm tra nếu đáp án nằm trong response
            return gold_lower in pred_lower
    
    def print_results(self, results: Dict):
        """In kết quả đánh giá"""
        print("\n" + "=" * 60)
        print("📈 KẾT QUẢ ĐÁNH GIÁ CHATBOT GRAPHRAG + QWEN")
        print("=" * 60)
        
        gr_acc = (results['graphrag']['correct'] / results['graphrag']['total'] * 100) \
                 if results['graphrag']['total'] > 0 else 0
        
        print(f"\n🤖 GraphRAG + Qwen OWen3:")
        print(f"   Đúng: {results['graphrag']['correct']}/{results['graphrag']['total']}")
        print(f"   Độ chính xác: {gr_acc:.1f}%")
        
        print(f"\n📊 Theo loại câu hỏi:")
        for qtype in sorted(results['graphrag']['by_type'].keys()):
            gr = results['graphrag']['by_type'].get(qtype, {'correct': 0, 'total': 0})
            
            gr_acc_type = (gr['correct'] / gr['total'] * 100) if gr['total'] > 0 else 0
            
            print(f"\n   {qtype}:")
            print(f"      GraphRAG: {gr_acc_type:.1f}% ({gr['correct']}/{gr['total']})")
        
        print(f"\n📈 Tổng độ chính xác: {gr_acc:.1f}%")
        print("=" * 60)
        
        # Lưu kết quả
        with open('eval_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Lưu kết quả vào eval_results.json")


if __name__ == "__main__":
    KnowledgeGraph = import_module('1_knowledge_graph').KnowledgeGraph
    GraphRAGReasoner = import_module('2_graphrag_reasoner').GraphRAGReasoner
    GraphRAGChatbot = import_module('4_chatbot_graphrag').GraphRAGChatbot
    
    # Khởi tạo
    kg = KnowledgeGraph('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')
    reasoner = GraphRAGReasoner(kg)
    graphrag_bot = GraphRAGChatbot(kg, reasoner)
    
    # Đánh giá
    evaluator = ChatbotEvaluator(graphrag_bot)
    results = evaluator.evaluate_on_dataset('eval_dataset_2000.json', sample_size=100)
    evaluator.print_results(results)
