from PIL import Image


def resize_to_fit(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Resize *img* preserving aspect ratio to fit within max_w x max_h.
    Guards against zero dimensions.
    """
    if max_w <= 0 or max_h <= 0 or img.width <= 0 or img.height <= 0:
        return img
    aspect = img.width / img.height
    new_w = max_w
    new_h = int(new_w / aspect)
    if new_h > max_h:
        new_h = max_h
        new_w = int(new_h * aspect)
    if new_w <= 0 or new_h <= 0:
        return img
    return img.resize((new_w, new_h), Image.LANCZOS)
