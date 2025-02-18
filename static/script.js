var ws = new WebSocket("ws://" + window.location.host + "/ws");

ws.onmessage = function(event) {
    var data = JSON.parse(event.data);
    document.getElementById("callsign").innerText = data.callsign;
    document.getElementById("altitude").innerText = data.altitude;
    document.getElementById("distance").innerText = data.distance;
    document.getElementById("type").innerText = data.type;
    document.getElementById("bearing").innerText = data.bearing;
    document.getElementById("timestamp").innerText = data.timestamp;
    document.getElementById("message").innerText = data.message_num;
    document.getElementById("registration").innerText = data.registration;
    document.getElementById("callsign_low").innerText = data.callsign_low;
    document.getElementById("altitude_low").innerText = data.altitude_low;
    document.getElementById("distance_low").innerText = data.distance_low;
    document.getElementById("type_low").innerText = data.type_low;
    document.getElementById("bearing_low").innerText = data.bearing_low;
    document.getElementById("timestamp_low").innerText = data.timestamp_low;
    document.getElementById("message_low").innerText = data.message_num_low;
    document.getElementById("registration_low").innerText = data.registration_low;
};