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
from workers.ai_orchestrator import AIOrchestrator
from updater import start_update_check_thread


def run_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


if __name__ == "__main__":
    # ─── Création des moteurs ───────────────────────────────
    audio_engine = AudioEngine()
    llm_engine = LLMEngine()
    vision_engine = VisionEngine()

    # ─── Création de l'orchestrateur IA ─────────────────────
    # Relie : face recognition → MyGes context → LLM → Gateway
    orchestrator = AIOrchestrator(
        gateway_url="https://ha.arthonetwork.fr:44888",
        gateway_token="bst_c9f28d3a1e4b85c7f0d4b9a2e6f1c3d5",
        verify_ssl=False,
    )
    orchestrator.start_context_watchdog()

    # ─── Initialisation de l'UI ─────────────────────────────
    app = CoreNodeApp(audio_engine, llm_engine, vision_engine, orchestrator)

    # ─── Liaison VisionEngine → Orchestrateur ───────────────
    # Quand un visage est identifié → l'orchestrateur charge le contexte MyGes
    vision_engine.on_face_identified = orchestrator.on_face_detected
    vision_engine.on_face_lost = orchestrator.on_face_lost

    # ─── Liaison Orchestrateur → UI (logs) ──────────────────
    orchestrator.on_log = app.add_log
    orchestrator.on_user_identified = lambda name: app.add_log(
        f"👤 Utilisateur identifié : {name} — chargement contexte..."
    )
    orchestrator.on_user_lost = lambda: app.add_log(
        "👤 Utilisateur perdu — contexte maintenu 5s"
    )

    # ─── Liaison Orchestrateur → LLM (contexte) ─────────────
    # Le LLM reçoit automatiquement le contexte de l'orchestrateur
    app.orchestrator = orchestrator
    app.llm_engine = llm_engine

    # ─── Vérification des mises à jour ──────────────────────
    start_update_check_thread()

    # ─── Création du client réseau ──────────────────────────
    gateway_client = GatewayClient(
        app_instance=app,
        gateway_url="wss://ha.arthonetwork.fr:44888/ws/node",
        token="bst_c9f28d3a1e4b85c7f0d4b9a2e6f1c3d5",
    )
    app.gateway_client = gateway_client

    # ─── Démarrage de la boucle asynchrone ──────────────────
    loop = asyncio.new_event_loop()
    app.loop = loop
    t = threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True)
    t.start()

    # ─── Connexion WebSocket ────────────────────────────────
    asyncio.run_coroutine_threadsafe(gateway_client.connect(), loop)

    # ─── Lancement de l'UI ──────────────────────────────────
    app.mainloop()
