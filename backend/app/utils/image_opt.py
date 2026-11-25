"""图片上传压缩与 EXIF 清理工具（Pillow 不可用时优雅降级为原始字节）。"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def optimize_image_bytes(
    raw: bytes,
    *,
    max_dim: int = 1200,
    quality: int = 82,
    preferred_ext: str = "jpg",
) -> tuple[bytes, str]:
    """校验、等比缩放、剥离 EXIF 并压缩图片；无法处理时回退原字节。"""
    ext = (preferred_ext or "jpg").lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    if not raw or ext == "gif":
        return raw, ext

    try:
        from PIL import Image, ImageOps
    except ImportError:
        return raw, ext

    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            if max_dim > 0 and max(w, h) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            if ext == "png" and img.mode in ("RGBA", "LA", "P"):
                img.save(buf, format="PNG", optimize=True)
                out_ext = "png"
            elif ext == "webp":
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                img.save(buf, format="WEBP", quality=quality, method=4)
                out_ext = "webp"
            else:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                out_ext = "jpg"

            optimized = buf.getvalue()
            if optimized and len(optimized) <= len(raw) or max(w, h) > max_dim:
                return optimized, out_ext
            return raw, ext
    except Exception:
        logger.debug("image optimization skipped; returning original bytes", exc_info=True)
        return raw, ext
