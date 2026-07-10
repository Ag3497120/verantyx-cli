import os
import sys
import glob
import json
import subprocess
from datetime import timedelta
import argparse

import torch
import whisper

# For Mac Vision OCR
import Quartz
import Vision
from Cocoa import NSURL

# Import the 27B boot system to generate vectors
from chat_27b import boot_system

def extract_audio(video_path, output_audio_path):
    print(f"[*] Extracting audio from {video_path}...")
    subprocess.run([
        'ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', 
        '-y', output_audio_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_audio_path

def extract_frames(video_path, output_dir, fps=0.2):
    print(f"[*] Extracting frames from {video_path} (1 frame per 5 seconds)...")
    os.makedirs(output_dir, exist_ok=True)
    subprocess.run([
        'ffmpeg', '-i', video_path, '-vf', f'fps={fps}', 
        '-y', f'{output_dir}/frame_%04d.jpg'
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    frames = sorted(glob.glob(f"{output_dir}/frame_*.jpg"))
    return frames

def perform_ocr_mac_vision(image_path):
    """Uses macOS built-in Vision framework for fast, offline, zero-VRAM OCR."""
    url = NSURL.fileURLWithPath_(image_path)
    
    # Initialize request handler
    request_handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    
    # Create text recognition request
    recognized_text = []
    def completion_handler(request, error):
        if error:
            return
        results = request.results()
        if not results:
            return
        for observation in results:
            candidates = observation.topCandidates_(1)
            if candidates:
                recognized_text.append(candidates[0].string())
                
    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(completion_handler)
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    
    # Execute request
    success, error = request_handler.performRequests_error_([request], None)
    return " ".join(recognized_text) if success else ""

def ingest_video(video_path, memory_bank, model, tokenizer, device):
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    temp_dir = f"/tmp/verantyx_clone_{base_name}"
    os.makedirs(temp_dir, exist_ok=True)
    
    audio_path = os.path.join(temp_dir, "audio.m4a")
    extract_audio(video_path, audio_path)
    
    print("[*] Running ultra-fast speech recognition (openai-whisper on CPU)...")
    # Load whisper model natively on CPU to prevent PyTorch MPS sparse tensor crashes
    # Apple Silicon CPU is extremely fast for 'base' or 'turbo'
    whisper_model = whisper.load_model("base", device="cpu")
    audio_result = whisper_model.transcribe(audio_path, fp16=False)
    
    frames = extract_frames(video_path, temp_dir)
    print(f"[*] Extracted {len(frames)} slide frames. Running Vision OCR...")
    
    # To avoid VRAM explosion, process OCR and map it by timestamp
    ocr_texts = {}
    for i, frame in enumerate(frames):
        timestamp = i * 5 # 1 frame every 5 seconds
        text = perform_ocr_mac_vision(frame)
        if text.strip():
            ocr_texts[timestamp] = text
            
    # Combine Audio and Vision by 60-second chunks
    print("[*] Merging sensory inputs into Latent Vectors...")
    chunks = []
    current_chunk = {"text": "", "slides": set()}
    current_minute = 0
    
    for segment in audio_result.get("segments", []):
        start_time = segment["start"]
        minute = int(start_time // 60)
        
        if minute > current_minute:
            # Finalize chunk
            if current_chunk["text"] or current_chunk["slides"]:
                slide_text = " ".join(list(current_chunk["slides"]))
                combined = f"[講義音声]: {current_chunk['text']}\n[スライド視覚情報]: {slide_text}"
                chunks.append(combined)
            current_chunk = {"text": "", "slides": set()}
            current_minute = minute
            
        current_chunk["text"] += segment["text"] + " "
        
        # Add any OCR text that falls into this timeframe
        for ts, slide_t in ocr_texts.items():
            if minute * 60 <= ts < (minute + 1) * 60:
                current_chunk["slides"].add(slide_t)
                
    if current_chunk["text"] or current_chunk["slides"]:
        slide_text = " ".join(list(current_chunk["slides"]))
        combined = f"[講義音声]: {current_chunk['text']}\n[スライド視覚情報]: {slide_text}"
        chunks.append(combined)
        
    print(f"[*] Processing {len(chunks)} contextual chunks through 27B architecture...")
    model.eval()
    with torch.no_grad():
        for i, chunk_text in enumerate(chunks):
            # 1. Tokenize the combined memory
            inputs = tokenizer(chunk_text, return_tensors="pt", truncation=True, max_length=1024).to(device)
            
            # 2. Extract latent vector from residual stream
            outputs = model(**inputs, output_hidden_states=True)
            # Take the last hidden state of the last token as the logic vector
            latent_vector = outputs.hidden_states[-1][0, -1, :] 
            
            # 3. Write directly to Infinite Latent Memory
            memory_bank.write(latent_vector.unsqueeze(0).unsqueeze(0))
            sys.stdout.write(f"\r  -> Vectorized chunk {i+1}/{len(chunks)} into memory")
            sys.stdout.flush()
    print("\n[*] Video ingestion complete!")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, required=True, help="Directory containing class videos")
    parser.add_argument("--out", type=str, default="my_clone.memory", help="Output memory file path")
    args = parser.parse_args()
    
    # 1. Boot the 27B Logic CPU
    print("[*] Initializing Verantyx 27B Logic CPU for Vectorization...")
    model, tokenizer, memory_bank, device = boot_system()
    
    # 2. Scan videos recursively
    search_pattern_mp4 = os.path.join(args.dir, "**", "*.mp4")
    search_pattern_mkv = os.path.join(args.dir, "**", "*.mkv")
    search_pattern_m4a = os.path.join(args.dir, "**", "*.m4a")
    
    video_files = glob.glob(search_pattern_mp4, recursive=True) + \
                  glob.glob(search_pattern_mkv, recursive=True) + \
                  glob.glob(search_pattern_m4a, recursive=True)
                  
    print(f"[*] Found {len(video_files)} videos/audios in {args.dir} and its subdirectories.")
    
    for video in video_files:
        print("-" * 50)
        ingest_video(video, memory_bank, model, tokenizer, device)
        
    # 3. Save the brain state
    memory_bank.save(args.out)
    print(f"\n✅ Clone Memory successfully saved to {args.out}")
    print("You can now boot chat_27b.py with this memory to test your clone.")

if __name__ == "__main__":
    main()
