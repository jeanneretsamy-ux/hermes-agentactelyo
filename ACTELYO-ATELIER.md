# Atelier Actelyo — première version

L'Atelier permet de demander une extension en langage naturel. Il propose deux
parcours : des chronologies avec passages sourcés et versions conservées dans
le profil, et de vrais plugins JavaScript qui ajoutent des panneaux au Desktop.
Les plugins utilisent le chargeur et le SDK existants, sans réécrire le cœur.

## Créer une chronologie

1. Ouvrez une conversation du profil concerné et sélectionnez le dossier ou
   précisez ses pièces dans votre demande.
2. Dans la barre latérale, ouvrez **Atelier Actelyo**, décrivez la chronologie
   puis cliquez **Préparer la création dans le chat**. Le texte est inséré dans
   votre conversation ; envoyez-le pour que l'agent travaille sur vos documents.
3. L'agent charge `actelyo-atelier`, extrait les pièces accessibles, sélectionne
   leurs passages et enregistre un brouillon. Cela nécessite un modèle capable
   d'utiliser les outils et de respecter le schéma ; un essai avec un petit
   modèle local ne garantit pas cette capacité.
4. Rouvrez l'Atelier et cliquez **Actualiser**, puis choisissez une version.
   Examinez les événements, leur date et les **Source** dépliables. Le filtre
   recherche dans les titres, les dates, les noms de fichiers et les extraits.
5. Après revue, cliquez **Activer cette version après revue**. Une seule version
   du même identifiant d'extension est active. L'Atelier confirme le résultat
   retourné par le backend ; une erreur reste affichée et permet d'actualiser.
6. Pour revenir en arrière, ouvrez une ancienne version et activez-la. Le bouton
   **Désactiver** conserve tous les brouillons et toutes les versions.

Les textes des pièces ne sont jamais exécutés comme HTML. Les sources sont
consultables dans le panneau avec leur extrait exact, leur empreinte SHA-256,
leur emplacement dans le texte fourni et leur page lorsqu'elle est connue.
Les URL affichées sont des références, pas des téléchargements automatiques.

## Créer un plugin avec un prompt

1. Utilisez une conversation connectée à un modèle capable de programmer et
   d'exécuter les outils. Le mode de création ne transforme pas automatiquement
   un petit modèle en modèle de code.
2. Ouvrez **Atelier Actelyo → Plugin d'interface** et décrivez votre fonction,
   par exemple « Crée un compteur de pièces avec Ajouter, Retirer et Remettre
   à zéro. Le compteur ne doit jamais devenir négatif. »
3. Cliquez **Préparer la création dans le chat**, puis envoyez la demande.
   Le dossier des plugins est fourni par la fenêtre Desktop ; aucun chemin
   n'est à inventer. La création locale n'est pas proposée depuis un backend
   distant, dont les fichiers ne sont pas ceux de votre ordinateur.
4. L'agent charge `actelyo-plugin-creator`, écrit un brouillon `plugin.js`,
   exécute les tests disponibles et installe le fichier dans un sous-dossier
   dédié. Il doit signaler explicitement les limites des vérifications.
5. Cliquez **Ouvrir les plugins**, examinez le code et les résultats puis
   activez le plugin dans le gestionnaire natif. Il est désactivé par défaut.
   Son panneau utilise les points d'extension du Desktop. Le gestionnaire
   permet ensuite de le désactiver ; le chargeur nettoie ses contributions.

Les plugins d'interface sont locaux à l'application, avec ses droits : ce
chargeur n'est pas un sandbox. La réussite dépend du modèle et de la fonction
demandée. Un échec ne doit pas être présenté comme un plugin créé et fonctionnel.
Une mise à jour d'un plugin actif se recharge ; gardez la version précédente.

## Ce qui est vérifié

Le backend reconstruit les passages et refuse les références inconnues, les
sources modifiées depuis leur sélection et les dates absentes des passages
cités. Il conserve les métadonnées des lignes et colonnes des tableaux.
L'activation relit la version et son empreinte ; une version altérée est refusée.

Ce contrôle prouve la correspondance avec le texte extrait fourni. Il ne prouve
ni l'authenticité du fichier d'origine, ni que la date signifie bien ce que dit
le titre de l'événement. La revue humaine reste indiquée dans chaque aperçu.
Le skill utilise le contrôle `grounded-citations` pour les interprétations
juridiques lorsque le modèle de revue est disponible, sans présenter cette
liaison mécanique comme une validation juridique universelle.

## Stockage et déploiement

Les chronologies et leur activation sont enregistrées dans `atelier.sqlite3` du
profil backend courant. Les appels Desktop portent ce profil, et les mutations
passent par le même service que la ligne de commande utilisée par l'agent.
Un changement de connexion, de profil ou de conversation ferme l'Atelier ouvert.
Les plugins JavaScript sont, eux, lus dans le dossier local de l'application
fourni par Electron, indépendamment du profil backend. Le modèle de la
conversation est utilisé ; aucun compte DeepSeek ni serveur de modèle n'est
installé automatiquement.

L'interface et le backend doivent provenir de la même version. Un backend ancien
affiche une erreur de connexion/méthode à mettre à jour, sans simuler l'Atelier.
Un push du code ne modifie pas les EXE déjà installés.

## Vérification développeur

```text
scripts/run_tests.sh tests/hermes_cli/test_atelier.py tests/tui_gateway/test_atelier_rpc.py tests/tui_gateway/contracts/test_generated.py -q -j 1
```

Depuis `apps/desktop` :

```text
npx vitest run --project ui src/app/chat/sidebar/atelier-dialog.test.tsx
npm run typecheck
```

La CI `Atelier verification` exécute ces vérifications. Les tests de données et
de RPC utilisent réellement SQLite, les contrats et le chargement de citations,
avec deux profils temporaires. Les tests React de l'Atelier utilisent des
réponses RPC contrôlées. En complément, deux prompts ont été exécutés par le
véritable `AIAgent` de Law Harness, via son moteur de programmation natif :
calculateur de jours calendaires et compteur de pièces. Les fichiers produits
sans réécriture manuelle sont conservés dans
`apps/desktop/src/test/plugin-workshop/fixtures/`.

Les 24 tests du calculateur et les 8 tests du compteur ont été rejoués avec
React/DOM. La fixture navigateur utilise ensuite les vrais `runtime-loader`,
SDK, contexte de plugin, registre et mécanismes d'activation dans Chromium :
13 contrôles de comportement, dont coexistence, rechargement et nettoyage.
La CI rejoue cette régression sans appel de modèle payant.

Cela ne constitue pas un lancement de l'EXE installé ni une garantie de réussite
de toutes les demandes avec tous les modèles.
