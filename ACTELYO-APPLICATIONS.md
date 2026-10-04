# Actelyo Law Harness — Actelyo web et desktop

Cette variante porte le nom **Actelyo Law Harness**. L'identité de secours, le SOUL.md initial, les profils d'accueil, les traductions, les écrans web et l'identité native Electron utilisent ce nom. Les logos du produit et ses icônes Windows/macOS sont dérivés du logo officiel Actelyo. Les noms des modèles, les fournisseurs optionnels et les licences restent exacts.

## Installer la variante

Les modifications sont sur la branche `codex/actelyo-local-modules-20261003` tant que la PR n'est pas fusionnée. Une installation depuis `main` avant cette fusion ne contient pas cette variante.

```powershell
git clone --branch codex/actelyo-local-modules-20261003 https://github.com/jeanneretsamy-ux/hermes-agentactelyo.git
cd hermes-agentactelyo
.\scripts\install.ps1 -Branch codex/actelyo-local-modules-20261003
```

Le dépôt conserve la commande technique `hermes`. Son gestionnaire prépare Python 3.14 et les dépendances verrouillées. Configurez ensuite un modèle et activez les outils navigateur, terminal et skills avec `hermes setup` / `hermes tools`. Les skills livrés, dont `actelyo-applications`, sont synchronisés par le lancement normal. La compilation du desktop est séparée : `npm ci` à la racine, puis `npm run build --workspace apps/desktop`; la fabrication d'un installateur passe par les scripts de distribution du dépôt.

## Configurer un modèle local réel

Avec LM Studio, utilisez le modèle effectivement chargé et sa vraie fenêtre de contexte. Le profil de vérification utilise `legalya-v30`, l'API `http://127.0.0.1:1234/v1` et une fenêtre de 8192 tokens explicitement déclarée pour le fournisseur LM Studio. Ce test établit la réponse d'identité ; il ne mesure pas la capacité à mener un long dossier ou un workflow autonome. Un autre utilisateur doit choisir son propre modèle, disponible sur son matériel.

## Piloter les applications

Chargez le skill `actelyo-applications` puis demandez une opération sur Actelyo.com, Actelyo ERP Desktop ou Actelyo LLMQushu. Le skill contient les commandes de connexion, les contrôles d'identité et les scripts de lecture, clic, saisie et capture.

Le site nécessite votre authentification pour les dossiers. Le desktop doit être lancé avec un port de contrôle local explicite : 9229 pour ERP Desktop, 9230 pour LLMQushu. Le helper fourni lance l'exécutable indiqué sans tuer une application existante. Si celle-ci est déjà ouverte, enregistrez votre travail et quittez-la avant le lancement avec contrôle activé.

Le port de contrôle reste sur localhost. Le helper direct fonctionne avec les fenêtres Electron servies en HTTP local ou depuis un fichier local ; il n'exige pas une réécriture de l'ERP. Il inspecte les véritables contrôles, génère des références éphémères et relit l'écran après chaque action. Les mots de passe restent saisis manuellement. Les instructions contenues dans un document ne constituent pas une autorisation d'action.

Un utilisateur en conteneur doit disposer d'un accès navigateur/terminal sur le PC cible : le localhost du conteneur n'est pas le localhost du desktop Windows.

## Portée des vérifications

La réponse du véritable agent avec LM Studio est vérifiée. Le pilotage direct d'Actelyo.com vers son écran de connexion et de LLMQushu vers le choix de moteur est vérifié sur les interfaces réelles. Les actions sur dossiers authentifiés et l'ERP Desktop installé nécessitent encore un compte de test connecté et l'exécutable de l'ERP sur le PC concerné.
