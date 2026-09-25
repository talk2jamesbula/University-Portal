"""Profile photo processing: validate, square-crop, resize and re-encode uploads."""

import uuid
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000  # refuse "decompression bomb" images before decoding them
SIZE = 256
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class AvatarError(ValueError):
    pass


def process_avatar(upload):
    """Return a ContentFile holding a 256×256 JPEG made from the uploaded image.

    Re-encoding discards all metadata, including EXIF GPS location from phone photos.
    """
    if upload.size > MAX_UPLOAD_BYTES:
        raise AvatarError("Image is too large. The maximum size is 5 MB.")
    try:
        image = Image.open(upload)
        if image.format not in ALLOWED_FORMATS:
            raise AvatarError("Upload a JPG, PNG or WebP image.")
        if image.width * image.height > MAX_PIXELS:
            raise AvatarError("Image dimensions are too large.")
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AvatarError("That file isn't a valid image.") from exc

    image = ImageOps.exif_transpose(image)  # respect the camera's rotation flag
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")
    image = ImageOps.fit(image, (SIZE, SIZE), Image.LANCZOS, centering=(0.5, 0.4))

    out = BytesIO()
    image.save(out, "JPEG", quality=85, optimize=True)
    # A new name on every change also busts browser caches.
    return ContentFile(out.getvalue(), name=f"{uuid.uuid4().hex}.jpg")
