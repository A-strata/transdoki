import os

from dadata import Dadata
from django.http import JsonResponse
from dotenv import load_dotenv

load_dotenv()

DADATA_TOKEN = os.getenv('DADATA_TOKEN')
DADATA_SECRET = os.getenv('DADATA_SECRET')


def suggest_bank(request):
    """Подсказки банков по БИК или названию (для автокомплита)."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"suggestions": []})

    try:
        dadata_client = Dadata(DADATA_TOKEN, DADATA_SECRET)
        results = dadata_client.suggest("bank", query, count=7)
    except Exception:
        return JsonResponse({"suggestions": []})

    suggestions = []
    for item in results:
        data = item.get("data", {})
        suggestions.append({
            "bic": data.get("bic", ""),
            "bank_name": (data.get("name") or {}).get("payment", ""),
            "corr_account": data.get("correspondent_account", ""),
        })

    return JsonResponse({"suggestions": suggestions})


def suggest_party(request):
    """Подсказки организаций по частичному ИНН или названию (для автокомплита)."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    try:
        dadata = Dadata(DADATA_TOKEN, DADATA_SECRET)
        results = dadata.suggest("party", query, count=7)
    except Exception:
        return JsonResponse({'suggestions': []})

    suggestions = []
    for item in results:
        data = item.get('data', {})
        suggestions.append({
            'inn':        data.get('inn', ''),
            'kpp':        data.get('kpp', '') or '',
            'ogrn':       data.get('ogrn', '') or '',
            'address':    (data.get('address') or {}).get('unrestricted_value', ''),
            'short_name': (data.get('name') or {}).get('short_with_opf', ''),
            'full_name':  (data.get('name') or {}).get('full_with_opf', ''),
        })

    return JsonResponse({'suggestions': suggestions})


def get_org_data(request):
    if request.method == 'GET' and 'inn' in request.GET:
        inn = request.GET['inn']

        dadata = Dadata(DADATA_TOKEN, DADATA_SECRET)
        data = dadata.find_by_id("party", query=inn)[0]['data']

        full_with_opf = data['name']['full_with_opf']
        short_with_opf = data['name']['short_with_opf']
        address = data['address']['unrestricted_value']  #['data']['source']  # ['value']
        ogrn = data['ogrn']

        director = ''
        post = ''
        kpp = '0'

        if data['opf']['short'] == 'ИП':
            director = data['name']['full']
            post = data['opf']['full']

        if data['opf']['short'] != 'ИП' and data['management']['post']:
            director = data['management']['name']
            post = data['management']['post']

        if 'kpp' in data:
            kpp = data['kpp']

        context = {
            'full_name': full_with_opf,
            'short_name': short_with_opf,
            'address': address,
            'ogrn': ogrn,
            'kpp': kpp,
            'director': director,
            'post': post
        }
        return JsonResponse(context)
