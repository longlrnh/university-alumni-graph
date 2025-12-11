# -*- coding: utf-8 -*-
"""
run_pipeline.py
Script chạy toàn bộ pipeline từ A-Z
"""
import sys
import os
import importlib

def import_module(name):
    """Import module với tên bắt đầu số"""
    return importlib.import_module(name)

def main():
    print("\n" + "🚀 PIPELINE CHATBOT GRAPHRAG ".center(70, "="))
    print("\n📋 Danh sách công việc:")
    print("   1️⃣  Nạp Knowledge Graph")
    print("   2️⃣  Khởi tạo GraphRAG Reasoner")
    print("   3️⃣  Sinh bộ dữ liệu đánh giá (≥2000 câu)")
    print("   4️⃣  Tạo Chatbot GraphRAG")
    print("   5️⃣  Đánh giá so sánh với Baseline")
    print("\n" + "=" * 70 + "\n")
    
    # Step 1: Load Knowledge Graph
    print("[1️⃣ ] Nạp Knowledge Graph...")
    try:
        KnowledgeGraph = import_module('1_knowledge_graph').KnowledgeGraph
        kg = KnowledgeGraph('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')
        kg.print_stats()
        print("✅ Knowledge Graph nạp thành công\n")
    except Exception as e:
        print(f"❌ Lỗi: {e}\n")
        return
    
    # Step 2: Initialize GraphRAG Reasoner
    print("[2️⃣ ] Khởi tạo GraphRAG Reasoner...")
    try:
        GraphRAGReasoner = import_module('2_graphrag_reasoner').GraphRAGReasoner
        reasoner = GraphRAGReasoner(kg)
        print("✅ GraphRAG Reasoner sẵn sàng\n")
    except Exception as e:
        print(f"❌ Lỗi: {e}\n")
        return
    
    # Step 3: Generate Evaluation Dataset
    print("[3️⃣ ] Sinh bộ dữ liệu đánh giá...")
    try:
        EvaluationDatasetGenerator = import_module('3_evaluation_dataset').EvaluationDatasetGenerator
        gen = EvaluationDatasetGenerator(kg)
        dataset = gen.generate_full_dataset('eval_dataset_2000.json')
        print("✅ Bộ dữ liệu sinh thành công\n")
    except Exception as e:
        print(f"❌ Lỗi: {e}\n")
        return
    
    # Step 4: Create Chatbot
    print("[4️⃣ ] Tạo Chatbot GraphRAG + Qwen OWen3...")
    try:
        GraphRAGChatbot = import_module('4_chatbot_graphrag').GraphRAGChatbot
        chatbot = GraphRAGChatbot(kg, reasoner)
        print("\n✅ Chatbot tạo thành công\n")
    except Exception as e:
        print(f"❌ Lỗi: {e}\n")
        return
    
    # Step 5: Evaluate & Compare
    print("[5️⃣ ] Chuẩn bị đánh giá...")
    try:
        ChatbotEvaluator = import_module('5_evaluate_compare').ChatbotEvaluator
        
        print("✅ Đánh giá được chuẩn bị (chạy riêng: py chatbot/app.py hoặc py 5_evaluate_compare.py)\n")
    except Exception as e:
        print(f"❌ Lỗi: {e}\n")
        return
    
    # Summary
    print("\n" + "🎉 HOÀN THÀNH CHUẨN BỊ CHATBOT ".center(70, "="))
    print("\n📁 Thư mục chatbot tạo được:")
    print("   • chatbot/graph_out/ (Knowledge Graph)")
    print("   • chatbot/*.py (Tất cả modules)")
    print("   • chatbot/eval_dataset_2000.json (1631 câu hỏi)")
    print("\n🚀 Bước tiếp theo:")
    print("   1. Demo Interactive: python 6_chatbot_interactive.py")
    print("   2. Website UI: python chatbot/app.py")
    print("   3. Đánh giá: python 5_evaluate_compare.py")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Bị ngắt bởi người dùng")
    except Exception as e:
        print(f"\n\n❌ Lỗi: {e}")
