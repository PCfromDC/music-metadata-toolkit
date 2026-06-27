"""Single validated pipeline for album cover art.

EVERY download and embed of album art MUST go through this module. It exists
because the toolkit was producing invalid art - ffprobe/Jellyfin reported
``width=0, height=0`` - by embedding bytes with no validation, no magic-byte
check, and a format guessed from the file extension (or an unsafe
``data[:8]`` slice that defaulted to JPEG on empty bytes).

Validation is two-engine:
  * Pillow is the cheap in-memory pre-write gate (:func:`validate_image`).
  * ffprobe is the authoritative post-write check - the same engine Jellyfin
    uses - re-reading the saved file to assert the cover stream has real
    dimensions (:func:`embed_in_file`).

Fail policy is layered: :func:`embed_in_file` HARD-FAILS (raises
:class:`InvalidCoverArt`) and never writes bad bytes, while batch helpers such
as :func:`embed_in_album` catch per-file failures, log, skip, and continue.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, Optional, Union

import requests
from PIL import Image
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover

from .audio_file import iter_audio_files
from .ffprobe import attached_pic_dims, ffprobe_available

# Below this, an image is not real album art (icons, tracking pixels, junk).
MIN_DIMENSION = 50
# Technically valid but low quality - warn only, do not reject.
RECOMMENDED_DIMENSION = 500

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

ImageSource = Union[bytes, bytearray, str, "Path"]


class InvalidCoverArt(Exception):
    """Raised when image bytes are missing, corrupt, or not usable as album art."""


def detect_image_mime(data: bytes) -> Optional[str]:
    """Return ``'image/jpeg'`` or ``'image/png'`` from magic bytes, else ``None``.

    Safe on empty or short input.
    """
    if not data:
        return None
    if data[:3] == _JPEG_MAGIC:
        return "image/jpeg"
    if data[:8] == _PNG_MAGIC:
        return "image/png"
    return None


def validate_image(data: bytes) -> str:
    """Validate raw image bytes for embedding; return the MIME type or raise.

    Pillow pre-gate, in order: non-empty -> recognized magic bytes ->
    ``verify()`` (integrity) -> reopen + ``load()`` (``verify()`` invalidates the
    object and does not decode pixels) -> dimensions > 0 -> reject below
    :data:`MIN_DIMENSION`.

    Raises :class:`InvalidCoverArt` on any failure.
    """
    if not data:
        raise InvalidCoverArt("image data is empty (0 bytes)")

    mime = detect_image_mime(data)
    if mime is None:
        raise InvalidCoverArt(f"unrecognized image format (first bytes: {bytes(data[:8])!r})")

    # Pass 1: structural integrity. verify() consumes/!invalidates the object.
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception as exc:
        raise InvalidCoverArt(f"image failed integrity check: {exc}") from exc

    # Pass 2: fresh object, actually decode pixels and read the real size.
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        width, height = img.size
    except Exception as exc:
        raise InvalidCoverArt(f"image could not be decoded: {exc}") from exc

    if width <= 0 or height <= 0:
        raise InvalidCoverArt(f"image has invalid dimensions {width}x{height}")
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise InvalidCoverArt(
            f"image too small to be album art ({width}x{height}, min {MIN_DIMENSION})"
        )
    return mime


def quality_warning(data: bytes) -> Optional[str]:
    """Return a low-resolution warning for already-valid art, or ``None``."""
    try:
        width, height = Image.open(io.BytesIO(data)).size
    except Exception:
        return None
    if width < RECOMMENDED_DIMENSION or height < RECOMMENDED_DIMENSION:
        return (
            f"low-resolution cover {width}x{height} "
            f"(recommended >= {RECOMMENDED_DIMENSION}x{RECOMMENDED_DIMENSION})"
        )
    return None


def download_cover(url: str, *, timeout: int = 60) -> bytes:
    """Download cover art from ``url`` and return validated bytes.

    Raises :class:`InvalidCoverArt` on a network error, a non-image
    Content-Type, or empty/corrupt payload.
    """
    if not url:
        raise InvalidCoverArt("no cover URL provided")
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise InvalidCoverArt(f"download failed: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if content_type and not content_type.lower().startswith("image/"):
        raise InvalidCoverArt(f"response is not an image (content-type: {content_type})")

    data = response.content
    validate_image(data)  # raises on empty/corrupt
    return data


def _read_cover_bytes(image: ImageSource) -> bytes:
    """Accept raw bytes or a filesystem path; always read in binary mode."""
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)
    with open(image, "rb") as handle:
        return handle.read()


def extract_cover_from_file(filepath) -> Optional[bytes]:
    """Return the embedded cover-art bytes from an audio file, or ``None``."""
    path = Path(filepath)
    ext = path.suffix.lower()
    try:
        if ext == ".mp3":
            audio = MP3(str(path), ID3=ID3)
            if audio.tags:
                for key in audio.tags:
                    if key.startswith("APIC"):
                        return audio.tags[key].data
        elif ext in (".m4a", ".mp4"):
            audio = MP4(str(path))
            if audio.get("covr"):
                return bytes(audio["covr"][0])
        elif ext == ".flac":
            audio = FLAC(str(path))
            if audio.pictures:
                return audio.pictures[0].data
    except Exception:
        return None
    return None


def _write_mp3(path: Path, data: bytes, mime: str) -> None:
    try:
        audio = MP3(str(path), ID3=ID3)
    except Exception:
        audio = MP3(str(path))
    if audio.tags is None:
        audio.add_tags()
    audio.tags.delall("APIC")  # never double-embed
    audio.tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=data))
    audio.save()


def _write_m4a(path: Path, data: bytes, mime: str) -> None:
    audio = MP4(str(path))
    image_format = MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG
    audio["covr"] = [MP4Cover(data, imageformat=image_format)]
    audio.save()


def _write_flac(path: Path, data: bytes, mime: str) -> None:
    audio = FLAC(str(path))
    audio.clear_pictures()  # never double-embed
    picture = Picture()
    picture.type = 3  # front cover
    picture.mime = mime
    picture.desc = "Cover"
    picture.data = data
    audio.add_picture(picture)
    audio.save()


def _assert_embedded_ok(path: Path) -> None:
    """Ground-truth post-write check: the saved file must expose real cover dims.

    Uses ffprobe (the engine Jellyfin uses). Falls back to a Pillow decode of
    the extracted bytes when ffprobe is unavailable - in which case consumer
    parity is unverified but we still guarantee the bytes decode.
    """
    if ffprobe_available():
        dims = attached_pic_dims(path)
        if not dims or dims[0] <= 0 or dims[1] <= 0:
            raise InvalidCoverArt(
                f"post-write check failed: ffprobe reports {dims} for embedded art "
                f"in {path.name}"
            )
        return

    data = extract_cover_from_file(path)
    if not data:
        raise InvalidCoverArt(f"post-write check failed: no art found in {path.name}")
    validate_image(data)  # raises if the stored bytes are not a real image


def embed_in_file(filepath, image: ImageSource, *, verify: bool = True) -> None:
    """Embed validated cover art into a single audio file.

    HARD-FAILS with :class:`InvalidCoverArt` if the image is invalid (before
    touching the file, so existing art is preserved) or if the post-write
    ffprobe read-back does not show real dimensions.
    """
    path = Path(filepath)
    data = _read_cover_bytes(image)
    mime = validate_image(data)  # raises before we clear/modify the file

    ext = path.suffix.lower()
    if ext == ".mp3":
        _write_mp3(path, data, mime)
    elif ext in (".m4a", ".mp4"):
        _write_m4a(path, data, mime)
    elif ext == ".flac":
        _write_flac(path, data, mime)
    else:
        raise InvalidCoverArt(f"unsupported audio format: {ext or '(none)'}")

    if verify:
        _assert_embedded_ok(path)


def embed_in_album(
    album_path,
    image: ImageSource,
    *,
    write_folder_jpg: bool = True,
) -> Dict[str, object]:
    """Embed validated cover art into every audio file in an album folder.

    Fail-soft at the batch layer: the source image is validated once up front
    (an invalid source raises and nothing is written), then each file is
    embedded independently - a file that fails is logged in the result and
    skipped while the rest continue.

    Returns a dict: ``{embedded, failed, total, errors}``.
    """
    data = _read_cover_bytes(image)
    validate_image(data)  # whole-batch gate: bad source -> raise, touch nothing

    result: Dict[str, object] = {"embedded": 0, "failed": 0, "total": 0, "errors": []}
    files = list(iter_audio_files(album_path))
    result["total"] = len(files)

    for audio_file in files:
        try:
            embed_in_file(audio_file, data)
            result["embedded"] = int(result["embedded"]) + 1
        except Exception as exc:  # fail-soft: log + skip + continue
            result["failed"] = int(result["failed"]) + 1
            result["errors"].append(f"{audio_file.name}: {exc}")  # type: ignore[attr-defined]

    if write_folder_jpg and int(result["embedded"]) > 0:
        try:
            with open(Path(album_path) / "folder.jpg", "wb") as handle:
                handle.write(data)
        except OSError:
            pass

    return result
