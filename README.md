# veille-bot — Digest quotidien de veille tech sur Discord

## 1. Description du projet

`veille-bot` est un bot Python qui, **chaque matin à 7h (heure de La Réunion, UTC+4)**, agrège
10 flux RSS techniques et sécurité, sélectionne via **Gemini 2.5 Flash** les articles
les plus pertinents pour un développeur en alternance, et publie un **digest structuré**
sur un canal Discord via webhook.

Projet personnel développé dans le cadre du **titre professionnel Concepteur Développeur
d'Applications (CDA, Bac+4)**. Il sert de support concret à plusieurs compétences
du référentiel et à l'exigence transverse de veille technologique.

## 2. Architecture

Architecture **hexagonale légère** en 3 couches strictement séparées. Le domaine ne
dépend d'aucune librairie tierce et reste 100% testable sans mock.

```
┌──────────────────────────────────────────────────────────────────┐
│                     application/                                 │
│              daily_digest_service.py                             │
│       (orchestration : lecture → filtre → IA → publication)      │
└────────────┬─────────────────┬──────────────────┬────────────────┘
             │                 │                  │
             ▼                 ▼                  ▼
┌──────────────────────┐  ┌──────────────┐  ┌────────────────────┐
│      domain/         │  │ infrastructure/                       │
│  - models.py         │  │  - rss_repository.py    (feedparser)  │
│  - article_filter.py │  │  - sqlite_repository.py (sqlite3)     │
│  - deduplicator.py   │  │  - gemini_repository.py (google-genai)│
│  (pur, sans I/O)     │  │  - discord_repository.py (requests)   │
└──────────────────────┘  └───────────────────────────────────────┘
```

**Flux d'exécution quotidien :**

1. Lecture parallèle des 10 flux RSS (`ThreadPoolExecutor`, max 5 workers)
2. Filtrage temporel : on ne garde que les articles publiés dans les 24h
3. Déduplication via SQLite (clé = SHA-256 du lien)
4. **Un seul** appel batch à Gemini → JSON structuré (classement + synthèse)
5. Publication d'un embed Discord riche (top 3 priorités, autres articles, synthèse IA)
6. Marquage des articles publiés comme "vus" en base
7. Commit auto de `seen.db` par GitHub Actions

## 3. Compétences CDA illustrées

- **CP n°1** — Installer et configurer un environnement de travail (Docker + venv)
- **CP n°4** — Contribuer à la gestion d'un projet (GitHub Actions, CI/CD, secrets)
- **CP n°6** — Définir l'architecture logicielle (hexagonale 3 couches, injection de dépendances via `Protocol`)
- **CP n°8** — Développer des composants d'accès aux données (SQLite paramétré + APIs REST Gemini/Discord)
- **CP n°10** — Préparer le déploiement (workflow planifié, gestion des secrets, logs structurés JSON)
- **Veille technologique et sécurité** — Sujet même du projet : automatisation d'une veille quotidienne, requêtes SQL paramétrées, validation des URLs, timeouts réseau, principe du moindre privilège (user non-root dans le conteneur)

## 4. Prérequis

- Python **3.11+**
- Un compte [Google AI Studio](https://aistudio.google.com/apikey) pour obtenir une clé Gemini (free tier)
- Un serveur Discord avec un canal et un **webhook** créé

## 5. Installation locale

```bash
git clone <url-de-votre-repo>
cd veille-bot

python -m venv .venv
# Linux / macOS :
source .venv/bin/activate
# Windows :
.venv\Scripts\activate

pip install -r requirements-dev.txt
python -m src.main
```

Créer un fichier `.env` à la racine du projet avec les 4 variables suivantes
(le fichier est volontairement non versionné, cf `.gitignore`) :

```
GEMINI_API_KEY=votre_cle_gemini
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/.../...
DATABASE_PATH=data/seen.db
LOG_LEVEL=INFO
```

Vous devriez recevoir le digest sur Discord immédiatement.

## 6. Lancement Docker (développement)

```bash
docker compose up --build
```

Le volume `./data` est monté dans le conteneur pour que `seen.db` persiste
entre les runs locaux.

## 7. Tests

```bash
pytest
```

La couverture du module `src/domain` est rapportée en console.

## 8. Configuration GitHub Actions (production)

1. Repo GitHub → **Settings → Secrets and variables → Actions → New repository secret** :
   - `GEMINI_API_KEY` — votre clé Google AI Studio
   - `DISCORD_WEBHOOK_URL` — l'URL complète du webhook Discord
2. Le cron `0 3 * * *` (3h UTC = 7h La Réunion) se déclenche automatiquement chaque jour.
3. Déclenchement manuel possible : onglet **Actions → Veille quotidienne → Run workflow**.

À la fin de chaque exécution réussie, le workflow commite automatiquement
`data/seen.db` pour persister la mémoire de déduplication d'un jour à l'autre.

## 9. Sources de veille suivies

| Source              | Catégorie  | URL                                                       |
|---------------------|------------|-----------------------------------------------------------|
| CERT-FR             | sécurité   | https://www.cert.ssi.gouv.fr/feed/                        |
| NVD CVE             | sécurité   | https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml       |
| The Hacker News     | sécurité   | https://feeds.feedburner.com/TheHackersNews               |
| OWASP               | sécurité   | https://owasp.org/feed.xml                                |
| Dev.to              | général    | https://dev.to/feed/                                      |
| Hacker News (top)   | général    | https://hnrss.org/frontpage?points=100                    |
| Symfony Blog        | backend    | https://feeds.feedburner.com/symfony/blog                 |
| PHP.net             | backend    | https://www.php.net/feed.atom                             |
| GreenIT             | général    | https://www.greenit.fr/feed/                              |
| Journal du Hacker   | général    | https://www.journalduhacker.net/rss                       |

La liste est éditable dans `src/sources.py`.

## 10. Licence

MIT
