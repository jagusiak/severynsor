# Generated manually

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('severynsor', '0013_alter_imagerecord_options_alter_imagesensor_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='sensor',
            options={
                'permissions': [
                    ('can_view_token', 'Can view and edit sensor token'),
                    ('can_preview_sensor', 'Can preview sensor data'),
                ],
            },
        ),
    ]
