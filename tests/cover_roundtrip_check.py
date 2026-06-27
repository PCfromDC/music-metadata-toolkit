"""Standalone smoke check: embed a cover and confirm ffprobe sees real dims.

Prints a per-format line and a final PASS/FAIL. Exit code 0 on PASS.
Run: python tests/cover_roundtrip_check.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.synth import make_audio, make_image_bytes  # noqa: E402
from utilities.core import cover_art  # noqa: E402
from utilities.core.ffprobe import attached_pic_dims, ffprobe_available  # noqa: E402


def main() -> int:
    ok = True
    formats = [("t.mp3", "libmp3lame"), ("t.m4a", "aac"), ("t.flac", "flac")]
    with tempfile.TemporaryDirectory() as td:
        for name, codec in formats:
            path = Path(td) / name
            make_audio(path, codec)
            data = make_image_bytes("JPEG", size=(640, 640))
            try:
                cover_art.embed_in_file(path, data)
                dims = attached_pic_dims(path) if ffprobe_available() else None
                byte_match = cover_art.extract_cover_from_file(path) == data
                dims_ok = dims is None or (dims[0] > 0 and dims[1] > 0)
                passed = byte_match and dims_ok
                ok = ok and passed
                print(
                    f"{'PASS' if passed else 'FAIL'} {name}: "
                    f"ffprobe dims={dims}, byte-match={byte_match}"
                )
            except Exception as exc:  # noqa: BLE001
                ok = False
                print(f"FAIL {name}: {exc}")

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
