from django.db import migrations
from django.contrib.auth.hashers import make_password

def create_default_admin(apps, schema_editor):
    User = apps.get_model('api', 'User')
    if not User.objects.filter(email='tafita@gmail.com').exists():
        User.objects.create(
            nom='Ravelonarivo',
            prenom='Tafitasoa',
            email='tafita@gmail.com',
            phone='0340000000',
            role='admin',
            is_active=True,
            is_staff=True,
            is_superuser=True,
            password=make_password('12345678'),
            classe=None
        )

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_admin),
    ]
