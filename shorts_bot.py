import os
import asyncio
import json
import feedparser
import requests
import datetime
import random
import numpy as np
import edge_tts
from urllib.parse import quote_plus
from google import genai
from google.genai import types

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

from moviepy import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip, CompositeAudioClip
)
from moviepy.video.fx import Resize

# ─── CONFIGURATION ───────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")

# ─── 1. TREND ENGINE ─────────────────────────────────────────────────────────
def fetch_live_trending_topic():
    print("🌍 Fetching live world trends...")
    day_of_week = datetime.datetime.now().weekday()

    if day_of_week in [0, 1]:
        niche = "Technology"
        rss_url = "https://news.google.com/rss/search?q=Artificial+Intelligence+OR+Technology+when:24h"
    elif day_of_week in [2, 3]:
        niche = "Business"
        rss_url = "https://news.google.com/rss/search?q=Business+OR+Startups+when:24h"
    else:
        niche = "Finance"
        rss_url = "https://news.google.com/rss/search?q=Finance+OR+Crypto+OR+Wealth+when:24h"

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

# ─── 2. GEMINI SCRIPT ────────────────────────────────────────────────────────
def generate_storyboard(headline, label):
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("🧠 Directing script with Gemini...")
    
    prompt = f"""You are an elite YouTube Shorts retention psychologist.
Topic: [{headline}] ({label})
Create an 18-to-20-second viral script (50-60 words).
Rules:
- Write in VERY SHORT sentences (3-5 words per sentence).
- THE LOOP: Final sentence must flow seamlessly back into the first spoken word.
- HOOK: First 3 words must trigger intense curiosity.
- SCENES: Exactly 3 visual search keywords.
Output ONLY raw valid JSON:
{{
  "title": "Clickbaity high-CTR title under 60 chars",
  "description": "Engaging description with #Shorts #Trending",
  "voiceover_script": "Full continuous spoken script text",
  "scenes": ["keyword one", "keyword two", "keyword three"]
}}"""
    try:
        available = [m.name.replace('models/', '') for m in client.models.list() if 'generateContent' in m.supported_actions]
        flash_models = [m for m in available if 'flash' in m]
        fallback_models = flash_models if flash_models else ["gemini-2.0-flash", "gemini-1.5-flash"]
    except Exception:
        fallback_models = ["gemini-2.0-flash", "gemini-1.5-flash"]

    for model_name in fallback_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7)
            )
            data = json.loads(response.text)
            print(f"✅ Script generated: {data['title']}")
            return data
        except Exception as e:
            print(f"⚠️ {model_name} failed: {e}")
            continue

    return {
        "title": "THE SECRET THEY HIDE",
        "description": "Automated Short #Shorts",
        "voiceover_script": f"Did you know about {headline}? The elite hide this. Watch till the end.",
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

# ─── 4. STOCK VIDEO (Coverr) ─────────────────────────────────────────────────
def generate_clip(query, index):
    filename = f"clip_{index}.mp4"
    print(f"🎬 Fetching video for scene {index + 1}: '{query}'...")
    try:
        res = requests.get("https://api.coverr.co/videos", params={"query": query, "sort": "popularity"}, timeout=10).json()
        if res.get("hits"):
            vid_data = requests.get(res["hits"][0]["urls"]["mp4_download"], timeout=30).content
            with open(filename, "wb") as f:
                f.write(vid_data)
            print(f"✅ Scene {index + 1} downloaded.")
            return filename
    except Exception as e:
        print(f"⚠️ Coverr failed: {e}")

    print("⚠️ Using fallback background.")
    clip = ColorClip(size=(1080, 1920), color=(15, 15, 35), duration=6)
    clip.fps = 30
    clip.write_videofile(filename, codec="libx264", audio=False, logger=None)
    return filename

# ─── 5. MUSIC & SFX (Stable Public URLs) ─────────────────────────────────────
def download_music():
    print("🎵 Fetching background music...")
    music_url = "https://www.bensound.com/bensound-music/bensound-energy.mp3"
    try:
        resp = requests.get(music_url, timeout=15)
        if resp.status_code == 200:
            with open("bg_music.mp3", "wb") as f:
                f.write(resp.content)
            print("✅ Music downloaded.")
            return "bg_music.mp3"
    except Exception as e:
        print(f"⚠️ Music failed: {e}")
    
    from moviepy.audio.AudioClip import AudioClip
    silent = AudioClip(lambda t: 0, duration=30, fps=44100)
    silent.write_audiofile("bg_music.mp3", logger=None)
    return "bg_music.mp3"

def download_whoosh():
    print("🔊 Fetching whoosh SFX...")
    whoosh_url = "https://www.soundjay.com/button/sounds/button-16.mp3"
    try:
        resp = requests.get(whoosh_url, timeout=15)
        if resp.status_code == 200:
            with open("whoosh.mp3", "wb") as f:
                f.write(resp.content)
            print("✅ Whoosh downloaded.")
            return "whoosh.mp3"
    except Exception as e:
        print(f"⚠️ Whoosh failed: {e}")
    return None

# ─── 6. RENDER (Rapid Cuts + Captions + Music + SFX) ─────────────────────────
def render_video(clips, audio_file, timings, metadata, output="final_short.mp4"):
    print("🎞️ Rendering video...")
    video_clips = []
    for c in clips:
        base_clip = VideoFileClip(c).resized(height=1920)
        for start in np.arange(0, base_clip.duration, 1.5):
            end = min(start + 1.5, base_clip.duration)
            if end - start < 0.5: continue
            segment = base_clip.subclipped(start, end)
            segment = segment.with_effects([Resize(lambda t: min(1.15, 1.0 + t * 0.3))])
            video_clips.append(segment)
    
    random.shuffle(video_clips)
    merged_video = concatenate_videoclips(video_clips, method="compose")
    audio = AudioFileClip(audio_file)
    final_duration = min(audio.duration, merged_video.duration)
    final_video = merged_video.subclipped(0, final_duration).with_audio(audio)

    caption_clips = []
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
        bg_music = AudioFileClip(download_music()).with_volume_scaled(0.08).with_duration(final_duration)
        final_video = final_video.with_audio(CompositeAudioClip([final_video.audio, bg_music]))
    except Exception as e:
        print(f"⚠️ Music mix failed: {e}")

    whoosh_path = download_whoosh()
    if whoosh_path:
        try:
            whoosh = AudioFileClip(whoosh_path)
            sfx_clips = [whoosh.with_start(t).with_volume_scaled(0.3) for t in np.arange(0, final_duration, 1.5) if t + whoosh.duration <= final_duration]
            if sfx_clips:
                final_video = final_video.with_audio(CompositeAudioClip([final_video.audio] + sfx_clips))
        except Exception as e:
            print(f"⚠️ SFX mix failed: {e}")

    rendered = CompositeVideoClip([final_video] + caption_clips)
    rendered.write_videofile(output, fps=30, codec="libx264", audio_codec="aac", threads=4)
    print(f"✨ Final Short rendered: {output}")
    return output

# ─── 7. YOUTUBE UPLOAD ───────────────────────────────────────────────────────
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
    scenes = [generate_clip(p, i) for i, p in enumerate(storyboard["scenes"])]
    final_mp4 = render_video(scenes, audio_path, timings, storyboard)
    publish_short(final_mp4, storyboard)

if __name__ == "__main__":
    main()
