from django.db import migrations


def backfill_sellers(apps, schema_editor):
    Invoice = apps.get_model("invoicing", "Invoice")

    updated = 0
    skipped = {"no_lines_with_trip": 0, "foreign_roles": 0, "mixed_sellers": 0}

    qs = Invoice.objects.filter(seller__isnull=True).prefetch_related(
        "lines__trip__carrier",
        "lines__trip__forwarder",
    )

    for invoice in qs.iterator(chunk_size=500):
        sellers = set()
        has_trip_line = False
        for line in invoice.lines.all():
            trip = line.trip
            if trip is None:
                continue
            has_trip_line = True
            if trip.carrier_id and trip.carrier.is_own_company:
                sellers.add(trip.carrier_id)
                continue
            if trip.forwarder_id and trip.forwarder.is_own_company:
                sellers.add(trip.forwarder_id)

        if not has_trip_line:
            skipped["no_lines_with_trip"] += 1
            continue
        if not sellers:
            skipped["foreign_roles"] += 1
            continue
        if len(sellers) > 1:
            skipped["mixed_sellers"] += 1
            continue

        invoice.seller_id = sellers.pop()
        invoice.save(update_fields=["seller"])
        updated += 1

    print(
        f"[invoicing backfill] updated={updated}; "
        f"left_null: no_lines_with_trip={skipped['no_lines_with_trip']}, "
        f"foreign_roles={skipped['foreign_roles']}, "
        f"mixed_sellers={skipped['mixed_sellers']}"
    )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("invoicing", "0012_invoice_seller"),
    ]

    operations = [
        migrations.RunPython(backfill_sellers, reverse_noop),
    ]
