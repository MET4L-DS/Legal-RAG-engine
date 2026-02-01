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
    test_query = "What is the procedure for Zero FIR and who can file it?"
    
    print(f"Running Full Engine Query: {test_query}")
    try:
        final_output = engine.query(test_query)
        print("\n" + "="*50)
        print("FINAL LEGAL ANSWER")
        print("="*50)
        print(f"\nIntent: {final_output['intent']['category']}")
        print(f"\n{final_output['response']['answer']}")
        
        print("\nLegal Basis:")
        print(final_output['response']['legal_basis'])
        
        print("\nSources:")
        for s in final_output['response']['sources']:
            print(f"- {s['citation']}")
            
        print(f"\nDisclaimer: {final_output['response']['disclaimer']}")
    except Exception as e:
        print(f"Error during query: {e}")
