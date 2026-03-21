from django.db import migrations

BATCH_SIZE = 1000


def backfill_organizations_account_retry(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    OrganizationBank = apps.get_model("organizations", "OrganizationBank")
    UserProfile = apps.get_model("accounts", "UserProfile")

    user_account_map = dict(
        UserProfile.objects.exclude(account_id__isnull=True).values_list("user_id", "account_id")
    )

    # Organization
    org_qs = Organization.objects.filter(account_id__isnull=True).only("id", "created_by_id", "account_id")
    to_update = []
    org_updated = 0

    for org in org_qs.iterator(chunk_size=BATCH_SIZE):
        account_id = user_account_map.get(org.created_by_id)
        if account_id:
            org.account_id = account_id
            to_update.append(org)

        if len(to_update) >= BATCH_SIZE:
            Organization.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
            org_updated += len(to_update)
            to_update.clear()

    if to_update:
        Organization.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
        org_updated += len(to_update)

    # OrganizationBank
    org_account_map = dict(
        Organization.objects.exclude(account_id__isnull=True).values_list("id", "account_id")
    )

    bank_qs = OrganizationBank.objects.filter(account_id__isnull=True).only(
        "id", "created_by_id", "account_owner_id", "account_id"
    )
    to_update = []
    bank_updated = 0

    for row in bank_qs.iterator(chunk_size=BATCH_SIZE):
        account_id = org_account_map.get(row.account_owner_id) or user_account_map.get(row.created_by_id)
        if account_id:
            row.account_id = account_id
            to_update.append(row)

        if len(to_update) >= BATCH_SIZE:
            OrganizationBank.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
            bank_updated += len(to_update)
            to_update.clear()

    if to_update:
        OrganizationBank.objects.bulk_update(to_update, ["account_id"], batch_size=BATCH_SIZE)
        bank_updated += len(to_update)

    print(
        "[organizations backfill retry] "
        f"updated: Organization={org_updated}, OrganizationBank={bank_updated}; "
        f"left_null: Organization={Organization.objects.filter(account_id__isnull=True).count()}, "
        f"OrganizationBank={OrganizationBank.objects.filter(account_id__isnull=True).count()}"
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0004_backfill_account_and_profiles"),
        ("organizations", "0013_backfill_account"),
    ]

    operations = [
        migrations.RunPython(backfill_organizations_account_retry, migrations.RunPython.noop),
    ]