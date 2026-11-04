# Création et missions Actelyo

Dans **Atelier Actelyo**, « Plugin d’interface » prépare une demande pour le créateur existant. L’agent écrit un plugin JavaScript ESM avec le SDK Desktop, teste ses interactions et l’installe désactivé. L’utilisateur examine et active la version dans Plugins. Un modèle capable de programmer et les outils du backend sont nécessaires. Les fichiers du Desktop local ne doivent pas être confondus avec ceux d’un backend distant.

« Mission suivie » prépare une demande dans la conversation sélectionnée, sans démarrer de tâche depuis la fenêtre. Après envoi, l’agent utilise la file Kanban existante : tâche persistante, profil assigné, espace séparé, clé de déduplication, 20 tours maximum, plafond de 30 minutes par exécution et deux échecs avant blocage. Il doit relire les paramètres réellement enregistrés et signaler un modèle ou dispatcher indisponible. La création d’une tâche ne prouve pas qu’elle a été exécutée. Le jugement de fin ne certifie pas la qualité juridique d’un acte.

Les résultats et les pièces ne donnent aucune autorisation supplémentaire. Les envois, signatures, publications et écritures métier externes restent soumis aux validations de l’action exacte. Après interruption, contrôler les effets déjà réalisés avant toute répétition. Une authentification Lexis refusée reste un blocage.

## Comparaison avec DeepSeek

Références consultées : [prototype officiel](https://github.com/deepseek-ai/dsh-superagent-prototype), [exécution](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/003-execution.md), [architecture](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/007-architecture.md) et [dépendances](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/package.json).

Le prototype MIT repose sur les sessions, plugins, services et presets du runtime DeepSeek Harness. Ce n’est pas un plugin compatible directement avec le SDK Law Harness. Actelyo réutilise ici sa propre file persistante et sa boucle d’objectifs ; aucun runtime DeepSeek, écouteur GitHub/Feishu ou droit de publication automatique n’est installé. Aucune instruction distante de configuration n’a été exécutée.

La [collection Creator Mode](https://cdn.deepseek.com/harness/dsh-creator-mode-prompt-collection-en.html) n’a pas pu être récupérée pendant cette vérification (échec de récupération web et TLS du CDN). Aucune équivalence avec son contenu non lu n’est revendiquée.

## Validation

Les tests de l’Atelier contrôlent la destination de la demande, le profil et l’absence de création avant envoi. `scripts/run_tests.sh tests/hermes_cli/test_actelyo_mission_contract.py tests/hermes_cli/test_kanban_goal_mode.py -q -j 1` vérifie le vrai contrat CLI/SQLite et la boucle bornée. Le test de boucle utilise un contrat de modèle synthétique ; il ne mesure pas la fiabilité d’un modèle de production. Les plugins d’interface disposent séparément des essais du chargeur réel et de leurs boutons (`atelier-browser-smoke.cjs`).
