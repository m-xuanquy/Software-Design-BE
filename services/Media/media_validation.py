"""
Media validation utilities for checking media types based on multiple indicators
"""

def is_valid_audio_media(media_data: dict) -> bool:
    """
    Validate if media is actually an audio file based on multiple indicators
    
    Args:
        media_data: Media document from database
        
    Returns:
        bool: True if media is valid audio, False otherwise
    """
    if not media_data:
        return False
    
    media_id = media_data.get("id", "unknown")
    
    # First check if it's explicitly marked as video - exclude it
    public_id = media_data.get("public_id", "")
    if public_id.startswith("video/"):
        print(f"📹➡️🎵 {media_id}: Rejecting as audio - public_id starts with 'video/': {public_id}")
        return False
        
    # Check URL patterns for video - exclude them
    url = media_data.get("url", "")
    if "/video/" in url:
        print(f"📹➡️🎵 {media_id}: Rejecting as audio - '/video/' in URL: {url[:100]}")
        return False
        
    # Check for video file extensions - exclude them
    for video_ext in [".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mkv"]:
        if url.lower().endswith(video_ext):
            print(f"📹➡️🎵 {media_id}: Rejecting as audio - video extension {video_ext} in URL: {url[:100]}")
            return False
    
    # Check media_type
    if media_data.get("media_type") == "audio":
        print(f"🎵✅ {media_id}: Accepting as audio - media_type is 'audio'")
        return True
    
    # Check public_id prefix
    if public_id.startswith("audio/"):
        print(f"🎵✅ {media_id}: Accepting as audio - public_id starts with 'audio/': {public_id}")
        return True
    
    # Check URL patterns (some cloud providers use different URL patterns for audio)
    if "/audio/" in url or "/raw/" in url:
        # Additional format check for raw uploads
        for audio_ext in [".mp3", ".wav", ".ogg", ".aac", ".flac", ".m4a"]:
            if url.lower().endswith(audio_ext):
                print(f"🎵✅ {media_id}: Accepting as audio - audio extension {audio_ext} in URL: {url[:100]}")
                return True
    
    print(f"🎵❌ {media_id}: Rejecting as audio - no audio indicators found (type: {media_data.get('media_type')}, public_id: {public_id})")
    return False

def is_valid_video_media(media_data: dict) -> bool:
    """
    Validate if media is actually a video file
    """
    if not media_data:
        return False
    
    media_id = media_data.get("id", "unknown")
    
    # First check if it's explicitly marked as audio - exclude it
    public_id = media_data.get("public_id", "")
    if public_id.startswith("audio/"):
        print(f"🎵➡️📹 {media_id}: Rejecting as video - public_id starts with 'audio/': {public_id}")
        return False
    
    # Check URL patterns for audio - exclude them
    url = media_data.get("url", "")
    if "/audio/" in url or "/raw/" in url:
        # Additional format check for raw uploads
        for audio_ext in [".mp3", ".wav", ".ogg", ".aac", ".flac", ".m4a"]:
            if url.lower().endswith(audio_ext):
                print(f"🎵➡️📹 {media_id}: Rejecting as video - audio extension {audio_ext} in URL: {url[:100]}")
                return False
    
    # Check media_type
    if media_data.get("media_type") == "video":
        print(f"📹✅ {media_id}: Accepting as video - media_type is 'video'")
        return True
    
    # Check public_id prefix for video
    if public_id.startswith("video/"):
        print(f"📹✅ {media_id}: Accepting as video - public_id starts with 'video/': {public_id}")
        return True
        
    # Check URL patterns for video
    if "/video/" in url:
        print(f"📹✅ {media_id}: Accepting as video - '/video/' in URL: {url[:100]}")
        return True
        
    # Check for video file extensions
    for video_ext in [".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mkv"]:
        if url.lower().endswith(video_ext):
            print(f"📹✅ {media_id}: Accepting as video - video extension {video_ext} in URL: {url[:100]}")
            return True
    
    print(f"📹❌ {media_id}: Rejecting as video - no video indicators found (type: {media_data.get('media_type')}, public_id: {public_id})")
    return False

def is_valid_image_media(media_data: dict) -> bool:
    """
    Validate if media is actually an image file
    """
    if not media_data:
        return False
    
    # First check if it's explicitly marked as video or audio - exclude them
    public_id = media_data.get("public_id", "")
    if public_id.startswith("video/") or public_id.startswith("audio/"):
        return False
        
    # Check URL patterns for video/audio - exclude them
    url = media_data.get("url", "")
    if "/video/" in url or "/audio/" in url:
        return False
        
    # Check for video/audio file extensions - exclude them
    for non_image_ext in [".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mkv", ".mp3", ".wav", ".ogg", ".aac", ".flac", ".m4a"]:
        if url.lower().endswith(non_image_ext):
            return False
    
    # Check media_type
    if media_data.get("media_type") == "image":
        return True
    
    # Check public_id prefix for image
    if public_id.startswith("image/"):
        return True
        
    # Check URL patterns for image
    if "/image/" in url:
        return True
        
    # Check for image file extensions
    for image_ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff"]:
        if url.lower().endswith(image_ext):
            return True
    
    return False
