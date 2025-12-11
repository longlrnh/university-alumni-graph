# -*- coding: utf-8 -*-
"""
6_chatbot_interactive.py
Chatbot Interactive - Chạy trực tiếp trên local với Qwen + GraphRAG
Dùng tiếng Việt 100%
"""
import sys
import os
import importlib

def import_module(name):
    """Import module với tên bắt đầu số"""
    return importlib.import_module(name)

def interactive_chat():
    """Chatbot interactive loop"""
    print("\n" + "🤖 CHATBOT GRAPHRAG - CHẾ ĐỘ INTERACTIVE ".center(70, "="))
    print("\n⏳ Khởi tạo...\n")
    
    # Load modules
    try:
        KnowledgeGraph = import_module('1_knowledge_graph').KnowledgeGraph
        GraphRAGReasoner = import_module('2_graphrag_reasoner').GraphRAGReasoner
        GraphRAGChatbot = import_module('4_chatbot_graphrag').GraphRAGChatbot
        
        print("   📥 Nạp Knowledge Graph...", end="", flush=True)
        kg = KnowledgeGraph('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')
        print(" ✓")
        
        print("   📥 Khởi tạo GraphRAG Reasoner...", end="", flush=True)
        reasoner = GraphRAGReasoner(kg)
        print(" ✓")
        
        print("   📥 Tạo Chatbot với Qwen LLM...", end="", flush=True)
        chatbot = GraphRAGChatbot(kg, reasoner, use_qwen=True)
        print(" ✓")
        
    except Exception as e:
        print(f"\n\n❌ Lỗi khởi tạo: {e}")
        print("\nGợi ý:")
        print("   1. Kiểm tra file graph_out/nodes_unified.csv và edges_unified.csv")
        print("   2. Cài đặt: pip install pandas networkx scikit-learn")
        print("   3. Cho Qwen LLM: pip install transformers torch")
        return
    
    print("\n" + "=" * 70)
    print("✅ Sẵn sàng! Nhập câu hỏi (gõ 'thoát', 'exit', hoặc 'quit' để dừng)")
    print("=" * 70 + "\n")
    
    # Chat loop
    chat_count = 0
    while True:
        try:
            query = input("❓ Bạn: ").strip()
            
            if not query:
                print("⚠️  Vui lòng nhập câu hỏi\n")
                continue
            
            if query.lower() in ['thoát', 'exit', 'quit']:
                print("\n👋 Tạm biệt! Cảm ơn đã sử dụng chatbot.")
                break
            
            # Get answer
            print("\n⏳ Đang xử lý...\n")
            result = chatbot.answer(query)
            
            print(f"🤖 Chatbot: {result['answer']}\n")
            
            # Show debug info
            if result.get('reasoning') and result['reasoning'].get('connected'):
                print(f"📊 Debug: {result['reasoning']['hops']} bước kết nối")
                print(f"   Đường đi: {' → '.join(result['reasoning']['path'][:5])}\n")
            
            chat_count += 1
            
        except KeyboardInterrupt:
            print("\n\n👋 Bị dừng. Tạm biệt!")
            break
        except Exception as e:
            print(f"\n❌ Lỗi: {e}\n")
            continue
    
    print(f"\n📊 Tổng câu hỏi: {chat_count}")


def demo_mode():
    """Demo mode - Chạy các ví dụ"""
    print("\n" + "🤖 CHATBOT GRAPHRAG - CHẾ ĐỘ DEMO ".center(70, "="))
    print("\n⏳ Khởi tạo...\n")
    
    try:
        KnowledgeGraph = import_module('1_knowledge_graph').KnowledgeGraph
        GraphRAGReasoner = import_module('2_graphrag_reasoner').GraphRAGReasoner
        GraphRAGChatbot = import_module('4_chatbot_graphrag').GraphRAGChatbot
        
        print("   📥 Nạp Knowledge Graph...", end="", flush=True)
        kg = KnowledgeGraph('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')
        print(" ✓")
        
        print("   📥 Khởi tạo GraphRAG Reasoner...", end="", flush=True)
        reasoner = GraphRAGReasoner(kg)
        print(" ✓")
        
        print("   📥 Tạo Chatbot với Qwen LLM...", end="", flush=True)
        chatbot = GraphRAGChatbot(kg, reasoner, use_qwen=True)
        print(" ✓\n")
        
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        return
    
    # Demo questions
    demo_questions = [
        "Barack Obama và Bill Clinton có kết nối không?",
        "Elon Musk học ở trường nào?",
        "Mark Zuckerberg và Bill Gates có học cùng trường không?",
        "Thông tin về Steve Jobs",
        "Ai có liên quan đến Apple?"
    ]
    
    print("=" * 70)
    print("📝 CÁC CÂU HỎI DEMO")
    print("=" * 70 + "\n")
    
    for i, q in enumerate(demo_questions, 1):
        print(f"[{i}/{len(demo_questions)}] ❓ {q}")
        print("⏳ Xử lý...\n")
        
        try:
            result = chatbot.answer(q)
            print(f"🤖 {result['answer']}\n")
            
            if result.get('reasoning') and result['reasoning'].get('connected'):
                print(f"📊 {result['reasoning']['hops']} bước: {' → '.join(result['reasoning']['path'][:5])}\n")
        except Exception as e:
            print(f"❌ Lỗi: {e}\n")
        
        print("-" * 70 + "\n")


def main():
    """Main function"""
    print("\n" + "=" * 70)
    print("🚀 CHATBOT GRAPHRAG + QWEN LLM".center(70))
    print("=" * 70)
    print("\n📋 Chế độ chạy:")
    print("   1. Interactive (chat tự do)")
    print("   2. Demo (chạy ví dụ)")
    print("   3. Thoát")
    
    while True:
        choice = input("\n💡 Lựa chọn (1/2/3): ").strip() or "1"
        
        if choice == "1":
            interactive_chat()
            break
        elif choice == "2":
            demo_mode()
            break
        elif choice == "3":
            print("\n👋 Tạm biệt!")
            break
        else:
            print("⚠️  Lựa chọn không hợp lệ, vui lòng nhập 1, 2 hoặc 3")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Bị ngắt")
    except Exception as e:
        print(f"\n\n❌ Lỗi: {e}")
