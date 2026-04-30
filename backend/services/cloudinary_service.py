"""Cloudinary image upload service for profile pictures.

Uses Cloudinary's Python SDK to upload images with automatic optimization,
face-detection cropping, and CDN delivery.

Env vars required:
  CLOUDINARY_CLOUD_NAME
  CLOUDINARY_API_KEY
  CLOUDINARY_API_SECRET
"""

import io
from typing import Optional, Tuple

import structlog

from config import get_settings

logger = structlog.get_logger()

# Max file size: 2MB
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def _init_cloudinary():
    """Lazily configure Cloudinary SDK once."""
    import cloudinary  # type: ignore
    settings = get_settings()
    if not cloudinary.config().cloud_name:
        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=True,
        )
    return cloudinary


def is_cloudinary_configured() -> bool:
    """Check if Cloudinary credentials are set."""
    settings = get_settings()
    return bool(
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    )


def validate_image(
    content: bytes,
    content_type: str,
) -> Tuple[bool, str]:
    """Validate uploaded image. Returns (valid, error_message)."""
    if content_type.lower() not in ALLOWED_CONTENT_TYPES:
        return False, f"Unsupported image format. Use JPG, PNG, or WebP."
    
    if len(content) > MAX_FILE_SIZE_BYTES:
        size_mb = len(content) / (1024 * 1024)
        return False, f"File too large ({size_mb:.1f} MB). Max 2 MB."
    
    if len(content) < 100:
        return False, "File is too small to be a valid image."
    
    # Verify magic bytes match content-type
    magic = content[:12]
    is_jpeg = magic.startswith(b"\xff\xd8\xff")
    is_png = magic.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = magic[0:4] == b"RIFF" and magic[8:12] == b"WEBP"
    
    if not (is_jpeg or is_png or is_webp):
        return False, "File content doesn't match a valid image format."
    
    # Try to open with Pillow to verify it's a valid image
    try:
        from PIL import Image  # type: ignore
        img = Image.open(io.BytesIO(content))
        img.verify()
        # Re-open because verify() consumes the file
        img = Image.open(io.BytesIO(content))
        w, h = img.size
        if w < 100 or h < 100:
            return False, "Image dimensions too small. Minimum 100x100."
        if w > 4000 or h > 4000:
            return False, "Image dimensions too large. Maximum 4000x4000."
    except Exception as e:
        logger.warning("Image validation failed", error=str(e))
        return False, "Invalid or corrupted image file."
    
    return True, ""


def upload_profile_picture(
    content: bytes,
    email: str,
    old_public_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Upload profile picture to Cloudinary.
    
    Returns (url, public_id, error). On success, (url, public_id, None).
    On failure, (None, None, error_message).
    
    Deletes old_public_id if provided and upload succeeds.
    """
    if not is_cloudinary_configured():
        return None, None, "Image uploads are not configured. Please contact support."
    
    try:
        cloudinary = _init_cloudinary()
        import cloudinary.uploader  # type: ignore
        
        # Use email hash as stable public_id so overwrites work
        import hashlib
        email_hash = hashlib.md5(email.lower().encode()).hexdigest()[:16]
        public_id = f"ginie/profiles/{email_hash}"
        
        result = cloudinary.uploader.upload(
            io.BytesIO(content),
            public_id=public_id,
            overwrite=True,
            folder="ginie/profiles",
            resource_type="image",
            # Auto-crop to square, face detection, optimize
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
                {"quality": "auto:good"},
                {"fetch_format": "auto"},
            ],
            # Safe defaults
            allowed_formats=["jpg", "png", "webp"],
            max_file_size=MAX_FILE_SIZE_BYTES,
        )
        
        url = result.get("secure_url")
        new_public_id = result.get("public_id")
        
        if not url:
            return None, None, "Upload failed: no URL returned"
        
        logger.info("Profile picture uploaded", email=email, public_id=new_public_id)
        return url, new_public_id, None
    
    except Exception as e:
        logger.exception("Cloudinary upload failed", email=email, error=str(e))
        return None, None, f"Upload failed: {str(e)[:100]}"


def delete_profile_picture(public_id: str) -> bool:
    """Delete a profile picture from Cloudinary."""
    if not is_cloudinary_configured() or not public_id:
        return False
    try:
        cloudinary = _init_cloudinary()
        import cloudinary.uploader  # type: ignore
        cloudinary.uploader.destroy(public_id)
        return True
    except Exception as e:
        logger.warning("Failed to delete Cloudinary image", public_id=public_id, error=str(e))
        return False
