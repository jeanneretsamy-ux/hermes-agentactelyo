# Actelyo Law Harness

Agent, outils, mémoire, tâches et interface locale.

Ce module est distribué avec Actelyo. Voir [le guide local](ACTELYO-LOCAL.md) pour le lancement et les prérequis.

Le logo provient du dépôt ACTELYO-ERP. Les mentions et licences des composants tiers sont conservées dans `LICENSE` et les notices de leurs composants. Les identifiants de protocoles, paquets et modèles tiers restent ceux de leurs fournisseurs afin de préserver la compatibilité.
## Legal Data Hunter et Actelyo RAG

Ce dépôt embarque les mêmes briques juridiques que PolyPocket Harness pour la recherche et le RAG local : le skill `skills/legal/legal-data-hunter`, le skill `skills/legal/actelyo-rag-backend` et le serveur MCP `mcp-servers/actelyo-rag`.

Les clés restent locales. Copiez `.env.example` vers `.env`, renseignez les variables nécessaires sur le poste utilisateur, puis activez le serveur MCP `actelyo-rag` dans la configuration Hermes/Actelyo. Voir `docs/legal-data-hunter-actelyo-rag.md` pour la configuration.
