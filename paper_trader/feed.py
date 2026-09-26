import time
import socketio


class NewTokenFeed:
    URL = "https://sol.shrine.trade"

    def __init__(self, protocols=None):
        self.protocols = protocols or ["PUMPFUN", "PUMPSWAP"]
        self.sio = socketio.Client(
            reconnection=True,
            logger=False,
            engineio_logger=False,
        )

    def stream(self, on_token):
        @self.sio.on("new_token")
        def handle(token):
            if not isinstance(token, dict):
                return
            token["_received_at"] = time.time()
            try:
                on_token(token)
            except Exception as exc:
                print(
                    f"[paper] token handler error: {type(exc).__name__}: {exc}",
                    flush=True,
                )

        self.sio.connect(
            self.URL,
            transports=["websocket", "polling"],
            wait_timeout=15,
        )
        self.sio.emit(
            "subscribe_new_tokens",
            {"protocols": self.protocols},
        )
        print(
            f"[paper] live feed connected; protocols={','.join(self.protocols)}",
            flush=True,
        )
        try:
            self.sio.wait()
        finally:
            self.sio.disconnect()
