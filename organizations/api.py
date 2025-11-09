from django.http import JsonResponse
from dadata import Dadata
from dotenv import load_dotenv
import os


load_dotenv()

DADATA_TOKEN = os.getenv('DADATA_TOKEN')
DADATA_SECRET = os.getenv('DADATA_SECRET')

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