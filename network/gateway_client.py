import asyncio
import websockets
import json
import ssl

class GatewayClient:
    def __init__(self, app_instance, gateway_url: str, token: str):
        self.app = app_instance
        self.gateway_url = gateway_url
        self.token = token
        self.websocket = None
        self._reconnect_event = asyncio.Event()

    def force_reconnect(self):
        self._reconnect_event.set()

    async def connect(self):
        headers = {"X-API-Token": self.token}
        
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        while True:
            self._reconnect_event.clear()
            self.app.update_connection_status(False)
            
            # Utiliser la gateway_url fraîche de l'UI
            url_to_use = self.app.gateway_url
            if "?token=" not in url_to_use:
                url_to_use = f"{url_to_use}?token={self.token}"
            use_ssl = ssl_context if url_to_use.startswith("wss") else None
            
            try:
                self.app.add_log(f"Connexion à {url_to_use}...")
                
                async with websockets.connect(url_to_use, extra_headers=headers, ssl=use_ssl) as ws:
                    self.websocket = ws
                    self.app.update_connection_status(True)
                    self.app.add_log("✅ Connecté au Gateway.")
                    
                    listen_task = asyncio.create_task(self.listen_loop())
                    event_task = asyncio.create_task(self._reconnect_event.wait())
                    
                    done, pending = await asyncio.wait(
                        [listen_task, event_task], 
                        return_when=asyncio.FIRST_COMPLETED
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

    async def listen_loop(self):
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    if data.get("type") == "feature_ack":
                        self.app.handle_feature_ack(data.get("feature"), data.get("state"), data.get("status"))
                    elif data.get("type") == "chat":
                        prompt = data.get("text", "")
                        context = data.get("context", "")
                        self.app.add_log(f"📥 Message chat reçu : '{prompt}'")
                        self.app.add_gateway_log(f"👤 Humain (via robot) :\n\"{prompt}\"")
                        
                        # Générer la réponse de façon non-bloquante dans un thread
                        async def process_llm_request():
                            try:
                                if self.app.llm_engine:
                                    self.app.add_log("🧠 Inférence LLM en cours...")
                                    response_text = await asyncio.to_thread(
                                        self.app.llm_engine.generate_response, 
                                        prompt, 
                                        context=context
                                    )
                                else:
                                    response_text = "Moteur LLM non disponible."
                                
                                self.app.add_log(f"📤 Envoi de la réponse chat : '{response_text}'")
                                self.app.add_gateway_log(f"🤖 Bastet :\n\"{response_text}\"")
                                
                                response_msg = {
                                    "type": "chat_response",
                                    "text": response_text
                                }
                                await self.send_message(json.dumps(response_msg))
                            except Exception as e:
                                self.app.add_log(f"❌ Erreur inférence/envoi : {e}")
                        
                        asyncio.create_task(process_llm_request())
                        
                except json.JSONDecodeError:
                    pass # Message non-JSON (audio, texte brut, etc)
        except websockets.exceptions.ConnectionClosed:
            self.app.update_connection_status(False)
            self.app.add_log("❌ Déconnecté par la Gateway.")

    def send_feature_request(self, feature: str, state: bool):
        req = {
            "type": "feature_request",
            "feature": feature,
            "state": state
        }
        if self.websocket and hasattr(self.app, 'loop'):
            asyncio.run_coroutine_threadsafe(self.send_message(json.dumps(req)), self.app.loop)

    async def send_message(self, message: str):
        if self.websocket:
            await self.websocket.send(message)
            self.app.add_log(f"📤 Envoyé ({len(message)} octets)")
