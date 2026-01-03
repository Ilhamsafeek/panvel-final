"""
Projects API Router - FIXED VERSION
File: app/api/api_v1/projects/projects.py
Fixed: Changed prefix from /api/projects to /api/projects to match frontend calls
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from fastapi import UploadFile, File, Form
from pathlib import Path
import logging
import hashlib 

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

#  FIXED: Changed prefix to /api/projects to match frontend
router = APIRouter(prefix="/api/projects", tags=["projects"])

# =====================================================
# Pydantic Schemas
# =====================================================

class ProjectCreate(BaseModel):
    title: str
    code: str
    status: str = 'planning'
    project_manager_id: Optional[int] = None
    client_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    value: Optional[float] = None
    description: Optional[str] = None

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    project_manager_id: Optional[int] = None
    client_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    value: Optional[float] = None
    description: Optional[str] = None

# =====================================================
# 🔥 CRITICAL: STATS ENDPOINT MUST BE FIRST!
# This prevents FastAPI from treating 'stats' as a project_id
# =====================================================
@router.get("/stats")
async def get_project_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get project statistics for dashboard"""
    try:
        company_id = current_user.company_id
        logger.info(f"📊 Getting project stats for company {company_id}")
        
        query = text("""
            SELECT 
                COUNT(*) as total_projects,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_projects,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_projects,
                SUM(CASE WHEN status = 'planning' THEN 1 ELSE 0 END) as planning_projects,
                SUM(CASE WHEN status = 'on_hold' THEN 1 ELSE 0 END) as on_hold_projects,
                COALESCE(SUM(project_value), 0) as total_value,
                (SELECT COUNT(*) FROM contracts WHERE project_id IN 
                    (SELECT id FROM projects WHERE company_id = :company_id)) as total_contracts
            FROM projects 
            WHERE company_id = :company_id
        """)
        
        result = db.execute(query, {"company_id": company_id}).fetchone()
        
        total_projects = int(result.total_projects) if result and result.total_projects else 0
        active_projects = int(result.active_projects) if result and result.active_projects else 0
        completed_projects = int(result.completed_projects) if result and result.completed_projects else 0
        planning_projects = int(result.planning_projects) if result and result.planning_projects else 0
        on_hold_projects = int(result.on_hold_projects) if result and result.on_hold_projects else 0
        total_contracts = int(result.total_contracts) if result and result.total_contracts else 0
        total_value = float(result.total_value) if result and result.total_value else 0.0
        
        return {
            "success": True,
            "data": {
                "total_projects": total_projects,
                "active_projects": active_projects,
                "completed_projects": completed_projects,
                "planning_projects": planning_projects,
                "on_hold_projects": on_hold_projects,
                "total_contracts": total_contracts,
                "total_value": total_value
            }
        }
        
    except Exception as e:
        logger.error(f" Error fetching stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )


# =====================================================
#  /list ENDPOINT - For correspondence management with pagination
# =====================================================
@router.get("/list")
async def get_projects_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of projects - for correspondence management"""
    try:
        company_id = current_user.company_id
        skip = (page - 1) * page_size
        
        logger.info(f"📋 GET /list - company_id: {company_id}, page: {page}, page_size: {page_size}")
        
        # Build query with filters
        query_str = """
            SELECT 
                p.id,
                p.project_code as code,
                p.project_name as title,
                p.description,
                p.status,
                p.project_value as value,
                p.start_date as startDate,
                p.end_date as endDate,
                p.project_manager_id,
                p.client_id,
                p.created_at as createdDate,
                c.company_name as client_name,
                CONCAT(u.first_name, ' ', u.last_name) as project_manager_name
            FROM projects p
            LEFT JOIN companies c ON p.client_id = c.id
            LEFT JOIN users u ON p.project_manager_id = u.id
            WHERE p.company_id = :company_id
        """
        
        params = {"company_id": company_id}
        
        # Add optional filters
        if status and status != 'all':
            query_str += " AND p.status = :status"
            params["status"] = status
        
        if search:
            query_str += " AND (p.project_name LIKE :search OR p.project_code LIKE :search)"
            params["search"] = f"%{search}%"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM ({query_str}) as count_query"
        count_result = db.execute(text(count_query), params).fetchone()
        total_count = count_result.total if count_result else 0
        
        # Add pagination
        query_str += " ORDER BY p.created_at DESC LIMIT :limit OFFSET :skip"
        params["limit"] = page_size
        params["skip"] = skip
        
        result = db.execute(text(query_str), params)
        
        projects = []
        for row in result:
            projects.append({
                "id": row.id,
                "code": row.code if row.code else "",
                "title": row.title if row.title else "",
                "description": row.description if row.description else "",
                "status": row.status if row.status else "planning",
                "value": float(row.value) if row.value else 0.0,
                "startDate": row.startDate.isoformat() if row.startDate else None,
                "endDate": row.endDate.isoformat() if row.endDate else None,
                "project_manager_id": row.project_manager_id,
                "client_id": row.client_id,
                "createdDate": row.createdDate.isoformat() if row.createdDate else None,
                "client_name": row.client_name if row.client_name else "",
                "project_manager_name": row.project_manager_name if row.project_manager_name else ""
            })
        
        logger.info(f" Returning {len(projects)} projects out of {total_count} total")
        
        return {
            "success": True,
            "data": projects,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_count,
                "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f" Error in /list endpoint: {str(e)}", exc_info=True)
        return {
            "success": False,
            "data": [],
            "error": str(e),
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": 0,
                "total_pages": 0
            }
        }


# =====================================================
# MY PROJECTS - For dropdowns and selections
# =====================================================
@router.get("/my-projects")
async def get_my_projects(
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all projects for the current user's company - for dropdowns"""
    try:
        company_id = current_user.company_id
        logger.info(f"📋 Fetching projects for company {company_id}")
        
        # Build query
        query_str = """
            SELECT 
                p.id,
                p.project_code,
                p.project_name,
                p.description,
                p.status,
                p.project_value,
                p.start_date,
                p.end_date,
                p.created_at,
                CONCAT(u.first_name, ' ', u.last_name) as manager_name
            FROM projects p
            LEFT JOIN users u ON p.project_manager_id = u.id
            WHERE p.company_id = :company_id
        """
        
        params = {
            "company_id": company_id,
            "limit": limit,
            "offset": offset
        }
        
        # Add status filter if provided
        if status:
            query_str += " AND p.status = :status"
            params["status"] = status
        
        query_str += " ORDER BY p.created_at DESC LIMIT :limit OFFSET :offset"
        
        result = db.execute(text(query_str), params)
        rows = result.fetchall()
        
        projects = []
        for row in rows:
            projects.append({
                "id": row.id,
                "project_code": row.project_code,
                "project_name": row.project_name,
                "description": row.description,
                "status": row.status,
                "project_value": float(row.project_value) if row.project_value else 0.0,
                "start_date": str(row.start_date) if row.start_date else None,
                "end_date": str(row.end_date) if row.end_date else None,
                "created_at": str(row.created_at) if row.created_at else None,
                "manager_name": row.manager_name
            })
        
        logger.info(f" Found {len(projects)} projects")
        
        return {
            "success": True,
            "projects": projects,
            "total": len(projects)
        }
        
    except Exception as e:
        logger.error(f" Error fetching projects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch projects: {str(e)}"
        )


# =====================================================
# GET ALL PROJECTS (Generic endpoint)
# =====================================================
@router.get("/")
async def get_projects(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all projects for the current user's company"""
    try:
        company_id = current_user.company_id
        
        # Build base query
        query_str = """
            SELECT 
                p.id,
                p.project_code as code,
                p.project_name as title,
                p.description,
                p.status,
                p.project_value as value,
                p.start_date as startDate,
                p.end_date as endDate,
                p.project_manager_id,
                p.client_id,
                p.created_at as createdDate,
                c.company_name as client_name,
                CONCAT(u.first_name, ' ', u.last_name) as project_manager_name
            FROM projects p
            LEFT JOIN companies c ON p.client_id = c.id
            LEFT JOIN users u ON p.project_manager_id = u.id
            WHERE p.company_id = :company_id
        """
        
        params = {"company_id": company_id, "limit": limit, "skip": skip}
        
        # Add filters
        if status and status != 'all':
            query_str += " AND p.status = :status"
            params["status"] = status
        
        if search:
            query_str += " AND (p.project_name LIKE :search OR p.project_code LIKE :search)"
            params["search"] = f"%{search}%"
        
        query_str += " ORDER BY p.created_at DESC LIMIT :limit OFFSET :skip"
        
        result = db.execute(text(query_str), params)
        
        projects = []
        for row in result:
            projects.append({
                "id": row.id,
                "code": row.code,
                "title": row.title,
                "description": row.description,
                "status": row.status,
                "value": float(row.value) if row.value else 0.0,
                "startDate": row.startDate.isoformat() if row.startDate else None,
                "endDate": row.endDate.isoformat() if row.endDate else None,
                "project_manager_id": row.project_manager_id,
                "client_id": row.client_id,
                "createdDate": row.createdDate.isoformat() if row.createdDate else None,
                "client_name": row.client_name,
                "project_manager_name": row.project_manager_name
            })
        
        return {
            "success": True,
            "data": projects,
            "total": len(projects)
        }
        
    except Exception as e:
        logger.error(f" Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )



# =====================================================
# GET PROJECT DOCUMENTS
# =====================================================
@router.get("/{project_id}/documents")
async def get_project_documents(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all documents for a specific project"""
    try:
        logger.info(f" Fetching documents for project {project_id}, company {current_user.company_id}")
        
        # FIXED QUERY: Join through contracts table since documents don't have project_id
        query_str = """
            SELECT
                d.id,
                d.document_name as name,
                d.document_type as type,
                d.file_size as size,
                d.file_path as path,
                d.uploaded_at as uploadedAt,
                d.uploaded_by,
                CONCAT(u.first_name, ' ', u.last_name) as uploaded_by_name,
                c.contract_number,
                c.contract_title
            FROM documents d
            INNER JOIN contracts c ON d.contract_id = c.id
            LEFT JOIN users u ON d.uploaded_by = u.id
            WHERE c.project_id = :project_id
            AND c.company_id = :company_id
            ORDER BY d.uploaded_at DESC
        """
        
        result = db.execute(
            text(query_str), 
            {
                "project_id": project_id,
                "company_id": current_user.company_id
            }
        )
        
        documents = []
        for row in result:
            documents.append({
                "id": row.id,
                "name": row.name,
                "type": row.type,
                "size": format_file_size(row.size) if row.size else "Unknown",
                "path": row.path,
                "uploadedAt": row.uploadedAt.isoformat() if row.uploadedAt else None,
                "uploaded_by": row.uploaded_by,
                "uploaded_by_name": row.uploaded_by_name or "Unknown",
                "contract_number": row.contract_number,
                "contract_title": row.contract_title
            })
        
        logger.info(f" Found {len(documents)} documents for project {project_id}")
        
        return {
            "success": True,
            "data": documents,
            "count": len(documents),
            "message": f"Found {len(documents)} documents"
        }
        
    except Exception as e:
        logger.error(f" Error fetching documents: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch documents: {str(e)}"
        )


@router.post("/{project_id}/documents/upload")
async def upload_project_documents(
    project_id: int,
    files: List[UploadFile] = File(...),
    document_type: str = Form(default="correspondence"),
    notes: Optional[str] = Form(default=None),
    contract_id: Optional[int] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload multiple documents to a project
    Documents must be linked to a contract within the project
    """
    try:
        from datetime import datetime
        
        # Verify project exists
        project_query = text("""
            SELECT id, project_name FROM projects 
            WHERE id = :project_id AND company_id = :company_id
        """)
        
        project = db.execute(project_query, {
            "project_id": project_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied"
            )
        
        #  FIXED: Properly verify contract exists and belongs to this project
        if not contract_id:
            # Check if project has any contracts
            contract_query = text("""
                SELECT id 
                FROM contracts 
                WHERE project_id = :project_id 
                AND company_id = :company_id
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            contract = db.execute(contract_query, {
                "project_id": project_id,
                "company_id": current_user.company_id
            }).fetchone()
            
            if contract:
                contract_id = contract.id
                logger.info(f" Using existing contract {contract_id} for uploads")
            else:
                # Create a default contract for document uploads
                create_contract_query = text("""
                    INSERT INTO contracts (
                        project_id, company_id, contract_number, contract_title,
                        contract_type, created_by, created_at
                    ) VALUES (
                        :project_id, :company_id, :contract_number, :contract_title,
                        :contract_type, :created_by, NOW()
                    )
                """)
                
                contract_number = f"DOCS-{project_id}-{datetime.now().strftime('%Y%m%d%H%M')}"
                
                result = db.execute(create_contract_query, {
                    "project_id": project_id,
                    "company_id": current_user.company_id,
                    "contract_number": contract_number,
                    "contract_title": f"Project Documents - {project.project_name}",
                    "contract_type": "Document Repository",
                    "created_by": current_user.id
                })
                
                db.commit()
                contract_id = result.lastrowid
                logger.info(f" Created default contract {contract_id} for document uploads")
        else:
            #  VERIFY the provided contract_id exists and belongs to this project
            verify_contract_query = text("""
                SELECT id 
                FROM contracts 
                WHERE id = :contract_id 
                AND project_id = :project_id 
                AND company_id = :company_id
            """)
            
            verified_contract = db.execute(verify_contract_query, {
                "contract_id": contract_id,
                "project_id": project_id,
                "company_id": current_user.company_id
            }).fetchone()
            
            if not verified_contract:
                logger.warning(f" Contract {contract_id} not found or doesn't belong to project {project_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Contract {contract_id} not found or doesn't belong to this project"
                )
        
        #  DOUBLE-CHECK: Verify contract_id exists before proceeding
        final_check = text("SELECT id FROM contracts WHERE id = :contract_id")
        contract_exists = db.execute(final_check, {"contract_id": contract_id}).fetchone()
        
        if not contract_exists:
            logger.error(f" Contract {contract_id} does not exist in database!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Contract verification failed. Please try again."
            )
        
        logger.info(f" Contract {contract_id} verified successfully")
        
        uploaded_documents = []
        errors = []
        
        # Create upload directory
        upload_dir = Path(f"app/uploads/projects/{project_id}")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            try:
                # Read file content
                content = await file.read()
                file_size = len(content)
                
                # Validate file size (50MB max)
                if file_size > 50 * 1024 * 1024:
                    errors.append({
                        "filename": file.filename,
                        "error": "File size exceeds 50MB"
                    })
                    continue
                
                # Calculate file hash
                file_hash = hashlib.sha256(content).hexdigest()
                
                # Check for duplicates using contract_id
                check_duplicate_query = text("""
                    SELECT id, document_name 
                    FROM documents 
                    WHERE contract_id = :contract_id 
                    AND hash_value = :file_hash
                    LIMIT 1
                """)
                
                duplicate = db.execute(check_duplicate_query, {
                    "contract_id": contract_id,
                    "file_hash": file_hash
                }).fetchone()
                
                if duplicate:
                    errors.append({
                        "filename": file.filename,
                        "error": f"Duplicate file already exists: {duplicate.document_name}"
                    })
                    continue
                
                # Save file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_ext = Path(file.filename).suffix
                safe_filename = f"{Path(file.filename).stem[:50]}_{timestamp}{file_ext}"
                file_path = upload_dir / safe_filename
                
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                # Insert document
                insert_query = text("""
                    INSERT INTO documents (
                        contract_id, company_id, document_name, document_type, 
                        file_path, file_size, hash_value, mime_type,
                        uploaded_by, uploaded_at
                    ) VALUES (
                        :contract_id, :company_id, :document_name, :document_type,
                        :file_path, :file_size, :hash_value, :mime_type,
                        :uploaded_by, :uploaded_at
                    )
                """)
                
                logger.info(f" Inserting document '{file.filename}' with contract_id={contract_id}")
                
                result = db.execute(insert_query, {
                    "contract_id": int(contract_id),  # Ensure it's an integer
                    "company_id": int(current_user.company_id),
                    "document_name": file.filename,
                    "document_type": document_type,
                    "file_path": str(file_path.relative_to(Path("app"))),
                    "file_size": file_size,
                    "hash_value": file_hash,
                    "mime_type": file.content_type,
                    "uploaded_by": int(current_user.id),
                    "uploaded_at": datetime.utcnow()
                })
                
                db.commit()
                document_id = result.lastrowid
                
                uploaded_documents.append({
                    "id": document_id,
                    "name": file.filename,
                    "size": file_size,
                    "type": file_ext.replace('.', '').lower()
                })
                
                logger.info(f" Document uploaded: {file.filename} (ID: {document_id})")
                
            except Exception as e:
                logger.error(f" Error uploading {file.filename}: {str(e)}")
                errors.append({
                    "filename": file.filename,
                    "error": str(e)
                })
                db.rollback()
        
        return {
            "success": True,
            "message": f"Uploaded {len(uploaded_documents)} of {len(files)} files",
            "data": {
                "uploaded": uploaded_documents,
                "errors": errors,
                "project_id": project_id,
                "contract_id": contract_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Upload error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )
    

# Helper function for file size formatting
def format_file_size(size_bytes):
    """Format file size in bytes to human readable format"""
    if not size_bytes:
        return "0 B"
    
    try:
        size_bytes = int(size_bytes)
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    except:
        return str(size_bytes)

# =====================================================
# GET SINGLE PROJECT
# =====================================================
@router.get("/{project_id}")
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single project by ID"""
    try:
        company_id = current_user.company_id
        
        query = text("""
            SELECT 
                p.*,
                c.company_name as client_name,
                CONCAT(u.first_name, ' ', u.last_name) as manager_name
            FROM projects p
            LEFT JOIN companies c ON p.client_id = c.id
            LEFT JOIN users u ON p.project_manager_id = u.id
            WHERE p.id = :project_id AND p.company_id = :company_id
        """)
        
        result = db.execute(query, {
            "project_id": project_id,
            "company_id": company_id
        }).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return {
            "success": True,
            "data": {
                "id": result.id,
                "project_code": result.project_code,
                "project_name": result.project_name,
                "description": result.description,
                "status": result.status,
                "project_value": float(result.project_value) if result.project_value else 0.0,
                "start_date": result.start_date.isoformat() if result.start_date else None,
                "end_date": result.end_date.isoformat() if result.end_date else None,
                "project_manager_id": result.project_manager_id,
                "client_id": result.client_id,
                "client_name": result.client_name,
                "manager_name": result.manager_name,
                "created_at": result.created_at.isoformat() if result.created_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# CREATE PROJECT
# =====================================================
@router.post("/")
async def create_project(
    project: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new project"""
    try:
        company_id = current_user.company_id
        user_id = current_user.id
        
        logger.info(f"➕ Creating project: {project.title}")
        
        # Check if project code already exists
        exists = db.execute(
            text("SELECT id FROM projects WHERE project_code = :code AND company_id = :company_id"),
            {"code": project.code, "company_id": company_id}
        ).fetchone()
        
        if exists:
            raise HTTPException(status_code=400, detail="Project code already exists")
        
        # Insert project
        query = text("""
            INSERT INTO projects (
                company_id, project_code, project_name, description,
                status, project_manager_id, client_id, start_date,
                end_date, project_value, created_by, created_at, updated_at
            ) VALUES (
                :company_id, :code, :title, :description,
                :status, :manager_id, :client_id, :start_date,
                :end_date, :value, :user_id, NOW(), NOW()
            )
        """)
        
        db.execute(query, {
            "company_id": company_id,
            "code": project.code,
            "title": project.title,
            "description": project.description,
            "status": project.status,
            "manager_id": project.project_manager_id,
            "client_id": project.client_id,
            "start_date": project.start_date,
            "end_date": project.end_date,
            "value": project.value,
            "user_id": user_id
        })
        
        db.commit()
        
        # Get the created project
        result = db.execute(
            text("SELECT * FROM projects WHERE project_code = :code AND company_id = :company_id"),
            {"code": project.code, "company_id": company_id}
        ).fetchone()
        
        logger.info(f" Project created: {result.id}")
        
        return {
            "success": True,
            "message": "Project created successfully",
            "project_id": result.id
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



# =====================================================
# UPDATE PROJECT
# =====================================================
@router.put("/{project_id}")
async def update_project(
    project_id: int,
    project: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a project"""
    try:
        company_id = current_user.company_id
        
        logger.info(f"✏️ Updating project {project_id}")
        
        # Check if project exists
        exists = db.execute(
            text("SELECT id FROM projects WHERE id = :id AND company_id = :company_id"),
            {"id": project_id, "company_id": company_id}
        ).fetchone()
        
        if not exists:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Build update query dynamically
        update_fields = []
        params = {"project_id": project_id, "company_id": company_id}
        
        if project.title is not None:
            update_fields.append("project_name = :title")
            params["title"] = project.title
        
        if project.status is not None:
            update_fields.append("status = :status")
            params["status"] = project.status
        
        if project.project_manager_id is not None:
            update_fields.append("project_manager_id = :manager_id")
            params["manager_id"] = project.project_manager_id
        
        if project.client_id is not None:
            update_fields.append("client_id = :client_id")
            params["client_id"] = project.client_id
        
        if project.description is not None:
            update_fields.append("description = :description")
            params["description"] = project.description
        
        if project.start_date is not None:
            update_fields.append("start_date = :start_date")
            params["start_date"] = project.start_date
        
        if project.end_date is not None:
            update_fields.append("end_date = :end_date")
            params["end_date"] = project.end_date
        
        if project.value is not None:
            update_fields.append("project_value = :value")
            params["value"] = project.value
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("updated_at = NOW()")
        
        query = text(f"""
            UPDATE projects 
            SET {', '.join(update_fields)}
            WHERE id = :project_id AND company_id = :company_id
        """)
        
        db.execute(query, params)
        db.commit()
        
        logger.info(f" Project {project_id} updated")
        
        return {"success": True, "message": "Project updated successfully", "project_id": project_id}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# DELETE PROJECT
# =====================================================
@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project"""
    try:
        company_id = current_user.company_id
        
        logger.info(f"🗑️ Deleting project {project_id}")
        
        # Check if project exists
        exists = db.execute(
            text("SELECT id, project_name FROM projects WHERE id = :id AND company_id = :company_id"),
            {"id": project_id, "company_id": company_id}
        ).fetchone()
        
        if not exists:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Delete project
        db.execute(
            text("DELETE FROM projects WHERE id = :id AND company_id = :company_id"),
            {"id": project_id, "company_id": company_id}
        )
        db.commit()
        
        logger.info(f" Project {project_id} deleted")
        
        return {"success": True, "message": "Project deleted successfully"}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f" Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))




# =====================================================
# FILE: app/api/api_v1/projects/projects.py
# Add this endpoint for direct project-level document uploads
# =====================================================

@router.post("/{project_id}/documents/upload")
async def upload_project_documents(
    project_id: int,
    files: List[UploadFile] = File(...),
    document_type: str = Form(default="project_document"),
    notes: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload documents directly to a project
    Documents are stored in the documents table and linked via project_documents junction table
    """
    try:
        from pathlib import Path
        import hashlib
        import uuid
        from datetime import datetime
        
        logger.info(f"📤 Uploading {len(files)} documents to project {project_id}")
        
        # Verify project exists and user has access
        project_query = text("""
            SELECT id, project_name, project_code 
            FROM projects 
            WHERE id = :project_id AND company_id = :company_id
        """)
        
        project = db.execute(project_query, {
            "project_id": project_id,
            "company_id": current_user.company_id
        }).fetchone()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied"
            )
        
        # Define upload directory
        UPLOAD_BASE_DIR = Path("app/static/uploads/project_documents")
        project_upload_dir = UPLOAD_BASE_DIR / f"project_{project_id}"
        project_upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Allowed file extensions
        ALLOWED_EXTENSIONS = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'txt': 'text/plain',
            'rtf': 'application/rtf',
            'odt': 'application/vnd.oasis.opendocument.text',
            'eml': 'message/rfc822'
        }
        
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
        
        uploaded_documents = []
        errors = []
        
        for file in files:
            try:
                # Validate file extension
                file_ext = Path(file.filename).suffix.lower().replace('.', '')
                if file_ext not in ALLOWED_EXTENSIONS:
                    errors.append({
                        "filename": file.filename,
                        "error": f"File type .{file_ext} not allowed"
                    })
                    continue
                
                # Read file content
                content = await file.read()
                file_size = len(content)
                
                # Validate file size
                if file_size > MAX_FILE_SIZE:
                    errors.append({
                        "filename": file.filename,
                        "error": f"File size exceeds 50MB limit"
                    })
                    continue
                
                # Generate unique document ID and hash
                doc_id = str(uuid.uuid4())
                file_hash = hashlib.sha256(content).hexdigest()
                
                # Save file
                file_path = project_upload_dir / f"{doc_id}_{file.filename}"
                with open(file_path, "wb") as f:
                    f.write(content)
                
                # Get relative path for database
                relative_path = str(file_path.relative_to(Path("app")))
                
                # Prepare metadata - MUST include project_id for correspondence integration
                metadata = json.dumps({
                    "project_id": int(project_id),  # Ensure integer for correspondence queries
                    "project_name": project.project_name,
                    "project_code": project.project_code,
                    "original_filename": file.filename,
                    "notes": notes,
                    "upload_source": "project_dashboard",
                    "upload_mode": "project-level",
                    "uploader_email": current_user.email
                })
                
                # Insert into documents table
                insert_doc_query = text("""
                    INSERT INTO documents (
                        id, company_id, document_name, document_type,
                        file_path, file_size, mime_type, hash_value,
                        uploaded_by, uploaded_at, version, access_count, metadata
                    ) VALUES (
                        :id, :company_id, :document_name, :document_type,
                        :file_path, :file_size, :mime_type, :hash_value,
                        :uploaded_by, :uploaded_at, 1, 0, :metadata
                    )
                """)
                
                db.execute(insert_doc_query, {
                    "id": doc_id,
                    "company_id": current_user.company_id,
                    "document_name": file.filename,
                    "document_type": document_type,
                    "file_path": relative_path,
                    "file_size": file_size,
                    "mime_type": ALLOWED_EXTENSIONS.get(file_ext, 'application/octet-stream'),
                    "hash_value": file_hash,
                    "uploaded_by": current_user.id,
                    "uploaded_at": datetime.utcnow(),
                    "metadata": metadata
                })
                
                # Link document to project via project_documents junction table
                link_query = text("""
                    INSERT INTO project_documents (project_id, document_id, created_at)
                    VALUES (:project_id, :document_id, :created_at)
                    ON DUPLICATE KEY UPDATE created_at = :created_at
                """)
                
                db.execute(link_query, {
                    "project_id": project_id,
                    "document_id": doc_id,
                    "created_at": datetime.utcnow()
                })
                
                db.commit()
                
                uploaded_documents.append({
                    "id": doc_id,
                    "name": file.filename,
                    "size": file_size,
                    "type": file_ext,
                    "uploaded_at": datetime.utcnow().isoformat()
                })
                
                logger.info(f" Uploaded: {file.filename} (ID: {doc_id})")
                
            except Exception as e:
                logger.error(f"❌ Error uploading {file.filename}: {str(e)}")
                errors.append({
                    "filename": file.filename,
                    "error": str(e)
                })
                db.rollback()
        
        return {
            "success": True,
            "message": f"Uploaded {len(uploaded_documents)} of {len(files)} files",
            "data": {
                "uploaded": uploaded_documents,
                "errors": errors,
                "project_id": project_id,
                "project_name": project.project_name
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Upload error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/{project_id}/documents")
async def get_project_documents(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all documents for a specific project"""
    try:
        logger.info(f"📂 Fetching documents for project {project_id}")
        
        # Query documents linked via project_documents junction table
        query_str = """
            SELECT
                d.id,
                d.document_name as name,
                d.document_type as type,
                d.file_size as size,
                d.file_path as path,
                d.uploaded_at as uploadedAt,
                d.uploaded_by,
                CONCAT(u.first_name, ' ', u.last_name) as uploaded_by_name
            FROM documents d
            INNER JOIN project_documents pd ON d.id = pd.document_id
            LEFT JOIN users u ON d.uploaded_by = u.id
            WHERE pd.project_id = :project_id
            AND d.company_id = :company_id
            ORDER BY d.uploaded_at DESC
        """
        
        result = db.execute(
            text(query_str), 
            {
                "project_id": project_id,
                "company_id": current_user.company_id
            }
        )
        
        documents = []
        for row in result:
            # Format file size
            size_str = "Unknown"
            if row.size:
                size_bytes = int(row.size)
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.2f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
            
            documents.append({
                "id": row.id,
                "name": row.name,
                "type": row.type,
                "size": size_str,
                "path": row.path,
                "uploadedAt": row.uploadedAt.isoformat() if row.uploadedAt else None,
                "uploaded_by": row.uploaded_by,
                "uploaded_by_name": row.uploaded_by_name or "Unknown"
            })
        
        logger.info(f" Found {len(documents)} documents")
        
        return {
            "success": True,
            "data": documents,
            "count": len(documents),
            "message": f"Found {len(documents)} documents"
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching documents: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch documents: {str(e)}"
        )