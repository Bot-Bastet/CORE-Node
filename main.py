import sys

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass  # old python versions

import asyncio
import threading
from ui.app_window import CoreNodeApp
from network.gateway_client import GatewayClient
from workers.audio_engine import AudioEngine
from workers.llm_engine import LLMEngine
from workers.vision_engine import VisionEngine
from updater import start_update_check_thread


def run_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


if __name__ == "__main__":
    audio_engine = AudioEngine()
    llm_engine = LLMEngine()
    vision_engine = VisionEngine()

    # Initialisation de l'UI
    app = CoreNodeApp(audio_engine, llm_engine, vision_engine)

    # Vérification des mises à jour en arrière-plan (2s après le démarrage)
    start_update_check_thread()

    # Création du client réseau
    # L'IP et le Token pourront être récupérés depuis l'UI ou un config file plus tard
    gateway_client = GatewayClient(
        app_instance=app,
        gateway_url="wss://ha.arthonetwork.fr:44888/ws/node",
        token="bst_c9f28d3a1e4b85c7f0d4b9a2e6f1c3d5",
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
