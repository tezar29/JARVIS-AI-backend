"""Génération de la réponse à un énoncé utilisateur.

⚠️ Stub temporaire : renvoie une réponse simple pour permettre de
tester le module vocal de bout en bout (STT → réponse → TTS) sans
attendre l'orchestrateur multi-agent complet. Cette fonction sera
remplacée à l'étape 5 par un appel à `ai/agents/router.py`
(analyse d'intention → agent spécialisé → LLM → function calling).
"""


async def generate_response(user_text: str, language: str = "fr") -> str:
    text = user_text.strip().lower()

    if not text:
        return "Je n'ai rien entendu, pouvez-vous répéter ?"

    if "bonjour" in text or "salut" in text:
        return "Bonjour Clarence. Comment puis-je vous aider aujourd'hui ?"

    if "heure" in text:
        return "Je n'ai pas encore accès à l'horloge système — ce sera branché avec le module d'automatisation."

    return (
        f"J'ai bien reçu : « {user_text} ». "
        "Mon moteur de raisonnement complet arrive à l'étape 5 — pour l'instant "
        "je ne fais que confirmer la boucle vocale."
    )
