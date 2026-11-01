'use strict';
// Reusable methods, listed in the library. They are edited as graphs in method-editor.js. Preparing one
// never launches it — you read the chain first, then start it from the mission panel like any other.
const methodState = {list: []};

// What the library card of an agent says about its methods, and the programs they need on this machine.
function profileMethodsLine(id) {
  const links = teamsState.methodSummary?.[id];
  if (!links) return '';
  return ui`<p><small>Méthodes : ${links.methods.map(m => (m.mode === 'always' ? '⚑ ' : '★ ') + esc(m.name)).join(', ')}</small></p>` +
    (links.software.length ? ui`<p><small>Nécessite : ${links.software.map(s => esc(s.name) + (s.found ? ' ✓' : ' <span class="me-warning">⚠ absent de cette machine</span>')).join(', ')}</small></p>` : '');
}
function noteBlock(owner, note, author, updated, target) {
  return ui`<details class="pm-note"><summary>Note d’usage${note ? ' · ' + (author === 'agent' ? ui('écrite par l’agent') : ui('écrite par vous')) + (updated ? ui(' le ') + esc(new Date(updated).toLocaleDateString(CYAI_FORMAT_LOCALE)) : '') : ui(' · aucune')}</summary>
    ${note ? `<div class="message-body pm-note-text">${richText(note)}</div>` : ''}
    <textarea rows="5" maxlength="20000" data-pm-note-text="${esc(target)}" placeholder="Ce qui marche avec cette méthode, les pièges, ce qu’il faut vérifier. L’agent peut aussi l’écrire lui-même (method_note_save).">${esc(note || '')}</textarea>
    <div class="row-actions"><button type="button" class="secondary" data-pm-note-save="${esc(target)}">Enregistrer la note</button></div></details>`;
}
function modeSelect(value, target) {
  return ui`<select data-pm-mode="${esc(target)}" aria-label="Lien"><option value="preferred" ${value === 'preferred' ? 'selected' : ''}>★ Préférée</option><option value="always" ${value === 'always' ? 'selected' : ''}>⚑ À utiliser</option><option value="none" ${!value ? 'selected' : ''}>Non liée (note seule)</option></select>`;
}
async function profileMethodsHTML(profileId) {
  const r = await action('profile_methods', {profile_id: profileId}), linked = new Set(r.methods.map(m => m.method_id));
  const methods = methodState.list.length ? methodState.list : (methodState.list = (await action('method_list')).methods);
  return ui`<div class="fields" id="pm-body" data-pm-profile="${esc(profileId)}"><button type="button" class="secondary" data-evaluation-reports="${esc(profileId)}">Évaluations et mode d’emploi de cet agent</button>
    <p class="field-help">Une méthode <b>préférée</b> est proposée en premier quand cet agent cherche une méthode ; une méthode <b>à utiliser</b> est celle qu’il doit appliquer pour ce type de travail. L’agent les lit au début de son contexte, avec sa note d’usage. Rien de tout cela ne crée de révision.</p>
    ${r.methods.map(m => `<div class="pm-row"><div class="pm-head"><div><b>${esc(m.name)}</b><small>${esc(m.description || '')}</small>
        ${m.software.length ? ui`<small>Nécessite : ${m.software.map(s => esc(s.name) + (s.found ? ' ✓ ' + esc(s.where) : ' ⚠ absent de cette machine')).join(' · ')}</small>` : ''}</div>
        ${modeSelect(m.mode, profileId + ':' + m.method_id)}</div>
      ${noteBlock('profile', m.note, m.note_author, m.note_updated_at, profileId + ':' + m.method_id)}</div>`).join('') || ui('<p class="muted">Aucune méthode liée.</p>')}
    <label>Lier une méthode<select data-pm-add="${esc(profileId)}"><option value="">Choisir…</option>${methods.filter(m => !linked.has(m.id)).map(m => `<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('')}</select></label>
  </div>`;
}
async function openProfileMethodsDialog(profileId) {
  const profile = (teamsState.profiles || []).find(p => p.id === profileId);
  openDialog(ui('Méthodes · ') + (profile?.name || 'agent'), await profileMethodsHTML(profileId), null);
}
async function refreshMethodLinks(profileId) {
  const body = $('pm-body');
  if (body && body.dataset.pmProfile === profileId) body.outerHTML = await profileMethodsHTML(profileId);
  if (state.view === 'method' && typeof loadMethodAgents === 'function') await loadMethodAgents();
  if (state.view === 'agents') { teamsState.methodSummary = (await action('profile_methods_summary')).profiles; $('page')._rendered = null; }
}
document.addEventListener('change', async e => {
  const t = e.target, d = t.dataset;
  try {
    if (d.pmMode) {
      const [profile, method] = d.pmMode.split(':');
      toast((await action('profile_method_set', {profile_id: profile, method_id: method, mode: t.value})).notice);
      await refreshMethodLinks(profile);
    }
    if (d.pmAdd && t.value) {
      toast((await action('profile_method_set', {profile_id: d.pmAdd, method_id: t.value, mode: 'preferred'})).notice);
      await refreshMethodLinks(d.pmAdd);
    }
  } catch (err) { fail(err); }
});

function methodsHTML() {
  const executors = m => [...new Set(m.steps.map(s => s.executor === 'profile' ? (s.profile_name || 'profil') : s.executor === 'any' ? ui('n’importe quelle IA') : agentName(s.connector)))].join(', ');
  return ui`<div class="page-intro"><div><h2>Méthodes</h2><p>Un enchaînement de tâches que vous avez vérifié, rejouable sur un nouvel objectif : chaque tâche est tenue par un profil, par un connecteur précis ou par n’importe quelle IA, et peut appeler d’autres agents. CyAI garantit l’ordre, les dépendances, les instructions envoyées et l’existence des fichiers déclarés — pas leur qualité.</p></div>
    <div class="row-actions"><button class="primary" data-method-graph="">＋ Nouvelle méthode</button><button class="secondary" data-method-import>Importer…</button><button class="secondary" data-evaluation-install>Ajouter la méthode d’évaluation</button></div></div>
    <div class="card-grid">${methodState.list.map(m => {
      const warnings = (m.warnings || []).filter(w => w.level === 'warning');
      return ui`<article class="card"><div class="card-header"><h3>${esc(m.name)}</h3>${m.category ? `<span class="team-chip">${esc(m.category)}</span>` : ''}</div>
        <p>${esc(m.description || ui('Pas de description.'))}</p>
        <p><small>${m.steps.length} tâche(s) · ${esc(executors(m))}</small></p>
        ${warnings.length ? ui`<p class="me-warning" title="${esc(warnings.map(w => w.where + ' : ' + w.message).join('\n'))}">⚠ ${warnings.length} avertissement(s) sur cette machine</p>` : ui('<p><span class="status succeeded">Prête sur cette machine</span></p>')}
        <div class="row-actions"><button class="primary" data-method-graph="${esc(m.id)}">Ouvrir l’éditeur</button><button class="secondary" data-method-apply="${esc(m.id)}">Appliquer…</button><button class="secondary" data-method-skill="${esc(m.id)}" title="Toute IA du projet la reçoit comme recette à suivre">Comme skill…</button><button class="text-button" data-method-export="${esc(m.id)}">Exporter</button><button class="text-button danger" data-method-delete="${esc(m.id)}">Supprimer</button></div></article>`;
    }).join('') || ui('<div class="empty-state">Aucune méthode. Créez-en une dans l’éditeur, ou importez un export.</div>')}</div>`;
}

document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button) return;
  const d = button.dataset;
  try {
    if ('evaluationInstall' in d) { const r = await action('evaluation_method_install', {}); toast(r.notice); methodState.list = (await action('method_list')).methods; if (state.view === 'agents') await renderAgentsPage(); }
    if (d.evaluationReports) await openEvaluationReports(d.evaluationReports);
    if (d.profileMethods) await openProfileMethodsDialog(d.profileMethods);
    if (d.pmNoteSave) {
      const [profile, method] = d.pmNoteSave.split(':'), text = document.querySelector(`[data-pm-note-text="${CSS.escape(d.pmNoteSave)}"]`).value;
      toast((await action('method_note_save', {profile_id: profile, method_id: method, content: text})).notice);
      await refreshMethodLinks(profile);
    }
    if (d.softwarePath) {
      const name = d.softwarePath;
      openDialog(ui('Où est « ') + name + ui(' » sur cette machine ?'), ui`<div class="fields"><label>Chemin complet de l’exécutable ou du dossier<input name="path" required placeholder="C:\\Program Files\\${esc(name)}\\${esc(name)}.exe"></label>
        <p class="field-help">Gardé dans la configuration de cette machine seulement : l’export de la méthode ne l’emporte pas. Il est écrit dans les tâches de la méthode, pour que l’agent sache où lancer le logiciel.</p></div>`,
        async form => {
          toast((await action('software_path_set', {name, path: form.get('path')})).notice);
          if (state.view === 'method' && methodEditor.id) { methodEditor.warnings = (await action('method_check', {id: methodEditor.id})).warnings; renderWarnings(); }
        }, ui('Enregistrer'));
    }
    if (d.methodDelete) {
      const method = methodState.list.find(m => m.id === d.methodDelete);
      openDialog(ui('Supprimer la méthode'), ui`<p>« ${esc(method.name)} » sera supprimée. Les chaînes déjà préparées à partir d’elle ne sont pas touchées.</p><label><span><input type="checkbox" required> Je confirme la suppression</span></label>`,
        async () => { const r = await action('method_delete', {id: method.id}); toast(r.notice); }, ui('Supprimer'));
    }
    if (d.methodApply) await methodApplyDialog(methodState.list.find(m => m.id === d.methodApply));
    if (d.methodSkill) {
      const method = methodState.list.find(m => m.id === d.methodSkill);
      openDialog(ui('Utiliser « ') + method.name + ui(' » comme skill'), ui`<div class="fields">
        <label>Projet<select name="project_id">${projectOptions(state.project)}</select></label>
        <p class="field-help">Toutes les conversations de ce projet recevront la méthode dans leur contexte, comme une recette à suivre, quelle que soit l’IA. Rien n’est lancé. La réajouter la met à jour ; elle se retire dans Skills & contexte.</p></div>`,
        async form => { toast((await action('method_as_skill', {id: method.id, project_id: form.get('project_id')})).notice); }, ui('Ajouter le skill'));
    }
  } catch (err) { fail(err); }
});


async function openEvaluationReports(profileId) {
  const result = await action('evaluation_reports', {profile_id: profileId});
  openDialog(ui('Évaluations · rapports et mode d’emploi'), ui`<p>Profil : <code>${esc(profileId)}</code>. Importez un rapport avec cet agent.id, ses auteurs, dates et handoff_guide. Les versions précédentes sont conservées. Les identités importées sont déclaratives.</p>
    <label>Importer un rapport JSON<input type="file" id="evaluation-import" accept=".json,application/json"></label>
    ${result.reports.map((r, index) => ui`<details><summary>${esc(r.report.provenance?.report_created_at || ui('Date inconnue'))} · ${esc((r.report.provenance?.contributors || []).map(a => a.agent_name || ui('IA inconnue')).join(', '))}</summary><button type="button" class="secondary" data-evaluation-export="${index}">Exporter le rapport</button><pre>${esc(JSON.stringify(r.report.handoff_guide, null, 2))}</pre></details>`).join('') || ui('<p>Aucune évaluation enregistrée.</p>')}`, null);
  $('evaluation-import').onchange = async e => {
    const file = e.target.files[0]; if (!file) return;
    try { const report = JSON.parse(await file.text()); toast((await action('evaluation_report_save', {profile_id: profileId, report})).notice); await openEvaluationReports(profileId); } catch (err) { fail(err); }
  };
  document.querySelectorAll('[data-evaluation-export]').forEach(button => button.onclick = () => {
    const report = result.reports[Number(button.dataset.evaluationExport)];
    const url = URL.createObjectURL(new Blob([JSON.stringify(report.report, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'evaluation-' + report.id + '.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}
