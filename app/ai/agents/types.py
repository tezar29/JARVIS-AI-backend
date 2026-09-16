from enum import Enum


class AgentType(str, Enum):
    CONVERSATION = "conversation"
    AUTOMATION = "automation"
    PRODUCTIVITY = "productivity"
    # VISION et MEMORY ne sont pas routés depuis le texte : VISION est
    # déclenché par la présence d'une image (étape 8), MEMORY est un
    # service transverse utilisé par tous les agents (étape 6).
