import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'boot.settings')
import django
django.setup()
from django.template import Template, TemplateSyntaxError

try:
    with open('templates/birthboard/birthboard_confirm.html') as f:
        t = Template(f.read())
    print('✓ 模板语法正确！')
except TemplateSyntaxError as e:
    print(f'✗ 模板语法错误：{e}')
