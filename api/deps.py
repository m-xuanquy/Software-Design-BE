from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException, status, Request
from services import get_user_by_username
from models import User
from core import verify_token
from jose import JWTError
from typing import Optional
security = HTTPBearer()

async def get_current_user(credentials:HTTPAuthorizationCredentials =Depends(security))->User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = verify_token(credentials.credentials,"access")
        if payload is None:
            print("Token verification returned None")
            raise credentials_exception
        username = payload.get("sub")
        if username is None:
            print("No username in token")
            raise credentials_exception
    except JWTError as e:
        print(f"JWT Error: {e}")
        raise credentials_exception
    except Exception as e:
        print(f"Other error in token verification: {e}")
        raise credentials_exception
    user = await get_user_by_username(username)
    if user is None:
        print("User not found in database")
        raise credentials_exception
    return user

async def get_current_user_optional(request: Request) -> Optional[User]:
    try:
        # Lấy token từ Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ")[1]
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(credentials)
        return user
    except Exception:
        return None