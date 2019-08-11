from odoo.tools.image import ImageProcess as IP

import logging
from PIL import ExifTags

_logger = logging.getLogger(__name__)


class ImageProcess(IP):
    def image_base64(self, quality=0, output_format='', auto_rotate=True):
        "Return the base64 image, apply rotation based on exif data if present"
        image = self.image
        if not hasattr(image, 'getexif'):
            _logger.warning('Exif data not available, update to Pillow==6.0.0 or later. Automatic rotation detection will not be applied.')
            return super().image_base64(quality=quality, output_format=output_format)
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation]=='Orientation':
                break
        exif=dict(image.getexif().items())
        if exif.get(orientation):
            if exif[orientation] == 3:
                image=image.rotate(180, expand=True)
            elif exif[orientation] == 6:
                image=image.rotate(270, expand=True)
            elif exif[orientation] == 8:
                image=image.rotate(90, expand=True)
            self.image = image
        return super().image_base64(quality=quality, output_format=output_format)


def image_process(base64_source, size=(0, 0), verify_resolution=False, quality=0, crop=None, colorize=False, output_format=''):
    """Process the `base64_source` image by executing the given operations and
    return the result as a base64 encoded image.
    Copied from odoo.tools.image to include rotation (didn't want to monkeypatch)
    """
    if not base64_source or ((not size or (not size[0] and not size[1])) and not verify_resolution and not quality and not crop and not colorize and not output_format):
        # for performance: don't do anything if the image is falsy or if
        # no operations have been requested
        return base64_source

    image = ImageProcess(base64_source, verify_resolution)
    if size:
        if crop:
            center_x = 0.5
            center_y = 0.5
            if crop == 'top':
                center_y = 0
            elif crop == 'bottom':
                center_y = 1
            image.crop_resize(max_width=size[0], max_height=size[1], center_x=center_x, center_y=center_y)
        else:
            image.resize(max_width=size[0], max_height=size[1])
    if colorize:
        image.colorize()
    return image.image_base64(quality=quality, output_format=output_format)
