# Dictée locale Actelyo

Configuration choisie : Whisper local pour la dictée, réponses écrites.

Fusionner les sections de `config.example.yaml` dans le `config.yaml` du profil Actelyo/Hermes utilisé par l'application. Conserver les autres sections et les identifiants existants. Ce fichier YAML configure le moteur vocal du bureau ; le service juridique indépendant conserve son propre `config.toml`.

- `stt.provider: local` doit être enregistré dans le fichier du profil : une sélection explicite refuse le repli cloud si le backend local est indisponible.
- `stt.local.model: base` utilise le modèle multilingue, avec la langue française explicite.
- `voice.auto_tts: false` désactive la lecture automatique par défaut. Si une préférence de lecture a déjà été choisie dans le bureau, désactiver également « Lire les réponses » dans son menu vocal : cette préférence locale prévaut sur le fichier.
- Utiliser la dictée vers le brouillon du message, puis relire avant l'envoi. Ne pas activer le mode conversation vocale.

`faster-whisper` est déjà prévu dans les options `voice`/`stt-whisper` du moteur. Les poids Whisper ne sont pas inclus dans l'installateur et doivent être disponibles localement ; leur acquisition initiale et les performances dépendent du poste. Aucun test avec le microphone de l'utilisateur n'a été effectué.

ElevenLabs est une option du paquet complet, sans rôle dans le service juridique. Ce profil n'utilise ni ElevenLabs ni un autre fournisseur de transcription cloud ; il ne supprime pas le SDK optionnel de l'archive Windows et n'active aucun moteur de synthèse vocale.
