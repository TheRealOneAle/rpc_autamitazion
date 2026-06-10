#!/bin/sh
set -e

python manage.py makemigrations publisher --noinput
python manage.py migrate --noinput

python manage.py shell << 'PYEOF'
from publisher.models import SystemConfig
import os
SystemConfig.objects.update_or_create(key='ms1_url', defaults={'value': os.environ['MS1_URL']})
SystemConfig.objects.update_or_create(key='ms2_url', defaults={'value': os.environ['MS2_URL']})
print('URLs sincronizadas:', os.environ['MS1_URL'], '|', os.environ['MS2_URL'])
PYEOF

exec python manage.py runserver 0.0.0.0:8000
