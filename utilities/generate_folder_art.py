#!/usr/bin/env python3
"""
Generate folder.jpg / folder.png for albums that have valid embedded art but no
folder image (the file Jellyfin and other scanners prefer for album art).

ADDITIVE + SAFE by design:
  - Writes a folder image ONLY to albums with no folder.jpg/cover.jpg/front.jpg.
  - Exclusive create ('xb'): if a folder image appears concurrently it is never
    overwritten - the album is skipped, honoring the never-overwrite contract.
  - NEVER writes to audio files (embedded art is read-only here), so embedded-art
    health and ffprobe width>0 cannot regress.
  - Validates every image (magic bytes + Pillow decode + dims>0) AND confirms it is
    ffmpeg-readable (the Jellyfin ground truth) before writing. Non-JPEG/PNG or
    ffmpeg-unreadable art is salvaged by re-encoding to a clean JPEG via Pillow.
  - Post-write read-back: the written file is re-probed (ffprobe dims>0, or Pillow
    if ffprobe is unavailable); a bad/truncated write is deleted and reported.
  - Degrades gracefully when ffprobe/static-ffmpeg is unavailable: falls back to the
    Pillow decode check (same policy as utilities/core), rather than failing every album.
  - The image extension matches the detected content (folder.png for PNG bytes).
  - Per-album fail-soft: an error on one album is logged and skipped, never aborting
    the batch. Created paths are appended to the undo log immediately.

Modes:
  --scan-only   list albums missing a folder image (no art reads, no writes)
  --dry-run     validate each candidate's art (no writes; default)
  --execute     write the folder image where missing

Usage:
  python utilities/generate_folder_art.py "/path/to/Music" --scan-only
  python utilities/generate_folder_art.py "/path/to/Music" --dry-run
  python utilities/generate_folder_art.py "/path/to/Music" --execute
"""
import argparse
import os
import stat
import sys
import tempfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402
from utilities.core.cover_art import (  # noqa: E402
    extract_cover_from_file,
    validate_image,
    detect_image_mime,
    InvalidCoverArt,
)
from utilities.core.ffprobe import attached_pic_dims, ffprobe_available  # noqa: E402
from utilities.core.audio_file import AUDIO_EXTS  # noqa: E402

EXC = {'.recycle', '@eadir', '#recycle', 'backups', '.cover_backup'}
IMG_EXT = {'.jpg', '.jpeg', '.png'}
FOLDER_STEMS = ('folder', 'cover', 'front')


class _Skip(Exception):
    """Album skipped (e.g. a folder image already exists) - not a failure."""


def excluded(root: Path, p: Path) -> bool:
    return any(
        x.lower() in EXC or x.startswith(('.', '@', '#'))
        for x in p.relative_to(root).parts
    )


def has_folder_image(d: Path) -> bool:
    for f in d.iterdir():
        if f.is_file() and f.suffix.lower() in IMG_EXT and f.stem.lower() in FOLDER_STEMS:
            return True
    return False


def find_missing_albums(root: Path):
    """Album dirs (containing audio) that have no folder/cover/front image."""
    missing = []
    for dp, dn, fn in os.walk(root):
        p = Path(dp)
        if p != root and excluded(root, p):
            dn[:] = []
            continue
        audio = sorted(p / n for n in fn if os.path.splitext(n)[1].lower() in AUDIO_EXTS)
        if audio and not has_folder_image(p):
            missing.append((p, audio))
    return missing


def first_embedded_art(audio_files):
    """Return embedded art bytes from the first track that has any, else None.

    Scans all tracks (not just track 1) so an album whose first-sorted track lacks
    art but whose others have it is still covered.
    """
    for f in audio_files:
        raw = extract_cover_from_file(f)
        if raw:
            return raw
    return None


def ffmpeg_image_dims(data: bytes):
    """(w, h) that ffprobe reads from standalone image bytes, or None.

    Reuses core.ffprobe.attached_pic_dims (it matches a lone mjpeg/png video
    stream too). Uses a unique temp file per call (no shared-path race).
    """
    fd, tmp = tempfile.mkstemp(suffix='.img', prefix='fja_')
    try:
        with os.fdopen(fd, 'wb') as fh:
            fh.write(data)
        return attached_pic_dims(tmp)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def prepare_image(data: bytes, has_ffprobe: bool):
    """Return (final_bytes, mime, reencoded:bool) or raise InvalidCoverArt.

    Lossless fast path when the bytes already validate and are ffmpeg-readable.
    Otherwise (unrecognized format, too-small-after-magic, or ffmpeg-unreadable)
    salvage by re-encoding to a clean JPEG via Pillow and re-validate.
    When ffprobe is unavailable, accept Pillow-validated bytes (graceful degrade).
    """
    try:
        mime = validate_image(data)
        valid_as_is = True
    except InvalidCoverArt:
        mime, valid_as_is = None, False

    if valid_as_is:
        if not has_ffprobe:
            return data, mime, False
        dims = ffmpeg_image_dims(data)
        if dims and dims[0] > 0 and dims[1] > 0:
            return data, mime, False

    # Salvage path: re-encode whatever Pillow can open into a clean JPEG.
    try:
        im = Image.open(BytesIO(data)).convert('RGB')
        buf = BytesIO()
        im.save(buf, 'JPEG', quality=92)
        reenc = buf.getvalue()
    except Exception as exc:  # UnidentifiedImageError, OSError, MemoryError, ...
        raise InvalidCoverArt(f'could not re-encode image: {exc}') from exc

    mime2 = validate_image(reenc)  # JPEG now; still enforces dims>=MIN_DIMENSION
    if has_ffprobe:
        dims2 = ffmpeg_image_dims(reenc)
        if not (dims2 and dims2[0] > 0 and dims2[1] > 0):
            raise InvalidCoverArt('re-encoded image still not ffmpeg-readable')
    return reenc, mime2, True


def verify_written(dest: Path, has_ffprobe: bool) -> bool:
    """Post-write read-back: confirm the saved file is a real, sized image."""
    if has_ffprobe:
        dims = attached_pic_dims(dest)
        return bool(dims and dims[0] > 0 and dims[1] > 0)
    try:
        with Image.open(dest) as im:
            im.load()
            return im.size[0] > 0 and im.size[1] > 0
    except Exception:
        return False


def write_folder_image(album: Path, data: bytes, mime: str, has_ffprobe: bool) -> Path:
    """Exclusive-create folder.<ext>, restore any toggled dir attr, verify, return path.

    Raises _Skip if a folder image already exists, InvalidCoverArt on a bad write.
    """
    ext = 'png' if (mime == 'image/png' or detect_image_mime(data) == 'image/png') else 'jpg'
    dest = album / f'folder.{ext}'
    restore = None
    try:
        try:
            fh = open(dest, 'xb')
        except FileExistsError:
            raise _Skip(f'{dest.name} already exists')
        except PermissionError:
            orig_mode = os.stat(album).st_mode
            os.chmod(album, orig_mode | stat.S_IWRITE)
            restore = (album, orig_mode)
            fh = open(dest, 'xb')  # may still raise FileExistsError -> propagates as skip below
        with fh:
            fh.write(data)
    except FileExistsError:
        raise _Skip(f'{dest.name} already exists')
    finally:
        if restore:
            try:
                os.chmod(restore[0], restore[1])
            except OSError:
                pass

    if not verify_written(dest, has_ffprobe):
        try:
            dest.unlink()
        except OSError:
            pass
        raise InvalidCoverArt('post-write verification failed (file removed)')
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('library', help='music library root (e.g. /path/to/Music or //SERVER/Music)')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--scan-only', action='store_true', help='list missing albums only')
    mode.add_argument('--dry-run', action='store_true', help='validate, write nothing (default)')
    mode.add_argument('--execute', action='store_true', help='write the folder image where missing')
    ap.add_argument('--log', default=str(Path(__file__).resolve().parent.parent / 'outputs' / 'folderjpg_created.log'))
    args = ap.parse_args()

    root = Path(args.library.replace('\\', '/'))
    if not root.is_dir():
        print(f'ERROR: library not found: {root}')
        sys.exit(2)

    print(f'Scanning {root} ...', flush=True)
    missing = find_missing_albums(root)
    print(f'Albums missing a folder image: {len(missing)}')

    if args.scan_only:
        for p, _ in missing[:50]:
            print('  ', p.relative_to(root))
        if len(missing) > 50:
            print(f'   ... and {len(missing) - 50} more')
        return

    has_ffprobe = ffprobe_available()
    if not has_ffprobe:
        print('NOTE: ffprobe/static-ffmpeg unavailable -> using Pillow decode check '
              '(consumer-parity unverified).')

    do_write = args.execute
    written = reencoded = skipped = failed = 0
    failures = []

    log_fh = None
    if do_write:
        Path(args.log).parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(args.log, 'a', encoding='utf-8')

    try:
        for i, (album, audio) in enumerate(missing, 1):
            try:
                if has_folder_image(album):  # appeared since the scan
                    skipped += 1
                    continue
                raw = first_embedded_art(audio)
                if not raw:
                    raise InvalidCoverArt('no embedded art on any track')
                data, mime, was_reenc = prepare_image(raw, has_ffprobe)
                if was_reenc:
                    reencoded += 1
                if do_write:
                    dest = write_folder_image(album, data, mime, has_ffprobe)
                    written += 1
                    log_fh.write(str(dest) + '\n')
                    log_fh.flush()
                else:
                    written += 1  # would-write (dry-run)
            except _Skip:
                skipped += 1
            except InvalidCoverArt as exc:
                failed += 1
                failures.append(f'{album.relative_to(root)} :: {exc}')
            except Exception as exc:  # never let one album abort the batch
                failed += 1
                failures.append(f'{album.relative_to(root)} :: unexpected: {exc}')
            if i % 50 == 0:
                print(f'  [{i}/{len(missing)}] {"written" if do_write else "validated"}={written} '
                      f'reencoded={reencoded} skipped={skipped} failed={failed}', flush=True)
    finally:
        if log_fh:
            log_fh.close()

    print('\n===== RESULT =====')
    verb = 'WROTE' if do_write else 'WOULD WRITE (dry-run)'
    print(f'{verb}: {written}  | re-encoded: {reencoded}  | skipped: {skipped}  | failed: {failed}')
    if failures:
        print(f'\n--- failures ({len(failures)}) ---')
        for f in failures[:40]:
            print('  ', f)
        if len(failures) > 40:
            print(f'   ... and {len(failures) - 40} more')
    if do_write and written:
        print(f'\ncreated paths logged to: {args.log}')


if __name__ == '__main__':
    main()
