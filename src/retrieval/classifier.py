import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class QueryIntent(BaseModel):
    category: str = Field(..., description="The category of the legal query.")
    sub_intent: Optional[str] = Field(None, description="A more specific sub-intent if applicable.")
    key_entities: List[str] = Field(default_factory=list, description="Relevant legal entities or keywords extracted from the query.")
    user_context: str = Field(..., description="The context of the user (victim_distress, informational, professional)")
    confidence: float = Field(..., description="Confidence score between 0 and 1.")

class QueryClassifier:
    QUERY_TYPES = [
        "definition",
        "procedure",
        "punishment",
        "bailability",
        "jurisdiction",
        "rights_of_victim",
        "police_duty",
        "court_power",
        "compensation",
        "general_explanation"
    ]

    def __init__(self, model_ids: Optional[List[str]] = None):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("API Key (GEMINI_API_KEY or GOOGLE_API_KEY) not found in environment variables.")
        
        self.client = genai.Client(api_key=api_key)
        
        # Default model list if not provided
        default_models = [ "gemma-3-27b-it", "gemini-2.5-flash-lite", "gemma-3-12b-it"]
        env_models = os.getenv("LLM_MODELS")
        if env_models:
            self.model_ids = [m.strip() for m in env_models.split(",")]
        else:
            self.model_ids = model_ids or default_models

    def classify(self, query: str) -> QueryIntent:
        prompt = f"""
        Analyze the following user query and categorize it into one of the following types:
        {", ".join(self.QUERY_TYPES)}

        Query: "{query}"

        Instructions:
        Determine the user's context:
        - "victim_distress": If the user is reporting a crime that happened to them or someone close, expresses urgency, or uses personal pronouns ("I", "my").
        - "informational": If the user is asking general questions, definitions, or is a student/researcher.
        - "professional": If the user is a legal professional or police officer.

        Return strictly in JSON format with these EXACT keys:
        1. "category": (must be one of the types listed above)
        2. "sub_intent": (string or null)
        3. "key_entities": (list of extracted legal terms)
        4. "user_context": (victim_distress, informational, or professional)
        5. "confidence": (float between 0 and 1)
        
        Example: {{"category": "procedure", "sub_intent": "filing", "key_entities": ["FIR"], "user_context": "victim_distress", "confidence": 0.9}}
        """

        last_exception = None
        for model_id in self.model_ids:
            try:
                print(f"Attempting classification with {model_id}...")
                
                is_gemma = "gemma" in model_id.lower()
                
                if is_gemma:
                    # Gemma doesn't reliably support JSON mode via SDK config yet
                    response = self.client.models.generate_content(
                        model=model_id,
                        contents=prompt + "\nIMPORTANT: Return ONLY valid JSON.",
                    )
                    # Simple JSON cleaner
                    text = response.text.strip()
                    if "```json" in text:
                        text = text.split("```json")[-1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[-1].split("```")[0].strip()
                    return QueryIntent.model_validate_json(text)
                else:
                    response = self.client.models.generate_content(
                        model=model_id,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=QueryIntent,
                        ),
                    )
                    return response.parsed
            except Exception as e:
                print(f"Model {model_id} failed: {e}")
                last_exception = e
        
        raise last_exception or Exception("Classification failed with all models.")

if __name__ == "__main__":
    # Test cases
    classifier = QueryClassifier()
    test_queries = [
        "What is Section 14 BNS?",
        "What should police do if FIR is online?",
        "Is rape a bailable offence?",
        "How much compensation for acid attack victims?",
        "Who has the power to grant bail in high court?"
    ]

    print("Query Classification Test (Victim-Centric):\n" + "="*40)
    test_queries = [
        "I have been robbed, what can I do?", # victim_distress
        "Someone assaulted my sister just now", # victim_distress
        "What is the definition of Section 14 BNS?", # informational
        "I am a lawyer looking for high court powers", # professional
        "Where should I file FIR for online theft?" # victim_distress / informational?
    ]

    for q in test_queries:
        try:
            intent = classifier.classify(q)
            print(f"Query: {q}")
            print(f"  Context: {intent.user_context}")
            print(f"  Category: {intent.category}")
            print(f"  Confidence: {intent.confidence}")
            print("-" * 20)
        except Exception as e:
            print(f"Error classifying '{q}': {e}")
