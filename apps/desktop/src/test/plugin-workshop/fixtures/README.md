# Plugins produits depuis deux prompts de l'Atelier

Ces fichiers sont les sorties de l'agent de programmation testé via le runtime
natif de Law Harness. Leur logique n'a pas été réécrite à la main après
génération. Ils restent désactivés par défaut et n'utilisent que React fourni
par le Desktop.

- `calendar-days/plugin.js` : « Crée un panneau pour calculer une date après un
  nombre de jours calendaires, avec un bouton Effacer. »
- `piece-counter/plugin.js` : « Crée un compteur de pièces avec les boutons
  Ajouter, Retirer et Remettre à zéro. Le compteur ne doit jamais devenir négatif. »

Le premier compte les jours calendaires, sans règle de procédure juridique.
Le second conserve son état tant que son panneau est monté.

La CI Atelier compile la fixture du chargeur réel et exécute
`apps/desktop/scripts/atelier-browser-smoke.cjs` dans Chromium : chargement ESM,
activation, calculs, erreurs, boutons, remise à zéro, absence de valeur négative,
coexistence des deux plugins, rechargement et nettoyage à la désactivation.
Les fichiers sont chargés par `runtime-loader.ts`, avec le SDK, le contexte de
plugin et le registre réels. Le shell Electron et l'EXE installé sont distincts
de cette vérification navigateur.

Cette régression ne lance pas d'inférence payante dans la CI. Elle conserve les
productions du test réel pour vérifier que les changements futurs du chargeur
continuent à les faire fonctionner. Elle ne garantit pas la réussite de toutes
les demandes avec tous les modèles.
