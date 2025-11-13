import re

from django.core.exceptions import ValidationError


def validate_grn_by_type(grn, vehicle_type):
    """
    Валидатор госномера в зависимости от типа ТС
    """
    if vehicle_type in ['single', 'truck']:
        if not re.match(r'^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$', grn):
            raise ValidationError('Формат номера для грузовика: А123ВЕ12 или А123ВЕ123')
    
    elif vehicle_type == 'trailer': 
        if not re.match(r'^[АВЕКМНОРСТУХ]{2}\d{5,6}$', grn):
            raise ValidationError('Формат номера для прицепа: АВ123412 или АВ1234123')