from fastapi import APIRouter, File, UploadFile, Form, HTTPException,BackgroundTasks
from fastapi.responses import FileResponse
import os
from uuid import uuid4
from typing import Optional
import tempfile
# from config import OUTPUT_DIR
from config import TEMP_DIR
from services import generate_text, generate_speech, generate_image, transcribe_audio, convert_to_srt, create_video, add_subtitles, upload_media,cleanup_temp_file, cleanup_temp_files
from typing import Literal
import json 
import re
from starlette.background import BackgroundTasks

router = APIRouter(prefix="/media", tags=["Media Generation"])

@router.post("/generate-text")
async def generate_text_endpoint(model: Literal["deepseek", "gemini"] = Form(...), prompt: str = Form(...)):
    """Generate text from a prompt"""
    try: 
        generated_text = generate_text(model, prompt)

        # Dùng regex để trích nội dung JSON từ giữa các dấu ```
        json_text = re.search(r"```(?:json)?\s*(\{.*?\})\s*```",  generated_text, re.DOTALL)
        if json_text:
            parsed_data = json.loads(json_text.group(1))
        else:
            raise ValueError("Không tìm thấy JSON hợp lệ trong response.")   
             
        return {"text": parsed_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text generation error: {str(e)}")

@router.post("/tts")
async def text_to_speech( background_tasks: BackgroundTasks,text: str = Form(...), voice: str = Form("Kore")):
    """Convert text to speech"""
    output_file = os.path.join(TEMP_DIR, f"{uuid4()}.wav")
    try:
        result_file = generate_speech(text, output_file, voice)
        background_tasks.add_task(cleanup_temp_file, output_file)
        return FileResponse(result_file, media_type="audio/wav", filename="speech.wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")

@router.post("/generate-image")
async def generate_image_endpoint(background_tasks: BackgroundTasks,
                                  model: Literal["flux", "gemini"] = Form(...),
                                  prompt: str = Form(...),
                                  style:Literal["ghibli","watercolor","manga",                            
                                                "pixar","scifi","oilpainting",
                                                "dark","lego","realistic",
                                                "cartoon","vintage","minimalist",
                                                "fantasy","popart","impressionist"]=Form(None)):
                                                                        
    """Generate image from text prompt"""
    output_file = os.path.join(TEMP_DIR, f"{uuid4()}.png")
    try:
        result_file = generate_image(model, prompt,style, output_file)
        background_tasks.add_task(cleanup_temp_file, output_file)
        return FileResponse(result_file, media_type="image/png", filename="image.png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation error: {str(e)}")
    

@router.post("/transcribe")
async def transcribe_audio_endpoint(file: UploadFile = File(...), script: Optional[str] = Form(""), create_srt: bool = Form(False)):
    """Transcribe audio to SRT format"""
    # Save uploaded file temporarily
    temp_file = os.path.join(TEMP_DIR, f"{uuid4()}.wav")
    with open(temp_file, "wb") as f:
        f.write(await file.read())
    
    try:
        if create_srt:
            srt_file = os.path.join(TEMP_DIR, f"{uuid4()}.srt")
            transcription = transcribe_audio(audio_file = temp_file, output_srt = srt_file, script=script)
            return FileResponse(srt_file, media_type="text/plain", filename="transcription.srt")
            
        else:
            transcription = transcribe_audio(aduio_file = temp_file, script=script)

            return {"srt": transcription}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)

@router.post("/create-video")
async def create_video_endpoint(
    image: UploadFile = File(...),
    audio: UploadFile = File(...),
    script: Optional[str] = Form(""),
    background_tasks: BackgroundTasks = None,
):
    """Create video from image and audio"""
    # Create temp files with specific file extensions
    temp_image = os.path.join(TEMP_DIR, f"{uuid4()}.png")
    temp_audio = os.path.join(TEMP_DIR, f"{uuid4()}.wav")
    temp_files = [temp_image, temp_audio]
    
    try:
        # Save uploaded files
        with open(temp_image, "wb") as f:
            f.write(await image.read())
        with open(temp_audio, "wb") as f:
            f.write(await audio.read())
        
        # Create SRT file
        srt_file = os.path.join(TEMP_DIR, f"{uuid4()}.srt")
        temp_files.append(srt_file)
        transcription = transcribe_audio(temp_audio, srt_file, script)

        # Create video
        output_video = os.path.join(TEMP_DIR, f"{uuid4()}.mp4")
        temp_files.append(output_video)
        result_file = create_video(temp_image, temp_audio, srt_file, output_video)
        
        if result_file is None:
            raise HTTPException(status_code=500, detail="Failed to create video")
        
        # Add background task to clean up temporary files after response is sent
        background_tasks.add_task(cleanup_temp_files, temp_files)
        
        return FileResponse(result_file, media_type="video/mp4", filename="output.mp4")
    except Exception as e:
        # Clean up any temporary files in case of error
        cleanup_temp_files(temp_files)
        raise HTTPException(status_code=500, detail=f"Video creation error: {str(e)}")
