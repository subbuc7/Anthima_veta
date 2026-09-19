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
FAL_KEY = os.getenv("FAL_KEY", "").strip()  # Optional: For genuine AI video motion

HASHTAGS = "#AnthimaVeta #TeluguCinema #ActionThriller #TeluguReels #DailySeries #ReelsIndia #AdityaVarma #Tollywood"

# EXACT VISUAL ANCHORS FOR ALL CHARACTERS (Prevents gender/face hallucination)
EXACT_CHARACTER_PROFILES = {
    "aditya": (
        "42-year-old rugged South Indian male covert operative, intense dark eyes, "
        "short messy black hair with subtle grey streaks, full trimmed black beard, "
        "tall athletic muscular frame, wearing a dark black tactical button-up work shirt, "
        "serious dangerous expression, hyperrealistic cinematic movie shot, 8k"
    ),
    "arjun": (
        "24-year-old young Indian male mechanic, youthful boyish face, curly messy dark hair, "
        "light stubble, wearing dark grey denim mechanic overalls with grease stains, "
        "alert nervous expression, cinematic documentary lighting, 8k"
    ),
    "maya": (
        "29-year-old South Indian female cyber intelligence analyst, sharp observant eyes, "
        "dark hair tied back in a neat bun, wearing black technical tactical clothing, "
        "surrounded by glowing server screens, cinematic cyber thriller lighting, 8k"
    ),
    "vikram": (
        "55-year-old powerful Indian industrialist patriarch, distinguished salt-and-pepper hair "
        "and trimmed beard, cold menacing gaze, wearing an expensive tailored charcoal three-piece suit, "
        "holding whiskey glass, luxury penthouse office background, 8k"
    ),
    "rudra": (
        "45-year-old massive muscular Indian military enforcer, broad shoulders, thick black beard, "
        "military buzzcut, scarred knuckles, wearing black tactical combat vest with chest rig, "
        "lethal disciplined posture, cinematic moody shadows, 8k"
    ),
    "niharika": (
        "29-year-old South Indian woman, kind emotional eyes, gentle but courageous expression, "
        "wavy dark hair, wearing an off-white printed traditional cotton kurta, "
        "warm cinematic lighting, photorealistic 8k"
    ),
    "karthik": (
        "31-year-old sharp Indian business strategist, groomed beard, slick dark hair, "
        "wearing a luxury navy-blue business suit, luxury watch, calculating calm expression, 8k"
    ),
    "kali": (
        "27-year-old mysterious masked shadow operative in all-black tactical hoodie, "
        "face completely concealed by black tactical balaclava, intense dark eyes visible, "
        "sitting with a black combat K9 dog, ominous temple backdrop, 8k"
    )
}


def verify_environment():
    print("=" * 60)
    print("STATUS CHECK:")
    print(f"• INSTAGRAM_ACCOUNT_ID set: {'YES' if IG_ACCOUNT_ID else 'NO'}")
    print(f"• INSTAGRAM_ACCESS_TOKEN set: {'YES' if IG_ACCESS_TOKEN else 'NO'}")
    print(f"• SUPABASE_URL set: {'YES' if SUPABASE_URL else 'NO'}")
    print(f"• SUPABASE_KEY set: {'YES' if SUPABASE_KEY else 'NO'}")
    print(f"• FAL_KEY (AI Video Engine) set: {'YES (Generating real AI video clips)' if FAL_KEY else 'NO (Using zero-key cinematic motion)'}")
    print("=" * 60)


def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
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
        print(f"TTS notice: {stderr.decode()}")


def generate_scene_visual(active_character, scene_action, scene_index, seed=200):
    """
    Generates the scene visual strictly using the character's exact physical identity
    to prevent gender/face mismatches.
    """
    char_profile = EXACT_CHARACTER_PROFILES.get(active_character.lower(), EXACT_CHARACTER_PROFILES["aditya"])
    full_prompt = f"Cinematic film still, {char_profile}, {scene_action}, ARRI Alexa 35mm lens, movie scene, 8k resolution"

    # 1. If FAL_KEY is provided, generate a genuine moving AI video clip
    if FAL_KEY:
        try:
            print(f"Generating true AI video clip for Scene {scene_index} via video engine...")
            headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
            payload = {
                "prompt": full_prompt,
                "aspect_ratio": "9:16",
                "duration": 5
            }
            res = requests.post("https://queue.fal.run/fal-ai/fast-svd/text-to-video", headers=headers, json=payload, timeout=60)
            if res.status_code in (200, 201):
                video_url = res.json().get("video", {}).get("url")
                if video_url:
                    video_clip_path = os.path.join(OUTPUT_DIR, f"scene_{scene_index}_aivideo.mp4")
                    v_res = requests.get(video_url, timeout=60)
                    with open(video_clip_path, "wb") as f:
                        f.write(v_res.content)
                    return {"type": "video", "path": video_clip_path}
        except Exception as e:
            print(f"Video API notice ({e}). Falling back to photorealistic anchor...")

    # 2. Photorealistic character image generation
    encoded_prompt = urllib.parse.quote(full_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&seed={seed + (scene_index * 7)}&model=flux"
    img_path = os.path.join(OUTPUT_DIR, f"scene_{scene_index}_frame.png")

    try:
        res = requests.get(url, timeout=45)
        if res.status_code == 200:
            with open(img_path, "wb") as f:
                f.write(res.content)
            return {"type": "image", "path": img_path}
    except Exception as e:
        print(f"Endpoint warning: {e}")

    # Fallback canvas
    img = Image.new("RGB", (1080, 1920), (14, 18, 30))
    draw = ImageDraw.Draw(img)
    draw.text((100, 960), f"ANTHIMA VETA — SCENE {scene_index}", fill=(255, 215, 60))
    img.save(img_path)
    return {"type": "image", "path": img_path}


def create_ass_subtitles(dialogues, scene_duration, ass_path):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TeluguSub,Lohit Telugu,54,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,80,80,260,1

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


def render_scene_video(visual_asset, audio_path, dialogues, scene_num, motion_type="push_in", duration=12):
    scene_mp4 = os.path.join(OUTPUT_DIR, f"scene_{scene_num}.mp4")
    ass_path = os.path.join(OUTPUT_DIR, f"scene_{scene_num}.ass")
    create_ass_subtitles(dialogues, duration, ass_path)
    escaped_ass = ass_path.replace(":", "\\:").replace("\\", "/")

    fps = 25
    frames = duration * fps

    if visual_asset["type"] == "video":
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", visual_asset["path"],
            "-i", audio_path,
            "-filter_complex", f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,ass={escaped_ass}[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            scene_mp4
        ]
    else:
        img_path = visual_asset["path"]
        if motion_type == "push_in":
            zoom_filter = f"zoompan=z='min(zoom+0.0014,1.22)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}"
        elif motion_type == "pan_left":
            zoom_filter = f"zoompan=z=1.14:x='if(lte(on,1),(iw-iw/zoom)/2,x-0.9)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps}"
        elif motion_type == "pan_right":
            zoom_filter = f"zoompan=z=1.14:x='if(lte(on,1),(iw-iw/zoom)/2,x+0.9)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps}"
        else:
            zoom_filter = f"zoompan=z='min(zoom+0.0018,1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}"

        video_filter = f"{zoom_filter},ass={escaped_ass}"
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_path,
            "-i", audio_path,
            "-vf", video_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
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
        print("ERROR: Supabase credentials missing. Cannot upload.")
        return None

    filename = f"episodes/anthima_veta_ep_{episode_num:03d}_{int(time.time())}.mp4"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/public_media/{filename}"

    print(f"Uploading video to Supabase Storage: {filename}...")
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
        print(f"Upload failed: HTTP {res.status_code} - {res.text}")
        return None


def publish_to_instagram(video_url, caption):
    if not IG_ACCOUNT_ID or not IG_ACCESS_TOKEN or not video_url:
        print("ERROR: Missing credentials or video URL. Skipping publishing.")
        return None

    print(f"Creating Instagram Reel container for ID {IG_ACCOUNT_ID}...")
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
        print(f"Container Error: {r}")
        return None

    print(f"Container ID {container_id} created. Polling processing status...")
    status_url = f"https://graph.facebook.com/v19.0/{container_id}"
    for i in range(30):
        time.sleep(10)
        res = requests.get(status_url, params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN}).json()
        status = res.get("status_code")
        print(f"Status check {i+1}/30: {status}")
        if status == "FINISHED":
            break
        elif status == "ERROR":
            print(f"Processing error: {res}")
            return None
    else:
        print("Processing timed out.")
        return None

    publish_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish"
    pub_res = requests.post(publish_url, data={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN}).json()
    print(f"Reel successfully published: {pub_res}")
    return pub_res.get("id")


async def process_episode():
    verify_environment()

    tracker = load_tracker()
    ep_num = tracker.get("current_episode", 1)
    ep_file = os.path.join(EPISODES_DIR, f"episode_{ep_num:03d}.json")

    # Automatically fall back to episode 1 if targeted episode is missing
    if not os.path.exists(ep_file):
        print(f"Notice: {ep_file} not found. Checking for episode_001.json...")
        fallback_file = os.path.join(EPISODES_DIR, "episode_001.json")
        if os.path.exists(fallback_file):
            ep_file = fallback_file
            ep_num = 1
        else:
            sys.exit(f"ERROR: No script found in '{EPISODES_DIR}'.")

    with open(ep_file, "r", encoding="utf-8") as f:
        ep_data = json.load(f)

    print(f"\n>>> PROCESSING: {ep_data['title']} (Episode {ep_num}) <<<")
    scene_files = []

    for idx, scene in enumerate(ep_data["scenes"], start=1):
        print(f"\n--- Scene {idx}/5: {scene['title']} (Character: {scene['active_character'].upper()}) ---")

        # Audio synthesis per dialogue line
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

        # Generates character-anchored visual
        visual_asset = generate_scene_visual(scene["active_character"], scene["setting_description"], idx)

        # Render 12s scene MP4
        scene_mp4 = render_scene_video(
            visual_asset, scene_audio, scene["dialogues"],
            idx, scene.get("camera_motion", "push_in"), scene["duration"]
        )
        scene_files.append(scene_mp4)

    # Stitch into 60s video
    print("\nStitching 5 scenes into 60s vertical MP4...")
    final_mp4 = stitch_episode(scene_files, ep_num)
    print(f"Video generated: {final_mp4}")

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
        print("\nNotice: Video rendered and uploaded, but Instagram API did not return a post ID.")


if __name__ == "__main__":
    asyncio.run(process_episode())
    
