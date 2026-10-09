# Legal Data Hunter et Actelyo RAG

Actelyo Law Harness embarque deux intégrations juridiques locales :

- `skills/legal/legal-data-hunter` pour la recherche juridique via le connecteur MCP Legal Data Hunter.
- `skills/legal/actelyo-rag-backend` et `mcp-servers/actelyo-rag` pour interroger Actelyo RAG sans recopier les documents dans le harness.

## Variables locales

Copiez `.env.example` vers `.env` sur le poste utilisateur, puis renseignez les valeurs locales :

```env
LEGAL_DATA_HUNTER_TOKEN=
LEGAL_DATA_HUNTER_API_KEY=
ACTELYO_RAG_BASE_URL=http://127.0.0.1:61045/api
ACTELYO_RAG_WORKSPACE=mon-espace-de-travail
ACTELYO_RAG_API_KEY=
```

Les valeurs réelles ne doivent pas être commitées. `.env` est ignoré par Git.

## Serveur MCP Actelyo RAG

Le serveur MCP versionné est `mcp-servers/actelyo-rag/actelyo_rag_mcp.py`. Il expose :

- `actelyo_rag_list_workspaces`
- `actelyo_rag_query`
- `actelyo_rag_vector_search`

Exemple de configuration locale dans le profil Hermes/Actelyo :

```yaml
mcp_servers:
  actelyo-rag:
    command: python
    args:
      - <CHEMIN_D_INSTALLATION>\mcp-servers\actelyo-rag\actelyo_rag_mcp.py
```

Adaptez le chemin si le harness est installé ailleurs. Le serveur lit `ACTELYO_RAG_BASE_URL`, `ACTELYO_RAG_WORKSPACE` et `ACTELYO_RAG_API_KEY` depuis l'environnement local.

## Utilisation attendue

Pour utiliser le RAG, demandez au harness de mobiliser le skill Actelyo RAG, par exemple : « mobilise Actelyo RAG sur mon espace de travail et réponds avec les sources ». Le skill doit appeler le serveur MCP local plutôt que charger ou envoyer les fichiers vers un service externe.


