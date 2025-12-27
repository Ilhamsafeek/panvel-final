# =====================================================
# FILE: app/services/claude_service.py
# Anthropic Claude API Integration for Contract Drafting
# UPDATED: Better error handling for analyze_correspondence
# =====================================================

from anthropic import Anthropic
from typing import Dict, List, Optional
import json
import logging
import time
from app.core.config import settings

logger = logging.getLogger(__name__)

class ClaudeService:
    """Service for AI-powered contract drafting using Claude API"""
    
    def __init__(self):
        """Initialize Anthropic Claude client"""
        try:
            api_key = settings.CLAUDE_API_KEY
            if not api_key:
                logger.warning(" CLAUDE_API_KEY not set - using mock mode")
                self.client = None
                self.model = "mock-model"
                self.max_tokens = 4096
                self.temperature = 0.7
            else:
                self.client = Anthropic(api_key=api_key)
                self.model = settings.CLAUDE_MODEL
                self.max_tokens = settings.CLAUDE_MAX_TOKENS
                self.temperature = settings.CLAUDE_TEMPERATURE
                logger.info(" Claude API client initialized successfully")
        except Exception as e:
            logger.error(f" Failed to initialize Claude client: {str(e)}")
            self.client = None
            self.model = "mock-model"
            self.max_tokens = 4096
            self.temperature = 0.7
    
    def draft_clause(
        self,
        clause_title: str,
        jurisdiction: str,
        business_context: Optional[str] = None,
        contract_type: Optional[str] = None,
        language: str = "en",
        party_role: Optional[str] = None
    ) -> Dict:
        """
        Draft a contract clause using Claude API
        
        Args:
            clause_title: Title/topic of the clause
            jurisdiction: Legal jurisdiction (e.g., "Qatar", "UAE", "UK")
            business_context: Additional business requirements
            contract_type: Type of contract (NDA, MSA, Service Agreement, etc.)
            language: Language for drafting (default: "en")
            party_role: User's role (client, contractor, consultant, subcontractor)
            
        Returns:
            Dict with clause_body, confidence_score, and suggestions
        """
        try:
            # Build context-aware prompt
            prompt = self._build_clause_prompt(
                clause_title=clause_title,
                jurisdiction=jurisdiction,
                business_context=business_context,
                contract_type=contract_type,
                language=language,
                party_role=party_role
            )
            
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extract response
            clause_text = message.content[0].text
            
            # Parse structured response
            result = self._parse_clause_response(clause_text)
            
            logger.info(f"Claude successfully drafted clause: {clause_title}")
            
            return {
                "clause_body": result.get("clause_body", clause_text),
                "confidence_score": result.get("confidence", 0.9),
                "suggestions": result.get("suggestions", []),
                "ai_generated": True,
                "model_used": self.model
            }
            
        except Exception as e:
            logger.error(f"Claude API error: {str(e)}")
            raise Exception(f"Failed to draft clause: {str(e)}")
    
    def _build_clause_prompt(
        self,
        clause_title: str,
        jurisdiction: str,
        business_context: Optional[str],
        contract_type: Optional[str],
        language: str,
        party_role: Optional[str]
    ) -> str:
        """Build comprehensive prompt for Claude"""
        
        prompt = f"""You are an expert contract lawyer specializing in {jurisdiction} law. Draft a professional contract clause with the following specifications:

**Clause Title:** {clause_title}
**Contract Type:** {contract_type or 'General Agreement'}
**Jurisdiction:** {jurisdiction}
**Party Role:** {party_role or 'Not specified'}
**Language:** {language}
"""
        
        if business_context:
            prompt += f"\n**Business Context:** {business_context}\n"
        
        prompt += """
**Requirements:**
1. Draft clear, legally sound language appropriate for the jurisdiction
2. Include standard legal protections and best practices
3. Make the clause balanced and fair to both parties
4. Use formal legal terminology appropriate for business contracts
5. Ensure compliance with local regulations and laws
6. Structure the clause with proper numbering and sub-clauses if needed

**Output Format:**
Provide the clause text in a professional format, followed by:
- [SUGGESTIONS]: List 2-3 alternative approaches or considerations
- [CONFIDENCE]: Rate your confidence (0.7-0.95)

Draft the clause now:"""
        
        return prompt
    
    def _parse_clause_response(self, response_text: str) -> Dict:
        """Parse Claude's response to extract clause and metadata"""
        
        parts = response_text.split("[SUGGESTIONS]")
        clause_body = parts[0].strip()
        
        suggestions = []
        confidence = 0.9  # Default
        
        if len(parts) > 1:
            remaining = parts[1]
            
            # Extract suggestions
            if "[CONFIDENCE]" in remaining:
                sugg_part, conf_part = remaining.split("[CONFIDENCE]")
                suggestions_text = sugg_part.strip()
                
                # Parse suggestions (bullet points or numbered list)
                for line in suggestions_text.split("\n"):
                    line = line.strip()
                    if line and (line.startswith("-") or line.startswith("•") or line[0].isdigit()):
                        suggestions.append(line.lstrip("-•0123456789. "))
                
                # Extract confidence
                try:
                    conf_text = conf_part.strip()
                    # Extract number from text
                    import re
                    match = re.search(r'0\.\d+', conf_text)
                    if match:
                        confidence = float(match.group())
                except:
                    pass
        
        return {
            "clause_body": clause_body,
            "suggestions": suggestions[:3],  # Max 3
            "confidence": confidence
        }
    def generate_full_contract(
        self,
        contract_type: str,
        party_a: str,
        party_b: str,
        jurisdiction: str,
        key_terms: Dict,
        language: str = "en"
    ) -> Dict:
        """
        Generate a complete contract draft using Claude's natural legal reasoning
        """
        try:
            # Extract required clauses if provided
            required_clauses = key_terms.get("REQUIRED CLAUSES (MUST INCLUDE)", "")
            additional_requirements = key_terms.get("Additional Requirements", "")
            
            # Build simple key terms list
            key_terms_text = "\n".join([
                f"- {key}: {value}" 
                for key, value in key_terms.items() 
                if key not in ["REQUIRED CLAUSES (MUST INCLUDE)", "Additional Requirements"]
            ])
            
            # Enhanced prompt emphasizing legal enforceability
            prompt = f"""Draft a comprehensive, contractually and legally binding {contract_type} contract that is fully enforceable under {jurisdiction} law.

    **PARTIES:**
    - Party A: {party_a}
    - Party B: {party_b}

    **JURISDICTION:** {jurisdiction}

    **KEY TERMS:**
    {key_terms_text}

    **REQUIRED CLAUSES (must include these specific provisions with full legal detail):**
    {required_clauses if required_clauses else "Include all standard clauses necessary for a legally binding contract"}

    **ADDITIONAL REQUIREMENTS:**
    {additional_requirements if additional_requirements else "None"}

    ---

    **CRITICAL REQUIREMENTS:**

    This contract must be **contractually and legally binding** with:

    1. **Complete legal enforceability** - Include all elements required for a valid, binding contract under {jurisdiction} law
    2. **Comprehensive rights and obligations** - Clearly define what each party must do, may do, and cannot do
    3. **Enforceable remedies** - Specify consequences for breach, termination rights, and dispute resolution mechanisms
    4. **All required clauses fully developed** - Each clause must include detailed provisions, sub-clauses, procedures, and timelines
    5. **No placeholders** - Use actual dates, values, and specific terms provided. No [TBD], [INSERT], or generic text
    6. **Production-ready quality** - This contract should be ready for signature and legal enforcement

    **DELIVERABLE:**
    - Minimum 3,500 words with thorough legal detail
    - Professional contract language suitable for commercial transactions
    - All provisions must be specific, measurable, and actionable
    - Include proper definitions, cross-references, and legal protections

    **FORMAT:**
    - Use clean HTML: <h2> for sections, <h3> for subsections, <p> for paragraphs, <strong> for defined terms
    - Wrap in: <div class="contract-document">...</div>
    - No markdown code blocks

    Generate the complete, legally binding contract now:"""

            # Call Claude with higher token limit
            message = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}]
            )
            
            contract_text = message.content[0].text
            
            # Clean up any markdown artifacts
            contract_text = contract_text.strip()
            for marker in ["```html", "```"]:
                if contract_text.startswith(marker):
                    contract_text = contract_text[len(marker):].strip()
                if contract_text.endswith("```"):
                    contract_text = contract_text[:-3].strip()
            
            word_count = len(contract_text.split())
            tokens_used = message.usage.input_tokens + message.usage.output_tokens
            
            logger.info(f"✅ Claude generated legally binding {contract_type}: {word_count} words, {tokens_used} tokens")
            
            # Warn if content seems too short for a binding contract
            if word_count < 2500:
                logger.warning(f"⚠️ Generated contract may lack sufficient detail for enforceability: {word_count} words")
            
            return {
                "contract_text": contract_text,
                "ai_generated": True,
                "model_used": self.model,
                "word_count": word_count,
                "tokens_used": tokens_used,
                "formatted": True,
                "format_type": "html"
            }
            
        except Exception as e:
            logger.error(f"❌ Claude API error: {str(e)}")
            raise Exception(f"Failed to generate contract: {str(e)}")
    
    def analyze_contract_risks(
        self,
        contract_text: str,
        party_role: str,
        jurisdiction: str
    ) -> Dict:
        """
        Analyze contract for potential risks and red flags
        
        Args:
            contract_text: Full contract text
            party_role: User's role (client, contractor, etc.)
            jurisdiction: Legal jurisdiction
            
        Returns:
            Dict with risk analysis results
        """
        try:
            prompt = f"""You are a contract risk analysis expert. Analyze the following contract from the perspective of the {party_role} under {jurisdiction} law.

**Contract Text:**
{contract_text[:3000]}  # Limit for token management

**Analysis Required:**
1. Identify HIGH-RISK clauses that could cause legal or financial harm
2. Flag MEDIUM-RISK items needing negotiation
3. Note any MISSING standard protections
4. Check compliance with {jurisdiction} regulations
5. Suggest improvements

**Output Format:**
[HIGH-RISK]
- List critical issues

[MEDIUM-RISK]
- List moderate concerns

[MISSING]
- List missing protections

[RECOMMENDATIONS]
- Provide 3-5 actionable suggestions

Analyze now:"""
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,  # Lower temp for factual analysis
                messages=[{"role": "user", "content": prompt}]
            )
            
            analysis_text = message.content[0].text
            
            # Parse results
            risks = self._parse_risk_analysis(analysis_text)
            
            logger.info(f"Claude completed risk analysis for {party_role}")
            
            return risks
            
        except Exception as e:
            logger.error(f"Claude API error in risk analysis: {str(e)}")
            raise Exception(f"Failed to analyze risks: {str(e)}")
    
    def _parse_risk_analysis(self, analysis_text: str) -> Dict:
        """Parse risk analysis response"""
        
        result = {
            "high_risk": [],
            "medium_risk": [],
            "missing": [],
            "recommendations": [],
            "overall_risk_score": 0.5
        }
        
        sections = {
            "[HIGH-RISK]": "high_risk",
            "[MEDIUM-RISK]": "medium_risk",
            "[MISSING]": "missing",
            "[RECOMMENDATIONS]": "recommendations"
        }
        
        current_section = None
        for line in analysis_text.split("\n"):
            line = line.strip()
            
            # Check for section headers
            for header, key in sections.items():
                if header in line:
                    current_section = key
                    break
            
            # Add items to current section
            if current_section and line and (line.startswith("-") or line.startswith("•") or line[0].isdigit()):
                item = line.lstrip("-•0123456789. ")
                if item:
                    result[current_section].append(item)
        
        # Calculate risk score
        high_count = len(result["high_risk"])
        medium_count = len(result["medium_risk"])
        result["overall_risk_score"] = min(0.9, 0.3 + (high_count * 0.15) + (medium_count * 0.05))
        
        return result
    
    # =====================================================
    # CORRESPONDENCE ANALYSIS METHOD - FIXED ERROR HANDLING
    # =====================================================
    def analyze_correspondence(
        self,
        query: str,
        documents: List[Dict],
        analysis_mode: str = "document",
        tone: str = "professional",
        urgency: str = "normal",
        language: str = "en",
        jurisdiction: str = "Qatar"
    ) -> Dict:
        """
        Analyze correspondence and provide guidance using Claude AI
        
        IMPORTANT: This method ALWAYS returns a Dict, never None
        
        Args:
            query: User's question or analysis request
            documents: List of document metadata and content
            analysis_mode: 'project' or 'document' level analysis
            tone: Communication tone (professional, formal, friendly)
            urgency: Urgency level (low, normal, high, critical)
            language: Response language (en, ar)
            jurisdiction: Legal jurisdiction (default: Qatar)
        
        Returns:
            Dict with analysis results, recommendations, and metadata
            NEVER returns None - always returns a valid Dict
        """
        start_time = time.time()
        
        try:
            # Check if Claude client is available
            if not self.client:
                logger.warning(" Claude API not available - using fallback analysis")
                return self._generate_fallback_correspondence_analysis(
                    query, documents, analysis_mode, tone, urgency, language, jurisdiction
                )
            
            # Build context from documents
            document_context = "\n\n".join([
                f"Document {i+1}: {doc.get('name', 'Unknown')}\n"
                f"Type: {doc.get('type', 'N/A')}\n"
                f"Contract: {doc.get('contract_title', 'N/A')}\n"
                f"Date: {doc.get('date', 'N/A')}\n"
                f"Content Preview: {doc.get('content_preview', doc.get('contract_content', 'No preview available'))[:300]}..."
                for i, doc in enumerate(documents[:10])  # Limit to 10 documents
            ])
            
            # Build prompt based on analysis mode and parameters
            if analysis_mode == "project":
                mode_context = f"You are analyzing multiple documents from a project to provide comprehensive guidance on: {query}"
            else:
                mode_context = f"You are analyzing specific document(s) to provide focused guidance on: {query}"
            
            tone_guidance = {
                "professional": "Use clear, professional business language",
                "formal": "Use formal legal and contractual language",
                "friendly": "Use accessible, helpful language while maintaining professionalism",
                "appreciative": "Use warm, grateful tone",
                "assertive": "Use direct, confident language",
                "cautionary": "Use careful, warning tone",
                "conciliatory": "Use diplomatic language",
                "consultative": "Use expert advisory tone",
                "convincing": "Use persuasive language",
                "enthusiastic": "Use energetic, positive tone",
                "motivating": "Use inspiring language"
            }.get(tone, "Use professional language")
            
            urgency_context = {
                "low": "This is a routine inquiry requiring standard analysis",
                "normal": "This requires standard attention and analysis",
                "high": "This requires priority attention with actionable recommendations",
                "critical": "This is urgent and requires immediate actionable guidance"
            }.get(urgency, "Standard analysis")
            
            prompt = f"""You are an expert contract management and correspondence specialist for construction and engineering projects in {jurisdiction}.

{mode_context}

Context Information:
- Analysis Mode: {analysis_mode.upper()}
- Number of Documents: {len(documents)}
- Jurisdiction: {jurisdiction}
- Urgency Level: {urgency.upper()}

DOCUMENTS BEING ANALYZED:
{document_context}

USER QUERY:
{query}

INSTRUCTIONS:
1. {tone_guidance}
2. {urgency_context}
3. Provide analysis in {"Arabic and English" if language == "ar" else "English"}
4. Structure your response with:
   - Executive Summary (2-3 sentences)
   - Detailed Analysis
   - Key Points (bullet list)
   - Recommendations (specific, actionable)
   - Suggested Next Steps
   - Risk Assessment (if applicable)
   - Contractual References (cite specific clauses if relevant)

5. For {jurisdiction} context, consider:
   - Qatar Civil Code requirements
   - QFCRA compliance where applicable
   - Local construction industry practices
   - Arabic and English contract interpretation

Provide comprehensive, actionable guidance that helps resolve the correspondence issue effectively."""

            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extract response
            response_text = message.content[0].text
            tokens_used = message.usage.input_tokens + message.usage.output_tokens
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Parse structured elements from response
            key_points = self._extract_key_points(response_text)
            recommendations = self._extract_recommendations(response_text)
            suggested_actions = self._extract_suggested_actions(response_text)
            
            # Calculate confidence score based on response quality
            confidence_score = self._calculate_confidence(
                response_text,
                len(documents),
                urgency
            )
            
            logger.info(f" Correspondence analysis completed: {tokens_used} tokens, {processing_time_ms}ms")
            
            return {
                "analysis_text": response_text,
                "confidence_score": confidence_score,
                "tokens_used": tokens_used,
                "processing_time_ms": processing_time_ms,
                "key_points": key_points,
                "recommendations": recommendations,
                "suggested_actions": suggested_actions,
                "analysis_mode": analysis_mode,
                "document_count": len(documents),
                "model_used": self.model
            }
            
        except Exception as e:
            logger.error(f" Correspondence analysis error: {str(e)}")
            # CRITICAL: Return fallback instead of raising exception
            return self._generate_fallback_correspondence_analysis(
                query, documents, analysis_mode, tone, urgency, language, jurisdiction
            )

    def _generate_fallback_correspondence_analysis(
        self,
        query: str,
        documents: List[Dict],
        analysis_mode: str,
        tone: str,
        urgency: str,
        language: str,
        jurisdiction: str
    ) -> Dict:
        """
        Generate fallback analysis when Claude API is unavailable
        ALWAYS returns a valid Dict, never None
        """
        
        doc_list = "\n".join([
            f"• {doc.get('name', 'Unknown')} - {doc.get('contract_title', 'N/A')}"
            for doc in documents[:10]
        ])
        
        analysis_text = f"""**CORRESPONDENCE ANALYSIS**
        
**Query:** {query}

**Analysis Mode:** {analysis_mode.upper()}
**Documents Reviewed:** {len(documents)} document(s)
**Jurisdiction:** {jurisdiction}
**Urgency:** {urgency.upper()}

**EXECUTIVE SUMMARY:**
A preliminary analysis has been completed based on the available documents and your query. This analysis provides foundational guidance. For enhanced AI-powered insights with detailed legal analysis, please ensure the Claude API is properly configured.

**DOCUMENTS ANALYZED:**
{doc_list}

**DETAILED ANALYSIS:**

Based on the information provided and general {jurisdiction} contractual principles, the following considerations apply:

1. **Contractual Position**
   - Review all relevant contract clauses carefully
   - Ensure compliance with notification and procedural requirements
   - Document all communications and decisions properly
   - Consider the timing and deadlines specified in the contract

2. **Legal and Compliance Considerations**
   - Follow {jurisdiction} legal requirements
   - Ensure all communications are properly documented
   - Maintain professional and formal correspondence
   - Preserve evidence and supporting documentation

3. **Risk Assessment**
   - Identify potential legal and financial risks
   - Evaluate impact on project timelines
   - Consider reputational factors
   - Assess need for legal counsel consultation

**KEY POINTS:**
• Comprehensive document review is essential
• Legal compliance must be maintained throughout
• Proper documentation is critical
• Professional communication tone is required
• Deadlines and timelines must be monitored

**RECOMMENDATIONS:**
1. Conduct thorough review of all contract documentation
2. Consult with legal counsel for specific guidance
3. Prepare formal written response following proper procedures
4. Maintain detailed records of all communications
5. Follow established dispute resolution mechanisms

**SUGGESTED NEXT STEPS:**
1. Schedule meeting with relevant stakeholders
2. Gather all supporting documentation and evidence
3. Prepare draft response for legal review
4. Establish timeline for response and follow-up actions
5. Document all decisions and rationale

**IMPORTANT NOTE:**
This is a preliminary analysis based on general principles. For comprehensive AI-powered legal analysis specific to your situation, please configure the Claude API service. For critical matters, consultation with qualified legal counsel is strongly recommended.

**ANALYSIS METADATA:**
- Analysis Type: Fallback/Basic
- AI Service: Mock Mode
- Confidence Level: Preliminary
"""
        
        return {
            "analysis_text": analysis_text,
            "confidence_score": 65.0,
            "tokens_used": 0,
            "processing_time_ms": 50,
            "key_points": [
                "Comprehensive document review required",
                "Legal compliance must be maintained",
                "Proper documentation is critical",
                "Professional communication essential",
                "Monitor deadlines and timelines"
            ],
            "recommendations": [
                "Review all contract documentation thoroughly",
                "Consult with legal counsel",
                "Prepare formal written response",
                "Maintain detailed records",
                "Follow dispute resolution procedures"
            ],
            "suggested_actions": [
                "Schedule stakeholder meeting",
                "Gather supporting documentation",
                "Prepare draft response for review",
                "Establish response timeline",
                "Document all decisions"
            ],
            "analysis_mode": analysis_mode,
            "document_count": len(documents),
            "model_used": "fallback-mock",
            "warning": "Claude API not available - using fallback analysis. Configure Claude API for enhanced analysis."
        }

    def _extract_key_points(self, text: str) -> List[str]:
        """Extract key points from analysis text"""
        lines = text.split('\n')
        key_points = []
        
        in_key_points_section = False
        for line in lines:
            line = line.strip()
            if 'key point' in line.lower() or 'key finding' in line.lower():
                in_key_points_section = True
                continue
            if in_key_points_section and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                point = line.lstrip('-•* ')
                if point:
                    key_points.append(point)
            elif in_key_points_section and line and not line[0].isdigit():
                if 'recommendation' in line.lower():
                    break
        
        return key_points[:5] if key_points else ["Analysis completed successfully", "Review all documentation", "Consult legal team as needed"]

    def _extract_recommendations(self, text: str) -> List[str]:
        """Extract recommendations from analysis text"""
        lines = text.split('\n')
        recommendations = []
        
        in_recommendations_section = False
        for line in lines:
            line = line.strip()
            if 'recommendation' in line.lower():
                in_recommendations_section = True
                continue
            if in_recommendations_section and (line.startswith('-') or line.startswith('•') or line.startswith('*') or (line and line[0].isdigit())):
                rec = line.lstrip('-•*0123456789. ')
                if rec:
                    recommendations.append(rec)
            elif in_recommendations_section and line and 'next step' in line.lower():
                break
        
        return recommendations[:5] if recommendations else ["Review analysis and consult with legal team", "Document all decisions", "Follow proper procedures"]

    def _extract_suggested_actions(self, text: str) -> List[str]:
        """Extract suggested actions from analysis text"""
        lines = text.split('\n')
        actions = []
        
        in_actions_section = False
        for line in lines:
            line = line.strip()
            if 'next step' in line.lower() or 'suggested action' in line.lower():
                in_actions_section = True
                continue
            if in_actions_section and (line.startswith('-') or line.startswith('•') or line.startswith('*') or (line and line[0].isdigit())):
                action = line.lstrip('-•*0123456789. ')
                if action:
                    actions.append(action)
            elif in_actions_section and line and 'risk' in line.lower():
                break
        
        return actions[:5] if actions else ["Schedule follow-up meeting", "Document decision in contract file", "Prepare formal response"]

    def _calculate_confidence(self, response_text: str, document_count: int, urgency: str) -> float:
        """Calculate confidence score based on response quality and context"""
        base_confidence = 85.0
        
        # Adjust based on response length and detail
        if len(response_text) > 1000:
            base_confidence += 5
        elif len(response_text) < 300:
            base_confidence -= 10
        
        # Adjust based on document count
        if document_count >= 3:
            base_confidence += 5
        elif document_count == 1:
            base_confidence -= 5
        
        # Adjust based on urgency
        if urgency == "critical":
            base_confidence -= 5  # More conservative for critical items
        
        # Check for structured elements
        if "recommendation" in response_text.lower():
            base_confidence += 3
        if "risk" in response_text.lower():
            base_confidence += 2
        
        return min(max(base_confidence, 60.0), 98.0)


# Global instance
try:
    claude_service = ClaudeService()
    logger.info(" Claude service instance created successfully")
except Exception as e:
    logger.error(f" Failed to create Claude service instance: {str(e)}")
    # Create a fallback instance that will use mock mode
    claude_service = ClaudeService()




# =====================================================
# Add this method to: app/services/claude_service.py
# Inside the ClaudeService class
# =====================================================

def analyze_contract_risks_detailed(
    self,
    contract_content: str,
    contract_title: str = "Contract",
    contract_type: str = "General Agreement",
    jurisdiction: str = "Qatar",
    party_role: str = "client"
) -> Dict:
    """
    Comprehensive contract risk analysis using Claude AI
    
    Args:
        contract_content: The full contract text or key clauses
        contract_title: Title of the contract
        contract_type: Type of contract (NDA, Service Agreement, etc.)
        jurisdiction: Legal jurisdiction
        party_role: Perspective for analysis (client, contractor, etc.)
    
    Returns:
        Dict with structured risk analysis including scores, items, and recommendations
    """
    
    if not self.client:
        logger.warning("Claude client not available for risk analysis")
        raise ValueError("Claude API not configured")
    
    try:
        prompt = f"""You are an expert legal contract risk analyst specializing in {jurisdiction} and GCC region commercial law. 
Analyze the following contract comprehensively from the perspective of a {party_role}.

═══════════════════════════════════════════════════════
CONTRACT DETAILS
═══════════════════════════════════════════════════════
Title: {contract_title}
Type: {contract_type}
Jurisdiction: {jurisdiction}
Analyzing for: {party_role}

═══════════════════════════════════════════════════════
CONTRACT CONTENT
═══════════════════════════════════════════════════════
{contract_content[:10000] if contract_content else "No specific content provided - analyze standard risks for this contract type"}

═══════════════════════════════════════════════════════
ANALYSIS REQUIREMENTS
═══════════════════════════════════════════════════════

Analyze the contract considering:
1. **Legal Risks**: Termination rights, liability exposure, indemnification
2. **Financial Risks**: Payment terms, penalties, guarantees
3. **Operational Risks**: Performance obligations, timelines, deliverables  
4. **Compliance Risks**: Qatar law alignment, QFCRA regulations, data protection
5. **Dispute Risks**: Arbitration clauses, governing law, jurisdiction

For Qatar-specific analysis, consider:
- Qatar Civil Code (Law No. 22 of 2004)
- Qatar Commercial Companies Law
- QFCRA regulations (for financial contracts)
- Qatar Arbitration Law No. 2 of 2017
- Qatar Personal Data Privacy Protection Law
- Standard GCC commercial practices

═══════════════════════════════════════════════════════
REQUIRED OUTPUT FORMAT (JSON ONLY)
═══════════════════════════════════════════════════════

Respond ONLY with this exact JSON structure - no additional text:

{{
    "overall_score": <0-100 safety score - higher is safer>,
    "high_risks": <integer count>,
    "medium_risks": <integer count>,
    "low_risks": <integer count>,
    "executive_summary": "<2-3 sentence summary of key findings and overall risk posture>",
    "risk_items": [
        {{
            "type": "<termination|liability|payment|compliance|confidentiality|intellectual_property|indemnification|force_majeure|dispute_resolution|regulatory|insurance|performance>",
            "severity": "<high|medium|low>",
            "score": <0-100 risk score - higher is more risky>,
            "issue": "<concise issue title - max 10 words>",
            "description": "<detailed explanation of the risk - 2-3 sentences>",
            "clause_reference": "<specific clause number or section name>",
            "recommendation": "<specific actionable recommendation - 1-2 sentences>",
            "qatar_law_reference": "<relevant Qatar law article or regulation>",
            "business_impact": "<financial|operational|reputational|legal>"
        }}
    ],
    "compliance_status": {{
        "qfcra_compliant": <true|false>,
        "qatar_civil_code_aligned": <true|false>,
        "data_protection_compliant": <true|false>,
        "notes": "<brief compliance notes>"
    }},
    "recommendations_summary": [
        "<top priority recommendation>",
        "<second priority recommendation>",
        "<third priority recommendation>"
    ],
    "missing_clauses": [
        "<missing clause 1>",
        "<missing clause 2>"
    ]
}}

IMPORTANT GUIDELINES:
- Identify at least 6-10 risk items covering different categories
- Be specific with clause references when possible
- Provide actionable, practical recommendations
- Consider both parties' perspectives but prioritize {party_role}'s interests
- Flag any Qatar-specific compliance concerns
- Overall score should reflect: 90-100 (low risk), 70-89 (moderate), 50-69 (elevated), below 50 (high risk)"""

        logger.info(f" Sending contract to Claude for detailed risk analysis...")
        
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0.15,  # Low temperature for consistent, factual analysis
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        logger.info(f"📥 Received risk analysis response: {len(response_text)} chars")
        
        # Extract JSON from response
        import re
        import json
        
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            raise ValueError("No valid JSON found in Claude response")
        
        analysis = json.loads(json_match.group())
        
        # Validate and normalize the response
        analysis = self._normalize_risk_analysis(analysis)
        
        logger.info(f" Risk analysis complete - Score: {analysis['overall_score']}")
        
        return analysis
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in risk analysis: {str(e)}")
        raise ValueError(f"Failed to parse AI response: {str(e)}")
    except Exception as e:
        logger.error(f"Error in Claude risk analysis: {str(e)}")
        raise


def _normalize_risk_analysis(self, analysis: Dict) -> Dict:
    """Normalize and validate risk analysis response"""
    
    # Ensure all required fields exist
    analysis.setdefault("overall_score", 70)
    analysis.setdefault("executive_summary", "Risk analysis completed. Review detailed findings below.")
    analysis.setdefault("risk_items", [])
    analysis.setdefault("compliance_status", {
        "qfcra_compliant": True,
        "qatar_civil_code_aligned": True,
        "data_protection_compliant": True,
        "notes": ""
    })
    analysis.setdefault("recommendations_summary", [])
    analysis.setdefault("missing_clauses", [])
    
    # Count risks by severity
    risk_items = analysis.get("risk_items", [])
    analysis["high_risks"] = len([r for r in risk_items if r.get("severity") == "high"])
    analysis["medium_risks"] = len([r for r in risk_items if r.get("severity") == "medium"])
    analysis["low_risks"] = len([r for r in risk_items if r.get("severity") == "low"])
    
    # Normalize each risk item
    for item in risk_items:
        item.setdefault("type", "general")
        item.setdefault("severity", "medium")
        item.setdefault("score", 50)
        item.setdefault("issue", "Risk identified")
        item.setdefault("description", "Review this section carefully.")
        item.setdefault("clause_reference", "General")
        item.setdefault("recommendation", "Consult with legal team.")
        item.setdefault("qatar_law_reference", "")
        item.setdefault("business_impact", "operational")
        
        # Ensure score is within bounds
        item["score"] = max(0, min(100, int(item.get("score", 50))))
    
    # Sort risk items by severity (high first, then by score)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    analysis["risk_items"] = sorted(
        risk_items,
        key=lambda x: (severity_order.get(x.get("severity", "medium"), 1), -x.get("score", 0))
    )
    
    # Ensure overall score is within bounds
    analysis["overall_score"] = max(0, min(100, int(analysis.get("overall_score", 70))))
    
    return analysis


def generate_risk_mitigation_text(
    self,
    risk_item: Dict,
    contract_type: str = "General Agreement",
    jurisdiction: str = "Qatar"
) -> str:
    """
    Generate specific mitigation language for a risk item
    
    Args:
        risk_item: The risk item to generate mitigation for
        contract_type: Type of contract
        jurisdiction: Legal jurisdiction
    
    Returns:
        Suggested contract language to mitigate the risk
    """
    
    if not self.client:
        return f"Recommended: {risk_item.get('recommendation', 'Consult legal team')}"
    
    try:
        prompt = f"""As a legal contract expert in {jurisdiction}, generate specific contract clause language to mitigate this risk:

Risk: {risk_item.get('issue')}
Description: {risk_item.get('description')}
Current Clause: {risk_item.get('clause_reference')}
Contract Type: {contract_type}

Generate a replacement or additional clause that:
1. Addresses the identified risk
2. Is legally compliant with {jurisdiction} law
3. Provides balanced protection
4. Uses clear, professional legal language

Provide ONLY the suggested clause text, no explanation needed."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return message.content[0].text.strip()
        
    except Exception as e:
        logger.error(f"Error generating mitigation text: {str(e)}")
        return f"Recommended: {risk_item.get('recommendation', 'Consult legal team')}"





# =====================================================
# ADD THIS METHOD TO: app/services/claude_service.py
# Add it inside the ClaudeService class
# =====================================================
async def generate_text(self, prompt: str, max_tokens: int = 2000) -> str:
    """Generate text using Claude API"""
    if not self.client:
        raise ValueError("Claude API not configured")
    
    message = self.client.messages.create(
        model=self.model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    return message.content[0].text



def _generate_mock_obligations_response(self) -> str:
    """Generate mock obligations response for testing"""
    mock_obligations = [
        {
            "title": "Payment Obligation",
            "description": "Timely payment for the work completed as per the agreed terms and milestone schedule. Payment shall be made within 30 days of invoice submission.",
            "type": "payment"
        },
        {
            "title": "Provision of Information",
            "description": "Provide necessary information, specifications, and resources for the contractor to complete the work efficiently and according to requirements.",
            "type": "coordination"
        },
        {
            "title": "Timely Completion",
            "description": "Complete the specified work within the agreed timeline and notify of any potential delays in advance to allow for appropriate mitigation.",
            "type": "timely_completion"
        },
        {
            "title": "Quality Standards Compliance",
            "description": "Ensure all work meets industry standards and specific quality requirements outlined in the agreement, subject to inspection and acceptance.",
            "type": "performance"
        },
        {
            "title": "Insurance Coverage",
            "description": "Maintain appropriate insurance coverage including liability, workers' compensation, and professional indemnity as specified in the contract.",
            "type": "insurance"
        },
        {
            "title": "Reporting Requirements",
            "description": "Provide regular progress updates and reports on work completion, issues encountered, and any variations from the original scope.",
            "type": "reporting"
        },
        {
            "title": "Compliance with Laws",
            "description": "Follow all applicable laws, regulations, and safety standards relevant to the work being performed under this contract.",
            "type": "compliance"
        }
    ]
    
    import json
    return json.dumps(mock_obligations)


# =====================================================
# ALSO ADD THIS ENHANCED METHOD FOR OBLIGATION EXTRACTION
# =====================================================

async def extract_obligations_from_contract(
    self,
    contract_content: str,
    contract_type: str = "General Agreement",
    party_role: str = "both"
) -> List[Dict]:
    """
    Extract contractual obligations using AI analysis
    
    Args:
        contract_content: Full contract text
        contract_type: Type of contract
        party_role: Extract for 'contractor', 'client', or 'both'
        
    Returns:
        List of extracted obligations with metadata
    """
    
    prompt = f"""You are a legal contract analyst. Analyze this {contract_type} and extract ALL contractual obligations.

For each obligation identified, provide:
1. **title**: Clear obligation title (max 50 words)
2. **description**: Detailed description (max 150 words)
3. **type**: One of [payment, deliverable, compliance, reporting, insurance, performance, coordination, indemnification, timely_completion]
4. **party**: Who has this obligation ('contractor' or 'client')
5. **priority**: high, medium, or low

Contract Content:
{contract_content[:8000]}

IMPORTANT: Return ONLY a valid JSON array. No markdown, no explanation, just the JSON array.

Example format:
[
  {{
    "title": "Payment Obligation",
    "description": "Timely payment for work completed as per agreed terms within 30 days of invoice",
    "type": "payment",
    "party": "client",
    "priority": "high"
  }},
  {{
    "title": "Quality Compliance",
    "description": "Ensure all deliverables meet specified quality standards and industry requirements",
    "type": "performance",
    "party": "contractor",
    "priority": "high"
  }}
]"""

    try:
        response_text = await self.generate_text(prompt, max_tokens=3000)
        
        # Parse JSON from response
        import json
        import re
        
        # Try to extract JSON array
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            obligations = json.loads(json_match.group(0))
            
            # Filter by party role if specified
            if party_role != "both":
                obligations = [
                    obl for obl in obligations 
                    if obl.get("party", "both").lower() == party_role.lower()
                ]
            
            logger.info(f" Extracted {len(obligations)} obligations from contract")
            return obligations
        else:
            logger.warning(" Could not parse JSON from response")
            return []
            
    except Exception as e:
        logger.error(f" Error extracting obligations: {str(e)}")
        return []


