from fastapi import APIRouter,Depends,HTTPException,status,Form,Query
from schemas import VideoUpLoadRequest,VideoStatsResponse,GoogleVideoStatsResponse,FacebookVideoStatsResponse
from models import User
from api.deps import get_current_user
from services.SocialNetwork import upload_video,get_video_stats,get_more_info_social_networks,get_social_videos
from services.Media.media_utils import check_media_of_user
from typing import Union,Optional
from schemas import SocialPlatform
router = APIRouter(prefix="/social", tags=["Social Media"])
@router.post("/upload-video",response_model=str)
async def upload_video_to_social(upload_request: VideoUpLoadRequest=Form(...), user: User = Depends(get_current_user)):
    try:
        # check_media_belong_user = await check_media_of_user(user_id=user.id,media_id=upload_request.media_id)
        # if not check_media_belong_user:
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="You do not have permission to upload this media."
        #     )
        result = await upload_video(user,upload_request)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload video: {str(e)}"
        ) 
    
@router.get("/video-stats",response_model=Union[GoogleVideoStatsResponse,FacebookVideoStatsResponse])
async def get_video_statstic(user:User =Depends(get_current_user),platform:str="",video_id:str="",page_id:Optional[str]=None):
    try:
        if not platform or not video_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Platform and video ID are required."
            )

        return await get_video_stats(user,video_id,platform,page_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve video statistics: {str(e)}"
        )
@router.get("/social-video",response_model=Optional[dict])
async def get_social_network_videos(user: User = Depends(get_current_user), platform: SocialPlatform = Query(...)):
    try:
        return await get_social_videos(user.id, platform)
    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.detail
        )
@router.post("/more-info",response_model=Optional[dict])
async def get_more_information_social_networks(user: User = Depends(get_current_user), platform: SocialPlatform = Form(...)):
    try:
        return await get_more_info_social_networks(user, platform)
    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.detail
        )