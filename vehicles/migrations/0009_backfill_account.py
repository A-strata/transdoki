from django.db import migrations

BATCH_SIZE = 1000


def backfill_vehicles_account(apps, schema_editor):
    Vehicle = apps.get_model("vehicles", "Vehicle")
    Organization = apps.get_model("organizations", "Organization")
    UserProfile = apps.get_model("accounts", "UserProfile")

    org_account_map = dict(
        Organization.objects.exclude(account_id__isnull=True).values_list("id", "account_id")
    )
    user_account_map = dict(
        UserProfile.objects.exclude(account_id__isnull=True).values_list("user_id", "account_id")
    )

    qs = Vehicle.objects.filter(account_id__isnull=True).only(
        "id", "owner_id", "created_by_id", "account_id"
    )

    to_update = []
    updated = 0

    for row in qs.iterator(chunk_size=BATCH_SIZE):
        account_id = org_account_map.get(row.owner_id) or user_account_map.get(row.created_by_id)
        if account_id:
            row.account_id = account_id
            to_update.append(row)

        if len(to_update) >= BATCH_SIZE:
            Vehicle.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
            updated += len(to_update)
            to_update.clear()

    if to_update:
        Vehicle.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
        updated += len(to_update)

    left_null = Vehicle.objects.filter(account_id__isnull=True).count()
    print(f"[vehicles backfill] updated={updated}; left_null={left_null}")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0004_backfill_account_and_profiles"),
        ("organizations", "0014_backfill_account_retry"),
        ("vehicles", "0008_vehicle_account"),
    ]

    operations = [
        migrations.RunPython(backfill_vehicles_account, migrations.RunPython.noop),
    ]