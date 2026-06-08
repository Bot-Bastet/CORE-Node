import asyncio
import threading
import customtkinter as ctk
from ui.app_window import CoreNodeApp
from network.gateway_client import GatewayClient
from workers.audio_engine import AudioEngine
from workers.llm_engine import LLMEngine
from workers.vision_engine import VisionEngine

def run_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == "__main__":
    audio_engine = AudioEngine()
    llm_engine = LLMEngine()
    vision_engine = VisionEngine()

    # Initialisation de l'UI
    app = CoreNodeApp(audio_engine, llm_engine, vision_engine)
    
    # Création du client réseau
    # L'IP et le Token pourront être récupérés depuis l'UI ou un config file plus tard
    gateway_client = GatewayClient(
        app_instance=app,
        gateway_url="ws://127.0.0.1:8001/ws/node",
        token="your-api-token-here"
    )
    app.gateway_client = gateway_client
    
    # Démarrage de la boucle asynchrone dans un thread séparé
    # pour ne pas bloquer l'UI CustomTkinter
    loop = asyncio.new_event_loop()
    app.loop = loop
    t = threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True)
    t.start()
    
    # Connecter le websocket
    asyncio.run_coroutine_threadsafe(gateway_client.connect(), loop)
    
    # Lancement de l'UI (boucle bloquante)
    app.mainloop()
