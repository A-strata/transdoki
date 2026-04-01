"""
Data migration: копирует Trip.consignor → load_point.organization,
Trip.consignee → unload_point.organization.

Безопасная миграция: обновляет только записи с organization=NULL,
не трогает уже заполненные. Обратная миграция — noop (данные в Trip остаются).
"""
from django.db import migrations


def forward(apps, schema_editor):
    TripPoint = apps.get_model("trips", "TripPoint")

    # Bulk update не поддерживает F() через FK в Django ORM для data migrations,
    # поэтому используем итерацию (записей не так много).
    load_points = TripPoint.objects.filter(
        point_type="LOAD",
        sequence=1,
        organization__isnull=True,
        trip__consignor__isnull=False,
    ).select_related("trip")

    for point in load_points:
        point.organization_id = point.trip.consignor_id
        point.save(update_fields=["organization_id"])

    unload_points = TripPoint.objects.filter(
        point_type="UNLOAD",
        sequence=2,
        organization__isnull=True,
        trip__consignee__isnull=False,
    ).select_related("trip")

    for point in unload_points:
        point.organization_id = point.trip.consignee_id
        point.save(update_fields=["organization_id"])


def backward(apps, schema_editor):
    # Обратная миграция не нужна: Trip.consignor/consignee остаются на месте
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0034_add_organization_to_trippoint"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
