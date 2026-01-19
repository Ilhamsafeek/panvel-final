# =====================================================
# FILE: app/api/api_v1/contracts/comments.py
# SIMPLIFIED BUBBLE COMMENTS API WITH EXACT POSITIONING
# =====================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.core.database import get_db
from app.core.dependencies import get_current_user
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)


class CommentCreate(BaseModel):
    contract_id: int
    comment_text: str
    selected_text: str
    position_start: int
    position_end: int
    start_xpath: Optional[str] = ''
    change_type: Optional[str] = 'comment'  # 'comment', 'insert', 'delete'
    original_text: Optional[str] = None
    new_text: Optional[str] = None


class CommentUpdate(BaseModel):
    comment_text: str


class CommentResponse(BaseModel):
    id: int
    contract_id: int
    user_id: int
    user_name: str
    comment_text: str
    selected_text: str
    position_start: int
    position_end: int
    change_type: str
    original_text: Optional[str]
    new_text: Optional[str]
    created_at: str
    updated_at: str
    can_delete: bool


@router.post("/comments/add")
async def add_comment(
    data: CommentCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Add a new bubble comment with exact positioning"""
    try:
        logger.info(f"📝 Adding comment by user {current_user.id}")
        
        position_info = {
            'start': data.position_start,
            'end': data.position_end,
            'start_xpath': data.start_xpath or '',
            'change_type': data.change_type,
            'original_text': data.original_text,
            'new_text': data.new_text
        }
        
        insert_query = text("""
            INSERT INTO contract_comments 
            (contract_id, user_id, comment_text, selected_text, position_info, created_at)
            VALUES 
            (:contract_id, :user_id, :comment_text, :selected_text, :position_info, NOW())
        """)
        
        result = db.execute(insert_query, {
            'contract_id': data.contract_id,
            'user_id': current_user.id,
            'comment_text': data.comment_text,
            'selected_text': data.selected_text,
            'position_info': json.dumps(position_info)
        })
        db.commit()
        
        comment_id = result.lastrowid
        
        # Get user name
        user_query = text("""
            SELECT CONCAT(first_name, ' ', last_name) as full_name
            FROM users WHERE id = :user_id
        """)
        user_result = db.execute(user_query, {'user_id': current_user.id}).fetchone()
        user_name = user_result[0] if user_result else "Unknown User"
        
        return {
            'success': True,
            'message': 'Comment added successfully',
            'comment': {
                'id': comment_id,
                'contract_id': data.contract_id,
                'user_id': current_user.id,  # ← Include user_id
                'user_name': user_name,
                'comment_text': data.comment_text,
                'selected_text': data.selected_text,
                'position_start': data.position_start,
                'position_end': data.position_end,
                'change_type': data.change_type,
                'original_text': data.original_text,
                'new_text': data.new_text,
                'created_at': datetime.now().isoformat(),
                'can_delete': True  # Owner can always delete their own
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error adding comment: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        

@router.get("/comments/{contract_id}")
async def get_comments(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all comments for a contract with position data"""
    try:
        query = text("""
            SELECT 
                cc.id,
                cc.contract_id,
                cc.user_id,
                CONCAT(u.first_name, ' ', u.last_name) as user_name,
                cc.comment_text,
                cc.selected_text,
                cc.position_info,
                cc.created_at,
                cc.updated_at,
                CASE WHEN cc.user_id = :current_user_id THEN 1 ELSE 0 END as can_delete
            FROM contract_comments cc
            INNER JOIN users u ON cc.user_id = u.id
            WHERE cc.contract_id = :contract_id
            ORDER BY cc.created_at DESC
        """)
        
        results = db.execute(query, {
            'contract_id': contract_id,
            'current_user_id': current_user.id
        }).fetchall()
        
        comments = []
        for row in results:
            # Parse position info JSON
            try:
                if row[6]:  # position_info column
                    pos_info = json.loads(row[6]) if isinstance(row[6], str) else row[6]
                else:
                    pos_info = {}
            except:
                pos_info = {}
            
            comments.append({
                'id': row[0],
                'contract_id': row[1],
                'user_id': row[2],  # Include user_id so frontend can compare
                'user_name': row[3],
                'comment_text': row[4],
                'selected_text': row[5],
                'position_start': pos_info.get('start', 0),
                'position_end': pos_info.get('end', 0),
                'start_xpath': pos_info.get('start_xpath', ''),
                'change_type': pos_info.get('change_type', 'comment'),
                'original_text': pos_info.get('original_text'),
                'new_text': pos_info.get('new_text'),
                'created_at': row[7].isoformat() if row[7] else '',
                'updated_at': row[8].isoformat() if row[8] else '',
                'can_delete': bool(row[9])  # Only owner can delete
            })
        
        logger.info(f"✅ Retrieved {len(comments)} comments for contract {contract_id}")
        
        return {
            'success': True,
            'comments': comments,
            'current_user_id': current_user.id  # ← ADD THIS LINE
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching comments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a comment (only by creator)"""
    try:
        # Check if comment belongs to current user
        check_query = text("""
            SELECT user_id FROM contract_comments WHERE id = :comment_id
        """)
        result = db.execute(check_query, {'comment_id': comment_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        if result[0] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only delete your own comments")
        
        # Delete comment
        delete_query = text("""
            DELETE FROM contract_comments WHERE id = :comment_id
        """)
        db.execute(delete_query, {'comment_id': comment_id})
        db.commit()
        
        logger.info(f"✅ Comment {comment_id} deleted successfully")
        
        return {
            'success': True,
            'message': 'Comment deleted successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting comment: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/comments/{comment_id}")
async def update_comment(
    comment_id: int,
    data: CommentUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a comment (only by creator)"""
    try:
        # Check ownership
        check_query = text("""
            SELECT user_id FROM contract_comments WHERE id = :comment_id
        """)
        result = db.execute(check_query, {'comment_id': comment_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        if result[0] != current_user.id:
            raise HTTPException(status_code=403, detail="You can only edit your own comments")
        
        # Update comment
        update_query = text("""
            UPDATE contract_comments 
            SET comment_text = :comment_text, updated_at = NOW()
            WHERE id = :comment_id
        """)
        db.execute(update_query, {
            'comment_id': comment_id,
            'comment_text': data.comment_text
        })
        db.commit()
        
        return {
            'success': True,
            'message': 'Comment updated successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating comment: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))