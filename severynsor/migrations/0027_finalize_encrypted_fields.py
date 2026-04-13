from django.db import migrations
import severynsor.db_fields

class Migration(migrations.Migration):

    dependencies = [
        ('severynsor', '0026_encrypt_existing_keys'),
    ]

    operations = [
        # 1. Remove the old (unencrypted) fields
        migrations.RemoveField(
            model_name='rtspretriever',
            name='rtsp_url',
        ),
        migrations.RemoveField(
            model_name='openweathermapretriever',
            name='api_key',
        ),
        # 2. Rename the new (encrypted) fields to the old names
        migrations.RenameField(
            model_name='rtspretriever',
            old_name='rtsp_url_new',
            new_name='rtsp_url',
        ),
        migrations.RenameField(
            model_name='openweathermapretriever',
            old_name='api_key_new',
            new_name='api_key',
        ),
        # 3. Alter the fields to use EncryptedCharField
        migrations.AlterField(
            model_name='rtspretriever',
            name='rtsp_url',
            field=severynsor.db_fields.EncryptedCharField(max_length=512, default=''),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='openweathermapretriever',
            name='api_key',
            field=severynsor.db_fields.EncryptedCharField(max_length=512, default=''),
            preserve_default=False,
        ),
    ]
