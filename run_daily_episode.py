
import os
import sys
import json
import time
import urllib.parse
import asyncio
import requests
import subprocess
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw

# Timezone & Directories
IST = timezone(timedelta(hours=5, minutes=30))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EPISODES_DIR = os.path.join(BASE_DIR, "episodes")
CHARACTERS_DIR = os.path.join(BASE_DIR, "characters")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TRACKER_FILE = os.path.join(BASE_DIR, "episode_tracker.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CHARACTERS_DIR, exist_ok=True)

# Secrets & Environment Variables
IG_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
IG_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

HASHTAGS = "#AnthimaVeta #TeluguCinema #ActionThriller #TeluguReels #DailySeries #ReelsIndia #AdityaVarma #Tollywood"


def verify_environment():
    """Prints diagnostic status of all secrets and folders."""
    print("=" * 60)
    print("DIAGNOSTIC STATUS CHECK:")
    print(f"• INSTAGRAM_ACCOUNT_ID set: {'YES (' + IG_ACCOUNT_ID[:5] + '...)' if IG_ACCOUNT_ID else 'NO (MISSING SECRET!)'}")
    print(f"• INSTAGRAM_ACCESS_TOKEN set: {'YES' if IG_ACCESS_TOKEN else 'NO (MISSING SECRET!)'}")
    print(f"• SUPABASE_URL set: {'YES (' + SUPABASE_URL + ')' if SUPABASE_URL else 'NO (MISSING SECRET!)'}")
    print(f"• SUPABASE_KEY set: {'YES' if SUPABASE_KEY else 'NO (MISSING SECRET!)'}")
    print(f"• Episodes directory exists: {os.path.exists(EPISODES_DIR)}")
    if os.path.exists(EPISODES_DIR):
        print(f"• Files inside 'episodes/': {os.listdir(EPISODES_DIR)}")
    print("=" * 60)

    if not IG_ACCOUNT_ID or not IG_ACCESS_TOKEN:
        print("CRITICAL WARNING: Instagram secrets are missing in GitHub repository secrets!")
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("CRITICAL WARNING: Supabase secrets are missing in GitHub repository secrets!")


def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Tracker read notice: {e}")
    return {"current_episode": 1, "history": []}


def save_tracker(tracker):
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)


async def synthesize_speech(text, voice, pitch, rate, output_path):
    cmd = [
        "edge-tts",
        "--voice", voice,
        "--text", text,
        f"--pitch={pitch}",
        f"--rate={rate}",
        "--write-media", output_path
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        print(f"TTS log: {stderr.decode()}")


def fetch_ai_cinematic_frame(prompt, scene_index, seed=100):
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&seed={seed + scene_index}&model=flux"
    img_path = os.path.join(OUTPUT_DIR, f"scene_{scene_index}_raw.png")

    try:
        res = requests.get(url, timeout=45)
        if res.status_code == 200:
            with open(img_path, "wb") as f:
                f.write(res.content)
            return img_path
    except Exception as e:
        print(f"Frame fetch warning: {e}. Generating background canvas.")

    img = Image.new("RGB", (1080, 1920), (14, 18, 30))
    draw = ImageDraw.Draw(img)
    draw.text((100, 960), f"ANTHIMA VETA — SCENE {scene_index}", fill=(255, 215, 60))
    img.save(img_path)
    return img_path


def create_ass_subtitles(dialogues, scene_duration, ass_path):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TeluguSub,Lohit Telugu,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    current_time = 0.5
    for d in dialogues:
        text = d["text"]
        speaker = d.get("speaker", "")
        duration = max(2.5, len(text) * 0.16)
        end_time = min(scene_duration - 0.2, current_time + duration)

        start_str = f"0:{int(current_time // 60):02d}:{current_time % 60:05.2f}"
        end_str = f"0:{int(end_time // 60):02d}:{end_time % 60:05.2f}"

        formatted_text = f"{{\\c&H00D4FF&}}{speaker}: {{\\c&HFFFFFF&}}{text}" if speaker else text
        events.append(f"Dialogue: 0,{start_str},{end_str},TeluguSub,,0,0,0,,{formatted_text}")
        current_time = end_time + 0.3

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events))


def render_scene_video(img_path, audio_path, dialogues, scene_num, motion_type="push_in", duration=12):
    scene_mp4 = os.path.join(OUTPUT_DIR, f"scene_{scene_num}.mp4")
    ass_path = os.path.join(OUTPUT_DIR, f"scene_{scene_num}.ass")
    create_ass_subtitles(dialogues, duration, ass_path)

    fps = 25
    frames = duration * fps

    if motion_type == "push_in":
        zoom_filter = f"zoompan=z='min(zoom+0.0012,1.20)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}"
    elif motion_type == "pan_left":
        zoom_filter = f"zoompan=z=1.12:x='if(lte(on,1),(iw-iw/zoom)/2,x-0.8)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps}"
    elif motion_type == "pan_right":
        zoom_filter = f"zoompan=z=1.12:x='if(lte(on,1),(iw-iw/zoom)/2,x+0.8)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps}"
    else:
        zoom_filter = f"zoompan=z='min(zoom+0.0018,1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}"

    escaped_ass = ass_path.replace(":", "\\:").replace("\\", "/")
    video_filter = f"{zoom_filter},ass={escaped_ass}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", img_path,
        "-i", audio_path,
        "-vf", video_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        scene_mp4
    ]
    subprocess.run(cmd, check=True)
    return scene_mp4


def stitch_episode(scene_files, episode_num):
    concat_list = os.path.join(OUTPUT_DIR, "concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for s in scene_files:
            f.write(f"file '{os.path.abspath(s)}'\n")

    output_episode_mp4 = os.path.join(OUTPUT_DIR, f"anthima_veta_ep_{episode_num:03d}.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        output_episode_mp4
    ]
    subprocess.run(cmd, check=True)
    return output_episode_mp4


def upload_to_supabase(video_path, episode_num):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL or SUPABASE_KEY is empty. Cannot upload video.")
        return None

    filename = f"episodes/anthima_veta_ep_{episode_num:03d}_{int(time.time())}.mp4"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/public_media/{filename}"

    print(f"Uploading video to Supabase: {upload_url} ...")
    with open(video_path, "rb") as f:
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "video/mp4"
        }
        res = requests.post(upload_url, headers=headers, data=f)

    if res.status_code in (200, 201):
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/public_media/{filename}"
        print(f"Upload successful! Public URL: {public_url}")
        return public_url
    else:
        print(f"Supabase Upload Failed! HTTP {res.status_code}: {res.text}")
        return None


def publish_to_instagram(video_url, caption):
    if not IG_ACCOUNT_ID or not IG_ACCESS_TOKEN:
        print("ERROR: INSTAGRAM_ACCOUNT_ID or INSTAGRAM_ACCESS_TOKEN is missing. Cannot publish.")
        return None
    if not video_url:
        print("ERROR: Public video URL is missing. Cannot publish to Instagram.")
        return None

    print(f"Initiating Instagram Reel container for account {IG_ACCOUNT_ID}...")
    create_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }
    r = requests.post(create_url, data=payload).json()
    container_id = r.get("id")
    if not container_id:
        print(f"Instagram Container Creation Error: {r}")
        return None

    print(f"Container created successfully (ID: {container_id}). Polling Meta processing status...")
    status_url = f"https://graph.facebook.com/v19.0/{container_id}"
    for i in range(30):
        time.sleep(10)
        res = requests.get(status_url, params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN}).json()
        status = res.get("status_code")
        print(f"Status check {i+1}/30: {status}")
        if status == "FINISHED":
            break
        elif status == "ERROR":
            print(f"Meta processing failed: {res}")
            return None
    else:
        print("Meta processing timed out.")
        return None

    publish_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish"
    pub_res = requests.post(publish_url, data={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN}).json()
    print(f"Instagram Publish Result: {pub_res}")
    return pub_res.get("id")


async def process_episode():
    verify_environment()

    tracker = load_tracker()
    ep_num = tracker.get("current_episode", 1)
    ep_file = os.path.join(EPISODES_DIR, f"episode_{ep_num:03d}.json")

    # If the targeted episode is missing, fallback to episode_001.json
    if not os.path.exists(ep_file):
        print(f"Notice: {ep_file} not found. Checking for episode_001.json...")
        fallback_file = os.path.join(EPISODES_DIR, "episode_001.json")
        if os.path.exists(fallback_file):
            ep_file = fallback_file
            ep_num = 1
            print("Found episode_001.json! Processing Episode 1.")
        else:
            sys.exit(f"FATAL ERROR: No episode file found in '{EPISODES_DIR}'. Please create 'episodes/episode_001.json'.")

    with open(ep_file, "r", encoding="utf-8") as f:
        ep_data = json.load(f)

    print(f"\n>>> PROCESSING: {ep_data['title']} (Episode {ep_num}) <<<")
    scene_files = []

    for idx, scene in enumerate(ep_data["scenes"], start=1):
        print(f"\n--- Scene {idx}/5: {scene['title']} ---")

        # Audio synthesis
        audio_parts = []
        for d_idx, d in enumerate(scene["dialogues"]):
            part_path = os.path.join(OUTPUT_DIR, f"s_{idx}_d_{d_idx}.mp3")
            await synthesize_speech(d["text"], d["voice"], d["pitch"], d["rate"], part_path)
            audio_parts.append(part_path)

        scene_audio = os.path.join(OUTPUT_DIR, f"scene_{idx}_audio.mp3")
        if len(audio_parts) == 1:
            cmd = ["ffmpeg", "-y", "-i", audio_parts[0], "-af", f"apad=whole_dur={scene['duration']}", scene_audio]
            subprocess.run(cmd, check=True)
        else:
            filter_str = "".join([f"[{i}:a]" for i in range(len(audio_parts))]) + f"concat=n={len(audio_parts)}:v=0:a=1[a]"
            inputs = []
            for p in audio_parts:
                inputs.extend(["-i", p])
            cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", filter_str, "-map", "[a]", "-af", f"apad=whole_dur={scene['duration']}", scene_audio]
            subprocess.run(cmd, check=True)

        # Image generation
        prompt = scene["character_action_prompt"]
        img_path = fetch_ai_cinematic_frame(prompt, idx)

        # Render 12s scene MP4
        scene_mp4 = render_scene_video(
            img_path, scene_audio, scene["dialogues"],
            idx, scene.get("camera_motion", "push_in"), scene["duration"]
        )
        scene_files.append(scene_mp4)

    # Stitch into 60s video
    print("\nStitching 5 scenes into 60s vertical video...")
    final_mp4 = stitch_episode(scene_files, ep_num)
    print(f"Video file generated: {final_mp4} ({os.path.getsize(final_mp4)} bytes)")

    caption = (
        f"🎬 {ep_data['title']}\n\n"
        "ఒక భయంకరమైన గతం... పదిహేడేళ్ల తర్వాత మళ్లీ నిద్రలేచింది.\n"
        "ఆదిత్య వర్మ అలియాస్ 'శూన్యం' వేట మొదలైంది.\n\n"
        "📺 Daily 60-Second Episode at 5:00 AM IST.\n\n"
        f"{HASHTAGS}"
    )

    public_url = upload_to_supabase(final_mp4, ep_num)
    post_id = publish_to_instagram(public_url, caption)

    if post_id:
        print(f"\nSUCCESS: Published Reel to Instagram! Post ID: {post_id}")
        tracker["history"].append({
            "episode": ep_num,
            "title": ep_data["title"],
            "timestamp": datetime.now(IST).isoformat(),
            "instagram_post_id": post_id
        })
        tracker["current_episode"] = ep_num + 1
        save_tracker(tracker)
    else:
        print("\nNotice: Video rendered and uploaded, but Instagram API did not return a post ID. Check diagnostic logs above.")


if __name__ == "__main__":
    asyncio.run(process_episode())
      
