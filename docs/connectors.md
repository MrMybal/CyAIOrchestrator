# Ajouter un connecteur

Le contrat commun est le protocole `Connector` dans `cyai/connectors.py` :

```python
class MyConnector:
    id = "my-provider"
    kind = "model"  # ou "agent" si le fournisseur possède sa propre boucle d’outils

    def __init__(self, id, config, secrets):
        self.id, self.config, self.secrets = id, config, secrets

    def check(self):
        return {"status": "unconfigured", "detail": "Configuration requise",
                "capabilities": ["stream", "cancel"]}

    def models(self):
        return []  # catalogue inconnu, pas de valeurs inventées

    def run(self, prompt, root, model, native_id, control):
        # Lire le protocole officiel ; vérifier la connexion avant toute requête.
        # Appeler control.check() régulièrement, y compris en attente réseau.
        # Émettre les événements documentés ci-dessous.
        raise NotImplementedError("Implémenter le protocole du fournisseur")
```

Enregistrer la classe dans `registry`, ajouter son libellé à `web/i18n.js` et sa présentation à la page Connecteurs. `config` ne contient jamais de secret. Utiliser un coffre adapté à l’OS et la fonction de masquage pour toute donnée persistée.

## Événements

| Type | Données attendues | Effet |
|---|---|---|
| `session` | `native_id` | Sauvegarder immédiatement l’identifiant natif |
| `model` | `model`, éventuellement `provider` | Identifier le modèle réellement déclaré |
| `delta` | `text` | Rendre la réponse progressive et conserver la sortie partielle |
| `tool` | Métadonnées structurées de l’appel | Exposer l’action native réelle |
| `tool_result` | Résultat et statut | Exposer la sortie réelle de l’outil |
| `artifact` | `path`, `content` | Conserver une copie texte du fichier produit |
| `usage` | Champs explicitement fournis | Conserver tokens/coût sans inventer de valeur |
| `provider_error` | Détail de l’erreur | Conserver les diagnostics progressifs |

Retourner la réponse finale uniquement après confirmation de fin par le fournisseur. Un EOF n’est pas un succès. Lever une erreur sur un résultat tronqué ou un échec de protocole. Ne pas convertir une interruption en réponse réussie.

`native_id=None` signifie nouvelle session. Ne jamais utiliser « dernière session » globale pour reprendre : les sessions appartiennent à une conversation précise. Un modèle sans session reçoit tout son contexte reconstruit ; il n’a pas de fausse session native.

## Approbations et annulation

Appeler `control.approve(details)` pour une demande native ; cette fonction bloque jusqu’à la décision, l’annulation ou la limite de durée. Elle rend un booléen à transmettre au fournisseur. Une décision ne doit pas activer un mode permissif permanent. Les capacités non prises en charge doivent être refusées et signalées.

Les processus passent par `spawn` et sont arrêtés avec leur arbre de processus. Aucune concaténation de prompt dans une commande shell. Pour un SDK asynchrone, propager l’annulation à son mécanisme officiel. Pour HTTP, borner les délais de lecture. Une annulation n’annule pas des effets déjà produits chez le fournisseur.

## Modèles avec outils applicatifs

Ne pas appeler un simple endpoint de génération « agent complet ». Fournir explicitement une boucle bornée et des outils avec contrats, validation des chemins, demandes d’approbation et journalisation. Le connecteur Anthropic sert d’exemple : `read_file` et `write_file`, 12 tours maximum, aucune exécution shell arbitraire.

## Validation minimale

Ajouter des tests pour : interprétation des deltas et de la fin, reprise du bon identifiant, erreurs API et EOF, annulation, refus d’approbation, usage absent, chemins hors projet. Puis faire un test réel avec une connexion configurée et noter la version du fournisseur. Tant que ce test n’existe pas, présenter l’intégration comme implémentée mais non vérifiée en conditions réelles.
