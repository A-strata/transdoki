from django.db import migrations

BATCH_SIZE = 1000


def backfill_persons_account(apps, schema_editor):
    Person = apps.get_model("persons", "Person")
    UserProfile = apps.get_model("accounts", "UserProfile")

    user_account_map = dict(
        UserProfile.objects.exclude(account_id__isnull=True).values_list("user_id", "account_id")
    )

    qs = Person.objects.filter(account_id__isnull=True).only("id", "created_by_id", "account_id")
    to_update = []
    updated = 0

    for row in qs.iterator(chunk_size=BATCH_SIZE):
        account_id = user_account_map.get(row.created_by_id)
        if account_id:
            row.account_id = account_id
            to_update.append(row)

        if len(to_update) >= BATCH_SIZE:
            Person.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
            updated += len(to_update)
            to_update.clear()

    if to_update:
        Person.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
        updated += len(to_update)

    left_null = Person.objects.filter(account_id__isnull=True).count()
    print(f"[persons backfill] updated={updated}; left_null={left_null}")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0004_backfill_account_and_profiles"),
        ("persons", "0014_person_account"),
    ]

    operations = [
        migrations.RunPython(backfill_persons_account, migrations.RunPython.noop),
    ]