'use strict';
// What the chief and the leads hold — the scorecard of the team, assessments and what follows them, the cursors of the
// work — and what each model is good at, with your order of preference per area. Facts and judgements, never a ranking
// computed for you: you read, you decide.
const leadState = {scorecard: null, capabilities: null, area: 'code', order: null};
const CURSOR_KEYS = ['autonomy', 'rigor', 'creativity', 'effort', 'detail'];
const CURSOR_NAMES = {autonomy: 'Autonomie', rigor: 'Rigueur', creativity: 'Créativité', effort: 'Effort de raisonnement', detail: 'Détail du compte rendu'};
const CURSOR_HINTS = {autonomy: ['demande tout', 'demande l’important', 'décide le réversible', 'avance seul', 'totalement seul'],
  rigor: ['au plus vite', 'le principal', 'l’essentiel', 'soigneusement', 'tout vérifier'],
  creativity: ['à la lettre', 'proche de la demande', 'améliorations mesurées', 'cherche mieux', 'explore'],
  effort: ['rapide', 'bref', 'normal', 'profond', 'maximal'], detail: ['très bref', 'court', 'normal', 'détaillé', 'très détaillé']};
const VERDICT_LABELS = {reliable: 'Fiable', watch: 'À surveiller', reassign: 'À réaffecter', adapt: 'À adapter', replace: 'À remplacer'};

// Five selects, « non réglé » by default. Used for the project, a card and a launch.
function cursorFieldsHTML(prefix, values = {}, help = '') {
  return `<div class="cursor-grid">${CURSOR_KEYS.map(key => `<label>${CURSOR_NAMES[key]}<select name="${prefix}:${key}"><option value="">— non réglé</option>${[1, 2, 3, 4, 5].map(n => `<option value="${n}" ${Number(values[key]) === n ? 'selected' : ''}>${n} · ${CURSOR_HINTS[key][n - 1]}</option>`).join('')}</select></label>`).join('')}</div>${help ? `<small class="field-help">${help}</small>` : ''}`;
}
function cursorValues(form, prefix) {
  const values = {};
  CURSOR_KEYS.forEach(key => { const v = form.get(prefix + ':' + key); if (v) values[key] = Number(v); });
  return values;
}

// --- the scorecard of the team -----------------------------------------------------------------------------------

function capabilityChips(list) {
  return (list || []).map(c => `<span class="cap-chip" title="Confiance : ${esc(c.confidence || '—')}">${esc(c.label)} ${c.value}</span>`).join('');
}
async function teamScorecardHTML(project=state.project) {
  let data;
  try { data = await action('team_scorecard', {project_id: project}); } catch (error) { return ''; }
  if(state.project!==project)return '';
  leadState.scorecard = data;
  const rows = data.members.filter(m => m.active).map(m => {
    const last = m.assessments[0];
    return `<div class="score-row"><div class="score-who"><b>${esc(m.name)}</b><small>${esc({chief: 'Chef de projet', lead: 'Lead', member: 'Membre', consultant: 'Consultant'}[m.role] || m.role)} · ${esc(agentName(m.connector))}${m.model ? ' · ' + esc(m.model) : ''}</small>
        <div class="cap-list">${capabilityChips(m.capabilities) || '<small class="muted">capacités du modèle inconnues</small>'}</div></div>
      <div class="score-facts"><span title="Cartes acceptées">✓ ${m.tasks.done}</span><span title="Cartes échouées ou annulées">✕ ${m.tasks.failed}</span><span title="En revue">◔ ${m.tasks.in_review}</span>
        <span title="Exécutions en échec / total">⚙ ${m.executions.failed}/${m.executions.total}</span>
        <span title="${esc(Object.entries(m.evaluations.by_criterion).map(([k, v]) => k + ' ' + v).join(' · ') || 'Aucune évaluation')}">★ ${m.evaluations.average ?? '—'}${m.evaluations.count ? ' (' + m.evaluations.count + ')' : ''}</span></div>
      <div class="score-verdict">${m.verdict ? `<span class="verdict ${esc(m.verdict)}">${esc(m.verdict_label)}</span><small title="${esc([last.strengths, last.weaknesses, last.recommendation].filter(Boolean).join('\n'))}">par ${esc(last.author)} · ${esc(date(last.created_at))}</small>` : '<small class="muted">pas de bilan</small>'}</div>
      <div class="row-actions">${m.role === 'chief' ? '' : `<button type="button" class="secondary" data-lead-assess="${esc(m.member_id)}">Bilan…</button>`}
        ${m.tasks.open ? `<button type="button" class="text-button" data-lead-reassign="${esc(m.member_id)}">Réaffecter ses cartes…</button>` : ''}
        <button type="button" class="text-button" data-lead-replace="${esc(m.member_id)}">Remplacer…</button></div></div>`;
  }).join('');
  return `<details class="event score-panel" open><summary>Bilan de l’équipe · ${data.members.filter(m => m.active).length} agent(s)</summary>
      <p class="field-help">${esc(data.notice)} Le chef et les leads rédigent le bilan des agents qu’ils encadrent ; l’agent le lit au début de son contexte. Pour adapter ses consignes, « Proposer une amélioration » plus bas.</p>
      ${rows || '<p class="muted">Aucun agent actif.</p>'}</details>
    <details class="event score-panel"><summary>Curseurs du projet${Object.keys(data.cursors).length ? ' · ' + Object.entries(data.cursors).map(([k, v]) => CURSOR_NAMES[k] + ' ' + v).join(', ') : ' · non réglés'}</summary>
      <form id="project-cursors" class="fields">${cursorFieldsHTML('project', data.cursors, 'Réglés pour tout le projet (par vous, ou par le chef de projet). Une carte peut préciser, et le lancement d’une tâche aussi : le plus précis l’emporte. Ils deviennent des consignes explicites, et l’effort de raisonnement du modèle quand le connecteur en a un.')}
        <div class="row-actions"><button type="submit" class="secondary">Enregistrer les curseurs</button></div></form></details>`;
}
function scoreMember(id) { return leadState.scorecard?.members.find(m => m.member_id === id); }
function assessDialog(id) {
  const m = scoreMember(id);
  openDialog('Bilan · ' + m.name, `<div class="fields">
    <label>Verdict<select name="verdict">${Object.entries(VERDICT_LABELS).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
    <label>Points forts<textarea name="strengths" rows="2" maxlength="2000"></textarea></label>
    <label>Points faibles<textarea name="weaknesses" rows="2" maxlength="2000"></textarea></label>
    <label>Recommandation<textarea name="recommendation" rows="2" maxlength="2000" placeholder="Par exemple : le garder sur la documentation ; exiger les commandes de test dans ses comptes rendus"></textarea></label>
    <p class="field-help">L’agent lira ce bilan au début de son contexte, et ses supérieurs le verront dans le bilan de l’équipe. Faits : ${m.tasks.done} carte(s) acceptée(s), ${m.tasks.failed} échouée(s), moyenne ${m.evaluations.average ?? '—'}.</p></div>`,
    async form => { const r = await action('member_assess', {project_id: state.project, member_id: id, by_user: true, verdict: form.get('verdict'),
      strengths: form.get('strengths'), weaknesses: form.get('weaknesses'), recommendation: form.get('recommendation')}); toast(r.notice); $('page')._rendered = null; }, 'Enregistrer le bilan');
}
function reassignDialog(id) {
  const m = scoreMember(id), others = leadState.scorecard.members.filter(x => x.active && x.member_id !== id);
  openDialog('Réaffecter les cartes de ' + m.name, `<div class="fields">
    <label>Vers<select name="to">${others.map(x => `<option value="${esc(x.member_id)}">${esc(x.name)}${x.verdict ? ' · ' + esc(x.verdict_label) : ''}</option>`).join('')}</select></label>
    <label>Motif (inscrit sur chaque carte)<input name="reason" maxlength="1000"></label>
    <p class="field-help">${m.tasks.open} carte(s) ouverte(s). Une carte en cours d’exécution reste à son agent.</p></div>`,
    async form => { const r = await action('task_reassign', {project_id: state.project, member_id: id, to_member_id: form.get('to'), by_user: true, reason: form.get('reason')}); toast(r.notice); $('page')._rendered = null; }, 'Réaffecter');
}
async function replaceDialog(id) {
  const m = scoreMember(id);
  const profiles = (await action('agent_profile_list')).profiles.filter(p => !p.archived);
  openDialog('Remplacer ' + m.name, `<div class="fields">
    <label>Par le profil<select name="profile">${profiles.map(p => `<option value="${esc(p.id)}">${p.icon ? esc(p.icon) + ' ' : ''}${esc(p.name)} · ${esc(agentName(p.connector))}${p.model ? ' · ' + esc(p.model) : ''}</option>`).join('')}</select></label>
    <label>Motif<input name="reason" maxlength="1000"></label>
    <p class="field-help">Même place : même rôle, même responsable, mêmes agents encadrés, cartes ouvertes reprises. ${esc(m.name)} est retiré de l’équipe, pas supprimé : son affectation reste consultable et réactivable.</p></div>`,
    async form => { const r = await action('team_replace_member', {project_id: state.project, member_id: id, profile_id: form.get('profile'), by_user: true, reason: form.get('reason')}); toast(r.notice); $('page')._rendered = null; }, 'Remplacer');
}

// --- models: capabilities and order of preference ------------------------------------------------------------

function capabilityLine(profile) {
  const entry = leadState.capabilities?.[profile.connector + ':' + (profile.model || '')];
  const known = (entry?.areas || []).filter(a => a.value !== null).sort((a, b) => b.value - a.value).slice(0, 4);
  return known.length ? `<p class="cap-list" title="Capacités de base du modèle : vos notes, vos projets, benchmarks publics, estimation d’IA">${capabilityChips(known)}</p>` : '';
}
async function loadCapabilities() {
  const data = await action('model_capabilities', {});
  leadState.overview = data;
  leadState.capabilities = Object.fromEntries(data.models.map(m => [m.key, m]));
  return data;
}
function capabilityValue(entry, area) { return entry?.areas.find(a => a.area === area); }
async function renderCapabilities() {
  const host = document.querySelector('.settings-content');
  if (!host || state.settingsTab !== 'models') return;
  const data = await loadCapabilities();
  if (state.view !== 'settings' || state.settingsTab !== 'models') return;
  let box = $('model-capabilities');
  if (!box) { box = document.createElement('section'); box.id = 'model-capabilities'; box.className = 'capabilities-section'; host.append(box); }
  const area = leadState.area, orders = data.orders[area];
  if (!leadState.order || leadState.orderArea !== area) { leadState.order = [...(orders.order.length ? orders.order : orders.suggested)]; leadState.orderArea = area; }
  const saved = orders.order.length > 0, changed = JSON.stringify(leadState.order) !== JSON.stringify(saved ? orders.order : orders.suggested);
  const rows = leadState.order.map((key, i) => {
    const entry = leadState.capabilities[key], value = capabilityValue(entry, area);
    return `<div class="cap-row"><span class="cap-rank">${i + 1}</span><div class="cap-model"><b>${esc(key)}</b><small>${esc((value?.sources || []).map(s => s.label + ' ' + s.value).join(' · ') || 'aucune source')}${entry?.preference && entry.preference !== 'neutral' ? ' · ' + (entry.preference === 'prefer' ? 'préféré' : 'à éviter') : ''}</small></div>
      <span class="cap-value ${value?.value === null || value?.value === undefined ? 'unknown' : ''}">${value?.value ?? '—'}</span><span class="cap-confidence">${esc(value?.confidence || '')}</span>
      <button type="button" class="icon" data-cap-move="${i}" data-dir="-1" aria-label="Monter" ${i ? '' : 'disabled'}>↑</button><button type="button" class="icon" data-cap-move="${i}" data-dir="1" aria-label="Descendre" ${i < leadState.order.length - 1 ? '' : 'disabled'}>↓</button>
      <button type="button" class="text-button" data-cap-detail="${esc(key)}">Détails</button></div>`;
  }).join('');
  box.innerHTML = `<h3>Capacités et ordre de préférence</h3><p class="field-help">${esc(data.notice)} Pour chaque domaine, l’ordre fixé ici est lu par le chef de projet, l’assistant et l’orchestrateur.</p>
    <div class="cap-areas">${Object.entries(data.areas).map(([k, v]) => `<button type="button" class="${k === area ? 'selected' : ''}" data-cap-area="${k}">${esc(v)}${data.orders[k].order.length ? ' ●' : ''}</button>`).join('')}</div>
    <div class="cap-list-rows">${rows || '<p class="muted">Aucun modèle connu : actualisez le catalogue d’un connecteur, ou notez un modèle.</p>'}</div>
    <div class="row-actions">${changed ? '<button type="button" class="primary" data-cap-save>Enregistrer cet ordre</button>' : ''}${saved ? '<button type="button" class="secondary" data-cap-reset>Revenir à l’ordre suggéré</button>' : '<small class="muted">Ordre suggéré : vos préférences, puis les estimations.</small>'}</div>`;
}
function capabilityDialog(key) {
  const entry = leadState.capabilities[key];
  const enabled = (state.data?.connectors || []).filter(c => c.enabled);
  openDialog('Capacités · ' + key, `<div class="cap-detail">${entry.areas.map(a => `<div class="cap-row"><b>${esc(a.label)}</b><span class="cap-value ${a.value === null ? 'unknown' : ''}">${a.value ?? '—'}</span><span class="cap-confidence">${esc(a.confidence)}</span>
      <small>${a.sources.map(s => `${esc(s.label)} ${s.value} <span class="muted">(${esc(s.detail)})</span>`).join(' · ') || 'aucune source'}</small></div>`).join('')}</div>
    <p class="field-help">Observé dans CyAI : ${entry.observed.calls} appel(s), ${entry.observed.succeeded} abouti(s), ${entry.observed.failed} en échec — un succès technique, pas une mesure de qualité.${entry.estimate_pending ? ' Estimation d’IA en cours…' : ''}</p>
    <div class="row-actions"><button type="button" class="secondary" data-cap-rate="${esc(key)}">Noter à la main…</button></div>
    ${enabled.length ? `<details><summary>Demander une estimation à une IA…</summary><div class="two-fields"><label>IA<select name="by">${enabled.map(c => `<option value="${esc(c.id)}">${esc(agentName(c.id))}</option>`).join('')}</select></label><label>Modèle<input name="by_model" placeholder="par défaut"></label></div>
      <p class="field-help">Un appel : l’IA dit ce qu’elle sait de ce modèle, domaine par domaine, avec son incertitude. Son avis s’ajoute aux sources sans remplacer vos notes.</p>
      <button type="button" class="secondary" data-cap-estimate="${esc(key)}">Estimer</button></details>` : ''}`, null);
}

document.addEventListener('submit', async e => {
  if (e.target.id !== 'project-cursors') return;
  e.preventDefault();
  try { toast((await action('team_cursors_set', {project_id: state.project, by_user: true, cursors: cursorValues(new FormData(e.target), 'project')})).notice); $('page')._rendered = null; await refresh(true); }
  catch (err) { fail(err); }
});
document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button) return;
  const d = button.dataset;
  try {
    if (d.leadAssess) assessDialog(d.leadAssess);
    if (d.leadReassign) reassignDialog(d.leadReassign);
    if (d.leadReplace) await replaceDialog(d.leadReplace);
    if (d.capArea) { leadState.area = d.capArea; leadState.order = null; await renderCapabilities(); }
    if (d.capMove !== undefined) {
      const i = Number(d.capMove), j = i + Number(d.dir);
      [leadState.order[i], leadState.order[j]] = [leadState.order[j], leadState.order[i]];
      await renderCapabilities();
    }
    if (button.hasAttribute('data-cap-save')) { toast((await action('model_preference_order', {area: leadState.area, models: leadState.order})).notice); leadState.order = null; await renderCapabilities(); }
    if (button.hasAttribute('data-cap-reset')) { toast((await action('model_preference_order', {area: leadState.area, models: []})).notice); leadState.order = null; await renderCapabilities(); }
    if (d.capDetail) capabilityDialog(d.capDetail);
    if (d.capRate) { $('dialog').close(); const key = d.capRate; if (!state.modelCatalog?.models.some(m => m.key === key)) toast('Ce modèle n’est pas dans le catalogue actuel : ajoutez-le par « Ajouter un modèle ».'); else ratingDialog(key); }
    if (d.capEstimate) {
      const [connector, ...rest] = d.capEstimate.split(':');
      const r = await action('model_estimate', {connector, model: rest.join(':'), by_connector: document.querySelector('#dialog [name="by"]').value, by_model: document.querySelector('#dialog [name="by_model"]').value});
      toast(r.notice); $('dialog').close();
    }
    if (d.profileCapabilities !== undefined) {
      const form = button.closest('form'), connector = form.querySelector('[name="connector"]').value, model = form.querySelector('[name="model"]').value;
      const result = await action('model_capabilities', {connector, model});
      const strong = result.areas.filter(a => a.value !== null && a.value >= 7).sort((a, b) => b.value - a.value);
      if (!strong.length) { toast('Aucune capacité connue d’au moins 7/10 pour ce modèle : notez-le ou demandez une estimation dans Paramètres › Modèles.'); return; }
      const skills = form.querySelector('[name="skills"]'), present = skills.value.toLowerCase();
      const added = strong.map(a => a.label).filter(label => !present.includes(label.toLowerCase()));
      skills.value = [skills.value.trim(), ...added].filter(Boolean).join('\n');
      toast(added.length ? 'Compétences ajoutées depuis le modèle : ' + added.join(', ') + '. Modifiez-les librement.' : 'Ces compétences sont déjà listées.');
    }
  } catch (err) { fail(err); }
});
