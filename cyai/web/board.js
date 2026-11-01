'use strict';
// Board of task cards. It shows and moves cards; it starts no agent. Every move is recorded
// with who decided it, and a report is never shown as an acceptance.
const boardState = {data: null, closed: false, member: ''};
const BOARD_FLOW = ['to_prepare', 'ready', 'in_progress', 'awaiting_information', 'in_review', 'to_correct'];
const BOARD_CLOSED = ['done', 'failed', 'cancelled'];
const BOARD_TONE = {to_prepare: 'configured', ready: 'queued', in_progress: 'running', awaiting_information: 'awaiting_approval',
  in_review: 'awaiting_approval', to_correct: 'failed', done: 'succeeded', failed: 'failed', cancelled: 'cancelled'};

function boardTask(id) { return (boardState.data?.tasks || []).find(t => t.id === id); }
function boardMembers(roles) {
  const members = (boardState.data?.members || []).filter(m => m.active && (!roles || roles.includes(m.role)));
  return members.map(m => `<option value="${esc(m.id)}">${esc(m.name)} · ${esc(m.role_label)}</option>`).join('');
}
function actorField(label, name = 'author_id') {
  return ui`<label>${label}<select name="${name}"><option value="">Vous (décision de l’utilisateur)</option>${boardMembers()}</select></label>`;
}
function taskCardHTML(task) {
  const blocked = task.status === 'to_prepare' || task.status === 'ready' ? task.dependencies.length : 0;
  return `<article class="board-card" data-task-open="${esc(task.id)}" tabindex="0" role="button">
    <strong>${esc(task.objective)}</strong>
    <small>${task.assignee ? esc(task.assignee) : ui('Sans responsable')}${task.reports ? ' · ' + task.reports + ' rapport(s)' : ''}</small>
    ${blocked ? ui`<span class="board-flag">${blocked} dépendance(s)</span>` : ''}
    ${task.status === 'in_review' ? ui('<span class="board-flag review">À examiner : rapport rendu, pas encore accepté</span>') : ''}
    ${task.pending_consultations ? ui`<span class="board-flag advice">${task.pending_consultations} avis attendu(s)</span>` : ''}
    ${task.running ? ui('<span class="board-flag running">Agent en cours · aucune preuve avant son compte rendu</span>') : ''}
    ${task.attempts >= 3 && !BOARD_CLOSED.includes(task.status) ? ui`<span class="board-flag stalled">${task.attempts} exécutions sans acceptation</span>` : ''}
  </article>`;
}
function boardColumnHTML(status, tasks) {
  const cards = tasks.filter(t => t.status === status);
  return `<section class="board-column"><header><span class="status ${BOARD_TONE[status]}">${esc(boardState.data.statuses[status])}</span><b>${cards.length}</b></header>
    ${cards.map(taskCardHTML).join('') || '<p class="board-empty">—</p>'}</section>`;
}

async function boardTabHTML(project) {
  if (!project.team?.exists) {
    return ui`<div class="page-heading"><div><small>BOARD DES TÂCHES</small><h3>Composez d’abord l’équipe</h3></div></div>
      <p>Les cartes de tâches sont attribuées à des affectations de l’équipe du projet. Créez l’équipe dans l’onglet Équipe, puis revenez ici.</p>
      <div class="row-actions"><button class="primary" data-project-tab="team">Ouvrir l’onglet Équipe</button></div>`;
  }
  const data = await action('task_list', {project_id: project.id});
  if(state.project!==project.id)return '';
  boardState.data = data;
  const tasks = boardState.member ? data.tasks.filter(t => t.assignee_id === boardState.member) : data.tasks;
  const closed = tasks.filter(t => BOARD_CLOSED.includes(t.status));
  const open = tasks.filter(t => !BOARD_CLOSED.includes(t.status));
  const review = open.filter(t => t.status === 'in_review').length;
  const pilot = await action('team_autopilot_plan', {project_id: project.id});
  return ui`<div class="page-heading"><div><small>BOARD DES TÂCHES</small><h3>${open.length} carte(s) ouverte(s)${review ? ' · ' + review + ui(' en attente de revue') : ''}</h3></div></div>
    <div class="row-actions">
      <button class="primary" data-task-new>＋ Nouvelle tâche</button>
      <label class="board-filter">Responsable<select id="board-member"><option value="">Toute l’équipe</option>${(data.members || []).filter(m => m.active).map(m => `<option value="${esc(m.id)}" ${m.id === boardState.member ? 'selected' : ''}>${esc(m.name)}</option>`).join('')}</select></label>
      <button class="secondary" data-project-tab="team">Équipe ↗</button>
    </div>
    ${autopilotBarHTML(pilot)}
    <p class="field-help">Les cartes avancent à la main, depuis leur fiche, ou par l’automate de délégation ; chaque mouvement enregistre qui l’a décidé. Un compte rendu d’agent n’est jamais une acceptation.</p>
    <div class="board-columns">${BOARD_FLOW.map(s => boardColumnHTML(s, open)).join('')}</div>
    ${closed.length ? ui`<details class="event" ${boardState.closed ? 'open' : ''}><summary>${closed.length} carte(s) close(s)</summary><div class="board-columns">${BOARD_CLOSED.map(s => boardColumnHTML(s, closed)).join('')}</div></details>` : ''}`;
}

function openTaskDialog(task) {
  const members = boardState.data.members;
  const name = id => members.find(m => m.id === id)?.name || ui('Affectation retirée');
  const closed = BOARD_CLOSED.includes(task.status);
  const running = task.executions.find(e => e.running);
  const nextStates = {to_prepare: ['ready', 'cancelled'], ready: ['to_prepare', 'in_progress', 'cancelled'],
    in_progress: ['awaiting_information', 'failed', 'cancelled'], awaiting_information: ['in_progress', 'cancelled'],
    in_review: ['failed', 'cancelled'], to_correct: ['in_progress', 'cancelled']}[task.status] || [];
  const detail = ui`<div class="task-detail">
    <p><span class="status ${BOARD_TONE[task.status]}">${esc(task.status_label)}</span> · responsable : <b>${task.assignee ? esc(task.assignee) : ui('aucun')}</b> · demandée par ${esc(task.author)}</p>
    ${task.stalled ? `<p class="team-issue">⚠ ${esc(task.stalled.message)}</p>` : ''}
    ${task.blocking.length ? ui`<p class="team-issue">⚠ Dépend de ${task.blocking.map(b => esc(b.objective) + ' (' + esc(boardState.data.statuses[b.status]) + ')').join(', ')}</p>` : ''}
    ${task.file_scope ? ui`<p><b>Périmètre de fichiers</b><br>${esc(task.file_scope)}</p>` : ''}
    ${task.acceptance_criteria ? ui`<p><b>Critères d’acceptation</b><br>${esc(task.acceptance_criteria)}</p>` : ''}
    ${task.deliverables ? ui`<p><b>Livrables</b><br>${esc(task.deliverables)}</p>` : ''}
    ${task.children.length ? ui`<p><b>Sous-tâches</b><br>${task.children.map(c => esc(c.objective) + ' · ' + esc(boardState.data.statuses[c.status])).join('<br>')}</p>` : ''}
    <div class="row-actions">
      ${nextStates.map(s => `<button type="button" class="secondary" data-task-move="${esc(task.id)}" data-target="${s}">${esc(boardState.data.statuses[s])}</button>`).join('')}
      ${task.status === 'in_progress' || task.status === 'to_correct' || task.status === 'in_review' ? ui`<button type="button" class="secondary" data-task-report="${esc(task.id)}">Déposer un rapport</button>` : ''}
      ${task.status === 'in_review' ? ui`<button type="button" class="primary" data-task-accept="${esc(task.id)}">Accepter</button><button type="button" class="secondary" data-task-correct="${esc(task.id)}">Demander une correction</button>` : ''}
      ${!closed && ['ready', 'to_correct'].includes(task.status) && task.assignee_id && !running ? ui`<button type="button" class="primary" data-task-run="${esc(task.id)}">Lancer ${esc(task.assignee)}</button>` : ''}
      ${running ? ui`<button type="button" class="secondary" data-execution-pause="${esc(running.id)}" data-resume="${running.paused ? 'true' : 'false'}">${running.paused ? ui('Reprendre l’agent') : ui('Mettre en pause')}</button><button type="button" class="secondary" data-execution-cancel="${esc(running.id)}">Arrêter l’agent</button>` : ''}
      ${task.assignee_id ? ui`<button type="button" class="secondary" data-member-chat="${esc(task.assignee_id)}" data-task="${esc(task.id)}">Conversation de l’agent ↗</button>` : ''}
      ${closed ? '' : ui`<button type="button" class="secondary" data-task-edit="${esc(task.id)}">Modifier</button>`}
      <button type="button" class="text-button danger" data-task-remove="${esc(task.id)}">Supprimer</button>
    </div>
    ${task.status === 'in_review' ? ui`<p class="field-help">Un rapport rendu n’est pas une tâche acceptée. Examinez les preuves avant de décider. Habilités : ${task.reviewers.map(r => esc(r.name)).join(', ') || ui('vous seul')}.</p>` : ''}
    <h4>Évaluations (${task.evaluations.length})</h4>
    <p class="field-help">Une note garde son auteur, sa date, la carte, la révision du préprompt et le modèle réellement utilisé. Elle n’alimente aucun classement automatique de modèles : une note ne démontre pas une supériorité.</p>
    ${task.evaluations.map(e => ui`<details class="event"><summary>${esc(e.author)} · ${date(e.created_at)} · ${Object.entries(e.labels).map(([k, v]) => esc(k) + ' ' + v + '/5').join(' · ')}</summary>
      <p>${esc(e.comment)}</p>
      <small>Profil ${esc(e.member)} · révision ${e.profile_revision} · ${esc(e.connector)}${e.model ? ' / ' + esc(e.model) : ui(' / modèle par défaut')}${e.duration_seconds ? ' · ' + e.duration_seconds + ' s' : ''} · ${e.usage ? ui('consommation fournie') : ui('consommation non fournie par le fournisseur')}</small></details>`).join('') || ui('<p class="muted">Aucune évaluation.</p>')}
    ${task.reports.length && !closed ? ui`<div class="row-actions"><button type="button" class="secondary" data-task-evaluate="${esc(task.id)}">Évaluer le travail rendu</button></div>` : ''}
    <h4>Exécutions (${task.executions.length})</h4>
    ${task.executions.map(e => `<p class="board-execution"><span class="status ${e.status === 'succeeded' ? 'succeeded' : e.paused ? 'paused' : e.running ? 'running' : 'failed'}">${esc(e.status_label || e.status)}</span> ${esc(e.member)} · ${date(e.created_at)}${e.detail ? '<br><small>' + esc(e.detail) + '</small>' : ''}</p>`).join('') || ui('<p class="muted">Jamais lancée. Lancer l’agent n’acceptera rien : son compte rendu passera en revue.</p>')}
    <h4>Avis demandés (${task.consultations.length})</h4>
    <p class="field-help">Un avis éclaire la décision. Il ne déplace pas la carte, ne transfère pas sa responsabilité, et ne remplace jamais un rapport.</p>
    ${task.consultations.map(c => ui`<details class="event"><summary>${esc(c.consultant)} · ${esc(c.status_label)} · demandé par ${esc(c.requester)}</summary>
      <p><b>Question</b><br>${esc(c.question)}</p>
      ${c.answer ? `<p><b>${c.status === 'declined' ? ui('Motif du refus') : ui('Avis rendu')}</b><br>${esc(c.answer)}</p><small>${esc(c.source_label)} · ${date(c.answered_at)}</small>`
        : ui`<div class="row-actions"><button type="button" class="secondary" data-consult-answer="${esc(c.id)}">Enregistrer l’avis</button><button type="button" class="text-button" data-consult-decline="${esc(c.id)}">Avis décliné</button></div>`}</details>`).join('') || ui('<p class="muted">Aucun avis demandé.</p>')}
    ${closed ? '' : ui`<div class="row-actions"><button type="button" class="secondary" data-task-consult="${esc(task.id)}">Demander un avis</button></div>`}
    <h4>Rapports rendus (${task.reports.length})</h4>
    ${task.reports.map(r => ui`<details class="event"><summary>${esc(r.author)} · ${date(r.created_at)}</summary>
      <p><span class="status ${r.source === 'agent' ? 'awaiting_approval' : 'operational'}">${r.source === 'agent' ? ui('Compte rendu de l’agent · non vérifié par CyAI') : ui('Saisi par l’utilisateur')}</span></p>
      <p><b>Résultat</b><br>${esc(r.result)}</p>
      ${r.modified_files ? ui`<p><b>Fichiers modifiés</b><br>${esc(r.modified_files)}</p>` : ''}
      <p><b>Tests réellement exécutés</b><br>${r.executed_tests ? esc(r.executed_tests) : ui('<i>aucun test déclaré — l’absence de test n’est pas une preuve de réussite</i>')}</p>
      ${r.limits ? ui`<p><b>Limites</b><br>${esc(r.limits)}</p>` : ''}
      ${r.risks ? ui`<p><b>Risques</b><br>${esc(r.risks)}</p>` : ''}
      ${r.requested_decisions ? ui`<p><b>Décisions demandées</b><br>${esc(r.requested_decisions)}</p>` : ''}</details>`).join('') || ui('<p class="muted">Aucun rapport rendu.</p>')}
    <h4>Historique</h4>
    <ul class="board-history">${task.history.map(h => `<li><b>${esc(boardState.data.statuses[h.status] || h.status)}</b> · ${esc(h.author)} · ${date(h.date)}${h.detail ? '<br><small>' + esc(h.detail) + '</small>' : ''}</li>`).join('')}</ul>
  </div>`;
  openDialog(task.objective, detail, null);
}

function taskFormHTML(task) {
  const t = task || {objective: '', assignee_id: '', parent_id: '', dependencies: [], file_scope: '', acceptance_criteria: '', deliverables: ''};
  const others = (boardState.data?.tasks || []).filter(x => !task || x.id !== task.id);
  return ui`<div class="fields">
    <label>Objectif<input name="objective" value="${esc(t.objective)}" maxlength="500" required autofocus></label>
    <div class="two-fields">
      <label>Responsable<select name="assignee_id"><option value="">À attribuer plus tard</option>${(boardState.data.members || []).filter(m => m.active).map(m => `<option value="${esc(m.id)}" ${m.id === t.assignee_id ? 'selected' : ''}>${esc(m.name)} · ${esc(m.role_label)}</option>`).join('')}</select></label>
      <label>Tâche parente<select name="parent_id"><option value="">Aucune</option>${others.map(x => `<option value="${esc(x.id)}" ${x.id === t.parent_id ? 'selected' : ''}>${esc(x.objective.slice(0, 60))}</option>`).join('')}</select></label>
    </div>
    <label>Dépendances (la tâche ne sera « prête » que lorsqu’elles seront terminées)
      <select name="dependencies" multiple size="4">${others.map(x => `<option value="${esc(x.id)}" ${t.dependencies.includes(x.id) ? 'selected' : ''}>${esc(x.objective.slice(0, 60))} · ${esc(boardState.data.statuses[x.status])}</option>`).join('')}</select></label>
    <label>Périmètre de fichiers<textarea name="file_scope" rows="2" maxlength="2000" placeholder="Les fichiers que cette tâche peut modifier">${esc(t.file_scope)}</textarea></label>
    <label>Critères d’acceptation<textarea name="acceptance_criteria" rows="3" maxlength="4000" placeholder="Ce qui devra être démontré, et comment le vérifier">${esc(t.acceptance_criteria)}</textarea></label>
    <label>Livrables<textarea name="deliverables" rows="2" maxlength="4000">${esc(t.deliverables)}</textarea></label>
    <details class="cursor-box" ${Object.keys(t.cursors || {}).length ? 'open' : ''}><summary>Curseurs de cette carte${Object.keys(t.cursors || {}).length ? ' · ' + Object.entries(t.cursors).map(([k, v]) => CURSOR_NAMES[k] + ' ' + v).join(', ') : ''}</summary>
      ${cursorFieldsHTML('cursor', t.cursors || {}, ui('Précisent ceux du projet pour cette carte ; un lancement peut encore les préciser.'))}</details>
    ${task ? '' : actorField(ui('Demandée par'))}
    <p class="field-help">Créer une carte ne lance aucun agent. L’exécution par l’équipe arrive avec la délégation.</p>
  </div>`;
}
function taskFormValues(form) {
  const values = Object.fromEntries(form);
  return {objective: values.objective, assignee_id: values.assignee_id, parent_id: values.parent_id,
          dependencies: form.getAll('dependencies'), file_scope: values.file_scope,
          acceptance_criteria: values.acceptance_criteria, deliverables: values.deliverables, cursors: cursorValues(form, 'cursor')};
}

document.addEventListener('click', async e => {
  const button = e.target.closest('button, [data-task-open]');
  if (!button) return;
  const d = button.dataset;
  try {
    if (d.taskOpen) {
      // A card can be opened from a graph or from a thread, before the board of this project was ever shown.
      if (!boardState.data || boardState.data.project_id !== state.project) boardState.data = await action('task_list', {project_id: state.project});
      const task = await action('task_get', {project_id: state.project, id: d.taskOpen});
      openTaskDialog(task);
    }
    if (button.hasAttribute('data-task-new')) {
      openDialog(ui('Nouvelle tâche'), taskFormHTML(null), async form => {
        const values = Object.fromEntries(form);
        const r = await action('task_create', {project_id: state.project, ...taskFormValues(form),
          ...(values.author_id ? {author_id: values.author_id} : {by_user: true})});
        toast(r.notice);
      }, ui('Créer la carte'));
    }
    if (d.taskEdit) {
      const task = boardTask(d.taskEdit) || await action('task_get', {project_id: state.project, id: d.taskEdit});
      if ($('dialog').open) $('dialog').close();
      openDialog(ui('Modifier · ') + task.objective, taskFormHTML(task),
        async form => { await action('task_update', {project_id: state.project, id: task.id, ...taskFormValues(form)}); });
    }
    if (d.taskMove) {
      const target = d.target;
      if ($('dialog').open) $('dialog').close();
      openDialog(ui('Passer à « ') + boardState.data.statuses[target] + ' »',
        ui`${actorField(ui('Décidé par'))}<label>Motif<textarea name="reason" rows="2" maxlength="1000" placeholder="Pourquoi ce changement"></textarea></label>`,
        async form => {
          const values = Object.fromEntries(form);
          const r = await action('task_status', {project_id: state.project, id: d.taskMove, status: target, reason: values.reason,
            ...(values.author_id ? {author_id: values.author_id} : {by_user: true})});
          toast(r.notice);
        }, ui('Enregistrer le changement'));
    }
    if (d.taskReport) {
      if ($('dialog').open) $('dialog').close();
      openDialog(ui('Rapport de tâche'), ui`<div class="fields">
        <label>Auteur du rapport<select name="author_id" required>${boardMembers()}</select></label>
        <p class="field-help">Un rapport est rendu par un agent de l’équipe : il décrit un travail fait, et il n’accepte pas la tâche.</p>
        <label>Résultat<textarea name="result" rows="4" maxlength="10000" required></textarea></label>
        <label>Fichiers modifiés<textarea name="modified_files" rows="2" maxlength="4000"></textarea></label>
        <label>Tests réellement exécutés<textarea name="executed_tests" rows="2" maxlength="4000" placeholder="Commandes lancées et résultat obtenu, pas une intention"></textarea></label>
        <label>Limites<textarea name="limits" rows="2" maxlength="2000"></textarea></label>
        <label>Risques<textarea name="risks" rows="2" maxlength="2000"></textarea></label>
        <label>Décisions demandées<textarea name="requested_decisions" rows="2" maxlength="2000"></textarea></label>
      </div>`, async form => {
        const r = await action('task_report', {project_id: state.project, id: d.taskReport, ...Object.fromEntries(form)});
        toast(r.notice);
      }, ui('Rendre le rapport'));
    }
    if (d.taskAccept || d.taskCorrect) {
      const id = d.taskAccept || d.taskCorrect;
      const task = await action('task_get', {project_id: state.project, id});
      if ($('dialog').open) $('dialog').close();
      const accepting = !!d.taskAccept;
      openDialog(accepting ? ui('Accepter la tâche') : ui('Demander une correction'), ui`<div class="fields">
        <label>Décidé par<select name="author_id"><option value="">Vous (décision de l’utilisateur)</option>${task.reviewers.map(r => `<option value="${esc(r.id)}">${esc(r.name)}</option>`).join('')}</select></label>
        <p class="field-help">${accepting ? ui('Un agent ne peut pas accepter sa propre tâche. Décrivez ce que vous avez réellement examiné : un rapport qui dit « succès » ne le démontre pas.') : ui('Indiquez précisément ce qui doit être repris.')}</p>
        <label>${accepting ? ui('Preuves examinées') : ui('Motif de la correction')}<textarea name="${accepting ? 'proofs' : 'reason'}" rows="4" maxlength="4000" required></textarea></label>
      </div>`, async form => {
        const values = Object.fromEntries(form);
        const r = await action(accepting ? 'task_accept' : 'task_correction', {project_id: state.project, id, ...values,
          ...(values.author_id ? {} : {by_user: true})});
        toast(r.notice);
      }, accepting ? ui('Accepter') : ui('Renvoyer en correction'));
    }
    if (d.taskEvaluate) {
      const task = await action('task_get', {project_id: state.project, id: d.taskEvaluate});
      if ($('dialog').open) $('dialog').close();
      openDialog(ui('Évaluer · ') + task.objective, ui`<div class="fields">
        <label>Évalué par<select name="author_id"><option value="">Vous (évaluation de l’utilisateur)</option>${task.reviewers.map(r => `<option value="${esc(r.id)}">${esc(r.name)}</option>`).join('')}</select></label>
        <p class="field-help">Un agent n’évalue pas son propre travail. Notez de 1 à 5 ; laissez vide un critère que vous ne pouvez pas juger.</p>
        ${Object.entries(task.score_labels).map(([key, label]) => ui`<label>${esc(label)}<select name="${key}"><option value="">Non évalué</option>${[1, 2, 3, 4, 5].map(n => `<option value="${n}">${n}</option>`).join('')}</select></label>`).join('')}
        <label>Commentaire explicatif<textarea name="comment" rows="4" maxlength="4000" required placeholder="Ce que vous avez constaté, et sur quoi vous vous appuyez"></textarea></label>
      </div>`, async form => {
        const values = Object.fromEntries(form);
        const scores = {};
        for (const key of Object.keys(task.score_labels)) if (values[key]) scores[key] = Number(values[key]);
        const r = await action('task_evaluate', {project_id: state.project, id: task.id, scores, comment: values.comment,
          ...(values.author_id ? {author_id: values.author_id} : {by_user: true})});
        toast(r.notice);
      }, ui('Enregistrer l’évaluation'));
    }
    if (d.taskConsult) {
      const task = await action('task_get', {project_id: state.project, id: d.taskConsult});
      if ($('dialog').open) $('dialog').close();
      if (!task.consultable.length) { openDialog(ui('Aucun agent à consulter'), ui('<p>L’équipe ne compte aucune autre affectation active que le responsable de cette tâche. Ajoutez un consultant dans l’onglet Équipe.</p>'), null); return; }
      openDialog('Demander un avis · ' + task.objective, ui`<div class="fields">
        <label>Consulter<select name="consultant_id" required>${task.consultable.map(m => `<option value="${esc(m.id)}">${esc(m.name)} · ${esc(m.role_label)}</option>`).join('')}</select></label>
        <p class="field-help">Un consultant est sollicité pour ce qu’il fait mieux. Le responsable de la carte ne se consulte pas lui-même : il rend un rapport.</p>
        ${actorField(ui('Demandé par'))}
        <label>Question posée<textarea name="question" rows="4" maxlength="4000" required placeholder="Ce sur quoi vous voulez son avis, et dans quel but"></textarea></label>
        <p class="field-help">La carte ne change pas de statut et garde son responsable. La sollicitation automatique de l’agent arrivera avec l’exécution ; pour l’instant, vous reporterez sa réponse ici.</p>
      </div>`, async form => {
        const values = Object.fromEntries(form);
        const r = await action('task_consult', {project_id: state.project, id: task.id, consultant_id: values.consultant_id,
          question: values.question, ...(values.author_id ? {author_id: values.author_id} : {by_user: true})});
        toast(r.notice);
      }, ui('Demander l’avis'));
    }
    if (d.consultAnswer || d.consultDecline) {
      const id = d.consultAnswer || d.consultDecline;
      const declined = !!d.consultDecline;
      if ($('dialog').open) $('dialog').close();
      openDialog(declined ? ui('Avis décliné') : ui('Enregistrer l’avis rendu'), `<div class="fields">
        <label>${declined ? ui('Motif du refus') : ui('Avis rendu')}<textarea name="answer" rows="5" maxlength="10000" required></textarea></label>
        ${declined ? '' : ui`<label><span><input type="checkbox" name="agent"> L’agent a réellement répondu lui-même</span></label>
        <p class="field-help">Laissez décoché si vous recopiez la réponse : elle sera marquée « saisi par l’utilisateur ». Ne présentez pas une saisie manuelle comme un travail de l’agent.</p>`}
      </div>`, async form => {
        const r = await action('task_consult_answer', {project_id: state.project, id, answer: form.get('answer'),
          ...(declined ? {declined: true} : {}), ...(form.has('agent') ? {source: 'agent'} : {})});
        toast(r.notice);
      }, ui('Enregistrer'));
    }
    if (d.taskRun) {
      const task = await action('task_get', {project_id: state.project, id: d.taskRun});
      if ($('dialog').open) $('dialog').close();
      openDialog(ui('Lancer ') + task.assignee, ui`<p><b>${esc(task.assignee)}</b> va travailler dans le dossier du projet, avec cette carte comme instruction, sur le connecteur et le modèle de sa révision figée.</p>
        <p>Ce que CyAI garantit : la carte passe « en cours », puis « en revue » quand l’agent aura répondu. Ce que CyAI ne garantit pas : que le travail annoncé ait été fait. Son compte rendu devra être examiné avant acceptation.</p>
        ${task.stalled ? `<p class="team-issue">⚠ ${esc(task.stalled.message)}</p>` : ''}
        ${task.file_scope ? ui`<p><b>Périmètre annoncé</b><br>${esc(task.file_scope)}<br><small>Le périmètre est transmis à l’agent comme consigne ; il n’est pas imposé techniquement par CyAI.</small></p>` : ui('<p class="team-issue">⚠ Aucun périmètre de fichiers n’est défini sur cette carte.</p>')}
        <details class="cursor-box"><summary>Réglages pour ce lancement${Object.keys(task.cursors || {}).length ? ui(' · carte : ') + Object.entries(task.cursors).map(([k, v]) => CURSOR_NAMES[k] + ' ' + v).join(', ') : ''}</summary>${cursorFieldsHTML('run', {}, ui('Priment sur ceux de la carte et du projet, pour ce lancement seulement.'))}</details>
        <label><span><input type="checkbox" required> J’autorise cette exécution.</span></label>`,
        async form => { const cursors = cursorValues(form, 'run'); const r = await action('task_execute', {project_id: state.project, id: task.id, ...(task.stalled ? {acknowledged: true} : {}), ...(Object.keys(cursors).length ? {cursors} : {})}); toast(r.notice); }, ui('Lancer l’agent'));
    }
    if (d.executionPause) {
      const r = await action('task_execution_pause', {project_id: state.project, id: d.executionPause, ...(d.resume === 'true' ? {resume: true} : {})});
      if ($('dialog').open) $('dialog').close();
      toast(r.notice); $('page')._rendered = null; await refresh(true);
    }
    if (d.executionCancel) {
      const r = await action('task_execution_cancel', {project_id: state.project, id: d.executionCancel});
      if ($('dialog').open) $('dialog').close();
      toast(r.notice); $('page')._rendered = null; await refresh(true);
    }
    if (d.memberChat) {
      const r = await action('team_conversation', {project_id: state.project, member_id: d.memberChat, ...(d.task ? {task_id: d.task} : {})});
      if ($('dialog').open) $('dialog').close();
      toast(r.notice);
      await selectConversation(r.id);
    }
    if (d.taskRemove) {
      const task = await action('task_get', {project_id: state.project, id: d.taskRemove});
      if ($('dialog').open) $('dialog').close();
      openDialog(ui('Supprimer la carte'), ui`<p>« ${esc(task.objective)} » sera supprimée avec ses ${task.children.length} sous-tâche(s) et ses ${task.reports.length} rapport(s). Les tâches qui en dépendent perdront cette dépendance.</p>
        <label><span><input type="checkbox" required> Je confirme la suppression.</span></label>`,
        async () => { const r = await action('task_delete', {project_id: state.project, id: task.id, acknowledged: true}); toast(r.notice); }, ui('Supprimer'));
    }
  } catch (err) { fail(err); }
});
document.addEventListener('change', e => {
  if (e.target.id === 'board-member') { boardState.member = e.target.value; $('page')._rendered = null; renderPage(); }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.dataset?.taskOpen) e.target.click();
});

// --- delegation automaton: one step you confirm, or an automatic pilot within a budget ------------------------------
function autopilotBarHTML(plan) {
  const a = plan.autopilot;
  const status = a.enabled ? ui`<span class="status running">Pilote actif · ${a.budget} lancement(s) restant(s), relectures comprises</span>`
    : ui`<span class="status">Pilote arrêté</span>${a.stopped ? ` <small class="muted">${esc(a.stopped)}</small>` : ''}`;
  const next = plan.launch.length + plan.reviews.length;
  return ui`<div class="autopilot-bar"><div><b>Automate de délégation</b> ${status}
      <small class="muted">${plan.running} exécution(s) et ${plan.reviewing} revue(s) en cours · ${next} action(s) possible(s) · ${plan.waiting.length} en attente de vous</small></div>
    <label class="tool-check" title="Un chef ou un lead qui relit peut proposer d’améliorer les consignes de l’agent, en citant la carte et le rapport. Rien ne change tant que vous n’adoptez pas la proposition (onglet Équipe)."><input type="checkbox" data-autopilot-proposals ${a.invite_proposals ? 'checked' : ''}> Les relecteurs peuvent proposer d’améliorer les consignes</label>
    <div class="row-actions"><button class="secondary" data-autopilot-step ${next ? '' : 'disabled'}>Avancer d’un pas…</button><button class="secondary" data-autopilot-config>${a.enabled ? ui('Arrêter le pilote') : ui('Pilote automatique…')}</button></div></div>`;
}
function planListHTML(title, items, line) {
  return items.length ? `<h4>${title} (${items.length})</h4><ul class="board-history">${items.map(i => `<li>${line(i)}</li>`).join('')}</ul>` : '';
}
document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button) return;
  try {
    if (button.hasAttribute('data-autopilot-step')) {
      const plan = await action('team_autopilot_plan', {project_id: state.project});
      openDialog(ui('Avancer d’un pas'), ui`<p class="field-help">${esc(plan.notice)}</p>
        ${planListHTML(ui('Cartes à lancer'), plan.launch.slice(0, plan.capacity), i => `<b>${esc(i.objective)}</b> · ${esc(i.member)} <small>(${esc(i.status)})</small>`)}
        ${planListHTML(ui('Comptes rendus à faire relire'), plan.reviews.slice(0, Math.max(0, plan.capacity - plan.launch.length)), i => ui`<b>${esc(i.objective)}</b> → relu par ${esc(i.reviewer)}`)}
        ${plan.launch.length + plan.reviews.length > plan.capacity ? ui`<p class="field-help">${plan.launch.length + plan.reviews.length - plan.capacity} autre(s) action(s) attendront le tour suivant : la limite d’exécutions simultanées est atteinte.</p>` : ''}
        ${planListHTML(ui('En attente de vous'), plan.waiting, i => `<b>${esc(i.objective)}</b> · ${esc(i.reason)}`)}
        <p class="field-help">Chaque lancement consomme les crédits du fournisseur de l’agent. Les écritures des agents restent soumises aux autorisations de leur conversation.</p>`,
        async () => { const r = await action('team_autopilot_step', {project_id: state.project}); toast(r.notice); $('page')._rendered = null; }, ui('Lancer ce tour'));
    }
    if (button.hasAttribute('data-autopilot-config')) {
      // Always the current state: the board may have been drawn before the pilot changed.
      const plan = await action('team_autopilot_plan', {project_id: state.project});
      if (plan.autopilot.enabled) {
        const r = await action('team_autopilot_set', {project_id: state.project, enabled: false});
        toast(r.notice); $('page')._rendered = null; await refresh(true); return;
      }
      openDialog(ui('Pilote automatique'), ui`<div class="fields">
        <p>Le pilote enchaîne les tours sans vous : il lance les cartes prêtes et fait relire les comptes rendus par le supérieur de l’agent.</p>
        <div class="two-fields"><label>Budget : lancements au plus (exécutions et relectures)<input name="budget" type="number" min="1" max="50" value="5" required></label>
        <label>Exécutions simultanées<input name="max_parallel" type="number" min="1" max="6" value="${plan.autopilot.max_parallel || 2}" required></label></div>
        <p class="field-help">Il s’arrête seul quand le budget est épuisé, à la première exécution échouée ou interrompue, quand plus rien ne peut avancer sans vous, et à chaque redémarrage de CyAI. Une carte signalée comme bloquée n’est jamais relancée. Chaque lancement consomme les crédits du fournisseur de l’agent.</p></div>`,
        async form => {
          const r = await action('team_autopilot_set', {project_id: state.project, enabled: true, budget: Number(form.get('budget')), max_parallel: Number(form.get('max_parallel'))});
          toast(r.notice); $('page')._rendered = null;
        }, ui('Activer le pilote'));
    }
  } catch (error) { fail(error); }
});

document.addEventListener('change', async e => {
  if (!e.target.hasAttribute?.('data-autopilot-proposals')) return;
  try {
    const r = await action('team_autopilot_options', {project_id: state.project, invite_proposals: e.target.checked});
    toast(r.notice); $('page')._rendered = null;
  } catch (error) { e.target.checked = !e.target.checked; fail(error); }
});
