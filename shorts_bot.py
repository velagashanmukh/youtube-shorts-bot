import os
import asyncio
import json
import feedparser
import requests
import datetime
import random
import numpy as np
import edge_tts
import urllib.parse
from google import genai
from google.genai import types
from openai import OpenAI

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

from moviepy import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip, CompositeAudioClip, ImageClip
)
from moviepy.video.fx import Resize
from moviepy.audio.AudioClip import AudioClip

# ─── CONFIGURATION ───────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")

# ─── SFX LIBRARY (CC0 / Public Domain) ───────────────────────────────────────
SFX_URLS = {
    "boom": "https://tryelements.dev/sfx/boom.mp3",
    "whoosh": "https://tryelements.dev/sfx/whoosh.mp3",
    "riser": "https://tryelements.dev/sfx/riser.mp3",
    "ding": "https://tryelements.dev/sfx/notification.mp3",
    "success": "https://tryelements.dev/sfx/success.mp3",
    "click": "https://tryelements.dev/sfx/click.mp3",
    "pop": "https://tryelements.dev/sfx/pop.mp3",
}

MONEY_WORDS = {"money", "dollar", "dollars", "profit", "wealth", "rich", "cash", "price", "revenue", "billion", "million", "rupee", "rupees", "invest"}
THREAT_WORDS = {"threat", "danger", "risk", "warning", "crash", "collapse", "crisis", "scam", "hide", "hidden", "secret", "lost", "lose"}
REVEAL_WORDS = {"secret", "truth", "now", "reveal", "discover", "find", "learn", "watch"}

# ─── 1. TREND ENGINE ─────────────────────────────────────────────────────────
def fetch_live_trending_topic():
    print("🌍 Fetching live world trends...")
    day_of_week = datetime.datetime.now().weekday()
    if day_of_week in [0, 1]:
        niche, rss_url = "Technology", "https://news.google.com/rss/search?q=Artificial+Intelligence+OR+Technology+when:24h"
    elif day_of_week in [2, 3]:
        niche, rss_url = "Business", "https://news.google.com/rss/search?q=Business+OR+Startups+when:24h"
    else:
        niche, rss_url = "Finance", "https://news.google.com/rss/search?q=Finance+OR+Crypto+OR+Wealth+when:24h"
    
    time_label = f"{niche} Day"
    try:
        res = requests.get(rss_url, timeout=10)
        feed = feedparser.parse(res.content)
        title = feed.entries[0].title
        print(f"🔥 [{time_label}] Live Trend: {title}")
        return title, time_label
    except Exception as e:
        print(f"⚠️ Trend fetch fallback: {e}")
        return f"The Latest Major Breakthrough in {niche}", time_label

# ─── 2. SCRIPT GENERATION (Groq + Gemini Fallback) ───────────────────────────
def generate_storyboard(headline, label):
    print("🧠 Directing script...")
    
    prompt = f"""You are an elite YouTube Shorts retention psychologist.
Topic: [{headline}] ({label})
Create an 18-to-20-second viral script (50-60 words).
Rules:
- Write in VERY SHORT sentences (3-5 words per sentence).
- THE LOOP: Final sentence must flow seamlessly back into the first spoken word.
- HOOK: First 3 words must trigger intense curiosity.
- SCENES: Exactly 3 visual prompts for AI image generation.
Output ONLY raw valid JSON:
{{
  "title": "Clickbaity high-CTR title under 60 chars",
  "description": "Engaging description with #Shorts #Trending",
  "voiceover_script": "Full continuous spoken script text",
  "scenes": ["visual prompt one", "visual prompt two", "visual prompt three"]
}}"""

    # --- Attempt 1: Groq (OpenAI-compatible) ---
    if GROQ_API_KEY:
        try:
            groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
            print("🧠 Trying Groq (llama-3.3-70b)...")
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            data = json.loads(response.choices[0].message.content)
            print(f"✅ Script generated with Groq: {data['title']}")
            return data
        except Exception as e:
            print(f"⚠️ Groq failed: {e}")

    # --- Attempt 2: Gemini Fallback ---
    if GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            fallback_models = ["gemini-2.0-flash", "gemini-1.5-flash"]
            for model_name in fallback_models:
                try:
                    print(f"🧠 Trying {model_name}...")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7)
                    )
                    data = json.loads(response.text)
                    print(f"✅ Script generated with {model_name}: {data['title']}")
                    return data
                except Exception as e:
                    print(f"⚠️ {model_name} failed: {e}")
                    continue
        except Exception as e:
            print(f"⚠️ Gemini fallback failed: {e}")

    # --- Final Fallback ---
    print("❌ All AI providers failed. Using fallback script.")
    return {
        "title": "THE SECRET THEY HIDE",
        "description": "Automated Short #Shorts",
        "voiceover_script": f"Did you know about {headline}? The elite hide this. Watch till the end to find out how this changes everything.",
        "scenes": ["futuristic finance technology", "luxury stock market", "success wealth"]
    }

# ─── 3. VOICEOVER ────────────────────────────────────────────────────────────
async def make_tts(text, output="audio.mp3"):
    print("🎙️ Generating neural voiceover...")
    comm = edge_tts.Communicate(text, "en-US-ChristopherNeural", rate="+10%")
    timings = []
    with open(output, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                dur = chunk["duration"] / 1e7
                timings.append({"word": chunk["text"], "start": start, "end": start + dur})
    print(f"✅ Voiceover saved with {len(timings)} word timings.")
    return output, timings

# ─── 4. FREE AI SCENE GENERATION (Pollinations.ai - No API Key) ──────────────
def generate_ai_image(prompt, index):
    filename = f"scene_{index}.jpg"
    print(f"🎨 Generating AI image for scene {index + 1}: '{prompt}'...")
    
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true"
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200 and len(resp.content) > 5000:
            with open(filename, "wb") as f:
                f.write(resp.content)
            print(f"✅ Scene {index + 1} image generated.")
            return filename
    except Exception as e:
        print(f"⚠️ Image generation failed: {e}")

    from PIL import Image
    img = Image.new('RGB', (1080, 1920), color=(15, 15, 35))
    img.save(filename)
    return filename

# ─── 5. SFX MANAGER ──────────────────────────────────────────────────────────
def download_sfx(name):
    path = f"sfx_{name}.mp3"
    if os.path.exists(path):
        return path
    url = SFX_URLS.get(name)
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(path, "wb") as f:
                f.write(resp.content)
            print(f"✅ SFX downloaded: {name}")
            return path
    except Exception as e:
        print(f"⚠️ SFX '{name}' failed: {e}")
    return None

def build_sfx_timeline(timings, final_duration):
    timeline = []
    timeline.append(("boom", 0.0, 0.9))
    t = 1.5
    while t < final_duration:
        timeline.append(("whoosh", t, 0.35))
        t += 1.5
    if timings:
        for item in timings:
            word = item["word"].lower().strip(".,!?")
            t = item["start"]
            if word in MONEY_WORDS:
                timeline.append(("success", t, 0.6))
            if word in THREAT_WORDS:
                timeline.append(("click", t, 0.4))
            if word in REVEAL_WORDS:
                timeline.append(("ding", t, 0.5))
    if final_duration > 3:
        timeline.append(("riser", max(0, final_duration - 2.5), 0.45))
    timeline.append(("pop", max(0, final_duration - 0.3), 0.7))
    return timeline

# ─── 6. BACKGROUND MUSIC ─────────────────────────────────────────────────────
def download_music():
    print("🎵 Fetching background music...")
    music_url = "https://www.learningcontainer.com/wp-content/uploads/2020/02/Kalimba.mp3"
    try:
        resp = requests.get(music_url, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 10000:
            with open("bg_music.mp3", "wb") as f:
                f.write(resp.content)
            print("✅ Music downloaded.")
            return "bg_music.mp3"
    except Exception as e:
        print(f"⚠️ Music failed: {e}")

    silent = AudioClip(lambda t: 0, duration=30, fps=44100)
    silent.write_audiofile("bg_music.mp3", logger=None)
    print("⚠️ Using silent fallback audio.")
    return "bg_music.mp3"

# ─── 7. RENDER ENGINE ────────────────────────────────────────────────────────
def render_video(clips, audio_file, timings, metadata, output="final_short.mp4"):
    print("🎞️ Rendering video with full audio pulse...")

    video_clips = []
    for c in clips:
        base_clip = ImageClip(c).with_duration(6).resized(height=1920)
        for start in np.arange(0, base_clip.duration, 1.5):
            end = min(start + 1.5, base_clip.duration)
            if end - start < 0.5:
                continue
            segment = base_clip.subclipped(start, end)
            segment = segment.with_effects([Resize(lambda t: min(1.15, 1.0 + t * 0.3))])
            video_clips.append(segment)

    random.shuffle(video_clips)
    merged_video = concatenate_videoclips(video_clips, method="compose")
    voiceover = AudioFileClip(audio_file)
    final_duration = min(voiceover.duration, merged_video.duration)
    final_video = merged_video.subclipped(0, final_duration).with_audio(voiceover)

    caption_clips = []
    if not timings:
        words = metadata["voiceover_script"].split()
        chunk_size = max(1, len(words) // 6)
        time_per_chunk = final_duration / (len(words) / chunk_size)
        for i in range(0, len(words), chunk_size):
            chunk = words[i:i+chunk_size]
            text = " ".join(chunk).upper()
            start_time = (i // chunk_size) * time_per_chunk
            txt_clip = TextClip(
                text=text, font_size=80, color='yellow',
                stroke_color='black', stroke_width=8,
                font='DejaVuSans-Bold', size=(1000, 300), method='caption'
            ).with_position(("center", "center")).with_start(start_time).with_duration(time_per_chunk)
            caption_clips.append(txt_clip)
    else:
        for i in range(0, len(timings), 2):
            chunk = timings[i:i+2] if i + 1 < len(timings) else timings[i:i+1]
            text = " ".join([t["word"] for t in chunk]).upper()
            start_time = chunk[0]["start"]
            duration = chunk[-1]["end"] - start_time
            txt_clip = TextClip(
                text=text, font_size=90, color='yellow',
                stroke_color='black', stroke_width=8,
                font='DejaVuSans-Bold', size=(1000, 300), method='caption'
            ).with_position(("center", "center")).with_start(start_time).with_duration(duration)
            caption_clips.append(txt_clip)

    try:
        music_path = download_music()
        bg_music = AudioFileClip(music_path).with_volume_scaled(0.08).with_duration(final_duration)
        final_video = final_video.with_audio(CompositeAudioClip([final_video.audio, bg_music]))
        print("✅ Background music added.")
    except Exception as e:
        print(f"⚠️ Music mix failed: {e}")

    print("🔊 Building SFX timeline...")
    sfx_timeline = build_sfx_timeline(timings, final_duration)
    sfx_clips = []
    for name, start_time, volume in sfx_timeline:
        path = download_sfx(name)
        if not path:
            continue
        try:
            clip = AudioFileClip(path).with_volume_scaled(volume)
            if start_time + clip.duration > final_duration:
                clip = clip.with_duration(final_duration - start_time)
            sfx_clips.append(clip.with_start(start_time))
        except Exception as e:
            print(f"⚠️ SFX '{name}' mixing failed: {e}")

    if sfx_clips:
        all_audio = CompositeAudioClip([final_video.audio] + sfx_clips)
        final_video = final_video.with_audio(all_audio)
        print(f"✅ {len(sfx_clips)} SFX cues added to the audio pulse.")

    rendered = CompositeVideoClip([final_video] + caption_clips)
    rendered.write_videofile(output, fps=30, codec="libx264", audio_codec="aac", threads=4)
    print(f"✨ Final Short rendered: {output}")
    return output

# ─── 8. YOUTUBE UPLOAD ───────────────────────────────────────────────────────
def publish_short(video_file, meta):
    print("🚀 Uploading to YouTube...")
    creds = Credentials(
        token=None, refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID, client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    yt = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": meta["title"][:100], "description": meta["description"], "categoryId": "28"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True, mimetype="video/mp4")
    res = yt.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    print(f"🎉 SUCCESS! https://www.youtube.com/shorts/{res['id']}")

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    topic, label = fetch_live_trending_topic()
    storyboard = generate_storyboard(topic, label)
    audio_path, timings = asyncio.run(make_tts(storyboard["voiceover_script"]))
    scenes = [generate_ai_image(p, i) for i, p in enumerate(storyboard["scenes"])]
    final_mp4 = render_video(scenes, audio_path, timings, storyboard)
    publish_short(final_mp4, storyboard)

if __name__ == "__main__":
    main()
