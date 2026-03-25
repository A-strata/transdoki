# Cron-задачи transdoki

## Ежесуточное списание (charge_daily)

Запускается в **00:05 по московскому времени** ежедневно.

### Установленная задача (crontab пользователя deploy)

```
5 0 * * * cd /home/deploy/projects/transdoki && DJANGO_SETTINGS_MODULE=transdoki.settings .venv/bin/python manage.py charge_daily >> logs/charge_daily.log 2>&1
```

### Что делает

- Перебирает все активные аккаунты (`is_active=True`, `is_billing_exempt=False`)
- Считает стоимость за сутки: организации + транспорт + пользователи сверх бесплатного уровня
- Списывает через `billing.services.withdraw()` с детализацией в `metadata`
- Логирует итог в `logs/django.log`, ошибки — в `logs/security.log`
- Вывод команды пишется в `logs/charge_daily.log`

### Тарифы (billing/constants.py)

| Сущность | Бесплатно | Цена за штуку/сутки |
|----------|-----------|---------------------|
| Организация (своя компания) | 1 | 15 ₽ |
| Транспортное средство | 2 | 10 ₽ |
| Пользователь | 2 | 5 ₽ |

### Проверка без списания

```bash
python manage.py charge_daily --dry-run
```

### Просмотр логов

```bash
tail -f logs/charge_daily.log
tail -f logs/django.log | grep charge_daily
```

### Редактирование расписания

```bash
crontab -e   # под пользователем deploy
```
