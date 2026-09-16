# JARVIS AI — Backend (Étape 10 — projet complet)

## Ce qui est livré à cette étape

- Structure FastAPI modulaire (`api/`, `services/`, `models/`, `schemas/`, `core/`, `database/`)
- Authentification complète : inscription, connexion, refresh token, endpoint `/me`
- Sécurité : mots de passe hachés (bcrypt), JWT (access + refresh), config centralisée par variables d'env
- Base de données : SQLAlchemy async + PostgreSQL avec extension **pgvector** prête pour la mémoire vectorielle (étape 6)
- Redis connecté (cache/sessions — utilisation étendue aux étapes suivantes)
- Migrations Alembic (async) avec une première révision (`users`)
- Docker Compose : backend + PostgreSQL (image `pgvector/pgvector`) + Redis
- Tests d'intégration de base (pytest + httpx)

## Démarrage rapide

```bash
cd backend
cp .env.example .env
# Édite .env : renseigne SECRET_KEY (openssl rand -hex 32) et tes clés IA si tu les as déjà

docker compose up --build
```

L'API est alors disponible sur http://localhost:8000, documentation interactive sur http://localhost:8000/docs.

## Appliquer les migrations

```bash
docker compose exec backend alembic upgrade head
```

## Lancer les tests

```bash
docker compose exec backend pytest -v
```

## Endpoints disponibles

| Méthode | URL | Description |
|---|---|---|
| GET | `/api/v1/health` | Vérifie que le service tourne |
| POST | `/api/v1/auth/register` | Créer un compte |
| POST | `/api/v1/auth/login` | Connexion (email + mot de passe) → tokens |
| POST | `/api/v1/auth/refresh` | Renouveler l'access token |
| GET | `/api/v1/auth/me` | Profil de l'utilisateur connecté (JWT requis) |
| WS | `/api/v1/voice/ws?token=...` | Conversation vocale temps réel (texte → réponse texte + audio) |
| POST | `/api/v1/voice/transcribe` | Transcription audio de secours (Whisper) |
| WS | `/api/v1/chat/ws?token=...` | Conversation texte temps réel (même orchestrateur que le vocal) |

## Module vocal (Étape 4)

- `services/stt_service.py` : transcription via l'API Whisper (OpenAI) — utilisé uniquement par
  l'endpoint de secours `/voice/transcribe`, car le flux principal transcrit localement sur le mobile.
- `services/tts_service.py` : synthèse vocale via ElevenLabs (multilingue), renvoie du MP3.
- `api/v1/voice.py` : endpoint WebSocket avec authentification JWT (token en query param), gestion de
  l'**annulation** d'un tour de conversation en cours (`{"type": "cancel"}`), et repli automatique
  signalé au mobile si ElevenLabs n'est pas configuré (`assistant_audio_unavailable`).

Pour activer l'audio de réponse, renseigne `ELEVENLABS_API_KEY` dans `.env` (sinon le mobile bascule
sur sa synthèse vocale locale). `OPENAI_API_KEY` est nécessaire uniquement pour la transcription de secours.

## Orchestrateur multi-agent + routage LLM (Étape 5)

- `ai/llm/` : un provider par fournisseur (`anthropic_provider.py`, `openai_provider.py`,
  `gemini_provider.py`, `ollama_provider.py`), chacun traduisant son format natif vers des structures
  communes (`schemas.py`). **Claude et GPT supportent le function calling complet** ; Gemini et Ollama
  sont conversationnels uniquement pour l'instant (limitation documentée dans leurs fichiers).
- `ai/llm/router.py` : `LLMRouter` essaie chaque fournisseur configuré dans l'ordre
  **Claude → GPT → Gemini → Ollama** jusqu'à ce que l'un réponde — résilience si une clé manque ou
  qu'un service est en panne. Si un agent a besoin d'outils, les fournisseurs qui ne les supportent
  pas sont automatiquement exclus de la chaîne pour ce tour.
- `ai/agents/` : trois agents spécialisés — `ConversationalAgent` (généraliste), `AutomationAgent`
  (avec l'outil réel `create_reminder`, qui écrit en base), `ProductivityAgent` (résumés/traduction).
  `intent_router.py` route vers le bon agent par mots-clés (rapide, sans dépendre d'une clé API).
- `ai/orchestrator.py` : point d'entrée unique partagé par `voice.py` et `chat.py`. Charge la mémoire
  court terme (12 derniers messages), appelle l'agent, exécute les outils demandés par le LLM
  (boucle function-calling à 2 tours max), persiste tout en base (`conversations`, `messages`).
- Nouvelles tables : `conversations`, `messages` (historique = mémoire court terme, RAG vectoriel à
  l'étape 6), `reminders` (rappels créés par l'agent d'automatisation).

Pour tester avec un vrai LLM, renseigne au moins `ANTHROPIC_API_KEY` (recommandé, function calling
complet) ou `OPENAI_API_KEY` dans `.env`, puis `docker compose exec backend alembic upgrade head`
pour appliquer la nouvelle migration.

## Mémoire vectorielle + RAG (Étape 6)

- `ai/memory/embedding_service.py` : génère les embeddings via l'API OpenAI
  (`text-embedding-3-small`, 1536 dimensions) — un besoin technique séparé du LLM conversationnel,
  donc utilisé même si Claude est le fournisseur principal des réponses.
- `ai/memory/memory_service.py` :
  - `remember(...)` indexe un souvenir (texte + embedding) dans `memory_items` / `memory_embeddings`.
  - `search_relevant_memories(...)` retrouve les souvenirs les plus pertinents par **distance
    cosinus** (pgvector, `<=>`), avec un seuil (`MAX_RELEVANT_DISTANCE`) pour ne remonter que du
    contenu réellement pertinent plutôt que le souvenir le plus proche même s'il ne sert à rien.
- `ai/agents/shared_tools.py` : l'outil `remember_fact`, commun à tous les agents — géré une seule
  fois dans `BaseAgent.execute_tool`, chaque agent qui l'ajoute à sa liste `tools` en hérite
  automatiquement (voir `ConversationalAgent`, `ProductivityAgent`, `AutomationAgent`).
- `ai/orchestrator.py` : avant chaque tour, recherche les souvenirs pertinents pour la requête et les
  injecte dans le prompt système de l'agent (RAG) — c'est ce qui permet à JARVIS de se souvenir de
  faits et préférences **au-delà** de la session de conversation en cours.
- **Dégradation gracieuse** : si `OPENAI_API_KEY` n'est pas configuré, la mémoire long terme est
  simplement désactivée (`remember()` renvoie `None`, `search_relevant_memories()` renvoie `[]`) —
  JARVIS continue de fonctionner normalement avec la seule mémoire court terme de la session.
- Nouvelle migration `0003` : tables `memory_items`, `memory_embeddings` (colonne `vector(1536)`,
  index IVFFlat pour la recherche par similarité cosinus).

**Testé** : dégradation gracieuse sans clé configurée, écriture réelle d'un souvenir (embedding
simulé) avec vérification en base, et exécution de l'outil `remember_fact` via l'agent
conversationnel de bout en bout.

## Intégrations externes : Google Agenda, Gmail, WhatsApp (Étape 7)

- `core/crypto.py` : **chiffrement AES-256-GCM** des secrets stockés en base (nonce aléatoire à
  chaque appel, clé dédiée `ENCRYPTION_KEY` distincte de `SECRET_KEY`). Concrétise enfin l'exigence
  de sécurité posée dès l'architecture de l'étape 1.
- `integrations/google_oauth.py` : flux OAuth 2.0 complet — URL d'autorisation, échange de code,
  **rafraîchissement automatique** du token expiré, tokens toujours chiffrés en base
  (table `integrations`, nouvelle migration `0004`).
- `integrations/google_calendar_service.py` / `gmail_service.py` : création d'événements et envoi
  d'emails via les APIs Google, avec des **scopes volontairement restreints**
  (`calendar.events` + `gmail.send` — jamais de lecture de la boîte mail).
- `integrations/whatsapp_service.py` : envoi via l'API Cloud de Meta. ⚠️ Fonctionne différemment de
  Google : un **numéro professionnel unique côté serveur** (pas d'OAuth par utilisateur), et une
  limite imposée par WhatsApp — impossible d'écrire à un numéro qui n'a pas déjà contacté ce numéro
  professionnel dans les 24h (sauf template pré-validé, non implémenté ici).
- `api/v1/integrations.py` : `GET /integrations/google/connect` (renvoie l'URL à ouvrir dans un
  navigateur intégré côté mobile), `GET /integrations/google/callback` (échange le code), 
  `GET /integrations/status` (état des connexions, pour l'écran réglages du mobile).
- `AutomationAgent` gagne 3 nouveaux outils : `create_event`, `send_email`, `send_whatsapp_message` —
  chacun renvoie un message clair et actionnable si le service n'est pas connecté, plutôt que de
  planter la conversation.

**Testé** (avec appels réseau simulés, sans vraies clés Google/WhatsApp) :
- Chiffrement AES-256-GCM : aller-retour correct, secret jamais en clair dans le blob stocké, nonce
  non-déterministe à chaque appel, refus propre si `ENCRYPTION_KEY` absent.
- Génération d'URL d'autorisation Google (bon `client_id`, `access_type=offline`, `state`).
- Échange de code → tokens bien chiffrés en base, déchiffrables correctement ; une reconnexion met à
  jour la ligne existante plutôt que d'en créer une seconde (contrainte d'unicité respectée).
- **Rafraîchissement automatique** d'un token expiré — bug réel détecté et corrigé en cours de route
  (comparaison de dates naïve/timezone-aware qui plantait avec SQLite) : `get_valid_access_token`
  normalise désormais défensivement le timezone avant de comparer.
- Les 3 nouveaux outils de `AutomationAgent` gèrent sans crash : absence de connexion Google, config
  WhatsApp absente, dates invalides — toujours un message exploitable renvoyé au LLM.

Pour activer ces intégrations, renseigne dans `.env` : `ENCRYPTION_KEY` (`openssl rand -hex 32`),
`GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` (Google Cloud Console → Credentials → OAuth
Client ID de type "Web application", avec `GOOGLE_OAUTH_REDIRECT_URI` dans les URIs de redirection
autorisées), et `WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` (Meta for Developers → WhatsApp
→ API Setup). Puis `docker compose exec backend alembic upgrade head`.

## Module de vision artificielle (Étape 8)

- `services/vision_service.py` : analyse d'image via le modèle vision natif de **Claude**
  uniquement (pas de chaîne de secours multi-fournisseur pour la vision — limitation assumée et
  documentée dans le fichier, à réévaluer si besoin réel de résilience sur ce module).
- Trois modes prédéfinis (`describe`, `ocr`, `objects`), ou une **question libre** de l'utilisateur
  qui prend le dessus sur le mode (analyse visuelle guidée, façon "y a-t-il un danger visible ?").
- `api/v1/vision.py` : `POST /vision/analyze` (upload multipart), pas de WebSocket — contrairement
  au vocal/chat, c'est un échange ponctuel. Le résultat est persisté dans l'historique de la
  conversation (`ai/orchestrator.py::record_vision_exchange`) pour qu'un message texte ou vocal
  ultérieur dans la même conversation puisse s'y référer.
- Validation stricte : formats acceptés (JPEG/PNG/WebP/GIF), taille max 8 Mo, rejetés avec un code
  HTTP explicite (415/413) avant tout appel réseau coûteux.

**Testé** : rejet propre des formats non supportés et des images trop volumineuses, dégradation
gracieuse sans clé Anthropic configurée, sélection correcte de l'instruction envoyée à Claude selon
le mode choisi, priorité de la question utilisateur sur le mode par défaut (avec appels réseau
simulés), et persistance réelle de l'échange vision dans `messages` (vérifiée en base).

## Petit ajout pour le tableau de bord mobile (Étape 9)

- `GET /api/v1/reminders` : liste les rappels en attente de l'utilisateur (lecture seule — la
  création reste toujours pilotée par une conversation avec l'agent d'automatisation). Alimente le
  panneau "Prochaines échéances" du nouveau tableau de bord mobile.

## Prochaine étape (Étape 10)

Tests plus poussés, scripts Docker de production, instructions de déploiement.

## Tests automatisés + déploiement (Étape 10)

- **40 tests automatisés** (`pytest`), tournant entièrement sur SQLite en mémoire (pas besoin d'un
  vrai PostgreSQL pour les lancer — `tests/conftest.py` fournit les fixtures `db_session`/`client`) :
  auth (inscription, connexion, refresh, cas d'erreur), chiffrement AES-256-GCM (aller-retour,
  non-déterminisme, détection de falsification), routeur d'intention, agent d'automatisation
  (rappels + intégrations externes, avec appels réseau simulés), orchestrateur complet (function
  calling, persistance, historique multi-tours), mémoire long terme (dégradation gracieuse +
  écriture), OAuth Google (échange de code, chiffrement, rafraîchissement automatique), vision
  (validation, sélection d'instruction).
- **Un vrai bug de dépendances a été détecté et corrigé grâce à cette suite** : `passlib==1.7.4`
  est incompatible avec les versions récentes de `bcrypt` (>= 4.1, qui a supprimé l'attribut de
  version que `passlib` lit pour se calibrer) — le hachage de mot de passe échouait silencieusement
  à l'exécution. `requirements.txt` épingle maintenant `bcrypt==4.0.1` explicitement.
- Lancer la suite : `docker compose exec backend pytest -v` (ou en local avec les dépendances
  installées : `cd backend && pytest -v`).
- `Dockerfile.prod` + `docker-compose.prod.yml` : build multi-stage, utilisateur non-root, plusieurs
  workers Gunicorn/Uvicorn, ports DB/Redis non exposés à l'hôte, limites de ressources, healthchecks.
- `.env.prod.example` : gabarit de configuration production, sans valeurs par défaut faibles.
- Voir **`../DEPLOYMENT.md`** à la racine du projet pour les instructions complètes (backend +
  mobile + checklist de soumission aux stores).

Ceci conclut les 10 étapes de la roadmap initiale — voir `../DEPLOYMENT.md` pour un résumé de
l'ensemble du projet.
