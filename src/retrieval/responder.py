import os
import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class LegalSource(BaseModel):
    uid: str = Field(..., description="Unique deterministic ID like BNS_115_2 for cross-message persistence.")
    law: str = Field(..., description="The name of the Act or Scheme.")
    section: str = Field(..., description="The section or clause number.")
    content: str = Field(..., description="The relevant text content used.")
    citation: str = Field(..., description="Full canonical citation.")
    chip_label: str = Field(..., description="Short label for UI chip like [BNS:115] or [BNSS].")

class LegalResponse(BaseModel):
    answer: str = Field(..., description="Direct response to the user's query.")
    safety_alert: Optional[str] = Field(None, description="Immediate critical safety advice if in distress.")
    immediate_action_plan: List[str] = Field(default_factory=list, description="Top-priority chronological steps for the user.")
    legal_basis: str = Field(..., description="Summary of the legal basis for this answer.")
    procedure_steps: List[str] = Field(default_factory=list, description="Detailed procedural steps.")
    sources: List[LegalSource] = Field(..., description="Exact sources used from the provided context.")
    disclaimer: str = Field(..., description="Mandatory non-advisory legal disclaimer.")

def generate_source_uid(law: str, section: str) -> str:
    """Generate unique deterministic ID for a source."""
    law_clean = law.upper().strip()
    section_clean = section.strip() if section and section != "None" else "GENERAL"
    uid = f"{law_clean}_{section_clean}"
    # Clean up special characters
    uid = uid.replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").replace(".", "_")
    return uid

def generate_chip_label(law: str, section: str) -> str:
    """Generate display label for citation chip."""
    law_clean = law.upper().strip()
    if section and section != "None":
        # Extract main section number (e.g., "48" from "48" or "48(2)")
        section_main = section.split("(")[0].strip()
        return f"[{law_clean}:{section_main}]"
    return f"[{law_clean}]"

class LegalResponder:
    def __init__(self, model_ids: Optional[List[str]] = None):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("API Key (GEMINI_API_KEY or GOOGLE_API_KEY) not found in environment variables.")
        self.client = genai.Client(api_key=api_key)
        
        # Default model list if not provided
        default_models = ["gemma-3-4b-it", "gemini-2.5-flash-lite", "gemma-3-12b-it"]
        # Prioritize RESPONDER_MODELS, then fallback to LLM_MODELS
        env_models = os.getenv("RESPONDER_MODELS") or os.getenv("LLM_MODELS")
        if env_models:
            self.model_ids = [m.strip() for m in env_models.split(",")]
        else:
            self.model_ids = model_ids or default_models

    def generate_response(self, query: str, context: List[Dict[str, Any]], intent: Dict[str, Any]) -> LegalResponse:
        user_context = intent.get("user_context", "informational")
        
        system_instruction = f"""
        You are a supportive and highly precise Indian Legal Assistant. Your primary goal is to assist users, particularly victims of crimes, by providing clear, actionable, and empathetic guidance.
        
        USER CONTEXT: {user_context}
        
        VICTIM DISTRESS RULES (if context is 'victim_distress'):
        1. SAFETY FIRST: If the query indicates immediate danger, generate a 'safety_alert' (e.g., "Dial 112 immediately if you are in danger.").
        2. IMMEDIATE ACTION PLAN: Provide 2-4 actionable steps in 'immediate_action_plan' (e.g., ["Go to nearest police station", "Register Zero FIR"]).
        3. EMPATHETIC TONE: Use supportive language. Avoid legal jargon. Prioritize clarity and urgency.
        4. ANSWER FORMATTING: The 'answer' field MUST be formatted in Markdown. Include all important notes, caveats, and conditions directly in the answer. Use bolding and bullet points for readability.
        5. ACCESSIBILITY: If you use terms like 'Cognizable' or 'Bailable', explain them in simple terms in parentheses (e.g., 'Cognizable (a serious crime where police can arrest without a warrant)').
        
        INLINE CITATION RULES (CRITICAL - READ CAREFULLY):
        1. When making a legal claim, insert an inline citation using the law chip labels from the Legal Context.
        2. Use the EXACT chip label format shown in the context (e.g., [BNS:115], [BNSS:48], [NALSA], [SOP]).
        3. Place the citation IMMEDIATELY after the relevant phrase or sentence, before the period.
        4. Example: "You have the right to be informed about your arrest [BNSS:48]."
        5. Example: "Assault is punishable under Section 115 of BNS [BNS:115]."
        6. Do NOT invent chip labels. Only use the labels shown in the Legal Context below.
        7. In the sources JSON array, include the "uid" and "chip_label" exactly as they appear in the context.
        
        GENERAL / INFORMATIONAL RULES (if context is 'informational' or 'professional'):
        1. DO NOT generate 'safety_alert' or 'immediate_action_plan'. Leave them null/empty.
        2. ANSWER FORMATTING: The 'answer' field MUST be formatted in Markdown. Organize complex information into bullet points. Include all important notes and caveats directly in the answer.
        3. Only use the provided context. If the answer is not in the context, state it clearly.
        4. Citations must be exact. Cite the canonical header.
        5. Do not give personalized legal advice.
        6. Always include the mandatory disclaimer.
        """

        # Format context for the prompt with law-based labels for citations
        context_items = []
        for c in context:
            chunk = c['chunk']
            header = chunk['canonical_header']
            text = chunk['text']
            metadata = chunk.get('metadata', {})
            
            # Extract law and section from metadata
            law = metadata.get('law', 'UNKNOWN')
            section = metadata.get('section', 'None')
            
            # Generate unique ID and chip label
            uid = generate_source_uid(law, section)
            chip_label = generate_chip_label(law, section)
            
            # Store for later use in source generation
            c['uid'] = uid
            c['chip_label'] = chip_label
            
            # Check if parent context was expanded by Orchestrator
            if c.get("parent_context"):
                # Prepend parent context clearly
                text = f"[PARENT CONTEXT]: {c['parent_context']}\n[SPECIFIC CLAUSE]: {text}"
            
            # Format with chip label so LLM knows what to cite
            context_items.append(f"{chip_label}:\n{header}\n{text}")

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
                2. "immediate_action_plan": (array of strings, NEVER null - use [] if empty)
                3. "answer": (string, prioritized by user urgency - include all important notes and caveats here)
                4. "legal_basis": (string)
                5. "procedure_steps": (array of strings, NEVER null - use [] if empty)
                6. "sources": (array of objects with keys: "uid" (string like "BNS_115"), "law", "section", "content", "citation", "chip_label" (string like "[BNS:115]"))
                7. "disclaimer": (string)
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
                
                # Override sources with actual context metadata
                if context:
                    real_sources = []
                    for i, ctx in enumerate(context):
                        chunk = ctx['chunk']
                        meta = chunk.get('metadata', {})
                        text_content = chunk.get('text', '')[:500]  # Limit content length
                        
                        # Use pre-generated uid and chip_label from context assembly
                        real_sources.append(LegalSource(
                            uid=ctx.get('uid', f"UNKNOWN_{i}"),
                            law=str(meta.get('law', 'Unknown')),
                            section=str(meta.get('section', 'Unknown')),
                            citation=str(chunk.get('canonical_header', 'Unknown')),
                            content=text_content,
                            chip_label=ctx.get('chip_label', '[UNKNOWN]')
                        ))
                    
                    result.sources = real_sources

                # Post-processing enforcement for Victim Context
                if user_context != "victim_distress":
                    result.safety_alert = None
                    result.immediate_action_plan = []
                
                # Sanitize arrays to ensure they're never null
                if result.immediate_action_plan is None:
                    result.immediate_action_plan = []
                if result.procedure_steps is None:
                    result.procedure_steps = []
                
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
