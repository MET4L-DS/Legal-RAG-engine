import json
import time
import os
from typing import List, Dict
from src.retrieval.engine import LegalEngine
from dotenv import load_dotenv

load_dotenv()

class LegalQualityTester:
    def __init__(self, output_file: str = "debug_quality_report.json"):
        self.engine = LegalEngine()
        self.output_file = output_file
        self.results = []
        
        # Mixed Test Set (Victim vs Informational)
        self.test_cases = [
            {"query": "I have been robbed, what can I do?", "expected_context": "victim_distress"},
            {"query": "Someone assaulted my sister just now", "expected_context": "victim_distress"},
            {"query": "Steps for medical examination of rape victim", "expected_context": "victim_distress"}, # Even if impersonal, often from victim
            {"query": "What is the definition of a public servant under BNS?", "expected_context": "informational"},
            {"query": "Define 'Document' under Bharatiya Sakshya Adhiniyam", "expected_context": "informational"},
            {"query": "Is electronic evidence admissible in court?", "expected_context": "informational"},
            {"query": "I am a lawyer looking for high court powers", "expected_context": "professional"},
            {"query": "Minimum compensation for loss of life under NALSA", "expected_context": "victim_distress"}, # High relevance to victims
            {"query": "What constitutes an unlawful assembly?", "expected_context": "informational"},
            {"query": "Procedure for Zero FIR", "expected_context": "victim_distress"}
        ]

    def run_tests(self):
        print(f"Starting Quality Assurance Test (Victim-Centric) on {len(self.test_cases)} queries...")
        print(f"Active Models: {', '.join(self.engine.responder.model_ids)}")
        
        for i, case in enumerate(self.test_cases):
            query = case["query"]
            print(f"\n[{i+1}/{len(self.test_cases)}] Testing: {query}")
            
            try:
                start_time = time.time()
                result = self.engine.query(query)
                duration = time.time() - start_time
                
                # Enhanced Validation
                intent = result["intent"]["category"]
                context = result["intent"]["user_context"]
                response = result["response"]
                
                status = "PASS"
                reasons = []
                
                # 1. Answer length
                if len(response["answer"]) < 10:
                    status = "FAIL"
                    reasons.append("Answer too short")
                
                # 2. Source count
                if len(response["sources"]) == 0:
                    status = "FAIL"
                    reasons.append("No sources cited")

                # 3. Victim Verification
                if context == "victim_distress":
                    if not response.get("safety_alert"):
                        status = "FAIL"
                        reasons.append("Missing Safety Alert for victim")
                    if not response.get("immediate_action_plan") or len(response["immediate_action_plan"]) == 0:
                        status = "FAIL"
                        reasons.append("Missing Action Plan for victim")
                
                test_result = {
                    "query": query,
                    "expected_context": case["expected_context"],
                    "detected_context": context,
                    "status": f"{status} ({', '.join(reasons)})" if reasons else status,
                    "duration_seconds": round(duration, 2),
                    "safety_alert": response.get("safety_alert"),
                    "action_plan_count": len(response.get("immediate_action_plan", [])),
                    "full_answer": response["answer"]
                }
                
                self.results.append(test_result)
                print(f"   -> Result: {test_result['status']} (Context: {context})")
                
                # Brief sleep to avoid rate limits
                time.sleep(20)
                
            except Exception as e:
                print(f"   -> ERROR: {e}")
                self.results.append({
                    "query": query,
                    "status": f"ERROR: {str(e)}"
                })
        
        self.save_report()

    def save_report(self):
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)
        print(f"\nTest passed. Report saved to {self.output_file}")
        
        # Summary
        passed = sum(1 for r in self.results if "PASS" in r["status"])
        print(f"Summary: {passed}/{len(self.test_cases)} Passed")

if __name__ == "__main__":
    tester = LegalQualityTester()
    tester.run_tests()
