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
};