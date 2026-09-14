# ragifix-mcp — Serveur MCP

## Vue d'ensemble

**ragifix-mcp** est un serveur MCP (Model Context Protocol) qui expose ragifix à des clients LLM (chat, agents).

Il traduit les appels MCP en requêtes HTTP vers ragifix, sans jamais toucher directement à la base vectorielle.

## Architecture interne

```
┌─────────────────────────────────────────────────────────┐
│                ragifix-mcp (Serveur MCP)                  │
├─────────────────────────────────────────────────────────┤
│  main.py                │  Point d'entrée                │
│                         │  - Construction de l'app       │
│                         │  - Lancement uvicorn           │
├─────────────────────────────────────────────────────────┤
│  tools.py               │  Outils MCP exposés            │
│  ├─ rag_query           │  Recherche sémantique          │
│  ├─ rag_list_documents  │  Liste des documents           │
│  ├─ rag_get_document    │  Détail d'un document          │
│  ├─ rag_list_sources    │  Liste des sources             │
│  └─ rag_health          │  Health check                  │
├─────────────────────────────────────────────────────────┤
│  ragifix_client.py      │  Client HTTP asynchrone        │
│                         │  - query                       │
│                         │  - list_documents              │
│                         │  - get_document                │
│                         │  - get_sources                 │
│                         │  - health                      │
├─────────────────────────────────────────────────────────┤
│  auth.py                │  Middleware auth bearer         │
│                         │  - Comparaison temps constant  │
├─────────────────────────────────────────────────────────┤
│  config.py              │  Configuration                 │
│                         │  - server.host/port            │
│                         │  - server.auth_token_env        │
│                         │  - server.instructions          │
│                         │  - ragifix.base_url            │
│                         │  - ragifix.api_token_env        │
│                         │  - mcp_sources (fallback)      │
└─────────────────────────────────────────────────────────┘
```

## Points clés

### 1. Séparation des responsabilités

- **ragifix-mcp** ne fait que traduire MCP → HTTP
- Pas de parsing, pas de chunking, pas d'embedding
- Pas d'accès direct à Milvus ou SQLite
- Le client HTTP est le seul point de sortie vers ragifix

### 2. Outils MCP exposés

Chaque outil est documenté avec une description claire pour le LLM :

| Outil | Description |
|-------|-------------|
| `rag_query` | Recherche sémantique de passages pertinents, filtrable (`filters`) |
| `rag_list_documents` | Lister les documents indexés, filtrable (`filters`) |
| `rag_get_document` | Détail d'un document (chunks, métadonnées) |
| `rag_list_sources` | Lister les sources disponibles |
| `rag_health` | Vérifier que ragifix est joignable |

`filters` (dict, transmis tel quel à `POST /query`/`GET /documents` côté
`ragifix`) accepte les clés `source`, `extension`, `filename_glob` (valeur
unique ou liste, `OR` intra-clé) et `modified_after`/`modified_before`
(valeur unique), combinées en `AND` — voir
[`ragifix/doc.md`](../ragifix/doc.md) point 4bis pour le détail.

### 3. Configuration des instructions

Les instructions de l'outil (ce que le LLM doit savoir) sont dans `config.yaml` :

```yaml
server:
  instructions: "Donne accès à la base documentaire ragifix : recherche sémantique..."
```

Cela permet aux utilisateurs de personnaliser la description sans modifier le code.

### 4. Origine des documents

Les modèles `QueryResultItem` et `DocumentInfo` exposent un champ `origin`
(`{kind, uri, label}` ou `null`), repris tel quel depuis la réponse de
ragifix. Les docstrings de `rag_query` et `rag_get_document` invitent le
LLM à citer `origin.uri` pour indiquer où trouver le document source.

### 5. Gestion des sources

- **Source de vérité** : ragifix-collector pousse les sources via `POST /sources`
- **Fallback** : `mcp_sources` dans config.yaml (pour les configs sans collector)
- **Priorité** : si les deux sont configurés, warning dans les logs, les sources de collector prennent la priorité

### 6. Authentification

Deux niveaux :
- **Entre client et MCP** : `RAGIFIX_MCP_TOKEN` (configuré dans `server.auth_token_env`)
- **Entre MCP et ragifix** : `RAGIFIX_API_TOKEN` (configuré dans `ragifix.api_token_env`)

Pas de distinction read/write pour le moment (TODO).

### 7. Transport

- **Streamable HTTP** (standard MCP pour serveurs distants)
- Path : `/mcp`
- Port : `8423` par défaut

---

## Déploiement

### Docker
```bash
docker build -f deploy/docker/Dockerfile -t ragifix-mcp .
docker run -d --name ragifix-mcp --network host -v "$(pwd)/config.yaml:/etc/ragifix-mcp/config.yaml:ro" ragifix-mcp
```

### Développement
```bash
python3 -m venv venv && source venv/bin/activate
pip install -e .
ragifix-mcp --config ./config.yaml
```

---

## Limitations connues

- Pas de pagination (TODO)
- Pas de cache côté serveur
- Pas de comparaison multi-sources (TODO)
