from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from typing import Optional
import os
import tempfile
from datetime import datetime
import asyncio
import httpx
from services.voice_service import get_voice_by_id
from api.deps import get_current_user
from models.user import User
from services.Media.media_utils import create_video, create_multi_scene_video, add_subtitles, upload_media, get_media_by_id
from services.Media.text_to_speech import generate_speech_async
from services.subtitle_service import generate_srt_content
from config import TEMP_DIR
from schemas.media import MediaResponse, CompleteVideoRequest, VideoFromComponentsRequest
from models.user import User

# Import validation functions
from services.Media.media_validation import is_valid_audio_media, is_valid_video_media, is_valid_image_media

router = APIRouter(prefix="/api/video", tags=["video"])

@router.post("/create-complete", response_model=MediaResponse)
async def create_complete_video(
    request: CompleteVideoRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create a complete video from script, voice, background, and optionally subtitles
    """
    # try:
    #     user_id = str(current_user.id)        # Step 1: Generate audio from script
    #     print("Generating audio from script...")
    #     audio_path = None
    #     fallback_audio_path = os.path.join(TEMP_DIR, "voice_v1_166ef5ee-d315-4883-b3b1-b53f6d8e083b.wav")
    #     fallback_audio_url = "https://res.cloudinary.com/dsozekr7k/video/upload/v1750415589/audio/pymxnd8dbtlb9rsqwmxe.wav"
    #     try:
    #         audio_result = await generate_speech_async(request.script_text, request.voice_id, user_id)            
    #         if audio_result and audio_result.get("audio_url"):
    #             # Download audio from Cloudinary to temp file for video creation
    #             audio_path = os.path.join(TEMP_DIR, f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
    #             async with httpx.AsyncClient() as client:
    #                 audio_response = await client.get(audio_result["audio_url"])
    #                 audio_response.raise_for_status()
    #                 with open(audio_path, "wb") as f:
    #                     f.write(audio_response.content)
    #             print(f"✅ Successfully generated and downloaded audio: {audio_path}")
    #         else:
    #             raise Exception("No audio URL returned from generation")
                
    #     except Exception as e:
    #         print(f"⚠️ Audio generation failed: {e}")
    #         # Use fallback audio file if available
    #         if os.path.exists(fallback_audio_path):
    #             audio_path = fallback_audio_path
    #             print(f"🔄 Using fallback audio file: {fallback_audio_path}")
    #             # Create a mock audio_result for metadata
    #             audio_result = {
    #                 "audio_url": f"file://{fallback_audio_path}",
    #                 "duration": 30,  # Estimated duration
    #                 "audio_id": "fallback_audio"
    #             }
    #         else:
    #             print(f"❌ Fallback audio file not found: {fallback_audio_path}")    #             raise HTTPException(status_code=500, detail="Failed to generate audio and no fallback available")
    
    try:
        user_id = str(current_user.id)
        
        # Validate user_id is a valid ObjectId format
        try:
            from bson import ObjectId
            ObjectId(user_id)  # This will raise exception if invalid
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Step 1: Generate audio from script
        print("Generating audio from script...")
        audio_path = None
        fallback_audio_path = os.path.join(TEMP_DIR, "fallback_audio.wav")
        fallback_audio_url = "https://res.cloudinary.com/dsozekr7k/video/upload/v1750415589/audio/pymxnd8dbtlb9rsqwmxe.wav"
        
        # Get voice configuration and convert to actual voice name
        voice_data = get_voice_by_id(request.voice_id)
        if not voice_data:
            raise HTTPException(status_code=400, detail=f"Voice {request.voice_id} not found")
            
        # Extract the actual voice name for TTS
        actual_voice_name = voice_data.get("name", "Kore")  # Use voice name, fallback to Kore
        print(f"🎤 Using voice: {actual_voice_name} (mapped from {request.voice_id})")
        
        try:
            audio_result = await generate_speech_async(request.script_text, actual_voice_name, user_id)
            if audio_result and audio_result.get("audio_url"):
                # Download audio from Cloudinary to temp file for video creation
                audio_path = os.path.join(TEMP_DIR, f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
                async with httpx.AsyncClient() as client:
                    audio_response = await client.get(audio_result["audio_url"])
                    audio_response.raise_for_status()
                    with open(audio_path, "wb") as f:
                        f.write(audio_response.content)
                print(f"✅ Successfully generated and downloaded audio: {audio_path}")
            else:
                raise Exception("No audio URL returned from generation")

        except Exception as e:
            print(f"⚠️ Audio generation failed: {e}")
            # Fallback: download fallback audio if not already downloaded
            if not os.path.exists(fallback_audio_path):
                try:
                    print(f"🔄 Downloading fallback audio from: {fallback_audio_url}")
                    async with httpx.AsyncClient() as client:
                        fallback_response = await client.get(fallback_audio_url)
                        fallback_response.raise_for_status()
                        with open(fallback_audio_path, "wb") as f:
                            f.write(fallback_response.content)
                    print(f"✅ Fallback audio downloaded: {fallback_audio_path}")
                except Exception as download_err:
                    print(f"❌ Failed to download fallback audio: {download_err}")
                    raise HTTPException(status_code=500, detail="Failed to generate audio and fallback download failed.")            # Use fallback audio file
            audio_path = fallback_audio_path
            print(f"🔄 Using fallback audio file: {fallback_audio_path}")
            audio_result = {
                "audio_url": f"file://{fallback_audio_path}",
                "duration": 30,  # Estimated or fixed duration
                "audio_id": "fallback_audio"
            }

        if not audio_path or not os.path.exists(audio_path):
            raise HTTPException(status_code=500, detail="No audio file available for video creation")
          # Step 2: Get background images
        print("Fetching background images...")
        background_paths = []
        background_ids = []
        
        # Handle multiple background images if provided
        if request.background_image_ids and len(request.background_image_ids) > 0:
            background_ids = request.background_image_ids
            print(f"Using multiple backgrounds: {background_ids}")
        elif request.background_image_id:
            background_ids = [request.background_image_id]
            print(f"Using single background: {request.background_image_id}")
        else:
            raise HTTPException(status_code=400, detail="No background image provided")
        
        # Download all background images with validation
        for i, bg_id in enumerate(background_ids):
            background_media = await get_media_by_id(bg_id)
            if not background_media:
                print(f"Warning: Background image {bg_id} not found, skipping")
                continue
            
            # Validate media is actually an image
            if not is_valid_image_media(background_media):
                print(f"Warning: Media {bg_id} is not a valid image file. "
                      f"Media type: {background_media.get('media_type')}, "
                      f"Public ID: {background_media.get('public_id')}")
                continue
                
            # Download background image to temp file
            background_path = os.path.join(TEMP_DIR, f"bg_{bg_id}_{i}.jpg")
            async with httpx.AsyncClient() as client:
                response = await client.get(background_media["url"])
                response.raise_for_status()
                with open(background_path, "wb") as f:
                    f.write(response.content)
            background_paths.append(background_path)
        
        if not background_paths:
            raise HTTPException(status_code=404, detail="No valid background images found")
        
        # Step 3: Create video from images and audio
        print(f"Creating video from {len(background_paths)} image(s) and audio...")
        video_path = os.path.join(TEMP_DIR, f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        
        if len(background_paths) > 1:
            # Multi-scene video
            video_result = create_multi_scene_video(background_paths, audio_path, video_path)
        else:
            # Single scene video
            video_result = create_video(background_paths[0], audio_path, video_path)
        
        if not video_result:
            raise HTTPException(status_code=500, detail="Failed to create video")
        
        final_video_path = video_result
          # Step 4: Add subtitles if enabled
        if request.subtitle_enabled:
            print("Adding subtitles to video...")
            # Generate SRT content
            srt_content = generate_srt_content(request.script_text, audio_result.get("duration", 30))
            
            # Save SRT to temp file
            srt_path = os.path.join(TEMP_DIR, f"subtitles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            
            # Add subtitles to video
            subtitled_video_path = os.path.join(TEMP_DIR, f"final_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
            subtitle_result = add_subtitles(video_path, srt_path, subtitled_video_path)
            
            if subtitle_result:
                final_video_path = subtitle_result
                # Clean up intermediate video
                if os.path.exists(video_path):
                    os.remove(video_path)
                if os.path.exists(srt_path):
                    os.remove(srt_path)
          # Step 5: Upload final video to cloud
        print("Uploading final video to cloud...")
          # Convert subtitle_style to string if it's an object
        subtitle_style_str = "default"
        if isinstance(request.subtitle_style, str):
            subtitle_style_str = request.subtitle_style
        elif hasattr(request.subtitle_style, 'name'):
            subtitle_style_str = request.subtitle_style.name
        
        upload_result = await upload_media(
            final_video_path, 
            user_id,
            folder="videos",
            resource_type="video",
            prompt=f"Complete video: {request.script_text[:50]}...",            metadata={
                "voice_id": request.voice_id,
                "audio_id": audio_result.get("audio_id"),  # Link to audio file
                "background_image_id": request.background_image_id,  # Keep for backward compatibility
                "background_image_ids": background_ids,  # Multiple background support
                "is_multi_scene": len(background_ids) > 1,
                "scene_count": len(background_ids),
                "subtitle_enabled": request.subtitle_enabled,
                "subtitle_language": request.subtitle_language,
                "subtitle_style": subtitle_style_str,
                "script_text": request.script_text[:200]  # Save partial script for reference
            }
        )        # Clean up temporary files
        cleanup_files = [audio_path, final_video_path] + background_paths
        for temp_file in cleanup_files:
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
        
        # Return MediaResponse with correct structure
        return {
            "id": upload_result["id"],
            "user_id": user_id,
            "content": f"Complete video: {request.script_text[:50]}...",
            "media_type": "video",
            "url": upload_result["url"],
            "public_id": upload_result["public_id"],            "metadata": {
                "voice_id": request.voice_id,
                "audio_id": audio_result.get("audio_id"),
                "background_image_id": request.background_image_id,  # Keep for backward compatibility
                "background_image_ids": background_ids,  # Multiple background support
                "is_multi_scene": len(background_ids) > 1,
                "scene_count": len(background_ids),
                "subtitle_enabled": request.subtitle_enabled,
                "subtitle_language": request.subtitle_language,
                "subtitle_style": subtitle_style_str,
                "script_text": request.script_text[:200]
            },
            "created_at": datetime.now(),
            "updated_at": datetime.now()        }
        
    except Exception as e:
        print(f"Error creating complete video: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create video: {str(e)}")

@router.post("/create-from-components")
async def create_video_from_components(
    request: VideoFromComponentsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create video from existing audio file and background image
    """
    try:
        user_id = str(current_user.id)
        
        # Validate user_id is a valid ObjectId format
        try:
            from bson import ObjectId
            ObjectId(user_id)  # This will raise exception if invalid
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Get audio file and validate it's actually audio
        audio_media = await get_media_by_id(request.audio_file_id)
        if not audio_media:
            raise HTTPException(status_code=404, detail="Audio file not found")
        
        # Validate media is actually audio
        if not is_valid_audio_media(audio_media):
            raise HTTPException(
                status_code=400, 
                detail=f"Media with ID {request.audio_file_id} is not a valid audio file. "
                       f"Media type: {audio_media.get('media_type')}, "
                       f"Public ID: {audio_media.get('public_id')}"
            )
          # Get background images
        background_paths = []
        background_ids = []
        
        # Handle multiple background images if provided
        if request.background_image_ids and len(request.background_image_ids) > 0:
            background_ids = request.background_image_ids
        elif request.background_image_id:
            background_ids = [request.background_image_id]
        else:
            raise HTTPException(status_code=400, detail="No background image provided")
        
        # Download files to temp
        audio_path = os.path.join(TEMP_DIR, f"audio_{request.audio_file_id}.wav")
        
        # Download audio
        async with httpx.AsyncClient() as client:
            audio_response = await client.get(audio_media["url"])
            audio_response.raise_for_status()
            with open(audio_path, "wb") as f:
                f.write(audio_response.content)
            
            # Download all background images with validation
            for i, bg_id in enumerate(background_ids):
                background_media = await get_media_by_id(bg_id)
                if not background_media:
                    print(f"Warning: Background image {bg_id} not found, skipping")
                    continue
                
                # Validate media is actually an image
                if not is_valid_image_media(background_media):
                    print(f"Warning: Media {bg_id} is not a valid image file. "
                          f"Media type: {background_media.get('media_type')}, "
                          f"Public ID: {background_media.get('public_id')}")
                    continue
                    
                background_path = os.path.join(TEMP_DIR, f"bg_{bg_id}_{i}.jpg")
                bg_response = await client.get(background_media["url"])
                bg_response.raise_for_status()
                with open(background_path, "wb") as f:
                    f.write(bg_response.content)
                background_paths.append(background_path)
        
        if not background_paths:
            raise HTTPException(status_code=404, detail="No valid background images found")
        
        # Create video
        video_path = os.path.join(TEMP_DIR, f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        
        if len(background_paths) > 1:
            # Multi-scene video
            video_result = create_multi_scene_video(background_paths, audio_path, video_path)
        else:
            # Single scene video
            video_result = create_video(background_paths[0], audio_path, video_path)
        
        if not video_result:
            raise HTTPException(status_code=500, detail="Failed to create video")
        
        final_video_path = video_result
        
        # Add subtitles if enabled and script provided
        if request.subtitle_enabled and request.script_text:
            srt_content = generate_srt_content(request.script_text, 30)  # Estimate duration
            srt_path = os.path.join(TEMP_DIR, f"subtitles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt")
            
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            
            subtitled_video_path = os.path.join(TEMP_DIR, f"final_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
            subtitle_result = add_subtitles(video_path, srt_path, subtitled_video_path)
            
            if subtitle_result:
                final_video_path = subtitle_result
                if os.path.exists(video_path):
                    os.remove(video_path)
                if os.path.exists(srt_path):
                    os.remove(srt_path)
        
        # Upload to cloud
        upload_result = await upload_media(
            final_video_path,
            user_id,
            folder="videos",
            resource_type="video",
            prompt=f"Video from components",            metadata={
                "audio_file_id": request.audio_file_id,
                "background_image_id": request.background_image_id,  # Keep for backward compatibility
                "background_image_ids": background_ids,  # Multiple background support
                "is_multi_scene": len(background_ids) > 1,
                "scene_count": len(background_ids),
                "subtitle_enabled": request.subtitle_enabled
            }
        )
          # Clean up
        cleanup_files = [audio_path, final_video_path] + background_paths
        for temp_file in cleanup_files:
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
        
        return MediaResponse(**upload_result["media"])
        
    except Exception as e:
        print(f"Error creating video from components: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create video: {str(e)}")

@router.get("/download/{video_id}")
async def download_video(
    video_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Download video file
    """
    try:
        # Get video metadata and validate it's actually a video
        video_media = await get_media_by_id(video_id)
        if not video_media:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Validate media is actually a video
        if not is_valid_video_media(video_media):
            raise HTTPException(
                status_code=400, 
                detail=f"Media with ID {video_id} is not a valid video file. "
                       f"Media type: {video_media.get('media_type')}, "
                       f"Public ID: {video_media.get('public_id')}"
            )
          # Check if user owns the video
        if str(video_media["user_id"]) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Access denied")        
        # Download video to temp file
        temp_video_path = os.path.join(TEMP_DIR, f"download_{video_id}.mp4")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(video_media["url"])
            response.raise_for_status()
            with open(temp_video_path, "wb") as f:
                f.write(response.content)
        
        # Return file for download
        return FileResponse(
            temp_video_path,
            media_type="video/mp4",
            filename=f"{video_media.get('prompt', 'video')}.mp4"
        )
        
    except Exception as e:
        print(f"Error downloading video: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download video: {str(e)}")

@router.get("/preview/{video_id}")
async def preview_video(
    video_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get video URL for preview
    """
    try:
        video_media = await get_media_by_id(video_id)
        if not video_media:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Validate media is actually a video
        if not is_valid_video_media(video_media):
            raise HTTPException(
                status_code=400, 
                detail=f"Media with ID {video_id} is not a valid video file. "
                       f"Media type: {video_media.get('media_type')}, "
                       f"Public ID: {video_media.get('public_id')}"
            )
          # Check if user owns the video
        if str(video_media["user_id"]) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {
            "video_url": video_media["url"],
            "title": video_media.get("prompt", "Video"),
            "duration": video_media.get("metadata", {}).get("duration"),
            "created_at": video_media["created_at"]
        }
        
    except Exception as e:
        print(f"Error getting video preview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get video: {str(e)}")

@router.get("/validate-media/{media_id}")
async def validate_media_type(
    media_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Test endpoint to validate media type detection
    """
    try:
        media_data = await get_media_by_id(media_id)
        if not media_data:
            raise HTTPException(status_code=404, detail="Media not found")
        
        # Check if user owns the media
        if str(media_data["user_id"]) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {
            "media_id": media_id,
            "media_info": {
                "stored_media_type": media_data.get("media_type"),
                "public_id": media_data.get("public_id"),
                "url": media_data.get("url"),
                "filename": media_data.get("title")
            },
            "validation_results": {
                "is_valid_audio": is_valid_audio_media(media_data),
                "is_valid_video": is_valid_video_media(media_data),
                "is_valid_image": is_valid_image_media(media_data)
            },
            "recommendations": {
                "can_use_for_audio": is_valid_audio_media(media_data),
                "can_use_for_background": is_valid_image_media(media_data),
                "can_preview_as_video": is_valid_video_media(media_data)
            }
        }
        
    except Exception as e:
        print(f"Error validating media: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to validate media: {str(e)}")
