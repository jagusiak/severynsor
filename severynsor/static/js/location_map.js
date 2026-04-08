document.addEventListener("DOMContentLoaded", function () {
    // Dynamically inject Referrer-Policy to satisfy OpenStreetMap 403 blocks
    let meta = document.querySelector('meta[name="referrer"]');
    if (!meta) {
        meta = document.createElement('meta');
        meta.name = "referrer";
        meta.content = "strict-origin-when-cross-origin";
        document.head.appendChild(meta);
    } else {
        meta.content = "strict-origin-when-cross-origin";
    }

    const latInput = document.getElementById("id_latitude");
    const lonInput = document.getElementById("id_longitude");

    if (!latInput || !lonInput) return;

    const mapDiv = document.createElement("div");
    mapDiv.id = "location-picker-map";
    mapDiv.style.width = "100%";
    mapDiv.style.height = "400px";
    mapDiv.style.marginBottom = "1rem";
    mapDiv.style.borderRadius = "8px";
    mapDiv.style.zIndex = "1";

    latInput.parentNode.parentNode.insertBefore(mapDiv, latInput.parentNode);

    const initLat = parseFloat(latInput.value) || 51.505;
    const initLon = parseFloat(lonInput.value) || -0.09;

    let zoomLevel = 13;
    if (!latInput.value || !lonInput.value) {
        zoomLevel = 2; // Zoom out if no point is set
    }

    const map = L.map('location-picker-map').setView([initLat, initLon], zoomLevel);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    let marker = L.marker([initLat, initLon]).addTo(map);
    if (!latInput.value || !lonInput.value) {
        map.removeLayer(marker);
    }

    map.on('click', function (e) {
        const lat = e.latlng.lat.toFixed(6);
        const lon = e.latlng.lng.toFixed(6);

        latInput.value = lat;
        lonInput.value = lon;

        if (!map.hasLayer(marker)) {
            marker.addTo(map);
        }
        marker.setLatLng(e.latlng);
    });
});
