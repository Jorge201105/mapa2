var map;
var markers = [];
var directionsService;
var directionsRenderer;

function initMap() {
    // Coordenadas por defecto (Concepción / San Pedro)
    var defaultLat = -36.84;
    var defaultLng = -73.11;

    // Si existen los inputs, tomamos esos valores para centrar el mapa
    var startLatInput = document.getElementById('lat_inicio');
    var startLngInput = document.getElementById('lng_inicio');

    var start_lat = startLatInput ? parseFloat(startLatInput.value) : NaN;
    var start_lng = startLngInput ? parseFloat(startLngInput.value) : NaN;

    var center = {
        lat: isNaN(start_lat) ? defaultLat : start_lat,
        lng: isNaN(start_lng) ? defaultLng : start_lng
    };

    map = new google.maps.Map(document.getElementById('map'), {
        zoom: 12,
        center: center
    });

    directionsService = new google.maps.DirectionsService();
    directionsRenderer = new google.maps.DirectionsRenderer({map: map});

    // Limpiar marcadores y ruta anterior si existen
    clearMarkers();
    directionsRenderer.set('directions', null);

    // Añadir marcadores existentes
    puntos_entrega_data.forEach(function(punto) {
        addMarker(
            {lat: punto.latitud, lng: punto.longitud},
            punto.nombre,
            punto.orden_optimo
        );
    });

    // Si hay puntos para dibujar una ruta (después de la optimización)
    if (puntos_entrega_data.length > 0 && puntos_entrega_data[0].orden_optimo !== null) {
        drawOptimizedRoute();
    }
}

function addMarker(location, title, order) {
    var markerTitle = order !== null ? (order + ". " + title) : title;

    // 🔴 AQUÍ ESTABA EL ERROR: antes tenías google.maps.Map
    var marker = new google.maps.Marker({
        position: location,
        map: map,
        title: markerTitle,
        label: order !== null ? String(order) : '' // número de orden como etiqueta
    });

    markers.push(marker);
}

function clearMarkers() {
    for (var i = 0; i < markers.length; i++) {
        markers[i].setMap(null);
    }
    markers = [];
}

// Para el botón "Limpiar mapa (ruta y marcadores)"
function clearMap() {
    clearMarkers();
    if (directionsRenderer) {
        directionsRenderer.set('directions', null);
    }
}

function drawOptimizedRoute() {
    // Valores por defecto (Concepción) si algo viene vacío
    var defaultLat = -36.84;
    var defaultLng = -73.11;

    var start_lat = parseFloat(document.getElementById('lat_inicio').value) || defaultLat;
    var start_lng = parseFloat(document.getElementById('lng_inicio').value) || defaultLng;
    var punto_inicio = {lat: start_lat, lng: start_lng};

    console.log("Origen usado para la ruta:", punto_inicio);

    // Limpiar ruta anterior
    directionsRenderer.set('directions', null);

    // Filtrar solo los puntos de entrega que tienen un orden óptimo asignado
    var ordered_points = puntos_entrega_data
        .filter(function(p) { return p.orden_optimo !== null; })
        .sort(function(a, b) { return a.orden_optimo - b.orden_optimo; });
    
    if (ordered_points.length === 0) {
        console.log("No hay puntos ordenados, no se dibuja ruta");
        return;
    }

    var waypoints = [];
    for (var i = 0; i < ordered_points.length; i++) {
        waypoints.push({
            location: {lat: ordered_points[i].latitud, lng: ordered_points[i].longitud},
            stopover: true
        });
    }

    var origin = punto_inicio;
    var destination = punto_inicio; // vuelta al origen

    directionsService.route({
        origin: origin,
        destination: destination,
        waypoints: waypoints,
        optimizeWaypoints: false, // La optimización ya la hiciste con tu IA
        travelMode: google.maps.TravelMode.DRIVING
    }, function(response, status) {
        if (status === 'OK') {
            directionsRenderer.setDirections(response);
        } else {
            window.alert('Directions request failed due to ' + status);
            console.error('Directions request failed:', status, response);
        }
    });
}
