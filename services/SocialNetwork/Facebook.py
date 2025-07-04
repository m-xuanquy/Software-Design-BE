from schemas import VideoUpLoadRequest,FacebookVideoStatsResponse
from models import User,SocialVideoCreate
from services import check_facebook_credentials, get_media_by_id
from .SocialUtils import add_social_video
from fastapi import HTTPException, status
from config import user_collection
from schemas import SocialPlatform
import requests
from typing import Any
from bson import ObjectId
collection = user_collection()
async def upload_video_to_facebook(user: User,page_id:str, upload_request: VideoUpLoadRequest) -> str:
    try:
        access_token =await check_facebook_credentials(user)
        if not user.social_credentials or 'facebook' not in user.social_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not have Facebook credentials"
            )
        page = await get_page_by_pageid(user, page_id)
        if not page:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Page not found"
            )
        page_access_token = page.get('access_token')
        if not page_access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page access token not found"
            )
        # Get media from media_id
        media = await get_media_by_id(upload_request.media_id)
        if not media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media not found"
            )
        media_url = media.get('url') or media.get('cloudinary_url')
        if not media_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to get media URL"
            )

        upload_url=f"https://graph.facebook.com/v23.0/{page_id}/videos"
        upload_data ={
            "title": upload_request.title,
            "description": upload_request.description,
            "file_url": media_url,
            "access_token": page_access_token,
            "privacy": "{\"value\":\"EVERYONE\"}"  # Always public
        }
        # Remove commented privacy mapping code since we always use public
        if upload_request.tags:
            upload_data["tags"] = ",".join(upload_request.tags)
        
        response = requests.post(upload_url, data=upload_data)
        result = response.json()
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error uploading video to Facebook: {result['error']['message']}"
            )
        video_id = result.get("id")
        if not video_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Video upload failed, no video ID returned"
            )
        social_video_data = SocialVideoCreate(
            user_id=str(user.id),
            platform=SocialPlatform.FACEBOOK,
            video_url=f"https://www.facebook.com/{video_id}"
        )
        await add_social_video(social_video_data)
        return f"https://www.facebook.com/{video_id}"
    except HTTPException as e:
        raise  HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload video to Facebook: {e.detail}"
        )
async def get_page_by_pageid(user:User,page_id:str):
    for page in user.social_credentials.get('facebook', {}).get('pages', []):
        if page.get('id') == page_id:
            return page
        
async def get_facebook_video_stats(user: User, video_id: str,page_id:str=None) -> FacebookVideoStatsResponse:
    try:
        access_token = await check_facebook_credentials(user)
        
        video_info = await get_video_basic_info(video_id, access_token)
        
        facebook_pages = user.social_credentials.get('facebook', {}).get('pages', [])
        page = None
        page_access_token = None
        
        for user_page in facebook_pages:
            page_id = user_page.get('id')
            post_id_from_video_id = video_info.get("post_id")
            if post_id_from_video_id:
                test_post_id = f"{page_id}_{post_id_from_video_id}"
                try:
                    temp_page_token = user_page.get('access_token')
                    if temp_page_token:
                        test_url = f"https://graph.facebook.com/v23.0/{test_post_id}"
                        response = requests.get(test_url, params={'access_token': temp_page_token})
                        if response.status_code == 200:
                            page = user_page
                            page_access_token = temp_page_token
                            post_id = test_post_id
                            break
                except:
                    continue
        
        if not page:
            if facebook_pages:
                page = facebook_pages[0]
                page_access_token = page.get('access_token')
                post_id_from_video_id = video_info.get("post_id")
                post_id = f"{page['id']}_{post_id_from_video_id}" if post_id_from_video_id else None
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No Facebook pages found for user"
                )
        
        if not page_access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page access token not found"
            )
        reactions = await get_video_creations(post_id, page_access_token)
        comments = await get_video_comments(video_id, page_access_token)
        shares = await get_video_shares(post_id, page_access_token)
        return FacebookVideoStatsResponse(
            platform=SocialPlatform.FACEBOOK,
            title=video_info.get("title", ""),
            description=video_info.get("description", ""),
            platform_url=video_info.get("permalink_url",f"https://www.facebook.com/{video_id}"),
            created_at=video_info.get("created_at"),
            view_count=video_info.get("views", 0),
            reaction_count=reactions,
            share_count=shares,
            comment_count= comments
        )
    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch video stats from Facebook: {e.detail}"
        )


async def get_video_basic_info(video_id: str, access_token: str) -> dict:
    try:
        url = f"https://graph.facebook.com/v23.0/{video_id}"
        params = {
            "access_token": access_token,
            "fields": "title,description,created_time,privacy,permalink_url,post_id,views"
        }
        response = requests.get(url, params=params)
        data = response.json()
        if "error" in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error fetching video info: {data['error']['message']}"
            )
        return {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "created_at": data.get("created_time"),
            "platform_url": data.get("permalink_url", ""),
            "post_id": data.get("post_id", ""),
            "views": data.get("views", 0)
        }
    except Exception as e:
        return{}

async def get_video_creations(post_id: str, access_token: str) -> dict:
        reactions=["LIKE", "LOVE", "WOW", "HAHA", "SAD", "ANGRY"]
        reactions_count ={}
        url = f"https://graph.facebook.com/v23.0/{post_id}/reactions"
        for reaction in reactions:
            try:
                params ={
                    "access_token": access_token,
                    "type": reaction,
                    "summary": "total_count",
                    "limit": 0  
                }
                response = requests.get(url, params=params)
                data = response.json()
                if "summary" in data and "error" not in data:
                    reactions_count[reaction] = data["summary"].get("total_count", 0)
                else:
                    reactions_count[reaction] = 0
            except Exception as e:
                reactions_count[reaction] = 0
        return reactions_count
async def get_video_comments(video_id: str, access_token: str) -> int:
    try:
        comments_url = f"https://graph.facebook.com/v23.0/{video_id}/comments"
        params = {
            "access_token": access_token,
            "summary": "total_count",
            "limit": 0  
        }
        response = requests.get(comments_url, params=params)
        data = response.json()
        if "summary" in data:
            return data["summary"].get("total_count", 0)
        return 0
    except Exception as e:
        return 0
    
async def get_video_shares(post_id: str, access_token: str) -> int:
    try:
        shares_url = f"https://graph.facebook.com/v23.0/{post_id}"
        params = {
            "access_token": access_token,
            "fields": "shares"
        }
        response = requests.get(shares_url, params=params)
        data = response.json()
        if "shares" in data:
            return data["shares"].get("count", 0)
        return 0
    except Exception as e:
        return 0
    
async def get_pages_of_user(user:User)-> dict[str,Any]:
    try:
        user = await collection.find_one({"_id":ObjectId(user.id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        if not user.get('social_credentials') or 'facebook' not in user['social_credentials']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not have Facebook credentials"
            )
        facebook_credentials = user['social_credentials']['facebook']
        if not facebook_credentials.get('pages'):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Facebook pages found for the user"
            )
        pages = [
            {k:v for k,v in page.items() if k!="access_token"}
            for page in facebook_credentials['pages']
        ]
        return {"pages": pages}
    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pages: {e.detail}"
        )
   
