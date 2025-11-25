import requests
import json
from django.conf import settings
import itertools # Útil para generar permutaciones para problemas pequeños o como base

# --- PARTE 1: Obtener Distancias/Tiempos de Google Maps ---
def get_distance_matrix(points, origin_coords, api_key):
    """
    Obtiene la matriz de distancias entre todos los puntos y el punto de origen.
    Los 'points' son una lista de objetos PuntoEntrega.
    'origin_coords' es un diccionario {'latitud': float, 'longitud': float}.
    """
    # Construir las strings de orígenes y destinos para la API
    # Incluimos el punto de origen en la matriz para calcular las distancias desde/hacia él
    all_points_coords = [f"{origin_coords['latitud']},{origin_coords['longitud']}"]
    for p in points:
        all_points_coords.append(f"{p.latitud},{p.longitud}")

    origins_str = "|".join(all_points_coords)
    destinations_str = origins_str # Queremos la matriz completa (origen a destino, destino a origen)

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origins_str,
        "destinations": destinations_str,
        "mode": "driving",
        "key": api_key
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Lanza una excepción para errores HTTP
        data = response.json()

        if data['status'] == 'OK':
            distance_matrix = []
            for row_data in data['rows']:
                row_distances = []
                for element in row_data['elements']:
                    if element['status'] == 'OK':
                        row_distances.append(element['distance']['value'] / 1000) # Convertir a KM
                    else:
                        row_distances.append(float('inf')) # Si no hay ruta, distancia infinita
                distance_matrix.append(row_distances)
            return distance_matrix
        else:
            print(f"Error en Distance Matrix API: {data['status']} - {data.get('error_message', '')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión con la API de Google Maps: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error al decodificar la respuesta JSON de la API: {e}")
        return None

# --- PARTE 2: Algoritmo de Optimización (TSP Solver) ---
def solve_tsp(distance_matrix, num_points_entrega, start_index=0):
    """
    Resuelve el Problema del Viajante (TSP) para encontrar la ruta más corta.
    'distance_matrix': Matriz de distancias en KM (ya incluye el punto de inicio/fin).
    'num_points_entrega': Número de puntos de entrega reales (sin contar el origen).
    'start_index': El índice del punto de inicio/fin en la distance_matrix (generalmente 0).

    Devuelve: (ruta_optima_indices, distancia_total_km)
    """
    if not distance_matrix or num_points_entrega == 0:
        return [], 0.0

    # Los índices de los puntos de entrega reales, excluyendo el origen (que está en el índice 0)
    delivery_indices = list(range(1, num_points_entrega + 1))

    min_distance = float('inf')
    best_route = []

    # Generar todas las permutaciones de los puntos de entrega
    # ¡CUIDADO! Esto es inviable para más de ~10-12 puntos.
    # Para más puntos, necesitarás algoritmos heurísticos (Recocido Simulado, Genéticos, etc.).
    for permutation in itertools.permutations(delivery_indices):
        current_route_indices = [start_index] + list(permutation) + [start_index] # Origen -> Puntos -> Origen
        current_distance = 0.0

        for i in range(len(current_route_indices) - 1):
            origin_idx = current_route_indices[i]
            dest_idx = current_route_indices[i+1]
            segment_distance = distance_matrix[origin_idx][dest_idx]
            if segment_distance == float('inf'): # Si una ruta es imposible
                current_distance = float('inf')
                break
            current_distance += segment_distance

        if current_distance < min_distance:
            min_distance = current_distance
            best_route = current_route_indices

    return best_route, min_distance

# --- PARTE 3: Cálculos de Consumo ---
AUTO_RENDIMIENTO_KM_POR_LITRO = 12

def calculate_fuel_cost(total_distance_km):
    """
    Calcula el consumo de bencina en litros.
    """
    if total_distance_km == float('inf'):
        return float('inf')
    return total_distance_km / AUTO_RENDIMIENTO_KM_POR_LITRO