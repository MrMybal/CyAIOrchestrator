'use strict';
// The instruction writer: a task's instruction — or the method's base prompt, or its user guide — opened large, with
// the files it carries and, beside it, the method's workshop: a real conversation with an AI, outside any project.
// The AI proposes a complete text in a ```consigne block; you adopt it or not. Nothing changes without you.
const writer = {open: false, target: null, assets: [], messages: [], proposals: [], mission: null, timer: null, live: '',
  undo: null, connector: '', model: '', sending: false};
const WRITER_FIELDS = {preprompt: ui('Prompt de base de la méthode'), usage: ui('Mode d’emploi de la méthode'), description: ui('Description de la méthode')};
const WRITER_PROMPTS = [ui('Rends cette consigne plus précise, sans la rallonger inutilement.'), ui('Liste les ambiguïtés et ce qui manque pour bien exécuter la tâche.'),
  ui('Adapte cette consigne à un petit modèle local : phrases courtes, étapes numérotées, format de sortie explicite.'),
  ui('Propose un découpage en sous-tâches, avec pour chacune ses entrées et ses sorties.')];

function writerStep() { return writer.target?.step ? stepByKey(writer.target.step) : null; }
function writerText() { const step = writerStep(); return step ? step.instruction : methodEditor.draft[writer.target.field] || ''; }
function setWriterText(value) {
  const step = writerStep();
  if (step) step.instruction = value; else methodEditor.draft[writer.target.field] = value;
  markDirty();
}
function writerTitle() {
  const step = writerStep();
  return step ? {kicker: ui('Consigne de la tâche'), title: step.name} : {kicker: methodEditor.draft.name, title: WRITER_FIELDS[writer.target.field]};
}

async function openWriter(target) {
  // The workshop and the files belong to a saved method.
  if (!methodEditor.id) await saveMethodGraph();
  writer.target = target; writer.open = true; writer.undo = null; writer.live = '';
  const enabled = (state.data?.connectors || []).filter(c => c.enabled);
  if (!enabled.some(c => c.id === writer.connector)) writer.connector = enabled[0]?.id || '';
  writer.assets = (await action('method_assets', {id: methodEditor.id})).assets;
  renderWriter();
  await loadWriterMessages();
}
function closeWriter() {
  clearInterval(writer.timer); writer.timer = null;
  writer.open = false;
  $('me-writer')?.remove();
  renderGraph(); renderInspectorPanel();
}

function writerAttachmentsHTML() {
  const step = writerStep();
  if (!step) return '';
  const byId = Object.fromEntries(writer.assets.map(a => [a.id, a]));
  const unused = writer.assets.filter(a => !step.attachments?.includes(a.id));
  const chips = (step.attachments || []).map(id => {
    const a = byId[id];
    if (!a) return '';
    const image = /^image\/(png|jpeg|webp|gif)$/.test(a.mime);
    return ui`<div class="mw-file">${image ? `<img alt="" src="/method-asset/${esc(a.id)}">` : '<span class="mw-file-icon">📄</span>'}<span title="${esc(a.name)}">${esc(a.name)}</span><button type="button" class="text-button" data-mw-detach="${esc(a.id)}" aria-label="Retirer de la tâche">✕</button></div>`;
  }).join('');
  return ui`<div class="mw-files"><b class="me-label">Fichiers et images de la consigne (${(step.attachments || []).length}/8) — transmis à cette tâche seulement</b>
    <div class="mw-file-list">${chips || ui('<small class="muted">Aucun. Glissez un fichier ici ou joignez-le.</small>')}</div>
    <div class="row-actions"><button type="button" class="secondary" data-mw-attach>＋ Joindre</button>
      ${unused.length ? ui`<select data-mw-reuse><option value="">Réutiliser un fichier de la méthode…</option>${unused.map(a => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('')}</select>` : ''}</div></div>`;
}
function writerInputsHint() {
  const step = writerStep();
  if (!step) return '';
  const wired = step.inputs.map(p => `<span class="team-chip" title="${esc(p.source ? ui('Reçoit : ') + sourceName(p.source) : ui('Non branchée'))}"><span class="me-kind k-${esc(p.kind)}"></span> ${esc(p.name)}</span>`).join('');
  return ui`<div class="mw-hint">${wired ? ui('Ajoutées après la consigne : ') + wired : ui('Aucune entrée branchée.')} <button type="button" class="text-button" data-mw-insert="{objectif}">Insérer {objectif}</button></div>`;
}
function writerMessagesHTML() {
  writer.proposals = [];
  const rows = writer.messages.map(m => {
    if (m.role === 'user') {
      const ask = m.content.includes('\nDemande :\n') ? m.content.split('\nDemande :\n').pop() : m.content;
      return `<div class="mw-msg user"><div class="mw-bubble">${esc(ask)}</div></div>`;
    }
    const parts = m.content.split(/```consigne[^\n]*\n([\s\S]*?)```/g);
    const html = parts.map((part, i) => {
      if (i % 2 === 0) return part.trim() ? `<div class="message-body">${richText(part.trim())}</div>` : '';
      const n = writer.proposals.push(part.replace(/\s+$/, '')) - 1;
      return ui`<div class="mw-proposal"><pre>${esc(part.replace(/\s+$/, ''))}</pre><button type="button" class="primary" data-mw-adopt="${n}">Adopter ce texte</button></div>`;
    }).join('');
    return `<div class="mw-msg ai"><small>${esc(agentName(m.connector || ''))}${m.model ? ' · ' + esc(m.model) : ''}</small>${html}</div>`;
  }).join('');
  const live = writer.mission ? ui`<div class="mw-msg ai live"><small>L’IA écrit…</small><div class="message-body">${writer.live ? richText(writer.live) : '<span class="loading">…</span>'}</div></div>` : '';
  return rows + live || ui('<p class="mw-empty">Demandez à une IA de vous aider : elle voit la méthode telle qu’elle est dans l’éditeur, et le texte que vous écrivez. Elle propose un texte complet ; vous l’adoptez ou non.</p>');
}
function renderWriter() {
  const host = document.querySelector('.method-editor');
  if (!host || !writer.open) return;
  let panel = $('me-writer');
  if (!panel) { panel = document.createElement('div'); panel.id = 'me-writer'; panel.className = 'me-writer'; host.append(panel); }
  const {kicker, title} = writerTitle(), enabled = (state.data?.connectors || []).filter(c => c.enabled);
  panel.innerHTML = ui`<header class="mw-head"><button type="button" class="secondary" data-mw-close>← Graphe</button>
      <div class="mw-title"><small>${esc(kicker)}</small><h3>${esc(title)}</h3></div><span class="me-spacer"></span>
      <button type="button" class="secondary" data-mw-undo ${writer.undo === null ? 'hidden' : ''}>Revenir au texte d’avant</button>
      <button type="button" class="primary" data-mw-close>Terminé</button></header>
    <div class="mw-body">
      <section class="mw-edit" id="mw-drop">
        ${writerInputsHint()}
        <textarea id="mw-text" maxlength="${writer.target.step ? 20000 : writer.target.field === 'usage' ? 8000 : writer.target.field === 'description' ? 4000 : 20000}" spellcheck="true" placeholder="Écrivez ici. Ce texte est enregistré avec la méthode quand vous enregistrez.">${esc(writerText())}</textarea>
        <div class="mw-count" id="mw-count"></div>
        ${writerAttachmentsHTML()}
      </section>
      <section class="mw-chat">
        <div class="mw-chat-head"><b>Assistant</b>
          ${enabled.length ? ui`<select data-mw-connector aria-label="IA">${enabled.map(c => `<option value="${esc(c.id)}" ${c.id === writer.connector ? 'selected' : ''}>${esc(agentName(c.id))}</option>`).join('')}</select><input data-mw-model value="${esc(writer.model)}" placeholder="modèle par défaut" aria-label="Modèle">` : ui('<span class="me-warning">⚠ Aucun connecteur activé</span>')}
          ${methodEditor.workshop ? ui('<button type="button" class="text-button" data-mw-conversation>Ouvrir la conversation ↗</button>') : ''}</div>
        <div class="mw-messages" id="mw-messages">${writerMessagesHTML()}</div>
        <div class="mw-quick">${WRITER_PROMPTS.map((p, i) => `<button type="button" class="text-button" data-mw-quick="${i}">${esc(p.split(/[,:.]/)[0])}</button>`).join('')}</div>
        <div class="mw-composer"><textarea id="mw-ask" rows="3" maxlength="8000" placeholder="Votre demande à l’IA (Ctrl+Entrée pour envoyer)"></textarea>
          <button type="button" class="primary" data-mw-send ${writer.mission || !enabled.length ? 'disabled' : ''}>Envoyer</button></div>
        <p class="field-help">Chaque demande part avec la méthode telle qu’elle est dans l’éditeur (renvoyée seulement si elle a changé) et le texte en cours. C’est une vraie conversation : elle consomme des crédits de l’IA choisie.</p>
      </section>
    </div>`;
  updateWriterCount();
  const box = $('mw-messages'); box.scrollTop = box.scrollHeight;
}
function updateWriterCount() { const t = $('mw-text'), c = $('mw-count'); if (t && c) c.textContent = t.value.length + ' / ' + t.maxLength + ui(' caractères'); }
function renderWriterMessages() { const box = $('mw-messages'); if (!box) return; box.innerHTML = writerMessagesHTML(); box.scrollTop = box.scrollHeight; }

async function loadWriterMessages() {
  if (!methodEditor.workshop) { writer.messages = []; renderWriterMessages(); return; }
  try {
    const detail = await api('conversation/' + methodEditor.workshop);
    writer.messages = detail.messages.filter(m => m.role === 'user' || m.role === 'assistant');
  } catch (error) { writer.messages = []; }
  renderWriterMessages();
}
async function sendToWorkshop() {
  const ask = $('mw-ask')?.value.trim();
  if (!ask || writer.mission) return;
  const r = await action('method_workshop_send', {id: methodEditor.id, draft: payload(), target: writer.target.step ? {step: writer.target.step} : {field: writer.target.field},
    instruction: ask, connector: writer.connector, model: writer.model});
  methodEditor.workshop = r.conversation_id;
  writer.mission = r.mission_id; writer.live = '';
  writer.messages.push({role: 'user', content: ask});
  renderWriter();
  watchWorkshop();
}
function watchWorkshop() {
  clearInterval(writer.timer);
  writer.timer = setInterval(async () => {
    if (!writer.open || !writer.mission) { clearInterval(writer.timer); return; }
    try {
      const m = await api('mission/' + writer.mission);
      writer.live = m.events.filter(e => e.kind === 'delta').map(e => e.data.text).join('');
      if (['succeeded', 'failed', 'cancelled', 'interrupted'].includes(m.status)) {
        clearInterval(writer.timer); writer.mission = null;
        if (m.status !== 'succeeded') toast(ui('L’IA n’a pas répondu : ') + (m.steps.find(s => s.error)?.error || m.status));
        await loadWriterMessages();
        const send = document.querySelector('[data-mw-send]'); if (send) send.disabled = false;
      } else renderWriterMessages();
    } catch (error) { clearInterval(writer.timer); writer.mission = null; fail(error); }
  }, 1000);
}

// Files: uploaded to the method, then joined to this task.
function uploadMethodAsset(file) {
  return new Promise((resolve, reject) => {
    if (file.size > 50 * 1024 ** 2) { reject(Error(ui('Fichier limité à 50 Mo : ') + file.name)); return; }
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload?method_id=' + encodeURIComponent(methodEditor.id) + '&name=' + encodeURIComponent(file.name));
    xhr.setRequestHeader('X-CyAI', '1'); xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.onerror = () => reject(Error(ui('Transfert interrompu.')));
    xhr.onload = () => { let r; try { r = JSON.parse(xhr.responseText); } catch { reject(Error(ui('Réponse de transfert invalide.'))); return; } xhr.status === 200 ? resolve(r) : reject(Error(r.error || ui('Échec du transfert'))); };
    xhr.send(file);
  });
}
async function attachFiles(files) {
  const step = writerStep();
  if (!step) return;
  for (const file of files) {
    if ((step.attachments || []).length >= 8) { toast(ui('Huit fichiers au plus par tâche.')); break; }
    try {
      const asset = await uploadMethodAsset(file);
      writer.assets.push(asset);
      step.attachments = [...(step.attachments || []), asset.id];
      markDirty();
    } catch (error) { fail(error); }
  }
  renderWriter();
}

document.addEventListener('input', e => {
  if (!writer.open) return;
  if (e.target.id === 'mw-text') { setWriterText(e.target.value); updateWriterCount(); }
  if (e.target.matches?.('[data-mw-model]')) writer.model = e.target.value;
});
document.addEventListener('change', e => {
  if (!writer.open) return;
  if (e.target.matches?.('[data-mw-connector]')) writer.connector = e.target.value;
  if (e.target.matches?.('[data-mw-reuse]') && e.target.value) {
    const step = writerStep();
    if ((step.attachments || []).length >= 8) { toast(ui('Huit fichiers au plus par tâche.')); return; }
    step.attachments = [...(step.attachments || []), e.target.value]; markDirty(); renderWriter();
  }
});
document.addEventListener('keydown', e => {
  if (writer.open && e.target.id === 'mw-ask' && e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); sendToWorkshop().catch(fail); }
});
document.addEventListener('dragover', e => { if (writer.open && writerStep() && e.target.closest?.('#mw-drop') && e.dataTransfer?.types.includes('Files')) { e.preventDefault(); $('mw-drop').classList.add('drop'); } });
document.addEventListener('dragleave', e => { if (e.target.id === 'mw-drop') e.target.classList.remove('drop'); });
document.addEventListener('drop', e => {
  if (!writer.open || !writerStep() || !e.target.closest?.('#mw-drop') || !e.dataTransfer?.files.length) return;
  e.preventDefault(); $('mw-drop').classList.remove('drop');
  attachFiles([...e.dataTransfer.files]);
});
document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button) return;
  const d = button.dataset;
  try {
    if (d.mwOpen) await openWriter(d.mwOpen === 'step' ? {step: methodEditor.selected} : {field: d.mwOpen});
    if (!writer.open) return;
    if (d.mwClose !== undefined) closeWriter();
    if (d.mwSend !== undefined) await sendToWorkshop();
    if (d.mwQuick !== undefined) { const ask = $('mw-ask'); ask.value = WRITER_PROMPTS[Number(d.mwQuick)]; ask.focus(); }
    if (d.mwAdopt !== undefined) {
      const text = writer.proposals[Number(d.mwAdopt)];
      if (text === undefined) return;
      writer.undo = writerText(); setWriterText(text); renderWriter();
      toast(ui('Texte adopté dans l’éditeur. Enregistrez la méthode pour le garder.'));
    }
    if (d.mwUndo !== undefined && writer.undo !== null) { setWriterText(writer.undo); writer.undo = null; renderWriter(); }
    if (d.mwInsert) {
      const area = $('mw-text'), at = area.selectionStart ?? area.value.length;
      area.value = area.value.slice(0, at) + d.mwInsert + area.value.slice(area.selectionEnd ?? at);
      setWriterText(area.value); updateWriterCount(); area.focus();
    }
    if (d.mwAttach !== undefined) {
      const input = document.createElement('input');
      input.type = 'file'; input.multiple = true;
      input.onchange = () => attachFiles([...input.files]);
      input.click();
    }
    if (d.mwDetach) { const step = writerStep(); step.attachments = step.attachments.filter(a => a !== d.mwDetach); markDirty(); renderWriter(); }
    if (d.mwConversation !== undefined && methodEditor.workshop) {
      const target = methodEditor.workshop;
      closeWriter();
      leaveMethodEditor(async () => { state.home = true; await selectConversation(target); });
    }
  } catch (error) { fail(error); }
});
