# trips/services.py
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from docxtpl import DocxTemplate


class DocGenerationError(Exception):
    """Ошибки генерации документов."""


class BaseDocxGenerator:
    """
    Базовый генератор DOCX:
    - рендерит шаблон в память (BytesIO)
    - отдает FileResponse (attachment)
    """

    # Переопределяется в наследниках
    template_candidates: tuple[str, ...] = ()

    @staticmethod
    def _fmt(value, pattern: str) -> str:
        return value.strftime(pattern) if value else ""

    @classmethod
    def _resolve_template_path(cls) -> Path:
        """
        Ищет существующий шаблон среди candidate путей.
        Каждый candidate может быть:
        - абсолютный путь
        - путь относительно BASE_DIR
        """
        if not cls.template_candidates:
            raise DocGenerationError("Не заданы пути к шаблону (template_candidates).")

        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))

        for candidate in cls.template_candidates:
            raw = Path(candidate)
            if raw.exists():
                return raw

            rel = base_dir / candidate
            if rel.exists():
                return rel

        raise DocGenerationError(
            f"Шаблон не найден. Проверены пути: {', '.join(cls.template_candidates)}"
        )

    @classmethod
    def _render_to_buffer(cls, context: dict) -> BytesIO:
        template_path = cls._resolve_template_path()
        try:
            doc = DocxTemplate(str(template_path))
            doc.render(context)
        except Exception as exc:
            raise DocGenerationError(
                f"Ошибка рендера шаблона {template_path}: {exc}"
            ) from exc

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer


class TNGenerator(BaseDocxGenerator):
    """
    Генератор транспортной накладной (ТН).
    """

    template_candidates = (
        # если шаблон лежит в корневом templates/docs
        "templates/docs/tn_template.docx",
        # если шаблон лежит внутри приложения trips/templates/docs
        "trips/templates/docs/tn_template.docx",
    )

    @classmethod
    def build_context(cls, trip) -> dict:
        # Простая функция только для форматирования дат
        def fmt_date(date_val, format_str):
            return date_val.strftime(format_str) if date_val else "—"

        return {
            "date_of_trip": fmt_date(trip.date_of_trip, "%d.%m.%Y"),
            "num_of_trip": trip.num_of_trip or "—",
            "cargo": trip.cargo or "—",
            "weight": trip.weight or "—",
            "client": trip.client or "—",
            "consignor": trip.consignor or "—",
            "consignee": trip.consignee or "—",
            "carrier": trip.carrier or "—",
            "driver": trip.driver or "—",
            "truck": trip.truck or "—",
            "trailer": trip.trailer or "—",
            "loading_address": trip.loading_address or "—",
            "unloading_address": trip.unloading_address or "—",
            "client_cost": trip.client_cost or "—",
            "payment_term": trip.payment_condition or "—",
            "loading_contact_name": trip.loading_contact_name or "—",
            "loading_contact_phone": trip.loading_contact_phone or "—",
            "unloading_contact_name": trip.unloading_contact_name or "—",
            "unloading_contact_phone": trip.unloading_contact_phone or "—",
            "planned_loading_date": fmt_date(
                trip.planned_loading_date, "%d.%m.%Y %H:%M"
            ),
            "planned_unloading_date": fmt_date(
                trip.planned_unloading_date, "%d.%m.%Y %H:%M"
            ),
            "actual_loading_date": fmt_date(trip.actual_loading_date, "%d.%m.%Y %H:%M"),
            "actual_unloading_date": fmt_date(
                trip.actual_unloading_date, "%d.%m.%Y %H:%M"
            ),
            # Для типов погрузки/разгрузки используем get_FOO_display()
            "loading_type": (
                trip.get_loading_type_display() if trip.loading_type else "—"
            ),
            "unloading_type": (
                trip.get_unloading_type_display() if trip.unloading_type else "—"
            ),
            "payment_condition": trip.get_payment_condition_display() or "—",
        }

    @classmethod
    def build_download_name(cls, trip) -> str:
        date_str = cls._fmt(trip.date_of_trip, "%d.%m.%Y")
        return f"ТрН №{trip.num_of_trip} от {date_str}.docx"

    @classmethod
    def generate_response(cls, trip) -> FileResponse:
        """
        Главный метод: сразу возвращает файл для скачивания.
        """
        context = cls.build_context(trip)
        buffer = cls._render_to_buffer(context)
        filename = cls.build_download_name(trip)

        return FileResponse(
            buffer,
            as_attachment=True,
            filename=filename,
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.wordprocessingml.document"
            ),
        )


class AgreementRequestGenerator(TNGenerator):
    """
    Договор-заявка: тот же context, что и для ТН,
    но другой шаблон и другое имя файла.
    """

    template_candidates = (
        "templates/docs/agreement_request_template.docx",
        "trips/templates/docs/agreement_request_template.docx",
    )

    @classmethod
    def build_download_name(cls, trip) -> str:
        date_str = cls._fmt(trip.date_of_trip, "%d.%m.%Y")
        return f"Договор-заявка №{trip.num_of_trip} от {date_str}.docx"
