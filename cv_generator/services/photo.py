"""The profile photo: from what the user uploads to the image that travels in each CV.

The photo is stored embedded in the profile as a base64 JPEG, not as a file. The
wizard thumbnails are HTML inside the browser, where a disk path is not visible, and
every history snapshot takes its own copy: changing the photo later does not alter a
CV that was already sent.
"""

import base64
import io

from PIL import Image, ImageOps, UnidentifiedImageError

from cv_generator.models.profile import MasterProfile, PersonalInfo

MAX_SIZE_BYTES = 10 * 1024 * 1024

# No ID photo justifies more than this, and decoding it already costs plenty of
# memory. It is checked before loading the pixels, by reading only the header.
MAX_PIXELS = 40_000_000

# Pillow reports as MPO a JPEG that carries an MPF block with more images inside: that is
# how iPhones and HDR Androids save photos (the gain map is the second image), and many
# cameras too. To the user it is a JPG, and Pillow decodes the first one.
ACCEPTED_FORMATS = ("JPEG", "MPO", "PNG")

# 3:4 portrait. At 450 px wide, the photo printed at about 38 mm comes close to 300 dpi,
# and the JPEG is around 40 KB: every history snapshot carries its own copy.
PHOTO_WIDTH = 450
PHOTO_HEIGHT = 600
JPEG_QUALITY = 85

# When cropping a tall portrait, the face is usually in the upper half: centering it
# fully on the vertical axis cuts the forehead before the chest.
CENTERED = (0.5, 0.4)

PREFIX = "data:image/jpeg;base64,"


def _to_rgb(image: Image.Image) -> Image.Image:
    """Flattens transparency onto white: JPEG has no alpha channel."""
    if image.mode == "RGB":
        return image
    with_alpha = image.convert("RGBA")
    background = Image.new("RGB", with_alpha.size, "white")
    background.paste(with_alpha, mask=with_alpha.getchannel("A"))
    return background


def _final_size(width: int, height: int) -> tuple[int, int]:
    """The largest 3:4 that fits in the image, without going over the final size.

    A small photo is cropped but not enlarged: enlarging it adds no detail.
    """
    crop_width = min(width, height * 3 // 4)
    return min(PHOTO_WIDTH, crop_width), min(PHOTO_HEIGHT, crop_width * 4 // 3)


def process_photo(data: bytes) -> str:
    """Turns what the user uploaded into the profile photo.

    It straightens it using the orientation the phone recorded, crops it to 3:4,
    downscales it and re-encodes it as JPEG. Re-encoding drops the EXIF metadata, which
    can carry the GPS location where it was taken, and the image comment: the CV is
    sent to third parties.

    Raises:
        ValueError: if it is not a readable JPG or PNG, or weighs more than 10 MB.
    """
    if len(data) > MAX_SIZE_BYTES:
        raise ValueError("The photo is larger than 10 MB. Upload a lighter version.")

    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ACCEPTED_FORMATS:
                raise ValueError("The photo has to be a JPG or PNG.")
            if image.width * image.height > MAX_PIXELS:
                raise ValueError("The photo has too many pixels. Upload a smaller version.")

            right = _to_rgb(ImageOps.exif_transpose(image))
            cropped = ImageOps.fit(
                right,
                _final_size(*right.size),
                method=Image.Resampling.LANCZOS,
                centering=CENTERED,
            )
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as error:
        raise ValueError("The photo could not be read. It has to be a JPG or PNG.") from error

    # Pillow's JPEG writer copies the image comment (`info["comment"]`, from a JPEG's COM
    # or a PNG's `comment` text), and the crop inherits it. The whole `info` is cleared, not
    # just the comment: today EXIF and XMP do not get through because the writer only takes
    # them when they are passed in, but if another Pillow version copied another field, it
    # would not reach the CV either.
    cropped.info = {}
    output = io.BytesIO()
    cropped.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return PREFIX + base64.b64encode(output.getvalue()).decode("ascii")


def set_photo(profile: MasterProfile, photo: str | None) -> MasterProfile:
    """Returns the profile with another photo, or with no photo if it receives None.

    It validates the value against the model: `model_copy(update=...)` would not, and the
    photo ends up in the template's `src`.

    Raises:
        ValueError: if the photo is not an embedded JPEG.
    """
    personal = PersonalInfo.model_validate({**profile.personal.model_dump(), "photo": photo})
    return profile.model_copy(update={"personal": personal}, deep=True)
