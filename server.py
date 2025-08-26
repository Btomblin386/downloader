import os
from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/extract")
def extract():
    """
    Body: { "url": "<facebook/instagram reel or video url>" }
    Returns: { id, title, uploader, duration, ext, webpage_url, download_url?, hls_url? }
    - Tries to pick the best progressive MP4 (video+audio) for easy downloading.
    - If Facebook only serves HLS, returns hls_url (m3u8) as a fallback.
    """
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

        # Prefer a progressive MP4 (http/https, ext mp4/mov, has both audio & video)
        best_prog = None
        for f in info.get("formats", []):
            if f.get("protocol") in ("http", "https") and f.get("ext") in ("mp4", "mov"):
                if f.get("vcodec") != "none" and f.get("acodec") != "none":
                    if best_prog is None:
                        best_prog = f
                    else:
                        cur_key = (f.get("height") or 0, f.get("tbr") or 0)
                        best_key = (best_prog.get("height") or 0, best_prog.get("tbr") or 0)
                        if cur_key > best_key:
                            best_prog = f

        # If no progressive MP4, fall back to HLS (m3u8)
        best_hls = None
        if best_prog is None:
            for f in info.get("formats", []):
                if f.get("protocol") in ("m3u8", "m3u8_native"):
                    if best_hls is None:
                        best_hls = f
                    else:
                        cur_key = (f.get("height") or 0, f.get("tbr") or 0)
                        best_key = (best_hls.get("height") or 0, best_hls.get("tbr") or 0)
                        if cur_key > best_key:
                            best_hls = f

        return jsonify({
            "id": info.get("id"),
            "title": info.get("title"),
            "uploader": info.get("uploader") or info.get("channel") or info.get("uploader_id"),
            "duration": info.get("duration"),
            "ext": (best_prog or {}).get("ext") or info.get("ext") or "mp4",
            "webpage_url": info.get("webpage_url") or url,
            "download_url": (best_prog or {}).get("url"),  # direct MP4 if available
            "hls_url": (best_hls or {}).get("url")         # .m3u8 fallback
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # IMPORTANT on Render: bind to the provided PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
