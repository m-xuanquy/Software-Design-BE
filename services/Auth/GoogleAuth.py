from fastapi import HTTPException,status
from google.auth.transport.requests import Request
from google.auth.transport import requests
from google.auth.exceptions import RefreshError
from config import user_collection
from models import User
from services import get_user_by_email
from .auth_utils import generate_username,generate_password
from config import app_config
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from typing import Dict,Any
import string
import random
from core import hash_password
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from typing import Optional
from bson import ObjectId
GOOGLE_CLIENT_ID = app_config.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = app_config.GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI = app_config.GOOGLE_REDIRECT_URI
GOOGLE_SCOPES =[
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]
collection = user_collection()


async def get_google_oauth_url(mode: str = "login") -> str:
    flow = Flow.from_client_config(
        {
            "web":{
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI],
            }
        },
        scopes=GOOGLE_SCOPES
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    authorization_url,_ =flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=mode
    )
    return authorization_url

async def handle_google_oauth_callback(code:str)->User:
    try:
        flow =Flow.from_client_config(
            {
                "web":{
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [GOOGLE_REDIRECT_URI],
                }
            },
            scopes=GOOGLE_SCOPES
        )
        flow.redirect_uri = GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code)
        credentials = flow.credentials
        idinfo = id_token.verify_oauth2_token(
            credentials.id_token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        user = await process_google_user(idinfo, credentials)
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth callback failed: {str(e)}"
        )
    

async def process_google_user(idinfo:Dict[str,Any],credentials) ->User:
    email = idinfo.get("email")
    name = idinfo.get("name")
    avatar = idinfo.get("picture")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is not provided by Google"
        )
    credentials_data =json.loads(credentials.to_json())
    google_platform_data ={
        "credentials": credentials_data,
    }
    print("Email from Google:", email)
    existing_user = await get_user_by_email(email)
    if existing_user:
        social_credentials = existing_user.social_credentials or {}
        social_credentials['google'] = google_platform_data    
        update_data = {
            "social_credentials": social_credentials,
            "type": "google" 
        }
        
        user_object_id = ObjectId(existing_user.id) if isinstance(existing_user.id, str) else existing_user.id
        
        update_result = await collection.update_one(
            {"_id": user_object_id},
            {"$set": update_data}
        )
        
        existing_user.social_credentials = social_credentials
        return existing_user
    else:
        username = await generate_username(email)
        new_user = {
            "username": username,
            "email": email,
            "fullName": name,
            "avatar": avatar,
            "type": "google",
            "password": hash_password(generate_password()),
            "social_credentials": {
                "google": google_platform_data
            }        }
        result = await collection.insert_one(new_user)
        created_user = await collection.find_one({"_id": result.inserted_id})
        if created_user:
            return User(**created_user)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server error while creating user"
            )
async def check_and_refresh_google_credentials(user:User) -> Credentials:
        if not user.social_credentials or 'google' not in user.social_credentials:
           raise HTTPException(
               status_code=status.HTTP_400_BAD_REQUEST,
               detail="User does not have Google credentials"
           )
        google_credentials=user.social_credentials['google']['credentials']
        credentials =Credentials.from_authorized_user_info(google_credentials)
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                updated_creds =credentials.to_json()
                await collection.update_one(
                    {"_id": user.id},
                    {"$set": {"social_credentials.google.credentials": json.loads(updated_creds)}}
                )
            except RefreshError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Google credentials error: {str(e)}"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Server error: {str(e)}"
                )
        return credentials

async def handle_google_callback(code: str, current_user: Optional[User] = None) -> User:
    flow = Flow.from_client_config(
        {
            "web":{
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI],
            }
        },        scopes=GOOGLE_SCOPES
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    flow.fetch_token(code=code)
    credentials = flow.credentials
    idinfo = id_token.verify_oauth2_token(
        credentials.id_token, requests.Request(), GOOGLE_CLIENT_ID
    )
    email = idinfo.get("email")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email not returned by Google")

    if current_user:        
        # Check if this Google email already exists in the system
        existing_user = await get_user_by_email(email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=400,
                detail="Google account is already linked to another user."
            )
        
        # Check if this Google account is already linked via social_credentials
        existing_google_user = await collection.find_one({
            "social_credentials.google.email": email,
            "_id": {"$ne": ObjectId(current_user.id) if isinstance(current_user.id, str) else current_user.id}
        })
        if existing_google_user:
            raise HTTPException(
                status_code=400,
                detail="Google account is already linked to another user."
            )
        
        credentials_data = json.loads(credentials.to_json())
        social_credentials = current_user.social_credentials or {}
        social_credentials["google"] = {
            "credentials": credentials_data,
            "email": email,
            "avatar": idinfo.get("picture"),
        }
        
        user_id = ObjectId(current_user.id) if isinstance(current_user.id, str) else current_user.id
        
        update_result = await collection.update_one(
            {"_id": user_id},
            {"$set": {"social_credentials": social_credentials}}
        )
        
        current_user.social_credentials = social_credentials
        return current_user
    else:
        existing_user = await get_user_by_email(email)
        if existing_user:
            credentials_data = json.loads(credentials.to_json())
            social_credentials = existing_user.social_credentials or {}
            social_credentials["google"] = {
                "credentials": credentials_data,
                "email": email,
                "avatar": idinfo.get("picture"),
            }
            
            update_data = {
                "social_credentials": social_credentials,
                "type": "google"  # Set type to "google" only for login
            }
            
            user_object_id = ObjectId(existing_user.id) if isinstance(existing_user.id, str) else existing_user.id
            
            await collection.update_one(
                {"_id": user_object_id},
                {"$set": update_data}
            )
            existing_user.social_credentials = social_credentials
            return existing_user
        else:
            username = await generate_username(email)
            new_user = {
                "username": username,
                "email": email,
                "fullName": idinfo.get("name"),
                "avatar": idinfo.get("picture"),
                "type": "google", 
                "password": hash_password(generate_password()),
                "social_credentials": {
                    "google": {
                        "credentials": json.loads(credentials.to_json()),
                        "email": email,
                        "avatar": idinfo.get("picture"),
                    }
                }
            }
            result = await collection.insert_one(new_user)
            created_user = await collection.find_one({"_id": result.inserted_id})
            user = User(**created_user)
            return user