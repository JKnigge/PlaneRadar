import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Serve static files (HTML, JS, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Store the latest data
latest_data = {}


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        await websocket.send_text(json.dumps(latest_data))  # Send initial data

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_text(json.dumps(message))


manager = ConnectionManager()


@app.get("/")
async def get_home():
    """Serve the HTML page."""
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep the connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/update")
async def update_data(data: dict):
    """Receive new data via REST API and broadcast to all WebSocket clients."""
    global latest_data
    latest_data = data
    await manager.broadcast(latest_data)
    return {"message": "Data updated"}


# Run the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
