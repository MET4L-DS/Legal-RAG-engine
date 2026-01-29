"""
Legal RAG System with LLM Integration.

This module provides the complete RAG system combining:
- Hierarchical retrieval
- Tier-specific prompt selection
- Google Gemini LLM integration
"""

from typing import Any, Optional

from ..models import SearchResult
from .retriever import HierarchicalRetriever


class LegalRAG:
    """Complete Legal RAG system combining retrieval with Gemini LLM generation.
    
    Supports procedural queries (Tier-1) with SOP-backed answers.
    """
    
    # Standard legal Q&A prompt
    SYSTEM_PROMPT = """You are a legal assistant specializing in Indian law (BNS, BNSS, BSA).
Your task is to answer questions using the provided legal extracts.

Instructions:
1. Carefully read ALL the provided legal extracts
2. Synthesize information from multiple sections if relevant
3. Always cite the specific Section and Chapter (e.g., "BSA Section 57")
4. If the extracts contain relevant information, provide a comprehensive answer
5. Only say you cannot find information if the extracts are truly unrelated to the question
6. Format your answer clearly with sections for: Definition, Procedure, Key Points (as applicable)"""
    
    # Procedural guidance prompt (Tier-1 feature)
    PROCEDURAL_PROMPT = """You are a legal assistant helping victims of crime in India understand their rights and the legal process.
Your task is to provide step-by-step procedural guidance using the provided materials.

The context contains:
- SOP (Standard Operating Procedure) blocks: Official police procedures and victim rights
- BNSS sections: Criminal procedure laws
- BNS sections: Criminal offense definitions

CRITICAL INSTRUCTIONS:
1. Structure your answer as STEP-BY-STEP GUIDANCE for the victim
2. Start with what the victim CAN DO IMMEDIATELY
3. Then explain what POLICE MUST DO (their duties)
4. Include TIME LIMITS where mentioned (e.g., "within 24 hours")
5. Cite sources using: SOP, BNSS Section X, BNS Section X
6. If police fail their duties, explain ESCALATION options
7. Use simple, empowering language - the reader is likely in distress
8. Prioritize SOP guidance over raw legal text

OUTPUT FORMAT:
## Immediate Steps
[What victim can do right now]

## Police Duties
[What police MUST do - cite SOP]

## Legal Rights
[Relevant law sections]

## Time Limits
[Any deadlines that apply]

## If Police Refuse
[Escalation steps]"""
    
    # Evidence & Investigation prompt (Tier-2 feature)
    EVIDENCE_PROMPT = """You are a legal assistant helping victims understand evidence collection and investigation standards in India.
Your task is to explain what proper evidence handling looks like and what happens if police fail to follow procedures.

The context contains:
- Crime Scene Manual: Official evidence collection and preservation procedures
- SOP: Standard Operating Procedures for investigations
- BNSS: Criminal procedure laws

CRITICAL INSTRUCTIONS:
1. Explain WHAT EVIDENCE should be collected for the specific crime
2. Describe HOW evidence should be properly collected and preserved
3. Highlight TIME LIMITS for evidence collection
4. Explain CONSEQUENCES if evidence is not properly handled (contamination, inadmissibility)
5. Cite sources: Crime Scene Manual, SOP, BNSS
6. If police failed, explain what legal recourse the victim has
7. Use technical terms but explain them simply

OUTPUT FORMAT:
## Required Evidence
[What evidence should be collected for this crime]

## Proper Procedure
[How evidence should be collected - cite Manual]

## Time Limits
[Critical time windows for evidence collection]

## If Procedure Not Followed
[Consequences - contamination, inadmissibility, case weakness]

## Legal Recourse
[What victim can do if evidence mishandled]"""
    
    # Compensation & Rehabilitation prompt (Tier-2 feature)
    COMPENSATION_PROMPT = """You are a legal assistant helping victims of crime in India understand their compensation and rehabilitation rights.
Your task is to explain what financial relief and support is available to victims.

The context contains:
- NALSA Compensation Scheme (2018): Victim compensation guidelines
- BNSS Section 396: Legal provision for victim compensation
- Other legal provisions

CRITICAL INSTRUCTIONS:
1. FIRST state whether conviction is required (IMPORTANT: for most schemes, conviction is NOT required)
2. List ALL types of compensation/support available (interim relief, final compensation, rehabilitation)
3. Explain the APPLICATION PROCESS step by step
4. State AMOUNT RANGES where mentioned
5. List DOCUMENTS REQUIRED for application
6. Mention AUTHORITIES to approach (DLSA, SLSA, etc.)
7. Include TIME LIMITS for applying
8. Cite sources: NALSA Scheme, BNSS

KEY FACT TO EMPHASIZE: Under NALSA Scheme, victim compensation does NOT require conviction of accused. Even if accused is acquitted or case is pending, victim can get compensation.

OUTPUT FORMAT:
## Eligibility
[Who can apply - emphasize conviction NOT required if applicable]

## Types of Compensation
[Interim relief, final compensation, rehabilitation support]

## How to Apply
[Step-by-step application process]

## Documents Required
[List of required documents]

## Amount Ranges
[Compensation amounts for different crimes]

## Where to Apply
[DLSA, SLSA, court - with contacts if available]

## Time Limits
[Deadlines for application]"""
    
    # General SOP prompt (Tier-3 feature) - Citizen-centric procedural guidance for all crimes
    GENERAL_SOP_PROMPT = """You are a legal assistant helping citizens of India understand what to do when they encounter a crime (robbery, theft, assault, murder, cybercrime, etc.).
Your task is to provide clear, citizen-centric procedural guidance using the provided materials.

The context contains:
- General SOP (BPR&D): Official procedures for all types of crimes
- BNSS sections: Criminal procedure laws
- BNS sections: Criminal offense definitions

CRITICAL INSTRUCTIONS:
1. Start with IMMEDIATE SAFETY steps for the citizen
2. Explain HOW TO FILE A COMPLAINT/FIR clearly
3. List what POLICE MUST DO (their duties under law)
4. Include TIME LIMITS where mentioned (e.g., "FIR within 24 hours")
5. Cite sources: General SOP, BNSS Section X, BNS Section X
6. If police refuse to act, explain ESCALATION options clearly
7. Use simple, action-oriented language
8. DO NOT include trauma-specific guidance (that's Tier-1)
9. DO NOT include detailed evidence procedures (that's Tier-2)

OUTPUT FORMAT:
## Immediate Steps (Citizen)
[What the citizen should do right now for safety and initial action]

## Police Duties
[What police MUST do - their legal obligations]

## Legal Basis
[Relevant BNSS/BNS sections briefly]

## Time Limits
[Any applicable deadlines]

## If Police Do Not Act
[Escalation: SHO -> SP -> Magistrate complaint]"""
    
    def __init__(
        self,
        retriever: HierarchicalRetriever,
        llm_client: Optional[Any] = None,
        model: str = "gemini-1.5-flash"
    ):
        """Initialize the RAG system.
        
        Args:
            retriever: Hierarchical retriever for document search
            llm_client: Google Gemini GenerativeModel (optional, for answer generation)
            model: LLM model to use (gemini-1.5-flash, gemini-1.5-pro, etc.)
        """
        self.retriever = retriever
        self.llm_client = llm_client
        self.model = model
    
    def query(self, question: str, generate_answer: bool = True, use_answer_units: bool = True) -> dict:
        """Answer a legal question using RAG.
        
        For procedural queries (Tier-1), uses SOP-backed procedural prompt.
        For Tier-2 queries, includes evidence/compensation context.
        
        Args:
            question: User's legal question
            generate_answer: Whether to generate LLM answer (requires llm_client)
            use_answer_units: Whether to use span-based answer units (Option B)
            
        Returns:
            Dictionary with retrieval results and optional LLM answer
        """
        # Retrieve relevant context
        retrieval_result = self.retriever.retrieve(question)
        
        response = {
            "question": question,
            "is_procedural": retrieval_result.is_procedural,
            "case_type": retrieval_result.case_type,
            "detected_stages": retrieval_result.detected_stages,
            # Tier-2 intent flags
            "needs_evidence": retrieval_result.needs_evidence,
            "needs_compensation": retrieval_result.needs_compensation,
            # Tier-3 intent flags
            "needs_general_sop": retrieval_result.needs_general_sop,
            "general_crime_type": retrieval_result.general_crime_type,
            "retrieval": {
                "documents": [self._format_result(r) for r in retrieval_result.documents],
                "chapters": [self._format_result(r) for r in retrieval_result.chapters],
                "sections": [self._format_result(r) for r in retrieval_result.sections],
                "subsections": [self._format_result(r) for r in retrieval_result.subsections],
                "sop_blocks": [self._format_result(r) for r in retrieval_result.sop_blocks],
                # Tier-2 results
                "evidence_blocks": [self._format_result(r) for r in retrieval_result.evidence_blocks],
                "compensation_blocks": [self._format_result(r) for r in retrieval_result.compensation_blocks],
                # Tier-3 results
                "general_sop_blocks": [self._format_result(r) for r in retrieval_result.general_sop_blocks]
            },
            "context": retrieval_result.context_text,
            "citations": retrieval_result.citations,  # Legacy string citations
            "structured_citations": [
                {
                    "source_type": sc.source_type,
                    "source_id": sc.source_id,
                    "display": sc.display,
                    "context_snippet": sc.context_snippet,
                    "relevance_score": sc.relevance_score,
                }
                for sc in retrieval_result.structured_citations
            ],  # New structured citations
            "answer": None,
            "answer_units": None,
            "min_citation_score": self.retriever.config.min_citation_score
        }
        
        # Generate answer if LLM client is available
        if generate_answer and self.llm_client and retrieval_result.context_text:
            # Try answer units first (Option B - span-based attribution)
            if use_answer_units:
                answer_units = self._generate_answer_units(
                    question,
                    retrieval_result.context_text,
                    is_procedural=retrieval_result.is_procedural,
                    needs_evidence=retrieval_result.needs_evidence,
                    needs_compensation=retrieval_result.needs_compensation,
                    needs_general_sop=retrieval_result.needs_general_sop
                )
                
                if answer_units:
                    response["answer_units"] = answer_units
                    # Also generate plain text answer for backward compatibility
                    response["answer"] = " ".join(u.get("text", "") for u in answer_units)
                else:
                    # Fallback to legacy answer generation
                    response["answer"] = self._generate_answer(
                        question, 
                        retrieval_result.context_text,
                        is_procedural=retrieval_result.is_procedural,
                        needs_evidence=retrieval_result.needs_evidence,
                        needs_compensation=retrieval_result.needs_compensation,
                        needs_general_sop=retrieval_result.needs_general_sop
                    )
            else:
                # Legacy answer generation
                response["answer"] = self._generate_answer(
                    question, 
                    retrieval_result.context_text,
                    is_procedural=retrieval_result.is_procedural,
                    needs_evidence=retrieval_result.needs_evidence,
                    needs_compensation=retrieval_result.needs_compensation,
                    needs_general_sop=retrieval_result.needs_general_sop
                )
        
        return response
    
    def _format_result(self, result: SearchResult) -> dict:
        """Format a search result for output."""
        formatted = {
            "citation": result.get_citation(),
            "text": result.text[:500] + "..." if len(result.text) > 500 else result.text,
            "score": round(result.score, 4),
            "level": result.level,
            "metadata": result.metadata
        }
        
        # Add doc_type indicator
        doc_type = result.metadata.get("doc_type", "")
        if doc_type == "sop":
            formatted["source_type"] = "SOP"
        elif doc_type == "evidence_manual":
            formatted["source_type"] = "Evidence Manual"
        elif doc_type == "compensation_scheme":
            formatted["source_type"] = "NALSA Scheme"
        elif doc_type == "general_sop":
            formatted["source_type"] = "General SOP"
        elif "BNSS" in result.doc_id:
            formatted["source_type"] = "BNSS"
        elif "BNS" in result.doc_id:
            formatted["source_type"] = "BNS"
        elif "BSA" in result.doc_id:
            formatted["source_type"] = "BSA"
        else:
            formatted["source_type"] = "Law"
        
        return formatted
    
    def _generate_answer(
        self, 
        question: str, 
        context: str, 
        is_procedural: bool = False,
        needs_evidence: bool = False,
        needs_compensation: bool = False,
        needs_general_sop: bool = False
    ) -> str:
        """Generate answer using Google Gemini with retry logic.
        
        Uses specialized prompts based on query type:
        - Procedural (Tier-1): SOP-backed guidance for sexual offences
        - Evidence (Tier-2): Crime scene/investigation standards
        - Compensation (Tier-2): Victim relief and rehabilitation
        - General SOP (Tier-3): Citizen-centric guidance for all crimes
        """
        import time
        
        # Select appropriate prompt based on query type
        # Priority: Tier-2 > Tier-1 > Tier-3 > Standard
        if needs_evidence:
            system_prompt = self.EVIDENCE_PROMPT
        elif needs_compensation:
            system_prompt = self.COMPENSATION_PROMPT
        elif is_procedural and not needs_general_sop:
            # Tier-1: Sexual offence procedural
            system_prompt = self.PROCEDURAL_PROMPT
        elif needs_general_sop:
            # Tier-3: General crime procedural
            system_prompt = self.GENERAL_SOP_PROMPT
        else:
            system_prompt = self.SYSTEM_PROMPT
        
        full_prompt = f"""{system_prompt}

Based on the following materials, answer the question.

Materials:
{context}

Question: {question}

Answer:"""
        
        # Models to try in order (from AI Studio dashboard - Jan 2026)
        # Prioritize models with available quota, avoid exhausted ones
        models_to_try = [
            # "gemini-3.0-flash",      # Newest, 0/20 RPD available
            "gemini-2.5-flash-lite",    # Good fallback, 0/20 RPD available 
            "gemma-3-27b-it",
            "gemma-3-12b-it",
        ]
        max_retries = 2
        
        for model in models_to_try:
            print(f"DEBUG: Attempting model: {model}")  # Debug logging
            for attempt in range(max_retries):
                try:
                    from google.genai import types
                    assert self.llm_client is not None, "LLM client not initialized"
                    response = self.llm_client.models.generate_content(
                        model=model,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.1,  # type: ignore
                            max_output_tokens=1000,  # type: ignore
                        )
                    )
                    print(f"DEBUG: Success with model: {model}")
                    return response.text
                except Exception as e:
                    error_str = str(e)
                    print(f"DEBUG: {model} failed (attempt {attempt + 1}): {error_str[:100]}")
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        # Rate limited - wait and retry or try next model
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 5  # 5s, 10s
                            print(f"DEBUG: Waiting {wait_time}s before retry...")
                            time.sleep(wait_time)
                            continue
                        else:
                            # Try next model
                            print(f"DEBUG: Moving to next model...")
                            break
                    else:
                        # Non-rate-limit error - try next model
                        print(f"DEBUG: Non-rate-limit error, trying next model...")
                        break
        
        return "Error: Rate limit exceeded on all models. Please wait a minute and try again."
    
    def _generate_answer_units(
        self, 
        question: str, 
        context: str,
        is_procedural: bool = False,
        needs_evidence: bool = False,
        needs_compensation: bool = False,
        needs_general_sop: bool = False
    ) -> list[dict]:
        """Generate structured answer units with verbatim/derived classification.
        
        This implements Option B from UPDATES.md - span-based attribution.
        Each answer unit is classified as:
        - "verbatim": Directly quoted from source (can be highlighted)
        - "derived": Synthesized guidance (cannot be highlighted)
        
        Returns list of answer unit dicts (to be parsed by adapter layer).
        """
        import time
        import json
        import re
        
        # Build tier-specific context for the prompt
        tier_context = ""
        if needs_evidence:
            tier_context = "Focus on evidence collection and investigation procedures."
        elif needs_compensation:
            tier_context = "Focus on compensation eligibility and application process."
        elif is_procedural and not needs_general_sop:
            tier_context = "Focus on procedural steps for sexual offence victims."
        elif needs_general_sop:
            tier_context = "Focus on citizen-centric procedural guidance."
        
        # Use the answer unit prompt
        from ..server.answer_units import get_answer_unit_prompt, parse_answer_units_response
        
        full_prompt = get_answer_unit_prompt(context, question, tier_context)
        
        # Models to try
        models_to_try = [
            "gemini-2.5-flash-lite",
            "gemma-3-27b-it",
            "gemma-3-12b-it",
        ]
        max_retries = 2
        
        for model in models_to_try:
            print(f"DEBUG [UNITS]: Attempting model: {model}")
            for attempt in range(max_retries):
                try:
                    from google.genai import types
                    assert self.llm_client is not None, "LLM client not initialized"
                    
                    response = self.llm_client.models.generate_content(
                        model=model,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.0,  # Deterministic for JSON
                            max_output_tokens=1500,
                        )
                    )
                    
                    print(f"DEBUG [UNITS]: Success with model: {model}")
                    
                    # Parse the response
                    units = parse_answer_units_response(response.text)
                    
                    # Convert to dicts for serialization
                    return [u.to_dict() for u in units]
                    
                except Exception as e:
                    error_str = str(e)
                    print(f"DEBUG [UNITS]: {model} failed (attempt {attempt + 1}): {error_str[:100]}")
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        if attempt < max_retries - 1:
                            time.sleep((attempt + 1) * 5)
                            continue
                        else:
                            break
                    else:
                        break
        
        # Fallback: return empty list (will use legacy answer generation)
        print("DEBUG [UNITS]: All models failed, falling back to legacy answer")
        return []
