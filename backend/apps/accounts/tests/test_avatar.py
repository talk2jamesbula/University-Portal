import os
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.core.testing import make_staff

User = get_user_model()
MEDIA = tempfile.mkdtemp()


def image_file(fmt="JPEG", size=(800, 600), name="photo.jpg", mode="RGB", exif=None):
    buf = BytesIO()
    img = Image.new(mode, size, "red" if mode == "RGB" else (255, 0, 0, 128))
    img.save(buf, fmt, **({"exif": exif} if exif else {}))
    return SimpleUploadedFile(name, buf.getvalue(), content_type="application/octet-stream")


@override_settings(MEDIA_ROOT=MEDIA)
class AvatarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("stu", password="x", role=User.Role.STUDENT, first_name="Ada")
        cls.prof = make_staff("prof", roles=["lecturer"])

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def upload(self, file):
        return self.client.post("/api/auth/me/avatar/", {"avatar": file}, format="multipart")

    def test_upload_is_cropped_resized_and_stripped(self):
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"  # Make
        res = self.upload(image_file(size=(1200, 800), exif=exif.tobytes()))
        self.assertEqual(res.status_code, 200, res.data)
        url = res.data["avatar_url"]
        self.assertTrue(url.startswith("/media/avatars/") and url.endswith(".jpg"))

        self.user.refresh_from_db()
        with Image.open(self.user.avatar.path) as saved:
            self.assertEqual((saved.format, saved.size), ("JPEG", (256, 256)))
            self.assertEqual(len(saved.getexif()), 0)

        # Publicly served, and shown in /auth/me/.
        self.assertEqual(self.client.get("/api/auth/me/").data["avatar_url"], url)
        res = APIClient().get(url)
        self.assertEqual(res.status_code, 200)
        res.close()

    def test_png_with_transparency_and_webp(self):
        self.assertEqual(self.upload(image_file("PNG", mode="RGBA", name="a.png")).status_code, 200)
        self.assertEqual(self.upload(image_file("WEBP", name="a.webp")).status_code, 200)

    def test_rejects_bad_files(self):
        self.assertIn("valid image", str(self.upload(SimpleUploadedFile("x.jpg", b"not an image")).data))
        self.assertIn("JPG, PNG or WebP", str(self.upload(image_file("GIF", name="x.gif")).data))
        big = SimpleUploadedFile("big.jpg", b"0" * (5 * 1024 * 1024 + 1))
        self.assertIn("too large", str(self.upload(big).data))
        self.assertEqual(self.client.post("/api/auth/me/avatar/", {}, format="multipart").status_code, 400)

    def test_replace_and_remove_delete_old_files(self):
        self.upload(image_file())
        self.user.refresh_from_db()
        first = self.user.avatar.path
        self.upload(image_file())
        self.user.refresh_from_db()
        self.assertFalse(os.path.exists(first))
        second = self.user.avatar.path

        res = self.client.delete("/api/auth/me/avatar/")
        self.assertIsNone(res.data["avatar_url"])
        self.assertFalse(os.path.exists(second))

    def test_photo_shown_in_directory(self):
        prof_client = APIClient()
        prof_client.force_authenticate(self.prof)
        prof_client.post("/api/auth/me/avatar/", {"avatar": image_file()}, format="multipart")
        rows = self.client.get("/api/directory/").data["results"]
        self.assertTrue(rows[0]["avatar_url"].startswith("/media/avatars/"))

    def test_payment_proofs_are_not_publicly_served(self):
        self.assertEqual(APIClient().get("/media/payment_proofs/2026/09/x.pdf").status_code, 404)

    def test_requires_login(self):
        self.assertEqual(
            APIClient().post("/api/auth/me/avatar/", {"avatar": image_file()}, format="multipart").status_code, 401
        )
