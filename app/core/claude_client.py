# =====================================================
# FILE: app/core/claude_client.py
# Claude API Client - Production Ready
# =====================================================

import httpx
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)

class ClaudeAPIClient:
    """
    Production-ready Claude API Client for AI-powered correspondence
    """
    
    def __init__(self):
        self.api_key = settings.CLAUDE_API_KEY
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.model = settings.CLAUDE_MODEL
        self.timeout = settings.API_TIMEOUT
        self.max_tokens = settings.MAX_TOKENS
        
        # Validate API key on initialization
        if not self.api_key or not self.api_key.startswith("sk-ant-api"):
            logger.error(" Invalid or missing Anthropic API key")
            raise ValueError("Invalid Anthropic API key")
        
        logger.info(f" Claude API Client initialized with model: {self.model}")
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the API connection with a simple request
        """
        try:
            logger.info("🔍 Testing Claude API connection...")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01"
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 100,
                        "messages": [
                            {
                                "role": "user",
                                "content": "Hello! Please respond with 'API connection successful' if you can read this."
                            }
                        ]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f" Claude API connection successful!")
                    logger.info(f"   Model: {data.get('model')}")
                    logger.info(f"   Response: {data['content'][0]['text']}")
                    
                    return {
                        "success": True,
                        "model": data.get("model"),
                        "response": data["content"][0]["text"],
                        "usage": data.get("usage", {})
                    }
                else:
                    logger.error(f" API connection failed: {response.status_code}")
                    logger.error(f"   Error: {response.text}")
                    
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                    
        except httpx.TimeoutException:
            logger.error(" API connection timeout")
            return {
                "success": False,
                "error": "Connection timeout"
            }
        except Exception as e:
            logger.error(f" API connection error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_correspondence(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        tone: str = "professional",
        correspondence_type: str = "email",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate AI-powered correspondence response
        
        Args:
            query: User's query or instruction
            documents: List of reference documents
            tone: Desired tone (professional, formal, friendly, etc.)
            correspondence_type: Type (email, letter, response)
            context: Additional context (contract details, parties, etc.)
        
        Returns:
            Dict with generated content and metadata
        """
        
        try:
            logger.info(f" Generating {correspondence_type} with {tone} tone")
            logger.info(f"   Query length: {len(query)} chars")
            logger.info(f"   Documents: {len(documents)}")
            
            # Build the prompt
            prompt = self._build_prompt(query, documents, tone, correspondence_type, context)
            
            # Log prompt preview
            logger.debug(f"   Prompt preview: {prompt[:200]}...")
            
            # Call Claude API
            async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minutes for contract generation
                response = await client.post(
                    self.api_url,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01"
                    },
                    json={
                        "model": self.model,
                        "max_tokens": self.max_tokens,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    generated_content = data["content"][0]["text"]
                    
                    usage = data.get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    total_tokens = input_tokens + output_tokens
                    
                    # Calculate estimated cost
                    # Claude Sonnet 4: $3 per million input tokens, $15 per million output tokens
                    input_cost = (input_tokens / 1_000_000) * 3.0
                    output_cost = (output_tokens / 1_000_000) * 15.0
                    total_cost = input_cost + output_cost
                    
                    logger.info(f" Successfully generated {correspondence_type}")
                    logger.info(f"   Tokens: {input_tokens} input + {output_tokens} output = {total_tokens} total")
                    logger.info(f"   Estimated cost: ${total_cost:.4f}")
                    logger.info(f"   Response length: {len(generated_content)} chars")
                    
                    return {
                        "success": True,
                        "content": generated_content,
                        "tone": tone,
                        "type": correspondence_type,
                        "tokens_used": total_tokens,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "estimated_cost": round(total_cost, 4),
                        "model": self.model,
                        "generated_at": datetime.utcnow().isoformat()
                    }
                else:
                    error_detail = response.text
                    logger.error(f" Claude API error: {response.status_code}")
                    logger.error(f"   Error details: {error_detail}")
                    
                    return {
                        "success": False,
                        "error": f"API request failed: {response.status_code}",
                        "error_detail": error_detail,
                        "content": ""
                    }
                    
        except httpx.TimeoutException:
            logger.error(f" Claude API timeout after {self.timeout} seconds")
            return {
                "success": False,
                "error": f"Request timeout after {self.timeout} seconds",
                "content": ""
            }
        except Exception as e:
            logger.error(f" Claude API error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "content": ""
            }
    
    def _build_prompt(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        tone: str,
        correspondence_type: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build comprehensive prompt for Claude API"""
        
        tone_descriptions = {
            "default": "neutral and balanced",
            "professional": "polished, business-like, and professional",
            "formal": "highly formal, structured, and official",
            "friendly": "warm, approachable, and conversational",
            "assertive": "direct, confident, and firm",
            "conciliatory": "diplomatic, understanding, and conflict-resolving",
            "consultative": "advisory, expert, and guidance-focused",
            "appreciative": "grateful, acknowledging, and positive",
            "cautionary": "careful, warning, and risk-aware",
            "convincing": "persuasive, compelling, and argument-driven"
        }
        
        tone_desc = tone_descriptions.get(tone.lower(), "professional and appropriate")
        
        prompt = f"""You are an expert legal and contract management specialist helping to draft {correspondence_type} correspondence for a construction and engineering project in Qatar.

**CORRESPONDENCE TYPE:** {correspondence_type.upper()}
**REQUIRED TONE:** {tone_desc}

**USER QUERY/INSTRUCTION:**
{query}

"""
        
        # Add document context
        if documents:
            prompt += "\n**REFERENCE DOCUMENTS PROVIDED:**\n"
            for idx, doc in enumerate(documents, 1):
                prompt += f"\n{idx}. **{doc.get('document_name', f'Document {idx}')}**"
                prompt += f"\n   - Type: {doc.get('document_type', 'N/A')}"
                if doc.get('summary'):
                    prompt += f"\n   - Summary: {doc['summary']}"
                prompt += "\n"
        
        # Add contract context
        if context:
            prompt += "\n**CONTRACT CONTEXT:**\n"
            if context.get('contract_number'):
                prompt += f"- Contract Number: {context['contract_number']}\n"
            if context.get('contract_title'):
                prompt += f"- Contract Title: {context['contract_title']}\n"
            if context.get('party_a_name'):
                prompt += f"- Party A: {context['party_a_name']}\n"
            if context.get('party_b_name'):
                prompt += f"- Party B: {context['party_b_name']}\n"
            if context.get('contract_value'):
                prompt += f"- Contract Value: {context['contract_value']} {context.get('currency', 'QAR')}\n"
            if context.get('start_date'):
                prompt += f"- Start Date: {context['start_date']}\n"
            if context.get('end_date'):
                prompt += f"- End Date: {context['end_date']}\n"
        
        prompt += f"""

**INSTRUCTIONS:**
1. Analyze the user's query and reference documents carefully
2. Draft a complete, professional {correspondence_type} that addresses the query
3. Use the {tone_desc} tone throughout
4. Include all necessary sections for a {correspondence_type}:
   - Professional greeting appropriate for Qatar business culture
   - Clear subject line or reference
   - Well-structured body with proper paragraphs
   - Professional closing
5. Reference specific contract clauses, dates, and amounts where relevant
6. Ensure legal accuracy and contractual compliance
7. Use proper Qatar business correspondence format
8. Make it ready to send with minimal editing required
9. Use British English spelling and conventions

**IMPORTANT FORMATTING RULES:**
- Start directly with the correspondence content
- For letters: Begin with "Dear Sir/Madam," or appropriate greeting
- For emails: Begin with greeting and get straight to the point
- Use proper paragraph spacing
- End with "Yours faithfully," or "Best regards," as appropriate
- Include signature placeholder: [Signature], [Name], [Title], [Company]

**DO NOT:**
- Include explanations or commentary outside the correspondence
- Add notes like "Here is the draft..." or "This correspondence..."
- Include multiple format options
- Add XML tags or markup

Generate the {correspondence_type} now:
"""
        
        return prompt
    
    async def analyze_documents(
        self,
        documents: List[Dict[str, Any]],
        query: str
    ) -> Dict[str, Any]:
        """
        Analyze documents and provide insights for correspondence
        """
        
        try:
            logger.info(f"📊 Analyzing {len(documents)} documents")
            
            prompt = f"""Analyze the following documents and provide key insights relevant to this query:

**QUERY:** {query}

**DOCUMENTS:**
"""
            for idx, doc in enumerate(documents, 1):
                prompt += f"\n{idx}. {doc.get('document_name', f'Document {idx}')}"
                prompt += f"\n   Type: {doc.get('document_type', 'Unknown')}"
                if doc.get('content'):
                    prompt += f"\n   Content excerpt: {doc['content'][:500]}..."
            
            prompt += """

Provide a comprehensive analysis in the following structure:

**KEY FINDINGS:**
- List the most important points relevant to the query
- Focus on contractual obligations, dates, amounts, and parties

**RELEVANT CLAUSES:**
- Identify specific contract clauses that apply
- Quote or reference clause numbers

**RISKS & CONCERNS:**
- Highlight potential risks or issues
- Note any red flags or areas requiring attention

**RECOMMENDATIONS:**
- Suggest the best approach to address the query
- Provide actionable next steps

Keep your analysis professional, factual, and focused on helping draft effective correspondence.
"""
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01"
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 2000,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    analysis = data["content"][0]["text"]
                    
                    usage = data.get("usage", {})
                    tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    
                    logger.info(f" Document analysis completed ({tokens_used} tokens)")
                    
                    return {
                        "success": True,
                        "analysis": analysis,
                        "tokens_used": tokens_used
                    }
                else:
                    logger.error(f" Document analysis failed: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"API request failed: {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f" Document analysis error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


# Global instance
claude_client = ClaudeAPIClient()