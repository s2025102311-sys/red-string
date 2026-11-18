"""Profile picture storage on disk (kept out of the repositories: it is files, not SQL)."""
import os
import secrets

from werkzeug.utils import secure_filename

from .exceptions import ValidationError

DEFAULT_PICTURE = "default.jpg"


class ProfilePictureStore:
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

    def __init__(self, folder):
        self.folder = folder

    def save(self, file, user_id):
        """Validates and stores an upload. Returns the new filename or raises ValidationError."""
        original = secure_filename(file.filename)
        ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError("Profile picture must be a PNG or JPG image.")

        header = file.stream.read(8)          # check real bytes so a renamed file is rejected
        file.stream.seek(0)
        is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
        is_jpg = header.startswith(b"\xff\xd8\xff")
        if not (is_png or is_jpg):
            raise ValidationError("That file doesn't look like a real PNG or JPG image.")

        filename = f"user{user_id}_{secrets.token_hex(8)}.{'png' if is_png else 'jpg'}"
        os.makedirs(self.folder, exist_ok=True)
        file.save(os.path.join(self.folder, filename))
        return filename

    def delete(self, filename):
        if filename and filename != DEFAULT_PICTURE:
            path = os.path.join(self.folder, os.path.basename(filename))
            if os.path.exists(path):
                os.remove(path)

    def exists(self, filename):
        return bool(filename) and filename != DEFAULT_PICTURE \
            and os.path.exists(os.path.join(self.folder, filename))
