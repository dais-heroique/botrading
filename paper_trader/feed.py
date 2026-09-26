import time
import socketio


class NewTokenFeed:
    URL = "https://sol.shrine.trade"

    def __init__(self, protocols=None):
        self.protocols = protocols or ["PUMPFUN", "PUMPSWAP"]
        self.sio = socketio.Client(reconnection=True, logger=False, engineio_logger=False)

    def stream(self, on_token):
        @self.sio.on("new_token")
        def handle(token):
            token["_received_at"] = time.time()
            on_token(token)

        self.sio.connect(self.URL, transports=["websocket", "polling"])
        self.sio.emit("subscribe_new_tokens", {"protocols": self.protocols})
        try:
            self.sio.wait()
        finally:
            self.sio.disconnect()
