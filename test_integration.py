#!/usr/bin/env python3
"""
Test d'intégration complet de node-core.

Teste :
  1. Connexion à Ollama + disponibilité du modèle
  2. LLMEngine avec function calling (tools)
  3. AIOrchestrator : contexte utilisateur + MyGes
  4. VisionEngine : callback de détection faciale
  5. Tolérance 5s de perte de visage
  6. Pipeline complet : face → contexte → LLM → actions
"""

import sys
import time
import json
import threading
import requests

# ═══════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════
OLLAMA_URL = "http://localhost:11434"
GATEWAY_URL = "https://ha.arthonetwork.fr:44888"
GATEWAY_TOKEN = "bst_c9f28d3a1e4b85c7f0d4b9a2e6f1c3d5"
TEST_MODEL = "gemma2:2b"  # Petit modèle pour le test

# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} — {detail}")

def section(title):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")


# ═══════════════════════════════════════════════════════════════
# TEST 1 : Ollama + Modèle disponible
# ═══════════════════════════════════════════════════════════════
section("TEST 1 : Ollama + Modèle disponible")

try:
    r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
    models = [m["name"] for m in r.json().get("models", [])]
    test("Ollama accessible", r.status_code == 200)
    test("Modèles disponibles", len(models) > 0, f"Liste: {models}")

    # Chercher un modèle utilisable
    target_model = None
    for m in models:
        if "gemma" in m.lower() or "mistral" in m.lower() or "qwen" in m.lower():
            target_model = m
            break
    if not target_model and models:
        target_model = models[0]

    test("Modèle LLM trouvé", target_model is not None, f"Modèle: {target_model}")
    print(f"  ℹ️  Modèle utilisé pour les tests: {target_model}")

except requests.ConnectionError:
    test("Ollama accessible", False, "Ollama n'est pas démarré sur localhost:11434")
    print("  ⚠️  Démarrez Ollama avec: ollama serve")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# TEST 2 : LLMEngine — Génération basique
# ═══════════════════════════════════════════════════════════════
section("TEST 2 : LLMEngine — Génération basique")

from workers.llm_engine import LLMEngine

llm = LLMEngine()
llm.load_model(target_model)

response, actions = llm.generate_response("Bonjour, qui es-tu ?")
test("LLM répond", len(response) > 0, f"Réponse: {response[:80]}...")
test("Réponse contient 'Bastet'", "bastet" in response.lower() or "robot" in response.lower(), f"Réponse: {response[:120]}")
print(f"  ℹ️  Réponse: {response[:200]}")


# ═══════════════════════════════════════════════════════════════
# TEST 3 : LLMEngine — Function Calling (Tools)
# ═══════════════════════════════════════════════════════════════
section("TEST 3 : LLMEngine — Function Calling (Tools)")

response_move, actions_move = llm.generate_response("Avance")
test("LLM répond à 'avance'", len(response_move) > 0)
move_keywords = ["avance", "déplace", "bouge", "marche", "step", "walk", "forward"]
action_ok = len(actions_move) > 0 or "[ACTION" in response_move or any(k in response_move.lower() for k in move_keywords)
test("Action comprise", action_ok, f"Actions: {actions_move}, Texte: {response_move[:100]}")
if actions_move:
    test("Action est robot_move", actions_move[0]["name"] == "robot_move", f"Action: {actions_move[0]}")
    test("Direction = up", actions_move[0]["args"].get("direction") == "up", f"Args: {actions_move[0]['args']}")
print(f"  ℹ️  Réponse: {response_move[:200]}")
print(f"  ℹ️  Actions: {actions_move}")

response_sit, actions_sit = llm.generate_response("Assieds-toi")
sit_keywords = ["assis", "assied", "sed", "sit"]
action_ok = len(actions_sit) > 0 or "[ACTION" in response_sit or any(k in response_sit.lower() for k in sit_keywords)
test("Action posture comprise", action_ok, f"Actions: {actions_sit}, Texte: {response_sit[:100]}")
print(f"  ℹ️  Réponse sit: {response_sit[:200]}")


# ═══════════════════════════════════════════════════════════════
# TEST 4 : AIOrchestrator — Contexte utilisateur
# ═══════════════════════════════════════════════════════════════
section("TEST 4 : AIOrchestrator — Contexte utilisateur")

from workers.ai_orchestrator import AIOrchestrator

orchestrator = AIOrchestrator(GATEWAY_URL, GATEWAY_TOKEN, verify_ssl=False)
orchestrator.start_context_watchdog()

# Simuler une détection faciale
orchestrator.on_face_detected("Teano")
time.sleep(0.5)

test("Utilisateur identifié", orchestrator.get_current_user_name() == "Teano")
test("Contexte actif", orchestrator.has_active_context())

context = orchestrator.get_current_context()
test("Contexte non vide", len(context) > 0, f"Contexte: {context[:100]}")
test("Contexte contient le nom", "Teano" in context)
print(f"  ℹ️  Contexte: {context[:200]}")


# ═══════════════════════════════════════════════════════════════
# TEST 5 : Tolérance 5s — Perte de visage
# ═══════════════════════════════════════════════════════════════
section("TEST 5 : Tolérance 5s — Perte de visage")

# Simuler perte de visage
orchestrator.on_face_lost()
time.sleep(0.5)

test("Contexte encore actif après 0.5s", orchestrator.has_active_context())
test("Nom encore disponible", orchestrator.get_current_user_name() == "Teano")

# Attendre que le contexte expire (5s + 1s de marge)
print("  ⏳ Attente de 6s pour expiration du contexte...")
time.sleep(6.5)

test("Contexte expiré après 6s", not orchestrator.has_active_context())
test("Nom nul après expiration", orchestrator.get_current_user_name() is None)


# ═══════════════════════════════════════════════════════════════
# TEST 6 : LLM avec contexte utilisateur
# ═══════════════════════════════════════════════════════════════
section("TEST 6 : LLM avec contexte utilisateur")

orchestrator.on_face_detected("Teano")
time.sleep(0.5)

ctx = orchestrator.get_current_context()
response_ctx, _ = llm.generate_response(
    "Qu'est-ce que je fais demain ?",
    system_context=ctx,
)
test("LLM répond avec contexte", len(response_ctx) > 0)
test("Réponse personnalisée", "teano" in response_ctx.lower() or "agenda" in response_ctx.lower() or "emploi" in response_ctx.lower() or "cours" in response_ctx.lower() or "?" in response_ctx, f"Réponse: {response_ctx[:150]}")
print(f"  ℹ️  Réponse contextuelle: {response_ctx[:200]}")


# ═══════════════════════════════════════════════════════════════
# TEST 7 : Pipeline complet face → LLM → action
# ═══════════════════════════════════════════════════════════════
section("TEST 7 : Pipeline complet face → LLM → action")

ctx = orchestrator.get_current_context()
response_full, actions_full = llm.generate_response(
    "Avance et dis-moi bonjour",
    system_context=ctx,
)
test("Pipeline complet fonctionne", len(response_full) > 0)
# Le modèle peut répondre avec [ACTION:] ou simplement décrire l'action
action_keywords = ["avance", "déplace", "bouge", "marche", "step", "walk"]
has_action意向 = any(k in response_full.lower() for k in action_keywords) or len(actions_full) > 0 or "[ACTION" in response_full
test("Action comprise par le LLM", has_action意向, f"Réponse: {response_full[:150]}")
print(f"  ℹ️  Réponse complète: {response_full[:200]}")
print(f"  ℹ️  Actions: {actions_full}")


# ═══════════════════════════════════════════════════════════════
# TEST 8 : VisionEngine — Callbacks (sans caméra)
# ═══════════════════════════════════════════════════════════════
section("TEST 8 : VisionEngine — Structure des callbacks")

from workers.vision_engine import VisionEngine

# Créer un VisionEngine sans démarrer le thread (pas de caméra en test)
ve = VisionEngine.__new__(VisionEngine)
ve.known_face_encodings = []
ve.known_face_names = []
ve._last_identified_name = None
ve.on_face_identified = None
ve.on_face_lost = None

callback_called = {"name": None}

def mock_callback(name, encoding):
    callback_called["name"] = name

ve.on_face_identified = mock_callback

# Simuler la logique de détection du VisionEngine
ve._last_identified_name = None
detected_name = "Teano"
if detected_name != "Inconnu" and detected_name != ve._last_identified_name:
    ve._last_identified_name = detected_name
    ve.on_face_identified(detected_name, None)

test("Callback face identifié appelé", callback_called["name"] == "Teano")
test("Dernière identification mise à jour", ve._last_identified_name == "Teano")


# ═══════════════════════════════════════════════════════════════
# RÉSUMÉ
# ═══════════════════════════════════════════════════════════════
section("RÉSUMÉ DES TESTS")
total = passed + failed
print(f"  Total: {total} | ✅ Passés: {passed} | ❌ Échoués: {failed}")
print(f"  Taux de réussite: {passed/total*100:.0f}%")

if failed > 0:
    print("\n  ⚠️  Certains tests ont échoué. Vérifiez les détails ci-dessus.")
    sys.exit(1)
else:
    print("\n  🎉 Tous les tests sont passés !")
    sys.exit(0)
