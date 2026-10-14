"""Download the selected speech originals; optionally convert with local FFmpeg.

Requires Python 3.10+ and Internet access. FFmpeg is optional and is never installed
automatically. Page transcripts are drafts for checking against the actual audio.
"""

from __future__ import annotations

import argparse
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import wave
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


ROOT = Path(__file__).resolve().parents[1]
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}


class SpeechPage(HTMLParser):
    """Read advertised audio URLs and the text after a Transcript heading."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.media = []
        self.transcript = []
        self.capture = False
        self.heading = None
        self.heading_text = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.ignored += 1
        for key in ("src", "href", "data-src"):
            value = attrs.get(key, "")
            if Path(urlparse(value).path).suffix.lower() in AUDIO_EXTENSIONS:
                self.media.append(value)
        if tag in {"h1", "h2", "h3", "h4"}:
            self.capture = False
            self.heading = tag
            self.heading_text = []
        if self.capture and tag in {"p", "br", "li"}:
            self.transcript.append("\n")

    def handle_data(self, data):
        if self.ignored:
            return
        if self.heading:
            self.heading_text.append(data)
        elif self.capture:
            if data.strip().lower() in {"view transcript", "previous", "next"}:
                self.capture = False
            else:
                self.transcript.append(data)

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignored = max(0, self.ignored - 1)
        if tag == self.heading:
            self.capture = " ".join(self.heading_text).strip().lower() == "transcript"
            self.heading = None
        if self.capture and tag == "p":
            self.transcript.append("\n")


def read_page(url):
    req = Request(url, headers={"User-Agent": "TrackC-ReferenceCollector/1.0"})
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_page(html, page_url):
    parser = SpeechPage()
    parser.feed(html)
    media = parser.media
    # Some archive pages advertise media URLs in JSON rather than source tags.
    normalized = unescape(html).replace("\\/", "/").replace("\\u002F", "/")
    media += re.findall(r'https?://[^\s<>"\']+\.(?:mp3|wav|flac|ogg|m4a)(?:\?[^\s<>"\']*)?', normalized)
    urls = list(dict.fromkeys(urljoin(page_url, u) for u in media))
    preference = {".mp3": 0, ".wav": 1, ".flac": 2, ".ogg": 3, ".m4a": 4}
    urls.sort(key=lambda u: preference.get(Path(urlparse(u).path).suffix.lower(), 9))
    text = "\n\n".join(" ".join(p.split()) for p in "".join(parser.transcript).split("\n") if p.strip())
    return urls, text


def download(url, destination):
    part = destination.with_suffix(destination.suffix + ".part")
    req = Request(url, headers={"User-Agent": "TrackC-ReferenceCollector/1.0"})
    digest = hashlib.sha256()
    size = 0
    try:
        with urlopen(req, timeout=60) as response, part.open("wb") as output:
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type or "application/json" in content_type:
                raise ValueError("The media URL returned a page rather than audio.")
            while chunk := response.read(1024 * 1024):
                if size == 0 and chunk.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                    raise ValueError("The media URL returned HTML rather than audio.")
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size < 1024:
            raise ValueError("The returned audio file is unexpectedly small.")
        part.replace(destination)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    return digest.hexdigest(), size


def convert(source, destination, ffmpeg):
    partial = destination.with_name(destination.stem + ".partial.wav")
    try:
        subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
                        "-c:a", "pcm_s16le", str(partial)], check=True)
        with wave.open(str(partial)) as audio:
            if (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) != (1, 16000, 2):
                raise ValueError("Converted WAV does not have the required format.")
            duration = audio.getnframes() / audio.getframerate()
            if duration <= 0:
                raise ValueError("Converted WAV is empty.")
        partial.replace(destination)
        return round(duration, 3)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="+", help="Download only these IDs from sources.json")
    ap.add_argument("--ffmpeg", help="Explicit path to an already installed FFmpeg executable")
    ap.add_argument("--convert-only", action="store_true", help="Convert downloaded originals without network access")
    args = ap.parse_args()
    manifest = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    known = {s["id"] for s in manifest["speeches"]}
    if args.only and set(args.only) - known:
        ap.error("Unknown IDs: " + ", ".join(sorted(set(args.only) - known)))
    ffmpeg = args.ffmpeg or shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass
    if args.convert_only and not ffmpeg:
        ap.error("Conversion requires an already installed FFmpeg executable.")
    for name in ("originals", "wav", "transcripts"):
        (ROOT / name).mkdir(exist_ok=True)
    status_path = ROOT / "download_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    failed = 0
    for speech in manifest["speeches"]:
        ident = speech["id"]
        if args.only and ident not in args.only:
            continue
        print(f"{ident}: processing", flush=True)
        item = status.setdefault(ident, {})
        try:
            original = ROOT / item["original_file"] if item.get("original_file") else None
            if original is None or not original.exists():
                if args.convert_only:
                    raise ValueError("No previously downloaded original found.")
                html = read_page(speech["source_page"])
                urls, transcript = parse_page(html, speech["source_page"])
                if not urls:
                    raise ValueError("No advertised audio URL found; use Download media on the source page.")
                if transcript:
                    transcript_path = ROOT / "transcripts" / (ident + ".txt")
                    transcript_path.write_text(transcript + "\n", encoding="utf-8")
                    item["transcript_file"] = str(transcript_path.relative_to(ROOT))
                    item["transcript_status"] = "source_text_not_audio_verified"
                errors = []
                for url in urls:
                    original = ROOT / "originals" / (ident + Path(urlparse(url).path).suffix.lower())
                    try:
                        sha, size = download(url, original)
                        item.update(original_file=str(original.relative_to(ROOT)), media_url=url,
                                    sha256=sha, size_bytes=size)
                        break
                    except Exception as exc:
                        errors.append(str(exc))
                else:
                    raise RuntimeError("All advertised media URLs failed: " + "; ".join(errors))
            if ffmpeg:
                destination = ROOT / "wav" / (ident + ".wav")
                duration = convert(original, destination, ffmpeg)
                item.update(status="wav_ready_for_manual_review", wav_file=str(destination.relative_to(ROOT)),
                            duration_seconds=duration, sample_rate_hz=16000, channels=1)
            else:
                item["status"] = "original_downloaded_conversion_pending"
            item.pop("error", None)
            print(f"  {item['status']}", flush=True)
        except Exception as exc:
            failed += 1
            item.update(status="failed", error=str(exc), source_page=speech["source_page"])
            print(f"  Failed: {exc}\n  Manual source: {speech['source_page']}", flush=True)
        status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not ffmpeg:
        print("FFmpeg was not found. Keep the originals and run --convert-only after FFmpeg is available.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
