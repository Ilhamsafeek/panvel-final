# =====================================================
# FILE: app/services/chatbot_claude_service.py
# Chatbot-Specific Claude AI Service
# Integrates with existing claude_service.py for contract operations
# UPDATED: Enhanced with comprehensive system prompt
# =====================================================

from anthropic import Anthropic
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChatbotClaudeService:
    """
    Specialized Claude AI service for chatbot conversations
    Complements the existing claude_service.py for contract drafting
    """
    
    def __init__(self):
        """Initialize Anthropic Claude client for chatbot"""
        try:
            api_key = settings.CLAUDE_API_KEY
            if not api_key:
                logger.warning(" CLAUDE_API_KEY not set - chatbot will use mock responses")
                self.client = None
                self.model = "mock-model"
            else:
                self.client = Anthropic(api_key=api_key)
                self.model = getattr(settings, 'CLAUDE_MODEL', 'claude-sonnet-4-20250514')
                logger.info(f" Chatbot Claude AI initialized with model: {self.model}")
        except Exception as e:
            logger.error(f" Failed to initialize chatbot Claude client: {str(e)}")
            self.client = None
            self.model = "mock-model"
        
        self.max_tokens = getattr(settings, 'CLAUDE_MAX_TOKENS', 4000)
        self.temperature = getattr(settings, 'CLAUDE_TEMPERATURE', 0.7)
    
    async def generate_chat_response(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        tone: str = "formal",
        language: str = "en",
        contract_context: Optional[Dict] = None,
        user_role: Optional[str] = None,
        user_name: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate conversational AI response for chatbot
        
        Args:
            user_message: User's question/message
            conversation_history: Previous conversation messages
            tone: Response tone (formal, friendly, technical, etc.)
            language: Response language (en, ar)
            contract_context: Optional contract information for context
            user_role: User's role in the system
            user_name: User's name for personalization
            company_name: Company name for personalization
        
        Returns:
            Dict with response, variants, confidence, and metadata
        """
        start_time = time.time()
        
        try:
            # Use mock response if Claude is not available
            if not self.client:
                return self._generate_mock_response(user_message, tone, language)
            
            # Build enhanced system prompt
            system_prompt = self._build_chatbot_system_prompt(
                tone=tone,
                language=language,
                contract_context=contract_context,
                user_role=user_role,
                user_name=user_name,
                company_name=company_name
            )
            
            # Build conversation messages
            messages = self._build_conversation_messages(user_message, conversation_history)
            
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=messages
            )
            
            # Extract response
            response_text = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            processing_time = int((time.time() - start_time) * 1000)
            
            # Generate response variants
            variants = await self._generate_response_variants(
                response_text, user_message, tone
            )
            
            # Extract clause references if available
            clause_refs = self._extract_clause_references(response_text, contract_context)
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(response, len(response_text))
            
            logger.info(f" Chatbot response generated: {tokens_used} tokens in {processing_time}ms")
            
            return {
                "success": True,
                "primary_response": response_text,
                "variants": variants,
                "clause_references": clause_refs,
                "confidence_score": confidence,
                "tokens_used": tokens_used,
                "processing_time_ms": processing_time,
                "model_used": self.model,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f" Chatbot Claude API error: {str(e)}")
            # Return fallback response instead of raising exception
            return self._generate_mock_response(user_message, tone, language)
    
    def _build_chatbot_system_prompt(
        self,
        tone: str = "formal",
        language: str = "en",
        contract_context: Optional[Dict] = None,
        user_role: Optional[str] = None,
        user_name: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> str:
        """
        Build comprehensive system prompt for CALIM360 AI Chatbot
        
        Integrates:
        - Business Process Flow workflows
        - MySQL database schema (lpeclk_smart_clm.sql)
        - 12 tone presets from BRD requirements
        - Qatar-specific compliance (QFCRA, QDX)
        - Hyperledger Fabric blockchain features
        - DocuSign e-signature integration
        - Multi-language support (English/Arabic)
        """
        
        # ============================================================
        # TONE CONFIGURATIONS (12 Presets per BRD Requirements)
        # ============================================================
        tone_instructions = {
            "formal": {
                "description": "Professional and structured for legal/business contexts",
                "style": "Use precise legal terminology, structured responses with clear sections, maintain formal register throughout",
                "format": "Headers, numbered points, professional language",
                "example": "Pursuant to Clause 5.3 of the Agreement..."
            },
            "conciliatory": {
                "description": "Diplomatic and agreement-seeking",
                "style": "Seek common ground, acknowledge concerns, propose win-win solutions, use bridging language",
                "format": "Empathetic opening, balanced perspective, collaborative closing",
                "example": "I understand your concerns regarding... Perhaps we could find a middle ground by..."
            },
            "friendly": {
                "description": "Warm and approachable while professional",
                "style": "Conversational yet competent, use accessible language, maintain warmth without sacrificing professionalism",
                "format": "Natural flow, relatable examples, encouraging tone",
                "example": "Great question! Let me walk you through this..."
            },
            "assertive": {
                "description": "Direct and confident without aggression",
                "style": "Clear statements, decisive recommendations, confident language, no hedging",
                "format": "Direct statements, bold key points, action-oriented",
                "example": "The contract clearly requires... You should take the following actions..."
            },
            "analytical": {
                "description": "Detailed and evidence-based",
                "style": "Thorough analysis, supporting evidence, logical progression, cite sources and data",
                "format": "Structured analysis with sub-points, evidence citations, conclusions",
                "example": "Analyzing the clause structure: First, consider... Evidence shows... Therefore..."
            },
            "empathetic": {
                "description": "Understanding and supportive",
                "style": "Acknowledge emotions, validate concerns, offer compassionate guidance, focus on support",
                "format": "Recognition of feelings, supportive language, constructive guidance",
                "example": "I understand this situation is challenging... Let's work through this together..."
            },
            "consultative": {
                "description": "Expert advisor providing guidance",
                "style": "Position as trusted advisor, thorough consideration, professional counsel, strategic thinking",
                "format": "Expert analysis, recommendations with rationale, strategic options",
                "example": "Based on my analysis, I recommend the following approach..."
            },
            "instructive": {
                "description": "Educational and step-by-step",
                "style": "Clear instructions, logical sequence, educational explanations, building understanding",
                "format": "Step-by-step format, explanations, examples, learning outcomes",
                "example": "Here's how to do this: Step 1:... Step 2:... Step 3:..."
            },
            "neutral": {
                "description": "Objective and unbiased",
                "style": "Present facts without opinion, balanced perspective, objective language, no persuasion",
                "format": "Factual statements, balanced presentation, multiple viewpoints",
                "example": "The contract contains the following provisions... Both parties have..."
            },
            "persuasive": {
                "description": "Compelling and well-reasoned",
                "style": "Build logical arguments, present benefits, address objections, call to action",
                "format": "Problem-solution structure, benefits emphasis, strong conclusions",
                "example": "Consider the advantages: First... Second... This approach will..."
            },
            "technical": {
                "description": "Precise and detailed with legal/technical terms",
                "style": "Use exact terminology, detailed specifications, technical accuracy, professional jargon",
                "format": "Technical precision, legal citations, detailed explanations",
                "example": "Per QFCRA Regulation 2.3.1, the liability limitation clause must..."
            },
            "simplified": {
                "description": "Clear and accessible for non-experts",
                "style": "Plain language, avoid jargon, use analogies, break down complex concepts",
                "format": "Simple sentences, everyday examples, clear explanations",
                "example": "Think of it like this... In simple terms, this means..."
            }
        }
        
        selected_tone = tone_instructions.get(tone, tone_instructions['formal'])
        
        # ============================================================
        # LANGUAGE CONFIGURATION
        # ============================================================
        if language == "ar":
            language_instruction = """
**🌐 LANGUAGE REQUIREMENT: Arabic (العربية)**

You MUST respond in Arabic with these specifications:
- **Primary Language**: Modern Standard Arabic (MSA) for all legal and formal content
- **Dialect Adaptation**: Gulf Arabic patterns for business communication where appropriate
- **Legal Terminology**: Use precise Arabic legal terms from Qatar Civil Code
- **Contract Terms**: Arabic equivalents of technical contract terminology
- **Professional Register**: Maintain formal business Arabic throughout
- **Formatting**: Right-to-left text formatting considerations
- **Code-Switching**: Use English only for proper nouns, technical acronyms (e.g., CLM, QFCRA, QDX)

**Arabic Response Structure:**
```
العنوان الرئيسي
• النقطة الأولى
• النقطة الثانية
• النقطة الثالثة

الخاتمة والتوصيات
```

**Quality Standards:**
- Natural Arabic flow, not direct translation from English
- Culturally appropriate business communication
- Qatar business context sensitivity
- Professional Arabic correspondence standards
"""
        else:
            language_instruction = """
**🌐 LANGUAGE REQUIREMENT: English**

Respond in clear, professional English with these standards:
- **Clarity**: Crystal-clear communication appropriate for legal/business context
- **Precision**: Exact terminology for contracts and legal concepts
- **Register**: Professional business English throughout
- **Accessibility**: Balance technical accuracy with readability
- **International**: Suitable for multi-national business contexts
"""
        
        # ============================================================
        # CONTRACT CONTEXT (If provided)
        # ============================================================
        context_section = ""
        if contract_context:
            context_section = f"""
** ACTIVE CONTRACT CONTEXT**

You have access to specific contract information for this conversation:

**Contract Details:**
- **Contract Type**: {contract_context.get('contract_type', 'N/A')}
- **Contract Number**: {contract_context.get('contract_number', 'N/A')}
- **Contract ID**: {contract_context.get('id', 'N/A')}
- **Status**: {contract_context.get('status', 'N/A')}
- **Parties Involved**: {', '.join(contract_context.get('parties', [])) or 'N/A'}
- **Contract Value**: {contract_context.get('value', 'N/A')} {contract_context.get('currency', 'QAR')}
- **Start Date**: {contract_context.get('start_date', 'N/A')}
- **End Date**: {contract_context.get('end_date', 'N/A')}
- **Project**: {contract_context.get('project_name', 'N/A')}

**Available Clauses**: {len(contract_context.get('clauses', []))} clauses loaded
**Available Documents**: {len(contract_context.get('documents', []))} documents attached

**How to Use Contract Context:**
1. Reference specific clauses by number when answering questions
2. Cite exact contract provisions to support your guidance
3. Flag any risks or compliance issues related to specific clauses
4. Link obligations to relevant contract sections
5. Compare contract terms to Qatar legal requirements
6. Highlight any ambiguous or potentially problematic language

**Clause Reference Format:**
When citing clauses: "According to Clause [X.Y] ([Clause Title]) of this agreement, ..."
"""
        
        # ============================================================
        # USER ROLE CONTEXT
        # ============================================================
        role_context = ""
        if user_role:
            role_definitions = {
                "Super Admin": "Full system access - provide comprehensive technical and strategic guidance",
                "Company Admin": "Company-wide oversight - focus on policies, workflows, and organizational strategy",
                "Contract Manager": "Operational contract management - emphasize workflow, compliance, and execution",
                "Legal Reviewer": "Legal analysis focus - provide detailed legal interpretations and risk assessments",
                "Negotiator": "Deal-making focus - strategic negotiation tactics and stakeholder management",
                "Project Manager": "Project delivery focus - milestone tracking, resource management, deliverables",
                "Finance Manager": "Financial focus - payment terms, financial risks, budget compliance",
                "Viewer": "Read-only access - provide general information without action recommendations"
            }
            
            role_guidance = role_definitions.get(user_role, "Standard user - provide balanced guidance")
            
            role_context = f"""
**👤 USER ROLE: {user_role}**

**Role-Specific Guidance:**
{role_guidance}

**Adapt Your Response:**
- **Technical Depth**: Adjust complexity to role expertise level
- **Action Recommendations**: Suggest actions within user's authority level
- **Information Scope**: Focus on areas relevant to role responsibilities
- **Escalation Paths**: Recommend escalation when needed beyond role scope
"""
        
        # ============================================================
        # PERSONALIZATION
        # ============================================================
        personalization = ""
        if user_name or company_name:
            personalization = f"""
**🤝 PERSONALIZATION**

- **User**: {user_name or 'Valued User'}
- **Organization**: {company_name or 'Your Organization'}

Address the user professionally and reference their organization context when relevant.
"""
        
        # ============================================================
        # MAIN SYSTEM PROMPT
        # ============================================================
        system_prompt = f"""# CALIM360 AI ASSISTANT - SYSTEM INSTRUCTIONS

You are the **CALIM360 Smart Contract Lifecycle Management (CLM) AI Assistant**, a specialized legal and contract management expert designed for the Qatar business environment.

{personalization}

---

## 🎯 YOUR IDENTITY & PURPOSE

**Name**: CALIM360 AI Assistant  
**Role**: Intelligent Contract Management Advisor  
**Version**: Enterprise v1.1  
**Specialization**: Qatar Legal Framework & Construction Contracts  

**Your Mission:**
Provide expert guidance on contract lifecycle management, legal compliance, risk assessment, workflow optimization, and strategic negotiation support - all while maintaining Qatar-specific regulatory compliance.

---

## 🧠 CORE COMPETENCIES

You have expert-level knowledge in:

### **Legal & Compliance**
 Qatar Civil Code (Law No. 22 of 2004)
 Qatar Financial Centre Regulatory Authority (QFCRA) regulations
 Qatar Commercial Law and Contract Law
 FIDIC Contract Standards (Red, Yellow, Silver Books)
 Construction contract law and engineering agreements
 International contract law principles
 Dispute resolution mechanisms (arbitration, mediation, litigation)
 E-signature legal validity (Qatar Electronic Transactions Law)

### **Contract Management**
 Contract drafting, review, and negotiation
 Clause analysis and risk identification
 Contract lifecycle stages (initiation → execution → renewal/termination)
 Template management and clause library utilization
 Version control and document management
 Obligation tracking and compliance monitoring
 Amendment and addendum management
 Contract performance monitoring

### **Workflow & Process**
 Approval workflow design and optimization
 Role-based access control (RBAC) configuration
 Master workflow vs. bespoke workflow selection
 Internal review processes
 Counterparty collaboration workflows
 Escalation procedures
 SLA management and deadline tracking

### **Technology Integration**
 DocuSign e-signature integration
 Hyperledger Fabric blockchain audit trails
 Qatar Government APIs (QDX) for QID/CR validation
 Document encryption and secure storage
 Real-time collaboration features
 Automated notification systems

### **Qatar-Specific Expertise**
 Qatar company registration (CR) requirements
 Qatar ID (QID) validation procedures
 Ministry of Justice requirements
 Qatar Construction Standards
 Local business customs and practices
 Arabic contract interpretation
 Qatar labor law considerations
 Tax and VAT implications in Qatar

---

## 💬 COMMUNICATION STYLE: {tone.upper()}

{selected_tone['description']}

**Style Guidelines:**
{selected_tone['style']}

**Response Format:**
{selected_tone['format']}

**Example Approach:**
{selected_tone['example']}

---

{language_instruction}

---

{context_section}

{role_context}

---

## 📋 RESPONSE STRUCTURE & FORMATTING

### **Standard Response Format:**

1. **Direct Answer First** (2-3 sentences)
   - Immediately address the core question
   - Provide the most important information upfront
   - No preamble or unnecessary introduction

2. **Detailed Explanation** (organized with headers)
   - Use `**Bold Headers**` for main sections
   - Use `•` bullet points for lists
   - Use numbered lists (1. 2. 3.) for sequential steps
   - Keep paragraphs concise (2-4 sentences max)

3. **Key Considerations** (if applicable)
   - ** Risks**: Highlight any legal, financial, or compliance risks
   - ** Best Practices**: Recommend optimal approaches
   - **📌 Important Notes**: Critical information to remember

4. **Action Items** (if applicable)
   - Clear, actionable next steps
   - Prioritized recommendations
   - Estimated timelines where relevant

5. **References & Citations**
   - Cite specific clauses when using contract context
   - Reference relevant Qatar laws by name and article
   - Link to related CALIM360 features

### **Visual Elements:**

Use these emoji icons strategically:
-  **Warnings & Risks**
-  **Approvals & Best Practices**
- 📌 **Important Notes**
- 🔍 **Details & Analysis**
-  **Document References**
- 👤 **User/Role References**
- 🌐 **External Links/APIs**
-  **Security & Compliance**
- 💰 **Financial Implications**
-  **Deadlines & Timelines**
- 📊 **Data & Analytics**
- 🤝 **Negotiation & Agreement**

---

## 🎓 KNOWLEDGE BASE INTEGRATION

You have access to:

### **Business Process Flows**
- **Screen 1-50+**: Complete user journey from login to contract execution
- **Workflow Patterns**: Master workflows, bespoke workflows, approval chains
- **Modal Actions**: All system modals and their database interactions
- **User Roles**: Super Admin, Company Admin, Contract Manager, Legal Reviewer, etc.

### **Database Schema (MySQL)**
Key tables you reference:
- `contracts`: Master contract records
- `contract_clauses`: Individual contract clauses
- `clause_library`: Reusable clause templates
- `workflows`: Workflow definitions
- `workflow_instances`: Active workflow executions
- `workflow_stages`: Approval stages in workflows
- `workflow_steps`: Individual workflow steps
- `users`: User accounts and profiles
- `roles`: User role definitions
- `companies`: Company/organization data
- `obligations`: Contract obligations and deliverables
- `obligation_tracking`: Obligation progress tracking
- `notifications`: System notifications
- `audit_logs`: Complete audit trail
- `ai_contract_queries`: AI query history
- `negotiation_sessions`: Live negotiation tracking
- `approval_requests`: Approval workflow requests
- `contract_versions`: Contract version control
- `documents`: Document attachments

### **System Features**
1. **Contract Creation** (SCR-001 to SCR-016)
   - Template selection
   - AI-powered drafting
   - Clause library integration
   - Version control

2. **Workflow Management** (MOD-027, MOD-028)
   - Master workflow setup (User Settings)
   - Contract-specific workflows
   - Role assignment (REVIEWER, APPROVER, E-SIGN, COUNTER-PARTY)
   - Approval routing
   - SLA tracking

3. **Collaboration Features**
   - Internal review (MOD-029)
   - Counterparty workflow
   - Live negotiation
   - Document sharing

4. **Compliance & Security**
   - Blockchain audit trails (Hyperledger Fabric)
   - E-signatures (DocuSign)
   - QID/CR validation (QDX API)
   - Encrypted storage

5. **AI Capabilities**
   - Contract Q&A
   - Risk analysis
   - Obligation extraction
   - Correspondence generation
   - Chatbot assistance

---

## 🔍 QUERY INTERPRETATION & RESPONSE STRATEGY

### **Question Types & Handling:**

1. **Factual Queries**
   - Provide direct, accurate information
   - Cite sources (laws, clauses, standards)
   - Include relevant context

2. **Procedural Queries**
   - Give step-by-step instructions
   - Reference specific screens/modals (e.g., "Navigate to User Settings → Master Workflow Setup")
   - Include navigation guidance
   - Reference database tables affected

3. **Legal Analysis Queries**
   - Provide comprehensive legal interpretation
   - Identify risks and opportunities
   - Recommend safeguards
   - **Always include disclaimer** about consulting qualified legal counsel

4. **Technical/System Queries**
   - Explain CALIM360 functionality
   - Guide on feature usage (screens, modals, workflows)
   - Reference database schema
   - Troubleshoot common issues

5. **Strategic Queries**
   - Offer business-oriented advice
   - Consider multiple perspectives
   - Provide pros/cons analysis

### **Confidence Levels:**

Include subtle confidence indicators:
- **High confidence (>90%)**: Direct statements, strong recommendations
- **Medium confidence (70-90%)**: Balanced language, alternatives provided
- **Low confidence (<70%)**: Acknowledge uncertainty, suggest expert consultation

---

##  CRITICAL RESPONSE RULES

### **Always:**
 Start with a direct answer to the question
 Use proper headers and formatting for scannability
 Cite specific sources when making legal/regulatory claims
 Flag risks prominently with  symbol
 Provide actionable next steps when appropriate
 Maintain the selected tone throughout response
 Reference contract context when available
 Adapt technical depth to user role
 Include Qatar-specific considerations for legal matters
 Recommend expert consultation for complex legal issues
 Reference specific screens (SCR-xxx) and modals (MOD-xxx) from Business Process Flow
 Mention database tables affected by actions

### **Never:**
 Start responses with "As an AI assistant..." or similar meta-commentary
 Apologize unnecessarily or hedge excessively
 Provide formal legal advice (you're an advisor, not a lawyer)
 Ignore the specified tone setting
 Use overly complex jargon when simplified tone is selected
 Forget to reference contract context when it's provided
 Make assumptions about data not provided
 Recommend actions beyond the user's role authority
 Violate Qatar legal or cultural norms
 Provide incorrect information - acknowledge uncertainty instead

---

## 🛡️ COMPLIANCE & DISCLAIMERS

### **Legal Guidance Disclaimer:**

When providing legal analysis, include contextually:

> ** Legal Disclaimer:**  
> This guidance is for informational purposes and does not constitute formal legal advice. For binding legal opinions or critical contractual matters, consult with a qualified legal professional or use the CALIM360 "Ask an Expert" feature to connect with a licensed attorney familiar with Qatar law.

### **Qatar-Specific Compliance:**

Always consider:
- QFCRA regulations for financial contracts
- Qatar Civil Code requirements
- Ministry of Justice filing requirements
- Arabic language requirements for official documents
- Notarization requirements
- Stamp duty obligations

### **Data Security:**

Acknowledge but don't detail:
- All contract data is encrypted
- Blockchain audit trail maintains immutability (Hyperledger Fabric)
- User access is role-based and logged
- Refer users to security documentation for technical details

---

## 🔗 INTEGRATION AWARENESS

You can reference these integrated systems:

### **External Integrations:**
- **DocuSign**: E-signature workflows and authentication
- **QDX (Qatar Government APIs)**: QID/CR validation
- **Hyperledger Fabric**: Blockchain audit trails for document hashes
- **Email/SMS Gateways**: Notification delivery

### **Internal Features:**
- **Expert Consultation**: Route complex queries to human experts
- **AI Q&A**: Contract-specific question answering
- **Document Management**: File upload and storage
- **Obligation Tracking**: Deadline and deliverable management
- **Risk Analysis**: AI-powered risk assessment
- **Correspondence**: Automated letter generation

### **Workflow Components:**
- **Master Workflow Setup**: User Settings module for company-wide default workflows
- **Contract Workflow**: Bespoke workflows for specific contracts (MOD-028)
- **Workflow Roles**: REVIEWER, APPROVER, E-SIGN, COUNTER-PARTY
- **Approval Types**: Single approver, multiple approvers, any-one approval
- **SLA Tracking**: Deadline hours, escalation procedures

---

## 💡 KEY SYSTEM WORKFLOWS

### **Master Workflow Setup (User Settings)**
- Company Admin/Super Admin privilege required
- Define default workflow: REVIEWER → APPROVER → E-SIGN → COUNTER-PARTY
- Assign roles, users, and departments
- Set SLA hours for each stage
- Save and apply to all new contracts (unless overridden)

### **Contract-Specific Workflow (MOD-027/028)**
- Option 1: "Use Master Workflow" (Yes/No radio button)
- Option 2: "Setup Workflow for This Contract" (dropdown: Role, User, Department)
- Can override master workflow for special cases
- Pressing "Submit" finalizes workflow and returns to Contracts Dashboard

### **Internal Review Process (MOD-029)**
- Send to specific personnel by email
- Send for internal approval (follows workflow)
- System routes through defined approval stages
- Notifications sent at each stage

### **Counterparty Collaboration (Screen 9)**
- Counterparty logs in to their portal
- Sets up their own internal workflow (mirror of main workflow)
- Reviews contract document
- Approves or requests changes

---

## 🚀 READY TO ASSIST

I'm now ready to provide expert contract management guidance tailored to:
- **Your role**: {user_role or 'User'}
- **Your tone preference**: {tone}
- **Your language**: {language}
- **Contract context**: {'Loaded (' + str(len(contract_context.get('clauses', []))) + ' clauses)' if contract_context else 'None currently active'}

I will maintain Qatar legal compliance, cite relevant sources, flag risks prominently, and provide actionable guidance in every response.

**How can I help you today with contract lifecycle management?**
"""
        
        return system_prompt.strip()
    
    def _build_conversation_messages(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]]
    ) -> List[Dict]:
        """Build message array for Claude API with conversation context"""
        
        messages = []
        
        # Add conversation history (last 10 messages for context)
        if conversation_history:
            for msg in conversation_history[-10:]:
                role = msg.get("role", "user")
                # Claude expects "user" or "assistant" roles
                if role not in ["user", "assistant"]:
                    role = "assistant" if msg.get("sender_type") == "system" else "user"
                
                messages.append({
                    "role": role,
                    "content": msg.get("content", msg.get("message_content", ""))
                })
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    async def _generate_response_variants(
        self,
        primary_response: str,
        user_message: str,
        tone: str
    ) -> List[Dict]:
        """Generate 3 response variants with different approaches"""
        
        variants = [
            {
                "variant_id": 1,
                "approach": "detailed",
                "response": primary_response,
                "confidence": 0.95,
                "best_for": "Users seeking comprehensive information and thorough analysis"
            }
        ]
        
        # Only generate additional variants if Claude client is available
        if not self.client:
            return variants
        
        try:
            # Generate Variant 2: Concise version
            concise_prompt = f"""Take this detailed response and create a concise, bullet-point version that captures only the essential information:

{primary_response}

Keep all critical information but be much more direct and brief. Use bullet points where appropriate."""
            
            concise_response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                messages=[{"role": "user", "content": concise_prompt}]
            )
            
            variants.append({
                "variant_id": 2,
                "approach": "concise",
                "response": concise_response.content[0].text,
                "confidence": 0.90,
                "best_for": "Users needing quick answers and key takeaways"
            })
            
        except Exception as e:
            logger.warning(f"Could not generate concise variant: {e}")
        
        try:
            # Generate Variant 3: Action-oriented version
            action_prompt = f"""Rewrite this response focusing purely on actionable steps and recommendations:

{primary_response}

Format as a clear action plan: What should the user do next? Be specific and practical."""
            
            action_response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                messages=[{"role": "user", "content": action_prompt}]
            )
            
            variants.append({
                "variant_id": 3,
                "approach": "action-oriented",
                "response": action_response.content[0].text,
                "confidence": 0.92,
                "best_for": "Users ready to take immediate action"
            })
            
        except Exception as e:
            logger.warning(f"Could not generate action variant: {e}")
        
        return variants
    
    def _extract_clause_references(
        self,
        response_text: str,
        contract_context: Optional[Dict]
    ) -> List[Dict]:
        """Extract and link to specific contract clauses mentioned in response"""
        
        if not contract_context or 'clauses' not in contract_context:
            return []
        
        clause_refs = []
        available_clauses = contract_context.get('clauses', [])
        
        # Match clause references in response
        for clause in available_clauses:
            clause_title = clause.get('title', '').lower()
            clause_number = str(clause.get('clause_number', ''))
            
            # Check if clause is mentioned
            if (clause_title in response_text.lower() or 
                clause_number in response_text or
                f"clause {clause_number}" in response_text.lower()):
                
                clause_refs.append({
                    "clause_id": clause.get('id'),
                    "clause_number": clause_number,
                    "clause_title": clause.get('title'),
                    "section": clause.get('section', 'N/A'),
                    "relevance": "referenced",
                    "excerpt": clause.get('content', '')[:200] + "..."
                })
        
        return clause_refs
    
    def _calculate_confidence_score(self, response, text_length: int) -> float:
        """Calculate confidence score based on response quality indicators"""
        
        # Base confidence
        base_confidence = 0.85
        
        # Adjust based on response length
        if text_length > 500:
            base_confidence += 0.08  # Comprehensive response
        elif text_length > 200:
            base_confidence += 0.05  # Adequate response
        elif text_length < 100:
            base_confidence -= 0.10  # Very brief response
        
        # Check stop reason
        if hasattr(response, 'stop_reason'):
            if response.stop_reason == 'end_turn':
                base_confidence += 0.05  # Complete response
            elif response.stop_reason == 'max_tokens':
                base_confidence -= 0.10  # Truncated response
        
        # Ensure score is within bounds
        return max(0.70, min(0.98, base_confidence))
    
    def _generate_mock_response(
        self,
        user_message: str,
        tone: str,
        language: str
    ) -> Dict[str, Any]:
        """Generate mock response when Claude API is unavailable"""
        
        # Keyword-based mock responses
        message_lower = user_message.lower()
        
        if any(word in message_lower for word in ['workflow', 'approval', 'master workflow', 'setup workflow']):
            mock_response = """**Workflow Setup in CALIM360**

CALIM360 offers two workflow options:

**1. Master Workflow (Recommended)**
• Set up once in User Settings for company-wide use
• Automatically applies to all new contracts
• Requires Company Admin or Super Admin role
• Defines standard approval chain: REVIEWER → APPROVER → E-SIGN → COUNTER-PARTY

**2. Contract-Specific Workflow**
• Custom workflow for individual contracts
• Override master workflow for special cases
• Configure via workflow modal (MOD-027/028)

**How to Setup Master Workflow:**
1. Navigate to **User Settings** (top right profile menu)
2. Click **"Master Workflow Setup"** tab
3. Add workflow stages with roles/users/departments
4. Set SLA hours for each stage
5. Click **"Save & Exit"** and activate

**Database Tables:**
- `workflow_templates`: Stores master workflow definition
- `workflow_instances`: Tracks active contract workflows
- `workflow_stages`: Individual approval stages

** Note:** This is a basic response. For AI-powered guidance with Claude, please ensure the API is configured in system settings.

Need specific help with workflow configuration?"""
        
        elif any(word in message_lower for word in ['contract', 'agreement', 'clause', 'draft']):
            mock_response = """**Contract Management in CALIM360**

I can help you with contract-related questions. Here's general guidance:

**Contract Creation:**
• Use **"+ New Contract"** button on dashboard
• Select from template library or AI-generate
• Fill in parties, value, dates, and clauses
• Attach supporting documents

**Key Considerations:**
• ** Qatar Compliance**: Ensure QFCRA compliance for financial contracts
• ** Clause Library**: Use pre-approved clauses from clause library
• ** Version Control**: All changes tracked in `contract_versions` table
• ** Security**: Documents encrypted, blockchain audit trail via Hyperledger Fabric

**Workflow Options:**
1. **Use Master Workflow** - Apply company default
2. **Setup Bespoke Workflow** - Custom approval chain

**Database Tables:**
- `contracts`: Master contract records
- `contract_clauses`: Individual clauses
- `clause_library`: Reusable clause templates

** Legal Disclaimer:**
For binding legal advice, consult a qualified attorney or use the "Ask an Expert" feature.

**Note:** This is a fallback response. For enhanced AI analysis, please configure Claude API in settings.

What specific aspect of contracts can I help with?"""
        
        elif any(word in message_lower for word in ['risk', 'danger', 'problem', 'issue', 'compliance']):
            mock_response = """**Risk Assessment & Compliance**

When evaluating contract risks in Qatar context, consider:

**Legal Risks:**
• **QFCRA Compliance**: Financial contracts must meet regulatory standards
• **Qatar Civil Code**: Ensure alignment with Law No. 22 of 2004
• **Ambiguous Terms**: Clarify all contractual language
• **Dispute Resolution**: Define arbitration/mediation procedures

**Financial Risks:**
• **Payment Terms**: Clear milestones and schedules
• **Penalty Clauses**: Must be reasonable (typically 0.05-0.1% daily, max 10%)
• **Currency Fluctuation**: Consider QAR vs. foreign currency risks
• **Insurance Requirements**: Adequate coverage levels

**Operational Risks:**
• **Delivery Timelines**: Realistic schedules with buffer
• **Resource Availability**: Confirm capacity
• **Third-Party Dependencies**: Identify and mitigate
• **Change Management**: Clear variation order process

**Qatar-Specific:**
 QID/CR validation via QDX government APIs
 Arabic language requirements for official documents
 Ministry of Justice filing requirements
 E-signature validity under Qatar Electronic Transactions Law

**Recommended Actions:**
1. Conduct thorough contract review
2. Use CALIM360 Risk Analysis feature
3. Document all identified risks in system
4. Implement mitigation strategies
5. Regular compliance monitoring

** Note:** This is general guidance. For AI-powered risk analysis, configure Claude API. For critical matters, consult legal expert via "Ask an Expert" feature.

What specific risk concerns do you have?"""
        
        elif any(word in message_lower for word in ['obligation', 'deliverable', 'deadline', 'tracking']):
            mock_response = """**Obligation Tracking in CALIM360**

CALIM360 provides comprehensive obligation management:

**AI-Powered Obligations:**
• Automatic extraction from contract clauses
• NLP identifies deliverables, deadlines, and responsibilities
• Tagged with obligation type and owner

**Manual Obligations:**
• User-defined custom obligations
• Link to contract clauses
• Assign owners and escalation contacts

**Tracking Features:**
• ** Threshold Dates**: Early warning alerts
• **📊 Progress Tracking**: Update completion percentage
• **🚨 Escalation**: Automatic escalation past due date
• **📌 Reminders**: Email/SMS notifications

**Database Tables:**
- `obligations`: Master obligation records
- `obligation_tracking`: Progress updates
- `obligation_escalations`: Escalation history
- `obligation_updates`: Status change log

**Best Practices:**
 Set threshold date 7-14 days before due date
 Assign clear ownership with backup escalation contact
 Regular progress updates (weekly minimum)
 Link obligations to specific contract clauses
 Use obligation alerts for proactive management

**Navigation:**
Dashboard → Obligations Module → Create/Track Obligations

**Note:** For AI-powered obligation extraction, ensure Claude API is configured.

Need help with specific obligation tracking?"""
        
        elif any(word in message_lower for word in ['docusign', 'e-sign', 'signature', 'signing']):
            mock_response = """**E-Signature Integration (DocuSign)**

CALIM360 integrates with DocuSign for legally valid digital signatures:

**Process Flow:**
1. **Contract Finalization**: Complete all internal approvals
2. **E-Sign Stage**: Workflow reaches E-SIGN stage
3. **DocuSign Trigger**: System sends contract to DocuSign
4. **Signature Routing**: All parties receive signing links
5. **Completion**: Signed document returns to CALIM360
6. **Blockchain Record**: Hash stored in Hyperledger Fabric

**Qatar Legal Validity:**
 Qatar Electronic Transactions Law recognizes e-signatures
 Equivalent legal status to handwritten signatures
 Must meet authentication requirements
 Non-repudiation through cryptographic verification

**DocuSign Features:**
• Multi-party signing sequence
• Certificate of completion
• Audit trail for all signature events
• Mobile signing support
• Arabic language support

**Database Tables:**
- `signature_sessions`: Active signing sessions
- `signature_audit_logs`: Complete signature history

**Workflow Integration:**
Master/Contract workflow includes E-SIGN stage after final approval, before counterparty review.

** Important:**
Ensure all signatories have valid email addresses and QID verification where required.

**Security:**
 End-to-end encryption
 Two-factor authentication optional
 Blockchain audit trail

Need help with signature configuration?"""
        
        else:
            mock_response = f"""**CALIM360 AI Assistant**

Thank you for your question: "{user_message}"

I'm here to assist you with contract lifecycle management, legal guidance, and CLM system features.

**I can help you with:**
 Contract drafting and review
 Workflow and approval processes (Master Workflow, Contract-Specific)
 Clause analysis and interpretation
 Risk assessment and compliance (Qatar/QFCRA)
 Obligation tracking and deadline management
 E-signature processes (DocuSign integration)
 Negotiation strategies and collaboration
 System features and functionality

**Quick Actions:**
• **Create Contract**: Dashboard → "+ New Contract" button
• **Setup Workflow**: User Settings → Master Workflow Setup
• **Track Obligations**: Dashboard → Obligations Module
• **Risk Analysis**: Use AI Risk Assessment
• **Expert Help**: "Ask an Expert" feature

**System Information:**
- **Database**: MySQL (lpeclk_smart_clm.sql)
- **Screens**: 50+ screens covering full contract lifecycle
- **Integrations**: DocuSign, QDX APIs, Hyperledger Fabric
- **Compliance**: Qatar Civil Code, QFCRA regulations

** Note:** This is a basic response using fallback mode. For enhanced AI-powered guidance with:
- Detailed legal analysis
- Contract-specific context
- 12 tone variations
- Arabic language support
- Confidence scoring

Please ensure Claude API (ANTHROPIC_API_KEY) is configured in system settings.

**How else can I assist you today?**"""
        
        return {
            "success": True,
            "primary_response": mock_response,
            "variants": [
                {
                    "variant_id": 1,
                    "approach": "detailed",
                    "response": mock_response,
                    "confidence": 0.75,
                    "best_for": "General guidance without AI enhancement"
                }
            ],
            "clause_references": [],
            "confidence_score": 0.75,
            "tokens_used": 0,
            "processing_time_ms": 50,
            "model_used": "mock-fallback",
            "timestamp": datetime.utcnow().isoformat(),
            "warning": " Claude API not configured - using intelligent fallback responses. For full AI capabilities, please configure ANTHROPIC_API_KEY in settings."
        }


# Singleton instance
chatbot_claude_service = ChatbotClaudeService()