import os
import time
import requests
import glob
import subprocess
import traceback

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp

# Bot Token
BOT_TOKEN = "..."

# Spotify API credentials
SPOTIFY_CLIENT_ID = "..."
SPOTIFY_CLIENT_SECRET = "..."

# Spotify API client
spotify_auth = SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET)
spotify = spotipy.Spotify(auth_manager=spotify_auth)

def get_tracks_from_album(url):
    try:
        album_id = url.split("/album/")[1].split("?")[0]
        album = spotify.album(album_id)
        return album["tracks"]["items"]
    except Exception as e:
        print("Album error:", e)
        return []

def get_tracks_from_playlist(url):
    try:
        playlist_id = url.split("/playlist/")[1].split("?")[0]
        playlist = spotify.playlist_tracks(playlist_id)
        return [item["track"] for item in playlist["items"] if item["track"]]
    except Exception as e:
        print("Playlist error:", e)
        return []

def download_spotify_mp3s(track_urls):
    try:
        for f in glob.glob("*.mp3"):
            os.remove(f)
        ffmpeg_path = r"..."
        process = subprocess.Popen(
            ["python", "-m", "spotdl", "--ffmpeg", ffmpeg_path, *track_urls],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()

        print("spotdl stdout:", stdout)
        print("spotdl stderr:", stderr)

        if process.returncode != 0:
            print(f"spotdl exited with code {process.returncode}")
            return []

        return glob.glob("*.mp3")
    except Exception as e:
        print("Download error:", e)
        traceback.print_exc()
        return []

def download_image(url, filename="cover.jpg"):
    try:
        img_data = requests.get(url).content
        with open(filename, 'wb') as f:
            f.write(img_data)
        return filename
    except Exception as e:
        print("Image download error:", e)
        return None

def download_from_url(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'media.%(ext)s'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    try:
        if "spotify.com/album/" in url:
            await update.message.reply_text("🎧 تحميل الألبوم، المرجو الانتظار...")
            tracks = get_tracks_from_album(url)

        elif "spotify.com/playlist/" in url:
            await update.message.reply_text("🎶 تحميل Playlist، المرجو الانتظار...")
            tracks = get_tracks_from_playlist(url)

        elif "spotify.com/track/" in url:
            await update.message.reply_text("🎵 تحميل الأغنية...")
            tracks = [spotify.track(url.split("/track/")[1].split("?")[0])]

        elif "tiktok.com" in url or "vm.tiktok.com" in url or "instagram.com" in url:
            await update.message.reply_text("📥 جاري تحميل الفيديو من TikTok/Instagram...")
            file_path = download_from_url(url)
            await update.message.reply_video(video=open(file_path, 'rb'))
            os.remove(file_path)
            return

        else:
            await update.message.reply_text("❗ المرجو إرسال رابط صحيح من Spotify أو TikTok أو Instagram.")
            return

        if not tracks:
            await update.message.reply_text("❌ لم أتمكن من الحصول على الأغاني.")
            return

        track_urls = [track["external_urls"]["spotify"] for track in tracks]
        mp3_files = download_spotify_mp3s(track_urls)

        if not mp3_files:
            await update.message.reply_text("❌ حدث خطأ أثناء تحميل الملفات الصوتية.")
            return

        for track, mp3_file in zip(tracks, mp3_files):
            title = track["name"]
            artist = track["artists"][0]["name"]
            image_url = track["album"]["images"][0]["url"] if "album" in track else None

            cover_path = download_image(image_url, "cover.jpg") if image_url else None

            with open(mp3_file, 'rb') as audio:
                if cover_path and os.path.exists(cover_path):
                    with open(cover_path, 'rb') as thumb:
                        await update.message.reply_audio(
                            audio=audio,
                            title=title,
                            performer=artist,
                            caption=f"🎵 {title}\n👤 {artist}",
                            thumbnail=thumb
                        )
                else:
                    await update.message.reply_audio(
                        audio=audio,
                        title=title,
                        performer=artist,
                        caption=f"🎵 {title}\n👤 {artist}"
                    )

            os.remove(mp3_file)
            if cover_path and os.path.exists(cover_path):
                os.remove(cover_path)

        await update.message.reply_text("✅ تم إرسال جميع الأغاني!")

    except Exception as e:
        tb_str = traceback.format_exc()
        print("Error:", e)
        print(tb_str)
        await update.message.reply_text(f"⚠️ وقع خطأ أثناء المعالجة:\n{str(e)}\n\n{tb_str}")

# تشغيل البوت
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
