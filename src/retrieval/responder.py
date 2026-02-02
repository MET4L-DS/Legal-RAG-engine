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
    safety_alert: Optional[str] = Field(None, description="Immediate critical safety advice if in distress.")
    immediate_action_plan: List[str] = Field(default_factory=list, description="Top-priority chronological steps for the user.")
    legal_basis: str = Field(..., description="Summary of the legal basis for this answer.")
    procedure_steps: List[str] = Field(default_factory=list, description="Detailed procedural steps.")
    important_notes: List[str] = Field(default_factory=list, description="Crucial caveats or conditions.")
    sources: List[LegalSource] = Field(..., description="Exact sources used from the provided context.")
    disclaimer: str = Field(..., description="Mandatory non-advisory legal disclaimer.")

class LegalResponder:
    def __init__(self, model_ids: Optional[List[str]] = None):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("API Key (GEMINI_API_KEY or GOOGLE_API_KEY) not found in environment variables.")
        self.client = genai.Client(api_key=api_key)
        
        # Default model list if not provided
        default_models = ["gemini-2.5-flash-lite", "gemma-3-27b-it", "gemma-3-12b-it"]
        env_models = os.getenv("LLM_MODELS")
        if env_models:
            self.model_ids = [m.strip() for m in env_models.split(",")]
        else:
            self.model_ids = model_ids or default_models

    def generate_response(self, query: str, context: List[Dict[str, Any]], intent: Dict[str, Any]) -> LegalResponse:
        user_context = intent.get("user_context", "informational")
        
        system_instruction = f"""
        You are a supportive and highly precise Indian Legal Assistant. Your primary goal is to assist users, particularly victims of crimes, by providing clear, actionable, and empathetic guidance.
        
        USER CONTEXT: {user_context}
        
        VICTIM-CENTRIC RULES (Priority if context is 'victim_distress'):
        1. FIRST PRIORITY: User safety. Use the 'safety_alert' field for critical advice (e.g., "Call 112 immediately", "Move to a secure location").
        2. SECOND PRIORITY: Immediate Action. List 3-5 clear steps in 'immediate_action_plan'. Use simple verbs. Use Grade 8 reading level (no complex words).
        3. TONE: Supportive, direct, and empathetic. Address the user as 'You'. Avoid cold, passive language.
        4. ANSWER FORMATTING: The 'answer' field MUST be formatted in Markdown. Merge the content of 'important_notes' seamlessly into the answer where relevant to create a comprehensive response. Use bolding and bullet points for readability.
        5. ACCESSIBILITY: If you use terms like 'Cognizable' or 'Bailable', explain them in simple terms in parentheses (e.g., 'Cognizable (a serious crime where police can arrest without a warrant)').
        
        GENERAL / INFORMATIONAL RULES (if context is 'informational' or 'professional'):
        1. DO NOT generate 'safety_alert' or 'immediate_action_plan'. Leave them null/empty.
        2. ANSWER FORMATTING: The 'answer' field MUST be formatted in Markdown. Organize complex information into bullet points. Merge 'important_notes' into the answer text flow.
        3. Only use the provided context. If the answer is not in the context, state it clearly.
        4. Citations must be exact. Cite the canonical header.
        5. Do not give personalized legal advice.
        6. Always include the mandatory disclaimer.
        """

        # Format context for the prompt
        context_items = []
        for c in context:
            header = c['chunk']['canonical_header']
            text = c['chunk']['text']
            
            # Check if parent context was expanded by Orchestrator
            if c.get("parent_context"):
                # Prepend parent context clearly
                text = f"[PARENT CONTEXT]: {c['parent_context']}\n[SPECIFIC CLAUSE]: {text}"
            
            context_items.append(f"SOURCE: {header}\nCONTENT: {text}")

        context_str = "\n\n".join(context_items)

        last_exception = None
        for model_id in self.model_ids:
            try:
                print(f"Attempting generation with {model_id}...")
                
                is_gemma = "gemma" in model_id.lower()
                
                prompt = f"""
                User Query: {query}
                Intent Category: {intent.get('category')}
                Key Entities: {', '.join(intent.get('key_entities', []))}

                Legal Context:
                {context_str}

                Task: Provide a structured legal response in JSON format with these EXACT keys:
                1. "safety_alert": (string or null, e.g., "Dial 112 immediately if you are in danger.")
                2. "immediate_action_plan": (list of strings, e.g., ["Go to nearest police station", "Register Zero FIR"])
                3. "answer": (string, prioritized by user urgency)
                4. "legal_basis": (string)
                5. "procedure_steps": (list of strings)
                6. "important_notes": (list of strings)
                7. "sources": (list of objects with keys: "law", "section", "content", "citation")
                8. "disclaimer": (string)
                """
                
                if is_gemma:
                    full_prompt = f"{system_instruction}\n\n{prompt}\nIMPORTANT: Return ONLY valid JSON."
                    response = self.client.models.generate_content(
                        model=model_id,
                        contents=full_prompt,
                    )
                    text = response.text.strip()
                    if "```json" in text:
                        text = text.split("```json")[-1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[-1].split("```")[0].strip()
                    result = LegalResponse.model_validate_json(text)
                else:
                    response = self.client.models.generate_content(
                        model=model_id,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            response_schema=LegalResponse,
                        ),
                    )
                    result = response.parsed
                
                # Post-processing: Enforce Context-Aware Sources
                # The LLM often summarizes sources. We replace them with the actual context used.
                real_sources = []
                limit = 4 # Max sources to show
                
                # Map context to source objects
                if context:
                    for i, ctx in enumerate(context[:limit]):
                        chunk = ctx['chunk']
                        meta = chunk.get('metadata', {})
                        
                        # Use parent context if available for fuller text
                        text_content = chunk['text']
                        if ctx.get('parent_context'):
                            text_content = f"{ctx['parent_context']}\n\n[Clause]: {text_content}"
                        
                        real_sources.append(LegalSource(
                            law=str(meta.get('law', 'Unknown')),
                            section=str(meta.get('section', 'Unknown')),
                            citation=str(chunk.get('canonical_header', 'Unknown')),
                            content=text_content
                        ))
                    
                    result.sources = real_sources

                # Post-processing enforcement for Victim Context
                if user_context != "victim_distress":
                    result.safety_alert = None
                    result.immediate_action_plan = []
                
                return result
            except Exception as e:
                print(f"Model {model_id} failed: {e}")
                last_exception = e
        
        raise last_exception or Exception("Response generation failed with all models.")

if __name__ == "__main__":
    # Test Responder
    responder = LegalResponder()
    
    # Mock data based on orchestration output
    mock_query = "I have been robbed, what can I do?"
    mock_intent = {
        "category": "police_duty", 
        "key_entities": ["robbery"], 
        "user_context": "victim_distress"
    }
    mock_context = [
        {
            "chunk": {
                "canonical_header": "General SOP\nSection: Filing of FIR\nStep: Zero FIR",
                "text": "A Zero FIR can be filed in any police station regardless of jurisdiction. It is later transferred to the relevant station.",
                "metadata": {"law": "SOP", "section": "Zero FIR"}
            }
        },
        {
            "chunk": {
                "canonical_header": "BNS 2023\nSection 309\nRobbery",
                "text": "Whoever commits robbery shall be punished with rigorous imprisonment up to seven years.",
                "metadata": {"law": "BNS", "section": "309"}
            }
        }
    ]
    
    print("Testing Legal Responder (Victim-Centric)...")
    answer = responder.generate_response(mock_query, mock_context, mock_intent)
    print(json.dumps(answer.model_dump(), indent=2))
