import os
import json
from typing import Dict, Any
from .orchestrator import LegalOrchestrator
from .responder import LegalResponder

class LegalEngine:
    def __init__(self, store_dir: str = "data/vector_store"):
        self.orchestrator = LegalOrchestrator(store_dir)
        # We can force a model if needed, e.g. gemini-1.5-flash for speed/quota
        self.responder = LegalResponder()

    def query(self, query_text: str) -> Dict[str, Any]:
        """
        Executes a full RAG cycle:
        1. Query Classification (Intent)
        2. Hybrid Retrieval (Semantic + Keywords)
        3. Priority Filtering & Parent Expansion
        4. Structured Answer Generation
        """
        # 1. Orchestrate
        orchestration = self.orchestrator.orchestrate(query_text)
        
        # 2. Respond
        response_data = self.responder.generate_response(
            query=query_text,
            context=orchestration["results"],
            intent=orchestration["intent"]
        )
        
        return {
            "query": query_text,
            "intent": orchestration["intent"],
            "response": response_data.model_dump(),
            "context_used": [
                {
                    "citation": c["chunk"]["canonical_header"],
                    "expanded": "parent_context" in c
                } for c in orchestration["results"]
            ]
        }

if __name__ == "__main__":
    # Full Loop Test
    engine = LegalEngine()
    test_query = "I have been robbed just now, what should I do first?"
    
    print(f"Running Full Engine Query (Victim Distress): {test_query}")
    try:
        final_output = engine.query(test_query)
        print("\n" + "="*50)
        print("VICTIM-CENTRIC LEGAL ANSWER")
        print("="*50)
        
        if final_output['response'].get('safety_alert'):
            print(f"\n🚨 SAFETY ALERT: {final_output['response']['safety_alert']}")
            
        print("\n📋 IMMEDIATE ACTION PLAN:")
        for step in final_output['response'].get('immediate_action_plan', []):
            print(f"  - {step}")

        print(f"\n💬 RESPONSE:\n{final_output['response']['answer']}")
        
        print("\n⚖️ LEGAL BASIS:")
        print(final_output['response']['legal_basis'])
        
        print("\n📚 SOURCES:")
        for s in final_output['response']['sources']:
            print(f"- {s['citation']}")
    except Exception as e:
        print(f"Error during query: {e}")
