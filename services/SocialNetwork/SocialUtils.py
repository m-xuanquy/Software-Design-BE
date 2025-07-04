from schemas import SocialPlatform
from config import social_collection
from models import Social,SocialVideoCreate
collection = social_collection()
async def add_social_video(social_create: SocialVideoCreate):
    try:
        exitsing_social =await collection.find_one({"user_id": social_create.user_id})
        if not exitsing_social:
            new_social = None
            if social_create.platform == SocialPlatform.FACEBOOK:
                new_social = Social(
                    user_id=social_create.user_id,
                    facebook=[social_create.video_url]
                )
            else:
                new_social = Social(
                    user_id=social_create.user_id,
                    youtube=[social_create.video_url]
                )
            await collection.insert_one(new_social.model_dump(by_alias=True,exclude={"id"}))
        else:
            if social_create.platform == SocialPlatform.FACEBOOK:
                if not exitsing_social.get('facebook'):
                    exitsing_social['facebook'] = []
                exitsing_social['facebook'].append(social_create.video_url)
            else:
                if not exitsing_social.get('youtube'):
                    exitsing_social['youtube'] = []
                exitsing_social['youtube'].append(social_create.video_url)
            await collection.update_one(
                {"_id": exitsing_social["_id"]},
                {"$set": exitsing_social}
            )
    except Exception as e:
        print(f"Error adding social video: {e}")
async def get_social_videos(user_id: str, platform: SocialPlatform) -> dict | None:
    try:
        social = await collection.find_one({"user_id": user_id})
        if not social:
            return None
        if platform == SocialPlatform.FACEBOOK:
            return {
                'facebook': social.get('facebook', []),
            }
        elif platform == SocialPlatform.GOOGLE:
           return {
                'youtube': social.get('youtube', []),
            }
        else:
            return None
    except Exception as e:
        print(f"Error fetching social videos: {e}")
        return None
