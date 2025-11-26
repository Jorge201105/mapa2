import json
from django.shortcuts import render, redirect
from django.conf import settings
from .models import PuntoEntrega
import requests
from . import optimizer # ¡Importamos nuestro módulo de optimización!

# views.py
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST



DEFAULT_FUEL_PRICE = 1250  # CLP/L por defecto
# views.py (tu vista del mapa)


import json
from django.conf import settings
from django.shortcuts import render
from .models import PuntoEntrega

DEFAULT_FUEL_PRICE = 1300  # o el valor que tengas

def mapa_view(request):
    puntos_entrega = PuntoEntrega.objects.all().order_by('orden_optimo')

    # Aquí generas el JSON que se usará en el JS del mapa
    puntos_json = json.dumps([
        {
            'id': p.id,
            'nombre': p.nombre,
            'direccion': p.direccion,
            'latitud': float(p.latitud),
            'longitud': float(p.longitud),
            'orden_optimo': p.orden_optimo,
        }
        for p in puntos_entrega
    ])

    context = {
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        'puntos_entrega_json': puntos_json,
        'puntos_entrega': puntos_entrega,

        'total_distance_km': request.session.pop('total_distance_km', None),
        'fuel_consumed_liters': request.session.pop('fuel_consumed_liters', None),
        'fuel_cost_clp': request.session.pop('fuel_cost_clp', None),
        'precio_bencina': request.session.pop('precio_bencina', DEFAULT_FUEL_PRICE),

        'direccion_origen': request.session.pop('direccion_origen', ''),
        'direccion_destino': request.session.pop('direccion_destino', ''),

        'origen_lat': request.session.pop('origen_lat', None),
        'origen_lng': request.session.pop('origen_lng', None),
        'destino_lat': request.session.pop('destino_lat', None),
        'destino_lng': request.session.pop('destino_lng', None),

        'error_message': request.session.pop('error_message', None),
    }

    return render(request, 'rutas/mapa.html', context)


def agregar_punto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        direccion = request.POST.get('direccion')

        if not nombre or not direccion:
            request.session['error_message'] = 'Nombre y dirección son obligatorios.'
            return redirect('mapa')

        latitud = request.POST.get('latitud')
        longitud = request.POST.get('longitud')

        # Geocodificación si no se proporcionan lat/lng
        if not latitud or not longitud:
            try:
                geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={direccion}&key={settings.GOOGLE_MAPS_API_KEY}"
                response = requests.get(geocode_url)
                data = response.json()
                if data['status'] == 'OK' and data['results']:
                    location = data['results'][0]['geometry']['location']
                    latitud = location['lat']
                    longitud = location['lng']
                else:
                    request.session['error_message'] = f"No se pudo geocodificar la dirección: {direccion}. Estado: {data['status']}"
                    return redirect('mapa')
            except requests.exceptions.RequestException as e:
                request.session['error_message'] = f"Error de conexión con la API de geocodificación: {e}"
                return redirect('mapa')
            except Exception as e:
                request.session['error_message'] = f"Error inesperado al geocodificar: {e}"
                return redirect('mapa')
        
        # Convertir a Decimal para el modelo
        try:
            latitud = float(latitud)
            longitud = float(longitud)
        except ValueError:
            request.session['error_message'] = 'Latitud o Longitud con formato incorrecto.'
            return redirect('mapa')

        PuntoEntrega.objects.create(nombre=nombre, direccion=direccion, latitud=latitud, longitud=longitud)
        return redirect('mapa')
    return redirect('mapa') # Si se accede directamente a /agregar_punto sin POST, redirige al mapa


def optimizar_ruta(request):
    if request.method != 'POST':
        return redirect('mapa')

    puntos_entrega_db = list(PuntoEntrega.objects.all())
    if not puntos_entrega_db:
        request.session['error_message'] = 'No hay puntos de entrega para optimizar.'
        return redirect('mapa')

    # 1) ORIGEN
    origen_predef = request.POST.get('origen_predefinido', '').strip()
    origen_custom = request.POST.get('origen_custom', '').strip()

    if origen_predef == 'custom':
        direccion_origen = origen_custom
    elif origen_predef:
        direccion_origen = origen_predef
    else:
        request.session['error_message'] = 'Debes seleccionar o escribir una dirección de origen.'
        return redirect('mapa')

    if not direccion_origen:
        request.session['error_message'] = 'La dirección de origen no puede estar vacía.'
        return redirect('mapa')

    # 2) DESTINO (puede ser igual al origen o una de las bodegas)
    destino_predef = request.POST.get('destino_predefinido', '').strip()

    if destino_predef == 'same_origin' or not destino_predef:
        # Por defecto, si no elige nada, volvemos al origen
        direccion_destino = direccion_origen
    else:
        direccion_destino = destino_predef

    # 3) GEOCOGIR ORIGEN
    try:
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
        params_origen = {
            "address": direccion_origen,
            "key": settings.GOOGLE_MAPS_API_KEY
        }
        resp_o = requests.get(geocode_url, params=params_origen)
        data_o = resp_o.json()

        if data_o['status'] == 'OK' and data_o['results']:
            loc_o = data_o['results'][0]['geometry']['location']
            lat_inicio = float(loc_o['lat'])
            lng_inicio = float(loc_o['lng'])
            punto_inicio_coords = {'latitud': lat_inicio, 'longitud': lng_inicio}
            request.session['origen_lat'] = lat_inicio
            request.session['origen_lng'] = lng_inicio
        else:
            request.session['error_message'] = f"No se pudo geocodificar la dirección de origen: {direccion_origen} (estado: {data_o['status']})."
            return redirect('mapa')
    except Exception as e:
        request.session['error_message'] = f"Error al geocodificar la dirección de origen: {e}"
        return redirect('mapa')

    # 4) GEOCOGIR DESTINO (si es distinto del origen, lo geocodificamos)
    destino_coords = None
    try:
        if direccion_destino == direccion_origen:
            # Misma coordenada que el origen
            destino_coords = {'latitud': lat_inicio, 'longitud': lng_inicio}
            request.session['destino_lat'] = lat_inicio
            request.session['destino_lng'] = lng_inicio
        else:
            params_dest = {
                "address": direccion_destino,
                "key": settings.GOOGLE_MAPS_API_KEY
            }
            resp_d = requests.get(geocode_url, params=params_dest)
            data_d = resp_d.json()
            if data_d['status'] == 'OK' and data_d['results']:
                loc_d = data_d['results'][0]['geometry']['location']
                lat_dest = float(loc_d['lat'])
                lng_dest = float(loc_d['lng'])
                destino_coords = {'latitud': lat_dest, 'longitud': lng_dest}
                request.session['destino_lat'] = lat_dest
                request.session['destino_lng'] = lng_dest
            else:
                request.session['error_message'] = f"No se pudo geocodificar la dirección destino: {direccion_destino} (estado: {data_d['status']})."
                return redirect('mapa')
    except Exception as e:
        request.session['error_message'] = f"Error al geocodificar la dirección destino: {e}"
        return redirect('mapa')

    # 5) MATRIZ DE DISTANCIAS
    distance_matrix = optimizer.get_distance_matrix(
        puntos_entrega_db,
        punto_inicio_coords,
        settings.GOOGLE_MAPS_API_KEY,
        dest_coords=destino_coords
    )

    if distance_matrix is None:
        request.session['error_message'] = 'No se pudo obtener la matriz de distancias. Revisa la clave API o la conexión.'
        return redirect('mapa')

    num_delivery_points = len(puntos_entrega_db)

    # índice del destino en la matriz: 0 = origen, 1..n = entregas, n+1 = destino
    end_index = num_delivery_points + 1 if destino_coords is not None else None

    # 6) OPTIMIZAR RUTA (camino start → entregas → destino)
    optimized_route_indices, total_distance_km = optimizer.solve_tsp(
        distance_matrix,
        num_delivery_points,
        start_index=0,
        end_index=end_index
    )

    if not optimized_route_indices:
        request.session['error_message'] = 'No se pudo optimizar la ruta. Verifica los puntos o el algoritmo.'
        return redirect('mapa')

    # 7) GUARDAR ORDEN ÓPTIMO EN LOS PUNTOS (solo índices 1..n)
    for i, matrix_idx in enumerate(optimized_route_indices[1:-1]):  # saltamos start y end
        if 1 <= matrix_idx <= num_delivery_points:
            punto = puntos_entrega_db[matrix_idx - 1]  # -1 porque la lista empieza en 0
            punto.orden_optimo = i + 1
            punto.save()

    # 8) CONSUMO Y COSTO
    fuel_consumed = optimizer.calculate_fuel_cost(total_distance_km)
    precio_bencina_str = request.POST.get('precio_bencina', '').strip()
    try:
        precio_bencina = float(precio_bencina_str) if precio_bencina_str else DEFAULT_FUEL_PRICE
    except ValueError:
        precio_bencina = DEFAULT_FUEL_PRICE

    fuel_cost = fuel_consumed * precio_bencina

    request.session['total_distance_km'] = round(total_distance_km, 2)
    request.session['fuel_consumed_liters'] = round(fuel_consumed, 2)
    request.session['fuel_cost_clp'] = round(fuel_cost, 0)
    request.session['precio_bencina'] = precio_bencina
    request.session['direccion_origen'] = direccion_origen
    request.session['direccion_destino'] = direccion_destino

    return redirect('mapa')



def borrar_puntos(request):
    if request.method == "POST":
        PuntoEntrega.objects.all().delete()
    # Cambia 'mapa' por el nombre de tu vista/URL del mapa
    return redirect('mapa')



@require_POST
def borrar_punto(request, punto_id):
    punto = get_object_or_404(PuntoEntrega, id=punto_id)
    punto.delete()
    return JsonResponse({"ok": True})
