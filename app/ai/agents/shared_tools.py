"""Outils partagés entre plusieurs agents — pour l'instant, seul
`remember_fact` (mémorisation explicite) est commun à tous."""
from app.ai.llm.schemas import ToolDefinition

REMEMBER_FACT_TOOL = ToolDefinition(
    name="remember_fact",
    description=(
        "Mémorise durablement une information sur l'utilisateur pour les conversations "
        "futures : une préférence, une habitude, un fait personnel qu'il vient de partager "
        "(ex: 'mon anniversaire est le 12 mars', 'je n'aime pas le café'). "
        "N'utilise cet outil que pour des informations qui ont de la valeur à long terme, "
        "pas pour des détails ponctuels sans intérêt futur."
    ),
    parameters={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Le fait à retenir, formulé clairement à la 3e personne (ex: \"Aime le thé, pas le café\").",
            },
            "category": {
                "type": "string",
                "enum": ["fact", "preference", "habit"],
                "description": "Type d'information : fait, préférence, ou habitude observée.",
            },
        },
        "required": ["content"],
    },
)
