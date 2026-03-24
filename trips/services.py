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
        def fmt_date(date_val, format_str):
            return date_val.strftime(format_str) if date_val else "—"

        load_p = trip.load_point
        unload_p = trip.unload_point

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
            "loading_address": (load_p.address if load_p else "") or "—",
            "unloading_address": (unload_p.address if unload_p else "") or "—",
            "client_cost": trip.client_cost or "—",
            "payment_term": trip.payment_condition or "—",
            "loading_contact_name": (load_p.contact_name if load_p else "") or "—",
            "loading_contact_phone": (load_p.contact_phone if load_p else "") or "—",
            "unloading_contact_name": (unload_p.contact_name if unload_p else "") or "—",
            "unloading_contact_phone": (unload_p.contact_phone if unload_p else "") or "—",
            "planned_loading_date": fmt_date(
                load_p.planned_date if load_p else None, "%d.%m.%Y %H:%M"
            ),
            "planned_unloading_date": fmt_date(
                unload_p.planned_date if unload_p else None, "%d.%m.%Y %H:%M"
            ),
            "actual_loading_date": fmt_date(
                load_p.actual_date if load_p else None, "%d.%m.%Y %H:%M"
            ),
            "actual_unloading_date": fmt_date(
                unload_p.actual_date if unload_p else None, "%d.%m.%Y %H:%M"
            ),
            "loading_type": (
                load_p.get_loading_type_display()
                if load_p and load_p.loading_type else "—"
            ),
            "unloading_type": (
                unload_p.get_loading_type_display()
                if unload_p and unload_p.loading_type else "—"
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
