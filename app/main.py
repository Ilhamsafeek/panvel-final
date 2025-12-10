"""
CALIM 360 - FastAPI Main Application with Database Integration
RESOLVED VERSION - Combined features from both branches
"""

from fastapi import FastAPI, HTTPException, Query, Request, Depends, status
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import uvicorn
from sqlalchemy import text
from app.routers import subscription_router
from app.core.subscription_guard import require_module_subscription, ModuleCodes
from app.core.dependencies import get_user_context_with_subscriptions

# Core imports
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.core.database import engine, get_db, init_db, test_connection
from app.models import Base
from app.models.user import User
from app.api.api_v1.chatbot.routes import router as chatbot_router
from app.api.api_v1.workflow import approval_router


# Configure logging FIRST
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================================================
# IMPORT ALL ROUTERS WITH ERROR HANDLING
# =====================================================

# Auth routers (Required)
from app.api.api_v1.auth.registration import router as registration_router
from app.api.api_v1.auth.login import router as login_router
from app.api.api_v1.auth.schemas import UserRegistration, LoginRequest
from app.api.api_v1.auth.logout import router as logout_router

# User routers (Required)
from app.api.api_v1.users.settings import router as settings_router
from app.api.api_v1.users.users import router as users_router


admin_router = None
try:
    from app.api.api_v1.admin.super_admin import router as admin_router
    logger.info("✅ Admin router imported")
except ImportError:
    logger.warning("⚠️ Admin router not found")

    
# User management router with error handling
user_router = None
try:
    from app.api.api_v1.users.user_management import router as user_router
    logger.info("✅ User management router imported")
except ImportError:
    logger.warning("⚠️ User management router not found")

# Business logic routers (Required)
from app.api.api_v1.projects.projects import router as projects_router
from app.api.api_v1.companies.companies import router as companies_router

# Contract routers - Import with error handling
contracts_router = None
contracts_api_router = None
try:
    from app.api.api_v1.contracts.contracts import router as contracts_router
    logger.info("✅ Contracts router (contracts.py) imported")
except ImportError:
    logger.warning("⚠️ Contracts router (contracts.py) not found")

try:
    from app.api.api_v1.contracts.router import router as contracts_api_router
    logger.info("✅ Contracts API router (router.py) imported")
except ImportError:
    logger.warning("⚠️ Contracts API router (router.py) not found")

# Dashboard router
dashboard_router = None
try:
    from app.api.api_v1.dashboard.router import router as dashboard_router
    logger.info("✅ Dashboard router imported")
except ImportError:
    logger.warning("⚠️ Dashboard router not found")

# Workflow routers
master_workflow_router = None
workflow_router = None
workflow_api_router = None

try:
    from app.api.api_v1.workflow.master_workflow import router as master_workflow_router
    logger.info("✅ Master workflow router imported")
except ImportError:
    logger.warning("⚠️ Master workflow router not found")

try:
    from app.api.api_v1.workflow.workflow import router as workflow_router
    logger.info("✅ Workflow router imported")
except ImportError:
    logger.warning("⚠️ Workflow router not found")

try:
    from app.api.api_v1.workflow.router import router as workflow_api_router
    logger.info("✅ Workflow API router imported")
except ImportError:
    logger.warning("⚠️ Workflow API router not found")

# Reports routers
audit_trail_router = None
try:
    from app.api.api_v1.reports.audit_trail import router as audit_trail_router
    logger.info("✅ Audit trail router imported")
except ImportError:
    logger.warning("⚠️ Audit trail router not found")

# Middleware
audit_middleware = None
try:
    from app.middleware.audit_middleware import AuditLoggingMiddleware
    audit_middleware = AuditLoggingMiddleware
    logger.info("✅ Audit middleware imported")
except ImportError:
    logger.warning("⚠️ Audit middleware not found")

# Obligations router
obligations_router = None
try:
    from app.api.api_v1.obligations.obligations import router as obligations_router
    logger.info("✅ Obligations router imported")
except ImportError:
    logger.warning("⚠️ Obligations router not found")

# Drafting routers
clause_library_router = None
try:
    from app.api.api_v1.drafting.clause_library import router as clause_library_router
    logger.info("✅ Clause library router imported")
except ImportError:
    logger.warning("⚠️ Clause library router not found")

# Expert consultation routers
experts_router = None
experts_api_router = None
consultations_router = None
consultation_router = None
ws_consultation_router = None

try:
    from app.api.api_v1.consultations import consultations_router
    logger.info("✅ Consultations router imported")
except ImportError:
    logger.warning("⚠️ Consultations router not found")

try:
    from app.api.api_v1.experts import router as experts_router
    logger.info("✅ Experts router (general) imported")
except ImportError:
    logger.warning("⚠️ Experts router (general) not found")

try:
    from app.api.api_v1.experts.experts import router as experts_api_router
    logger.info("✅ Experts API router imported")
except ImportError:
    logger.warning("⚠️ Experts API router not found")

try:
    from app.api.api_v1.experts.consultation_router import router as consultation_router
    logger.info("✅ Consultation router imported")
except ImportError:
    logger.warning("⚠️ Consultation router not found")

try:
    from app.api.api_v1.experts.websocket_consultation import router as ws_consultation_router
    logger.info("✅ WebSocket consultation router imported")
except ImportError:
    logger.warning("⚠️ WebSocket consultation router not found")

# Correspondence router (with error handling)
correspondence_router = None
try:
    from app.api.api_v1.correspondence.router import router as correspondence_router
    logger.info("✅ Correspondence router imported")
except ImportError:
    try:
        from app.api.api_v1.correspondence import router as correspondence_router
        logger.info("✅ Correspondence router imported (alternate path)")
    except ImportError:
        logger.warning("⚠️ Correspondence router not found")



from app.api.api_v1.blockchain.router import router as blockchain_router



# =====================================================
# CREATE REQUIRED DIRECTORIES
# =====================================================
Path("app/static").mkdir(exist_ok=True, parents=True)
Path("app/static/templates").mkdir(exist_ok=True, parents=True)
Path("app/static/templates/screens").mkdir(exist_ok=True, parents=True)
Path("app/static/templates/screens/auth").mkdir(exist_ok=True, parents=True)
Path("app/static/css").mkdir(exist_ok=True, parents=True)
Path("app/static/js").mkdir(exist_ok=True, parents=True)
Path("app/uploads").mkdir(exist_ok=True, parents=True)
Path("app/uploads/documents").mkdir(exist_ok=True, parents=True)
Path("app/logs").mkdir(exist_ok=True, parents=True)

# =====================================================
# UTILITY HELPER FUNCTIONS
# =====================================================

def get_user_context(current_user: User, db: Session) -> Dict[str, Any]:
    """
    Extract user context for template rendering
    Centralizes user data preparation for consistency
    """
    try:
        # Get user's full name
        full_name = f"{current_user.first_name} {current_user.last_name}".strip()
        if not full_name:
            full_name = current_user.email.split('@')[0]
        
        # Get company info if available
        company_name = "No Company"
        if current_user.company_id:
            from app.models.user import Company
            company = db.query(Company).filter(Company.id == current_user.company_id).first()
            if company:
                company_name = company.company_name
        
        return {
            "id": current_user.id,
            "email": current_user.email,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "full_name": full_name,
            "company": company_name,
            "company_id": current_user.company_id,
            "user_type": current_user.user_type,
            "avatar_initial": full_name[0].upper() if full_name else "U",
            "is_active": current_user.is_active,
            "phone": getattr(current_user, 'phone', None),
            "job_title": getattr(current_user, 'job_title', None),
            "department": getattr(current_user, 'department', None),
        }
    except Exception as e:
        logger.error(f"Error building user context: {str(e)}")
        return {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.email.split('@')[0],
            "company": "Unknown",
            "user_type": getattr(current_user, 'user_type', 'user'),
            "avatar_initial": "U"
        }

# =====================================================
# LIFESPAN CONTEXT MANAGER
# =====================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting CALIM 360 application...")
    
    # Test database connection
    if test_connection():
        logger.info("✅ Database connection successful")
        init_db()
        logger.info("✅ Database tables initialized")
    else:
        logger.error("❌ Database connection failed! Running without database.")
        logger.info("⚠️  Application will run with limited functionality")
    
    yield
    
    # Shutdown
    logger.info("Shutting down CALIM 360 application...")
    try:
        engine.dispose()
        logger.info("✅ Database connections closed")
    except:
        pass

# =====================================================
# INITIALIZE FASTAPI APP
# =====================================================
app = FastAPI(
    title=settings.APP_NAME,
    description="Smart Contract Lifecycle Management System",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# =====================================================
# MIDDLEWARE CONFIGURATION
# =====================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add audit logging middleware (if available)
if audit_middleware:
    app.add_middleware(audit_middleware)
    logger.info("✅ Audit logging middleware registered")


try:
    from app.middleware.blockchain_middleware import BlockchainVerificationMiddleware
    app.add_middleware(BlockchainVerificationMiddleware)
    logger.info("✅ Blockchain verification middleware registered")
except ImportError:
    logger.warning("⚠️ Blockchain verification middleware not found")

# Add audit logging middleware (if available)
if audit_middleware:
    app.add_middleware(audit_middleware)
    logger.info("✅ Audit logging middleware registered")

# =====================================================
# INCLUDE ALL API ROUTERS
# =====================================================

# Auth routes (no prefix - already defined in router)
app.include_router(registration_router)
app.include_router(login_router)
app.include_router(logout_router)
app.include_router(
    approval_router.router,
    prefix="/api/v1/workflow",
    tags=["workflow"]
)

logger.info("✅ Auth routers registered")

# Register router
app.include_router(chatbot_router, tags=["AI Chatbot"])
# Settings router
app.include_router(settings_router)

app.include_router(blockchain_router, prefix="/api/blockchain", tags=["Blockchain"])

# Admin/Super Admin routes
if admin_router:
    app.include_router(admin_router, tags=["admin"])  # Remove prefix - router already has it
    logger.info("✅ Admin router registered at /api/admin")

# Projects router - NO /api/v1 prefix! Router already has /api/projects
app.include_router(projects_router)
logger.info("✅ Projects router registered at /api/projects")

# Company and user routers
app.include_router(companies_router)
app.include_router(users_router)

if user_router:
    app.include_router(user_router, prefix="/api/users", tags=["users"])
    logger.info("✅ User management router registered")

# Contract routers (if available)
if contracts_router:
    app.include_router(contracts_router)
    logger.info("✅ Contracts router registered")

if contracts_api_router:
    app.include_router(contracts_api_router)
    logger.info("✅ Contracts API router registered")

# Workflow routers (if available)
if master_workflow_router:
    app.include_router(master_workflow_router)
    logger.info("✅ Master workflow router registered")

if workflow_router:
    app.include_router(workflow_router)
    logger.info("✅ Workflow router registered")

if workflow_api_router:
    app.include_router(workflow_api_router)
    logger.info("✅ Workflow API router registered")

# Report routers (if available)
if audit_trail_router:
    app.include_router(audit_trail_router)
    logger.info("✅ Audit trail router registered")

# Dashboard router (if available)
if dashboard_router:
    app.include_router(dashboard_router)
    logger.info("✅ Dashboard router registered")

# Obligations router (if available)
if obligations_router:
    app.include_router(obligations_router)
    logger.info("✅ Obligations router registered")

# Drafting routers (if available)
if clause_library_router:
    app.include_router(clause_library_router, prefix="/api/clause-library", tags=["clause-library"])
    logger.info("✅ Clause library router registered")

# Expert and consultation routers (if available)
if experts_router:
    app.include_router(experts_router, prefix="/api/experts", tags=["experts"])
    logger.info("✅ Experts router registered")

if experts_api_router:
    app.include_router(experts_api_router)
    logger.info("✅ Experts API router registered")

if consultations_router:
    app.include_router(consultations_router, prefix="/api/v1/consultations", tags=["Consultations"])
    logger.info("✅ Consultations router registered")

if consultation_router:
    app.include_router(consultation_router)
    logger.info("✅ Consultation router registered")

if ws_consultation_router:
    app.include_router(ws_consultation_router)
    logger.info("✅ WebSocket consultation router registered")

# Correspondence router (only once, with proper prefix)
if correspondence_router:
    app.include_router(correspondence_router)  # No additional prefix needed!
    logger.info("✅ Correspondence router registered at /api/correspondence")

logger.info("✅ All available API routers registered successfully")


app.include_router(subscription_router.router)

# =====================================================
# STATIC FILES AND TEMPLATES
# =====================================================
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/app/static", StaticFiles(directory="app/static"), name="app_static")
app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")



templates = Jinja2Templates(directory="app/static/templates")

# =====================================================
# LEGACY/BACKWARD COMPATIBILITY ENDPOINTS
# =====================================================
@app.post("/api/register")
async def legacy_register(request: Request, db: Session = Depends(get_db)):
    """Legacy registration endpoint for backward compatibility"""
    try:
        body = await request.json()
        logger.info(f"📝 Registration request received: {body.get('email', 'unknown')}")
        
        user_data = UserRegistration(**body)
        from app.api.api_v1.auth.registration import register_user
        result = await register_user(user_data, db)
        return result
        
    except Exception as e:
        logger.error(f"❌ Registration error: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "detail": str(e),
                "message": "Registration failed. Please check your inputs."
            }
        )

@app.post("/api/login")
async def legacy_login(request: Request, db: Session = Depends(get_db)):
    """Legacy login endpoint for backward compatibility"""
    try:
        body = await request.json()
        logger.info(f"🔐 Login request received: {body.get('email', 'unknown')}")
        
        from app.api.api_v1.auth.login import login
        login_data = LoginRequest(**body)
        result = await login(login_data, request, db)
        return result
        
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "Invalid email or password"
            }
        )

# =====================================================
# TEST/DEBUG ENDPOINTS
# =====================================================
@app.get("/test-obligations", response_class=HTMLResponse)
async def test_obligations_page():
    """Test page for obligations API"""
    html_path = Path("app/static/templates/test_obligations.html")
    if html_path.exists():
        return html_path.read_text()
    return "<h1>Test page not found</h1>"

# =====================================================
# DATABASE HEALTH CHECK ROUTES
# =====================================================
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Enhanced health check endpoint with database status"""
    health_status = {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        db.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health_status["database"] = "disconnected"
        health_status["db_error"] = str(e)
    
    return health_status

@app.get("/api/v1/db-status")
async def database_status(db: Session = Depends(get_db)):
    """Check database status and statistics"""
    try:
        result = db.execute(text("SELECT DATABASE() as db_name, VERSION() as version")).fetchone()
        return {
            "status": "connected",
            "database_name": result[0] if result else None,
            "database_type": "MySQL",
            "version": result[1] if result else None
        }
    except Exception as e:
        logger.error(f"Database status check failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Database is not available."
        }


# =====================================================
# LANDING HUB ROUTE (Post-Login Module Selection)
# =====================================================
@app.get("/hub", response_class=HTMLResponse)
async def landing_hub(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Landing Hub Page - Post Authentication
    User selects which module to access (CLM, Tender, Bid, etc.)
    Only CLM module is active, others show "Coming Soon"
    """
    try:
        user_context = get_user_context_with_subscriptions(current_user, db)
        
        return templates.TemplateResponse("screens/hub/SCR_009_landing_hub.html", {
            "request": request,
            "current_page": "hub",
            "user": user_context,
        "subscriptions": user_context['subscriptions'],
        })
        
    except Exception as e:
        logger.error(f"Hub page error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load hub page"
        )


# =====================================================
# AUTHENTICATION ROUTES (FRONTEND PAGES)
# =====================================================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Root redirects to hub (landing page)"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_page": "landing"
    })


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """Root redirects to about"""
    return templates.TemplateResponse("about.html", {
        "request": request,
        "current_page": "about"
    })



MODULES = {
    "clm": "Smart Contract Lifecycle Management",
    "correspondence": "Correspondence Management",
    "risk": "Risk Analysis & Assessment",
    "obligations": "Obligation Tracking",
    "reports": "Reports & Analytics",
    "blockchain": "Blockchain Verification",
    "expert": "Expert Collaboration"
}



@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, module: str = None):  # ← Optional (= None)
    module_name = MODULES.get(module) if module else None
    return templates.TemplateResponse("screens/auth/SCR_001_registration.html", {
        "request": request,
        "module_name": module_name
    })

@app.get("/verify-email", response_class=HTMLResponse)
async def verify_email_page(request: Request, token: Optional[str] = Query(None)):
    """Email Verification Page"""
    return templates.TemplateResponse("screens/auth/email_verification.html", {
        "request": request,
        "current_page": "verify_email",
        "token": token
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    """Login page - Redirects to dashboard if already authenticated"""
    try:
        session_token = request.cookies.get("session_token")
        
        if session_token:
            from app.core.security import verify_token
            payload = verify_token(session_token)
            
            if payload and payload.get("sub"):
                user_id = payload.get("sub")
                current_user = db.query(User).filter(User.id == int(user_id)).first()
                
                if current_user and current_user.is_active:
                    logger.info(f"✅ User {current_user.email} already authenticated")
                    return RedirectResponse(url="/dashboard", status_code=302)
        
        return templates.TemplateResponse("screens/auth/SCR_002_login.html", {
            "request": request,
            "active_tab": "login",
            "current_page": "auth"
        })
        
    except Exception as e:
        logger.error(f"Login page error: {str(e)}")
        return templates.TemplateResponse("screens/auth/SCR_002_login.html", {
            "request": request,
            "active_tab": "login",
            "current_page": "auth"
        })

@app.get("/forgot-password", response_class=HTMLResponse)
async def password_recovery_page(request: Request, token: Optional[str] = Query(None)):
    """Password recovery page"""
    return templates.TemplateResponse("screens/auth/SCR_003_password_recovery.html", {
        "request": request,
        "current_page": "password_recovery",
        "token": token
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """User Settings page"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/auth/SCR_007_user_settings.html", {
        "request": request,
        "active_tab": "settings",
        "current_page": "settings",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/api/auth/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user information"""
    try:
        user_context = get_user_context_with_subscriptions(current_user, db)
        return {
            "success": True,
            "user": user_context,
        "subscriptions": user_context['subscriptions'],
        }
    except Exception as e:
        logger.error(f"Get user info error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )

# =====================================================
# DASHBOARD ROUTES
# =====================================================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected Dashboard - Requires Authentication"""
    try:
        user_context = get_user_context_with_subscriptions(current_user, db)
        
        return templates.TemplateResponse("screens/dashboard/SCR_008_main_dashboard.html", {
            "request": request,
            "current_page": "dashboard",
            "user": user_context,
            "subscriptions": user_context['subscriptions'],
        })
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return RedirectResponse(url="/login", status_code=302)

@app.get("/contracts", response_class=HTMLResponse)
async def contracts_dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Display the Contracts Dashboard"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/dashboard/SCR_010_contract_dashboard.html", {
        "request": request,
        "current_page": "contracts",
        "user": user_context,
    "subscriptions": user_context['subscriptions'],
    })

# =====================================================
# CONTRACT MANAGEMENT ROUTES
# =====================================================
@app.get("/contract/create", response_class=HTMLResponse)
async def contract_creation_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Contract Creation Page"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/drafting/SCR_013_contract_creation.html", {
        "request": request,
        "current_page": "contract_creation",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
        "profile_type": current_user.user_type
    })

@app.get("/contract/editor", response_class=HTMLResponse)
async def contract_editor_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Display Contract Editor Screen"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/drafting/SCR_016_contract_editor.html", {
        "request": request,
        "current_page": "editor",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/contract/edit/{contract_id}", response_class=HTMLResponse)
async def contract_editor_with_id(
    request: Request,
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Display Contract Editor Screen for specific contract"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/drafting/SCR_016_contract_editor.html", {
        "request": request,
        "contract_id": contract_id,
        "current_page": "editor",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/contract/counter-party-edit/{contract_id}", response_class=HTMLResponse)
async def contract_counterparty_editor(
    request: Request,
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Display Contract Editor Screen for counterparty"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/negotiation/counterparty_review.html", {
        "request": request,
        "contract_id": contract_id,
        "current_page": "negotiation",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/contract/templates")
async def template_selection(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Template Selection Page"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/drafting/SCR_014_template_selection.html", {
        "request": request,
        "current_page": "templates",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/contract/invite/{contract_id}", response_class=HTMLResponse)
async def counterparty_invite_page(
    request: Request,
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Counterparty Invitation Page"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/negotiation/SCR_030_counterparty_invite.html", {
        "request": request,
        "contract_id": contract_id,
        "current_page": "negotiation",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/clause-library", response_class=HTMLResponse)
async def clause_library(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Display the clause library page"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/drafting/SCR_017_clause_library.html", {
        "request": request,
        "current_page": "clause_library",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

# Fetch all templates
@app.get("/api/templates")
async def get_all_templates(db: Session = Depends(get_db)):
    """Fetch all active templates from database"""
    try:
        query = text("""
            SELECT id, template_name, template_type, template_category, 
                   description, is_active
            FROM contract_templates 
            WHERE is_active = 1
            ORDER BY id
        """)
        
        results = db.execute(query).fetchall()
        
        return {
            "success": True,
            "templates": [
                {
                    "id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "category": row[3],
                    "description": row[4],
                    "is_active": bool(row[5])
                }
                for row in results
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Fetch single template by ID
@app.get("/api/templates/{template_id}")
async def get_template_details(template_id: int, db: Session = Depends(get_db)):
    """Fetch template details from database"""
    try:
        query = text("""
            SELECT id, template_name, template_type, template_category, 
                   description, template_content, file_url, is_active, 
                   created_at, updated_at
            FROM contract_templates 
            WHERE id = :template_id
        """)
        
        result = db.execute(query, {"template_id": template_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return {
            "id": result[0],
            "name": result[1],
            "template_name": result[1],
            "type": result[2],
            "template_type": result[2],
            "category": result[3],
            "template_category": result[3],
            "description": result[4] or "No description available",
            "template_content": result[5] or "Template content not available",
            "content": result[5] or "Template content not available",
            "file_url": result[6],
            "is_active": bool(result[7]),
            "created_at": str(result[8]) if result[8] else None,
            "updated_at": str(result[9]) if result[9] else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching template {template_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/check-templates")
async def check_templates(db: Session = Depends(get_db)):
    """Check template content - TEMPORARY ENDPOINT"""
    try:
        query = text("""
            SELECT id, template_name, 
                   LENGTH(template_content) as content_length,
                   LEFT(template_content, 100) as content_preview
            FROM contract_templates 
            WHERE is_active = 1
        """)
        
        results = db.execute(query).fetchall()
        
        return {
            "templates": [
                {
                    "id": row[0],
                    "name": row[1],
                    "content_length": row[2],
                    "has_content": row[2] > 0 if row[2] else False,
                    "preview": row[3]
                }
                for row in results
            ]
        }
    except Exception as e:
        return {"error": str(e)}



# @app.get("/api/add-template-content-column")
# async def add_template_content_column(db: Session = Depends(get_db)):
#     """Add template_content column - RUN ONCE ONLY"""
#     try:
#         query = text("""
#             ALTER TABLE contract_templates 
#             ADD COLUMN template_content TEXT AFTER description
#         """)
#         db.execute(query)
#         db.commit()
        
#         return {
#             "success": True, 
#             "message": "✅ Column 'template_content' added successfully!"
#         }
#     except Exception as e:
#         if "Duplicate column name" in str(e):
#             return {"success": False, "message": "Column already exists"}
#         return {"success": False, "error": str(e)}

# @app.get("/api/populate-template-content")
# async def populate_template_content(db: Session = Depends(get_db)):
#     """Add sample HTML content to templates - RUN ONCE ONLY"""
#     try:
#         templates_content = {
#             1: '''<div style="font-family: Arial; padding: 2rem;">
#                 <h1 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 1rem;">NON-DISCLOSURE AGREEMENT</h1>
#                 <p><strong>Date:</strong> <span style="background: #fff3cd; padding: 2px 8px;">[DATE]</span></p>
#                 <h2>BETWEEN:</h2>
#                 <p><strong>Party A:</strong> <span style="background: #fff3cd; padding: 2px 8px;">[PARTY A NAME]</span></p>
#                 <p><strong>Party B:</strong> <span style="background: #fff3cd; padding: 2px 8px;">[PARTY B NAME]</span></p>
#                 <h2>1. CONFIDENTIAL INFORMATION</h2>
#                 <p>The parties agree to protect confidential information disclosed during business discussions.</p>
#                 <h2>2. OBLIGATIONS</h2>
#                 <p>Each party shall maintain confidentiality and not disclose to third parties.</p>
#             </div>''',
            
#             2: '''<div style="font-family: Arial; padding: 2rem;">
#                 <h1 style="color: #2c3e50; border-bottom: 3px solid #27ae60; padding-bottom: 1rem;">SERVICE AGREEMENT</h1>
#                 <p><strong>Date:</strong> <span style="background: #d4edda; padding: 2px 8px;">[DATE]</span></p>
#                 <h2>PARTIES:</h2>
#                 <p><strong>Service Provider:</strong> <span style="background: #d4edda; padding: 2px 8px;">[PROVIDER]</span></p>
#                 <p><strong>Client:</strong> <span style="background: #d4edda; padding: 2px 8px;">[CLIENT]</span></p>
#                 <h2>1. SCOPE OF SERVICES</h2>
#                 <p>The Service Provider agrees to provide professional services as described.</p>
#             </div>''',
            
#             3: '''<div style="font-family: Arial; padding: 2rem;">
#                 <h1 style="color: #2c3e50; border-bottom: 3px solid #e67e22; padding-bottom: 1rem;">PURCHASE ORDER</h1>
#                 <p><strong>PO Number:</strong> <span style="background: #ffe5cc; padding: 2px 8px;">[PO_NUMBER]</span></p>
#                 <p><strong>Date:</strong> <span style="background: #ffe5cc; padding: 2px 8px;">[DATE]</span></p>
#                 <h2>VENDOR:</h2>
#                 <p><strong>Name:</strong> <span style="background: #ffe5cc; padding: 2px 8px;">[VENDOR NAME]</span></p>
#                 <h2>ITEMS:</h2>
#                 <p>Description of goods and services being purchased.</p>
#             </div>''',
            
#             4: '''<div style="font-family: Arial; padding: 2rem;">
#                 <h1 style="color: #2c3e50; border-bottom: 3px solid #9b59b6; padding-bottom: 1rem;">MASTER SERVICE AGREEMENT</h1>
#                 <p><strong>Effective Date:</strong> <span style="background: #f3e5f5; padding: 2px 8px;">[DATE]</span></p>
#                 <h2>PARTIES:</h2>
#                 <p>This Master Service Agreement establishes terms for ongoing business relationship.</p>
#                 <h2>1. GENERAL TERMS</h2>
#                 <p>Governs all future service orders and statements of work.</p>
#             </div>''',
            
#             5: '''<div style="font-family: Arial; padding: 2rem;">
#                 <h1 style="color: #2c3e50; border-bottom: 3px solid #16a085; padding-bottom: 1rem;">SERVICE LEVEL AGREEMENT</h1>
#                 <p><strong>Agreement Date:</strong> <span style="background: #d5f4e6; padding: 2px 8px;">[DATE]</span></p>
#                 <h2>SERVICE METRICS:</h2>
#                 <p><strong>Uptime:</strong> <span style="background: #d5f4e6; padding: 2px 8px;">[PERCENTAGE]</span></p>
#                 <p><strong>Response Time:</strong> <span style="background: #d5f4e6; padding: 2px 8px;">[TIME]</span></p>
#                 <h2>1. PERFORMANCE STANDARDS</h2>
#                 <p>Defines measurable performance criteria and service levels.</p>
#             </div>'''
#         }
        
#         for template_id, content in templates_content.items():
#             query = text("""
#                 UPDATE contract_templates 
#                 SET template_content = :content 
#                 WHERE id = :id
#             """)
#             db.execute(query, {"content": content, "id": template_id})
        
#         db.commit()
        
#         return {
#             "success": True,
#             "message": f"✅ Added content to {len(templates_content)} templates!"
#         }
        
#     except Exception as e:
#         return {"success": False, "error": str(e)}
@app.get("/api/verify-template-content")
async def verify_template_content(db: Session = Depends(get_db)):
    """Check if template_content column exists and has data"""
    try:
        # Check table structure
        structure = text("DESCRIBE contract_templates")
        columns = db.execute(structure).fetchall()
        
        # Check actual data
        data_query = text("""
            SELECT id, template_name, 
                   LENGTH(template_content) as content_length,
                   LEFT(template_content, 150) as content_preview
            FROM contract_templates 
            LIMIT 3
        """)
        data = db.execute(data_query).fetchall()
        
        return {
            "columns": [row[0] for row in columns],
            "data": [
                {
                    "id": row[0],
                    "name": row[1],
                    "content_length": row[2],
                    "content_preview": row[3]
                }
                for row in data
            ]
        }
    except Exception as e:
        return {"error": str(e), "message": "Column probably doesn't exist"}

# =====================================================
# PROJECT AND WORKFLOW ROUTES
# =====================================================
@app.get("/projects", response_class=HTMLResponse)
async def projects_page(
    request: Request,
    current_user: User = Depends(get_current_user),       # for specific access - Depends(require_module_subscription("clm")),
    db: Session = Depends(get_db)
):
    """Projects Dashboard"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    return templates.TemplateResponse("screens/dashboard/SCR_011_project_dashboard.html", {
        "request": request,
        "current_page": "projects",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """User Management Page"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    return templates.TemplateResponse("users.html", {
        "request": request,
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/master-workflow", response_class=HTMLResponse)
async def master_workflow(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Master Workflow Setup Page"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/workflow/SCR_024_master_workflow.html", {
        "request": request,
        "current_page": "master-workflow",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

# =====================================================
# REPORTS AND ANALYTICS ROUTES
# =====================================================
@app.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analytics Dashboard"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/reports/SCR_051_analytics_dashboard.html", {
        "request": request,
        "current_page": "reports",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/audit-trail", response_class=HTMLResponse)
async def audit_trail(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Audit Trail Screen - SCR-052"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/reports/SCR_052_audit_trail.html", {
        "request": request,
        "current_page": "audit-trail",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

# =====================================================
# OBLIGATIONS ROUTES
# =====================================================
@app.get("/obligations", response_class=HTMLResponse)
async def obligations_dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obligations Dashboard"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/obligations/SCR_039_obligations_dashboard.html", {
        "request": request,
        "current_page": "obligations",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/contract/obligations/{contract_id}", response_class=HTMLResponse)
async def contract_obligations(
    request: Request,
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """AI-Generated Obligations for a specific contract"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/obligations/SCR_040_ai_obligations.html", {
        "request": request,
        "current_page": "obligations",
        "contract_id": contract_id,
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

# =====================================================
# CORRESPONDENCE ROUTES
# =====================================================
@app.get("/correspondence", response_class=HTMLResponse)
async def correspondence_page(
    request: Request,
    current_user: User = Depends(require_module_subscription("correspondence")),
    db: Session = Depends(get_db)
):
    """Correspondence Management"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/correspondence/SCR_044_correspondence_management.html", {
        "request": request,
        "current_page": "correspondence",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

# =====================================================
# EXPERT COLLABORATION ROUTES
# =====================================================
@app.get("/expert-directory", response_class=HTMLResponse)
async def expert_directory(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Expert Directory"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/experts/SCR_057_expert_directory.html", {
        "request": request,
        "current_page": "experts",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/ask-expert", response_class=HTMLResponse)
async def ask_expert_page(
    request: Request,
    expert: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ask an Expert page"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/experts/SCR_056_ask_expert.html", {
        "request": request,
        "pre_selected_expert": expert,
        "action": action,
        "current_page": "experts",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/consultation-room", response_class=HTMLResponse)
async def consultation_room_page(
    request: Request,
    query: str = Query(..., description="Query ID"),
    session: str = Query(..., description="Session ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Consultation Room page - Fixed to accept query parameter
    Loads consultation room based on query ID instead of expert ID
    """
    try:
        user_context = get_user_context_with_subscriptions(current_user, db)
        
        # Fetch query details to get expert information
        query_sql = text("""
        SELECT q.id, q.query_code, q.subject, q.assigned_to,
               u.first_name, u.last_name, u.email, u.department,
               u.profile_picture_url
        FROM queries q
        LEFT JOIN users u ON q.assigned_to = u.id
        WHERE q.id = :query_id
        """)
        
        result = db.execute(query_sql, {"query_id": query})
        query_data = result.fetchone()
        
        if not query_data:
            raise HTTPException(status_code=404, detail="Query not found")
        
        # Extract query and expert details
        query_info = {
            "id": str(query_data[0]),
            "code": query_data[1],
            "subject": query_data[2],
            "assigned_to": str(query_data[3]) if query_data[3] else None,
            "expert_name": f"{query_data[4]} {query_data[5]}" if query_data[4] else "Unassigned",
            "expert_email": query_data[6],
            "expert_department": query_data[7],
            "expert_profile_picture": query_data[8]
        }
        
        return templates.TemplateResponse("screens/experts/consultation_room.html", {
            "request": request,
            "query_id": query,
            "session_id": session,
            "query_info": query_info,
            "current_page": "experts",
            "user": user_context,
        "subscriptions": user_context['subscriptions'],
        })
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌ Error loading consultation room: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load consultation room: {str(e)}"
        )

@app.get("/consultations", response_class=HTMLResponse)
async def my_consultations_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """My Consultations page"""
    user_context = get_user_context_with_subscriptions(current_user, db)
    
    return templates.TemplateResponse("screens/experts/SCR_058_my_consultations.html", {
        "request": request,
        "current_page": "consultations",
        "user": user_context,
        "subscriptions": user_context['subscriptions'],
    })

@app.get("/consultations/{consultation_id}")
async def consultation_details_page(request: Request, consultation_id: str):
    return templates.TemplateResponse("screens/experts/consultation_details.html", {
        "request": request,
        "consultation_id": consultation_id,
        "active_page": "consultations"
    })

@app.get("/consultations/{consultation_id}/action-items", response_class=HTMLResponse)
async def action_items_page(request: Request, consultation_id: str):
    """
    Action Items Page
    Displays action items for a specific consultation
    """
    return templates.TemplateResponse("screens/experts/action_items.html", {
        "request": request,
        "consultation_id": consultation_id,
        "active_page": "consultations"
    })

@app.get("/consultations/{consultation_id}/transcript", response_class=HTMLResponse)
async def transcript_page(request: Request, consultation_id: str):
    """
    Transcript Page
    Displays transcript for a text-based consultation
    """
    return templates.TemplateResponse("screens/experts/consultation_transcript.html", {
        "request": request,
        "consultation_id": consultation_id,
        "active_page": "consultations"
    })

# =====================================================
# API DOCUMENTATION ROUTES
# =====================================================
@app.get("/docs-info")
async def docs_info():
    """API Documentation Info"""
    return {
        "swagger_ui": "http://localhost:8000/docs",
        "redoc": "http://localhost:8000/redoc",
        "openapi_json": "http://localhost:8000/openapi.json",
        "endpoints": {
            "register": "POST /api/register or POST /api/auth/register",
            "login": "POST /api/login or POST /api/auth/login",
            "verify_email": "POST /api/auth/verify-email",
            "resend_verification": "POST /api/auth/resend-verification"
        }
    }

# =====================================================
# MAIN ENTRY POINT
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 CALIM 360 Server Starting...")
    print("=" * 60)
    
    try:
        host = settings.HOST
        port = settings.PORT
        reload = settings.DEBUG
        workers = 1 if settings.DEBUG else settings.WORKERS
    except:
        host = "0.0.0.0"
        port = 8000
        reload = True
        workers = 1
    
    print(f"📝 API Documentation: http://localhost:{port}/docs")
    print(f"🌐 Application: http://localhost:{port}")
    print(f"📋 Registration: http://localhost:{port}/register")
    print(f"✉️  Email Verification: http://localhost:{port}/verify-email")
    print(f"🔐 Login: http://localhost:{port}/login")
    print(f"📊 Dashboard: http://localhost:{port}/dashboard")
    print(f"🏥 Health Check: http://localhost:{port}/health")
    print("=" * 60)
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers
    )