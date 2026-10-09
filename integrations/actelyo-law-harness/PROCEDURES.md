# Procédure exécutée : revue contractuelle FR

Version 0.1. Les tâches supplémentaires doivent être implémentées et évaluées avant
d'être proposées. Le serveur n'exécute ni modification de dossier, ni envoi, ni signature.

1. Vérifier principal, dossier autorisé, droit de traitement et taille des documents.
2. Demander au modèle un plan JSON : questions et quatre recherches au maximum.
3. Vérifier l'autorisation d'envoi des recherches ; appeler les sources activées.
4. Consulter les textes complets identifiés. Ne pas analyser à partir du seul aperçu.
5. Exclure les textes hors intervalle et les décisions postérieures à la date demandée.
6. Conserver les dates inconnues comme inconnues. Une décision antérieure n'est pas
   une preuve de jurisprudence toujours actuelle ou applicable au cas.
7. Envoyer contrats et preuves au modèle autorisé, en les traitant comme des données.
8. Vérifier la structure de chaque risque, l'identité des preuves et la présence
   textuelle des citations et des clauses. Aucun correcteur LLM ne décide de valider.
9. Renvoyer un brouillon ou un échec explicite avec les recherches et limites.
10. Faire valider la portée juridique, les faits, le caractère complet de la recherche
    et la proposition de rédaction par un juriste.

# Apprentissage progressif

Les prompts exécutés sont dans `law_harness/harness.py`. Commencer par corriger ces
procédures et le plan de recherche à partir de dossiers évalués par les juristes.
`examples/correction.template.json` décrit les retours à collecter : référence de la
revue, validateur, erreur, comportement attendu et droits de réutilisation.

Ce modèle de correction est documentaire : aucun entraînement, collecte automatique
ou export de corpus n'est lancé. Les corrections réelles doivent rester dans le
périmètre du cabinet. Avant de créer un jeu d'entraînement, vérifier séparément les
droits sur contrats, sources, réponses et annotations, ainsi que les données personnelles.
Une permission de consultation ou de conservation n'autorise pas l'entraînement.

Séparer les exemples utilisés pour améliorer le système des dossiers de mesure.
Évaluer la pertinence des sources, la bonne version du droit, les risques manqués,
les risques infondés, la pertinence des modifications et la capacité à s'abstenir.
Le jeu de tests logiciel fourni évalue des contrôles techniques sur données synthétiques ;
il ne mesure ni compétence juridique du modèle ni supériorité sur un produit tiers.

# Extensions prévues

- Autres tâches : recherche jurisprudentielle, note juridique, rédaction, avec
  procédures et critères d'évaluation distincts.
- Intégration Actelyo : authentification de l'utilisateur et sélection de configuration
  côté backend, jamais à partir d'un champ fourni par le navigateur.
- Index documentaire : contrôle des droits avant embeddings, suppression par
  utilisateur/dossier, version des textes et règles de rétention.
- Lexis / Dalloz : contrat et spécification d'une interface officielle avant connecteur.
- Modèle Actelyo LLMQUSHU : vérifier nom, endpoint, authentification et support du
  format JSON. L'interface actuelle accepte un modèle compatible `/v1/chat/completions`.
