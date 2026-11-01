'use strict';
// Global agent library and per-project team composition. Configuration only:
// nothing on these screens starts an agent, and no control here pretends to run one.
const teamsState = {profiles: null, showArchived: false, team: null, focus: null};
const TEAM_ROLES = {chief: ui('Chef de projet'), lead: ui('Lead / chef d’équipe'), member: ui('Membre'), consultant: ui('Consultant · sollicité à la tâche')};
// A consultant answers task requests for what it does better; it owns no branch of the hierarchy.
const HIERARCHY_ROLES = ['chief', 'lead', 'member'];
const CONNECTOR_BADGE = {enabled: ['succeeded', ui('Connecteur activé')], disabled: ['awaiting_approval', ui('Connecteur désactivé')], missing: ['failed', ui('Connecteur absent')]};
const MODEL_BADGE = {default: ['operational', ui('Modèle par défaut du connecteur')], confirmed: ['succeeded', ui('Modèle confirmé')],
  unconfirmed: ['awaiting_approval', ui('Modèle non confirmé')], catalogue_indisponible: ['awaiting_approval', ui('Catalogue indisponible')]};

function profileBadges(status) {
  const connector = CONNECTOR_BADGE[status.connector] || ['failed', ui('Connecteur inconnu')];
  const model = MODEL_BADGE[status.model] || ['awaiting_approval', ui('Modèle non vérifié')];
  return `<span class="status ${connector[0]}" title="${esc(status.connector_detail)}">${esc(connector[1])}</span> <span class="status ${model[0]}" title="${esc(status.model_detail)}">${esc(model[1])}</span>`;
}
function skillChips(skills, attested = []) {
  return skills.length ? `<p class="team-skills">${skills.map(s => attested.includes(s)
    ? ui`<span class="team-chip attested" title="Attestée par vous sur du travail accepté">✓ ${esc(s)}</span>`
    : ui`<span class="team-chip" title="Déclarée, non attestée">${esc(s)}</span>`).join('')}</p>` : ui('<p class="muted">Aucune compétence déclarée.</p>');
}
function connectorDatalist() {
  return `<datalist id="profile-connectors">${(state.data?.connectors || []).map(c => `<option value="${esc(c.id)}">${esc(agentName(c.id))}${c.enabled ? '' : ui(' · désactivé')}</option>`).join('')}</datalist>`;
}
function modelDatalist(connector) {
  const models = state.data?.models_cache?.[connector] || [];
  return `<datalist id="profile-models">${models.map(m => `<option value="${esc(m.id || m)}">${esc(m.name || m.id || m)}</option>`).join('')}</datalist>`;
}

// --- global library -------------------------------------------------------------------------

function profileCategories() {
  return [...new Set((teamsState.profiles || []).map(p => p.category || '').filter(Boolean))].sort((a, b) => a.localeCompare(b, 'fr'));
}
function profileCard(p) {
  return ui`<article class="card team-profile-card" draggable="true" data-profile-card="${esc(p.id)}">
    <div class="card-header"><h3>${p.icon ? esc(p.icon) + ' ' : ''}${esc(p.name)}</h3><span class="status ${p.archived ? 'disconnected' : 'operational'}">${p.archived ? ui('Archivé') : TEAM_ROLES[p.role]}</span></div>
    <p>${esc(p.description || ui('Pas de description.'))}</p>
    ${skillChips(p.skills, p.attested || [])}
    <p><b>${esc(agentName(p.connector) || p.connector)}</b> · ${esc(p.model || ui('modèle par défaut'))}</p>
    <p>${profileBadges(p.status)}</p>
    ${(p.tools || []).length ? ui`<p><small>Outils : ${p.tools.map(id => esc((state.data?.plugins || []).find(x => x.id === id)?.name || id)).join(', ')}</small></p>` : ''}
    ${(p.helpers || []).length ? ui`<p><small>Peut appeler : ${p.helpers.map(h => esc((teamsState.profiles || []).find(x => x.id === h.profile_id)?.name || ui('profil supprimé'))).join(', ')}</small></p>` : ''}
    ${profileMethodsLine(p.id)}
    ${capabilityLine(p)}
    <small>Révision ${p.revision} · ${p.assignments.length} affectation(s) dans ${new Set(p.assignments.map(a => a.project_id)).size} projet(s)</small>
    <div class="row-actions">${p.archived ? '' : ui`<button class="primary" data-profile-dm="${esc(p.id)}" title="Discussion privée, hors de tout projet">Écrire</button>`}<button class="secondary" data-profile-edit="${esc(p.id)}">Modifier</button><button class="secondary" data-profile-methods="${esc(p.id)}" title="Méthodes préférées ou à utiliser, et ses notes">Méthodes</button><button class="secondary" data-profile-duplicate="${esc(p.id)}">Dupliquer</button><button class="text-button" data-profile-history="${esc(p.id)}">Historique ↗</button><button class="text-button" data-profile-record="${esc(p.id)}">Bilan ↗</button><button class="text-button" data-profile-archive="${esc(p.id)}" data-archived="${p.archived ? 'false' : 'true'}">${p.archived ? ui('Réactiver') : ui('Archiver')}</button></div>
  </article>`;
}
async function renderAgentsPage() {
  const result = await action('agent_profile_list');
  if (state.view !== 'agents') return;
  teamsState.profiles = result.profiles;
  methodState.list = (await action('method_list')).methods;
  teamsState.methodSummary = (await action('profile_methods_summary')).profiles;
  await loadCapabilities().catch(() => null);
  if (state.view !== 'agents') return;
  const filter = teamsState.libraryFilter || 'all', active = result.profiles.filter(p => !p.archived);
  const categories = profileCategories();
  const count = list => `<span class="nav-count">${list.length}</span>`;
  const navButton = (key, label, list, drop) => `<button class="${filter === key ? 'selected' : ''}" data-library-filter="${esc(key)}" ${drop !== undefined ? `data-library-drop="${esc(drop)}"` : ''}>${label}${list ? count(list) : ''}</button>`;
  const nav = ui`<nav aria-label="Bibliothèque">
    ${navButton('all', ui('Tous les agents'), active)}
    ${categories.map(c => navButton('cat:' + c, esc(c), active.filter(p => p.category === c), c)).join('')}
    ${navButton('none', ui('Sans catégorie'), active.filter(p => !p.category), '')}
    <button class="nav-add" data-library-category-new>＋ Nouvelle catégorie</button>
    <span class="nav-label">MÉTHODES</span>
    ${navButton('methods', ui('Méthodes'), methodState.list)}
    <span class="nav-label">ARCHIVES</span>
    ${navButton('archived', ui('Profils archivés'), result.profiles.filter(p => p.archived))}
  </nav>`;
  let heading, body;
  if (filter === 'methods') {
    heading = '';
    body = methodsHTML();
  } else {
    const pool = filter === 'archived' ? result.profiles.filter(p => p.archived)
      : filter === 'none' ? active.filter(p => !p.category)
      : filter.startsWith('cat:') ? active.filter(p => p.category === filter.slice(4)) : active;
    const title = filter === 'all' ? ui('Tous les agents') : filter === 'none' ? ui('Sans catégorie') : filter === 'archived' ? ui('Profils archivés') : filter.slice(4);
    const rename = filter.startsWith('cat:') ? ui`<button class="secondary" data-library-category-rename="${esc(filter.slice(4))}">Renommer la catégorie</button>` : '';
    heading = ui`<div class="page-intro"><div><h2>${esc(title)}</h2><p>Des profils réutilisables partout, comme des personnes : écrivez-leur directement, ou affectez-les à l’équipe d’un projet. Glissez une fiche sur une catégorie pour la ranger ; ranger ne crée pas de révision. Une compétence déclarée n’est pas une capacité vérifiée.</p></div><div class="row-actions"><button class="primary" data-profile-new>＋ Nouveau profil</button>${rename}</div></div>`;
    const grouped = filter === 'all' && categories.length
      ? [...categories.map(c => [c, pool.filter(p => p.category === c)]), [ui('Sans catégorie'), pool.filter(p => !p.category)]].filter(([, list]) => list.length)
      : [[null, pool]];
    body = grouped.map(([label, list]) => `${label ? `<h3 class="library-group">${esc(label)} <small>${list.length}</small></h3>` : ''}<div class="card-grid">${list.map(profileCard).join('')}</div>`).join('')
      || `<div class="empty-state">${filter === 'archived' ? ui('Aucun profil archivé.') : filter === 'all' ? ui('Aucun profil. Créez le chef de projet, puis ses leads et ses membres.') : ui('Aucun profil ici. Glissez une fiche sur cette catégorie pour l’y ranger.')}</div>`;
  }
  htmlIfChanged('page', `<div class="settings-layout library-layout">${nav}<section class="settings-content library-content">${heading}${body}</section></div>`);
}

async function fileProfiles(ids, category) {
  let last;
  for (const id of ids) last = await action('agent_profile_category', {id, category});
  return last;
}

function profileForm(profile) {
  const p = profile || {name: '', icon: '', role: 'member', description: '', skills: [], connector: (state.data?.connectors || []).find(c => c.enabled)?.id || 'codex', model: '', prompt: '', settings: {}, helpers: [], tools: []};
  return ui`<div class="fields">
    <div class="two-fields">
      <label>Nom affiché<input name="name" value="${esc(p.name)}" maxlength="120" required autofocus></label>
      <label>Icône (emoji ou 1-2 caractères)<input name="icon" value="${esc(p.icon || '')}" maxlength="8" placeholder="🛠"></label>
    </div>
    <label>Catégorie dans la bibliothèque<input name="category" list="profile-categories" value="${esc(p.category || (teamsState.libraryFilter || '').replace(/^cat:/, '').replace(/^(all|none|methods|archived)$/, ''))}" maxlength="60" placeholder="3D, Recherche, Code…"><datalist id="profile-categories">${profileCategories().map(c => `<option value="${esc(c)}">`).join('')}</datalist><small class="field-help">Rangement seulement : aucune révision n’est créée.</small></label>
    <label>Rôle conseillé<select name="role">${Object.entries(TEAM_ROLES).map(([k, v]) => `<option value="${k}" ${k === p.role ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
    <p class="field-help">Le rôle conseillé oriente l’affectation ; c’est l’équipe du projet qui fixe le rôle effectif.</p>
    <label>Description<textarea name="description" rows="2" maxlength="2000">${esc(p.description)}</textarea></label>
    <label>Compétences déclarées (une par ligne ou séparées par des virgules)<textarea name="skills" rows="3">${esc(p.skills.join('\n'))}</textarea></label>
    <div class="row-actions"><button type="button" class="text-button" data-profile-capabilities>Compléter depuis les capacités du modèle</button><small class="field-help">Ajoute les domaines où le modèle choisi est estimé à 7/10 ou plus (vos notes, vos projets, benchmarks, estimation d’IA). Vous modifiez librement.</small></div>
    <div class="two-fields">
      <label>Connecteur<input name="connector" id="profile-connector" list="profile-connectors" value="${esc(p.connector)}" required></label>
      <label>Modèle (vide = défaut du connecteur)<input name="model" id="profile-model" list="profile-models" value="${esc(p.model)}"></label>
    </div>${connectorDatalist()}${modelDatalist(p.connector)}
    <div class="row-actions"><button type="button" class="secondary" data-profile-catalog>Actualiser le catalogue du connecteur</button></div>
    <p class="field-help" id="profile-status">${profile ? profileBadges(profile.status) : ui('Le connecteur et le modèle sont vérifiés à l’enregistrement, puis affichés sur la fiche.')}</p>
    <label>Consignes initiales / préprompt<textarea name="prompt" rows="6" maxlength="20000">${esc(p.prompt)}</textarea></label>
    <div class="two-fields">
      <label>Effort de raisonnement (si le connecteur le propose)<input name="effort" value="${esc(p.settings.effort || '')}" placeholder="vide = défaut"></label>
      <label>Vitesse de service (Codex uniquement)<input name="service_tier" value="${esc(p.settings.service_tier || '')}" placeholder="vide = défaut"></label>
    </div>
    <label>Spécialistes que cet agent peut appeler pendant son travail
      <select name="helpers" multiple size="4">${(teamsState.profiles || []).filter(x => !x.archived && x.id !== profile?.id).map(x => `<option value="${esc(x.id)}" ${(p.helpers || []).some(h => h.profile_id === x.id) ? 'selected' : ''}>${x.icon ? esc(x.icon) + ' ' : ''}${esc(x.name)} · ${esc(x.connector)}</option>`).join('')}</select></label>
    <label>Outils (plugins) que cet agent peut utiliser directement
      <select name="tools" multiple size="3">${(state.data?.plugins || []).filter(x => x.type === 'mcp').map(x => `<option value="${esc(x.id)}" ${(p.tools || []).includes(x.id) ? 'selected' : ''}>${esc(x.name || x.id)}${x.enabled ? '' : ui(' · désactivé')}</option>`).join('') || ui('<option disabled>Aucun plugin MCP configuré</option>')}</select></label>
    <p class="field-help">Par exemple un serveur MCP Blender pour un modeleur. Un outil en lecture s’utilise librement ; un outil qui agit passe par votre autorisation, comme un outil natif. Chaque appel est enregistré. Déclarer un outil est une permission : CyAI ne vérifie pas que le plugin fait ce que son nom annonce.</p>
    <p class="field-help">Pendant son exécution, cet agent verra un outil pour solliciter ces spécialistes — par exemple faire produire des images de référence avant de modéliser. Chaque appel est enregistré dans la chaîne, un spécialiste ne peut pas en appeler un autre, et le nombre d’appels par étape est plafonné. Sa réponse est un compte rendu, pas une preuve.</p>
    <label>Note de révision (facultative)<input name="note" maxlength="400" placeholder="Ce qui change et pourquoi"></label>
    <p class="field-help">Chaque modification crée une nouvelle révision. Les équipes existantes conservent la leur jusqu’à une adoption explicite.</p>
  </div>`;
}

function openProfileDialog(profile) {
  openDialog(profile ? ui('Modifier le profil') : ui('Nouveau profil d’agent'), profileForm(profile), async form => {
    const values = Object.fromEntries(form);
    const helpers = form.getAll('helpers').map(id => ({profile_id: id,
      purpose: (profile?.helpers || []).find(h => h.profile_id === id)?.purpose || ''}));
    const settings = {};
    if (values.effort.trim()) settings.effort = values.effort.trim();
    if (values.service_tier.trim()) settings.service_tier = values.service_tier.trim();
    const result = await action('agent_profile_save', {...(profile ? {id: profile.id} : {}), name: values.name, role: values.role,
      icon: values.icon, category: values.category.trim(), description: values.description, skills: values.skills, connector: values.connector,
      model: values.model, prompt: values.prompt, settings, helpers, tools: form.getAll('tools'), note: values.note});
    toast(result.notice || ui('Profil enregistré · révision ') + result.revision + '.');
  }, profile ? ui('Enregistrer la révision') : ui('Créer le profil'));
}

// --- project team ---------------------------------------------------------------------------

function memberById(id) { return (teamsState.team?.members || []).find(m => m.id === id); }
function override(member, field) { return (member.overridden || []).includes(field) ? ui(' <span class="status awaiting_approval">modifié ici</span>') : ''; }
function eligibleManagers(exclude) {
  const members = teamsState.team?.members || [];
  const banned = new Set();
  if (exclude) {
    const walk = id => members.filter(m => m.manager_id === id).forEach(m => { banned.add(m.id); walk(m.id); });
    banned.add(exclude); walk(exclude);
  }
  return members.filter(m => m.active && (m.role === 'chief' || m.role === 'lead') && !banned.has(m.id));
}
function isConsultant(id) { return memberById(id)?.role === 'consultant';
}
function managerOptions(selected, exclude) {
  return ui`<option value="">Aucun responsable (à compléter)</option>` + eligibleManagers(exclude).map(m =>
    `<option value="${esc(m.id)}" ${m.id === selected ? 'selected' : ''}>${esc(m.definition.name)} · ${TEAM_ROLES[m.role]}</option>`).join('');
}
function memberCardHTML(member, issues) {
  const own = issues.filter(i => i.member_id === member.id);
  const subordinates = (teamsState.team.members || []).filter(m => m.active && m.manager_id === member.id);
  return ui`<div class="team-node ${teamsState.focus === member.id ? 'focused' : ''}" id="team-node-${esc(member.id)}">
    <div class="team-node-head"><strong>${member.definition.icon ? esc(member.definition.icon) + ' ' : ''}${esc(member.definition.name)}</strong><span class="status ${member.role === 'chief' ? 'operational' : 'connected'}">${TEAM_ROLES[member.role]}</span>${member.active ? '' : ui('<span class="status disconnected">Retiré</span>')}</div>
    <small>${esc(agentName(member.definition.connector) || member.definition.connector)} · ${esc(member.definition.model || ui('modèle par défaut'))} · révision figée ${member.profile_revision}${member.update_available ? ui(' · révision ') + member.profile_revision_current + ' disponible' : ''}${member.profile_archived ? ui(' · profil archivé') : ''}${member.override_labels?.length ? ui(' · modifié ici : ') + member.override_labels.map(esc).join(', ') : ''}</small>
    <p>${profileBadges(member.status)}</p>
    <p class="team-responsibility">${esc(member.responsibility || ui('Responsabilité locale à préciser.'))}</p>
    ${own.map(i => `<p class="team-issue">⚠ ${esc(i.message)}</p>`).join('')}
    <div class="row-actions">
      <button class="secondary" data-member-edit="${esc(member.id)}">Modifier</button>
      ${member.active ? ui`<button class="secondary" data-member-chat="${esc(member.id)}">Discuter ↗</button>` : ''}
      ${member.update_available ? ui`<button class="secondary" data-member-revision="${esc(member.id)}">Voir la révision ${member.profile_revision_current}</button>` : ''}
      ${member.active ? ui`<button class="text-button danger" data-member-remove="${esc(member.id)}" data-subordinates="${subordinates.length}">Retirer</button>`
                      : ui`<button class="text-button" data-member-restore="${esc(member.id)}">Réintégrer</button>`}
    </div></div>`;
}
function teamTreeHTML(members, issues) {
  const active = members.filter(m => m.active && m.role !== 'consultant');
  const consultants = members.filter(m => m.active && m.role === 'consultant');
  const children = id => active.filter(m => m.manager_id === id && m.id !== id);
  const rendered = new Set();
  const branch = member => {
    if (rendered.has(member.id)) return '';
    rendered.add(member.id);
    const kids = children(member.id).map(branch).join('');
    return `<li>${memberCardHTML(member, issues)}${kids ? `<ul class="team-branch">${kids}</ul>` : ''}</li>`;
  };
  const roots = active.filter(m => !m.manager_id || !active.some(x => x.id === m.manager_id));
  let html = roots.map(branch).join('');
  const orphans = active.filter(m => !rendered.has(m.id));
  if (orphans.length) html += orphans.map(m => `<li>${memberCardHTML(m, issues)}</li>`).join('');
  const retired = members.filter(m => !m.active);
  const advisory = consultants.length ? ui`<div class="team-panel"><h4>Consultants · sollicités à la tâche</h4><p>Hors hiérarchie : ils ne dirigent personne et ne rendent pas compte à un responsable. On les sollicite sur une tâche précise pour ce qu’ils font mieux. La sollicitation elle-même arrive avec le board.</p><ul class="team-tree">${consultants.map(m => `<li>${memberCardHTML(m, issues)}</li>`).join('')}</ul></div>` : '';
  return `<ul class="team-tree">${html || ui('<li class="empty-state">Aucun agent actif. Commencez par le chef de projet.</li>')}</ul>` + advisory +
    (retired.length ? ui`<details class="event"><summary>${retired.length} agent(s) retiré(s)</summary><ul class="team-tree">${retired.map(m => `<li>${memberCardHTML(m, issues)}</li>`).join('')}</ul></details>` : '');
}

async function teamTabHTML(project=state.project) {
  const data = await action('team_get', {project_id: project});
  if(state.project!==project)return '';
  teamsState.team = data;
  const board = `<p class="field-help">${esc(data.notice)}</p>`;
  if (!data.team) {
    return ui`<div class="page-heading"><div><small>ÉQUIPE DU PROJET</small><h3>Aucune équipe pour ce projet</h3></div></div>
      <p>Composez une équipe à partir de la bibliothèque globale : un chef de projet, des leads et des membres. La composition est enregistrée telle quelle ; aucune conversation ni exécution n’est créée.</p>
      <div class="row-actions"><button class="primary" data-team-create>Créer l’équipe</button><button class="secondary" data-view="agents">Ouvrir la bibliothèque d’agents</button>${data.templates.length ? ui('<button class="secondary" data-team-apply-template>Appliquer un modèle d’équipe</button>') : ''}</div>${board}`;
  }
  const ready = data.team.status === 'ready' && !data.issues.length;
  const problems = data.issues.length ? ui`<div class="team-panel"><h4>À corriger avant de déclarer l’équipe prête</h4><ul class="team-problems">${data.issues.map(i =>
    `<li>${esc(i.message)} ${i.member_id ? ui`<button class="text-button" data-member-edit="${esc(i.member_id)}">Corriger ↗</button>` : ui`<button class="text-button" data-team-rename>Corriger ↗</button>`}</li>`).join('')}</ul></div>`
    : ui('<div class="team-panel"><h4>Composition valide</h4><p>Chaque branche remonte au chef de projet. « Prête » décrit la configuration, pas une exécution.</p></div>');
  const warnings = data.warnings.length ? ui`<details class="event"><summary>${data.warnings.length} avertissement(s) d’exécution · n’empêchent pas la configuration</summary><ul>${data.warnings.map(w => `<li>${esc(w.message)}</li>`).join('')}</ul><p class="field-help">Ces points concernent une future exécution. Ils ne bloquent ni l’enregistrement ni la déclaration « prête », et ne valent pas un statut « prêt à exécuter ».</p></details>` : '';
  return ui`<div class="page-heading"><div><small>ÉQUIPE DU PROJET</small><h3>${esc(data.team.name)}</h3></div><span class="status ${ready ? 'succeeded' : 'awaiting_approval'}">${ready ? ui('Composition prête') : ui('Brouillon')}</span></div>
    <div class="row-actions">
      <button class="primary" data-team-add>＋ Ajouter un agent</button>
      <button class="secondary" data-team-rename>Renommer</button>
      ${ready ? ui('<button class="secondary" data-team-status="draft">Repasser en brouillon</button>') : ui('<button class="secondary" data-team-status="ready">Déclarer l’équipe prête</button>')}
      <button class="secondary" data-team-save-template>Enregistrer comme modèle</button>
      <button class="secondary" data-team-apply-template>Appliquer un modèle</button>
      <button class="text-button" data-view="agents">Bibliothèque d’agents ↗</button>
    </div>
    ${problems}${warnings}
    <div id="team-scorecard"></div>
    <div id="team-learning"></div>
    ${teamTreeHTML(data.members, data.issues)}
    ${board}`;
}

async function teamLearningHTML(project=state.project) {
  const memory = await action('agent_memory_list', {scope: 'member', project_id: project});
  const proposals = (await action('improvement_list', {project_id: project})).proposals;
  const pending = proposals.filter(p => p.status === 'proposed');
  return ui`<details class="event" ${pending.length ? 'open' : ''}><summary>Mémoire des agents et propositions · ${memory.entries.length} observation(s), ${pending.length} à décider</summary>
    <p class="field-help">${esc(memory.notice)}</p>
    <h4>Observations locales</h4>
    <p class="field-help">Ce qu’un agent a appris <b>dans ce projet</b>. Ces notes ne partent jamais ailleurs toutes seules : il faut une proposition que vous adoptez.</p>
    ${memory.entries.map(e => ui`<p class="board-execution"><b>${esc(e.member)}</b>${e.category ? ' · ' + esc(e.category) : ''} · ${date(e.created_at)}<br>${esc(e.content)}<br><small>${e.source_ids.length} source(s) · <button type="button" class="text-button" data-memory-edit="${esc(e.id)}" data-member="${esc(e.member_id)}">Modifier</button> · <button type="button" class="text-button danger" data-memory-delete="${esc(e.id)}">Supprimer</button></small></p>`).join('') || ui('<p class="muted">Aucune observation enregistrée.</p>')}
    <div class="row-actions"><button type="button" class="secondary" data-memory-new>Ajouter une observation</button><button type="button" class="secondary" data-proposal-new>Proposer une amélioration</button></div>
    <h4>Propositions d’amélioration</h4>
    ${proposals.map(p => ui`<details class="event"><summary>${esc(p.profile)} · ${esc(p.kind_label)} · ${esc(p.status_label)}</summary>
      <p><b>Motif</b><br>${esc(p.rationale)}</p>
      ${p.current_value ? ui`<p><b>Actuel</b></p><pre class="context-pre">${esc(p.current_value)}</pre>` : ''}
      <p><b>Proposé</b></p><pre class="context-pre">${esc(p.proposed_value)}</pre>
      <small>${p.source_ids.length} source(s)${p.source_ids.length === 1 ? ui(' — une seule : vérifiez qu’il ne s’agit pas d’un incident isolé') : ''}${p.decided_at ? ui(' · décidée le ') + date(p.decided_at) : ''}${p.revision ? ui(' · révision ') + p.revision : ''}</small>
      ${p.decision ? `<p><small>${esc(p.decision)}</small></p>` : ''}
      ${p.status === 'proposed' ? ui`<div class="row-actions"><button type="button" class="primary" data-proposal-decide="${esc(p.id)}" data-adopt="true">Adopter</button><button type="button" class="secondary" data-proposal-decide="${esc(p.id)}" data-adopt="false">Écarter</button></div>` : ''}</details>`).join('') || ui('<p class="muted">Aucune proposition.</p>')}
  </details>`;
}

function openMemberDialog(id) {
  const member = memberById(id);
  if (!member) return;
  const subordinates = teamsState.team.members.filter(m => m.active && m.manager_id === id);
  openDialog(ui('Affectation · ') + member.definition.name, ui`<div class="fields">
    <p>Profil <b>${esc(member.profile_name)}</b>, révision figée ${member.profile_revision}${member.profile_archived ? ui(' · profil archivé dans la bibliothèque') : ''}.</p>
    <label>Rôle dans cette équipe<select name="role">${Object.entries(TEAM_ROLES).map(([k, v]) => `<option value="${k}" ${k === member.role ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
    <label>Responsable<select name="manager_id">${managerOptions(member.manager_id, member.id)}</select></label>
    <p class="field-help">Un chef de projet n’a pas de responsable. Seuls un chef ou un lead peuvent en diriger d’autres, et une boucle hiérarchique est refusée par le service.</p>
    <label>Responsabilité locale<textarea name="responsibility" rows="3" maxlength="2000">${esc(member.responsibility)}</textarea></label>
    <details ${member.overridden?.length ? 'open' : ''}><summary>Modifier cet agent dans ce projet${member.overridden?.length ? ' · ' + member.override_labels.join(', ') : ''}</summary>
      <p class="field-help"><b>À manier avec précaution.</b> Ces champs viennent de la révision figée ${member.profile_revision} du profil.
        Les modifier ici crée une <b>surcharge locale à cette affectation</b> : ni le profil global, ni les autres projets ne changent.
        Une surcharge reste prioritaire même après l’adoption d’une nouvelle révision — il faudra la retirer pour retrouver la valeur du profil.
        Pour un changement durable et partagé, modifiez plutôt le profil dans la bibliothèque.</p>
      <div class="two-fields">
        <label>Nom${override(member, 'name')}<input name="o_name" value="${esc(member.definition.name)}" maxlength="120"></label>
        <label>Icône${override(member, 'icon')}<input name="o_icon" value="${esc(member.definition.icon || '')}" maxlength="8"></label>
      </div>
      <label>Description${override(member, 'description')}<textarea name="o_description" rows="2" maxlength="2000">${esc(member.definition.description || '')}</textarea></label>
      <label>Compétences déclarées${override(member, 'skills')}<textarea name="o_skills" rows="2">${esc((member.definition.skills || []).join('\n'))}</textarea></label>
      <div class="two-fields">
        <label>Connecteur${override(member, 'connector')}<input name="o_connector" list="member-connectors" value="${esc(member.definition.connector)}"></label>
        <label>Modèle${override(member, 'model')}<input name="o_model" value="${esc(member.definition.model || '')}" placeholder="vide = défaut du connecteur"></label>
      </div>
      <datalist id="member-connectors">${(state.data?.connectors || []).map(c => `<option value="${esc(c.id)}">${esc(agentName(c.id))}</option>`).join('')}</datalist>
      <label>Consignes initiales${override(member, 'prompt')}<textarea name="o_prompt" rows="6" maxlength="20000">${esc(member.definition.prompt || '')}</textarea></label>
      <div class="two-fields">
        <label>Effort${override(member, 'settings')}<input name="o_effort" value="${esc(member.definition.settings?.effort || '')}" placeholder="vide = défaut"></label>
        <label>Vitesse (Codex)<input name="o_service_tier" value="${esc(member.definition.settings?.service_tier || '')}" placeholder="vide = défaut"></label>
      </div>
      <label>Outils (plugins)${override(member, 'tools')}
        <select name="o_tools" multiple size="3">${(state.data?.plugins || []).filter(x => x.type === 'mcp').map(x => `<option value="${esc(x.id)}" ${(member.definition.tools || []).includes(x.id) ? 'selected' : ''}>${esc(x.name || x.id)}</option>`).join('')}</select></label>
      <label>Spécialistes appelables${override(member, 'helpers')}
        <select name="o_helpers" multiple size="4">${(teamsState.team?.library || []).filter(x => !x.archived).map(x => `<option value="${esc(x.id)}" ${(member.definition.helpers || []).some(h => h.profile_id === x.id) ? 'selected' : ''}>${esc(x.name)} · ${esc(x.connector)}</option>`).join('')}</select></label>
      ${member.overridden?.length ? ui`<label><span><input type="checkbox" name="reset"> Effacer mes modifications locales et revenir à la révision figée ${member.profile_revision}</span></label>` : ''}
    </details>
    ${subordinates.length ? ui`<label>Si cet agent perd son autorité, réaffecter ses ${subordinates.length} subordonné(s) à<select name="reassign_to"><option value="">Personne (équipe explicitement incomplète)</option>${eligibleManagers(member.id).map(m => `<option value="${esc(m.id)}">${esc(m.definition.name)}</option>`).join('')}</select></label>` : ''}
    <details><summary>Consignes initiales figées pour cette affectation</summary><pre class="context-pre">${esc(member.definition.prompt || ui('Aucune consigne enregistrée dans cette révision.'))}</pre></details>
  </div>`, async form => {
    const values = Object.fromEntries(form);
    const settings = {};
    if (values.o_effort?.trim()) settings.effort = values.o_effort.trim();
    if (values.o_service_tier?.trim()) settings.service_tier = values.o_service_tier.trim();
    const overrides = form.has('reset') ? {} : {name: values.o_name, icon: values.o_icon, description: values.o_description,
      skills: values.o_skills, connector: values.o_connector, model: values.o_model, prompt: values.o_prompt, settings,
      tools: form.getAll('o_tools'),
      helpers: form.getAll('o_helpers').map(id => ({profile_id: id,
        purpose: (member.definition.helpers || []).find(h => h.profile_id === id)?.purpose || ''}))};
    const result = await action('team_update_member', {project_id: state.project, id, role: values.role, manager_id: values.manager_id || '',
      responsibility: values.responsibility, overrides,
      ...(values.reassign_to ? {reassign_to: values.reassign_to} : {acknowledged: true})});
    teamsState.focus = id;
    toast(result.notice);
  });
}

function openAddMemberDialog() {
  const library = (teamsState.team?.library || []).filter(p => !p.archived);
  if (!library.length) { openDialog(ui('Aucun profil disponible'), ui('<p>La bibliothèque globale est vide ou entièrement archivée. Créez un profil d’agent avant de composer l’équipe.</p><div class="row-actions"><button type="button" class="secondary" data-view="agents">Ouvrir la bibliothèque ↗</button></div>'), null); return; }
  openDialog(ui('Ajouter un agent à l’équipe'), ui`<div class="fields">
    <label>Profil global<select name="profile_id">${library.map(p => ui`<option value="${esc(p.id)}">${esc(p.name)} · ${TEAM_ROLES[p.role]} · ${esc(p.connector)}${p.model ? ' / ' + esc(p.model) : ''} · révision ${p.revision}</option>`).join('')}</select></label>
    <label>Rôle dans cette équipe<select name="role"><option value="">Rôle conseillé du profil</option>${Object.entries(TEAM_ROLES).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
    <label>Responsable<select name="manager_id">${managerOptions(null, null)}</select></label>
    <label>Responsabilité locale<textarea name="responsibility" rows="3" placeholder="Ce dont cet agent répond dans ce projet"></textarea></label>
    <p class="field-help">L’agent est affecté avec une copie figée de la révision courante du profil. Aucun agent n’est démarré et aucune session fournisseur n’est ouverte.</p>
  </div>`, async form => {
    const values = Object.fromEntries(form);
    const result = await action('team_add_member', {project_id: state.project, profile_id: values.profile_id, role: values.role || undefined,
      manager_id: values.manager_id, responsibility: values.responsibility});
    teamsState.focus = result.id;
    toast(result.notice);
  }, ui('Affecter au projet'));
}

async function openRevisionDialog(id) {
  const preview = await action('team_revision_preview', {project_id: state.project, id});
  const member = memberById(id);
  const rows = preview.changes.map(c => `<tr><td>${esc(c.label)}</td><td><pre class="context-pre">${esc(JSON.stringify(c.from, null, 1))}</pre></td><td><pre class="context-pre">${esc(JSON.stringify(c.to, null, 1))}</pre></td></tr>`).join('');
  openDialog(ui('Révision ') + preview.from_revision + ' → ' + preview.to_revision + ' · ' + member.definition.name,
    ui`<p>${esc(preview.notice)}</p><div class="table-scroll"><table class="project-table"><thead><tr><th>Champ</th><th>Révision figée ${preview.from_revision}</th><th>Révision ${preview.to_revision}</th></tr></thead><tbody>${rows || ui('<tr><td colspan="3">Aucune différence entre ces deux révisions.</td></tr>')}</tbody></table></div><p class="field-help">L’adoption ne concerne que cette affectation. Les autres projets gardent la révision qu’ils utilisent.</p>`,
    async () => { const r = await action('team_adopt_revision', {project_id: state.project, id, revision: preview.to_revision}); teamsState.focus = id; toast(r.notice); },
    ui('Adopter la révision ') + preview.to_revision);
}

function openRemoveDialog(id, subordinates) {
  const member = memberById(id);
  openDialog(ui('Retirer ') + member.definition.name, ui`<div class="fields">
    <p>L’affectation est conservée et réintégrable ; elle n’est pas supprimée de l’historique.</p>
    ${subordinates ? ui`<label>Réaffecter ses ${subordinates} subordonné(s) à<select name="reassign_to"><option value="">Personne : laisser l’équipe explicitement incomplète</option>${eligibleManagers(id).map(m => `<option value="${esc(m.id)}">${esc(m.definition.name)} · ${TEAM_ROLES[m.role]}</option>`).join('')}</select></label>` : ''}
    <label><span><input type="checkbox" name="delete"> Supprimer définitivement cette affectation de la composition</span></label>
  </div>`, async form => {
    const values = Object.fromEntries(form);
    const r = await action('team_remove_member', {project_id: state.project, id, reassign_to: values.reassign_to || '', acknowledged: true, delete: form.has('delete')});
    toast(r.notice);
  }, ui('Retirer'));
}

function openTemplateDialogs(mode) {
  if (mode === 'save') {
    openDialog(ui('Enregistrer la composition comme modèle'), ui`<div class="fields">
      <label>Nom du modèle<input name="name" required autofocus maxlength="120" value="${esc(teamsState.team.team.name)}"></label>
      <label>Description<textarea name="description" rows="2" maxlength="2000"></textarea></label>
      <p class="field-help">Le modèle reprend profils, révisions, rôles, responsabilités et liens hiérarchiques. Il ne copie ni tâches, ni discussions, ni sessions natives, ni mémoire du projet.</p></div>`,
      async form => { const r = await action('team_save_template', {project_id: state.project, ...Object.fromEntries(form)}); toast(r.notice); }, ui('Enregistrer le modèle'));
    return;
  }
  const templates = teamsState.team.templates || [];
  if (!templates.length) { openDialog(ui('Aucun modèle d’équipe'), ui('<p>Enregistrez d’abord une composition comme modèle depuis un projet.</p>'), null); return; }
  const occupied = (teamsState.team.members || []).length;
  openDialog(ui('Appliquer un modèle d’équipe'), ui`<div class="fields">
    <label>Modèle<select name="template_id">${templates.map(t => `<option value="${esc(t.id)}">${esc(t.name)} · ${t.composition.members.length} agent(s)</option>`).join('')}</select></label>
    ${occupied ? ui`<label><span><input type="checkbox" name="replace" required> Remplacer les ${occupied} affectation(s) actuelles de ce projet</span></label>` : ''}
    <p class="field-help">De nouveaux identifiants d’affectation sont générés et la hiérarchie est reconstruite. Rien n’est importé du projet d’origine en dehors de la composition.</p></div>`,
    async form => { const r = await action('team_apply_template', {project_id: state.project, template_id: form.get('template_id'), replace: form.has('replace')}); toast(r.notice); }, ui('Appliquer'));
}

// --- delegated actions ----------------------------------------------------------------------

document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button) return;
  const d = button.dataset;
  try {
    if (d.view && $('dialog').open) $('dialog').close();
    if (button.hasAttribute('data-profile-new')) openProfileDialog(null);
    if (button.hasAttribute('data-profile-archives')) { teamsState.showArchived = !teamsState.showArchived; $('page')._rendered = null; await renderAgentsPage(); }
    if (d.libraryFilter) { teamsState.libraryFilter = d.libraryFilter; $('page')._rendered = null; await renderAgentsPage(); }
    if (d.profileDm) {
      const r = await action('agent_direct_message', {profile_id: d.profileDm});
      toast(r.notice); await refresh(true); await selectConversation(r.id);
    }
    if (button.hasAttribute('data-library-category-new')) {
      openDialog(ui('Nouvelle catégorie'), ui`<div class="fields"><label>Nom<input name="name" maxlength="60" required autofocus placeholder="3D, Recherche, Code…"></label>
        <fieldset class="profile-picks"><legend>Profils à y ranger</legend>${(teamsState.profiles || []).filter(p => !p.archived).map(p => `<label><input type="checkbox" name="ids" value="${esc(p.id)}"> ${p.icon ? esc(p.icon) + ' ' : ''}${esc(p.name)}${p.category ? ' <small>(' + esc(p.category) + ')</small>' : ''}</label>`).join('')}</fieldset>
        <p class="field-help">Une catégorie existe tant qu’un profil y est rangé. Ranger ne crée pas de révision.</p></div>`,
        async form => {
          const name = form.get('name').trim(), ids = form.getAll('ids');
          if (!ids.length) throw new Error(ui('Choisissez au moins un profil : une catégorie vide ne serait pas conservée.'));
          await fileProfiles(ids, name); teamsState.libraryFilter = 'cat:' + name; toast(ui('Catégorie « ') + name + ui(' » créée.'));
        }, ui('Créer'));
    }
    if (d.libraryCategoryRename) {
      const old = d.libraryCategoryRename;
      openDialog(ui('Renommer « ') + old + ' »', ui`<label>Nouveau nom (vide pour retirer la catégorie)<input name="name" maxlength="60" value="${esc(old)}"></label>`,
        async form => {
          const name = form.get('name').trim();
          await fileProfiles((teamsState.profiles || []).filter(p => p.category === old).map(p => p.id), name);
          teamsState.libraryFilter = name ? 'cat:' + name : 'none';
        }, ui('Renommer'));
    }
    if (d.profileEdit) openProfileDialog(await action('agent_profile_get', {id: d.profileEdit}));
    if (d.profileDuplicate) {
      const profile = await action('agent_profile_get', {id: d.profileDuplicate});
      openDialog(ui('Dupliquer ') + profile.name, ui`<p>La copie est un profil indépendant : elle ne partage ni révisions, ni affectations, ni conversation avec l’original.</p><label>Nom de la copie<input name="name" value="${esc(profile.name + ' (copie)')}" required autofocus></label>`,
        async form => { const r = await action('agent_profile_duplicate', {id: profile.id, name: form.get('name')}); toast(r.notice); }, ui('Dupliquer'));
    }
    if (d.profileHistory) {
      const profile = await action('agent_profile_get', {id: d.profileHistory});
      openDialog(ui('Historique des révisions · ') + profile.name, ui`<p>Révision courante : ${profile.revision}. Les affectations gardent la révision qu’elles ont figée.</p>` +
        profile.revisions.map(r => ui`<details class="event"${r.revision === profile.revision ? ' open' : ''}><summary>Révision ${r.revision} · ${date(r.created_at)}${r.note ? ' · ' + esc(r.note) : ''}</summary><pre class="context-pre">${esc(JSON.stringify(r.definition, null, 2))}</pre></details>`).join('') +
        (profile.assignments.length ? ui`<h4>Affectations</h4><ul>${profile.assignments.map(a => ui`<li>${esc(a.project)} · ${TEAM_ROLES[a.role]} · révision ${a.profile_revision}${a.active ? '' : ui(' · retiré')}</li>`).join('')}</ul>` : ui('<p>Aucune affectation.</p>')), null);
    }
    if (d.profileRecord) {
      const profile = (teamsState.profiles || []).find(x => x.id === d.profileRecord);
      const r = await action('profile_track_record', {profile_id: d.profileRecord});
      const rec = r.record, att = Object.fromEntries(r.attestations.map(a => [a.skill, a]));
      openDialog(ui('Bilan · ') + profile.name, ui`<p class="field-help">${esc(r.notice)}</p>
        <div class="project-stats"><div><b>${rec.tasks}</b> tâche(s)</div><div><b>${rec.accepted}</b> acceptée(s)</div><div><b>${rec.executions}</b> exécution(s), ${rec.failed_executions} échouée(s)</div></div>
        <h4>Évaluations (${rec.evaluations})</h4>
        ${Object.keys(rec.averages).length ? `<ul class="board-history">${Object.entries(rec.averages).map(([k, v]) => ui`<li>${esc(k)} : <b>${v.average}</b>/5 <small>sur ${v.count} évaluation(s)${v.count < 3 ? ui(' — trop peu pour conclure') : ''}</small></li>`).join('')}</ul>` : ui('<p class="muted">Aucune évaluation enregistrée.</p>')}
        <h4>Compétences</h4>
        <p class="field-help">Une compétence déclarée n’est pas une capacité vérifiée. Vous pouvez l’attester en citant une tâche <b>acceptée</b> de ce profil ou une évaluation de son travail : c’est ce qui a été constaté, pas une promesse pour la suite.</p>
        <ul class="board-history">${profile.skills.map(s => att[s]
          ? ui`<li>✓ <b>${esc(s)}</b> <small>attestée sur ${att[s].source_ids.length} preuve(s)${att[s].note ? ' · ' + esc(att[s].note) : ''}</small> <button type="button" class="text-button" data-skill-withdraw="${esc(s)}" data-profile="${esc(profile.id)}">Retirer</button></li>`
          : ui`<li>${esc(s)} <small>déclarée</small> <button type="button" class="text-button" data-skill-attest="${esc(s)}" data-profile="${esc(profile.id)}">Attester…</button></li>`).join('') || ui('<li class="muted">Aucune compétence déclarée.</li>')}</ul>`, null);
    }
    if (d.skillAttest) {
      const skill = d.skillAttest, profileId = d.profile;
      if ($('dialog').open) $('dialog').close();
      openDialog(ui('Attester « ') + skill + ' »', ui`<div class="fields">
        <label>Preuves (identifiants de tâches acceptées ou d’évaluations, séparés par des virgules)<input name="source_ids" required></label>
        <label>Ce que vous avez constaté<textarea name="note" rows="3" maxlength="2000"></textarea></label>
        <p class="field-help">Les preuves qui ne sont ni une tâche acceptée de ce profil, ni une évaluation de son travail, sont écartées et signalées.</p></div>`,
        async form => { const r = await action('skill_attest', {profile_id: profileId, skill, note: form.get('note'),
          source_ids: form.get('source_ids').split(',').map(s => s.trim()).filter(Boolean)}); toast(r.notice); }, ui('Attester'));
    }
    if (d.skillWithdraw) {
      const r = await action('skill_withdraw', {profile_id: d.profile, skill: d.skillWithdraw});
      if ($('dialog').open) $('dialog').close();
      toast(r.notice); $('page')._rendered = null; await refresh(true);
    }
    if (d.profileArchive) { const r = await action('agent_profile_archive', {id: d.profileArchive, archived: d.archived === 'true'}); toast(r.notice); $('page')._rendered = null; await refresh(true); }
    if (button.hasAttribute('data-profile-catalog')) {
      const connector = $('profile-connector').value.trim();
      button.disabled = true;
      try { const r = await action('list_models', {id: connector}); state.data.models_cache[connector] = r.models; $('profile-models').outerHTML = modelDatalist(connector); $('profile-status').textContent = r.models.length + ui(' modèle(s) au catalogue de ') + connector + '.'; }
      catch (err) { $('profile-status').textContent = ui('Catalogue indisponible : ') + err.message + ui(' Vous pouvez saisir un identifiant de modèle explicite.'); }
      finally { button.disabled = false; }
    }
    if (button.hasAttribute('data-team-create')) { const r = await action('team_save', {project_id: state.project}); toast(r.notice); $('page')._rendered = null; await refresh(true); }
    if (button.hasAttribute('data-team-add')) openAddMemberDialog();
    if (button.hasAttribute('data-team-rename')) openDialog(ui('Nom de l’équipe'), ui`<label>Nom<input name="name" value="${esc(teamsState.team.team?.name || '')}" required autofocus maxlength="120"></label>`,
      async form => { await action('team_save', {project_id: state.project, name: form.get('name')}); });
    if (d.teamStatus) {
      const r = await action('team_save', {project_id: state.project, status: d.teamStatus});
      toast(r.notice); $('page')._rendered = null; await refresh(true);
    }
    if (button.hasAttribute('data-team-save-template')) openTemplateDialogs('save');
    if (button.hasAttribute('data-team-apply-template')) openTemplateDialogs('apply');
    if (button.hasAttribute('data-memory-new') || d.memoryEdit) {
      const members = (teamsState.team?.members || []).filter(m => m.active);
      const entry = d.memoryEdit ? (await action('agent_memory_list', {scope: 'member', project_id: state.project})).entries.find(e => e.id === d.memoryEdit) : null;
      if ($('dialog').open) $('dialog').close();
      openDialog(entry ? ui('Modifier l’observation') : ui('Observation locale d’un agent'), ui`<div class="fields">
        <label>Agent<select name="member_id">${members.map(m => `<option value="${esc(m.id)}" ${entry && m.id === entry.member_id ? 'selected' : ''}>${esc(m.definition.name)} · ${TEAM_ROLES[m.role]}</option>`).join('')}</select></label>
        <label>Observation<textarea name="content" rows="4" maxlength="20000" required placeholder="Ce que cet agent a appris dans ce projet">${esc(entry?.content || '')}</textarea></label>
        <label>Catégorie<input name="category" maxlength="80" value="${esc(entry?.category || '')}" placeholder="Convention, piège connu, décision…"></label>
        <label>Sources (identifiants de cartes, rapports ou messages, séparés par des virgules)<input name="source_ids" value="${esc((entry?.source_ids || []).join(', '))}" placeholder="facultatif ici, obligatoire pour une mémoire transférable"></label>
        <p class="field-help">Cette note reste dans ce projet. Elle n’atteindra le profil global que par une proposition que vous adopterez.</p>
      </div>`, async form => {
        const values = Object.fromEntries(form);
        const r = await action('agent_memory_save', {scope: 'member', project_id: state.project, member_id: values.member_id,
          ...(entry ? {id: entry.id} : {}), content: values.content, category: values.category,
          source_ids: values.source_ids.split(',').map(s => s.trim()).filter(Boolean)});
        toast(r.notice);
      }, ui('Enregistrer'));
    }
    if (d.memoryDelete) { const r = await action('agent_memory_delete', {id: d.memoryDelete}); toast(r.notice); $('page')._rendered = null; await refresh(true); }
    if (button.hasAttribute('data-proposal-new')) {
      const all = (teamsState.team?.members || []).filter(m => m.active);
      const authors = all.filter(m => m.role === 'chief' || m.role === 'lead');
      if (!authors.length) { openDialog(ui('Aucun responsable'), ui('<p>Une proposition vient d’un chef de projet ou d’un lead : c’est une observation de responsable, pas une auto-évaluation.</p>'), null); return; }
      openDialog(ui('Proposer une amélioration'), ui`<div class="fields">
        <label>Proposée par<select name="member_id">${authors.map(m => `<option value="${esc(m.id)}">${esc(m.definition.name)} · ${TEAM_ROLES[m.role]}</option>`).join('')}</select></label>
        <label>Profil concerné<select name="profile_id">${all.map(m => `<option value="${esc(m.profile_id)}">${esc(m.profile_name)}</option>`).join('')}</select></label>
        <label>Type<select name="kind"><option value="prompt">Consignes initiales — crée une nouvelle révision</option><option value="memory">Mémoire transférable — méthode générale</option></select></label>
        <label>Valeur proposée<textarea name="proposed_value" rows="6" maxlength="20000" required></textarea></label>
        <label>Motif<textarea name="rationale" rows="3" maxlength="4000" required placeholder="Ce qui a été constaté, et sur combien de cas"></textarea></label>
        <label>Sources (identifiants de cartes, rapports ou évaluations, séparés par des virgules)<input name="source_ids" required></label>
        <p class="field-help">Rien ne change tant que vous n’adoptez pas. Une adoption crée une révision du profil global ; les équipes gardent la leur jusqu’à adoption explicite, et revenir en arrière consiste à réadopter la révision précédente.</p>
      </div>`, async form => {
        const values = Object.fromEntries(form);
        const r = await action('improvement_propose', {project_id: state.project, member_id: values.member_id,
          profile_id: values.profile_id, kind: values.kind, proposed_value: values.proposed_value, rationale: values.rationale,
          source_ids: values.source_ids.split(',').map(s => s.trim()).filter(Boolean)});
        toast(r.notice);
      }, ui('Enregistrer la proposition'));
    }
    if (d.proposalDecide) {
      const adopt = d.adopt === 'true';
      if ($('dialog').open) $('dialog').close();
      openDialog(adopt ? ui('Adopter la proposition') : ui('Écarter la proposition'),
        ui`<p>${adopt ? ui('L’adoption crée une nouvelle révision du profil global, ou ajoute une mémoire transférable. Aucune équipe ne change : chaque projet adopte la révision explicitement.') : ui('La proposition reste consultable avec votre motif. Rien n’est modifié.')}</p>
         <label>Motif de la décision<textarea name="decision" rows="3" maxlength="2000"></textarea></label>`,
        async form => { const r = await action('improvement_decide', {id: d.proposalDecide, adopt, decision: form.get('decision')}); toast(r.notice); },
        adopt ? ui('Adopter') : ui('Écarter'));
    }
    if (d.memberEdit) { if ($('dialog').open) $('dialog').close(); openMemberDialog(d.memberEdit); }
    if (d.memberRevision) await openRevisionDialog(d.memberRevision);
    if (d.memberRemove) openRemoveDialog(d.memberRemove, Number(d.subordinates || 0));
    if (d.memberRestore) { const r = await action('team_update_member', {project_id: state.project, id: d.memberRestore, active: true}); toast(r.notice); $('page')._rendered = null; await refresh(true); }
  } catch (err) { fail(err); }
});

// Drag a profile card onto a category of the navigation to file it there.
document.addEventListener('dragstart', e => {
  const card = e.target.closest?.('[data-profile-card]');
  if (card) { e.dataTransfer.setData('text/cyai-profile', card.dataset.profileCard); e.dataTransfer.effectAllowed = 'move'; }
});
document.addEventListener('dragover', e => {
  const target = e.target.closest?.('[data-library-drop]');
  if (target && e.dataTransfer.types.includes('text/cyai-profile')) { e.preventDefault(); target.classList.add('drop-target'); }
});
document.addEventListener('dragleave', e => e.target.closest?.('[data-library-drop]')?.classList.remove('drop-target'));
document.addEventListener('drop', async e => {
  const target = e.target.closest?.('[data-library-drop]'), id = e.dataTransfer?.getData('text/cyai-profile');
  if (!target || !id) return;
  e.preventDefault(); target.classList.remove('drop-target');
  try { toast((await action('agent_profile_category', {id, category: target.dataset.libraryDrop})).notice); $('page')._rendered = null; await renderAgentsPage(); }
  catch (error) { fail(error); }
});
