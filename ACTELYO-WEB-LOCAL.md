# Actelyo Law Harness dans le navigateur local

Ce mode utilise le dashboard et le terminal de l’agent, avec ConPTY sous Windows.
Il complète la distribution conteneur décrite dans ACTELYO-LOCAL.md.

Avec les dépendances Python et Node du projet installées :

```powershell
npm run build --workspace ui-tui
npm run build --workspace web
python scripts/actelyo-local-web.py
```

Ouvrir http://127.0.0.1:8091. Le serveur doit rester démarré. `--port`,
`--home` et `--web-dist` permettent de choisir le port, le profil persistant
et les fichiers web déjà construits. Le serveur écoute uniquement sur ce PC.

La première configuration utilise LM Studio sur http://127.0.0.1:1234/v1
et le modèle `legalya-v30`, à charger réellement avec un contexte de 16 384
tokens. Aucun modèle n’est téléchargé par ce lanceur. Un autre fournisseur
ou modèle peut être choisi dans les réglages. Les outils sont découverts
à la demande pour réduire le prompt initial ; les capacités restent celles
des outils installés et configurés. La première réponse peut prendre plusieurs
minutes sur un PC utilisant le CPU.

Le profil par défaut est `~/.actelyo-law-harness/web`, séparé de la passerelle
Telegram. La télémétrie partagée est désactivée dans ce nouveau profil.
Les profils déjà présents conservent leurs réglages.

Depuis Actelyo.com, choisir **Espace IA → Actelyo Law Harness → Sur mon PC**.
Le lien ouvre l’application de cet ordinateur dans un nouvel onglet, sans
transmettre les identifiants du compte Actelyo.
