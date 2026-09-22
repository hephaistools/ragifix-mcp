# ragifix-mcp

Serveur MCP qui expose la base [ragifix](https://github.com/hephaistools/ragifix) à un client de chat compatible (recherche, listing de documents). Le client ne permet pas d'ajouter des documents, uniquement de consulter (read-only).

## Sommaire

- [Installation via Docker](#installation-via-docker)
- [Installation via paquet .deb](#installation-via-paquet-deb)
- [Installation en environnement de développement](#installation-en-environnement-de-développement)
- [Configuration à coller dans le client de chat](#configuration-à-coller-dans-le-client-de-chat)
- [Outils exposés](#outils-exposés)
- [Accès distant](#accès-distant)

---

## Installation via Docker

```bash
git clone <url-du-dépôt> ragifix-mcp && cd ragifix-mcp

cp config.example.yaml config.yaml                # puis l'adapter
cp deploy/ragifix-mcp.env.example ragifix-mcp.env # puis renseigner les secrets

docker build -f deploy/docker/Dockerfile -t ragifix-mcp .

docker run -d \
  --name ragifix-mcp \
  --network host \
  --env-file ragifix-mcp.env \
  -v "$(pwd)/config.yaml:/etc/ragifix/config.yaml:ro" \
  ragifix-mcp
```

`--network host` : par défaut (`server.host: 127.0.0.1`), le serveur doit rester joignable en local sur la machine qui héberge aussi `ragifix` et le client de chat.

Vérifier que le service tourne (401 attendu sans token) :

```bash
curl -s -X POST -H "Content-Type: application/json" -d '{}' http://127.0.0.1:8422/mcp
```

## Installation via paquet .deb

1. **Télécharger le `.deb`** sur la page release... ou générer vous-même le `.deb` :
```bash
git clone <url-du-dépôt> ragifix-mcp && cd ragifix-mcp

sudo apt-get install -y devscripts debhelper python3-venv python3-pip
dpkg-buildpackage -us -uc -b
```

2. Puis **l'installer** via `apt` :
```bash
sudo apt install -y ../ragifix-mcp_0.3.0_all.deb
```

L'installation (`postinst`) construit un environnement virtuel Python dans `/opt/ragifix-mcp/venv` et y installe les dépendances.

Le paquet crée un utilisateur système dédié, `/etc/ragifix-mcp/config.yaml` et `ragifix-mcp.env` (depuis les exemples), et une unité systemd `ragifix-mcp.service`.

3. **Configurer** :
```bash
sudo nano /etc/ragifix-mcp/config.yaml
sudo nano /etc/ragifix-mcp/ragifix-mcp.env
sudo systemctl enable --now ragifix-mcp
journalctl -u ragifix-mcp -f
```

**Pour désinstaller** :
```bash
sudo apt remove ragifix-mcp    # conserve la config
sudo apt purge ragifix-mcp     # supprime tout
```

## Installation en environnement de développement

```bash
git clone <url-du-dépôt> ragifix-mcp && cd ragifix-mcp

python3 -m venv venv
source venv/bin/activate
pip install -e .

cp config.example.yaml config.yaml   # reste à côté du code, hors /etc

export RAGIFIX_MCP_TOKEN=dev-mcp-token
export RAGIFIX_API_TOKEN=dev-token    # le token de l'API ragifix visée

ragifix-mcp --config ./config.yaml
```

## Configuration à coller dans le client de chat

Une fois le serveur démarré, déclarer un serveur MCP distant (transport HTTP) dans la configuration du client :

```json
{
  "mcpServers": {
    "ragifix": {
      "url": "http://127.0.0.1:8422/mcp",
      "headers": {
        "Authorization": "Bearer <RAGIFIX_MCP_TOKEN>"
      }
    }
  }
}
```

Remplacer `<RAGIFIX_MCP_TOKEN>` par la valeur configurée dans `ragifix-mcp.env` (ou `RAGIFIX_MCP_TOKEN` en développement), et l'URL par l'adresse réelle du serveur si différente de `127.0.0.1:8422`.

Certains clients plus anciens ne savent pas encore se connecter directement à un serveur HTTP distant et n'acceptent qu'une commande locale (`command`/`args`) ; dans ce cas, passer par un pont comme [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) :

```json
{
  "mcpServers": {
    "ragifix": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote",
        "http://127.0.0.1:8422/mcp",
        "--header", "Authorization: Bearer <RAGIFIX_MCP_TOKEN>"
      ]
    }
  }
}
```

Se référer à la documentation du client de chat utilisé pour savoir où coller cette configuration (fichier de config MCP, ou interface de gestion des connecteurs/serveurs MCP).

## Outils exposés

| Outil | Description |
|---|---|
| `rag_query(query, top_k=5, filters=None)` | Recherche les passages les plus pertinents, filtrable via `filters` (voir "Filtres" ci-dessous). |
| `rag_list_documents(filters=None)` | Liste les documents indexés dans ragifix, filtrable via `filters` (sans pagination pour le moment — voir TODO). |
| `rag_get_document(doc_id)` | Détail d'un document. |
| `rag_list_sources()` | Liste les sources de documents disponibles. |
| `rag_health()` | Vérifie que `ragifix` est joignable. |

Les résultats de `rag_query`, `rag_get_document` et `rag_list_documents` incluent un champ `metadata` (objet JSON à plat, voir [`ragifix/doc.md`](../ragifix/doc.md)), dont la clé `uri` : le lien ou chemin le plus rapide vers le document source, à citer pour indiquer à l'utilisateur où le trouver.

### Filtres

`filters` est un dict transmis tel quel à l'API `ragifix` (combiné en `AND`) :

| Clé | Type | Sémantique |
|---|---|---|
| `source` | `str` ou liste de `str` | Nom de la source configurée ; liste = `OR`. |
| `extension` | `str` ou liste de `str` | Extension du fichier ; liste = `OR`. |
| `filename_glob` | motif (ex: `*rapport*.pdf`) ou liste de motifs | `OR` entre motifs si liste. |
| `modified_after` / `modified_before` | `str` (ISO 8601) | Bornes sur la date de modification, valeur unique. |

Exemple : `rag_query(query="politique de télétravail", filters={"source": "my_sharepoint"})`.

## Accès distant

Par défaut (`server.host: 127.0.0.1`), le serveur n'est joignable que depuis la machine locale.

Pour un client de chat distant, deux changements sont nécessaires :

1. **`server.host`** dans `config.yaml` : passer à `0.0.0.0` (toutes les interfaces) ou à l'IP de l'interface réseau concernée.
2. **TLS** : ce serveur ne termine pas lui-même de TLS. Placer un reverse-proxy (nginx, Caddy, Traefik...) devant, qui gère le certificat et relaie vers `http://127.0.0.1:<port>/mcp` en interne. Exemple minimal avec Caddy :

   ```
   mcp.exemple.fr {
       reverse_proxy 127.0.0.1:8422
   }
   ```

   Le `url` déclaré côté client de chat devient alors `https://mcp.exemple.fr/mcp`.

Le token dédié (`RAGIFIX_MCP_TOKEN`) reste la protection applicative dans les deux cas.

## TODO

- [x] exposer des filtres sur `rag_query`/`rag_list_documents` (par source(s), extension(s), motif de nom de fichier, plage de date — voir "Filtres" ci-dessus).

- [ ] ajouter la pagination sur `rag_list_documents` (aujourd'hui, tous les documents sont retournés en une fois).
