from fastapi import APIRouter,HTTPException,Form,Response,Request,Depends,status,File,UploadFile
from fastapi.responses import RedirectResponse
from models import User
from schemas import UserResponse, UserCreate, UserLogin, UserUpdate, ChangePassword, Token
from api.deps import get_current_user, get_current_user_optional
from typing import Optional
from services import create_user,authenticate_user,\
    get_google_oauth_url, get_facebook_oauth_url,get_tiktok_auth_url,\
    handle_facebook_oauth_callback,handle_google_callback,handle_tiktok_oauth_callback
from services.Auth.FacebookAuth import handle_facebook_callback
from services.Auth.User import update_user, change_password
from core import create_access_token,create_refresh_token,verify_token
from config import app_config
from config.cloudinary_config import cloudinary_config
import cloudinary.uploader
import urllib.parse

router = APIRouter(prefix="/user", tags=["Authentication"])
ACCESS_TOKEN_EXPIRE_MINUTES = app_config.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = app_config.REFRESH_TOKEN_EXPIRE_DAYS
FRONTEND_URL = app_config.FRONTEND_URL
@router.post("/register",response_model=UserResponse)
async def register_user(user: UserCreate):
    try:
        new_user = await create_user(user)
        new_user_response = new_user.model_dump(exclude={"password"})
        return UserResponse(
            **new_user_response
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the user: {str(e)}"
        )
@router.post("/login",response_model=Token)
async def login_user(response:Response,user_client: UserLogin):
    try:
        user = await authenticate_user(user_client)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
                
            )
        access_token =create_access_token(data={"sub":user.username,"id":user.id})
        refresh_token =create_refresh_token(data={"sub":user.username,"id":user.id})
        response.set_cookie(
            key= "refresh_token",
            value=refresh_token,
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # days to seconds
            httponly=True,
            samesite="Strict",
            secure=False
        )
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
          )  
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during login: {str(e)}"
        )
@router.get("/google/auth")
async def google_auth():
    try:
        auth_url =await get_google_oauth_url()
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while getting Google OAuth URL: {str(e)}"
        )
@router.get("/google/callback")
async def google_callback(
    code: str,
    response: Response,
    state: str = None,
    request: Request = None
):
    is_linking = False 
    try:
        import urllib.parse
        current_user = None
        
        if state and "access_token=" in state:
            state_decoded = urllib.parse.unquote(state)
            params = dict(x.split("=") for x in state_decoded.split("&") if "=" in x)
            access_token = params.get("access_token")
            is_linking = True
            
            if access_token:
                from core import verify_token
                from services import get_user_by_id
                try:
                    payload = verify_token(access_token, token_type="access")
                    user_id = payload.get("id")
                    current_user = await get_user_by_id(user_id)
                except Exception as e:
                    current_user = None
        
        user = await handle_google_callback(code, current_user)
        
        access_token = create_access_token(data={"sub": user.username, "id": user.id})
        refresh_token = create_refresh_token(data={"sub": user.username, "id": user.id})
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            httponly=True,
            samesite="Lax",
            secure=False
        )        
        if is_linking:
            frontend_url = f"{FRONTEND_URL}/auth/profile?linked=google"
        else:
            frontend_url = f"{FRONTEND_URL}#access_token={access_token}"
        return RedirectResponse(url=frontend_url)
    except HTTPException as e:
        if is_linking:
            
            error_message = urllib.parse.quote(e.detail)
            frontend_url = f"{FRONTEND_URL}/auth/profile?link_error={error_message}"
            return RedirectResponse(url=frontend_url)
        else:
            raise e
    except Exception as e:
        if is_linking:
            frontend_url = f"{FRONTEND_URL}/auth/profile?link_error=An error occurred while linking your Google account"
            return RedirectResponse(url=frontend_url)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred while processing Google callback: {str(e)}"
            )
@router.get("/facebook/auth")
async def facebook_auth():
    try:
        auth_url = await get_facebook_oauth_url()
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while getting Facebook OAuth URL: {str(e)}"
        )

@router.get("/facebook/link/auth")
async def facebook_link_auth(current_user: User = Depends(get_current_user)):
    try:
        access_token = create_access_token(data={"sub": current_user.username, "id": current_user.id})
        base_url = "https://www.facebook.com/v23.0/dialog/oauth"
        import urllib.parse
        state_value = urllib.parse.quote(f"link&access_token={access_token}")
        
        params = {
            "client_id": app_config.FACEBOOK_APP_ID,
            "redirect_uri": app_config.FACEBOOK_REDIRECT_URI,
            "scope": "email,public_profile,pages_manage_posts,pages_read_engagement,publish_video,pages_show_list",
            "response_type": "code",
            "state": state_value
        }
        auth_url = f"{base_url}?" + "&".join([f"{key}={value}" for key, value in params.items()])
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while getting Facebook link URL: {str(e)}"
        )

@router.get("/facebook/callback")
async def facebook_callback(
    code: str,
    response: Response,
    state: str = None,
    request: Request = None
):
    is_linking = False 
    try:
        import urllib.parse
        current_user = None
        
        if state and "access_token=" in state:
            state_decoded = urllib.parse.unquote(state)
            params = dict(x.split("=") for x in state_decoded.split("&") if "=" in x)
            access_token = params.get("access_token")
            is_linking = True
            
            if access_token:
                from core import verify_token
                from services import get_user_by_id
                try:
                    payload = verify_token(access_token, token_type="access")
                    user_id = payload.get("id")
                    current_user = await get_user_by_id(user_id)
                except Exception as e:
                    current_user = None
        elif state == "link":
            is_linking = True
            authorization = request.headers.get("Authorization")
            if authorization and authorization.startswith("Bearer "):
                access_token = authorization.split(" ")[1]
                from core import verify_token
                from services import get_user_by_id
                try:
                    payload = verify_token(access_token, token_type="access")
                    user_id = payload.get("id")
                    current_user = await get_user_by_id(user_id)
                except Exception as e:
                    current_user = None
            else:
                refresh_token = request.cookies.get("refresh_token")
                if refresh_token:
                    from core import verify_token
                    from services import get_user_by_id
                    try:
                        payload = verify_token(refresh_token, token_type="refresh")
                        user_id = payload.get("id")
                        current_user = await get_user_by_id(user_id)
                    except Exception as e:
                        current_user = None
        
        user = await handle_facebook_callback(code, current_user)
        
        access_token = create_access_token(data={"sub": user.username, "id": user.id})
        refresh_token = create_refresh_token(data={"sub": user.username, "id": user.id})
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            httponly=True,
            samesite="Lax",
            secure=False
        )        
        if is_linking:
            frontend_url = f"{FRONTEND_URL}/auth/profile?linked=facebook"
        else:
            frontend_url = f"{FRONTEND_URL}#access_token={access_token}"
        return RedirectResponse(url=frontend_url)
    except HTTPException as e:
        if is_linking:
            import urllib.parse
            error_message = urllib.parse.quote(e.detail)
            frontend_url = f"{FRONTEND_URL}/auth/profile?link_error={error_message}"
            return RedirectResponse(url=frontend_url)
        else:
            raise e
    except Exception as e:
        if is_linking:
            frontend_url = f"{FRONTEND_URL}/auth/profile?link_error=An error occurred while linking your Facebook account"
            return RedirectResponse(url=frontend_url)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred while processing Facebook callback: {str(e)}"
            )
@router.get("/tiktok/auth")
async def tiktok_auth():
    auth_url = get_tiktok_auth_url()
    return {"auth_url": auth_url}
@router.get("/tiktok/callback")
async def tiktok_callback(code: str, response: Response,state:str =None):
    try:
        print("State:", state)
        user = await handle_tiktok_oauth_callback(code, state)
        access_token = create_access_token(data={"sub": user.username, "id": user.id})
        refresh_token = create_refresh_token(data={"sub": user.username, "id": user.id})
        response.set_cookie(
            key= "refresh_token",
            value=refresh_token,
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # days to seconds
            httponly=True,
            samesite="Strict",
            secure=False
        )
        frontend_url = f"{FRONTEND_URL}#access_token={access_token}"
        return RedirectResponse(
            url=frontend_url
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing TikTok callback: {str(e)}"
        )
@router.post("/logout")
async def logout_user(response: Response):
    try:
        response.delete_cookie(
            key="refresh_token",
            httponly=True,
            samesite="Strict",
            secure=False
        )
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while logging out: {str(e)}"
        )
    
@router.post("/refresh", response_model=Token)
async def refresh_token(request:Request):
    try:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found"
            )
        payload = verify_token(refresh_token, token_type="refresh")
        user_id = payload.get("id")
        username = payload.get("sub")
        if not user_id or not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        new_access_token = create_access_token(data={"sub": username, "id": user_id})
        return Token(
           access_token=new_access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while logging out: {str(e)}"
        )
@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(**current_user.model_dump(exclude={"password"}))

@router.put("/update", response_model=UserResponse)
async def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user)):
    updated_user = await update_user(current_user.id, user_update)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.post("/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        result = cloudinary.uploader.upload(
            file.file,
            folder="avatars",
            public_id=f"user_{current_user.id}",
            overwrite=True,
            resource_type="image"
        )
        return {"url": result["secure_url"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
@router.post("/change-password")
async def change_password_endpoint(
    req: ChangePassword,    current_user: User = Depends(get_current_user)
):
    await change_password(current_user.id, req.current_password, req.new_password)
    return {"message": "Password changed successfully"}

@router.get("/google/link/auth")
async def google_link_auth(current_user: User = Depends(get_current_user)):
    try:
        auth_url = await get_google_oauth_url("link")
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))