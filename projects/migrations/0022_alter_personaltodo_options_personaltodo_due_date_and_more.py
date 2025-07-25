# Generated by Django 5.2.3 on 2025-07-04 13:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0021_alter_personaltodo_options_alter_personaltodo_title_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='personaltodo',
            options={'ordering': ['is_completed', 'due_date']},
        ),
        migrations.AddField(
            model_name='personaltodo',
            name='due_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='personaltodo',
            name='priority',
            field=models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium', max_length=10),
        ),
    ]
