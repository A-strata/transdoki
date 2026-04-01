from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0038_split_datetime_step2_copy_data'),
    ]

    operations = [
        # Удаляем старые DateTimeField
        migrations.RemoveField(model_name='trippoint', name='planned_date'),
        migrations.RemoveField(model_name='trippoint', name='actual_date'),

        # Переименовываем _new → оригинальные имена
        migrations.RenameField(
            model_name='trippoint',
            old_name='planned_date_new',
            new_name='planned_date',
        ),
        migrations.RenameField(
            model_name='trippoint',
            old_name='actual_date_new',
            new_name='actual_date',
        ),
    ]
