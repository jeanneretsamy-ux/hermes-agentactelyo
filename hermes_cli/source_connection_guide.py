"""Guided user-owned connections. No credentials or browser cookies enter tool context."""
SETUP_URL = "https://actelyo.com/settings?tab=vault"


def source_connection_guide(provider: str) -> dict:
    guides = {
        "pappers": [
            "Ouvrir le parcours de connexion Actelyo et son espace API Pappers.",
            "Saisir la clé dans le champ sécurisé, jamais dans le chat.",
            "Tester et enregistrer ; les recherches utilisent les crédits du titulaire.",
        ],
        "drive": [
            "Ouvrir le parcours de connexion Actelyo puis Google Drive.",
            "Se connecter directement chez Google et vérifier les autorisations.",
            "Sélectionner les pièces utiles puis tester leur lecture avant rédaction.",
        ],
        "external": [
            "Se connecter directement au service documentaire de son choix.",
            "Raccorder son API ou un connecteur de navigateur compatible aux onglets autorisés.",
            "Tester la lecture d'une pièce ; sinon importer le Word exporté manuellement.",
        ],
    }
    if provider not in guides:
        raise ValueError("Source inconnue : choisir pappers, drive ou external.")
    return {
        "provider": provider, "setup_url": SETUP_URL, "steps": guides[provider],
        "state": "requires_user_setup", "connected": False,
        "secret_in_chat": False, "requires_user_interaction": True,
        "notice": "Le compte en ligne et les coffres locaux sont distincts. Une configuration ou l'ouverture d'un site ne prouve pas l'accès du profil Law Harness ; vérifier son connecteur et une lecture réelle. Les dirigeants ne sont pas le registre des associés.",
    }
