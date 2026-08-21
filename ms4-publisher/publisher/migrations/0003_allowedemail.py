from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('publisher', '0002_coachsubscription_user_publicationlog_user_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AllowedEmail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('added_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='added_allowed_emails', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'allowed_email',
                'ordering': ['-created_at'],
            },
        ),
    ]
