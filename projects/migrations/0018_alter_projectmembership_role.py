# Generated by Django 5.2.3 on 2025-06-30 11:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0017_projectlog_report'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projectmembership',
            name='role',
            field=models.CharField(choices=[('admin', 'Admin'), ('editor', 'Editor'), ('viewer', 'Viewer')], max_length=20),
        ),
    ]
