// static/js/main.js

let map;
let markers = [];
let directionsService = null;
let directionsRenderer = null;

/**
 * Inicializa el mapa de Google.
 * Usado como callback por la API de Google Maps (initMap).
 */
function initMap() {
    console.log("initMap llamado");

    // Centro por defecto: Concepción
    let center = { lat: -36.827, lng: -73.050 };

    if (typeof origen_coords !== "undefined" && origen_coords && origen_coords.lat && origen_coords.lng) {
        center = { lat: origen_coords.lat, lng: origen_coords.lng };
    } else if (Array.isArray(puntos_entrega_data) && puntos_entrega_data.length > 0) {
        center = {
            lat: puntos_entrega_data[0].latitud,
            lng: puntos_entrega_data[0].longitud
        };
    }

    map = new google.maps.Map(document.getElementById("map"), {
        center: center,
        zoom: 12
    });

    // Inicializamos servicios de Directions
    directionsService = new google.maps.DirectionsService();
    directionsRenderer = new google.maps.DirectionsRenderer({
        suppressMarkers: true  // usamos nuestros propios marcadores
    });
    directionsRenderer.setMap(map);

    renderPuntosEntrega();
}

/**
 * Dibuja el origen, los puntos de entrega y la ruta usando Directions API.
 * Ahora la ruta es: ORIGEN → puntos → ORIGEN.
 */
function renderPuntosEntrega() {
    clearMap();

    const bounds = new google.maps.LatLngBounds();
    const path = [];

    let originPos = null;

    // 1) Dibujar origen si existe
    if (typeof origen_coords !== "undefined" && origen_coords && origen_coords.lat && origen_coords.lng) {
        originPos = { lat: origen_coords.lat, lng: origen_coords.lng };

        const originMarker = new google.maps.Marker({
            position: originPos,
            map: map,
            label: "O",   // Origen
            title: "Origen del recorrido"
        });

        markers.push(originMarker);
        path.push(originPos);
        bounds.extend(originPos);
    }

    // 2) Dibujar puntos de entrega
    if (Array.isArray(puntos_entrega_data) && puntos_entrega_data.length > 0) {

        const anyOrden = puntos_entrega_data.some(
            (p) => p.orden_optimo !== null && p.orden_optimo !== undefined
        );

        const puntos = [...puntos_entrega_data];

        if (anyOrden) {
            puntos.sort((a, b) => {
                if (a.orden_optimo == null) return 1;
                if (b.orden_optimo == null) return -1;
                return a.orden_optimo - b.orden_optimo;
            });
        }

        puntos.forEach((p, index) => {
            const position = { lat: p.latitud, lng: p.longitud };

            const labelText = anyOrden && p.orden_optimo
                ? String(p.orden_optimo)
                : String(index + 1);

            const marker = new google.maps.Marker({
                position: position,
                map: map,
                label: labelText,
                title: `${p.nombre} - ${p.direccion}`
            });

            markers.push(marker);
            path.push(position);
            bounds.extend(position);
        });
    }

    // 🔁 3) Volver al origen al final del recorrido (si hay origen y al menos un punto)
    if (originPos && path.length > 1) {
        path.push(originPos);
        bounds.extend(originPos);
    }

    // Ajustar mapa para que se vean todos los puntos
    if (!bounds.isEmpty()) {
        map.fitBounds(bounds);
    }

    // 4) Dibujar ruta real por calles
    if (path.length > 1) {
        drawRouteWithDirectionsAPI(path);
    }
}

/**
 * Calcula y dibuja la ruta usando la Directions API de Google.
 * path: arreglo de {lat, lng} en el orden que queremos visitar.
 * Aquí ya viene: ORIGEN → puntos → ORIGEN.
 */
function drawRouteWithDirectionsAPI(path) {
    if (!directionsService || !directionsRenderer) return;
    if (!Array.isArray(path) || path.length < 2) return;

    const origin = path[0];
    const destination = path[path.length - 1];

    const waypoints = path.slice(1, -1).map((pos) => ({
        location: pos,
        stopover: true
    }));

    const request = {
        origin: origin,
        destination: destination,
        waypoints: waypoints,
        travelMode: google.maps.TravelMode.DRIVING,
        optimizeWaypoints: false  // el orden ya viene optimizado del backend
    };

    directionsService.route(request, (result, status) => {
        console.log("Directions status:", status);
        if (status === "OK" || status === google.maps.DirectionsStatus.OK) {
            directionsRenderer.setDirections(result);
        } else {
            console.error("Error en Directions API:", status);
            // Si falla Directions, igual se ven los marcadores
        }
    });
}

/**
 * Limpia marcadores y ruta del mapa, pero deja el mapa creado.
 */
function clearMap() {
    if (markers.length > 0) {
        markers.forEach((m) => m.setMap(null));
        markers = [];
    }

    if (directionsRenderer) {
        directionsRenderer.set("directions", null);
    }
}

/**
 * Muestra u oculta el input de dirección personalizada cuando
 * se elige "Otra dirección..." en el select de origen.
 */
function toggleOrigenCustom() {
    const select = document.getElementById("origen_predefinido");
    const wrapper = document.getElementById("origen_custom_wrapper");

    if (!select || !wrapper) return;

    if (select.value === "custom") {
        wrapper.style.display = "block";
    } else {
        wrapper.style.display = "none";
    }
}

// Exponemos funciones globalmente para que el HTML pueda llamarlas
window.initMap = initMap;
window.clearMap = clearMap;
window.toggleOrigenCustom = toggleOrigenCustom;
