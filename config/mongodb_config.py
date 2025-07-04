import os
import asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables if not already loaded
load_dotenv()

# MongoDB connection string
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

client = AsyncIOMotorClient(MONGODB_URI)

async def test_connection():
    try:
        await client.admin.command('ping')
        print("Successfully connected to MongoDB")
        return True
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        return False



def get_database():
    """Get MongoDB database instance"""
    return client[DATABASE_NAME]

# Database collections
def media_collection():
    """Get media collection"""
    db = get_database()
    return db["media"]

def user_collection():
    """Get user collection"""
    db = get_database()
    return db["users"]

def trending_topics_collection():
    """Get trending topics collection"""
    db = get_database()
    return db["trending_topics"]

def social_collection():
    """Get social collection"""
    db = get_database()
    return db["socials"]