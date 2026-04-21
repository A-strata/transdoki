"""
Тесты доменной функции compute_trip_role.

Чистые unit-тесты (SimpleTestCase): функция не обращается ни к БД,
ни к Django-модели, ей достаточно целочисленных id. Держим их отдельно
от trips/tests.py, чтобы не мешать медленным интеграционным тестам
и чтобы было очевидно, что это спецификация доменного правила.
"""

from django.test import SimpleTestCase

from trips.roles import TripRole, compute_trip_role


# Реальных org.pk не нужно — используем произвольные числа.
# Важно: SL = Славянские луга (client-кейс), IP = ИП Астахин (carrier-кейс),
# FWD = фирма-экспедитор, OTHER = сторонний контрагент.
SL = 1
IP = 2
FWD = 3
OTHER = 4
RANDOM = 5


class ComputeTripRoleTests(SimpleTestCase):
    # ── Базовые роли ──

    def test_viewer_is_client_returns_client(self):
        role = compute_trip_role(
            client_id=SL, carrier_id=OTHER, forwarder_id=None,
            viewer_org_id=SL,
        )
        self.assertEqual(role, TripRole.CLIENT)

    def test_viewer_is_carrier_returns_carrier(self):
        role = compute_trip_role(
            client_id=OTHER, carrier_id=IP, forwarder_id=None,
            viewer_org_id=IP,
        )
        self.assertEqual(role, TripRole.CARRIER)

    def test_viewer_is_forwarder_returns_forwarder(self):
        role = compute_trip_role(
            client_id=OTHER, carrier_id=RANDOM, forwarder_id=FWD,
            viewer_org_id=FWD,
        )
        self.assertEqual(role, TripRole.FORWARDER)

    # ── Observer: viewer не участвует ──

    def test_viewer_none_returns_observer(self):
        role = compute_trip_role(
            client_id=SL, carrier_id=IP, forwarder_id=None,
            viewer_org_id=None,
        )
        self.assertEqual(role, TripRole.OBSERVER)

    def test_viewer_not_in_trip_returns_observer(self):
        role = compute_trip_role(
            client_id=SL, carrier_id=IP, forwarder_id=None,
            viewer_org_id=RANDOM,
        )
        self.assertEqual(role, TripRole.OBSERVER)

    def test_empty_trip_viewer_none_returns_observer(self):
        role = compute_trip_role(
            client_id=None, carrier_id=None, forwarder_id=None,
            viewer_org_id=None,
        )
        self.assertEqual(role, TripRole.OBSERVER)

    # ── Internal-рейс (обе свои, разные): роль зависит от viewer ──

    def test_internal_trip_viewer_client_perspective(self):
        """
        SL=client (своя), IP=carrier (своя). Под навбаром SL видим
        рейс как CLIENT (платим IP). Это и есть основной сценарий бага:
        UI не должен показывать 2 блока, должен показывать один «client».
        """
        role = compute_trip_role(
            client_id=SL, carrier_id=IP, forwarder_id=None,
            viewer_org_id=SL,
        )
        self.assertEqual(role, TripRole.CLIENT)

    def test_internal_trip_viewer_carrier_perspective(self):
        """Тот же рейс, но смотрим из-под IP → CARRIER (получаем от SL)."""
        role = compute_trip_role(
            client_id=SL, carrier_id=IP, forwarder_id=None,
            viewer_org_id=IP,
        )
        self.assertEqual(role, TripRole.CARRIER)

    def test_internal_trip_third_navbar_is_observer(self):
        """
        Internal-рейс (SL+IP), а навбар — третья own-фирма, которой
        в рейсе нет. perspective = observer. TenantManager должен
        отсеять такой рейс от списка, но compute_trip_role всё равно
        вернёт OBSERVER корректно.
        """
        role = compute_trip_role(
            client_id=SL, carrier_id=IP, forwarder_id=None,
            viewer_org_id=RANDOM,
        )
        self.assertEqual(role, TripRole.OBSERVER)

    # ── Forwarder имеет приоритет перед client/carrier ──
    # В существующей модели validate_forwarder запрещает совпадение
    # forwarder с client/carrier, но функция должна быть устойчива даже
    # в теоретически «сломанных» данных: forwarder выигрывает.

    def test_forwarder_takes_precedence_over_client(self):
        role = compute_trip_role(
            client_id=SL, carrier_id=OTHER, forwarder_id=SL,
            viewer_org_id=SL,
        )
        self.assertEqual(role, TripRole.FORWARDER)

    def test_forwarder_takes_precedence_over_carrier(self):
        role = compute_trip_role(
            client_id=OTHER, carrier_id=IP, forwarder_id=IP,
            viewer_org_id=IP,
        )
        self.assertEqual(role, TripRole.FORWARDER)

    # ── Сценарий «поменяли client на стороннего, carrier наш» ──
    # Это расширение основного бага: пользователь меняет client.
    # Ранее: navbar=SL был client → role=CLIENT, одна колонка.
    # После смены: client=RANDOM, carrier=IP (own, ≠navbar=SL).
    # Navbar=SL больше не участвует в рейсе → OBSERVER.
    # В UI продуктовая логика Phase 2 решит, как это отображать
    # (read-only / автопереключение). Здесь важно, что роль
    # определена однозначно.

    def test_after_client_replaced_navbar_becomes_observer(self):
        role = compute_trip_role(
            client_id=RANDOM, carrier_id=IP, forwarder_id=None,
            viewer_org_id=SL,
        )
        self.assertEqual(role, TripRole.OBSERVER)

    def test_after_client_replaced_carrier_own_is_carrier_for_its_navbar(self):
        role = compute_trip_role(
            client_id=RANDOM, carrier_id=IP, forwarder_id=None,
            viewer_org_id=IP,
        )
        self.assertEqual(role, TripRole.CARRIER)

    # ── Keyword-only: защита от ошибок порядка аргументов ──

    def test_positional_args_rejected(self):
        """
        Все параметры должны быть keyword-only (одинаковый тип int
        легко перепутать). Позитивная проверка — TypeError на попытку
        передать позиционно.
        """
        with self.assertRaises(TypeError):
            compute_trip_role(SL, IP, None, SL)  # type: ignore[misc]
