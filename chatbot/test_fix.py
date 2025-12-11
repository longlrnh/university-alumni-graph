#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test the fix for yes/no query handling
"""

import sys
import json
sys.path.insert(0, '.')

from chatbot_graphrag import ChatbotGraphRAG
from knowledge_graph import KnowledgeGraph

# Load knowledge graph
kg = KnowledgeGraph()
kg.load_from_files(
    graph_file='graph_out/university_alumni_graph.graphml',
    node_details_file='graph_out/node_details.json',
    csv_file='../graph_out/nodes_unified.csv'
)

# Initialize chatbot
chatbot = ChatbotGraphRAG(kg)

# Test the problematic query
print("\n" + "="*70)
print("🔍 TEST: Elon Musk và Donald Trump có học cùng trường không?")
print("="*70)

query = "Elon Musk và Donald Trump có học cùng trường không?"
try:
    result = chatbot.answer(query)
    print(f"\n✅ SUCCESS!")
    print(f"Type: {result.get('type')}")
    print(f"Answer: {result.get('answer')}")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test another yes/no query
print("\n" + "="*70)
print("🔍 TEST: Elon Musk làm việc ở Tesla phải không?")
print("="*70)

query2 = "Elon Musk làm việc ở Tesla phải không?"
try:
    result = chatbot.answer(query2)
    print(f"\n✅ SUCCESS!")
    print(f"Type: {result.get('type')}")
    print(f"Answer: {result.get('answer')}")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test a property query
print("\n" + "="*70)
print("🔍 TEST: Elon Musk làm nghề gì?")
print("="*70)

query3 = "Elon Musk làm nghề gì?"
try:
    result = chatbot.answer(query3)
    print(f"\n✅ SUCCESS!")
    print(f"Type: {result.get('type')}")
    print(f"Answer: {result.get('answer')}")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("Test completed!")
print("="*70)
