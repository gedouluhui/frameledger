import base64
import io
from PIL import Image


def thumbnail_data(image):
    picture=image.copy() if isinstance(image,Image.Image) else Image.fromarray(image)
    picture.thumbnail((480,270),Image.Resampling.LANCZOS)
    buffer=io.BytesIO();picture.save(buffer,format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('ascii')
