import os
import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class LegalSource(BaseModel):
    law: str = Field(..., description="The name of the Act or Scheme.")
    section: str = Field(..., description="The section or clause number.")
    content: str = Field(..., description="The relevant text content used.")
    citation: str = Field(..., description="Full canonical citation.")

class LegalResponse(BaseModel):
    answer: str = Field(..., description="Direct response to the user's query.")
    legal_basis: str = Field(..., description="Summary of the legal basis for this answer.")
    procedure_steps: List[str] = Field(default_factory=list, description="Step-by-step procedure if applicable.")
    important_notes: List[str] = Field(default_factory=list, description="Crucial caveats or conditions.")
    sources: List[LegalSource] = Field(..., description="Exact sources used from the provided context.")
    disclaimer: str = Field(..., description="Mandatory non-advisory legal disclaimer.")

class LegalResponder:
    def __init__(self, model_id: Optional[str] = None):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_id = model_id or os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")
        self.client = genai.Client(api_key=api_key)

    def generate_response(self, query: str, context: List[Dict[str, Any]], intent: Dict[str, Any]) -> LegalResponse:
        system_instruction = """
        You are a highly precise Indian Legal Assistant. Your goal is to answer legal queries strictly based on the provided context chunks.
        
        RULES:
        1. Only use the provided context. If the answer is not in the context, state it clearly.
        2. Citations must be exact. If you use a section, cite it exactly as provided in the canonical header.
        3. Do not assume facts. Do not give personalized legal advice.
        4. Maintain a formal, authoritative, yet helpful tone.
        5. For procedures, list steps clearly.
        6. Always include a disclaimer that this is for informational purposes and not legal advice.
        """

        # Format context for the prompt
        context_str = "\n\n".join([
            f"SOURCE: {c['chunk']['canonical_header']}\nCONTENT: {c['chunk']['text']}"
            for c in context
        ])

        prompt = f"""
        User Query: {query}
        Intent Category: {intent.get('category')}
        Key Entities: {', '.join(intent.get('key_entities', []))}

        Legal Context:
        {context_str}

        Task: Provide a structured legal response in JSON format.
        """

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=LegalResponse,
            ),
        )

        return response.parsed

if __name__ == "__main__":
    # Test Responder
    responder = LegalResponder()
    
    # Mock data based on orchestration output
    mock_query = "What is the procedure for Zero FIR?"
    mock_intent = {"category": "procedure", "key_entities": ["Zero FIR"]}
    mock_context = [
        {
            "chunk": {
                "canonical_header": "General SOP\nSection: Filing of FIR\nStep: Zero FIR",
                "text": "A Zero FIR can be filed in any police station regardless of jurisdiction. It is later transferred to the relevant station.",
                "metadata": {"law": "SOP", "section": "Zero FIR"}
            }
        }
    ]
    
    print("Testing Legal Responder...")
    answer = responder.generate_response(mock_query, mock_context, mock_intent)
    print(json.dumps(answer.model_dump(), indent=2))
