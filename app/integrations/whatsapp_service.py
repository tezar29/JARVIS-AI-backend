"""Client WhatsApp Business (Meta Cloud API).

⚠️ Différent de Google Calendar/Gmail : WhatsApp Business ne fonctionne
pas avec un OAuth par utilisateur, mais avec **un numéro d'expéditeur
professionnel unique**, configuré au niveau du serveur
(`WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`) et partagé par
tous les utilisateurs de l'application — c'est le fonctionnement normal
de l'API Business de Meta, pas une simplification de notre part.

⚠️ Limite de la politique WhatsApp : en dehors d'un "template" pré-validé
par Meta, on ne peut envoyer un message libre à un numéro que si celui-ci
a écrit à ce numéro professionnel dans les 24 heures précédentes
("fenêtre de service client"). Ce n'est donc pas encore un canal
d'envoi de messages arbitraires vers n'importe quel contact — utile
pour répondre à une conversation WhatsApp entrante, pas pour prévenir
un tiers à froid.
"""
import httpx

from app.core.config import settings


class WhatsAppIntegrationError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)


async def send_whatsapp_message(to_phone: str, text: str) -> None:
    if not is_configured():
        raise WhatsAppIntegrationError("L'intégration WhatsApp n'est pas configurée côté serveur.")

    url = f"https://graph.facebook.com/v20.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise WhatsAppIntegrationError(
            f"Échec de l'envoi WhatsApp (souvent : le destinataire n'a pas écrit dans les 24h) : {response.text}"
        )
