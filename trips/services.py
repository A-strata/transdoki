import os

from django.http import FileResponse
from docxtpl import DocxTemplate


class TNGenerator:
    @staticmethod
    def generate_tn(trip):
        """Генерация транспортной накладной"""
        # Форматируем даты
        formatted_date_of_trip = trip.date_of_trip.strftime(
            '%d.%m.%Y') if trip.date_of_trip else ''
        planned_loading_date = trip.planned_loading_date.strftime(
            '%d.%m.%Y %H:%M') if trip.planned_loading_date else ''
        planned_unloading_date = trip.planned_unloading_date.strftime(
            '%d.%m.%Y %H:%M') if trip.planned_unloading_date else ''
        actual_loading_date = trip.actual_loading_date.strftime(
            '%d.%m.%Y %H:%M') if trip.actual_loading_date else ''
        actual_unloading_date = trip.actual_unloading_date.strftime(
            '%d.%m.%Y %H:%M') if trip.actual_unloading_date else ''

        context = {
            'date_of_trip': formatted_date_of_trip,
            'num_of_trip': trip.num_of_trip,
            'cargo': trip.cargo,
            'weight': trip.weight,
            'client': trip.client,
            'consignor': trip.consignor,
            'consignee': trip.consignee,
            'carrier': trip.carrier,
            'driver': trip.driver,
            'truck': trip.truck,
            'trailer': trip.trailer,
            'planned_loading_date': planned_loading_date,
            'planned_unloading_date': planned_unloading_date,
            'actual_loading_date': actual_loading_date,
            'actual_unloading_date': actual_unloading_date,
        }

        # Генерируем документ
        doc = DocxTemplate("templates/docs/tn_template.docx")
        doc.render(context)

        # Создаем папку если нет
        os.makedirs('documents', exist_ok=True)

        file_name = (
            f"documents/ТН № {trip.num_of_trip} "
            f"от {formatted_date_of_trip}.docx")
        doc.save(file_name)

        return file_name

    @staticmethod
    def create_file_response(file_path, trip):
        """Создание HTTP response с файлом"""
        formatted_date = trip.date_of_trip.strftime(
            '%d.%m.%Y') if trip.date_of_trip else ''
        response = FileResponse(open(file_path, "rb"))
        response['Content-Disposition'] = (
            f'attachment; filename="TN {trip.num_of_trip} '
            f'- {formatted_date}.docx"')
        return response
