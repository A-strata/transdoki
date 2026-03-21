from django.db import migrations

BATCH_SIZE = 1000


def backfill_trips_account(apps, schema_editor):
    Trip = apps.get_model("trips", "Trip")
    TripAttachment = apps.get_model("trips", "TripAttachment")
    Organization = apps.get_model("organizations", "Organization")
    UserProfile = apps.get_model("accounts", "UserProfile")

    org_account_map = dict(
        Organization.objects.exclude(account_id__isnull=True).values_list("id", "account_id")
    )
    user_account_map = dict(
        UserProfile.objects.exclude(account_id__isnull=True).values_list("user_id", "account_id")
    )

    # 1) Trip.account_id
    trips_qs = Trip.objects.filter(account_id__isnull=True).only(
        "id",
        "created_by_id",
        "carrier_id",
        "client_id",
        "consignor_id",
        "consignee_id",
        "account_id",
    )

    to_update = []
    trips_updated = 0

    for row in trips_qs.iterator(chunk_size=BATCH_SIZE):
        account_id = (
            org_account_map.get(row.carrier_id)
            or org_account_map.get(row.client_id)
            or org_account_map.get(row.consignor_id)
            or org_account_map.get(row.consignee_id)
            or user_account_map.get(row.created_by_id)
        )

        if account_id:
            row.account_id = account_id
            to_update.append(row)

        if len(to_update) >= BATCH_SIZE:
            Trip.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
            trips_updated += len(to_update)
            to_update.clear()

    if to_update:
        Trip.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
        trips_updated += len(to_update)

    # 2) TripAttachment.account_id
    trip_account_map = dict(
        Trip.objects.exclude(account_id__isnull=True).values_list("id", "account_id")
    )

    attachments_qs = TripAttachment.objects.filter(account_id__isnull=True).only(
        "id", "trip_id", "created_by_id", "account_id"
    )

    to_update = []
    attachments_updated = 0

    for row in attachments_qs.iterator(chunk_size=BATCH_SIZE):
        account_id = trip_account_map.get(row.trip_id) or user_account_map.get(row.created_by_id)

        if account_id:
            row.account_id = account_id
            to_update.append(row)

        if len(to_update) >= BATCH_SIZE:
            TripAttachment.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
            attachments_updated += len(to_update)
            to_update.clear()

    if to_update:
        TripAttachment.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
        attachments_updated += len(to_update)

    print(
        "[trips backfill] "
        f"updated: Trip={trips_updated}, TripAttachment={attachments_updated}; "
        f"left_null: Trip={Trip.objects.filter(account_id__isnull=True).count()}, "
        f"TripAttachment={TripAttachment.objects.filter(account_id__isnull=True).count()}"
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0004_backfill_account_and_profiles"),
        ("organizations", "0014_backfill_account_retry"),
        ("trips", "0022_trip_account_tripattachment_account"),
    ]

    operations = [
        migrations.RunPython(backfill_trips_account, migrations.RunPython.noop),
    ]