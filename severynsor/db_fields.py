import base64
import hashlib
from django.conf import settings
from django.db import models
from cryptography.fernet import Fernet

class EncryptedCharField(models.CharField):
    description = "A field that encrypts data before saving to the database"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        key = getattr(settings, 'FIELD_ENCRYPTION_KEY', settings.SECRET_KEY)
        # Fernet needs 32 bytes base64 encoded. We derive it from the key.
        h = hashlib.sha256(key.encode()).digest()
        self.fernet = Fernet(base64.urlsafe_b64encode(h))

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except Exception:
            # If decryption fails, return the value as is (useful during migration or if already decrypted)
            return value

    def to_python(self, value):
        # to_python is used for both DB and forms. 
        # But Django 2.0+ uses from_db_value for DB.
        return value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        
        # Check if it's already encrypted (optional, but safer for re-saving)
        # However, Fernet doesn't have an easy "is_encrypted" check without trying to decrypt.
        # But we only want to encrypt when saving to DB.
        return self.fernet.encrypt(value.encode()).decode()

    def get_internal_type(self):
        return "CharField"
