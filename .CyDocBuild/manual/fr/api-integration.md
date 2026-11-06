---
id: api-integration
title: API d’intégration
description: Connecter des clients externes et utiliser les liens d’aide publics.
section: Référence développeur
order: 40
revision: 1
sourceRevision: 1
---

## Connecter un client MCP {#connection}

1. Démarrez CyAI et ouvrez Paramètres → MCP.
2. Choisissez les projets accessibles, le format du client et les droits de lecture/écriture. Générez la configuration et utilisez la commande exacte affichée.
3. Redémarrez ou actualisez la connexion MCP du client externe. Appelez `cyai_actions` pour découvrir les schémas disponibles pour cette connexion.

Le pont stdio communique avec le service CyAI local en cours. `--project` est répétable ; il ne donne pas accès aux autres projets. Les écritures nécessitent `--allow-write`. Les écritures dans la bibliothèque globale nécessitent le droit distinct `--allow-global`. Le pont utilise le jeton stocké localement ; ne copiez aucune valeur d’identification dans les exemples ou les messages.

## Découvrir et appeler les opérations {#operations}

`cyai_actions` accepte un `domain` facultatif et renvoie les définitions d’actions avec leur `inputSchema`, leur périmètre et leurs indicateurs d’écriture et de traitement différé. `cyai_call` accepte `action` et `arguments`. Utilisez le schéma reçu : disponibilité et autorisations dépendent de la connexion courante.

```json
{"domain":"conversations"}
```

Après avoir découvert `get_conversation`, appelez `cyai_call` avec l’identifiant d’une conversation existante :

```json
{"action":"get_conversation","arguments":{"conversation_id":"YOUR_CONVERSATION_ID"}}
```

Les domaines courants couvrent projets, conversations, mémoire, missions, modèles, modèles locaux, plugins, compétences et équipes. Par exemple, `context_preview` inspecte le contexte choisi, `plugins_list` liste les intégrations du projet et `mission_status` suit une mission existante. Le schéma et le périmètre de chaque demande sont contrôlés. La politique d’approbation de la conversation s’applique aux écritures ; l’agent ne peut pas la modifier via `agent_settings`.

## Résultats et travaux en arrière-plan {#results}

`create_mission` prépare une mission sans la lancer ; utilisez ensuite l’opération de lancement découverte. Un identifiant de mission désigne une exécution à suivre jusqu’à son état final. Les opérations différées de l’application renvoient `job_id` : terminez la réponse courante puis consultez `job_status` avec `{"id":"YOUR_JOB_ID"}`. Les téléchargements possèdent leurs propres jobs, suivis via `local_state`. Une opération différée interrompue nécessite une reprise explicite ; elle n’est pas répétée silencieusement.

```diagram
{"type":"flow","title":"Utiliser l’API découverte","nodes":[{"id":"discover","label":"Découvrir le schéma","x":0,"y":0},{"id":"call","label":"Appeler dans le périmètre","x":260,"y":0},{"id":"follow","label":"Suivre résultat ou job","x":520,"y":0}],"edges":[{"from":"discover","to":"call"},{"from":"call","to":"follow"}]}
```

## Liens d’aide Python {#help-links}

Le module `cyai.documentation` expose les fonctions d’URL locale ci-dessous. Son import ne démarre pas le service de l’application. La dépendance de bureau facultative `pywebview` n’est chargée qu’à l’ouverture d’une fenêtre. Ces fonctions renvoient des adresses et des URL ; elles ne présentent pas les points d’accès HTTP internes comme une API tierce stable.

```python
from cyai.documentation import documentation_url

url = documentation_url(
    page_id="start", locale="fr", anchor="help-part-1",
    state={"media": "conversation", "zoom": 1.5}, theme="dark"
)
```

## Paramètres et valeurs de retour {#parameters}

Consultez [documentation_url](doc:api-cyai-documentation-documentation-url-url) pour sa signature, ses paramètres et l’URL renvoyée. [canonical_route](doc:api-cyai-documentation-canonical-route-route) effectue la même validation et renvoie un dictionnaire d’adresse. Les deux lisent `DocData/manifest.json`. Une ancre ou un média explicite invalide lève `ValueError` ; une page inconnue revient à l’accueil du guide.

## Intégration dans une fenêtre native {#native}

`DocumentationWindows(open_settings=None).open(page_id='start', locale='en', anchor='', state=None, theme='dark')` crée ou réutilise la fenêtre d’aide dédiée du processus et renvoie un objet contenant `opened`, `url` et `reader`. Appelez cette méthode depuis un hôte pywebview initialisé. Une nouvelle ouverture fait naviguer le lecteur existant sans remplacer l’espace de travail principal. Le rappel facultatif des paramètres n’accepte que les rubriques connues de l’application ; en lecture autonome, le lien ouvre plutôt le chapitre correspondant.

[Configurer un MCP local](doc:mcp) · [Autorisations](doc:permissions) · [Évaluations en arrière-plan](doc:background)
