'use strict';
// The method lab: tests saved with a method, runs scored by you or by an AI, improvements proposed by an AI, and a
// bounded refining loop. In the task inspector: a comprehension check by the model that would do the task, and
// precisions written for one model only. Everything that calls an AI says so and waits for your click.
const lab = {open: false, tests: [], runs: [], loops: [], proposals: [], selected: null, timer: null, checks: [], checkTimer: null};
const RUN_STATES = {running: 'en cours', succeeded: 'terminé', failed: 'échec'};

function labConnectors(selected, name) {
  const enabled = (state.data?.connectors || []).filter(c => c.enabled);
  return enabled.length ? `<select name="${name}" data-lab-field="${name}">${enabled.map(c => `<option value="${esc(c.id)}" ${c.id === selected ? 'selected' : ''}>${esc(agentName(c.id))}</option>`).join('')}</select>`
    : '<span class="me-warning">⚠ Aucun connecteur activé</span>';
}
function scoreBadge(run) {
  if (!run?.score) return '';
  return `<span class="lab-score s${run.score}" title="${run.rating_by === 'user' ? 'Votre note' : 'Note d’une IA, pas une preuve'}">${run.score}/5 · ${run.rating_by === 'user' ? 'vous' : 'IA'}</span>`;
}
function statusBadge(run) { return `<span class="status ${run.status === 'failed' ? 'failed' : run.status === 'running' ? 'running' : 'succeeded'}">${RUN_STATES[run.status] || run.status}</span>`; }

// --- the lab overlay -------------------------------------------------------------------------------------------

async function openLab() {
  if (!methodEditor.id || methodEditor.dirty) await saveMethodGraph();
  lab.open = true;
  await loadLab();
  if (!lab.selected && lab.tests.length) lab.selected = lab.tests[0].id;
  renderLab();
}
function closeLab() { lab.open = false; clearInterval(lab.timer); lab.timer = null; $('me-lab')?.remove(); }
async function loadLab() {
  const [tests, runs, loops, proposals] = await Promise.all([action('method_tests', {id: methodEditor.id}), action('method_runs', {id: methodEditor.id}),
    action('method_loops', {id: methodEditor.id}), action('method_proposals', {id: methodEditor.id})]);
  lab.tests = tests.tests; lab.runs = runs.runs; lab.loops = loops.loops; lab.proposals = proposals.proposals;
  methodEditor.proposalsNew = lab.proposals.filter(p => p.status === 'new').length;
  const busy = lab.runs.some(r => r.status === 'running') || lab.loops.some(l => l.status === 'running') || lab.proposals.some(p => p.reviews.some(r => r.status === 'running'));
  clearInterval(lab.timer); lab.timer = null;
  if (busy && lab.open) lab.timer = setInterval(async () => { if (!lab.open) return clearInterval(lab.timer); await loadLab(); renderLab(true); }, 2500);
}
function testFormHTML(test) {
  const inputs = methodEditor.draft.inputs.filter(p => p.key !== 'objectif');
  const t = test || {name: '', objective: '', inputs: {}, expected: ''};
  return `<form class="fields lab-test-form" data-lab-test-form="${esc(t.id || '')}">
    <div class="two-fields"><label>Nom du test<input name="name" value="${esc(t.name)}" maxlength="120" required placeholder="Cargo minier"></label>
      <label>Objectif<input name="objective" value="${esc(t.objective)}" maxlength="4000" required placeholder="une affiche pour un cargo minier"></label></div>
    ${inputs.map(p => `<label>${esc(p.name)}${p.kind === 'context' ? ' (contexte)' : p.kind === 'file' ? ' (chemin dans le projet de test)' : ''}<textarea name="in:${esc(p.key)}" rows="${p.kind === 'context' ? 3 : 1}" maxlength="50000">${esc(t.inputs?.[p.key] || '')}</textarea></label>`).join('')}
    <label>Résultat attendu — vos critères de réussite<textarea name="expected" rows="3" maxlength="8000" placeholder="Un slogan de moins de dix mots, qui cite le cuivre.">${esc(t.expected)}</textarea></label>
    <div class="row-actions"><button type="submit" class="secondary">Enregistrer le test</button>${t.id ? `<button type="button" class="text-button danger" data-lab-test-delete="${esc(t.id)}">Supprimer le test</button>` : ''}</div>
    <p class="field-help">Un test est enregistré avec la méthode ; il n’entre pas dans le contexte des agents.</p></form>`;
}
function runHTML(run) {
  const evaluations = lab.runs.filter(r => r.kind === 'evaluation' && r.parent_id === run.id);
  const last = evaluations[0];
  return `<div class="lab-run"><div class="lab-run-head">${statusBadge(run)} <b>v${run.revision}</b> <small>${esc(new Date(run.created_at).toLocaleString())}</small> ${scoreBadge(run)}
      <span class="me-spacer"></span><button type="button" class="text-button" data-lab-conversation="${esc(run.conversation_id)}">Conversation ↗</button></div>
    ${run.status === 'failed' ? `<p class="me-warning">⚠ ${esc(run.data.error || 'Échec')}</p>` : ''}
    ${(run.data.outputs || []).map(o => `<details class="lab-output"><summary>${esc(o.name)}${o.found === false ? ' (section introuvable : réponse complète)' : ''}</summary><div class="message-body">${richText(o.content || '')}</div></details>`).join('')}
    ${run.notes ? `<p class="field-help">${run.rating_by === 'user' ? 'Votre commentaire' : 'Verdict de l’IA'} : ${esc(run.notes)}</p>` : ''}
    ${last ? `<div class="lab-eval">${statusBadge(last)} Évaluation par ${esc(agentName(last.connector))}${last.data.verdict ? ' — ' + esc(last.data.verdict) : ''}${last.data.error ? ` <span class="me-warning">⚠ ${esc(last.data.error)}</span>` : ''}
      ${(last.data.problems || []).length ? `<small>Problèmes : ${last.data.problems.map(esc).join(' · ')}</small>` : ''}${(last.data.suggestions || []).length ? `<small>Suggestions : ${last.data.suggestions.map(esc).join(' · ')}</small>` : ''}</div>` : ''}
    ${run.status === 'succeeded' ? `<div class="row-actions lab-rate"><select data-lab-score="${esc(run.id)}" aria-label="Note"><option value="">Noter…</option>${[5, 4, 3, 2, 1].map(n => `<option value="${n}">${n}/5</option>`).join('')}</select>
      <input data-lab-notes="${esc(run.id)}" maxlength="4000" placeholder="Commentaire (facultatif)"><button type="button" class="secondary" data-lab-rate="${esc(run.id)}">Enregistrer ma note</button>
      <button type="button" class="secondary" data-lab-evaluate="${esc(run.id)}">Faire évaluer par une IA…</button></div>` : ''}</div>`;
}
function proposalHTML(run) {
  return `<div class="lab-run">${statusBadge(run)} Proposition de ${esc(agentName(run.connector))} <small>(sur la version ${run.revision}) ${esc(new Date(run.created_at).toLocaleString())}</small>
    ${run.data.error ? `<p class="me-warning">⚠ ${esc(run.data.error)}</p>` : ''}
    ${run.data.explanation ? `<div class="message-body">${richText(run.data.explanation)}</div>` : ''}
    ${(run.data.changes || []).length ? `<ul class="lab-changes">${run.data.changes.map(c => `<li>${esc(c)}</li>`).join('')}</ul>` : ''}
    ${run.data.proposal ? (run.notes ? `<p class="field-help">${esc(run.notes)}</p>` : `<div class="row-actions"><button type="button" class="primary" data-lab-adopt="${esc(run.id)}">Adopter comme nouvelle version</button><button type="button" class="secondary" data-lab-load="${esc(run.id)}">Charger dans l’éditeur</button></div>`) : ''}</div>`;
}
function proposalItemHTML(p) {
  const model = agentName(p.connector) + (p.model ? ' · ' + p.model : '');
  return `<div class="lab-run lab-proposal ${esc(p.status)}"><div class="lab-run-head"><span class="status ${p.status === 'new' ? 'running' : p.status === 'adopted' ? 'succeeded' : ''}">${esc({new: 'à lire', adopted: 'adoptée', dismissed: 'écartée'}[p.status] || p.status)}</span>
      <b>${esc(p.step_name)}</b><small>par ${esc(model)} · ${esc(new Date(p.created_at).toLocaleString())}</small></div>
    <div class="message-body">${richText(p.content)}</div>
    <details><summary>Fin de sa réponse</summary><div class="message-body">${richText(p.excerpt || '')}</div></details>
    ${p.decision ? `<small>${esc(p.decision)}</small>` : ''}
    ${p.reviews.map(r => `<div class="lab-eval">${statusBadge(r)} ${r.data.discuss ? 'Discussion' : 'Examen'} par ${esc(r.data.by || '')}${r.data.error ? ` <span class="me-warning">⚠ ${esc(r.data.error)}</span>` : ''}
        ${r.data.verdict ? `<div class="message-body">${richText(r.data.verdict)}</div>` : ''}
        ${r.data.questions ? `<details><summary>Questions et réponses de l’auteur</summary><div class="message-body">${richText(r.data.questions + '\n\n' + (r.data.answers || ''))}</div></details>` : ''}
        ${r.data.instruction ? `<details open><summary>Nouvelle consigne proposée (pour tous les modèles)</summary><div class="message-body">${richText(r.data.instruction)}</div></details>${p.status === 'new' ? `<button type="button" class="secondary" data-lab-proposal-adopt="${esc(r.id)}" data-mode="instruction">Adopter comme consigne</button>` : ''}` : ''}
        ${r.data.precisions ? `<details open><summary>Précisions pour ${esc(model)} seulement</summary><div class="message-body">${richText(r.data.precisions)}</div></details>${p.status === 'new' ? `<button type="button" class="secondary" data-lab-proposal-adopt="${esc(r.id)}" data-mode="precisions">Adopter comme précisions pour ${esc(model)}</button>` : ''}` : ''}</div>`).join('')}
    ${p.status === 'new' ? `<div class="row-actions"><button type="button" class="secondary" data-lab-proposal-review="${esc(p.id)}">Faire examiner…</button><button type="button" class="text-button danger" data-lab-proposal-dismiss="${esc(p.id)}">Écarter</button></div>` : ''}</div>`;
}
function reviewDialog(id) {
  const p = lab.proposals.find(x => x.id === id);
  openDialog('Examiner la proposition · ' + p.step_name, `<div class="fields">
    <p class="field-help">Un modèle, de préférence plus fort, juge la proposition de ${esc(agentName(p.connector))} : pertinente ou non, puis une nouvelle consigne pour tous, ou des précisions pour ce modèle seulement. Vous adoptez ensuite ou non.</p>
    <div class="two-fields"><label>Modèle qui examine ${labConnectors('', 'connector')}</label><label>Modèle<input name="model" placeholder="par défaut"></label></div>
    <label><span><input type="checkbox" name="discuss"> Discuter d’abord avec l’auteur : l’examinateur lui pose ses questions, puis tranche (trois appels au lieu d’un)</span></label></div>`,
    async form => { const r = await action('method_proposal_review', {id, connector: form.get('connector'), model: form.get('model') || '', discuss: !!form.get('discuss')}); toast(r.notice); await loadLab(); renderLab(); }, 'Examiner');
}
function loopHTML(loop) {
  const history = loop.state.history || [];
  return `<div class="lab-run">${statusBadge({status: loop.status === 'running' ? 'running' : loop.status === 'succeeded' ? 'succeeded' : 'failed'})} Boucle · visée ${loop.config.target}/5 · ${loop.config.max_rounds} tour(s) au plus
    ${history.length ? `<small>Notes : ${history.map(h => 'tour ' + h.round + ' (v' + h.revision + ') ' + h.score + '/5').join(' · ')}</small>` : ''}
    ${loop.status === 'running' ? `<small>Tour ${loop.state.round} · ${esc({run: 'exécution du test', evaluate: 'évaluation', improve: 'amélioration'}[loop.state.phase] || '')}</small><div class="row-actions"><button type="button" class="secondary danger" data-lab-loop-stop="${esc(loop.id)}">Arrêter la boucle</button></div>` : `<small>${esc(loop.reason)}</small>`}</div>`;
}
function renderLab(keepScroll) {
  if (!lab.open) return;
  const host = document.querySelector('.method-editor');
  if (!host) return;
  let panel = $('me-lab');
  const scroll = keepScroll && panel ? [...panel.querySelectorAll('.lab-col')].map(c => c.scrollTop) : null;
  if (!panel) { panel = document.createElement('div'); panel.id = 'me-lab'; panel.className = 'me-writer me-lab'; host.append(panel); }
  const test = lab.tests.find(t => t.id === lab.selected);
  const proposals = lab.runs.filter(r => r.kind === 'improve');
  panel.innerHTML = `<header class="mw-head"><button type="button" class="secondary" data-lab-close>← Graphe</button>
      <div class="mw-title"><small>Tests & affinage</small><h3>${esc(methodEditor.draft.name)}</h3></div><span class="me-spacer"></span>
      ${test ? '<button type="button" class="secondary" data-lab-loop>Boucle d’affinage…</button>' : ''}<button type="button" class="primary" data-lab-close>Terminé</button></header>
    <div class="lab-body">
      <section class="lab-col lab-tests"><b class="me-label">Tests (${lab.tests.length})</b>
        ${lab.tests.map(t => `<button type="button" class="lab-test ${t.id === lab.selected ? 'selected' : ''}" data-lab-select="${esc(t.id)}"><b>${esc(t.name)}</b><small>${esc(t.objective)}</small>${scoreBadge(t.runs.find(r => r.score))}</button>`).join('') || '<p class="muted">Aucun test.</p>'}
        <button type="button" class="secondary" data-lab-select="">＋ Nouveau test</button></section>
      <section class="lab-col lab-main">${testFormHTML(test)}
        ${test ? `<div class="me-section"><b class="me-label">Lancer ce test</b>
          <div class="lab-launch">${method_free_tasks() ? `<label>IA des tâches libres ${labConnectors('', 'run_connector')}</label><label>Modèle<input data-lab-field="run_model" placeholder="par défaut"></label>` : ''}
            <label>Tâches simultanées<input type="number" min="1" max="8" value="1" data-lab-field="run_concurrency"></label>
            <button type="button" class="primary" data-lab-run="${esc(test.id)}">▶ Lancer</button></div>
          <p class="field-help">Un vrai lancement : la version enregistrée de la méthode est appliquée dans le projet « Tests de méthodes » et chaque tâche consomme des crédits de son IA.</p></div>
          <div class="me-section"><b class="me-label">Exécutions</b>${test.runs.map(runHTML).join('') || '<p class="muted">Pas encore lancé.</p>'}</div>` : ''}</section>
      <section class="lab-col lab-side"><b class="me-label">Amélioration par une IA</b>
        <div class="lab-launch"><label>IA ${labConnectors('', 'improve_connector')}</label><label>Modèle<input data-lab-field="improve_model" placeholder="par défaut"></label></div>
        <textarea data-lab-field="improve_request" rows="3" maxlength="4000" placeholder="Ce que vous voulez améliorer (facultatif) : l’IA lit aussi les tests, les notes et les vérifications."></textarea>
        <button type="button" class="secondary" data-lab-improve>Proposer une amélioration</button>
        <p class="field-help">L’IA propose une méthode complète ; vous voyez ce qui change, puis vous l’adoptez comme nouvelle version, ou vous la chargez dans l’éditeur pour la retoucher.</p>
        ${proposals.map(proposalHTML).join('')}
        ${lab.loops.length ? `<div class="me-section"><b class="me-label">Boucles</b>${lab.loops.map(loopHTML).join('')}</div>` : ''}
        <div class="me-section"><b class="me-label">Propositions des agents (${lab.proposals.filter(p => p.status === 'new').length} à lire)</b>
          ${lab.proposals.map(proposalItemHTML).join('') || `<p class="muted">Aucune. ${methodEditor.draft.options?.proposals ? 'Elles apparaissent après les chaînes de cette méthode.' : 'Cochez « Inviter les agents à proposer des améliorations » dans les propriétés de la méthode.'}</p>`}</div></section>
    </div>`;
  if (scroll) panel.querySelectorAll('.lab-col').forEach((c, i) => { c.scrollTop = scroll[i] || 0; });
}
function method_free_tasks() { return methodEditor.draft.steps.some(s => s.kind !== 'method' && s.executor === 'any') || methodEditor.draft.steps.some(s => s.kind === 'method'); }
function labValue(name) { return document.querySelector(`[data-lab-field="${name}"]`)?.value || ''; }

async function launchTest(testId) {
  const connector = labValue('run_connector'), model = labValue('run_model'), concurrency = Number(labValue('run_concurrency') || 1);
  const estimate = await action('method_loop_estimate', {id: methodEditor.id, max_rounds: 1});
  openDialog('Lancer le test', `<p>La méthode est appliquée et lancée : <b>${estimate.tasks} tâche(s)</b>${connector ? ', les tâches libres par ' + esc(agentName(connector)) : ''}. Chaque tâche consomme des crédits de son IA.</p><p class="field-help">Le résultat s’affiche ici ; vous le notez, ou le faites évaluer par une IA.</p>`,
    async () => { const r = await action('method_test_run', {test_id: testId, connector, model, concurrency}); toast(r.notice); await loadLab(); renderLab(); }, 'Lancer');
}
function evaluateDialog(runId) {
  openDialog('Faire évaluer par une IA', `<div class="fields"><label>IA d’évaluation ${labConnectors('', 'evaluator')}</label><label>Modèle<input name="model" placeholder="par défaut"></label>
    <p class="field-help">L’IA compare ce que la méthode a produit à vos critères et rend une note de 1 à 5 avec ses raisons. C’est un avis, pas une preuve ; votre propre note prime.</p></div>`,
    async form => { const r = await action('method_run_evaluate', {run_id: runId, connector: form.get('evaluator'), model: form.get('model')}); toast(r.notice); await loadLab(); renderLab(); }, 'Évaluer');
}
async function loopDialog() {
  const test = lab.tests.find(t => t.id === lab.selected);
  const estimate = await action('method_loop_estimate', {id: methodEditor.id, max_rounds: 3});
  openDialog('Boucle d’affinage · ' + test.name, `<div class="fields">
    <p>À chaque tour : le test est lancé (${estimate.tasks} tâche(s)), une IA l’évalue ; si la note visée n’est pas atteinte, une IA propose une meilleure méthode, <b>adoptée automatiquement comme nouvelle version</b>, puis le test repart.</p>
    <div class="two-fields"><label>Note visée<select name="target">${[5, 4, 3].map(n => `<option value="${n}">${n}/5</option>`).join('')}</select></label>
      <label>Nombre de tours au plus (1 à 10)<input name="max_rounds" type="number" min="1" max="10" value="3" required data-lab-rounds></label></div>
    ${method_free_tasks() ? `<div class="two-fields"><label>IA des tâches libres ${labConnectors('', 'run_connector_loop')}</label><label>Modèle<input name="run_model" placeholder="par défaut"></label></div>` : ''}
    <div class="two-fields"><label>IA d’évaluation ${labConnectors('', 'evaluator_loop')}</label><label>Modèle<input name="evaluator_model" placeholder="par défaut"></label></div>
    <div class="two-fields"><label>IA qui améliore ${labConnectors('', 'improver_loop')}</label><label>Modèle<input name="improver_model" placeholder="par défaut"></label></div>
    <p class="me-warning" id="lab-cost">⚠ Jusqu’à ${estimate.per_round * 3 - 1} exécutions d’IA pour 3 tours.</p>
    <label><span><input type="checkbox" name="confirm" required> J’accepte ces dépenses et l’adoption automatique des versions. Toutes restent dans l’historique ; la boucle s’arrête à la note visée, à la limite de tours, au premier échec et au redémarrage de CyAI.</span></label></div>`,
    async form => {
      const r = await action('method_loop_start', {test_id: test.id, confirm: !!form.get('confirm'), target: Number(form.get('target')), max_rounds: Number(form.get('max_rounds')),
        run: {connector: form.get('run_connector_loop') || '', model: form.get('run_model') || ''},
        evaluator: {connector: form.get('evaluator_loop'), model: form.get('evaluator_model') || ''},
        improver: {connector: form.get('improver_loop'), model: form.get('improver_model') || ''}});
      toast(r.notice); await loadLab(); renderLab();
    }, 'Lancer la boucle');
  lab.perRound = estimate.per_round;
}

// --- in the task inspector: does the model understand, and precisions for one model ------------------------------

function labStepHTML(step) {
  const checks = lab.checks.filter(r => r.step_key === step.key && (r.kind === 'check' || r.kind === 'refine'));
  const adaptations = Object.entries(step.adaptations || {});
  return `<div class="me-section"><b class="me-label">Compréhension et précisions par modèle</b>
    ${methodEditor.id ? `<button type="button" class="secondary" data-lab-check="${esc(step.key)}">Vérifier la compréhension…</button>` : '<small class="muted">Enregistrez la méthode pour vérifier cette tâche.</small>'}
    ${checks.slice(0, 4).map(r => r.kind === 'check'
      ? `<div class="lab-run">${statusBadge(r)} ${esc(agentName(r.connector))}${r.model ? ' · ' + esc(r.model) : ''} <small>${esc(new Date(r.created_at).toLocaleString())}</small>
          ${r.data.report ? `<details><summary>Ce qu’il a compris</summary><div class="message-body">${richText(r.data.report)}</div></details><button type="button" class="text-button" data-lab-refine="${esc(r.id)}">Affiner pour ce modèle…</button>` : ''}${r.data.error ? `<small class="me-warning">⚠ ${esc(r.data.error)}</small>` : ''}</div>`
      : `<div class="lab-run">${statusBadge(r)} Précisions pour <b>${esc(r.data.target)}</b> par ${esc(r.data.by || '')}
          ${r.data.adaptation ? `<div class="message-body">${richText(r.data.adaptation)}</div>${r.data.explanation ? `<small>${esc(r.data.explanation)}</small>` : ''}<button type="button" class="text-button" data-lab-keep="${esc(r.id)}">Garder pour ${esc(r.data.target)}</button>` : ''}${r.data.error ? `<small class="me-warning">⚠ ${esc(r.data.error)}</small>` : ''}</div>`).join('')}
    ${adaptations.map(([target, text]) => `<div class="lab-adaptation"><div class="pm-head"><b>Pour ${esc(target)}</b><button type="button" class="text-button danger" data-lab-adaptation-remove="${esc(target)}">Retirer</button></div>
      <textarea rows="3" maxlength="8000" data-lab-adaptation="${esc(target)}">${esc(text)}</textarea></div>`).join('')}
    <small class="field-help">Les précisions d’un modèle s’ajoutent à la consigne seulement quand ce modèle exécute la tâche.</small></div>`;
}
async function loadChecks() {
  if (!methodEditor.id) { lab.checks = []; return; }
  const [checks, refines] = await Promise.all([action('method_runs', {id: methodEditor.id, kind: 'check'}), action('method_runs', {id: methodEditor.id, kind: 'refine'})]);
  lab.checks = [...refines.runs, ...checks.runs].sort((a, b) => b.created_at.localeCompare(a.created_at));
  clearInterval(lab.checkTimer); lab.checkTimer = null;
  if (lab.checks.some(r => r.status === 'running')) lab.checkTimer = setInterval(async () => {
    if (state.view !== 'method') return clearInterval(lab.checkTimer);
    await loadChecks();
    if (stepByKey(methodEditor.selected)?.kind === 'task') renderInspectorPanel();
  }, 2500);
}
function checkDialog(stepKey) {
  const step = stepByKey(stepKey);
  openDialog('Vérifier la compréhension · ' + step.name, `<div class="fields">
    <p class="field-help">Le modèle reçoit la consigne exacte de cette tâche, avec ses fichiers, et rapporte ce qu’il comprend — sans faire la tâche. Un appel à cette IA.</p>
    <label><span><input type="checkbox" name="other" data-lab-other> Vérifier avec une autre IA que l’exécutant de la tâche</span></label>
    <div class="two-fields" data-lab-other-fields hidden><label>IA ${labConnectors('', 'connector')}</label><label>Modèle<input name="model" placeholder="par défaut"></label></div>
    ${lab.tests.length ? `<label>Entrées d’un test (facultatif)<select name="test_id"><option value="">Aucune — entrées nommées seulement</option>${lab.tests.map(t => `<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('')}</select></label>` : ''}</div>`,
    async form => {
      const r = await action('method_check_understanding', {id: methodEditor.id, step_key: stepKey, test_id: form.get('test_id') || '',
        ...(form.get('other') ? {connector: form.get('connector'), model: form.get('model') || ''} : {})});
      toast(r.notice); await loadChecks(); renderInspectorPanel();
    }, 'Vérifier');
}
function refineDialog(checkId) {
  const check = lab.checks.find(r => r.id === checkId);
  openDialog('Affiner pour ' + agentName(check.connector) + (check.model ? ' · ' + check.model : ''), `<div class="fields">
    <p class="field-help">Un modèle plus fort lit la consigne et le rapport, pose ses questions au modèle vérifié, puis écrit des précisions pour ce modèle seulement. Trois appels d’IA. Vous gardez les précisions ou non.</p>
    <div class="two-fields"><label>Modèle qui affine ${labConnectors('', 'connector')}</label><label>Modèle<input name="model" placeholder="par défaut"></label></div></div>`,
    async form => { const r = await action('method_refine_for_model', {check_id: checkId, connector: form.get('connector'), model: form.get('model') || ''}); toast(r.notice); await loadChecks(); renderInspectorPanel(); }, 'Affiner');
}

document.addEventListener('change', e => {
  if (e.target.matches?.('[data-lab-other]')) { const box = document.querySelector('[data-lab-other-fields]'); if (box) box.hidden = !e.target.checked; }
  if (e.target.matches?.('[data-lab-rounds]') && lab.perRound) { const cost = $('lab-cost'); if (cost) cost.textContent = '⚠ Jusqu’à ' + (lab.perRound * Number(e.target.value) - 1) + ' exécutions d’IA pour ' + e.target.value + ' tour(s).'; }
});
document.addEventListener('input', e => {
  const target = e.target.dataset?.labAdaptation;
  if (target === undefined || state.view !== 'method') return;
  const step = stepByKey(methodEditor.selected);
  if (step) { step.adaptations = {...(step.adaptations || {}), [target]: e.target.value}; markDirty(); }
});
document.addEventListener('submit', async e => {
  const form = e.target.closest?.('[data-lab-test-form]');
  if (!form) return;
  e.preventDefault();
  try {
    const values = Object.fromEntries(new FormData(form)), inputs = {};
    Object.entries(values).forEach(([k, v]) => { if (k.startsWith('in:') && String(v).trim()) inputs[k.slice(3)] = v; });
    const r = await action('method_test_save', {method_id: methodEditor.id, ...(form.dataset.labTestForm ? {id: form.dataset.labTestForm} : {}),
      name: values.name, objective: values.objective, expected: values.expected, inputs});
    lab.selected = r.id; toast(r.notice); await loadLab(); renderLab();
  } catch (err) { fail(err); }
});
document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button) return;
  const d = button.dataset;
  try {
    if (button.hasAttribute('data-lab-open')) await openLab();
    if (d.labCheck) { if (!lab.tests.length && methodEditor.id) lab.tests = (await action('method_tests', {id: methodEditor.id})).tests; checkDialog(d.labCheck); }
    if (d.labRefine) refineDialog(d.labRefine);
    if (d.labKeep) {
      const run = lab.checks.find(r => r.id === d.labKeep), step = stepByKey(run.step_key);
      if (!step) { toast('Cette tâche est dans une sous-méthode : ouvrez-la pour y garder ces précisions.'); return; }
      step.adaptations = {...(step.adaptations || {}), [run.data.target]: run.data.adaptation};
      markDirty(); renderInspectorPanel(); toast('Précisions ajoutées à la tâche : enregistrez la méthode pour les garder.');
    }
    if (d.labAdaptationRemove) { const step = stepByKey(methodEditor.selected); delete step.adaptations[d.labAdaptationRemove]; markDirty(); renderInspectorPanel(); }
    if (!lab.open) return;
    if (d.labClose !== undefined) closeLab();
    if (d.labSelect !== undefined) { lab.selected = d.labSelect || null; renderLab(); }
    if (d.labTestDelete) {
      openDialog('Supprimer le test', '<p>Le test et l’historique de ses exécutions sont supprimés. Les conversations restent.</p>',
        async () => { toast((await action('method_test_delete', {id: d.labTestDelete})).notice); lab.selected = null; await loadLab(); renderLab(); }, 'Supprimer');
    }
    if (d.labRun) await launchTest(d.labRun);
    if (d.labRate) {
      const score = document.querySelector(`[data-lab-score="${CSS.escape(d.labRate)}"]`).value;
      if (!score) { toast('Choisissez une note.'); return; }
      toast((await action('method_run_rate', {run_id: d.labRate, score: Number(score), notes: document.querySelector(`[data-lab-notes="${CSS.escape(d.labRate)}"]`).value})).notice);
      await loadLab(); renderLab();
    }
    if (d.labEvaluate) evaluateDialog(d.labEvaluate);
    if (d.labConversation) { const target = d.labConversation; closeLab(); leaveMethodEditor(async () => { await selectConversation(target); }); }
    if (button.hasAttribute('data-lab-improve')) {
      const r = await action('method_improve', {id: methodEditor.id, test_id: lab.selected || '', connector: labValue('improve_connector'), model: labValue('improve_model'), request: labValue('improve_request')});
      toast(r.notice); await loadLab(); renderLab();
    }
    if (d.labAdopt) {
      openDialog('Adopter la proposition', `<p>La proposition devient la nouvelle version de la méthode. L’ancienne reste dans l’historique.${methodEditor.dirty ? ' <b>Vos modifications non enregistrées seront perdues.</b>' : ''}</p>`, async () => {
        const r = await action('method_improvement_adopt', {run_id: d.labAdopt});
        toast(r.notice); methodEditor.dirty = false; closeLab();
        setTimeout(async () => { await openMethodGraph(methodEditor.id, true); }, 0);
      }, 'Adopter');
    }
    if (d.labLoad) {
      const run = lab.runs.find(r => r.id === d.labLoad);
      methodEditor.draft = draftFrom({...run.data.proposal, category: run.data.proposal.category || methodEditor.draft.category});
      ensureLayout(); markDirty(); closeLab(); methodEditor.selected = null; renderGraph(); renderInspectorPanel();
      toast('Proposition chargée dans l’éditeur : relisez-la, puis enregistrez pour en faire une version.');
    }
    if (button.hasAttribute('data-lab-loop')) await loopDialog();
    if (d.labProposalReview) reviewDialog(d.labProposalReview);
    if (d.labProposalDismiss) { toast((await action('method_proposal_dismiss', {id: d.labProposalDismiss})).notice); await loadLab(); renderLab(); }
    if (d.labProposalAdopt) {
      const run = d.labProposalAdopt, mode = d.mode;
      openDialog('Adopter', `<p>${mode === 'instruction' ? 'La consigne de la tâche est remplacée' : 'Les précisions sont gardées pour ce modèle'} : c’est une nouvelle version de la méthode, l’ancienne reste dans l’historique.${methodEditor.dirty ? ' <b>Vos modifications non enregistrées seront perdues.</b>' : ''}</p>`, async () => {
        const r = await action('method_proposal_adopt', {run_id: run, mode});
        toast(r.notice); methodEditor.dirty = false; closeLab();
        setTimeout(async () => { await openMethodGraph(methodEditor.id, true); }, 0);
      }, 'Adopter');
    }
    if (d.labLoopStop) { toast((await action('method_loop_stop', {id: d.labLoopStop})).notice); await loadLab(); renderLab(); }
  } catch (err) { fail(err); }
});
