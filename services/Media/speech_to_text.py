from groq import Groq
import os
from config import GROQ_KEY
from config import GEMINI_KEY
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import base64
from IPython.display import display
import re

def get_prompt(script="NOT_PROVIDED"):
    return f"""
        Generate a transcript of the speech with timestamps in seconds. Given transcript without timestamps: {script}. Group words into subtitle segments (grouping by ~5 words per segment). Follow .srt format.
    """

def transcribe_audio(audio_file, output_srt=None,script="NOT_PROVIDED", language="en"):
    """Transcribe audio to SRT format using Gemini API and optionally create SRT file"""
    client = genai.Client(api_key=GEMINI_KEY)

    myfile = client.files.upload(file=audio_file)
    prompt= get_prompt(script)

    response = client.models.generate_content(
    model='gemini-1.5-flash',
    contents=[prompt, myfile]
    )

    # Dùng regex để trích nội dung JSON từ giữa các dấu ```
    match = re.search(r"```srt\s*(.*?)\s*```", response.text, re.DOTALL)
    if match:
        processed_text = match.group(1).strip()
    else:
        raise ValueError("Không tìm thấy nội dung .srt trong phản hồi.")  

    # If output_srt is provided, create SRT file
    if output_srt and processed_text:
        convert_to_srt(processed_text, output_srt)

    return processed_text

def convert_to_srt(transcription_text, output_file):
    with open(output_file, "w") as f:
        f.write(transcription_text)

    return output_file