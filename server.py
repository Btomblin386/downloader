from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

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
        # grab the best direct media url
        direct = info.get("url")
        return jsonify({
            "id": info.get("id"),
            "title": info.get("title"),
            "uploader": info.get("uploader") or info.get("channel") or info.get("uploader_id"),
            "duration": info.get("duration"),
            "ext": info.get("ext") or "mp4",
            "webpage_url": info.get("webpage_url") or url,
            "download_url": direct
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
