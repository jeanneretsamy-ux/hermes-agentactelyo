# Atelier Actelyo — première version

L'Atelier permet de demander à l'agent une extension de chronologie, de la
prévisualiser avec ses sources et de conserver plusieurs versions. Cette version
utilise des panneaux de données validés, sans exécution de code généré. Les
autres types d'extensions et la modification libre de l'interface restent à développer.

## Utiliser l'Atelier

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

Les versions et leur activation sont enregistrées dans `atelier.sqlite3` du
profil backend courant. Les appels Desktop portent ce profil, et les mutations
passent par le même service que la ligne de commande utilisée par l'agent.
Un changement de connexion, de profil ou de conversation ferme l'Atelier ouvert.
Aucun serveur de modèle, compte DeepSeek ou service payant n'est ajouté.

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
avec deux profils temporaires. Les tests React vérifient les interactions avec
des réponses RPC contrôlées ; ils ne constituent pas un essai d'un modèle de
génération ni un lancement de l'EXE installé.
