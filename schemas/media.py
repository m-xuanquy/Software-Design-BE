from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Union, List
from models.media import MediaType

# Schema for subtitle style
class SubtitleStyle(BaseModel):
    name: str = Field(default="default", description="Style name")
    fontFamily: str = Field(default="Arial", description="Font family")
    fontSize: int = Field(default=16, description="Font size")
    fontColor: str = Field(default="#FFFFFF", description="Font color")
    backgroundColor: str = Field(default="#000000", description="Background color")
    backgroundOpacity: float = Field(default=0.7, description="Background opacity")
    position: str = Field(default="bottom", description="Subtitle position")
    outline: bool = Field(default=True, description="Enable outline")
    outlineColor: str = Field(default="#000000", description="Outline color")

# Schema for creating new media
class MediaCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500, description="Prompt or text content for the media")
    media_type: MediaType = Field(..., description="Type of media")
    metadata: Optional[Dict] = Field(default={}, description="Additional metadata")

# Schema for updating media
class MediaUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=500, description="Prompt or text content for the media")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")

# Schema for complete video creation
class CompleteVideoRequest(BaseModel):
    script_text: str = Field(..., description="Script content for the video")
    voice_id: str = Field(..., description="ID of the voice to use")
    background_image_id: str = Field(..., description="ID of the background image (legacy)")
    background_image_ids: Optional[List[str]] = Field(None, description="IDs of multiple background images")
    subtitle_enabled: bool = Field(default=True, description="Whether to enable subtitles")
    subtitle_language: str = Field(default="en", description="Language for subtitles")
    subtitle_style: Union[str, SubtitleStyle] = Field(default="default", description="Style for subtitles")

# Schema for video from components
class VideoFromComponentsRequest(BaseModel):
    audio_file_id: str = Field(..., description="ID of the audio file")
    background_image_id: str = Field(..., description="ID of the background image (legacy)")
    background_image_ids: Optional[List[str]] = Field(None, description="IDs of multiple background images")
    script_text: Optional[str] = Field(None, description="Script text for subtitles")
    subtitle_enabled: bool = Field(default=False, description="Whether to enable subtitles")
    subtitle_language: str = Field(default="en", description="Language for subtitles")
    subtitle_style: Union[str, SubtitleStyle] = Field(default="default", description="Style for subtitles")

# Schema for media response
class MediaResponse(BaseModel):
    id: str = Field(..., description="Media ID")
    user_id: str = Field(..., description="User ID who owns the media")
    title: Optional[str] = Field(None, description="Title of the media")
    content: str = Field(..., description="Prompt or text content for the media")
    media_type: MediaType = Field(..., description="Type of media")
    url: str = Field(..., description="Cloudinary URL")
    public_id: str = Field(..., description="Cloudinary public ID")
    metadata: Dict = Field(default={}, description="Additional metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

# Schema for media list response
class MediaListResponse(BaseModel):
    media: list[MediaResponse]
    total: int
    page: int
    size: int

# Schema for deleting media
class MediaDelete(BaseModel):
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Deletion message")