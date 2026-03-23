# Àttaya bi — Le Dernier Camp 🏝️

Un jeu de simulation où des agents IA négocient **en wolof** pour survivre sur une île déserte au large du Sénégal. Vous êtes spectateur — regardez le drame se dérouler en temps réel.

![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Concept

3 à 5 agents IA, chacun avec une personnalité unique, sont échoués sur une île. Ils doivent négocier, échanger, former des alliances et voter — tout en communiquant **en wolof** grâce à un LLM fine-tuné. Le joueur humain observe.

### Deux modes de jeu

| Mode | Description |
|------|-------------|
| **🏝️ Survie** | 15 tours. Catastrophes naturelles, récolte de ressources, échanges et votes d'élimination. Le dernier debout gagne. |
| **🚤 Le Bateau** | 10 tours. Un seul bateau, une seule place. Corruption, assassinat, vol et vote. Tous les coups sont permis. |

### Les Agents

| Nom | Rôle | Style |
|-----|------|-------|
| **Moussa** | Le Diplomate (jëf-jëli) | Pacificateur, négociateur |
| **Awa** | La Stratège (xel-kanam) | Calculatrice froide, trahit quand ça l'arrange |
| **Ibrahima** | Le Survivant (dëkkalkat) | Paranoïaque, accumule, ne fait confiance à personne |
| **Fatou** | La Cheffe (kilifa) | Organisatrice, exige la loyauté |
| **Ousmane** | Le Rusé (fënëkat) | Manipulateur, charmeur, imprévisible |

### Ressources

| Ressource | Wolof | Rôle |
|-----------|-------|------|
| 💧 Eau | Ndox | Consommée chaque tour (mode survie) |
| 🍖 Nourriture | Lekk | Consommée chaque tour (mode survie) |
| 💊 Médicament | Garab | Soigne / protège contre les assassinats |
| 🏗️ Matériaux | Mbëj | Construit un abri (mode survie) |
| ⚔️ Armes | Paxal | Défense contre pillards / assassinat |
| 💰 Argent | Xaalis | Monnaie d'échange et corruption |

## Stack technique

- **Frontend** : React 19 + TypeScript + HTML Canvas + Vite
- **Backend** : FastAPI + SQLAlchemy + SQLite (async)
- **LLM** : API compatible OpenAI (modèle wolof fine-tuné)
- **Infra** : Docker Compose

## Démarrage rapide

### Prérequis

- Docker & Docker Compose
- Node.js 18+
- Un accès à une API LLM compatible OpenAI

### Installation

```bash
git clone https://github.com/motall-u/atayabi.git
cd atayabi
```

### Configuration

Copiez le fichier d'exemple et ajoutez votre clé API :

```bash
cp .env.example .env
```

Éditez `.env` avec vos identifiants :

```env
OPENAI_API_KEY=votre_clé_api
OPENAI_BASE_URL=https://api.llm-wolof.live/v1
OPENAI_MODEL=galsenai-chat
```

> **⚠️ Ne commitez jamais le fichier `.env`** — il est dans le `.gitignore`.

### Lancement

```bash
# Démarrer le backend
docker compose up -d

# Installer et démarrer le frontend
cd frontend
npm install
npm run dev
```

Le frontend est accessible sur `http://localhost:5173` et le backend sur `http://localhost:8000`.

### Sans Docker

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (dans un autre terminal)
cd frontend
npm install
npm run dev
```

## API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/llm/status` | Vérifier la connexion au LLM |
| `POST` | `/api/games` | Créer une partie (`{agent_count, game_mode}`) |
| `GET` | `/api/games` | Lister les parties |
| `GET` | `/api/games/{id}` | État d'une partie |
| `POST` | `/api/games/{id}/next-round` | Jouer un tour |
| `GET` | `/api/games/{id}/next-round-stream` | Jouer un tour (SSE temps réel) |
| `GET` | `/api/games/{id}/replay` | Données de replay |
| `DELETE` | `/api/games/{id}` | Supprimer une partie |

## Architecture

```
atayabi/
├── .env.example          # Template de configuration
├── docker-compose.yml    # Démarrage du backend
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # FastAPI + CORS
│       ├── config.py         # Constantes de jeu
│       ├── database.py       # SQLAlchemy async + SQLite
│       ├── models.py         # Modèles DB (Game, RoundSnapshot)
│       ├── schemas.py        # Schémas Pydantic
│       ├── engine/
│       │   ├── game.py       # Moteur de jeu (survie + bateau)
│       │   └── prompts.py    # Personnalités et prompts système
│       └── routers/
│           ├── games.py      # CRUD + rounds + replay
│           └── llm.py        # Status LLM
└── frontend/
    └── src/
        ├── types/game.ts
        ├── api/client.ts
        ├── constants/config.ts
        └── components/
            ├── StartScreen.tsx
            ├── GameCanvas.tsx      # Canvas 2D animé
            ├── AgentCard.tsx
            ├── ActivityLog.tsx
            ├── EventBanner.tsx
            ├── RelationshipMap.tsx
            ├── GameControls.tsx
            ├── GameOverScreen.tsx
            └── ReplayControls.tsx
```

## Fonctionnalités

- **Agents IA parlant wolof** avec personnalités distinctes
- **7 types d'événements** en mode survie (tempête, pillards, maladie...)
- **Actions secrètes** en mode bateau (corruption, assassinat, vol, défense)
- **Feedback en temps réel** via Server-Sent Events (SSE)
- **Sauvegarde et replay** de toutes les parties en base de données
- **Canvas animé** avec feu de camp, palmiers, vagues et bulles de dialogue
- **Interface en français**, communication des agents en wolof

## Utiliser un autre LLM

Le backend utilise le format API OpenAI. Vous pouvez utiliser n'importe quel LLM compatible :

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Groq
OPENAI_API_KEY=gsk_...
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile

# Local (Ollama)
OPENAI_API_KEY=unused
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen2.5:3b
```

> **Note** : Pour des réponses en wolof de qualité, un modèle fine-tuné sur le wolof est recommandé.

## Licence

MIT

## Crédits

Construit avec [Claude Code](https://claude.ai/claude-code) par Anthropic.

LLM wolof fine-tuné par [GalsenAI](https://llm-wolof.live).
