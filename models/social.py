from pydantic import BaseModel, Field,EmailStr,ConfigDict
from datetime import datetime
from bson import ObjectId
from typing import Optional,Dict,Any,List
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated
PyObjectId = Annotated[str,BeforeValidator(str)]
class Social(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id:str = Field(...)
    facebook:Optional[List[str]] = Field(default_factory=list)
    youtube:Optional[List[str]] = Field(default_factory=list)
    model_config =ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId:str}
    )
class SocialVideoCreate(BaseModel):
    user_id:str = Field(...)
    platform: str = Field(...)
    video_url: str = Field(...)
