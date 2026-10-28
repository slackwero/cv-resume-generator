"""The profile photo: from what the user uploads to the image that travels in each CV."""

import base64
import io

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from cv_generator.models.profile import MasterProfile
from cv_generator.services.photo import MAX_SIZE_BYTES, PHOTO_HEIGHT, PHOTO_WIDTH, process_photo, set_photo
from tests.test_models_personal import REQUIRED

PREFIX = "data:image/jpeg;base64,"
ORIENTATION = 0x0112
VENDOR = 0x010F


def _image(width: int, height: int, fmt: str = "JPEG", mode: str = "RGB", exif: Image.Exif | None = None) -> bytes:
    output = io.BytesIO()
    image = Image.new(mode, (width, height), "teal")
    if exif is not None:
        image.save(output, format=fmt, exif=exif)
    else:
        image.save(output, format=fmt)
    return output.getvalue()


def sample_photo() -> str:
    """An already processed photo, for the tests that only need it to exist."""
    return process_photo(_image(600, 800))


def _decode(photo: str) -> Image.Image:
    assert photo.startswith(PREFIX)
    return Image.open(io.BytesIO(base64.b64decode(photo.removeprefix(PREFIX))))


@pytest.mark.parametrize(("width", "height"), [(1000, 1000), (3000, 2000), (900, 2000)])
def test_crops_to_three_by_four_and_downscales(width: int, height: int) -> None:
    photo = _decode(process_photo(_image(width, height)))

    assert photo.format == "JPEG"
    assert photo.size == (PHOTO_WIDTH, PHOTO_HEIGHT)


def test_does_not_enlarge_a_small_photo() -> None:
    """Enlarging it adds no detail: it only pixelates it and makes it heavier."""
    photo = _decode(process_photo(_image(240, 400)))

    assert photo.size == (240, 320)


def test_straightens_the_photo_using_the_phone_orientation() -> None:
    """A phone saves the photo lying down and records in EXIF how to rotate it.

    Without applying that orientation, a 300x400 portrait arrives as 400x300 and the 3:4
    crop cuts half the face.
    """
    exif = Image.Exif()
    exif[ORIENTATION] = 6  # rotate 90 degrees to see it upright

    photo = _decode(process_photo(_image(400, 300, exif=exif)))

    assert photo.size == (300, 400)


def test_removes_exif_metadata() -> None:
    """EXIF can carry the GPS location where the photo was taken, and the CV is sent to third parties."""
    exif = Image.Exif()
    exif[VENDOR] = "Test camera"

    data = base64.b64decode(process_photo(_image(600, 800, exif=exif)).removeprefix(PREFIX))

    assert not Image.open(io.BytesIO(data)).getexif()
    assert b"Test camera" not in data


def test_accepts_a_phone_jpg_with_several_images() -> None:
    """An iPhone or an Android with HDR saves the photo as a JPEG with an MPF block, and Pillow
    reports it as MPO: rejecting it meant rejecting the phone photos uploaded most."""
    output = io.BytesIO()
    main = Image.new("RGB", (900, 1200), "teal")
    main.save(output, format="MPO", save_all=True, append_images=[Image.new("RGB", (300, 400), "white")])

    photo = _decode(process_photo(output.getvalue()))

    assert photo.format == "JPEG"
    assert photo.size == (PHOTO_WIDTH, PHOTO_HEIGHT)


def _with_comment(fmt: str, comment: str) -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (600, 800), "teal")
    if fmt == "PNG":
        texts = PngInfo()
        texts.add_text("comment", comment)
        image.save(output, format="PNG", pnginfo=texts)
    else:
        image.save(output, format="JPEG", comment=comment.encode())
    return output.getvalue()


@pytest.mark.parametrize("fmt", ["JPEG", "PNG"])
def test_removes_the_photo_comment(fmt: str) -> None:
    """Pillow copies the input image's comment into the output JPEG (a JPEG's COM, a PNG's
    `comment` text), and the CV is sent to third parties: a location the EXIF no longer
    carries may come in there."""
    data = base64.b64decode(process_photo(_with_comment(fmt, "lat -33.44 lon -70.65")).removeprefix(PREFIX))

    assert b"lat -33.44 lon -70.65" not in data


def test_accepts_png_with_transparency() -> None:
    photo = _decode(process_photo(_image(600, 800, fmt="PNG", mode="RGBA")))

    assert photo.mode == "RGB"


def test_rejects_what_is_not_an_image() -> None:
    with pytest.raises(ValueError, match="JPG or PNG"):
        process_photo(b"%PDF-1.7 this is not a photo")


def test_rejects_formats_other_than_jpg_and_png() -> None:
    with pytest.raises(ValueError, match="JPG or PNG"):
        process_photo(_image(600, 800, fmt="GIF", mode="P"))


def test_rejects_a_too_large_file_without_opening_it() -> None:
    with pytest.raises(ValueError, match="10 MB"):
        process_photo(b"\0" * (MAX_SIZE_BYTES + 1))


def test_set_photo_does_not_touch_the_given_profile() -> None:
    profile = MasterProfile(personal=REQUIRED)
    photo = process_photo(_image(600, 800))

    updated = set_photo(profile, photo)

    assert updated.personal.photo == photo
    assert profile.personal.photo is None


def test_setting_photo_to_none_removes_it() -> None:
    profile = set_photo(MasterProfile(personal=REQUIRED), process_photo(_image(600, 800)))

    assert set_photo(profile, None).personal.photo is None


def test_set_photo_validates_its_input() -> None:
    """`model_copy(update=...)` does not validate: without this, any text would reach the template's src."""
    with pytest.raises(ValueError, match="photo"):
        set_photo(MasterProfile(personal=REQUIRED), "file:///etc/passwd")
