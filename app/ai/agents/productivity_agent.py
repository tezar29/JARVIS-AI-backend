from app.ai.agents.base_agent import BaseAgent
from app.ai.agents.shared_tools import REMEMBER_FACT_TOOL

SYSTEM_PROMPT = """Tu es le module productivité de JARVIS. Tu aides Clarence à \
résumer des textes, traduire, prendre des notes claires et structurer des tâches. \
Sois synthétique et structuré (listes à puces quand c'est pertinent). \
Réponds dans la langue demandée par l'utilisateur, ou dans la langue de sa \
requête si aucune langue cible n'est précisée. Si une note contient une \
information personnelle durable sur l'utilisateur, utilise remember_fact \
pour la mémoriser."""


class ProductivityAgent(BaseAgent):
    """Agent dédié aux tâches de productivité : résumés, traduction,
    notes. Pour l'instant purement conversationnel côté productivité
    (pas de persistance des notes/tâches elles-mêmes) — la sauvegarde
    réelle en base (table `notes`, voir schéma de l'étape 1) est prévue
    pour une itération ultérieure une fois les priorités automatisation/
    mémoire posées. Peut mémoriser des faits durables via remember_fact."""

    name = "productivity_agent"
    system_prompt = SYSTEM_PROMPT
    tools = [REMEMBER_FACT_TOOL]
