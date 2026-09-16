"""Tests unitaires du routeur d'intention (app/ai/agents/intent_router.py, étape 5)."""
import pytest

from app.ai.agents.intent_router import classify_intent
from app.ai.agents.types import AgentType


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Rappelle-moi demain à 10h de payer la facture", AgentType.AUTOMATION),
        ("Ajoute un rendez-vous vendredi", AgentType.AUTOMATION),
        ("N'oublie pas d'appeler le client", AgentType.AUTOMATION),
        ("Résume-moi ce texte", AgentType.PRODUCTIVITY),
        ("Traduis ce paragraphe en anglais", AgentType.PRODUCTIVITY),
        ("Bonjour, comment vas-tu ?", AgentType.CONVERSATION),
        ("Quelle est la capitale du Cameroun ?", AgentType.CONVERSATION),
    ],
)
def test_classify_intent(text, expected):
    assert classify_intent(text) == expected
