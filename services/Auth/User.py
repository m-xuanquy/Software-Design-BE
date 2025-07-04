from fastapi import HTTPException,status
from models import User
from schemas import UserCreate,UserLogin, UserUpdate, ChangePassword
from config import user_collection
from core import hash_password,verify_password
from bson import ObjectId
collection = user_collection()
async def get_user_by_username(username: str)-> User | None:
    try:
        user = await collection.find_one({"username": username})
        if user:
            return User(**user)
        return None
    except Exception as e:
        print("Error fetching user by username")
        return None

async def get_user_by_id(user_id: str) -> User | None:
    try:
        user = await collection.find_one({"_id": ObjectId(user_id)})
        if user:
            return User(**user)
        return None
    except Exception as e:
        print("Error fetching user by id")
        return None

async def get_user_by_email(email: str)-> User | None:
    try:
        user = await collection.find_one({"email": email})
        if user:
            try:
                user_obj = User(**user)
                return user_obj
            except Exception as e:
                return None
        return None
    except Exception as e:
        print("Error fetching user by email",e)
        return None
async def create_user(user:UserCreate) ->User:
    exitsting_user = await get_user_by_username(user.username)
    if exitsting_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    if user.email:
        exitsting_email = await get_user_by_email(user.email)
        if exitsting_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    hashed_password = hash_password(user.password)
    new_user = user.model_dump()
    new_user["password"] = hashed_password
    new_user["type"] = "regular"  # Set type to "regular" for username/password registration
    try:
        result = await collection.insert_one(new_user)
        created_user = await collection.find_one({"_id": result.inserted_id})
        if created_user:
            return  User(**created_user)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server error while creating user"
            )
    except Exception as e:
        print("Error creating user:", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server error while creating user"
        )

async def authenticate_user(user:UserLogin) ->User|None:
    try:
        userDB = await get_user_by_username(user.username) or await get_user_by_email(user.username)
        if not userDB:
            return None
        if not verify_password(user.password,userDB.password):
            return None
        
        if not userDB.model_dump().get("type"):
            user_dict = await collection.find_one({"_id": ObjectId(userDB.id)})
            has_social = user_dict.get("social_credentials", {})
            # Only set to "regular" if no social credentials exist
            if not has_social.get("google") and not has_social.get("facebook"):
                await collection.update_one(
                    {"_id": ObjectId(userDB.id)},
                    {"$set": {"type": "regular"}}
                )
                # Refresh user object
                userDB = await get_user_by_id(userDB.id)
        
        return userDB
    except Exception as e:
      return None

async def update_user(user_id: str, user_update: UserUpdate):
    update_data = {k: v for k, v in user_update.model_dump().items() if v is not None}
    if not update_data:
        return None
    if not isinstance(user_id, ObjectId):
        try:
            user_id = ObjectId(user_id)
        except Exception:
            return None
    result = await collection.find_one_and_update(
        {"_id": user_id},
        {"$set": update_data},
        return_document=True
    )
    if result:
        return User(**result)
    return None

async def change_password(user_id: str, current_password: str, new_password: str):
    if not isinstance(user_id, ObjectId):
        try:
            user_id = ObjectId(user_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user ID")
    user = await collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_type = user.get("type", "regular") 
    if user_type != "regular":
        raise HTTPException(status_code=400, detail="Cannot change password for social media accounts. Please use your social media account to sign in.")
    
    if not verify_password(current_password, user["password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    new_hashed = hash_password(new_password)
    await collection.update_one({"_id": user_id}, {"$set": {"password": new_hashed}})
    return True

async def get_user_by_tiktok_open_id(open_id: str) -> User | None:
    user =await collection.find_one({"social_credentials.tiktok.open_id": open_id})
    if user:
            return User(**user)
    return None