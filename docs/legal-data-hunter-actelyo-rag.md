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

Configuration du serveur MCP dans le profil Hermes/Actelyo (installation Windows par défaut) :

```yaml
mcp_servers:
  actelyo-rag:
    command: ${LOCALAPPDATA}/Programs/ActelyoLawHarness/resources/agent-payload/venv/Scripts/python.exe
    args:
      - ${LOCALAPPDATA}/Programs/ActelyoLawHarness/resources/agent-payload/hermes-agent/mcp-servers/actelyo-rag/actelyo_rag_mcp.py
    env:
      ACTELYO_RAG_BASE_URL: ${ACTELYO_RAG_BASE_URL}
      ACTELYO_RAG_WORKSPACE: ${ACTELYO_RAG_WORKSPACE}
      ACTELYO_RAG_API_KEY: ${ACTELYO_RAG_API_KEY}
```

Hermes résout les valeurs `${...}` depuis le `.env` du profil actif et les transmet au processus MCP. Placez les trois variables `ACTELYO_RAG_*` dans le `.env` du profil Hermes utilisé par Law Harness. La clé reste sur le poste et n'est transmise qu'au serveur MCP local. Après configuration, redémarrez la session ou rechargez MCP. Si l'installation utilise un répertoire personnalisé, remplacez les deux chemins `LOCALAPPDATA/Programs/ActelyoLawHarness` par ce répertoire. Le serveur lit les variables depuis son environnement.

## Utilisation attendue

Pour utiliser le RAG, demandez au harness de mobiliser le skill Actelyo RAG, par exemple : « mobilise Actelyo RAG sur mon espace de travail et réponds avec les sources ». Le skill doit appeler le serveur MCP local plutôt que charger ou envoyer les fichiers vers un service externe.


