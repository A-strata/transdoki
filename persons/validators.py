from django.core.exceptions import ValidationError


def validate_phone_number(value):
    if not value:
        raise ValidationError('Заполните это поле')

    clean_phone = ''.join(filter(str.isdigit, value))

    if len(clean_phone) != 11:
        raise ValidationError('Номер телефона должен содержать 11 цифр')

    if not clean_phone.startswith(('7', '8')):
        raise ValidationError('Номер телефона должен начинаться с 7 или 8')

    operator_code = clean_phone[1:4]
    valid_operator_codes = [
        '900', '901', '902', '903', '904', '905', '906', '908', '909',
        '910', '911', '912', '913', '914', '915', '916', '917', '918', '919',
        '920', '921', '922', '923', '924', '925', '926', '927', '928', '929',
        '930', '931', '932', '933', '934', '936', '937', '938', '939',
        '950', '951', '952', '953', '954', '955', '956', '958',
        '960', '961', '962', '963', '964', '965', '966', '967', '968', '969',
        '980', '981', '982', '983', '984', '985', '986', '987', '988', '989',
        '999'
    ]

    if operator_code not in valid_operator_codes:
        raise ValidationError('Неверный код оператора')

    return clean_phone
