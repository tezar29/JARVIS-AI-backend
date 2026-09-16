"""Classification d'intention légère, basée sur des mots-clés.

Volontairement rapide et sans appel LLM : le routage doit être quasi
instantané et ne pas dépendre d'une clé API configurée. Une
classification plus fine (via un appel LLM dédié, avec sortie
structurée) pourra remplacer cette heuristique si les faux
routages deviennent un problème en usage réel — pour l'instant, les
catégories sont volontairement larges pour éviter les faux négatifs.
"""
from app.ai.agents.types import AgentType

_AUTOMATION_KEYWORDS = [
    "rappel", "rappelle", "n'oublie pas", "agenda", "rendez-vous",
    "événement", "evenement", "réunion", "reunion", "planifie",
    "reminder", "schedule", "appointment", "remind me",
]

_PRODUCTIVITY_KEYWORDS = [
    "résume", "resume", "résumé", "traduis", "traduction", "translate",
    "note", "notes", "synthétise", "synthetise", "summary", "summarize",
]


def classify_intent(text: str) -> AgentType:
    lowered = text.lower()

    if any(keyword in lowered for keyword in _AUTOMATION_KEYWORDS):
        return AgentType.AUTOMATION

    if any(keyword in lowered for keyword in _PRODUCTIVITY_KEYWORDS):
        return AgentType.PRODUCTIVITY

    return AgentType.CONVERSATION
