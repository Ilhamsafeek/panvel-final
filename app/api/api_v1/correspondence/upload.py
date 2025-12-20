# app/api/api_v1/correspondence/upload.py
"""
Document Upload API for Correspondence Management
Handles file uploads with validation, storage, and database integration
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status,Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import hashlib
import uuid
import os
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# Allowed file types
ALLOWED_EXTENSIONS = {
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'txt': 'text/plain',
    'rtf': 'application/rtf',
    'odt': 'application/vnd.oasis.opendocument.text',
    'eml': 'message/rfc822',
    'msg': 'application/vnd.ms-outlook',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png'
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_BATCH_SIZE = 10
UPLOAD_BASE_DIR = Path("app/uploads/correspondence")


def validate_file(file: UploadFile) -> tuple:
    """Validate uploaded file"""
    # Check file extension
    file_ext = Path(file.filename).suffix.lower().replace('.', '')
    
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"File type .{file_ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS.keys())}"
    
    return True, "Valid"


def calculate_file_hash(content: bytes) -> str:
    """Calculate SHA-256 hash of file content"""
    return hashlib.sha256(content).hexdigest()



def save_file_to_disk(
    content: bytes,
    filename: str,
    project_id,  # Can be int or 'standalone'
    company_id: int
) -> str:
    """Save file to disk and return relative path"""
    # Create directory structure
    if project_id == 'standalone':
        save_dir = UPLOAD_BASE_DIR / str(company_id) / "standalone"
    else:
        save_dir = UPLOAD_BASE_DIR / str(company_id) / str(project_id)
    
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(filename).suffix
    base_name = Path(filename).stem[:50]  # Limit filename length
    unique_filename = f"{base_name}_{timestamp}{file_ext}"
    
    file_path = save_dir / unique_filename
    
    # Write file
    with open(file_path, 'wb') as f:
        f.write(content)
    
    # Return relative path for database storage
    return str(file_path.relative_to(Path("app")))

@router.post("/upload")
async def upload_document(
    files: List[UploadFile] = File(...),
    project_id: str = Form(default=""),  # ✅ Changed: Accept empty string as default
    document_type: str = Form(default="correspondence"),
    notes: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload one or more documents
    
    **Two Upload Modes:**
    1. **Project-level**: Provide project_id to associate with a project
    2. **Document-level**: Leave project_id empty for standalone documents
    """
    
    try:
        logger.info(f"📤 Upload request received from {current_user.email}")
        logger.info(f"Files count: {len(files)}")
        logger.info(f"Project ID received: '{project_id}'")
        logger.info(f"Document type: {document_type}")
        
        if not files or len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files provided"
            )
        
        # ✅ Convert project_id to int ONLY if provided and not empty
        project_id_int = None
        if project_id and project_id.strip() and project_id.strip() not in ['null', 'undefined', 'None']:
            try:
                project_id_int = int(project_id.strip())
                logger.info(f"✅ Project ID converted: {project_id_int}")
            except ValueError:
                logger.warning(f"⚠️ Invalid project_id format: '{project_id}', treating as standalone")
                project_id_int = None
        
        upload_mode = "project-level" if project_id_int else "document-level"
        logger.info(f"📋 Upload mode: {upload_mode}")
        
        if len(files) > MAX_BATCH_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum {MAX_BATCH_SIZE} files allowed per upload"
            )
        
        if project_id_int:
            project_query = text("""
                SELECT id, project_name 
                FROM projects 
                WHERE id = :project_id AND company_id = :company_id
            """)
            
            project = db.execute(project_query, {
                "project_id": project_id_int,
                "company_id": current_user.company_id
            }).fetchone()
            
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project with ID {project_id_int} not found or access denied"
                )
            
            logger.info(f"✅ Project verified: {project.project_name}")
        else:
            logger.info(f"✅ Standalone upload (no project association)")
        
        uploaded_files = []
        errors = []
        
        for idx, file in enumerate(files):
            try:
                logger.info(f"📄 Processing file {idx + 1}/{len(files)}: {file.filename}")
                
                is_valid, error_msg = validate_file(file)
                if not is_valid:
                    logger.warning(f"⚠️ Validation failed: {error_msg}")
                    errors.append(f"{file.filename}: {error_msg}")
                    continue
                
                content = await file.read()
                file_size = len(content)
                
                logger.info(f"  Size: {file_size:,} bytes")
                
                if file_size > MAX_FILE_SIZE:
                    error = f"{file.filename}: File exceeds {MAX_FILE_SIZE / 1024 / 1024}MB limit"
                    logger.warning(f"⚠️ {error}")
                    errors.append(error)
                    continue
                
                file_hash = calculate_file_hash(content)
                
                file_path = save_file_to_disk(
                    content,
                    file.filename,
                    project_id_int if project_id_int else 'standalone',
                    current_user.company_id
                )
                
                logger.info(f"  Saved to: {file_path}")
                
                doc_id = str(uuid.uuid4())
                
                insert_query = text("""
                    INSERT INTO documents (
                        id, project_id, document_name, document_type,
                        file_path, file_size, file_hash, uploaded_by,
                        created_at, status
                    ) VALUES (
                        :id, :project_id, :doc_name, :doc_type,
                        :file_path, :file_size, :file_hash, :uploaded_by,
                        NOW(), 'active'
                    )
                """)
                
                db.execute(insert_query, {
                    "id": doc_id,
                    "project_id": project_id_int,  # NULL for standalone
                    "doc_name": file.filename,
                    "doc_type": document_type,
                    "file_path": file_path,
                    "file_size": file_size,
                    "file_hash": file_hash,
                    "uploaded_by": current_user.id
                })
                
                uploaded_files.append({
                    "id": doc_id,
                    "filename": file.filename,
                    "file_size": file_size,
                    "document_type": document_type,
                    "upload_mode": upload_mode
                })
                
                logger.info(f"  ✅ Uploaded successfully")
                
            except Exception as e:
                logger.error(f"❌ Error uploading {file.filename}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                errors.append(f"{file.filename}: {str(e)}")
        
        db.commit()
        
        logger.info(f"✅ Upload complete: {len(uploaded_files)} successful, {len(errors)} failed")
        
        return {
            "success": True,
            "uploaded": len(uploaded_files),
            "failed": len(errors),
            "upload_mode": upload_mode,
            "files": uploaded_files,
            "errors": errors if errors else None,
            "message": f"Successfully uploaded {len(uploaded_files)} of {len(files)} files ({upload_mode})"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Upload error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

        
def save_standalone_file(
    content: bytes,
    filename: str,
    company_id: int
) -> str:
    """Save standalone file (not associated with project)"""
    # Create directory: uploads/correspondence/{company_id}/standalone/
    save_dir = UPLOAD_BASE_DIR / str(company_id) / "standalone"
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(filename).suffix
    base_name = Path(filename).stem[:50]
    unique_filename = f"{base_name}_{timestamp}{file_ext}"
    
    file_path = save_dir / unique_filename
    
    # Write file
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return str(file_path.relative_to(Path("app")))

@router.get("/documents/{project_id}")
async def get_project_documents(
    project_id: int,
    document_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all documents for a project
    
    - **project_id**: Project ID to fetch documents for
    - **document_type**: Optional filter by document type
    """
    
    try:
        logger.info(f"📂 Fetching documents for project {project_id}")
        
        # Build query
        query_str = """
            SELECT 
                id, document_name, document_type, file_path,
                file_size, mime_type, uploaded_by, uploaded_at,
                metadata
            FROM documents
            WHERE JSON_EXTRACT(metadata, '$.project_id') = :project_id
        """
        params = {"project_id": project_id}
        
        if document_type:
            query_str += " AND document_type = :document_type"
            params["document_type"] = document_type
        
        query_str += " ORDER BY uploaded_at DESC"
        
        query = text(query_str)
        result = db.execute(query, params).fetchall()
        
        documents = []
        for row in result:
            documents.append({
                "id": row.id,
                "document_name": row.document_name,
                "document_type": row.document_type,
                "file_size": row.file_size,
                "mime_type": row.mime_type,
                "uploaded_by": row.uploaded_by,
                "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None
            })
        
        return {
            "success": True,
            "project_id": project_id,
            "documents": documents,
            "total": len(documents)
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch documents: {str(e)}"
        )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a document
    
    - **document_id**: Document ID to delete
    """
    
    try:
        # Check document exists and user has permission
        check_query = text("""
            SELECT id, file_path, uploaded_by, document_name
            FROM documents
            WHERE id = :document_id
        """)
        result = db.execute(check_query, {"document_id": document_id}).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Delete file from disk
        try:
            if result.file_path and os.path.exists(result.file_path):
                os.remove(result.file_path)
                logger.info(f"🗑️ Deleted file: {result.file_path}")
        except Exception as file_error:
            logger.warning(f"⚠️ Could not delete file: {file_error}")
        
        # Delete from database
        delete_query = text("DELETE FROM documents WHERE id = :document_id")
        db.execute(delete_query, {"document_id": document_id})
        db.commit()
        
        logger.info(f"✅ Document deleted: {document_id}")
        
        return {
            "success": True,
            "message": f"Document '{result.document_name}' deleted successfully",
            "document_id": document_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error deleting document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )