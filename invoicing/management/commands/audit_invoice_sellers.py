from collections import defaultdict

from django.core.management.base import BaseCommand

from invoicing.models import Invoice


def resolve_seller_for_invoice(invoice):
    """
    Возвращает (seller_id, reason):
      - (int, None) — seller однозначно определён;
      - (None, "no_lines_with_trip") — у счёта нет строк с trip;
      - (None, "foreign_roles")       — ни carrier ни forwarder не own;
      - (None, "mixed_sellers")       — строки дают разных seller'ов.
    """
    lines = list(invoice.lines.select_related(
        "trip__carrier", "trip__forwarder"
    ).all())

    sellers = set()
    has_trip_line = False
    for line in lines:
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
        return None, "no_lines_with_trip"
    if not sellers:
        return None, "foreign_roles"
    if len(sellers) > 1:
        return None, "mixed_sellers"
    return sellers.pop(), None


class Command(BaseCommand):
    help = (
        "Аудит Invoice.seller перед backfill-миграцией. "
        "Для каждого счёта определяет seller через carrier/forwarder "
        "связанных рейсов и печатает сводку по bucket'ам."
    )

    def handle(self, *args, **options):
        total = Invoice.objects.count()
        determinable = 0
        buckets = defaultdict(list)

        for invoice in Invoice.objects.all().iterator():
            seller_id, reason = resolve_seller_for_invoice(invoice)
            if seller_id is not None:
                determinable += 1
            else:
                buckets[reason].append(invoice.display_number)

        manual_total = sum(len(v) for v in buckets.values())

        self.stdout.write(f"[audit] total_invoices={total}")
        self.stdout.write(f"[audit]   determinable={determinable}")
        for reason in ("no_lines_with_trip", "foreign_roles", "mixed_sellers"):
            self.stdout.write(f"[audit]   {reason}={len(buckets[reason])}")
        self.stdout.write(f"[audit] manual_review_total={manual_total}")

        if manual_total:
            self.stdout.write("[audit] affected invoices:")
            for reason, numbers in buckets.items():
                for num in numbers:
                    self.stdout.write(f"[audit]   {reason}: {num}")
