import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
CAMB_KEY = os.getenv("CAMB_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
TOGETHER_KEY = os.getenv("TOGETHER_KEY")
GROQ_KEY = os.getenv("GROQ_KEY")
GEMINI_KEY = os.getenv("GEMINI_KEY")

# Media settings
# OUTPUT_DIR = "media"
# os.makedirs(OUTPUT_DIR, exist_ok=True)

TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

#AUTH
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
FACEBOOK_APP_ID =os.getenv("FACEBOOK_APP_ID")
FACEBOOK_APP_SECRET=os.getenv("FACEBOOK_APP_SECRET")
FACEBOOK_REDIRECT_URI=os.getenv("FACEBOOK_REDIRECT_URI","http://localhost:3000")
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
TIKTOK_REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI")
