import subprocess
import imageio_ffmpeg
import os
import tempfile
from config import TEMP_DIR
import cloudinary
import cloudinary.uploader
from datetime import datetime
from typing import Optional, Dict
from config import media_collection
from models.media import MediaModel, MediaType
from bson import ObjectId
from io import BytesIO
import httpx

media_colt = media_collection()

async def upload_media(file_path: str, user_id: str, folder: str = "media", resource_type: str = "auto", 
                 prompt: str = None, metadata: Dict = None) -> Dict:
    """
    Upload media to Cloudinary and save metadata to MongoDB
    
    Args:
        file_path: Path to local file
        user_id: ID of the user uploading the media
        folder: Cloudinary folder
        resource_type: auto, image, video, raw
        prompt: Media prompt
        metadata: Additional metadata
        
    Returns:
        Dictionary with upload result and database ID
    """
    # Get filename for the prompt if not provided
    if not prompt:
        prompt = os.path.basename(file_path)
    
    # Upload to Cloudinary
    try:
        upload_result = cloudinary.uploader.upload(
            file_path,
            folder=folder,
            resource_type=resource_type,
            unique_filename=True
        )
        print(f"Uploaded {file_path} to Cloudinary")
    except Exception as e:
        raise Exception(f"Failed to upload media to Cloudinary: {str(e)}")

    # Determine media type
    media_type = MediaType.TEXT
    if resource_type == "image" or (resource_type == "auto" and upload_result.get("resource_type") == "image"):
        media_type = MediaType.IMAGE
    elif resource_type == "video" or (resource_type == "auto" and upload_result.get("resource_type") == "video"):
        media_type = MediaType.VIDEO
    elif upload_result.get("format") in ["mp3", "wav", "ogg"]:
        media_type = MediaType.AUDIO
    
    # Convert user_id to ObjectId for MongoDB storage
    try:
        from bson import ObjectId
        if isinstance(user_id, str):
            user_id_obj = ObjectId(user_id)
        else:
            user_id_obj = user_id
    except Exception as e:
        raise Exception(f"Invalid user_id format: {user_id}. Error: {str(e)}")
    
    # Create media document
    media_doc = MediaModel(
        user_id=str(user_id_obj),  # Store as string in Pydantic model
        title=upload_result.get("original_filename", "Untitled"),
        content=prompt,
        media_type=media_type,
        url=upload_result["secure_url"],
        public_id=upload_result["public_id"],
        metadata=metadata or {},
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Insert into MongoDB
    if not media_collection:
        raise Exception("Media collection is not initialized")
    try:
        media_dict = media_doc.model_dump(by_alias=True, exclude_unset=True)
        # Remove _id field completely to let MongoDB generate it
        media_dict.pop("_id", None)
        
        # Convert user_id back to ObjectId for MongoDB storage
        media_dict["user_id"] = user_id_obj
        
        result = await media_collection().insert_one(media_dict)
        print(f"Inserted media document into MongoDB with ID {result.inserted_id}")
    except Exception as e:
        raise Exception(f"Failed to insert media into MongoDB: {str(e)}")

    return {
        "id": str(result.inserted_id),
        "public_id": upload_result["public_id"],
        "url": upload_result["secure_url"],
        "media_type": media_type
    }

async def get_media_by_id(media_id: str) -> Optional[Dict]:
    """Get media by ID"""
    try:
        from bson import ObjectId
        
        # Try to convert to ObjectId, if fails, use as string (for custom IDs)
        try:
            query_id = ObjectId(media_id)
            media = await media_collection().find_one({"_id": query_id})
        except:
            # If not a valid ObjectId, try searching by custom ID or string ID
            media = await media_collection().find_one({"id": media_id})
        
        if media:
            media["id"] = str(media.get("_id", media.get("id", media_id)))
            if "user_id" in media and media["user_id"]:
                media["user_id"] = str(media["user_id"])
            if "_id" in media:
                del media["_id"]
        return media
    except Exception as e:
        print(f"Error getting media: {e}")
        return None

async def get_media_by_user(user_id: str, page: int = 1, size: int = 10, media_type: Optional[MediaType] = None) -> Dict:
    """Get media by user ID with pagination and optional filtering"""
    try:
        from bson import ObjectId
        skip = (page - 1) * size
        
        # Build query filter - try both ObjectId and string format
        try:
            user_id_obj = ObjectId(user_id)
            # Query for both ObjectId and string format of user_id
            user_query = {
                "$or": [
                    {"user_id": user_id_obj},
                    {"user_id": user_id}
                ]
            }
        except:
            # If user_id is not a valid ObjectId, only query by string
            user_query = {"user_id": user_id}
            
        query_filter = user_query
        if media_type:
            query_filter = {
                "$and": [
                    user_query,
                    {"media_type": media_type.value}
                ]
            }
        
        # Get total count
        total = await media_collection().count_documents(query_filter)
        
        # Get media with pagination
        cursor = media_collection().find(query_filter).skip(skip).limit(size).sort("created_at", -1)
        media_list = []
        
        async for media in cursor:
            media["id"] = str(media["_id"])
            media["user_id"] = str(media["user_id"])
            del media["_id"]
            media_list.append(media)
            
        return {
            "media": media_list,
            "total": total,
            "page": page,
            "size": size
        }
    except Exception as e:
        print(f"Error getting user media: {e}")
        return {"media": [], "total": 0, "page": page, "size": size}

async def update_media(media_id: str, user_id: str, update_data: Dict) -> Optional[Dict]:
    """Update media metadata"""
    try:
        from bson import ObjectId
        
        # Add updated timestamp
        update_data["updated_at"] = datetime.now()
        
        # Try both ObjectId and string format for user_id
        try:
            user_id_obj = ObjectId(user_id)
            query_filter = {
                "_id": ObjectId(media_id),
                "$or": [
                    {"user_id": user_id_obj},
                    {"user_id": user_id}
                ]
            }
        except:
            query_filter = {"_id": ObjectId(media_id), "user_id": user_id}
        
        result = await media_collection().update_one(
            query_filter,
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            return await get_media_by_id(media_id)
        return None
    except Exception as e:
        print(f"Error updating media: {e}")
        return None

async def delete_media(media_id: str, user_id: str) -> bool:
    """Delete media from Cloudinary and MongoDB"""
    try:
        from bson import ObjectId
        
        # Try both ObjectId and string format for user_id
        try:
            user_id_obj = ObjectId(user_id)
            query_filter = {
                "_id": ObjectId(media_id),
                "$or": [
                    {"user_id": user_id_obj},
                    {"user_id": user_id}
                ]
            }
        except:
            query_filter = {"_id": ObjectId(media_id), "user_id": user_id}
        
        # Get media to get public_id
        media = await media_collection().find_one(query_filter)
        if not media:
            return False
            
        # Delete from Cloudinary
        cloudinary.uploader.destroy(media["public_id"])
        
        # Delete from MongoDB
        result = await media_collection().delete_one(query_filter)
        
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting media: {e}")
        return False

def create_video(image_path, audio_path, output_path=None):
    """Create a video from an image and audio using FFmpeg"""
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    if not output_path:
        output_path = os.path.join(TEMP_DIR, f"{os.path.splitext(os.path.basename(image_path))[0]}.mp4")
    
    print(f"Creating video with:")
    print(f"  Image: {image_path} (exists: {os.path.exists(image_path)})")
    print(f"  Audio: {audio_path} (exists: {os.path.exists(audio_path)})")
    print(f"  Output: {output_path}")
    
    try:
        command = [
            ffmpeg_path,
            "-loop", "1",  # Loop the image
            "-i", image_path,  # Input image
            "-i", audio_path,  # Input audio
            "-c:v", "libx264",  # Video codec
            "-tune", "stillimage",  # Optimize for still images
            "-c:a", "aac",  # Audio codec
            "-b:a", "192k",  # Audio bitrate
            "-pix_fmt", "yuv420p",  # Pixel format
            "-shortest",  # Match video duration to audio
            "-y",  # Overwrite output file if it exists
            output_path  # Output file
        ]

        print(f"FFmpeg command: {' '.join(command)}")
        subprocess.run(command, check=True)
        print(f"Video created successfully: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error creating video: {e}")
        return None

def add_subtitles(video_path, subtitle_path, output_path=None):
    """Add subtitles to a video using FFmpeg"""
    if not output_path:
        output_path = os.path.join(TEMP_DIR, f"sub_{os.path.basename(video_path)}")
    
    try:
        # Convert paths to absolute paths with forward slashes
        video_path_abs = video_path.replace('\\', '/')
        subtitle_path_abs = subtitle_path.replace('\\', '/')
        output_path_abs = output_path.replace('\\', '/')
        
        command = [
            "ffmpeg",
            "-i", video_path_abs,  # Input video
            "-vf", f"subtitles='{subtitle_path_abs}'",  # Quote the subtitle path
            "-c:a", "copy",  # Copy audio without re-encoding
            "-y",  # Overwrite output file if it exists
            output_path_abs  # Output video
        ]

        print(f"Running command: {' '.join(command)}")
        subprocess.run(command, check=True)
        return output_path
    except Exception as e:
        print(f"Error adding subtitles: {e}")
        return None

def upload_video_to_cloud(video_path, title=None, description=None):
    """Create video and upload to Cloudinary"""
    # Upload to Cloudinary
    result = upload_media(
        video_path, 
        folder="videos",
        resource_type="video",
        title=title,
        description=description
    )
    
    # Clean up temporary file
    if os.path.exists(video_path) and video_path.startswith(TEMP_DIR):
        os.remove(video_path)
        
    return result


async def download_video_media_from_cloud(media_id:str) ->BytesIO|None:
    try:
        video = BytesIO()
        media = await get_media_by_id(media_id)
        if not media or not media.get("url"):
            return None
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", media.get("url")) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(8192):
                    video.write(chunk)
        video.seek(0)
        return video
    except Exception as e:
        return None

def create_multi_scene_video(image_paths, audio_path, output_path=None):
    """Create a multi-scene video from multiple images and audio using FFmpeg"""
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    if not output_path:
        output_path = os.path.join(TEMP_DIR, f"multiscene_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
    
    print(f"Creating multi-scene video with:")
    print(f"  Images: {[img for img in image_paths]} (count: {len(image_paths)})")
    print(f"  Audio: {audio_path} (exists: {os.path.exists(audio_path)})")
    print(f"  Output: {output_path}")
    
    if len(image_paths) == 1:
        # If only one image, use the regular create_video function
        return create_video(image_paths[0], audio_path, output_path)
    
    try:
        # Simplified approach: Get audio duration using ffmpeg instead of ffprobe
        print("Getting audio duration...")
        duration_cmd = [
            ffmpeg_path,
            "-i", audio_path,
            "-f", "null", "-",
            "-hide_banner",
            "-loglevel", "error"
        ]
        
        # Try to get duration, fallback to 30s if fails
        try:
            result = subprocess.run(duration_cmd, capture_output=True, text=True, stderr=subprocess.STDOUT)
            # Parse duration from ffmpeg output
            import re
            duration_match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", result.stderr)
            if duration_match:
                h, m, s = duration_match.groups()
                audio_duration = int(h) * 3600 + int(m) * 60 + float(s)
            else:
                audio_duration = 30.0
        except:
            audio_duration = 30.0
        
        # Calculate duration per scene
        scene_duration = audio_duration / len(image_paths)
        print(f"Audio duration: {audio_duration}s, Scene duration: {scene_duration}s each")
        
        # Create a simpler approach: create individual scene videos then concat
        scene_videos = []
        for i, image_path in enumerate(image_paths):
            if not os.path.exists(image_path):
                print(f"Warning: Image {image_path} does not exist, skipping")
                continue
                
            scene_video = os.path.join(TEMP_DIR, f"scene_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
            
            # Create video for this scene
            cmd = [
                ffmpeg_path,
                "-loop", "1",
                "-t", str(scene_duration),
                "-i", image_path,
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-pix_fmt", "yuv420p",
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
                "-r", "25",
                "-y",
                scene_video
            ]
            
            print(f"Creating scene {i+1} video: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            scene_videos.append(scene_video)
        
        if not scene_videos:
            raise Exception("No scene videos created")
          # Create concat file for ffmpeg
        concat_file = os.path.join(TEMP_DIR, f"concat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(concat_file, 'w', encoding='utf-8') as f:
            for video in scene_videos:
                # Use forward slashes for ffmpeg compatibility
                video_path = os.path.abspath(video).replace('\\', '/')
                f.write(f"file '{video_path}'\n")
        
        # Concatenate all scene videos and add audio
        final_cmd = [
            ffmpeg_path,
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-y",
            output_path
        ]
        
        print(f"Final concat command: {' '.join(final_cmd)}")
        subprocess.run(final_cmd, check=True)
        
        # Cleanup temp files
        for video in scene_videos:
            if os.path.exists(video):
                os.remove(video)
        if os.path.exists(concat_file):
            os.remove(concat_file)
        
        print(f"Multi-scene video created successfully: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"Error creating multi-scene video: {e}")
        # Cleanup on error
        try:
            for video in scene_videos:
                if os.path.exists(video):
                    os.remove(video)
            if os.path.exists(concat_file):
                os.remove(concat_file)
        except:
            pass
            
        # Fallback to single image video using first image
        if image_paths:
            print(f"Falling back to single image video using: {image_paths[0]}")
            return create_video(image_paths[0], audio_path, output_path)
        return None


def cleanup_temp_file(file_path: str):
    """
    Clean up a single temporary file
    
    Args:
        file_path: Path to the file to delete
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        print(f"Error cleaning up temp file {file_path}: {e}")


def cleanup_temp_files(file_paths: list):
    """
    Clean up multiple temporary files
    
    Args:
        file_paths: List of file paths to delete
    """
    for file_path in file_paths:
        cleanup_temp_file(file_path)

async def check_media_of_user(user_id:str, media_id:str) -> bool:
    try:
        from bson import ObjectId
        
        # Try both ObjectId and string format for user_id
        try:
            user_id_obj = ObjectId(user_id)
            query_filter = {
                "_id": ObjectId(media_id),
                "$or": [
                    {"user_id": user_id_obj},
                    {"user_id": user_id}
                ]
            }
        except:
            query_filter = {"_id": ObjectId(media_id), "user_id": user_id}
            
        media = await media_collection().find_one(query_filter)
        return media is not None
    except Exception as e:
        print(f"Error checking media ownership: {e}")
        return False