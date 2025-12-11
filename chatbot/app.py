# -*- coding: utf-8 -*-
"""
app.py
Website UI cho Chatbot GraphRAG + Qwen OWen3
Chạy: python app.py
Truy cập: http://localhost:5000
"""
from flask import Flask, render_template, request, jsonify
import json
import os
import importlib
import sys

# Import modules
def import_module(name):
    return importlib.import_module(name)

app = Flask(__name__)

# Global variables
kg = None
reasoner = None
chatbot = None
chat_history = []

def init_chatbot():
    """Khởi tạo chatbot"""
    global kg, reasoner, chatbot
    
    print("\n⏳ Khởi tạo Chatbot GraphRAG + Qwen OWen3...")
    
    try:
        KnowledgeGraph = import_module('1_knowledge_graph').KnowledgeGraph
        GraphRAGReasoner = import_module('2_graphrag_reasoner').GraphRAGReasoner
        GraphRAGChatbot = import_module('4_chatbot_graphrag').GraphRAGChatbot
        
        print("   📥 Nạp Knowledge Graph...", end="", flush=True)
        kg = KnowledgeGraph('../graph_out/nodes_unified.csv', '../graph_out/edges_unified.csv')
        print(" ✓")
        
        print("   📥 Khởi tạo GraphRAG Reasoner...", end="", flush=True)
        reasoner = GraphRAGReasoner(kg)
        print(" ✓")
        
        print("   📥 Tạo Chatbot...", end="", flush=True)
        chatbot = GraphRAGChatbot(kg, reasoner)
        print(" ✓\n")
        
        print("✅ Chatbot sẵn sàng!\n")
        return True
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        return False


@app.route('/')
def index():
    """Trang chủ"""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """API chat"""
    global chat_history
    
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Vui lòng nhập câu hỏi'}), 400
        
        # Gọi chatbot
        result = chatbot.answer(user_message)
        bot_message = result['answer']
        
        # Làm sạch bot_message (bỏ system prompt)
        if '💬 TRẢ LỜI:' in bot_message:
            bot_message = bot_message.split('💬 TRẢ LỜI:')[-1].strip()
            if bot_message.startswith('"') and bot_message.endswith('"'):
                bot_message = bot_message[1:-1]
        
        # Lưu lịch sử
        chat_history.append({
            'user': user_message,
            'bot': bot_message,
            'type': result.get('type', 'general'),
            'reasoning': result.get('reasoning', {})
        })
        
        # Lưu file
        with open('chat_history.json', 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'message': bot_message,
            'type': result.get('type', 'general'),
            'context': result.get('context', '')[:200],
            'history': chat_history[-5:]  # 5 tin nhắn gần đây
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    """Lấy lịch sử chat"""
    return jsonify(chat_history[-10:])  # 10 tin nhắn gần đây


@app.route('/api/clear', methods=['POST'])
def clear_history():
    """Xóa lịch sử"""
    global chat_history
    chat_history = []
    if os.path.exists('chat_history.json'):
        os.remove('chat_history.json')
    return jsonify({'status': 'ok'})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Lấy thống kê"""
    try:
        return jsonify({
            'graph': {
                'nodes': kg.G.number_of_nodes(),
                'edges': kg.G.number_of_edges()
            },
            'chat_count': len(chat_history),
            'status': 'ready'
        })
    except:
        return jsonify({'error': 'Error getting stats'}), 500


if __name__ == '__main__':
    # Khởi tạo
    if not init_chatbot():
        print("❌ Không thể khởi tạo chatbot")
        sys.exit(1)
    
    # Chạy server
    print("\n🚀 Website chạy tại: http://localhost:5000")
    print("⏹️  Bấm Ctrl+C để dừng\n")
    
    app.run(debug=False, host='127.0.0.1', port=5000)
