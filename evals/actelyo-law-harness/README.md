# Évaluation Actelyo Law Harness — pilote FR v1

Ce pilote interne ne reproduit pas le benchmark indépendant de Justinian. Il mesure des contrôles précis sur dix contrats synthétiques et trois extraits du Code civil vérifiés sur Légifrance le 4 octobre 2026.

## Protocole figé

- Dix cas, deux répétitions indépendantes, deux bras avec le même modèle et température 0.
- Bras `grounded_model` : même consigne REVIEW_PROMPT, mêmes pièces et sources, JSON contraint ; sans planificateur ni filtre temporel ni contrôle bloquant.
- Bras `harness` : pipeline de production Harness.review, planification réelle, filtre temporel, périmètre FR, validation exacte des clauses et des citations.
- Les différences comprennent donc planification, filtrage et contrôles ; ce n'est pas l'ablation d'un seul composant.
- Récupération par connecteur de snapshots fixé : elle fournit les sources prévues indépendamment des requêtes. Elle ne mesure ni le rappel documentaire ni les API Légifrance/Legal Data Hunter réelles.
- Ordre des bras alterné, aucune exécution parallèle contre le modèle local.
- Le manifeste, le corpus, les consignes et les empreintes du code sont écrits avant toute génération. Ne pas modifier le corpus v1 après examen des réponses : créer un v2 et garder un jeu de réserve distinct.
- Les poids du modèle ne sont pas empreintés : le nom d'API peut être un alias. Les répétitions à température 0 peuvent rester corrélées.
- Les sorties sont complètes, jamais tronquées silencieusement. Une erreur ou un dépassement de délai reste dans le dénominateur.
- Aucun document client, abonnement documentaire ou appel cloud n'est utilisé par défaut. Un modèle distant exige --allow-remote ; sa clé reste dans la variable serveur indiquée par --token-env.

## Mesures

`summary.json` sépare les réponses générées, les réponses livrables, les citations introuvables, les blocages, les refus, les échecs techniques et la couverture. Les compteurs ont leurs dénominateurs explicites.

Le proxy mécanique est un indicateur de conformité de structure, de citation et de signal d'information manquante. Il n'est pas le taux de réussite juridique. Un refus sûr à une tâche sans preuve ne démontre pas la capacité à effectuer une revue ; un blocage à une tâche faisable n'est pas une réussite.

La notion de réponse livrable reproduit l'affichage de LawHarnessSettings dans l'ERP : le composant masque l'analyse des rapports bloqués. L'API HTTP/MCP conserve l'analyse brute dans ces rapports. Un autre consommateur doit respecter leur statut ; les chiffres de livraison ne certifient pas toutes les intégrations.

Une citation exacte peut soutenir une interprétation fausse. Des faits, montants, raisonnements, affirmations dans la synthèse et références hors du tableau de citations peuvent être inventés malgré tous les contrôles. `overall_hallucination_rate` et `substantive_legal_success_rate` restent donc null tant qu'aucune adjudication humaine qualifiée n'est fournie.

## Exécution

Depuis la racine du dépôt, Python 3.11+ et serveur local compatible /v1 :

```powershell
python evals/actelyo-law-harness/run.py run --model legalya-v30 --out results/pilot-fr-v1
python evals/actelyo-law-harness/run.py adjudicate --folder results/pilot-fr-v1 --annotations jurist-annotations.json
```

Le dossier de sortie doit être nouveau. Le service est importé depuis integrations/actelyo-law-harness. Aucune dépendance supplémentaire.

Pour tester une nouvelle version du pipeline face au même témoin, utiliser
`--baseline-prompt evals/actelyo-law-harness/baseline-fr-v1.txt`. Le manifeste distingue
les empreintes des deux prompts, et leurs textes sont conservés dans la sortie. La
version corrigée ajoute les identifiants contraints et un audit factuel par le même
modèle. Ce dernier est un contrôle de production faillible, pas le juge du benchmark.
Le corpus v1 déjà examiné constitue maintenant un jeu de régression ; les progrès sur
ce corpus ne prouvent pas une généralisation à des contrats inconnus.

La correction suivante contraint aussi les passages littéraux et contrôle les
références numérotées dans les affirmations. Les compteurs distinguent défauts de
citations structurées et références non fournies dans le texte libre. Ces détecteurs
restent incomplets et ne constituent pas le score d'hallucination sur le fond.
Les séries interrompues pour stabiliser le serveur ou développer une correction
doivent rester marquées incomplètes, séparées de toute série définitive.

Le paquet en aveugle est `blind-answers.json` ; transmettre aussi `dataset.snapshot.json` au juriste. Garder `blind-key.json` et `records.jsonl` à part pendant la notation. La grille `jurist-annotations.template.json` exige le nom du relecteur, son statut de juriste, chaque critère binaire et le constat d'hallucination. La note définitive exige toutes les annotations ; une notation partielle affiche son propre dénominateur. Un second juriste et une procédure de désaccord sont requis avant revendication indépendante.

Les fichiers de résultats ne doivent pas être commités automatiquement. Les données sont destinées à l'évaluation, pas à l'entraînement.

## Référence Justinian

HAQQ publie 27,0 % de réussite globale sur 61 tâches de 21 juridictions, exécutées deux fois ; 5,9 % sur The High Bar ; 100 % sur le checkpoint de références manquantes. Sur la résistance plus large aux hallucinations, le taux de réussite publié est 28,0 %, et non 100 %. Ce sont des résultats rapportés par le fournisseur ; les rapports de l'évaluateur sont privés par défaut.

La comparabilité exige les mêmes tâches, fichiers natifs, critères et conditions, ainsi qu'une notation externe. Notre harnais FR de revue textuelle ne couvre pas actuellement toutes ces juridictions, l'OCR ni les documents Word natifs.

Source : https://www.haqq.ai/blog/legal-ai-benchmark-2026

Textes primaires figés dans le pilote :
- https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000032041115
- https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000032040772
- https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000032010131
