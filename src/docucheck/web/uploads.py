"""Decode bounded uploads once; evidence coordinates use the normalized image."""

import hashlib
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError


def normalize_upload(path, max_pixels):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"} or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP một khung hình.")
                width, height = image.size
                if width * height > max_pixels:
                    raise ValueError("Ảnh vượt giới hạn số pixel.")
                orientation = image.getexif().get(274, 1)
                corrected = ImageOps.exif_transpose(image).convert("RGB")
                corrected.save(path.with_name("image.png"), format="PNG")
                result = {"width":corrected.width, "height":corrected.height,
                          "original_sha256":digest, "original_size":[width,height],
                          "exif_orientation":orientation, "transform":"EXIF transpose then RGB; no resize",
                          "evidence_coordinates":"normalized image pixel space"}
                corrected.close()
        return result
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("Ảnh không hợp lệ hoặc quá lớn.") from error
