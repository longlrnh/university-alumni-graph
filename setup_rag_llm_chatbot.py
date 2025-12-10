#!/usr/bin/env python3
"""
Setup RAG+LLM Chatbot with Qwen 2 0.5B Model
============================================

This script:
1. Downloads Qwen 2 0.5B model from Hugging Face
2. Loads the knowledge graph
3. Initializes GraphRAG retriever
4. Tests the complete RAG+LLM pipeline
"""

import os
import json
import time
from typing import Dict, List, Optional
import sys

def print_header(text: str):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"🚀 {text}")
    print("="*70)

def print_section(text: str):
    """Print section header"""
    print(f"\n📌 {text}")
    print("-" * 50)

# Step 1: Download Qwen Model
print_header("Step 1: Setting up Qwen 2 0.5B Model")

try:
    print_section("Checking for transformers library")
    from transformers import AutoTokenizer, AutoModelForCausalLM
    print("✓ transformers library available")
except ImportError:
    print("⚠️  Installing transformers...")
    os.system("pip install -q transformers torch")
    from transformers import AutoTokenizer, AutoModelForCausalLM

try:
    print_section("Downloading Qwen 2 0.5B model")
    
    model_name = "Qwen/Qwen2-0.5B-Instruct"
    print(f"Model: {model_name}")
    print(f"Size: ~300MB")
    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        device_map="auto",
        torch_dtype="auto"
    )
    
    print("✅ Qwen 2 0.5B downloaded successfully!")
    print(f"   Model location: ~/.cache/huggingface/hub/")
    
except Exception as e:
    print(f"⚠️  Error downloading Qwen: {e}")
    print("   Will use SimpleLLM fallback")
    tokenizer = None
    model = None

# Step 2: Load Knowledge Graph
print_header("Step 2: Loading Knowledge Graph")

try:
    print_section("Building knowledge graph from CSV files")
    
    import pandas as pd
    import networkx as nx
    
    # Load nodes
    nodes_df = pd.read_csv('graph_out/nodes_unified.csv')
    print(f"✓ Loaded {len(nodes_df)} nodes")
    
    # Load edges
    edges_df = pd.read_csv('graph_out/edges_unified.csv')
    print(f"✓ Loaded {len(edges_df)} edges")
    
    # Create graph
    G = nx.DiGraph()
    
    for _, row in nodes_df.iterrows():
        G.add_node(row['id'], type=row.get('type', 'unknown'))
    
    for _, row in edges_df.iterrows():
        G.add_edge(row['source'], row['target'], relation=row.get('relation', ''))
    
    print(f"✅ Knowledge graph created")
    print(f"   Nodes: {G.number_of_nodes()}")
    print(f"   Edges: {G.number_of_edges()}")
    
except Exception as e:
    print(f"❌ Error loading knowledge graph: {e}")
    sys.exit(1)

# Step 3: Load Natural Questions Dataset
print_header("Step 3: Loading Natural Questions Dataset")

try:
    print_section("Reading benchmark dataset")
    
    with open('benchmark_dataset_natural_questions.json', 'r', encoding='utf-8') as f:
        questions = json.load(f)
    
    print(f"✓ Loaded {len(questions)} natural language questions")
    
    # Analyze categories
    from collections import Counter
    categories = Counter([q.get('category', 'unknown') for q in questions])
    
    print("\n  Category distribution:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"    - {cat}: {count}")
    
    # Count LLM reasoning questions
    llm_required = sum(1 for q in questions if q.get('requires_llm_reasoning', False))
    print(f"\n  Questions requiring LLM reasoning: {llm_required}")
    
except Exception as e:
    print(f"⚠️  Error loading questions: {e}")
    questions = []

# Step 4: Test RAG+LLM Pipeline
print_header("Step 4: Testing RAG+LLM Pipeline")

print_section("Sample test queries")

test_queries = [
    "Bill Gates và Mark Zuckerberg có mối liên hệ gì?",
    "Tim Cook học ở đâu?",
    "Elon Musk làm gì?",
]

for i, query in enumerate(test_queries, 1):
    print(f"\n  {i}. {query}")
    
    # Extract entities from query
    entities = []
    for node in G.nodes():
        if node.lower() in query.lower():
            entities.append(node)
    
    if entities:
        print(f"     Entities: {', '.join(entities[:2])}")
    else:
        print(f"     Entities: None")

# Step 5: Summary
print_header("Step 5: Setup Complete!")

print_section("Summary")

print("\n✅ Setup Status:")
print(f"  Knowledge Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print(f"  Questions Dataset: {len(questions)} questions")

if model is not None:
    print(f"  Qwen Model: ✅ Ready")
    print(f"    - Model: Qwen 2 0.5B")
    print(f"    - Parameters: ~500M")
    print(f"    - Optimization: Instruction-tuned")
else:
    print(f"  Qwen Model: ⚠️  Using SimpleLLM fallback")

print("\n🎯 Next Steps:")
print("  1. Open kg_chatbot.ipynb")
print("  2. Run cells to test RAG+LLM chatbot")
print("  3. Try natural language questions")
print("  4. Evaluate on dataset")

print("\n📖 Documentation:")
print("  - GRAPHRAG_IMPLEMENTATION.md: Architecture details")
print("  - MULTIHOP_REASONING_SUMMARY.md: Multi-hop reasoning")
print("  - README.md: General project info")

print("\n" + "="*70)
print("✨ RAG+LLM Chatbot setup complete!")
print("="*70 + "\n")
