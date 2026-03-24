from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0028_populate_trippoints"),
    ]

    operations = [
        migrations.RemoveField(model_name="trip", name="planned_loading_date"),
        migrations.RemoveField(model_name="trip", name="planned_unloading_date"),
        migrations.RemoveField(model_name="trip", name="actual_loading_date"),
        migrations.RemoveField(model_name="trip", name="actual_unloading_date"),
        migrations.RemoveField(model_name="trip", name="loading_address"),
        migrations.RemoveField(model_name="trip", name="unloading_address"),
        migrations.RemoveField(model_name="trip", name="loading_contact_name"),
        migrations.RemoveField(model_name="trip", name="loading_contact_phone"),
        migrations.RemoveField(model_name="trip", name="unloading_contact_name"),
        migrations.RemoveField(model_name="trip", name="unloading_contact_phone"),
        migrations.RemoveField(model_name="trip", name="loading_type"),
        migrations.RemoveField(model_name="trip", name="unloading_type"),
    ]
