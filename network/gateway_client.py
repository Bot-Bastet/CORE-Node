import asyncio
import websockets
import json
import ssl
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def ws_url_to_rest(ws_url: str) -> str:
    """Convertit une URL WebSocket en URL REST de base."""
    url = ws_url.replace("wss://", "https://").replace("ws://", "http://")
    # Retirer le path /ws/node pour garder la base
    for suffix in ["/ws/node", "/ws/app", "/ws/robot"]:
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    return url


class GatewayClient:
    def __init__(self, app_instance, gateway_url: str, token: str):
        self.app = app_instance
        self.gateway_url = gateway_url
        self.token = token
        self.websocket = None
        self._reconnect_event = asyncio.Event()
        self._rest_base = ws_url_to_rest(gateway_url)
        self._rest_headers = {"X-API-Token": token}

    def force_reconnect(self):
        self._reconnect_event.set()

    # ──────────────────────────────────────────────
    # REST helpers (appelés depuis threads séparés)
    # ──────────────────────────────────────────────
    def rest_post(self, path: str, payload: dict) -> dict | None:
        """Effectue un POST REST synchrone vers la Gateway."""
        url = f"{self._rest_base}{path}"
        try:
            headers = {"X-API-Token": self.app.gateway_token}
            r = requests.post(
                url,
                json=payload,
                headers=headers,
                verify=self.app.verify_ssl,
                timeout=8,
            )
            if r.status_code < 300:
                try:
                    return r.json()
                except Exception:
                    return {"status": "ok"}
            else:
                self.app.add_log(
                    f"⚠️ REST {path} → HTTP {r.status_code}: {r.text[:120]}"
                )
                return None
        except Exception as e:
            self.app.add_log(f"❌ REST {path} → {e}")
            return None

    def rest_get(self, path: str) -> dict | None:
        """Effectue un GET REST synchrone vers la Gateway."""
        url = f"{self._rest_base}{path}"
        try:
            headers = {"X-API-Token": self.app.gateway_token}
            r = requests.get(
                url, headers=headers, verify=self.app.verify_ssl, timeout=8
            )
            if r.status_code < 300:
                return r.json()
            else:
                self.app.add_log(f"⚠️ REST GET {path} → HTTP {r.status_code}")
                return None
        except Exception as e:
            self.app.add_log(f"❌ REST GET {path} → {e}")
            return None

    # ──────────────────────────────────────────────
    # WebSocket – connexion principale
    # ──────────────────────────────────────────────
    async def connect(self):
        while True:
            # Configurer le contexte SSL de manière sécurisée ou non selon les paramètres
            if getattr(self.app, "verify_ssl", True):
                try:
                    import certifi

                    ssl_context = ssl.create_default_context(cafile=certifi.where())
                except ImportError:
                    ssl_context = ssl.create_default_context()
            else:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            self._reconnect_event.clear()
            self.app.update_connection_status(False)

            url_to_use = self.app.gateway_url
            token_to_use = self.app.gateway_token
            if "?token=" not in url_to_use:
                url_to_use = f"{url_to_use}?token={token_to_use}"
            use_ssl = ssl_context if url_to_use.startswith("wss") else None

            # Mettre à jour la base REST si l'URL a changé depuis l'UI
            self._rest_base = ws_url_to_rest(self.app.gateway_url)

            # Configurer le VisionEngine avec l'hôte courant
            try:
                parts = self.app.gateway_url.split("://")[-1].split("/")[0].split(":")
                host = parts[0]
                rest_proto = (
                    "https" if self.app.gateway_url.startswith("wss") else "http"
                )
                port = (
                    parts[1]
                    if len(parts) > 1
                    else ("44888" if rest_proto == "https" else "80")
                )

                rest_url = f"{rest_proto}://{host}:{port}"
                rtsp_url = f"rtsp://{host}:48554/robot/cam1"

                if self.app.vision_engine:
                    self.app.vision_engine.gateway_url = rest_url
                    self.app.vision_engine.rtsp_url = rtsp_url
                    self.app.vision_engine.token = self.token
            except Exception as ex:
                self.app.add_log(f"⚠️ Erreur config VisionEngine: {ex}")

            try:
                self.app.add_log(f"Connexion à {url_to_use}...")
                import inspect

                try:
                    sig = inspect.signature(websockets.connect)
                    use_additional = "additional_headers" in sig.parameters
                except Exception:
                    use_additional = True

                headers = {"X-API-Token": self.app.gateway_token}
                kwargs = {}
                if use_additional:
                    kwargs["additional_headers"] = headers
                else:
                    kwargs["extra_headers"] = headers

                async with websockets.connect(url_to_use, ssl=use_ssl, **kwargs) as ws:
                    self.websocket = ws
                    self.app.update_connection_status(True)
                    self.app.add_log("✅ Connecté à la Gateway.")

                    listen_task = asyncio.create_task(self.listen_loop())
                    event_task = asyncio.create_task(self._reconnect_event.wait())

                    done, pending = await asyncio.wait(
                        [listen_task, event_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if event_task in done:
                        self.app.add_log("⚠️ Déconnexion forcée par l'utilisateur.")
                        await ws.close()

                    for task in pending:
                        task.cancel()

            except Exception as e:
                self.app.add_log(f"⚠️ Erreur: {e}")
                self.app.add_log("Reconnexion dans 5s...")
                try:
                    await asyncio.wait_for(self._reconnect_event.wait(), timeout=5.0)
                    self.app.add_log("🔄 Reconnexion immédiate demandée.")
                except asyncio.TimeoutError:
                    pass

    # ──────────────────────────────────────────────
    # WebSocket – boucle de réception
    # ──────────────────────────────────────────────
    async def listen_loop(self):
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "")

                    if msg_type == "chat":
                        # Le robot a envoyé un message vocal/textuel → inférence LLM
                        prompt = data.get("text", "")
                        context = data.get("context", "")
                        self.app.add_log(f"📥 Chat reçu : '{prompt}'")
                        self.app.add_gateway_log(f'👤 Humain (via robot) :\n"{prompt}"')
                        asyncio.create_task(self._process_chat(prompt, context))

                    elif msg_type == "request_camera":
                        # Le robot ou l'app demande une caméra → on notifie l'UI
                        cam = data.get("camera", "?")
                        self.app.add_log(f"📷 Flux caméra {cam} demandé.")

                    elif msg_type == "stream_status":
                        cam = data.get("camera", "?")
                        active = data.get("active", False)
                        self.app.add_log(
                            f"📡 Flux caméra {cam} : {'actif' if active else 'inactif'}"
                        )

                    elif msg_type == "feature_request":
                        feature = data.get("feature")
                        state = data.get("state", False)
                        self.app.add_log(
                            f"📥 Demande de prise en charge : {feature} -> {state}"
                        )
                        # Activer localement via l'UI
                        self.app.handle_feature_ack(feature, state, "ok")
                        # Répondre avec un feature_ack à la Gateway
                        asyncio.create_task(
                            self.send_json(
                                {
                                    "type": "feature_ack",
                                    "feature": feature,
                                    "state": state,
                                    "status": "ok",
                                }
                            )
                        )

                    elif msg_type == "feature_ack":
                        self.app.handle_feature_ack(
                            data.get("feature"), data.get("state"), data.get("status")
                        )

                    else:
                        if msg_type not in [
                            "telemetry_diagnostics",
                            "diagnostics",
                            "ping",
                            "pong",
                        ]:
                            # Message générique — on le logue brièvement
                            self.app.add_log(f"📨 Message [{msg_type}] reçu.")

                except json.JSONDecodeError:
                    pass  # Audio binaire ou texte brut, ignoré
        except websockets.exceptions.ConnectionClosed:
            self.app.update_connection_status(False)
            self.app.add_log("❌ Déconnecté par la Gateway.")

    # ──────────────────────────────────────────────
    # Inférence LLM non-bloquante
    # ──────────────────────────────────────────────
    async def _process_chat(self, prompt: str, context: str):
        try:
            if self.app.llm_engine:
                self.app.add_log("🧠 Inférence LLM en cours...")
                response_text = await asyncio.to_thread(
                    self.app.llm_engine.generate_response, prompt, context=context
                )
            else:
                response_text = "Moteur LLM non disponible."

            self.app.add_log(f"📤 Réponse LLM : '{response_text}'")
            self.app.add_gateway_log(f'🤖 Bastet :\n"{response_text}"')

            # Envoi via WebSocket (type chat_response — relayé au robot par la Gateway)
            await self.send_json({"type": "chat_response", "text": response_text})

        except Exception as e:
            self.app.add_log(f"❌ Erreur inférence/envoi : {e}")

    # ──────────────────────────────────────────────
    # Activation / Désactivation des modules IA
    # ──────────────────────────────────────────────
    def send_feature_request(self, feature: str, state: bool):
        """
        Envoie une demande de prise en charge (feature_request) via WebSocket.
        Si la Gateway l'accepte, elle répondra par un 'feature_ack' que nous
        intercepterons dans la boucle listen_loop pour activer le module.
        """
        req = {"type": "feature_request", "feature": feature, "state": state}
        self.send_message_threadsafe(req)

    # ──────────────────────────────────────────────
    # Envoi WebSocket
    # ──────────────────────────────────────────────
    async def send_json(self, payload: dict):
        """Envoie un message JSON via WebSocket."""
        await self.send_message(json.dumps(payload))

    async def send_message(self, message: str):
        if self.websocket:
            await self.websocket.send(message)
            self.app.add_log(f"📤 Envoyé ({len(message)} octets)")

    def send_message_threadsafe(self, payload: dict):
        """Envoie un message JSON depuis un thread non-asyncio."""
        if self.websocket and hasattr(self.app, "loop"):
            asyncio.run_coroutine_threadsafe(self.send_json(payload), self.app.loop)
