from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional
import os
import json
from datetime import datetime
from api.deps import get_current_user
from models.user import User
from services.Media.media_utils import upload_media
from config import TEMP_DIR, media_collection
from bson import ObjectId

router = APIRouter(prefix="/api/video", tags=["video-export"])

def is_valid_objectid(oid: str) -> bool:
    """Check if a string is a valid ObjectId"""
    try:
        ObjectId(oid)
        return True
    except:
        return False

def build_flexible_query(user_id: str, video_id: str) -> dict:
    """Build a flexible query that handles both ObjectId and string IDs"""
    query = {"user_id": ObjectId(user_id)}
    
    if is_valid_objectid(video_id):
        query["_id"] = ObjectId(video_id)
    else:
        # Search by multiple possible fields
        query["$or"] = [
            {"id": video_id},
            {"metadata.generated_id": video_id},
            {"external_video_id": video_id},
            {"metadata.editing_session.video_id_reference": video_id}
        ]
    
    return query

@router.post("/upload-edited")
async def upload_edited_video(
    video_file: UploadFile = File(...),
    original_video_id: Optional[str] = Form(None),
    title: str = Form(...),
    description: Optional[str] = Form(""),
    processing_steps: Optional[str] = Form("[]"),  # JSON string of processing steps
    timeline_data: Optional[str] = Form("{}"),  # JSON string of timeline state
    current_user: User = Depends(get_current_user)
):
    """
    Upload edited video and update in database
    """
    try:
        user_id = str(current_user.id)
        
        # Parse processing steps and timeline data
        try:
            processing_steps_data = json.loads(processing_steps) if processing_steps else []
            timeline_data_parsed = json.loads(timeline_data) if timeline_data else {}
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
        
        # Save uploaded file temporarily
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_video_path = os.path.join(TEMP_DIR, f"edited_{timestamp}_{video_file.filename}")
        
        with open(temp_video_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # Upload to Cloudinary with enhanced metadata
        upload_result = await upload_media(
            file_path=temp_video_path,
            user_id=user_id,
            folder="videos/edited",
            resource_type="video",
            prompt=f"Edited: {title}",
            metadata={
                "original_video_id": original_video_id,
                "is_edited": True,
                "processing_steps": processing_steps_data,
                "timeline_data": timeline_data_parsed,
                "edit_timestamp": datetime.now().isoformat(),
                "video_duration": timeline_data_parsed.get("duration", 0),
                "audio_tracks_count": len(timeline_data_parsed.get("audioTracks", [])),
                "trim_applied": timeline_data_parsed.get("trimStart", 0) > 0 or timeline_data_parsed.get("trimEnd", 0) > 0
            }
        )
        
        # Update original video if specified
        if original_video_id:
            try:
                media_col = media_collection()
                
                # Prepare query to find original video
                query = {"user_id": ObjectId(user_id)}
                
                try:
                    # Try to treat as ObjectId first
                    ObjectId(original_video_id)
                    query["_id"] = ObjectId(original_video_id)
                except:
                    # If not valid ObjectId, search by other fields
                    query["$or"] = [
                        {"id": original_video_id},
                        {"metadata.generated_id": original_video_id},
                        {"external_video_id": original_video_id}
                    ]
                
                original_video = await media_col.find_one(query)
                
                if original_video:
                    # Update original video with edited version reference
                    await media_col.update_one(
                        {"_id": original_video["_id"]},
                        {
                            "$set": {
                                "metadata.edited_version_id": upload_result["id"],
                                "metadata.has_edited_version": True,
                                "metadata.last_edited": datetime.now().isoformat(),
                                "updated_at": datetime.now()
                            }
                        }
                    )
                    print(f"Updated original video {original_video_id} with edited version reference")
                else:
                    print(f"Warning: Original video {original_video_id} not found in database")
            except Exception as e:
                print(f"Warning: Could not update original video reference: {e}")
                # Don't fail the whole operation if this fails
        
        # Clean up temp file
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        
        return {
            "success": True,
            "video_id": upload_result["id"],
            "video_url": upload_result["url"],
            "public_id": upload_result["public_id"],
            "original_video_updated": bool(original_video_id),
            "processing_summary": {
                "steps_applied": len(processing_steps_data),
                "audio_tracks": len(timeline_data_parsed.get("audioTracks", [])),
                "trim_applied": timeline_data_parsed.get("trimStart", 0) > 0 or timeline_data_parsed.get("trimEnd", 0) > 0
            },
            "message": "Edited video uploaded and database updated successfully"
        }
        
    except Exception as e:
        # Clean up on error
        if 'temp_video_path' in locals() and os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        
        print(f"Error uploading edited video: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload edited video: {str(e)}")

@router.post("/save-edit-session")
async def save_edit_session(
    video_id: str = Form(...),
    timeline_data: str = Form(...),  # JSON string of timeline state
    current_user: User = Depends(get_current_user)
):
    """
    Save current editing session for later continuation
    """
    try:
        # Parse timeline data
        try:
            timeline_data_parsed = json.loads(timeline_data)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid timeline data JSON: {str(e)}")
        
        # Prepare query based on video_id format
        media_col = media_collection()
        query = build_flexible_query(str(current_user.id), video_id)
        
        # Update video with editing session data
        update_result = await media_col.update_one(
            query,
            {
                "$set": {
                    "metadata.editing_session": {
                        "timeline_data": timeline_data_parsed,
                        "saved_at": datetime.now().isoformat(),
                        "session_active": True,
                        "video_id_reference": video_id  # Store original ID for reference
                    },
                    "updated_at": datetime.now()
                }
            }
        )
        
        operation_type = "updated"
        
        if update_result.matched_count == 0:
            # If still not found, create a session document with the provided video_id
            # This handles cases where the video might not be in database yet
            session_doc = {
                "user_id": ObjectId(current_user.id),
                "external_video_id": video_id,
                "media_type": "video",
                "title": f"Edit Session - {video_id}",
                "content": "Editing session data",
                "url": "",  # Will be updated when video is uploaded
                "public_id": "",
                "metadata": {
                    "is_editing_session": True,
                    "editing_session": {
                        "timeline_data": timeline_data_parsed,
                        "saved_at": datetime.now().isoformat(),
                        "session_active": True,
                        "video_id_reference": video_id
                    }
                },
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            insert_result = await media_col.insert_one(session_doc)
            operation_type = "created"
            print(f"Created new editing session document for video_id: {video_id}")
        
        return {
            "success": True,
            "message": "Edit session saved successfully",
            "video_id": video_id,
            "operation": operation_type
        }
        
    except Exception as e:
        print(f"Error saving edit session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save edit session: {str(e)}")

@router.get("/edited-versions/{original_video_id}")
async def get_edited_versions(
    original_video_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get all edited versions of a video
    """
    try:
        media_col = media_collection()
        
        # Build query to find edited versions
        query = {
            "user_id": ObjectId(current_user.id),
            "metadata.is_edited": True
        }
        
        # Add original_video_id condition with flexible matching
        try:
            # Try as ObjectId first
            ObjectId(original_video_id)
            query["metadata.original_video_id"] = original_video_id
        except:
            # If not ObjectId, use string matching or regex
            query["$or"] = [
                {"metadata.original_video_id": original_video_id},
                {"metadata.original_video_id": {"$regex": original_video_id}},
                {"external_video_id": original_video_id}
            ]
        
        # Find all edited versions
        edited_videos = await media_col.find(query).sort("created_at", -1).to_list(length=None)
        
        # Convert ObjectId to string for JSON serialization
        for video in edited_videos:
            video["_id"] = str(video["_id"])
            video["user_id"] = str(video["user_id"])
        
        return {
            "success": True,
            "edited_versions": edited_videos,
            "count": len(edited_videos),
            "original_video_id": original_video_id
        }
        
    except Exception as e:
        print(f"Error getting edited versions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get edited versions: {str(e)}")

@router.get("/edit-session/{video_id}")
async def get_edit_session(
    video_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get saved editing session for a video
    """
    try:
        media_col = media_collection()
        query = build_flexible_query(str(current_user.id), video_id)
        video = await media_col.find_one(query)
        
        if not video:
            return {
                "success": True,
                "has_session": False,
                "session_data": None,
                "video_id": video_id,
                "message": "No editing session found for this video"
            }
        
        editing_session = video.get("metadata", {}).get("editing_session")
        
        return {
            "success": True,
            "has_session": bool(editing_session),
            "session_data": editing_session,
            "video_id": video_id,
            "database_id": str(video.get("_id", ""))
        }
        
    except Exception as e:
        print(f"Error getting edit session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get edit session: {str(e)}")
