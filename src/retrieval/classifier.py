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

    def __init__(self, model_id: str = "gemini-2.5-flash-lite"):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("API Key (GEMINI_API_KEY or GOOGLE_API_KEY) not found in environment variables.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_id = model_id or os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")

    def classify(self, query: str) -> QueryIntent:
        prompt = f"""
        You are a legal intent classifier for an Indian Legal RAG system.
        Analyze the following user query and categorize it into one of the following types:
        {", ".join(self.QUERY_TYPES)}

        Query: "{query}"

        Instructions:
        1. Identify the primary legal intent.
        2. Extract key legal entities (Acts, Sections, Offence names).
        3. Provide a confidence score.
        """

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=QueryIntent,
            ),
        )

        return response.parsed

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

    print("Query Classification Test:\n" + "="*30)
    for q in test_queries:
        intent = classifier.classify(q)
        print(f"Query: {q}")
        print(f"Category: {intent.category}")
        print(f"Entities: {', '.join(intent.key_entities)}")
        print(f"Confidence: {intent.confidence}")
        print("-" * 20)
