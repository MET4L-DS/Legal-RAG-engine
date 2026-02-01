from src.retrieval.engine import LegalEngine
import json

def debug_query(query: str):
    engine = LegalEngine()
    print(f"\n🔎 DEBUGGING QUERY: '{query}'")
    
    # 1. Inspect Orchestration (Concept Expansion)
    orchestration = engine.orchestrator.orchestrate(query)
    intent = orchestration["intent"]
    results = orchestration["results"]
    
    print(f"\n🧠 INTENT DETECTED: {intent.get('category')} / {intent.get('sub_intent')}")
    print(f"   User Context: {intent.get('user_context')}")
    print(f"   Entities: {intent.get('key_entities')}")
    
    print(f"\n📄 RETRIEVED CHUNKS ({len(results)}):")
    for i, res in enumerate(results):
        chunk = res['chunk']
        print(f"\n[{i+1}] {chunk['canonical_header']}")
        print(f"    Source: {chunk['metadata'].get('law')} - {chunk['metadata'].get('section')}")
        print(f"    Score: {res.get('combined_score', 0):.4f}")
        print(f"    Snippet: {chunk['text'][:100]}...")

if __name__ == "__main__":
    # Test the problematic query
    debug_query("I have been assaulted and police refused to file FIR")
