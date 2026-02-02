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
            intent = QueryIntent(category="general_explanation", confidence=0.5, key_entities=[], user_context="informational")

        # 2. Retrieval with Concept Expansion
        search_queries = [query]
        
        # If victim in distress, force-inject procedural and compensation queries
        if intent.user_context == "victim_distress":
            print("Victim Distress detected: Expanding concept search...")
            # Detect crime type from entities if possible
            offence = next((e for e in intent.key_entities if e.lower() in ["robbery", "assault", "rape", "theft"]), "crime")
            search_queries.append(f"How to file FIR for {offence} BNSS procedure")
            search_queries.append(f"Victim compensation rights for {offence} NALSA scheme")
            search_queries.append("Zero FIR registration procedure BNSS")

        # Combine results from all queries
        all_raw_results = []
        seen_chunks = set()
        
        for q in search_queries:
            # Shift hybrid weight for procedural queries
            q_weight = 0.6 if intent.category == "procedure" or "procedure" in q.lower() else 0.5
            results = self.engine.search(q, k=k, hybrid_weight=q_weight)
            for r in results:
                chunk_id = r["chunk"].get("canonical_header")
                if chunk_id and chunk_id not in seen_chunks:
                    all_raw_results.append(r)
                    seen_chunks.add(chunk_id)

        # 3. Apply Priority Rules (Statute > SOP)
        prioritized = self.prioritize_results(all_raw_results, intent)
        
        # 4. Parent Expansion
        expanded_results = self.expand_results(prioritized[:k])
        
        return {
            "intent": intent.model_dump(),
            "results": expanded_results
        }

    def prioritize_results(self, results: List[Dict], intent: QueryIntent) -> List[Dict]:
        for res in results:
            meta = res["chunk"].get("metadata", {})
            law = str(meta.get("law", "")).upper()
            
            boost = 1.0
            
            # Victim Mode Boosting
            if intent.user_context == "victim_distress":
                # Boost BNSS and SOP significantly for Police/FIR related tasks
                is_police_task = intent.category in ["police_duty", "procedure"] or any(w in intent.model_dump().get('sub_intent', '') or '' for w in ['FIR', 'report', 'police'])
                
                if "BNSS" in law or "SOP" in law:
                    boost += 0.5 if is_police_task else 0.3
                
                # Boost NALSA (Compensation) moderately, but less than Procedure if it's a procedural query
                if "NALSA" in law:
                    boost += 0.2 if is_police_task else 0.4

                # Penalize BNS (punishment) slightly so procedure ranks higher
                if "BNS" in law and "BNSS" not in law:
                    boost -= 0.2
            
            # Boost if law is mentioned in key entities
            for entity in intent.key_entities:
                if entity.upper() in law:
                    boost += 0.2
            
            # Penalize SOP slightly if primary legislation is needed for definitions
            if intent.category in ["definition", "punishment"] and "SOP" in law:
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
    sample_queries = [
        "What is Section 302 of BNS?", # informational
        "I was just robbed at gunpoint, what do I do?" # victim_distress
    ]
    
    for query in sample_queries:
        print(f"\n{'='*50}\nTESTING: {query}")
        output = orchestrator.orchestrate(query)
        
        print("\nOrchestrated Results:")
        print(f"Detected Context: {output['intent']['user_context']}")
        print(f"Detected Intent: {output['intent']['category']}")
        for i, res in enumerate(output["results"]):
            print(f"\n[{i+1}] {res['chunk']['canonical_header']} (Score: {res.get('score', 'N/A')})")
            content = res['chunk']['text'][:150].replace('\n', ' ')
            print(f"   Content: {content}...")
