import json
from django.shortcuts import render, redirect
from django.conf import settings
from .models import PuntoEntrega
import requests
from . import optimizer # ¡Importamos nuestro módulo de optimización!

def mapa_view(request):
    puntos_entrega = PuntoEntrega.objects.all().order_by('orden_optimo') # Ordena si ya hay un orden

    # Convertir puntos a un formato JSON seguro para JS
    puntos_json = json.dumps([{
        'id': p.id, # Añadir ID para posible uso en JS si es necesario
        'nombre': p.nombre,
        'direccion': p.direccion,
        'latitud': float(p.latitud),
        'longitud': float(p.longitud),
        'orden_optimo': p.orden_optimo
    } for p in puntos_entrega])

    context = {
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        'puntos_entrega_json': puntos_json,
        'puntos_entrega': puntos_entrega, # Pasar los objetos directamente también para la lista HTML
        'total_distance_km': request.session.pop('total_distance_km', None), # Obtener y limpiar de la sesión
        'fuel_consumed_liters': request.session.pop('fuel_consumed_liters', None), # Obtener y limpiar de la sesión
        'error_message': request.session.pop('error_message', None), # Mensajes de error
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
    if request.method == 'POST':
        # 1. Obtener los puntos de entrega y el punto de inicio
        puntos_entrega_db = list(PuntoEntrega.objects.all())
        
        # Validar si hay puntos para optimizar
        if not puntos_entrega_db:
            request.session['error_message'] = 'No hay puntos de entrega para optimizar.'
            return redirect('mapa')

        try:
            lat_inicio = float(request.POST['lat_inicio'])
            lng_inicio = float(request.POST['lng_inicio'])
            punto_inicio_coords = {'latitud': lat_inicio, 'longitud': lng_inicio}
        except ValueError:
            request.session['error_message'] = 'Latitud o Longitud de inicio inválida.'
            return redirect('mapa')

        # 2. Obtener la matriz de distancias
        distance_matrix = optimizer.get_distance_matrix(puntos_entrega_db, punto_inicio_coords, settings.GOOGLE_MAPS_API_KEY)

        if distance_matrix is None:
            request.session['error_message'] = 'No se pudo obtener la matriz de distancias. Revisa la clave API o la conexión.'
            return redirect('mapa')
        
        num_delivery_points = len(puntos_entrega_db)
        
        # 3. Llamar al algoritmo de optimización TSP
        optimized_route_indices, total_distance_km = optimizer.solve_tsp(
            distance_matrix,
            num_delivery_points,
            start_index=0 # El punto de inicio siempre es el índice 0 en nuestra matriz
        )

        if not optimized_route_indices:
             request.session['error_message'] = 'No se pudo optimizar la ruta. Verifica los puntos o el algoritmo.'
             return redirect('mapa')

        # 4. Asignar el orden optimizado a los objetos PuntoEntrega
        # Los índices en optimized_route_indices (excluyendo el primero y el último que son el origen)
        # corresponden a los puntos de entrega en puntos_entrega_db.
        # matrix_idx - 1 es necesario porque puntos_entrega_db no incluye el origen.
        
        for i, matrix_idx in enumerate(optimized_route_indices[1:-1]): # Iteramos solo sobre los puntos de entrega
            punto = puntos_entrega_db[matrix_idx - 1] # -1 porque los puntos de entrega empiezan en el índice 1 de la matriz
            punto.orden_optimo = i + 1 # Asignar un orden secuencial (1, 2, 3...)
            punto.save()

        # 5. Calcular y guardar el consumo de bencina (o mostrarlo)
        fuel_consumed = optimizer.calculate_fuel_cost(total_distance_km)

        request.session['total_distance_km'] = round(total_distance_km, 2)
        request.session['fuel_consumed_liters'] = round(fuel_consumed, 2)

        return redirect('mapa')
    return redirect('mapa')

def borrar_puntos(request):
    if request.method == "POST":
        PuntoEntrega.objects.all().delete()
    # Cambia 'mapa' por el nombre de tu vista/URL del mapa
    return redirect('mapa')