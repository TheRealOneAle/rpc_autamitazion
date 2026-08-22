from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('publisher', '0003_allowedemail'),
    ]

    operations = [
        migrations.CreateModel(
            name='FirstSolutionEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contest_key', models.CharField(max_length=50)),
                ('problem_letter', models.CharField(max_length=10)),
                ('problem_name', models.CharField(blank=True, default='', max_length=100)),
                ('problem_color', models.CharField(blank=True, default='#CF1F4A', max_length=20)),
                ('team_name', models.CharField(max_length=200)),
                ('university', models.CharField(blank=True, default='', max_length=200)),
                ('university_acronym', models.CharField(blank=True, default='', max_length=50)),
                ('country_code', models.CharField(blank=True, default='', max_length=10)),
                ('country_name', models.CharField(blank=True, default='', max_length=50)),
                ('time_minutes', models.IntegerField(default=0)),
                ('language', models.CharField(blank=True, default='', max_length=50)),
                ('published_at', models.DateTimeField(auto_now_add=True)),
                ('post_id', models.CharField(blank=True, max_length=100, null=True)),
                ('success', models.BooleanField(default=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='first_solution_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'first_solution_event',
                'ordering': ['time_minutes'],
                'unique_together': {('contest_key', 'problem_letter')},
            },
        ),
    ]
