from google import genai
from google.genai import types
import wave
from config import GEMINI_KEY, TEMP_DIR
import os
import asyncio
from datetime import datetime
import hashlib

# Cache for deduplication
_audio_cache = {}

# Available voices from Gemini API (based on the image provided)
AVAILABLE_VOICES = [
    "Zephyr", "Puck", "Charon", 
    "Kore", "Fenrir", "Leda", 
    "Orus", "Aoede", "Callirrhoe", 
    "Autonoe", "Enceladus", "Iapetus", 
    "Umbriel", "Algieba", "Despina", 
    "Erinome", "Algenib", "Rasalgethi", 
    "Laomedeia", "Achernar", "Alnilam", 
    "Schedar", "Gacrux", "Pulcherrima", 
    "Achird", "Zubenelgenubi", "Vindematrix", 
    "Sadachbia", "Sadaltager", "Sulafat"
]

# Default fallback voice
DEFAULT_VOICE = "Kore"

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """Helper function to save PCM data as WAV file"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

def generate_speech(text, output_file="speech.wav", voice="Kore"):
    """Generate speech from text using Gemini API"""
    client = genai.Client(api_key=GEMINI_KEY)
    
    # Use Kore as fallback if voice not in available list
    if voice not in AVAILABLE_VOICES:
        print(f"Voice '{voice}' not available. Using {DEFAULT_VOICE} as fallback.")
        voice = DEFAULT_VOICE
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            )
        )
        
        # Extract audio data and save to WAV file
        audio_data = response.candidates[0].content.parts[0].inline_data.data
        wave_file(output_file, audio_data)
        return output_file
        
    except Exception as e:
        # Final fallback to Kore if anything fails
        if voice != DEFAULT_VOICE:
            print(f"Voice '{voice}' failed: {e}. Trying {DEFAULT_VOICE}...")
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash-preview-tts",
                    contents=text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=DEFAULT_VOICE,
                                )
                            )
                        ),
                    )
                )
                
                audio_data = response.candidates[0].content.parts[0].inline_data.data
                wave_file(output_file, audio_data)
                return output_file
            except Exception as fallback_error:
                raise fallback_error
        else:
            raise e

async def generate_speech_async(text: str, voice_id: str = DEFAULT_VOICE, user_id: str = None):
    """
    Generate speech from text using Gemini API (async wrapper)
    Uploads to Cloudinary and returns media info
    
    Args:
        text: Text to convert to speech
        voice_id: Gemini voice to use
        user_id: Optional user ID for Cloudinary upload
        
    Returns:
        Dictionary with audio info
    """
    try:
        # Create unique output file path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(TEMP_DIR, f"speech_{timestamp}.wav")
        
        # Run the synchronous function in a thread
        def sync_generate():
            return generate_speech(text, output_file, voice_id)
        
        # Execute in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        audio_path = await loop.run_in_executor(None, sync_generate)
        
        # Estimate duration (rough calculation: ~150 words per minute)
        word_count = len(text.split())
        estimated_duration = max(5, (word_count / 150) * 60)  # minimum 5 seconds
        
        # Upload to Cloudinary if user_id provided
        if user_id:
            from services.Media.media_utils import upload_media
            upload_result = await upload_media(
                audio_path,
                user_id,
                folder="audio",
                resource_type="video",  # For audio files
                prompt=f"Generated speech: {text[:100]}{'...' if len(text) > 100 else ''}",
                metadata={
                    "voice_id": voice_id,
                    "duration": estimated_duration,
                    "word_count": word_count,
                    "type": "generated_speech"
                }
            )
            
            # Clean up local file after upload
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            return {
                "audio_path": audio_path,  # Keep for backward compatibility
                "audio_url": upload_result["url"],  # Cloudinary URL
                "audio_id": upload_result["id"],  # Database ID
                "duration": estimated_duration,
                "voice_id": voice_id,
                "cloudinary_public_id": upload_result["public_id"]
            }
        else:
            print("No user_id provided, returning local file path only.")
            # Fallback to local file if no user_id
            return {
                "audio_path": audio_path,
                "duration": estimated_duration,
                "voice_id": voice_id
            }
        
    except Exception as e:
        print(f"Error generating speech: {e}")
        return None