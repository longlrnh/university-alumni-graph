#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integrate all edges into single comprehensive graph
- Fix university node types
- Merge original graph edges (alumni, same_uni, link_to mentions)
- Merge enrichment v3 edges (career, country, relationships)
- Output: single nodes + edges files
"""

import json
import csv
from collections import defaultdict
from typing import List, Dict, Set

def load_original_graph():
    """Load original graph.json"""
    print("[+] Loading original graph...")
    with open('graph_out/graph.json', 'r', encoding='utf-8') as f:
        graph = json.load(f)
    
    print(f"  - Persons: {len(graph.get('persons', []))}")
    print(f"  - Universities: {len(graph.get('universities', []))}")
    print(f"  - edges_up: {len(graph.get('edges_up', []))}")
    print(f"  - edges_shared: {len(graph.get('edges_shared', []))}")
    print(f"  - edges_same_grad: {len(graph.get('edges_same_grad', []))}")
    
    return graph

def load_enrichment_v3():
    """Load enrichment v3 nodes and edges"""
    print("[+] Loading enrichment v3...")
    
    with open('graph_out/nodes_vi_v3.json', 'r', encoding='utf-8') as f:
        nodes = json.load(f)
    
    with open('graph_out/edges_vi_v3.json', 'r', encoding='utf-8') as f:
        edges = json.load(f)
    
    print(f"  - Nodes: {len(nodes)}")
    print(f"  - Edges: {len(edges)}")
    
    return nodes, edges

def load_mention_edges():
    """Load mention edges from separate CSV files and convert to link_to"""
    print("[+] Loading mention edges (as link_to)...")
    
    mention_edges = []
    mention_files = [
        'graph_out/edges_mentions_pp.csv',
        'graph_out/edges_mentions_pu.csv',
        'graph_out/edges_uni_mentions_p.csv',
        'graph_out/edges_uni_mentions_u.csv',
    ]
    
    total_count = 0
    for filename in mention_files:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Extract source and destination from different column names
                    src = row.get('src_person') or row.get('src_university', '')
                    dst = row.get('dst_person') or row.get('dst_university', '')
                    
                    if src.strip() and dst.strip():
                        mention_edges.append({
                            'from': src.strip(),
                            'to': dst.strip(),
                            'type': 'link_to',
                            'weight': 1,
                        })
                        total_count += 1
            print(f"  - {filename}: OK")
        except FileNotFoundError:
            print(f"  - {filename}: NOT FOUND (skipped)")
        except Exception as e:
            print(f"  - {filename}: ERROR - {e}")
    
    print(f"[OK] Loaded {total_count} mention edges as link_to")
    return mention_edges

def create_unified_nodes(original_graph, enrichment_nodes):
    """Create unified node list with correct types"""
    print("[+] Creating unified nodes...")
    
    unified_nodes = []
    seen_ids = set()
    
    # Universities from original graph (as authoritative source for universities)
    universities_set = set(original_graph.get('universities', []))
    
    # Process enrichment nodes
    for node in enrichment_nodes:
        node_id = node['id']
        node_title = node['title']
        
        # Fix type for universities
        if node_id in universities_set or node_title in universities_set:
            node_type = 'university'
        elif node_id.startswith('career_'):
            node_type = 'career'
        elif node_id.startswith('country_'):
            node_type = 'country'
        else:
            node_type = node.get('type', 'person')
        
        if node_id not in seen_ids:
            unified_nodes.append({
                'id': node_id,
                'title': node_title,
                'type': node_type,
                'link': node.get('link', ''),
            })
            seen_ids.add(node_id)
    
    print(f"[OK] Created {len(unified_nodes)} unified nodes")
    
    return unified_nodes

def create_unified_edges(original_graph, enrichment_edges, mention_edges, valid_nodes):
    """Create unified edge list from all sources
    
    Args:
        original_graph: Original graph data
        enrichment_edges: Edges from enrichment v3
        mention_edges: Link_to edges from mentions
        valid_nodes: Set of valid node IDs to filter orphan edges
    """
    print("[+] Creating unified edges...")
    
    unified_edges = []
    edge_dedup = set()
    orphan_count = 0
    
    # 1. Original graph edges - ALUMNI_OF (person -> university)
    # Format: [university, person, 'ALUMNI_OF', year]
    print("  - Processing alumni_of edges...")
    alumni_count = 0
    for edge in original_graph.get('edges_up', []):
        if isinstance(edge, list) and len(edge) >= 3:
            university = edge[0]
            person = edge[1]
            
            if person and university:
                edge_key = (person, university, 'alumni_of')
                if edge_key not in edge_dedup:
                    unified_edges.append({
                        'from': person,
                        'to': university,
                        'type': 'alumni_of',
                        'weight': 1,
                    })
                    edge_dedup.add(edge_key)
                    alumni_count += 1
    print(f"    Added {alumni_count} alumni_of edges")
    
    # 2. Original graph - SAME_UNI (person -> person, same university)
    # Format: [src, dst, 'SHARED_UNI' (label), count]
    print("  - Processing same_uni edges...")
    same_uni_count = 0
    for edge in original_graph.get('edges_shared', []):
        if isinstance(edge, list) and len(edge) >= 3:
            src = edge[0]
            dst = edge[1]
            weight = int(edge[3]) if len(edge) > 3 and edge[3] else 1
            
            if src and dst:
                # For undirected relationships, normalize to avoid duplicates
                normalized_key = tuple(sorted([src, dst]))
                edge_key = (normalized_key, 'same_uni')
                
                if edge_key not in edge_dedup:
                    unified_edges.append({
                        'from': src,
                        'to': dst,
                        'type': 'same_uni',
                        'weight': weight,
                    })
                    edge_dedup.add(edge_key)
                    same_uni_count += 1
    print(f"    Added {same_uni_count} same_uni edges")
    
    # 3. Link_to edges from mention CSV files
    print("  - Processing link_to edges...")
    link_to_count = 0
    for edge in mention_edges:
        src = edge['from']
        dst = edge['to']
        
        if src and dst:
            # For undirected relationships, normalize to avoid duplicates
            normalized_key = tuple(sorted([src, dst]))
            edge_key = (normalized_key, 'link_to')
            
            if edge_key not in edge_dedup:
                unified_edges.append(edge)
                edge_dedup.add(edge_key)
                link_to_count += 1
    print(f"    Added {link_to_count} link_to edges")
    
    # 4. Original graph - SAME_UNIVERSITY (person -> person)
    # Format: [src, dst, 'SAME_GRAD', '']
    print("  - Processing same_grad edges...")
    same_grad_count = 0
    for edge in original_graph.get('edges_same_grad', []):
        if isinstance(edge, list) and len(edge) >= 2:
            src = edge[0]
            dst = edge[1]
            
            if src and dst:
                normalized_key = tuple(sorted([src, dst]))
                edge_key = (normalized_key, 'same_uni')
                if edge_key not in edge_dedup:
                    unified_edges.append({
                        'from': src,
                        'to': dst,
                        'type': 'same_uni',
                        'weight': 1,
                    })
                    edge_dedup.add(edge_key)
                    same_grad_count += 1
    if same_grad_count > 0:
        print(f"    Added {same_grad_count} same_grad edges")
    
    # 5. Enrichment v3 edges (career, country, relationships)
    print("  - Processing enrichment v3 edges...")
    
    # Undirected relationship types (should deduplicate A→B and B→A)
    undirected_types = {'same_birth_country', 'same_career', 'same_uni', 'same_school'}
    
    enrichment_count = 0
    for edge in enrichment_edges:
        src = edge.get('from', '')
        dst = edge.get('to', '')
        edge_type = edge.get('type', '')
        
        if src and dst:
            # VALIDATE: Both nodes must exist
            if src not in valid_nodes or dst not in valid_nodes:
                orphan_count += 1
                continue
            
            # For undirected relationships, normalize to avoid A→B and B→A duplicates
            if edge_type in undirected_types:
                normalized_key = tuple(sorted([src, dst]))
                edge_key = (normalized_key, edge_type)
            else:
                # Directed relationships (has_career, born_in, alumni_of, etc.)
                edge_key = (src, dst, edge_type)
            
            if edge_key not in edge_dedup:
                unified_edges.append({
                    'from': src,
                    'to': dst,
                    'type': edge_type,
                    'weight': edge.get('weight', 1),
                })
                edge_dedup.add(edge_key)
                enrichment_count += 1
    print(f"    Added {enrichment_count} enrichment v3 edges (filtered {orphan_count} orphan edges)")
    
    print(f"\n[OK] Created {len(unified_edges)} unified edges total (filtered {orphan_count} total orphan edges)")
    
    return unified_edges

def export_unified_graph(nodes, edges):
    """Export unified graph to JSON and CSV"""
    print("[+] Exporting unified graph...")
    
    # Export JSON
    nodes_file = 'graph_out/nodes_unified.json'
    with open(nodes_file, 'w', encoding='utf-8') as f:
        json.dump(nodes, f, ensure_ascii=False, indent=2)
    print(f"  [OK] {nodes_file}")
    
    edges_file = 'graph_out/edges_unified.json'
    with open(edges_file, 'w', encoding='utf-8') as f:
        json.dump(edges, f, ensure_ascii=False, indent=2)
    print(f"  [OK] {edges_file}")
    
    # Export CSV
    nodes_csv = 'graph_out/nodes_unified.csv'
    with open(nodes_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'title', 'type'])
        writer.writeheader()
        for node in nodes:
            writer.writerow({
                'id': node['id'],
                'title': node['title'],
                'type': node['type'],
            })
    print(f"  [OK] {nodes_csv}")
    
    edges_csv = 'graph_out/edges_unified.csv'
    with open(edges_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['from', 'to', 'type', 'weight'])
        writer.writeheader()
        writer.writerows(edges)
    print(f"  [OK] {edges_csv}")

def print_statistics(nodes, edges):
    """Print graph statistics"""
    print("\n" + "=" * 80)
    print("UNIFIED GRAPH STATISTICS")
    print("=" * 80)
    
    # Node statistics
    node_types = defaultdict(int)
    for node in nodes:
        node_types[node['type']] += 1
    
    print(f"\nNodes: {len(nodes)}")
    for node_type, count in sorted(node_types.items()):
        print(f"  {node_type}: {count}")
    
    # Edge statistics
    edge_types = defaultdict(int)
    for edge in edges:
        edge_types[edge['type']] += 1
    
    print(f"\nEdges: {len(edges)}")
    for edge_type, count in sorted(edge_types.items(), key=lambda x: -x[1]):
        print(f"  {edge_type}: {count}")

def main():
    print("=" * 80)
    print("UNIFIED GRAPH INTEGRATION")
    print("=" * 80)
    
    # Load data
    original_graph = load_original_graph()
    enrichment_nodes, enrichment_edges = load_enrichment_v3()
    mention_edges = load_mention_edges()
    
    # Create unified graph
    unified_nodes = create_unified_nodes(original_graph, enrichment_nodes)
    valid_nodes = set(node['id'] for node in unified_nodes)
    unified_edges = create_unified_edges(original_graph, enrichment_edges, mention_edges, valid_nodes)
    
    # Export
    export_unified_graph(unified_nodes, unified_edges)
    
    # Statistics
    print_statistics(unified_nodes, unified_edges)
    
    print("\n" + "=" * 80)
    print("INTEGRATION COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()
