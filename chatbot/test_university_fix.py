#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test fix for 2-person university query using graph data
"""

import sys
import json
import os

# Add current directory to path
sys.path.insert(0, '.')

print("\n" + "="*70)
print("🔄 Initializing Chatbot...")
print("="*70)

# Import modules dynamically
import importlib
KnowledgeGraph = importlib.import_module('1_knowledge_graph').KnowledgeGraph
GraphRAGReasoner = importlib.import_module('2_graphrag_reasoner').GraphRAGReasoner
ChatbotGraphRAG = importlib.import_module('4_chatbot_graphrag').ChatbotGraphRAG

# Initialize knowledge graph
print("📥 Loading Knowledge Graph...", end=" ", flush=True)
kg = KnowledgeGraph('graph_out/nodes_unified.csv', 'graph_out/edges_unified.csv')
print("✓")

# Initialize reasoner
print("📥 Loading GraphRAG Reasoner...", end=" ", flush=True)
reasoner = GraphRAGReasoner(kg)
print("✓")

# Initialize chatbot
print("📥 Loading Chatbot...", end=" ", flush=True)
chatbot = ChatbotGraphRAG(kg, reasoner)
print("✓")

print("\n" + "="*70)
print("🔍 TEST: Elon Musk và Donald Trump có học cùng trường không?")
print("="*70)

query = "Elon Musk và Donald Trump có học cùng trường không?"
try:
    result = chatbot.answer(query)
    print(f"\n✅ SUCCESS!")
    print(f"\n📝 Query: {result.get('query')}")
    print(f"🏷️  Type: {result.get('type')}")
    if result.get('reasoning'):
        print(f"🧠 Reasoning: {result.get('reasoning')}")
    print(f"💬 Answer: {result.get('answer')}")
    print()
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("="*70)
