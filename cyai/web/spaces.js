'use strict';
// Channels you create in a project. The first kind is a whiteboard: notes and arrows, saved automatically.
// Every save names the version it started from, so a board changed by an AI or another window is never
// overwritten: you are told, and you reload.
const board = {id: null, data: null, base: null, name: '', view: {x: 40, y: 40, z: 1}, selected: null, link: null,
  drag: null, dirty: false, saving: false, conflict: false, timer: null, mounted: null};
const NOTE_COLORS = ['yellow', 'blue', 'green', 'pink', 'violet', 'grey'];
const NOTE_WIDTH = 200;
L.views.space = ui('Tableau blanc');

function noteById(id) { return board.data.notes.find(n => n.id === id); }
function boardStatus(text) { const el = $('wb-status'); if (el) el.textContent = text; }
function scheduleSave() {
  board.dirty = true; boardStatus(ui('Modifications…'));
  clearTimeout(board.timer);
  board.timer = setTimeout(saveBoard, 700);
}
async function saveBoard() {
  if (!board.dirty || board.saving || board.conflict) return;
  board.saving = true; boardStatus(ui('Enregistrement…'));
  try {
    const r = await action('whiteboard_save', {project_id: state.project, id: board.id, data: board.data, base: board.base});
    board.base = r.updated_at; board.dirty = false; boardStatus(ui('Enregistré'));
  } catch (error) {
    if (/modifié ailleurs/.test(error.message)) { board.conflict = true; renderConflict(); }
    else { boardStatus(ui('Échec de l’enregistrement')); fail(error); }
  } finally { board.saving = false; }
}
function renderConflict() {
  const bar = $('wb-conflict');
  if (bar) bar.hidden = !board.conflict;
  boardStatus(board.conflict ? ui('Non enregistré') : '');
}

function linkPath(a, b) {
  const x1 = a.x + NOTE_WIDTH / 2, y1 = a.y + 40, x2 = b.x + NOTE_WIDTH / 2, y2 = b.y + 40;
  return `M${x1},${y1} L${x2},${y2}`;
}
function linksSVG() {
  return board.data.links.map((l, i) => {
    const a = noteById(l.from), b = noteById(l.to);
    if (!a || !b) return '';
    const mx = (a.x + b.x) / 2 + NOTE_WIDTH / 2, my = (a.y + b.y) / 2 + 40;
    return `<path class="wb-link-hit" data-link="${i}" d="${linkPath(a, b)}"></path><path class="wb-link ${board.link === i ? 'selected' : ''}" d="${linkPath(a, b)}" marker-end="url(#wb-arrow)"></path>${l.label ? `<text class="wb-label" x="${mx}" y="${my - 6}">${esc(l.label)}</text>` : ''}`;
  }).join('') + '<path id="wb-wire" class="wb-link pending" d=""></path>';
}
function noteHTML(n) {
  return ui`<div class="wb-note color-${esc(n.color)} ${board.selected === n.id ? 'selected' : ''}" data-note="${esc(n.id)}">
    <div class="wb-grip" data-note-drag="${esc(n.id)}" title="Déplacer"></div>
    <textarea data-note-text="${esc(n.id)}" maxlength="4000" placeholder="Écrire…">${esc(n.text)}</textarea>
    <span class="wb-handle" data-note-link="${esc(n.id)}" title="Glisser vers une autre note pour les relier"></span>
  </div>`;
}
function placeNotes() {
  document.querySelectorAll('#wb-notes [data-note]').forEach(el => {
    const n = noteById(el.dataset.note);
    if (n) { el.style.left = n.x + 'px'; el.style.top = n.y + 'px'; }
  });
}
function applyView() {
  const {x, y, z} = board.view;
  $('wb-world').style.transform = `translate(${x}px,${y}px) scale(${z})`;
  $('wb-canvas').style.backgroundPosition = `${x}px ${y}px`;
  $('wb-canvas').style.backgroundSize = `${24 * z}px ${24 * z}px`;
}
function renderBoard() {
  if (!$('wb-world')) return;
  applyView();
  $('wb-notes').innerHTML = board.data.notes.map(noteHTML).join('');
  placeNotes();
  $('wb-links').innerHTML = linksSVG();
  const picker = $('wb-colors');
  if (picker) picker.hidden = !board.selected;
}
function renderLinksOnly() { const g = $('wb-links'); if (g) g.innerHTML = linksSVG(); }

async function loadBoard(id) {
  const space = (await action('space_get', {project_id: state.project, id})).space;
  Object.assign(board, {id, data: space.data, base: space.updated_at, name: space.name, selected: null, link: null,
    dirty: false, conflict: false});
  return space;
}
async function renderSpace() {
  if (!state.spaceId) { showView('project'); return; }
  if (($('wb-canvas') || $('gr-canvas')) && board.mounted === state.spaceId) return;
  if (board.dirty && board.id && board.id !== state.spaceId) await saveBoard();
  // The type comes from the space itself, not from the channel list, which may not be loaded yet.
  const kind = (await action('space_get', {project_id: state.project, id: state.spaceId})).space.type;
  if (state.view !== 'space') return;
  if (kind === 'graph') { await renderGraphSpace(); return; }
  if (kind === 'plugin') { await renderPluginSpace(); return; }
  await loadBoard(state.spaceId);
  if (state.view !== 'space') return;
  board.mounted = state.spaceId;
  board.view = {x: 40, y: 40, z: 1};
  $('page-title').textContent = board.name;
  $('page').innerHTML = ui`<div class="whiteboard">
    <div class="wb-toolbar"><button type="button" class="secondary" data-wb-add>＋ Note</button>
      <span id="wb-colors" class="wb-colors" hidden>${NOTE_COLORS.map(c => ui`<button type="button" class="wb-swatch color-${c}" data-wb-color="${c}" aria-label="Couleur ${c}"></button>`).join('')}<button type="button" class="text-button danger" data-wb-delete>Supprimer la note</button></span>
      <span class="me-spacer"></span><span id="wb-status" class="wb-status">Enregistré</span>
      <button type="button" class="secondary" data-wb-fit>Cadrer</button></div>
    <div id="wb-conflict" class="notice" hidden>Ce tableau a été modifié ailleurs (par une IA ou une autre fenêtre) depuis son ouverture. Vos dernières modifications ne sont pas enregistrées. <button type="button" class="secondary" data-wb-reload>Recharger le tableau</button></div>
    <div id="wb-canvas" class="wb-canvas" tabindex="0"><div id="wb-world" class="me-world">
      <svg class="me-edges" width="20000" height="20000" viewBox="-10000 -10000 20000 20000"><defs><marker id="wb-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="wb-arrow"></path></marker></defs><g id="wb-links"></g></svg>
      <div id="wb-notes"></div></div>
      ${board.data.notes.length ? '' : ui('<p class="wb-empty">Double-cliquez pour ajouter une note. Glissez le ● d’une note vers une autre pour les relier.</p>')}</div>
  </div>`;
  renderBoard();
}
function addNote(position) {
  const id = 'n' + Date.now().toString(36);
  board.data.notes.push({id, x: position?.x ?? 60 + board.data.notes.length * 30, y: position?.y ?? 60 + board.data.notes.length * 30, text: '', color: 'yellow'});
  board.selected = id;
  document.querySelector('.wb-empty')?.remove();
  renderBoard(); scheduleSave();
  document.querySelector(`[data-note-text="${CSS.escape(id)}"]`)?.focus();
}
function boardPoint(e) {
  const rect = $('wb-canvas').getBoundingClientRect(), {x, y, z} = board.view;
  return {x: (e.clientX - rect.left - x) / z, y: (e.clientY - rect.top - y) / z};
}
function fitBoard() {
  const notes = board.data.notes, canvas = $('wb-canvas');
  if (!notes.length || !canvas) return;
  const xs = notes.map(n => n.x), ys = notes.map(n => n.y);
  const w = Math.max(...xs) + NOTE_WIDTH - Math.min(...xs), h = Math.max(...ys) + 140 - Math.min(...ys);
  const z = Math.max(0.3, Math.min(1.3, Math.min((canvas.clientWidth - 80) / w, (canvas.clientHeight - 80) / h)));
  board.view = {z, x: 40 - Math.min(...xs) * z, y: 40 - Math.min(...ys) * z};
  applyView();
}

document.addEventListener('pointerdown', e => {
  const canvas = e.target.closest?.('#wb-canvas');
  if (!canvas || e.button !== 0 || e.target.closest('textarea')) return;
  const grip = e.target.closest('[data-note-drag]'), handle = e.target.closest('[data-note-link]'), hit = e.target.closest('[data-link]');
  if (handle) board.drag = {type: 'link', from: handle.dataset.noteLink};
  else if (grip) {
    const n = noteById(grip.dataset.noteDrag), p = boardPoint(e);
    board.drag = {type: 'note', id: n.id, dx: p.x - n.x, dy: p.y - n.y, moved: false};
    if (board.selected !== n.id) { board.selected = n.id; board.link = null; renderBoard(); }
  } else if (hit) { board.link = Number(hit.dataset.link); board.selected = null; renderBoard(); return; }
  else if (!e.target.closest('[data-note]')) board.drag = {type: 'pan', sx: e.clientX, sy: e.clientY, ox: board.view.x, oy: board.view.y, moved: false};
  else return;
  canvas.setPointerCapture(e.pointerId);
});
document.addEventListener('pointermove', e => {
  const drag = board.drag;
  if (!drag || !$('wb-canvas')) return;
  if (drag.type === 'note') {
    const n = noteById(drag.id), p = boardPoint(e);
    n.x = Math.round(p.x - drag.dx); n.y = Math.round(p.y - drag.dy); drag.moved = true;
    const el = document.querySelector(`[data-note="${CSS.escape(n.id)}"]`);
    if (el) { el.style.left = n.x + 'px'; el.style.top = n.y + 'px'; }
    renderLinksOnly();
  } else if (drag.type === 'pan') {
    board.view.x = drag.ox + e.clientX - drag.sx; board.view.y = drag.oy + e.clientY - drag.sy;
    drag.moved = drag.moved || Math.abs(e.clientX - drag.sx) + Math.abs(e.clientY - drag.sy) > 3;
    applyView();
  } else if (drag.type === 'link') {
    const a = noteById(drag.from), p = boardPoint(e);
    $('wb-wire').setAttribute('d', `M${a.x + NOTE_WIDTH / 2},${a.y + 40} L${p.x},${p.y}`);
  }
});
document.addEventListener('pointerup', e => {
  const drag = board.drag;
  if (!drag) return;
  board.drag = null;
  if (drag.type === 'note' && drag.moved) scheduleSave();
  if (drag.type === 'pan' && !drag.moved && (board.selected || board.link !== null)) { board.selected = null; board.link = null; renderBoard(); }
  if (drag.type === 'link') {
    $('wb-wire')?.setAttribute('d', '');
    const target = document.elementFromPoint(e.clientX, e.clientY)?.closest('[data-note]');
    if (!target || target.dataset.note === drag.from || board.data.links.some(l => l.from === drag.from && l.to === target.dataset.note)) return;
    board.data.links.push({from: drag.from, to: target.dataset.note, label: ''});
    renderLinksOnly(); scheduleSave();
  }
});
document.addEventListener('dblclick', e => {
  if (!e.target.closest?.('#wb-canvas')) return;
  const hit = e.target.closest('[data-link]');
  if (hit) {
    const link = board.data.links[Number(hit.dataset.link)];
    openDialog(ui('Libellé du lien'), ui`<label>Libellé<input name="label" maxlength="120" value="${esc(link.label || '')}" autofocus></label>`,
      async form => { link.label = form.get('label').trim(); renderLinksOnly(); scheduleSave(); }, ui('Enregistrer'));
    return;
  }
  if (e.target.closest('[data-note]')) return;
  const p = boardPoint(e);
  addNote({x: Math.round(p.x - NOTE_WIDTH / 2), y: Math.round(p.y - 30)});
});
document.addEventListener('wheel', e => {
  if (!e.target.closest?.('#wb-canvas') || e.target.closest('textarea')) return;
  e.preventDefault();
  const rect = $('wb-canvas').getBoundingClientRect(), v = board.view;
  const z = Math.max(0.3, Math.min(2, v.z * (e.deltaY < 0 ? 1.1 : 0.9))), px = e.clientX - rect.left, py = e.clientY - rect.top;
  v.x = px - (px - v.x) * z / v.z; v.y = py - (py - v.y) * z / v.z; v.z = z;
  applyView();
}, {passive: false});
document.addEventListener('input', e => {
  const id = e.target.dataset?.noteText;
  if (!id || state.view !== 'space') return;
  noteById(id).text = e.target.value; scheduleSave();
});
document.addEventListener('focusin', e => {
  const id = e.target.dataset?.noteText;
  if (!id || board.selected === id) return;
  board.selected = id; board.link = null;
  document.querySelectorAll('.wb-note').forEach(el => el.classList.toggle('selected', el.dataset.note === id));
  $('wb-colors').hidden = false; renderLinksOnly();
});
document.addEventListener('keydown', e => {
  if (state.view !== 'space' || $('dialog').open || e.target.closest?.('input,textarea,select')) return;
  if (e.key !== 'Delete' && e.key !== 'Backspace') return;
  if (board.link !== null) { board.data.links.splice(board.link, 1); board.link = null; renderBoard(); scheduleSave(); }
  else if (board.selected) removeNote(board.selected);
});
function removeNote(id) {
  board.data.notes = board.data.notes.filter(n => n.id !== id);
  board.data.links = board.data.links.filter(l => l.from !== id && l.to !== id);
  board.selected = null; renderBoard(); scheduleSave();
}
// Someone else — an AI through the MCP, another window — may draw on the board: follow it when you are not editing.
setInterval(async () => {
  if (state.view !== 'space' || !board.id || board.dirty || board.saving || board.drag || board.conflict) return;
  if (document.activeElement?.dataset?.noteText) return;
  try {
    const space = (await action('space_get', {project_id: state.project, id: board.id})).space;
    if (space.updated_at !== board.base && !board.dirty) { board.data = space.data; board.base = space.updated_at; renderBoard(); boardStatus(ui('Mis à jour')); }
  } catch (error) { /* the next tick retries */ }
}, 3000);

document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button) return;
  const d = button.dataset;
  try {
    if (d.space) {
      if (board.dirty) await saveBoard();
      state.spaceId = d.space; board.mounted = null; showView('space');
    }
    if (d.shellAction === 'new-space') {
      openDialog(ui('Nouveau salon'), ui`<div class="fields"><label>Nom<input name="name" maxlength="80" placeholder="Idées, architecture, planches…" autofocus></label>
        <label>Type<select name="type"><option value="whiteboard">Tableau blanc — notes et liens</option><option value="graph:tasks">Graphe — tâches et dépendances</option><option value="graph:team">Graphe — hiérarchie de l’équipe</option>${consolePlugins().length ? ui('<option value="plugin">Console de plugin — ses outils de lecture</option>') : ''}</select></label>
        ${consolePlugins().length ? ui`<label>Plugin (pour une console)<select name="plugin">${consolePlugins().map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select></label>` : ''}
        <p class="field-help">Une IA du projet peut aussi le lire et y dessiner par le MCP CyAI, avec votre autorisation.</p></div>`,
        async form => {
          const [type, source] = form.get('type').split(':');
          const r = await action('space_create', {project_id: state.project, name: form.get('name'), type, ...(source ? {source} : {}),
            ...(type === 'plugin' ? {plugin: form.get('plugin')} : {})});
          toast(r.notice);
          shell.channels[state.project] = await action('project_channels', {project_id: state.project});
          setTimeout(() => { state.spaceId = r.id; board.mounted = null; showView('space'); }, 0);
        }, ui('Créer'));
    }
    if (d.spaceMenu) {
      const id = d.spaceMenu, channel = (shell.channels[state.project]?.channels || []).find(c => c.id === id);
      openDialog(ui('Salon « ') + (channel?.name || '') + ' »', ui`<label>Nom<input name="name" maxlength="80" value="${esc(channel?.name || '')}" required></label>
        <label><span><input type="checkbox" name="delete"> Supprimer ce salon et son contenu</span></label>`,
        async form => {
          if (form.get('delete')) { toast((await action('space_delete', {project_id: state.project, id})).notice); if (state.spaceId === id) { state.spaceId = null; setTimeout(() => showView('project'), 0); } }
          else await action('space_rename', {project_id: state.project, id, name: form.get('name')});
          shell.fetchedAt[state.project] = 0;
        }, ui('Enregistrer'));
    }
    if (state.view !== 'space') return;
    if (button.hasAttribute('data-wb-add')) addNote();
    if (button.hasAttribute('data-wb-fit')) fitBoard();
    if (d.wbColor && board.selected) { noteById(board.selected).color = d.wbColor; renderBoard(); scheduleSave(); }
    if (button.hasAttribute('data-wb-delete') && board.selected) removeNote(board.selected);
    if (button.hasAttribute('data-wb-reload')) { board.mounted = null; board.dirty = false; board.conflict = false; await renderSpace(); }
  } catch (error) { fail(error); }
});

// --- graphs: computed from the project each time, read-only ------------------------------------------------------
const graph = {data: null, view: {x: 40, y: 40, z: 1}, drag: null, signature: ''};
const GRAPH_WIDTH = 220;
function graphLayout(data) {
  const incoming = {}, level = {};
  data.nodes.forEach(n => { incoming[n.id] = []; });
  data.edges.forEach(e => incoming[e.to]?.push(e.from));
  const depth = (id, seen = new Set()) => {
    if (level[id] !== undefined) return level[id];
    if (seen.has(id)) return 0;
    seen.add(id);
    level[id] = incoming[id].length ? 1 + Math.max(...incoming[id].map(k => depth(k, seen))) : 0;
    return level[id];
  };
  const rows = {}, position = {};
  data.nodes.forEach(n => { const l = depth(n.id); rows[l] = (rows[l] || 0) + 1; position[n.id] = {x: 40 + l * 280, y: 40 + (rows[l] - 1) * 110}; });
  return position;
}
function graphHTML(data, position) {
  const edges = data.edges.map(e => {
    const a = position[e.from], b = position[e.to];
    if (!a || !b) return '';
    const x1 = a.x + GRAPH_WIDTH, y1 = a.y + 30, x2 = b.x, y2 = b.y + 30, dx = Math.max(50, Math.abs(x2 - x1) / 2);
    return `<path class="gr-edge ${esc(e.kind)}" d="M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}" marker-end="url(#gr-arrow)"></path>`;
  }).join('');
  const nodes = data.nodes.map(n => `<button type="button" class="gr-node kind-${esc(n.kind)} st-${esc(n.status)}" data-graph-node="${esc(n.id)}" ${n.kind === 'task' ? `data-task-open="${esc(n.id)}"` : `data-shell-member="${esc(n.id)}"`}>
      <span class="status ${esc(n.status)}">${esc(n.status_label)}</span><b>${esc(n.label)}</b><small>${esc(n.detail || '')}</small></button>`).join('');
  return {edges, nodes};
}
function applyGraphView() {
  const {x, y, z} = graph.view;
  $('gr-world').style.transform = `translate(${x}px,${y}px) scale(${z})`;
  $('gr-canvas').style.backgroundPosition = `${x}px ${y}px`;
}
function drawGraph() {
  const data = graph.data, position = graphLayout(data), html = graphHTML(data, position);
  $('gr-edges').innerHTML = html.edges;
  $('gr-nodes').innerHTML = html.nodes;
  document.querySelectorAll('#gr-nodes [data-graph-node]').forEach(el => {
    const p = position[el.dataset.graphNode];
    el.style.left = p.x + 'px'; el.style.top = p.y + 'px';
  });
  $('gr-empty').hidden = data.nodes.length > 0;
  applyGraphView();
}
async function renderGraphSpace() {
  const data = await action('graph_data', {project_id: state.project, id: state.spaceId});
  if (state.view !== 'space') return;
  graph.data = data; graph.signature = JSON.stringify(data); graph.view = {x: 40, y: 40, z: 1};
  board.mounted = state.spaceId; board.id = null;
  $('page-title').textContent = data.name;
  $('page').innerHTML = ui`<div class="whiteboard">
    <div class="wb-toolbar"><b>${esc(data.source_label)}</b><span class="wb-status">Calculé à partir du ${data.source === 'tasks' ? 'board' : ui('l’équipe')}, à jour à chaque affichage. Cliquez sur un nœud pour l’ouvrir.</span><span class="me-spacer"></span></div>
    <div id="gr-canvas" class="wb-canvas"><div id="gr-world" class="me-world">
      <svg class="me-edges" width="20000" height="20000" viewBox="-10000 -10000 20000 20000"><defs><marker id="gr-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="wb-arrow"></path></marker></defs><g id="gr-edges"></g></svg>
      <div id="gr-nodes"></div></div>
      <p id="gr-empty" class="wb-empty">${!data.team ? ui('Aucune équipe dans ce projet : composez-la dans le salon équipe.') : data.source === 'tasks' ? ui('Aucune carte sur le board pour l’instant.') : ui('Aucun membre actif.')}</p></div>
  </div>`;
  drawGraph();
}
document.addEventListener('pointerdown', e => {
  const canvas = e.target.closest?.('#gr-canvas');
  if (!canvas || e.button !== 0 || e.target.closest('[data-graph-node]')) return;
  graph.drag = {sx: e.clientX, sy: e.clientY, ox: graph.view.x, oy: graph.view.y};
  canvas.setPointerCapture(e.pointerId);
});
document.addEventListener('pointermove', e => {
  if (!graph.drag || !$('gr-canvas')) return;
  graph.view.x = graph.drag.ox + e.clientX - graph.drag.sx; graph.view.y = graph.drag.oy + e.clientY - graph.drag.sy;
  applyGraphView();
});
document.addEventListener('pointerup', () => { graph.drag = null; });
document.addEventListener('wheel', e => {
  if (!e.target.closest?.('#gr-canvas')) return;
  e.preventDefault();
  const rect = $('gr-canvas').getBoundingClientRect(), v = graph.view;
  const z = Math.max(0.3, Math.min(2, v.z * (e.deltaY < 0 ? 1.1 : 0.9))), px = e.clientX - rect.left, py = e.clientY - rect.top;
  v.x = px - (px - v.x) * z / v.z; v.y = py - (py - v.y) * z / v.z; v.z = z;
  applyGraphView();
}, {passive: false});
// The graph follows the board while it is open.
setInterval(async () => {
  if (state.view !== 'space' || !$('gr-canvas') || graph.drag) return;
  try {
    const data = await action('graph_data', {project_id: state.project, id: state.spaceId});
    const signature = JSON.stringify(data);
    if (signature !== graph.signature) { graph.data = data; graph.signature = signature; drawGraph(); }
  } catch (error) { /* the next tick retries */ }
}, 5000);

// --- plugin console: the read tools of a plugin, called by hand, with their history ---------------------------------
function consolePlugins() {
  return (state.data?.plugins || []).filter(p => p.project_tab === true && p.enabled && p.projects?.[state.project]?.enabled !== false && (!p.local_registry || p.projects?.[state.project]?.enabled === true));
}
const pluginConsole = {data: null};
function argumentFields(tool) {
  const properties = tool?.inputSchema?.properties || {}, required = tool?.inputSchema?.required || [];
  const simple = Object.entries(properties).filter(([, s]) => ['string', 'number', 'integer', 'boolean'].includes(s.type));
  return simple.map(([key, s]) => s.type === 'boolean'
    ? `<label><span><input type="checkbox" data-arg="${esc(key)}" data-arg-type="boolean"> ${esc(key)}</span>${s.description ? `<small class="field-help">${esc(s.description)}</small>` : ''}</label>`
    : `<label>${esc(key)}${required.includes(key) ? ' *' : ''}<input data-arg="${esc(key)}" data-arg-type="${esc(s.type)}" ${s.type === 'string' ? '' : 'type="number"'} ${required.includes(key) ? 'required' : ''}>${s.description ? `<small class="field-help">${esc(s.description)}</small>` : ''}</label>`).join('')
    + ui`<label>Autres arguments (JSON)<textarea data-arg-json rows="3">{}</textarea></label>`;
}
function callHTML(c) {
  return `<article class="pc-call ${c.ok ? 'ok' : 'error'}"><header><b>${esc(c.tool)}</b> <span class="status ${c.ok ? 'succeeded' : 'failed'}">${c.ok ? ui('Réponse') : ui('Refusé ou en erreur')}</span><time>${date(c.at)}</time></header>
    ${Object.keys(c.arguments || {}).length ? `<pre class="context-pre">${esc(JSON.stringify(c.arguments, null, 2))}</pre>` : ''}
    <pre class="context-pre">${esc(c.ok ? c.result : c.error)}</pre></article>`;
}
async function renderPluginSpace() {
  const data = await action('plugin_console', {project_id: state.project, id: state.spaceId});
  if (state.view !== 'space') return;
  pluginConsole.data = data; board.mounted = state.spaceId; board.id = null;
  $('page-title').textContent = data.name;
  const tool = data.tools[0];
  $('page').innerHTML = ui`<div class="page-intro"><h2>${esc(data.name)}</h2><p>Console du plugin <b>${esc(data.plugin)}</b> : seuls ses outils de <b>lecture</b> déclarés sont appelables, dans les règles de ce projet. Chaque appel et sa réponse restent dans ce salon.</p></div>
    ${data.problem ? `<p class="me-warning">⚠ ${esc(data.problem)}</p>` : ''}
    ${data.tools.length ? ui`<form id="pc-form" class="card fields">
      <label>Outil<select id="pc-tool">${data.tools.map(t => `<option value="${esc(t.name)}">${esc(t.name)}</option>`).join('')}</select></label>
      <p id="pc-description" class="field-help">${esc(tool.description || '')}</p>
      <div id="pc-args" class="fields">${argumentFields(tool)}</div>
      <div class="row-actions"><button class="primary" type="submit">Appeler</button></div></form>` : ''}
    <h3>Historique</h3><div id="pc-history">${data.calls.map(callHTML).join('') || ui('<div class="empty-state">Aucun appel pour l’instant.</div>')}</div>`;
}
document.addEventListener('change', e => {
  if (e.target.id !== 'pc-tool') return;
  const tool = pluginConsole.data.tools.find(t => t.name === e.target.value);
  $('pc-description').textContent = tool.description || '';
  $('pc-args').innerHTML = argumentFields(tool);
});
document.addEventListener('submit', async e => {
  if (e.target.id !== 'pc-form') return;
  e.preventDefault();
  try {
    let args = {};
    try { args = JSON.parse(e.target.querySelector('[data-arg-json]').value || '{}'); } catch (error) { throw new Error(ui('Les autres arguments ne sont pas un JSON valide.')); }
    e.target.querySelectorAll('[data-arg]').forEach(input => {
      const type = input.dataset.argType;
      if (type === 'boolean') { if (input.checked) args[input.dataset.arg] = true; return; }
      if (input.value === '') return;
      args[input.dataset.arg] = type === 'string' ? input.value : Number(input.value);
    });
    const button = e.target.querySelector('[type="submit"]'); button.disabled = true;
    try {
      const r = await action('plugin_console_call', {project_id: state.project, id: state.spaceId, tool: $('pc-tool').value, arguments: args});
      pluginConsole.data.calls.unshift(r.call);
      $('pc-history').innerHTML = pluginConsole.data.calls.map(callHTML).join('');
    } finally { button.disabled = false; }
  } catch (error) { fail(error); }
});
