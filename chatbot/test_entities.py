import importlib
import json

KnowledgeGraph = importlib.import_module('1_knowledge_graph').KnowledgeGraph
GraphRAGReasoner = importlib.import_module('2_graphrag_reasoner').GraphRAGReasoner
GraphRAGChatbot = importlib.import_module('4_chatbot_graphrag').GraphRAGChatbot

kg = KnowledgeGraph('../graph_out/nodes_unified.csv', '../graph_out/edges_unified.csv')
reasoner = GraphRAGReasoner(kg)
chatbot = GraphRAGChatbot(kg, reasoner)

query = 'Bill Gates là cựu sinh viên trường đại học nào? A. Đại học Yale B. Đại học Harvard C. Đại học New York D. Đại học Oxford'
entities = reasoner._extract_entities(query)
print('Entities extracted:', entities)
print('Bill Gates in graph:', 'Bill Gates' in kg.title_to_node)

# Check node_details
print('Bill Gates in node_details:', 'Bill Gates' in chatbot.node_details)

# Check properties
if 'Bill Gates' in chatbot.node_details:
    detail = chatbot.node_details['Bill Gates']
    props = detail.get('properties', {})
    print('\nProperties of Bill Gates:')
    for key in ['Alma mater', 'Trường lớp', 'Education', 'Học vấn']:
        if key in props:
            print(f'  {key}: {props[key]}')

# Test the answer
result = chatbot.answer(query)
print('\nChatbot answer:', result['answer'])
