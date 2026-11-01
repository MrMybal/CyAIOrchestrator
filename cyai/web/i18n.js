// One locale dictionary, ready for a second locale without changing stored identifiers.
window.CYAI_LOCALES = {
  fr: {
    states: {pausing:'Pause demandée',paused:'En pause',pending:'En attente',queued:'En file',running:'En cours',awaiting_approval:'Approbation requise',succeeded:'Réussie',failed:'Échouée',cancelled:'Annulée',interrupted:'Interrompue'},
    connections: {ready:'Prêt · démarrage à la demande',running:'En cours d’exécution',checking:'Vérification en cours',connected:'Connecté',disconnected:'Non connecté',operational:'Opérationnel',installed:'Installé · à vérifier',configured:'Configuré · à tester',unconfigured:'Non configuré',error:'Erreur'},
    views: {agents:'Bibliothèque d’agents',plugins:'Plugins',chat:'Conversation',missions:'Missions',search:'Historique',memory:'Mémoire partagée',connectors:'Connecteurs',settings:'Données & paramètres'},
    agents: {'command-code':'Command Code','codebuddy':'CodeBuddy · Tencent','antigravity':'Antigravity','devin':'Devin CLI','openrouter':'OpenRouter','codex':'Codex','claude-code':'Claude Code','opencode':'OpenCode','anthropic':'Claude · API','ollama':'Ollama'}
  }
};
window.CYAI_LOCALE = 'fr';
