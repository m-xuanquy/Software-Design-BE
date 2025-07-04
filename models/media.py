from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict
from bson import ObjectId
from enum import Enum
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

def str_to_objectid(v):
    if isinstance(v, ObjectId):
        return str(v)
    return str(v)

PyObjectId = Annotated[str, BeforeValidator(str_to_objectid)]

# Media type enum
class MediaType(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TEXT = "text"

# Media model for MongoDB
class MediaModel(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId  # Link to user
    title: str
    content: str
    media_type: MediaType
    url: str  # Cloudinary URL
    public_id: str  # Cloudinary public ID
    thumbnail_url: Optional[str] = None  # Thumbnail URL for videos/images
    metadata: Optional[Dict] = {}
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    model_config = ConfigDict(
        populate_by_name = True,
        arbitrary_types_allowed = True,
        json_encoders = {ObjectId: str}
    )