from typing import List, Dict, Optional
import os
from services.Media.text_to_speech import generate_speech
from config import TEMP_DIR
from uuid import uuid4

# Voice data mapping from frontend mockdata with real Groq voices
AVAILABLE_VOICES = [
    {
        "id": "v1",
        "name": "Zephyr",
        "gender": "female", 
        "language": "English",
        "accent": "American",
        "tags": ["bright", "higher pitch"],
        "gemini_voice": "Zephyr"  # Male, clear voice
    },
    {
        "id": "v2", 
        "name": "Puck",
        "gender": "male",
        "language": "English", 
        "accent": "British",
        "tags": ["upbeat", "middle pitch"],
        "gemini_voice": "Puck" 
    },
    {
        "id": "v3",
        "name": "Charon", 
        "gender": "male",
        "language": "English",
        "accent": "Australian", 
        "tags": ["informative", "lower pitch"],
        "gemini_voice": "Charon" 
    },
    {
        "id": "v4",
        "name": "Kore",
        "gender": "female",
        "language": "English", 
        "accent": "American",
        "tags": ["firm", "middle pitch"],
        "gemini_voice": "Kore" 
    },
    {
        "id": "v5",
        "name": "Fenrir",
        "gender": "male",
        "language": "English",
        "tags": ["excitable", "lower middle pitch"],
        "gemini_voice": "Fenrir"  
    },
    {
        "id": "v6",
        "name": "Leda",
        "gender": "female",
        "language": "English", 
        "tags": ["youthful", "higher pitch"],
        "gemini_voice": "Leda"  
    },
    {
        "id": "v7",
        "name": "Orus",
        "gender": "male",
        "language": "English",
        "accent": "American",
        "tags": ["Firm", "Lower middle pitch"], 
        "gemini_voice": "Orus"
    },
    {
        "id": "v8",
        "name": "Aoede",
        "gender": "female",
        "language": "English",
        "tags": ["breezy", "middle pitch"],
        "gemini_voice": "Aoede" 
    },
    {
        "id": "v9",
        "name": "Callirrhoe",
        "gender": "female",
        "language": "English",
        "accent": "American",
        "tags": ["easy-going", "middle pitch"],
        "gemini_voice": "Callirrhoe" 
    },
    {
        "id": "v10",
        "name": "Autonoe",
        "gender": "female",
        "language": "English",
        "accent": "American",
        "tags": ["bright", "middle pitch"],
        "gemini_voice": "Autonoe"  
    },
    {
        "id": "v11",
        "name": "Enceladus",
        "gender": "male",
        "language": "English",
        "accent": "American",
        "tags": ["breathy", "lower pitch"],
        "gemini_voice": "Enceladus" 
    },
    {
        "id": "v12",
        "name": "Iapetus",
        "gender": "male",
        "language": "English",
        "accent": "American",
        "tags": ["clear", "lower middle pitch"],
        "gemini_voice": "Iapetus"  # Male, young voice
    }
]

def get_all_voices() -> List[Dict]:
    """Get all available voices"""
    return [
        {
            "id": voice["id"],
            "name": voice["name"], 
            "gender": voice["gender"],
            "language": voice["language"],
            "accent": voice.get("accent"),
            "tags": voice["tags"],
            "preview_url": f"/assets/sounds/voice-preview-{voice['id']}.mp3",
            "available": True
        }
        for voice in AVAILABLE_VOICES
    ]

def get_voice_by_id(voice_id: str) -> Optional[Dict]:
    """Get voice by ID"""
    for voice in AVAILABLE_VOICES:
        if voice["id"] == voice_id:
            return {
                "id": voice["id"],
                "name": voice["name"],
                "gender": voice["gender"], 
                "language": voice["language"],
                "accent": voice.get("accent"),
                "tags": voice["tags"],
                "preview_url": f"/assets/sounds/voice-preview-{voice['id']}.mp3",
                "available": True
            }
    return None

def get_voices_by_language(language: str) -> List[Dict]:
    """Get voices filtered by language"""
    return [
        voice for voice in get_all_voices()
        if voice["language"].lower() == language.lower()
    ]

def get_voices_by_gender(gender: str) -> List[Dict]:
    """Get voices filtered by gender"""
    return [
        voice for voice in get_all_voices()
        if voice["gender"].lower() == gender.lower()
    ]

async def generate_voice_audio(text: str, voice_id: str, speed: float = 1.0, pitch: int = 0, user_id: str = None) -> Dict:
    """
    Generate audio from text using specified voice and settings
    
    Args:
        text: Text to convert to speech
        voice_id: Voice ID to use
        speed: Speaking speed (0.5-2.0) 
        pitch: Voice pitch (-10 to +10)
        user_id: User ID for Cloudinary upload
        
    Returns:
        Dict with audio_url, duration, voice_id, and settings
    """
    try:
        # Find voice configuration
        voice_config = None
        for voice in AVAILABLE_VOICES:
            if voice["id"] == voice_id:
                voice_config = voice
                break
                
        # Fallback to default voice if not found
        if not voice_config:
            print(f"Warning: Voice {voice_id} not found, using default Kore")
            voice_config = {
                "id": voice_id,
                "name": "Default",
                "gemini_voice": "Kore"
            }
        
        # Use Gemini TTS with the mapped voice
        gemini_voice = voice_config["gemini_voice"]
        print(f"Using Gemini voice: {gemini_voice} for voice_id: {voice_id}")
        
        # Generate speech using async version with Cloudinary upload
        from services.Media.text_to_speech import generate_speech_async
        result = await generate_speech_async(text, gemini_voice, user_id)
      
        if not result:
            raise Exception("Failed to generate audio")
        
        # Calculate adjusted duration for speed
        base_duration = result["duration"]
        adjusted_duration = base_duration / speed  # Adjust for speed
        
        # Return result with Cloudinary URL if available, otherwise fallback URL
        audio_url = result.get("audio_url", f"/media/audio/{os.path.basename(result.get('audio_path', 'unknown.wav'))}")
        
        return {
            "audio_url": audio_url,
            "duration": adjusted_duration,
            "voice_id": voice_id,
            "settings": {
                "speed": speed,
                "pitch": pitch
            },
            "audio_id": result.get("audio_id"),  # For database reference
            "cloudinary_public_id": result.get("cloudinary_public_id")  # For Cloudinary reference
        }
        
    except Exception as e:
        raise Exception(f"Voice generation failed: {str(e)}")

def get_voice_languages() -> List[str]:
    """Get list of available languages"""
    languages = set()
    for voice in AVAILABLE_VOICES:
        languages.add(voice["language"])
    return sorted(list(languages))

def get_voice_genders() -> List[str]:
    """Get list of available genders"""
    genders = set()
    for voice in AVAILABLE_VOICES:
        genders.add(voice["gender"])
    return sorted(list(genders))
