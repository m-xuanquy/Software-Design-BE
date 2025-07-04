from config import user_collection, app_config
import secrets
import httpx
import hashlib
from typing import Dict,Any
import requests
import json
from fastapi import HTTPException,status
from models import User
from services import get_user_by_tiktok_open_id,generate_username,generate_password,hash_password
from datetime import datetime
from urllib.parse import urlencode,quote
TIKTOK_CLIENT_KEY = app_config.TIKTOK_CLIENT_KEY
TIKTOK_CLIENT_SECRET = app_config.TIKTOK_CLIENT_SECRET
TIKTOK_REDIRECT_URI = app_config.TIKTOK_REDIRECT_URI
TIKTOK_SCOPES = [
    "user.info.basic",
    "video.list",
    "video.upload",
    "video.publish",
]
collection = user_collection()
_code_verifiers = {}

def generate_code_verifier() -> str:
    # TikTok Desktop yêu cầu các ký tự unreserved [A-Z], [a-z], [0-9], "-", ".", "_", "~"
    allowed_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    return ''.join(secrets.choice(allowed_chars) for _ in range(64))  # độ dài 64-128

def generate_code_challenge(verifier: str) -> str:
    # Desktop PKCE: SHA256 → hex string
    return hashlib.sha256(verifier.encode('ascii')).hexdigest()

def get_tiktok_auth_url():
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    state = f"tiktok_auth_{secrets.token_urlsafe(16)}"
    _code_verifiers[state] = code_verifier
    base_url = "https://www.tiktok.com/v2/auth/authorize/"
    params = {
        "client_key": TIKTOK_CLIENT_KEY,
        "scope": ",".join(TIKTOK_SCOPES),
        "response_type": "code",
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    
    url = f"{base_url}?{urlencode(params)}"
    return url
async def handle_tiktok_oauth_callback(code: str,state:str =None) -> User:
    try:
        token_url ="https://open.tiktokapis.com/v2/oauth/token/"
        token_data = {
            "client_key": TIKTOK_CLIENT_KEY,
            "client_secret": TIKTOK_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": TIKTOK_REDIRECT_URI,
        }
        code_verifier =None
        if state and state in _code_verifiers:
            code_verifier = _code_verifiers.pop(state)
        if code_verifier:
            token_data["code_verifier"] = code_verifier
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(token_url, data=token_data,headers=headers)
        result = response.json()
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to fetch TikTok access token"
            )
        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        expires_in = result.get("expires_in")

        user_info = await get_tiktok_user_info(access_token)
        user = await process_tiktok_user(user_info, access_token, refresh_token, expires_in)
        return user

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"TikTok OAuth callback failed: {str(e)}"
        )


async def get_tiktok_user_info(access_token: str) -> Dict[str, Any]:
    url = "https://open.tiktokapis.com/v2/user/info/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    params = {
        "fields": "open_id,display_name,avatar_url"
    }

    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch TikTok user info: {response.text}"
        )

    data = response.json()
    return data.get("data", {}).get("user", {})

async def process_tiktok_user(user_data: Dict[str, Any], access_token: str,refresh_token:str,expires_int:int) -> User:
    display_name = user_data.get("display_name")
    avatar_url = user_data.get("avatar_url")
    open_id = user_data.get("open_id")
    if not open_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Open ID is not provided by TikTok"
        )
    tiktok_platform_data={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_int,
        "token_created_at": datetime.now().timestamp(),
        "open_id": open_id,
    }
    existing_user = await get_user_by_tiktok_open_id(open_id)
    if existing_user:
        social_credentials = existing_user.social_credentials or {}
        social_credentials['tiktok'] = tiktok_platform_data
        await collection.update_one(
            {"_id": existing_user.id},
            {"$set": {"social_credentials": social_credentials}}
        )
        existing_user.social_credentials = social_credentials
        return existing_user
    else:
        unique_username = await generate_username(display_name or f"tiktok_user_{open_id[:4]}")
        password = generate_password()
        new_user ={
            "username": unique_username,
            "fullName": display_name or f"TikTok User {open_id[:4]}",
            "avatar": avatar_url,
            "password": hash_password(password),
            "social_credentials": {
                "tiktok": tiktok_platform_data
            }
        }
        result = await collection.insert_one(new_user)
        created_user = await collection.find_one({"_id": result.inserted_id})
        if created_user:
            return User(**created_user)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server error while creating user"
            )
        
async def check_and_refresh_tiktok_credentials(user:User)->str:
    if not user.social_credentials or 'tiktok' not in user.social_credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have TikTok credentials"
        )
    tiktok_credentials = user.social_credentials['tiktok']
    access_token = tiktok_credentials.get("access_token")
    refresh_token = tiktok_credentials.get("refresh_token")
    expires_in = tiktok_credentials.get("expires_in")
    token_created_at = tiktok_credentials.get("token_created_at")
    if not access_token or not refresh_token or not expires_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TikTok credentials are incomplete"
        )

    if expires_in and token_created_at:
        expiry_time = token_created_at + expires_in
        current_time = datetime.now().timestamp()
        token_expired = current_time >= expiry_time
        if token_expired:
            try:
                new_tokens = await refresh_tiktok_token(refresh_token)
                new_access_token = new_tokens.get("access_token")
                new_refresh_token = new_tokens.get("refresh_token")
                new_expires_in = new_tokens.get("expires_in")
                if not new_access_token or not new_refresh_token or not new_expires_in:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to refresh TikTok token"
                    )
                update_tiktok_credentials={
                    **tiktok_credentials,
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                    "expires_in": new_expires_in,
                    "token_created_at": datetime.now().timestamp()
                }
                social_credentials = user.social_credentials.copy()
                social_credentials['tiktok'] = update_tiktok_credentials
                await collection.update_one(
                    {"_id": user.id},
                    {"$set": {"social_credentials": social_credentials}}
                )
                return new_access_token
            except Exception as e:  
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to refresh TikTok token: {str(e)}"
                )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TikTok token expiration time is not set"
        )

    
    return access_token

async def refresh_tiktok_token(refresh_token: str) -> Dict[str, Any]:
    try:
        url = "https://open.tiktokapis.com/v2/oauth/token/"
        data = {
        "client_key": TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
        }
        headers = {
        "Content-Type": "application/x-www-form-urlencoded"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, headers=headers)
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to refresh TikTok token: {response.text}"
            )
        result = response.json()
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to refresh TikTok token: {result.get('error_description', 'Unknown error')}"
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to refresh TikTok token: {str(e)}"
        )