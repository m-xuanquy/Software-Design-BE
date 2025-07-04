from pydantic import BaseModel, Field
from enum import Enum
from typing import Dict,Any,Optional, List
from datetime import datetime
class SocialPlatform(str,Enum):
    GOOGLE = "google"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"

class VideoUpLoadRequest (BaseModel):
    media_id:str
    platform: SocialPlatform
    title: str
    description: Optional[str] = ""
    tags: Optional[List[str]] = []
    privacy_status:str = Field(default="private")
    page_id: Optional[str] = None

class VideoStatsResponse(BaseModel):
    platform:SocialPlatform
    title: str
    description: Optional[str] = ""
    platform_url:str
    created_at: datetime
class GoogleVideoStatsResponse(VideoStatsResponse):
    view_count: Optional[int] = 0
    like_count: Optional[int] = 0
    comment_count: Optional[int] = 0

class FacebookVideoStatsResponse(VideoStatsResponse):
    view_count: Optional[int] = 0
    reaction_count:Optional[Dict[str, int]] = {}
    share_count: Optional[int] = 0
    comment_count: Optional[int] = 0

class FacebookPageResponse(BaseModel):
    page_id: str
    page_name: str
    page_access_token: str
    category: Optional[str] = None
    about: Optional[str] = None
    picture_url: Optional[str] = None
    is_published: bool = True

class FacebookPageListResponse(BaseModel):
    pages: List[FacebookPageResponse]
    
class FacebookPageVideoUploadRequest(VideoUpLoadRequest):
    page_id: str  # ID of Facebook Page to upload video
    
class TikTokVideoStatsResponse(VideoStatsResponse):
    view_count: Optional[int] = 0
    like_count: Optional[int] = 0
    share_count: Optional[int] = 0
    comment_count: Optional[int] = 0
    cover_image_url: Optional[str] = ""
