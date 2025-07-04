from fastapi import HTTPException, status
from models import User
from schemas import VideoUpLoadRequest,SocialPlatform
from services.SocialNetwork import upload_video_to_youtube,get_youtube_video_stats
from .Youtube import upload_video_to_youtube, get_youtube_video_stats
from .Facebook import upload_video_to_facebook, get_facebook_video_stats,get_pages_of_user
from .TikTok import upload_video_to_tiktok,get_list_of_tiktok_videos,get_tiktok_video_stats
async def upload_video(user:User,upload_request:VideoUpLoadRequest):
    if upload_request.platform == SocialPlatform.GOOGLE:
        if not user.social_credentials or 'google' not in user.social_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google credentials are not available for the user."
            )
        return await upload_video_to_youtube(user, upload_request)
    elif upload_request.platform == SocialPlatform.FACEBOOK:
        if not user.social_credentials or 'facebook' not in user.social_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Facebook credentials are not available for the user."
            )
        
        # Get page_id from request, if not provided use first page from user credentials
        page_id = upload_request.page_id
        if not page_id:
            facebook_pages = user.social_credentials.get('facebook', {}).get('pages', [])
            if not facebook_pages:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No Facebook pages found. Please specify page_id or link your Facebook pages."
                )
            page_id = facebook_pages[0].get('id')
            
        return await upload_video_to_facebook(user, page_id, upload_request)
    elif upload_request.platform == SocialPlatform.TIKTOK:
        if not user.social_credentials or 'tiktok' not in user.social_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tiktok credentials are not available for the user."
            )
        return await upload_video_to_tiktok(user, upload_request)
async def get_video_stats(user:User,video_id:str,platform:SocialPlatform,page_id:str=None):
    if platform==SocialPlatform.GOOGLE:
        return await get_youtube_video_stats(user, video_id)
    elif platform==SocialPlatform.FACEBOOK:
        return await get_facebook_video_stats(user, video_id,page_id)
    elif platform==SocialPlatform.TIKTOK:
        return await get_tiktok_video_stats(user, video_id)

async def get_more_info_social_networks(user:User,platform:SocialPlatform):
    if platform ==SocialPlatform.TIKTOK:
        if not user.social_credentials or 'tiktok' not in user.social_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tiktok credentials are not available for the user."
            )
        return await get_list_of_tiktok_videos(user)
    elif platform == SocialPlatform.FACEBOOK:
        if not user.social_credentials or 'facebook' not in user.social_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Facebook credentials are not available for the user."
            )
        return await get_pages_of_user(user)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Platform {platform} is not supported for fetching more info."
        )

    
        