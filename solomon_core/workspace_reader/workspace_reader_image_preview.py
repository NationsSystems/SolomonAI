# -------------------------------------------------------------------
# FILE: workspace_reader_image_preview.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# Server-owned image preview metadata helpers for Solomon Documents.
# -------------------------------------------------------------------

from io import BytesIO
from pathlib import Path
from struct import unpack
from typing import Dict, Optional, Tuple
from urllib.parse import quote

from solomon_core.logger import get_logger

logger = get_logger("workspace_reader.image_preview")

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
GIF_87A_SIGNATURE = b"GIF87a"
GIF_89A_SIGNATURE = b"GIF89a"
BMP_SIGNATURE = b"BM"
RIFF_SIGNATURE = b"RIFF"
WEBP_SIGNATURE = b"WEBP"
TIFF_LITTLE_ENDIAN_SIGNATURE = b"II*\x00"
TIFF_BIG_ENDIAN_SIGNATURE = b"MM\x00*"
BIG_TIFF_LITTLE_ENDIAN_SIGNATURE = b"II+\x00"
BIG_TIFF_BIG_ENDIAN_SIGNATURE = b"MM\x00+"

TIFF_EXTENSIONS = {".tif", ".tiff"}
TIFF_PREVIEW_MIME_TYPE = "image/png"
TIFF_SOURCE_MIME_TYPE = "image/tiff"
MAX_TIFF_PREVIEW_EDGE = 2400

IMAGE_MIME_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


def get_image_mime_type(source_path: str) -> Optional[str]:
    """Return a browser-readable image MIME type after extension and header checks."""

    path = Path(str(source_path or ""))
    extension = path.suffix.lower().strip()

    if extension not in IMAGE_MIME_BY_EXTENSION:
        return None

    try:
        with path.open("rb") as image_file:
            header = image_file.read(32)
    except OSError:
        return None

    if extension == ".png" and header.startswith(PNG_SIGNATURE):
        return "image/png"

    if extension in {".jpg", ".jpeg"} and header.startswith(JPEG_SIGNATURE):
        return "image/jpeg"

    if extension == ".gif" and (
        header.startswith(GIF_87A_SIGNATURE) or header.startswith(GIF_89A_SIGNATURE)
    ):
        return "image/gif"

    if extension == ".bmp" and header.startswith(BMP_SIGNATURE):
        return "image/bmp"

    if (
        extension == ".webp"
        and len(header) >= 12
        and header.startswith(RIFF_SIGNATURE)
        and header[8:12] == WEBP_SIGNATURE
    ):
        return "image/webp"

    return None


def get_tiff_mime_type(source_path: str) -> Optional[str]:
    """Return TIFF source MIME type after extension and header checks."""

    path = Path(str(source_path or ""))
    extension = path.suffix.lower().strip()

    if extension not in TIFF_EXTENSIONS:
        return None

    try:
        with path.open("rb") as image_file:
            header = image_file.read(4)
    except OSError:
        return None

    if header in {
        TIFF_LITTLE_ENDIAN_SIGNATURE,
        TIFF_BIG_ENDIAN_SIGNATURE,
        BIG_TIFF_LITTLE_ENDIAN_SIGNATURE,
        BIG_TIFF_BIG_ENDIAN_SIGNATURE,
    }:
        return TIFF_SOURCE_MIME_TYPE

    return None


def is_tiff_preview_source(source_path: str) -> bool:
    """Return whether the source is a supported TIFF preview candidate."""

    return get_tiff_mime_type(source_path) == TIFF_SOURCE_MIME_TYPE


def get_png_dimensions(source_path: str) -> Optional[Tuple[int, int]]:
    """Return PNG image dimensions when available."""

    try:
        with Path(source_path).open("rb") as image_file:
            header = image_file.read(24)
    except OSError:
        return None

    if len(header) < 24 or not header.startswith(PNG_SIGNATURE):
        return None

    try:
        width, height = unpack(">II", header[16:24])
    except Exception:
        return None

    if width > 0 and height > 0:
        return width, height

    return None


def get_jpeg_dimensions(source_path: str) -> Optional[Tuple[int, int]]:
    """Return JPEG image dimensions from SOF markers when available."""

    try:
        with Path(source_path).open("rb") as image_file:
            if image_file.read(2) != b"\xff\xd8":
                return None

            while True:
                marker_prefix = image_file.read(1)

                if not marker_prefix:
                    return None

                while marker_prefix != b"\xff":
                    marker_prefix = image_file.read(1)

                    if not marker_prefix:
                        return None

                marker = image_file.read(1)

                while marker == b"\xff":
                    marker = image_file.read(1)

                if not marker:
                    return None

                marker_code = marker[0]

                if marker_code in {0xD8, 0xD9}:
                    continue

                segment_length_data = image_file.read(2)

                if len(segment_length_data) != 2:
                    return None

                segment_length = unpack(">H", segment_length_data)[0]

                if segment_length < 2:
                    return None

                if marker_code in {
                    0xC0,
                    0xC1,
                    0xC2,
                    0xC3,
                    0xC5,
                    0xC6,
                    0xC7,
                    0xC9,
                    0xCA,
                    0xCB,
                    0xCD,
                    0xCE,
                    0xCF,
                }:
                    frame_data = image_file.read(5)

                    if len(frame_data) != 5:
                        return None

                    height = unpack(">H", frame_data[1:3])[0]
                    width = unpack(">H", frame_data[3:5])[0]

                    if width > 0 and height > 0:
                        return width, height

                    return None

                image_file.seek(segment_length - 2, 1)
    except OSError:
        return None


def get_gif_dimensions(source_path: str) -> Optional[Tuple[int, int]]:
    """Return GIF image dimensions when available."""

    try:
        with Path(source_path).open("rb") as image_file:
            header = image_file.read(10)
    except OSError:
        return None

    if len(header) < 10 or not (
        header.startswith(GIF_87A_SIGNATURE) or header.startswith(GIF_89A_SIGNATURE)
    ):
        return None

    try:
        width, height = unpack("<HH", header[6:10])
    except Exception:
        return None

    if width > 0 and height > 0:
        return width, height

    return None


def get_bmp_dimensions(source_path: str) -> Optional[Tuple[int, int]]:
    """Return BMP image dimensions when available."""

    try:
        with Path(source_path).open("rb") as image_file:
            header = image_file.read(26)
    except OSError:
        return None

    if len(header) < 26 or not header.startswith(BMP_SIGNATURE):
        return None

    try:
        dib_header_size = unpack("<I", header[14:18])[0]

        if dib_header_size == 12:
            if len(header) < 26:
                return None

            width, height = unpack("<HH", header[18:22])
        else:
            if len(header) < 26:
                return None

            width, height = unpack("<ii", header[18:26])
    except Exception:
        return None

    width = abs(int(width or 0))
    height = abs(int(height or 0))

    if width > 0 and height > 0:
        return width, height

    return None


def get_webp_dimensions(source_path: str) -> Optional[Tuple[int, int]]:
    """Return WEBP image dimensions for VP8, VP8L, or VP8X containers."""

    try:
        with Path(source_path).open("rb") as image_file:
            header = image_file.read(64)
    except OSError:
        return None

    if len(header) < 30 or not (
        header.startswith(RIFF_SIGNATURE) and header[8:12] == WEBP_SIGNATURE
    ):
        return None

    chunk_type = header[12:16]

    try:
        if chunk_type == b"VP8 ":
            if len(header) < 30 or header[23:26] != b"\x9d\x01\x2a":
                return None

            width = unpack("<H", header[26:28])[0] & 0x3FFF
            height = unpack("<H", header[28:30])[0] & 0x3FFF

        elif chunk_type == b"VP8L":
            if len(header) < 25 or header[20] != 0x2F:
                return None

            bits = int.from_bytes(header[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1

        elif chunk_type == b"VP8X":
            if len(header) < 30:
                return None

            width = int.from_bytes(header[24:27], "little") + 1
            height = int.from_bytes(header[27:30], "little") + 1

        else:
            return None
    except Exception:
        return None

    if width > 0 and height > 0:
        return width, height

    return None


def get_tiff_dimensions(source_path: str) -> Optional[Tuple[int, int]]:
    """Return TIFF image dimensions when Pillow can read the source."""

    if not is_tiff_preview_source(source_path):
        return None

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("TIFF preview requires the Pillow package.") from exc

    try:
        with Image.open(source_path) as image:
            width, height = image.size
    except Exception:
        return None

    if width > 0 and height > 0:
        return int(width), int(height)

    return None


def get_image_dimensions(source_path: str, mime_type: str) -> Optional[Tuple[int, int]]:
    """Return image dimensions for supported image formats."""

    if mime_type == "image/png":
        return get_png_dimensions(source_path)

    if mime_type == "image/jpeg":
        return get_jpeg_dimensions(source_path)

    if mime_type == "image/gif":
        return get_gif_dimensions(source_path)

    if mime_type == "image/bmp":
        return get_bmp_dimensions(source_path)

    if mime_type == "image/webp":
        return get_webp_dimensions(source_path)

    if mime_type == TIFF_SOURCE_MIME_TYPE:
        return get_tiff_dimensions(source_path)

    return None


def get_orientation_label(width: Optional[int], height: Optional[int]) -> str:
    """Return a simple image orientation label."""

    if not width or not height:
        return "Unknown"

    if width == height:
        return "Square"

    return "Landscape" if width > height else "Portrait"


def _get_pillow_resample_filter():
    """Return a stable Pillow resampling filter across supported versions."""

    try:
        from PIL import Image

        return Image.Resampling.LANCZOS
    except Exception:
        try:
            from PIL import Image

            return Image.LANCZOS
        except Exception:
            return None


def _normalize_pillow_image_for_png(image):
    """Return a Pillow image mode that can be safely written as PNG."""

    if image.mode in {"RGB", "RGBA"}:
        return image.copy()

    if image.mode in {"1", "L", "P"}:
        return image.convert("RGBA")

    return image.convert("RGB")


def render_tiff_preview_png(source_path: str) -> BytesIO:
    """Render the first TIFF frame/page as a bounded PNG preview."""

    if not is_tiff_preview_source(source_path):
        raise ValueError("Unsupported or invalid TIFF preview file.")

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("TIFF preview requires the Pillow package.") from exc

    output_stream = BytesIO()

    with Image.open(source_path) as source_image:
        try:
            source_image.seek(0)
        except EOFError:
            pass

        preview_image = ImageOps.exif_transpose(source_image)
        preview_image = _normalize_pillow_image_for_png(preview_image)
        resample_filter = _get_pillow_resample_filter()

        if max(preview_image.size or (0, 0)) > MAX_TIFF_PREVIEW_EDGE:
            preview_image.thumbnail(
                (MAX_TIFF_PREVIEW_EDGE, MAX_TIFF_PREVIEW_EDGE),
                resample_filter,
            )

        preview_image.save(output_stream, format="PNG", optimize=True)

    output_stream.seek(0)
    return output_stream


def build_image_preview(
    source_path: str,
    *,
    document_id: str,
    display_name: str,
    request_id: str = "untracked",
) -> Dict:
    """Build safe server-owned image preview metadata."""

    clean_document_id = str(document_id or "").strip()
    clean_display_name = Path(str(display_name or "")).name.strip() or "Image File"
    path = Path(str(source_path or ""))
    mime_type = get_image_mime_type(str(path))
    is_tiff_preview = False

    if not mime_type:
        mime_type = get_tiff_mime_type(str(path))
        is_tiff_preview = mime_type == TIFF_SOURCE_MIME_TYPE

    if not clean_document_id:
        raise ValueError("Missing document id for image preview.")

    if not path.is_file():
        raise FileNotFoundError("Image preview source file was not found.")

    if not mime_type:
        raise ValueError("Unsupported or invalid image preview file.")

    dimensions = get_image_dimensions(str(path), mime_type)
    width = dimensions[0] if dimensions else None
    height = dimensions[1] if dimensions else None
    encoded_document_id = quote(clean_document_id, safe="")
    image_url = f"/workspace/document/{encoded_document_id}/reader/image"

    if is_tiff_preview:
        image_url = f"/workspace/document/{encoded_document_id}/reader/image/preview.png"

    logger.info(
        "[workspace.reader.image_preview_ready] request_id=%s document_id=%s "
        "filename=%s mime_type=%s preview_mime_type=%s width=%s height=%s "
        "converted_preview=%s",
        request_id,
        clean_document_id,
        clean_display_name,
        mime_type,
        TIFF_PREVIEW_MIME_TYPE if is_tiff_preview else mime_type,
        width,
        height,
        is_tiff_preview,
    )

    return {
        "title": clean_display_name,
        "mime_type": mime_type,
        "preview_mime_type": TIFF_PREVIEW_MIME_TYPE if is_tiff_preview else mime_type,
        "width": width,
        "height": height,
        "orientation": get_orientation_label(width, height),
        "image_url": image_url,
        "alt_text": f"Read-only preview of {clean_display_name}",
        "converted_preview": is_tiff_preview,
    }