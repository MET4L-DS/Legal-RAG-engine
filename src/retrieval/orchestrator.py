import json
import os
from typing import List, Dict, Any
from pathlib import Path
from .classifier import QueryClassifier, QueryIntent
from test_retrieval import RetrievalEngine

class LegalOrchestrator:
    def __init__(self, store_dir: str = "data/vector_store"):
        self.engine = RetrievalEngine(store_dir)
        self.classifier = QueryClassifier()
        self.store_dir = Path(store_dir)
        
        # Load metadata into a lookup table for expansion
        with open(self.store_dir / "metadata.json", "r", encoding="utf-8") as f:
            self.all_chunks = json.load(f)
        
        # Build a lookup for sections: (law, section) -> chunk
        self.section_lookup = {}
        for chunk in self.all_chunks:
            meta = chunk.get("metadata", {})
            law = meta.get("law")
            section = meta.get("section")
            unit_type = meta.get("unit_type")
            
            if law and section and unit_type == "section":
                self.section_lookup[(law, section)] = chunk

    def orchestrate(self, query: str, k: int = 5) -> Dict[str, Any]:
        # 1. Classify Intent
        print(f"Classifying query: {query}")
        try:
            intent = self.classifier.classify(query)
        except Exception as e:
            print(f"Classification failed: {e}. Falling back to general.")
            intent = QueryIntent(category="general_explanation", confidence=0.5, key_entities=[])

        # 2. Retrieval with Priority Logic
        # Adjust hybrid weight based on intent if needed
        # (e.g., procedure might benefit more from keyword search)
        hybrid_weight = 0.6 if intent.category == "procedure" else 0.5
        
        raw_results = self.engine.search(query, k=k*2, hybrid_weight=hybrid_weight)
        
        # 3. Apply Priority Rules (Statute > SOP)
        # We also boost based on key entities (e.g., if query says "BNS")
        prioritized = self.prioritize_results(raw_results, intent)
        
        # 4. Parent Expansion
        expanded_results = self.expand_results(prioritized[:k])
        
        return {
            "intent": intent.model_dump(),
            "results": expanded_results
        }

    def prioritize_results(self, results: List[Dict], intent: QueryIntent) -> List[Dict]:
        for res in results:
            meta = res["chunk"].get("metadata", {})
            law = meta.get("law", "").upper()
            
            # Boost if law is mentioned in key entities
            boost = 1.0
            for entity in intent.key_entities:
                if entity.upper() in law:
                    boost += 0.2
            
            # Penalize SOP slightly if primary legislation is needed for definitions
            if intent.category in ["definition", "punishment"] and law == "SOP":
                boost -= 0.3
            
            res["score"] *= boost
            
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def expand_results(self, results: List[Dict]) -> List[Dict]:
        final_results = []
        seen_headers = set()

        for res in results:
            chunk = res["chunk"]
            meta = chunk.get("metadata", {})
            
            # Skip if we already included this exact section/header
            header = chunk.get("canonical_header")
            if header in seen_headers:
                continue
            seen_headers.add(header)

            # Check if this is a sub-unit that needs its parent
            unit_type = meta.get("unit_type")
            if unit_type in ["illustration", "explanation", "sub_section"]:
                law = meta.get("law")
                section = meta.get("section")
                
                parent = self.section_lookup.get((law, section))
                if parent and parent.get("canonical_header") != header:
                    # Prepend parent text or include it as field
                    res["parent_context"] = parent["text"]
            
            final_results.append(res)
            
        return final_results

if __name__ == "__main__":
    orchestrator = LegalOrchestrator()
    sample_query = "What is the punishment for Section 302 of BNS?"
    output = orchestrator.orchestrate(sample_query)
    
    print("\nOrchestrated Results:")
    print(f"Detected Intent: {output['intent']['category']} (Conf: {output['intent']['confidence']})")
    for i, res in enumerate(output["results"]):
        print(f"\n[{i+1}] {res['chunk']['canonical_header']}")
        if "parent_context" in res:
            print(f"   (Parent Context Included from {res['chunk']['metadata']['section']})")
        content = res['chunk']['text'][:200].replace('\n', ' ')
        print(f"   Content: {content}...")
