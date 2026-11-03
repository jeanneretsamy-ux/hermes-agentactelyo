---
name: actelyo-plugin-creator
description: Créer et tester des plugins pour le Desktop.
version: 1.0.0
author: Samy Jeanneret (@jeanneretsamy-ux) + Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    category: research
    tags: [plugins, creator, desktop]
---

# Actelyo Plugin Creator Skill

Créez de vrais plugins JavaScript pour Law Harness à partir d'une demande.
Utilisez le chargeur et le SDK existants, sans modifier le cœur du logiciel.

## When to Use

L'utilisateur demande un panneau, un calculateur ou une interaction personnalisée
dans son Desktop. Pour une chronologie avec provenance, utilisez `actelyo-atelier`.

## Prerequisites

Un modèle capable de programmer et les outils `read_file`, `patch` et `terminal`.
La fenêtre Atelier fournit la racine locale exacte via `desktopPluginsRoot`.
Ne dérivez jamais cette racine du profil backend : une connexion distante ne
désigne pas le disque du Desktop. Si ce chemin manque, demandez une connexion
locale ou préparez seulement un brouillon sans annoncer son installation.

## How to Run

1. Reformulez brièvement la fonction demandée et ses actions observables.
2. Avec `patch`, créez un dossier de brouillon et un `plugin.js` ESM autonome.
3. Avec `terminal`, vérifiez la syntaxe JavaScript puis exécutez un vrai essai
   des calculs et des interactions. Corrigez les erreurs et retestez.
4. Installez le fichier dans `<racine fournie>/<identifiant>/plugin.js`, avec
   `defaultEnabled: false`. Le chargeur détecte le fichier ; l'utilisateur
   active le plugin dans Capacités → Plugins.

## Quick Reference

Forme d'un plugin d'interface, sans JSX ni compilation requise :

```javascript
import React from 'react'

function Panel() {
  const [count, setCount] = React.useState(0)
  return React.createElement('section', null,
    React.createElement('p', null, String(count)),
    React.createElement('button', { onClick: () => setCount(count + 1) }, 'Ajouter'),
    React.createElement('button', { onClick: () => setCount(0) }, 'Effacer'))
}

export default {
  id: 'mon-compteur',
  name: 'Mon compteur',
  description: 'Compter et remettre à zéro.',
  defaultEnabled: false,
  register(ctx) {
    ctx.register({ id: 'panel', area: 'secondarySidebar', title: 'Compteur',
      render: () => React.createElement(Panel) })
  }
}
```

L'exemple illustre le contrat ; implémentez la fonction réellement demandée.
Imports autorisés : `react`, ses runtimes JSX, `@hermes/plugin-sdk`.
Un fichier `.js` brut ne peut pas contenir de JSX ou TypeScript non compilé.

## Procedure

Utilisez un identifiant stable propre au plugin et un fichier autonome. Le
chargeur appelle `register(ctx)` ; `ctx.register` et `ctx.registerMany` attachent
les panneaux. `ctx.onDispose`, `ctx.setTimeout`, `ctx.setInterval` et
`ctx.addEventListener` assurent leur nettoyage au rechargement et à la désactivation.

Conservez les droits au minimum de la fonction demandée. Pour un calculateur,
aucun réseau, accès aux fichiers ou appel backend n'est nécessaire. Le plugin
s'exécute avec les droits de l'application ; la liste d'imports n'est pas un
sandbox. Ne contournez pas le SDK par `eval`, du code distant, l'injection de
scripts ou la manipulation du DOM du cœur.

Réutilisez les primitives `ui` du SDK lorsqu'elles conviennent et les variables
CSS de l'application. Déclarez des libellés accessibles et une erreur visible
pour les entrées invalides. Un calcul en jours calendaires ne constitue pas
un calcul de délai procédural : ne prétendez pas gérer jours fériés ou règles
juridiques sans implémentation et vérifications correspondantes.

Testez le chargement avec le chargeur réel, le rendu dans React, les boutons,
les cas limites et l'état après désactivation. Si seul `node --check` a été
exécuté, annoncez uniquement une vérification de syntaxe. Un mock du SDK ou
un résultat écrit à la main ne prouve pas que le plugin est utilisable.

## Pitfalls

N'écrivez pas dans `apps/desktop/src` pour installer une extension utilisateur.
Ne dupliquez pas le chargeur, les points de contribution ou le gestionnaire de
plugins. Ne remplacez pas un plugin d'un autre auteur avec le même identifiant.
Les plugins Desktop sont locaux à l'application ; les chronologies de l'Atelier
sont, elles, stockées dans le profil backend.

Un fichier nouvellement installé est désactivé par défaut. Une mise à jour d'un
plugin déjà activé peut se recharger immédiatement : préparez la révision dans
le brouillon et expliquez la modification avant son remplacement. Gardez une
copie de la version précédente pour pouvoir revenir en arrière.

## Verification

Relisez le fichier installé et vérifiez sa présence dans le gestionnaire natif.
Activez-le dans l'environnement de test autorisé, utilisez ses contrôles et
désactivez-le pour vérifier le nettoyage. Rapporter le prompt, les fichiers
produits par le modèle, les erreurs rencontrées, les corrections éventuelles
et les vérifications effectivement réalisées, sans revendiquer une compatibilité
universelle pour tous les modèles ou tous les types de plugins.
