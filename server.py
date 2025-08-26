import os, tempfile
from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

# Load Google Drive credentials (from secret file on Render)
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service-account.json")
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=creds)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/extract")
def extract():
    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "missing url"}), 400

    ydl_opts = {
        "quiet": True,
        "nocheckcertificate": True,
        "skip_download": True,
        "geo_bypass": True,
        "noplaylist": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Try to pick a direct progressive MP4
        best_prog = next(
            (
                f for f in info.get("formats", [])
                if f.get("protocol") in ("http", "https")
                and f.get("ext") == "mp4"
                and f.get("vcodec") != "none"
                and f.get("acodec") != "none"
            ),
            None,
        )

        # If progressive available, return its URL
        if best_prog:
            return jsonify({
                "id": info.get("id"),
                "title": info.get("title"),
                "uploader": info.get("uploader"),
                "duration": info.get("duration"),
                "download_url": best_prog.get("url"),
                "webpage_url": info.get("webpage_url"),
            })

        # Otherwise, download HLS with yt-dlp + ffmpeg, upload to Drive
        tmpdir = tempfile.mkdtemp()
        filepath = os.path.join(tmpdir, f"{info.get('id')}.mp4")
        ydl_dl_opts = {
            "outtmpl": filepath,
            "format": "mp4",
            "quiet": True,
        }
        with YoutubeDL(ydl_dl_opts) as ydl:
            ydl.download([url])

        # Upload to Google Drive
        file_metadata = {"name": os.path.basename(filepath)}
        media = MediaFileUpload(filepath, mimetype="video/mp4")
        drive_file = drive_service.files().create(
            body=file_metadata, media_body=media, fields="id,webViewLink"
        ).execute()

        return jsonify({
            "id": info.get("id"),
            "title": info.get("title"),
            "uploader": info.get("uploader"),
            "duration": info.get("duration"),
            "drive_file_id": drive_file["id"],
            "drive_link": drive_file["webViewLink"],
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
