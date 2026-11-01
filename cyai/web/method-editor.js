'use strict';
// Node editor for methods, like a blueprint. A task node has order pins in its header (after / before) and data pins
// below it: inputs on the left, outputs on the right. A wire from an output to an input is what passes between two
// tasks, and it orders them too. The method's own inputs (objective, contexts, files) and outputs are two nodes of the
// graph; a context wired to one task only reaches that task. A node can also be another method, unfolded on applying.
// The graph is the method itself — an AI edits the same structure through the MCP (method_save).
// Nothing here runs anything: applying a method prepares a chain that you launch yourself.
const methodEditor = {draft: null, id: null, selected: null, edge: null, view: {x: 40, y: 40, z: 1}, dirty: false,
  warnings: [], mounted: null, drag: null, library: [], stack: [], menu: null, revisions: null};
const EXECUTOR_LABELS = {profile: ui('Profil de la bibliothèque'), any: ui('N’importe quelle IA'), connector: ui('Connecteur précis')};
const EXECUTOR_ICONS = {profile: '@', any: '✦', connector: '⚙', method: '⧉'};
const KIND_LABELS = {text: ui('Texte'), context: ui('Contexte'), file: ui('Fichier')};
const IN_NODE = '@entrees', OUT_NODE = '@sorties';
L.views.method = ui('Éditeur de méthode');
const NODE_WIDTH = 240, IO_WIDTH = 200, PORT_Y = 19, PIN_TOP = 44, PIN_H = 22;

function newStep(key, name, position) {
  return {key, kind: 'task', name, description: '', executor: 'any', profile_id: '', connector: '', model: '', instruction: '',
    depends_on: [], artifact: '', helpers: [], receives: 'inputs', inputs: [], attachments: [],
    outputs: [{key: 's1', name: ui('Résultat'), kind: 'text', description: ''}], position};
}
function blankMethod() {
  return {name: ui('Nouvelle méthode'), description: '', category: '', preprompt: '', usage: '', requirements: [],
    inputs: [{key: 'objectif', name: ui('Objectif'), kind: 'text', description: ui('Ce que la méthode doit produire.'), required: true, prepare: ''}],
    outputs: [], layout: {in: {x: -200, y: 120}, out: {x: 420, y: 120}}, steps: [newStep('t1', ui('Tâche 1'), {x: 80, y: 120})]};
}
function methodProfiles() { return (teamsState.profiles || []).filter(p => !p.archived); }
function stepByKey(key) { return methodEditor.draft.steps.find(s => s.key === key); }
function ioNode(key) {
  const m = methodEditor.draft;
  if (key === IN_NODE) return {key, io: true, name: ui('Entrées de la méthode'), position: m.layout.in, inputs: [], outputs: m.inputs};
  if (key === OUT_NODE) return {key, io: true, name: ui('Sorties de la méthode'), position: m.layout.out, inputs: m.outputs, outputs: []};
  return null;
}
function nodeByKey(key) { return ioNode(key) || stepByKey(key); }
function nodeWidth(node) { return node.io ? IO_WIDTH : NODE_WIDTH; }
function nextKey() {
  const used = new Set(methodEditor.draft.steps.map(s => s.key));
  let n = methodEditor.draft.steps.length + 1;
  while (used.has('t' + n)) n++;
  return 't' + n;
}
function slugKey(name, used, fallback) {
  let base = (name || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 32) || fallback;
  let key = base, n = 2;
  while (used.some(p => p.key === key)) key = base + '_' + n++;
  return key;
}
function pinKey(list, prefix) { let n = list.length + 1; while (list.some(p => p.key === prefix + n)) n++; return prefix + n; }
function markDirty() { methodEditor.dirty = true; const flag = $('me-dirty'); if (flag) flag.hidden = false; }

// What a task waits for: its order links and every task wired into its inputs.
function after(step) {
  return [...new Set([...step.depends_on, ...step.inputs.filter(p => p.source && p.source.step !== IN_NODE).map(p => p.source.step)])];
}
function wouldLoop(from, to) {
  // Making "to" wait for "from" loops if "from" already waits, directly or not, for "to".
  const stack = [from], seen = new Set();
  while (stack.length) {
    const key = stack.pop();
    if (key === to) return true;
    if (seen.has(key)) continue;
    seen.add(key);
    const step = stepByKey(key);
    if (step) after(step).forEach(k => stack.push(k));
  }
  return false;
}
function nodeHeight(node) { return PIN_TOP + Math.max(node.inputs.length, node.outputs.length) * PIN_H + (node.io ? 30 : 80); }

// Levels from what each task waits for: a task sits one column right of what it depends on.
function autoLayout() {
  const m = methodEditor.draft, level = {};
  const depth = (s, seen = new Set()) => {
    if (level[s.key] !== undefined) return level[s.key];
    if (seen.has(s.key)) return 0;
    seen.add(s.key);
    const deps = after(s).map(stepByKey).filter(Boolean);
    level[s.key] = deps.length ? 1 + Math.max(...deps.map(d => depth(d, seen))) : 0;
    return level[s.key];
  };
  const bottom = {};
  m.steps.forEach(s => {
    const l = depth(s), y = bottom[l] || 60;
    s.position = {x: 60 + l * 320, y};
    bottom[l] = y + nodeHeight(s) + 40;
  });
  const last = Math.max(0, ...m.steps.map(s => level[s.key] || 0));
  m.layout = {in: {x: -260, y: 60}, out: {x: 60 + (last + 1) * 320, y: 60}};
}
function ensureLayout() {
  const m = methodEditor.draft;
  m.layout = m.layout || {};
  const xs = m.steps.filter(s => s.position).map(s => s.position.x), ys = m.steps.filter(s => s.position).map(s => s.position.y);
  if (!m.layout.in) m.layout.in = {x: Math.min(80, ...xs) - 300, y: Math.min(120, ...ys)};
  if (!m.layout.out) m.layout.out = {x: Math.max(80, ...xs) + 320, y: Math.min(120, ...ys)};
}

// --- rendering -------------------------------------------------------------------------------------------

function nodeWarnings(step) {
  return methodEditor.warnings.filter(w => w.where === 'Tâche « ' + step.name + ' »' && w.level === 'warning');
}
function executorDetail(step) {
  if (step.executor === 'profile') {
    const p = methodProfiles().find(x => x.id === step.profile_id) || (teamsState.profiles || []).find(x => x.id === step.profile_id);
    return p ? (p.icon ? p.icon + ' ' : '') + p.name : ui('profil à choisir');
  }
  if (step.executor === 'connector') return agentName(step.connector) + (step.model ? ' · ' + step.model : '');
  return ui('choisie à l’application');
}
function sourceName(source) {
  if (!source) return '';
  const node = nodeByKey(source.step), port = node?.outputs.find(p => p.key === source.port);
  if (source.step === IN_NODE) return ui('entrée « ') + (port?.name || source.port) + ' »';
  return '« ' + (node?.name || source.step) + ' » › ' + (port?.name || source.port);
}
function outputWired(nodeKey, portKey) {
  const match = p => p.source && p.source.step === nodeKey && p.source.port === portKey;
  return methodEditor.draft.steps.some(s => s.inputs.some(match)) || methodEditor.draft.outputs.some(match);
}
function nodePinHTML(node, port, side) {
  const id = node.key + ':' + port.key, wired = side === 'in' ? !!port.source : outputWired(node.key, port.key);
  const title = KIND_LABELS[port.kind] + ' · ' + port.name + (port.description ? ' — ' + port.description : '') +
    (side === 'in' ? (port.source ? ui('\nReçoit : ') + sourceName(port.source) : ui('\nNon branchée : glissez une sortie ici.')) : ui('\nGlissez vers une entrée pour la transmettre.'));
  return `<span class="me-pin ${side} k-${esc(port.kind)} ${wired ? 'wired' : ''}" data-pin-${side}="${esc(id)}" title="${esc(title)}"><i></i><em>${esc(port.name)}${port.required && node.key === IN_NODE ? ' *' : ''}</em></span>`;
}
function nodePinsHTML(node) {
  const rows = Math.max(node.inputs.length, node.outputs.length);
  let html = '';
  for (let i = 0; i < rows; i++) {
    html += `<div class="me-pin-row">${node.inputs[i] ? nodePinHTML(node, node.inputs[i], 'in') : '<span></span>'}${node.outputs[i] ? nodePinHTML(node, node.outputs[i], 'out') : '<span></span>'}</div>`;
  }
  return rows ? `<div class="me-pins">${html}</div>` : '';
}
function orderPins(key) {
  return ui`<span class="me-port in" data-port-in="${esc(key)}" title="Ordre : cette tâche attend celles branchées ici"></span>
    <span class="me-port out" data-port-out="${esc(key)}" title="Ordre : glissez vers une tâche qui doit attendre celle-ci"></span>`;
}
function nodeHTML(step) {
  const selected = methodEditor.selected === step.key ? 'selected' : '', warnings = nodeWarnings(step);
  const warn = warnings.length ? `<span class="me-warn" title="${esc(warnings.map(w => w.message).join('\n'))}">⚠ ${warnings.length}</span>` : '';
  if (step.kind === 'method') {
    const sub = methodEditor.library.find(m => m.id === step.method_id);
    return ui`<div class="me-node kind-method ${selected}" data-node="${esc(step.key)}">${orderPins(step.key)}
      <div class="me-node-head" data-node-drag="${esc(step.key)}"><span class="me-exec">${EXECUTOR_ICONS.method}</span><b>${esc(step.name)}</b>${warn}</div>
      ${nodePinsHTML(step)}
      <div class="me-node-body"><small>Sous-méthode${sub ? ' · ' + sub.steps.length + ui(' tâche(s)') : ' absente'}</small><p>${esc(sub?.description || ui('Double-cliquez pour l’ouvrir.')).slice(0, 140)}</p></div></div>`;
  }
  const roots = !after(step).length;
  return `<div class="me-node exec-${esc(step.executor)} ${selected}" data-node="${esc(step.key)}">${orderPins(step.key)}
    <div class="me-node-head" data-node-drag="${esc(step.key)}"><span class="me-exec">${EXECUTOR_ICONS[step.executor]}</span><b>${esc(step.name)}</b>${warn}</div>
    ${nodePinsHTML(step)}
    <div class="me-node-body"><small>${esc(EXECUTOR_LABELS[step.executor])} · ${esc(executorDetail(step))}</small>
      <p>${esc(step.instruction || ui('Aucune consigne — cliquez pour l’écrire.')).slice(0, 140)}</p>
      <div class="me-tags">${roots ? ui('<span>▶ départ</span>') : ''}<span title="${step.receives === 'inputs' ? ui('Ne reçoit que ses entrées branchées') : ui('Reçoit toute la conversation de la chaîne')}">${step.receives === 'inputs' ? ui('🔒 entrées seules') : ui('💬 toute la chaîne')}</span>${step.artifact ? ui`<span title="Fichier attendu">📄 ${esc(step.artifact)}</span>` : ''}${step.helpers.length ? ui`<span title="Agents appelables pendant la tâche">＋${step.helpers.length} agent(s)</span>` : ''}</div></div>
  </div>`;
}
function ioHTML(key) {
  const node = ioNode(key), selected = methodEditor.selected === key ? 'selected' : '';
  const hint = key === IN_NODE ? (node.outputs.length > 1 ? ui('Donné en appliquant la méthode.') : ui('Clic droit : ajouter un contexte, un fichier…'))
    : (node.inputs.length ? ui('Ce que la méthode rend.') : ui('Déposez ici un fil de sortie.'));
  return `<div class="me-node me-io ${key === IN_NODE ? 'io-in' : 'io-out'} ${selected}" data-node="${esc(key)}">
    <div class="me-node-head" data-node-drag="${esc(key)}"><span class="me-exec">${key === IN_NODE ? '▶' : '■'}</span><b>${esc(node.name)}</b></div>
    ${nodePinsHTML(node)}<div class="me-node-body"><small>${esc(hint)}</small></div></div>`;
}
function pinPoint(nodeKey, portKey, side) {
  const node = nodeByKey(nodeKey);
  if (!node || !node.position) return null;
  const i = (side === 'in' ? node.inputs : node.outputs).findIndex(p => p.key === portKey);
  if (i < 0) return null;
  return {x: node.position.x + (side === 'in' ? 0 : nodeWidth(node)), y: node.position.y + PIN_TOP + i * PIN_H + PIN_H / 2};
}
// Forward wires bend gently; a wire going back loops wide instead of cutting through the nodes.
function curve(x1, y1, x2, y2) {
  const dx = x2 >= x1 + 40 ? Math.max(50, (x2 - x1) / 2) : Math.max(110, Math.abs(y2 - y1) / 2, (x1 - x2) / 2 + 70);
  return `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
}
function sinks() {
  const list = [];
  methodEditor.draft.steps.forEach(s => s.inputs.forEach(p => list.push([s.key, p])));
  methodEditor.draft.outputs.forEach(p => list.push([OUT_NODE, p]));
  return list;
}
function edgesSVG() {
  const paths = [];
  for (const step of methodEditor.draft.steps) for (const key of step.depends_on) {
    const from = stepByKey(key);
    if (!from) continue;
    const id = 'o:' + key + '>' + step.key, d = curve(from.position.x + NODE_WIDTH, from.position.y + PORT_Y, step.position.x, step.position.y + PORT_Y);
    paths.push(`<path class="me-edge-hit" data-edge="${esc(id)}" d="${d}"></path><path class="me-edge order ${methodEditor.edge === id ? 'selected' : ''}" d="${d}"></path>`);
  }
  for (const [nodeKey, port] of sinks()) {
    if (!port.source) continue;
    const a = pinPoint(port.source.step, port.source.port, 'out'), b = pinPoint(nodeKey, port.key, 'in');
    if (!a || !b) continue;
    const id = 'd:' + nodeKey + ':' + port.key, d = curve(a.x, a.y, b.x, b.y);
    const kind = nodeByKey(port.source.step)?.outputs.find(p => p.key === port.source.port)?.kind || port.kind;
    paths.push(`<path class="me-edge-hit" data-edge="${esc(id)}" d="${d}"></path><path class="me-edge data k-${esc(kind)} ${methodEditor.edge === id ? 'selected' : ''}" d="${d}"></path>`);
  }
  return paths.join('') + '<path id="me-wire" class="me-edge pending" d=""></path>';
}
function renderGraph() {
  const world = $('me-world');
  if (!world) return;
  const {x, y, z} = methodEditor.view;
  world.style.transform = `translate(${x}px,${y}px) scale(${z})`;
  $('me-canvas').style.backgroundPosition = `${x}px ${y}px`;
  $('me-canvas').style.backgroundSize = `${24 * z}px ${24 * z}px`;
  $('me-nodes').innerHTML = ioHTML(IN_NODE) + methodEditor.draft.steps.map(nodeHTML).join('') + ioHTML(OUT_NODE);
  placeNodes();
  $('me-edges').innerHTML = edgesSVG();
}
// Positions go through the DOM: the page's security policy ignores inline style attributes.
function placeNodes() {
  document.querySelectorAll('#me-nodes [data-node]').forEach(el => {
    const node = nodeByKey(el.dataset.node);
    if (node?.position) { el.style.left = node.position.x + 'px'; el.style.top = node.position.y + 'px'; }
  });
}
function renderEdgesOnly() { const svg = $('me-edges'); if (svg) svg.innerHTML = edgesSVG(); }
function redraw() { markDirty(); renderGraph(); renderInspectorPanel(); }

// --- inspector ---------------------------------------------------------------------------------------------------

function kindSelect(scope, index, kind, locked) {
  return `<select data-me-pin="${scope}:${index}" data-me-pin-field="kind" ${locked ? 'disabled' : ''} aria-label="Type">${Object.entries(KIND_LABELS).map(([k, v]) => `<option value="${k}" ${kind === k ? 'selected' : ''}>${v}</option>`).join('')}</select>`;
}
function sourceLine(scope, index, port) {
  return `<div class="me-source">${port.source ? ui`← ${esc(sourceName(port.source))} <button type="button" class="text-button" data-me-unwire="${scope}:${index}">débrancher</button>` : ui('<span class="muted">non branchée</span>')}</div>`;
}
function portsEditor(scope, list, options = {}) {
  const rows = list.map((p, i) => {
    const locked = options.locked || (scope === 'min' && p.key === 'objectif');
    return ui`<div class="me-port-item"><div class="me-port-row"><span class="me-kind k-${esc(p.kind)}"></span>
        <input data-me-pin="${scope}:${i}" data-me-pin-field="name" value="${esc(p.name)}" maxlength="80" ${options.locked ? 'disabled' : ''} aria-label="Nom">
        ${kindSelect(scope, i, p.kind, locked)}
        ${locked ? '<span></span>' : ui`<button type="button" class="text-button danger" data-me-pin-remove="${scope}:${i}" aria-label="Retirer">✕</button>`}</div>
      <div class="me-port-extra">
        ${options.sources ? sourceLine(scope, i, p) : ''}
        ${scope === 'outputs' && p.kind === 'file' ? ui`<input data-me-pin="${scope}:${i}" data-me-pin-field="path" value="${esc(p.path || '')}" maxlength="400" placeholder="Chemin dans le projet : modele/vaisseau.blend">` : ''}
        ${options.locked ? '' : `<input data-me-pin="${scope}:${i}" data-me-pin-field="description" value="${esc(p.description || '')}" maxlength="1000" placeholder="${scope === 'min' ? ui('Ce que c’est') : scope === 'outputs' ? ui('Ce que la tâche doit y mettre') : ui('Description (facultative)')}">`}
        ${scope === 'min' ? ui`${p.key === 'objectif' ? '' : ui`<label class="me-check"><input type="checkbox" data-me-pin="${scope}:${i}" data-me-pin-field="required" ${p.required ? 'checked' : ''}> requise pour appliquer</label>`}
          <textarea data-me-pin="${scope}:${i}" data-me-pin-field="prepare" rows="2" maxlength="2000" placeholder="Comment la préparer : lu par l’IA ou la personne qui applique la méthode">${esc(p.prepare || '')}</textarea>` : ''}
      </div></div>`;
  }).join('');
  return `<div class="me-port-list">${rows || ui('<small class="muted">Aucune.</small>')}</div>`;
}
function helpersHTML(step, profiles) {
  const list = profiles.filter(p => p.id !== step.profile_id);
  return ui`<div class="me-helpers"><b class="me-label">Agents appelables pendant la tâche (6 au plus)</b>
    <div class="me-helper-list">${list.map(p => `<label><input type="checkbox" data-me-helper="${esc(p.id)}" ${step.helpers.includes(p.id) ? 'checked' : ''}> ${p.icon ? esc(p.icon) + ' ' : ''}${esc(p.name)}</label>`).join('') || ui('<small class="muted">Aucun autre profil actif.</small>')}</div></div>`;
}
function dependsHTML(step) {
  const others = methodEditor.draft.steps.filter(s => s.key !== step.key && !step.depends_on.includes(s.key) && !wouldLoop(s.key, step.key));
  return ui`<div><b class="me-label">Attend aussi (ordre, sans rien recevoir)</b><div class="me-deps">${step.depends_on.map(k => ui`<span class="team-chip">${esc(stepByKey(k)?.name || k)} <button type="button" class="text-button" data-me-undepend="${esc(k)}" aria-label="Retirer">✕</button></span>`).join('') || ui('<small class="muted">Rien d’autre que ses entrées.</small>')}</div>
    ${others.length ? ui`<select data-me-depend><option value="">＋ Attendre une tâche…</option>${others.map(s => `<option value="${esc(s.key)}">${esc(s.name)}</option>`).join('')}</select>` : ''}</div>`;
}
function taskInspectorHTML(step) {
  const profiles = methodProfiles(), connectors = state.data?.connectors || [];
  return ui`<div class="me-inspector-head"><span class="me-exec">${EXECUTOR_ICONS[step.executor]}</span><h3>Tâche</h3><button type="button" class="text-button" data-me-select="">Méthode ↩</button></div>
    <div class="fields">
      <label>Nom<input data-me-field="name" value="${esc(step.name)}" maxlength="120"></label>
      <label>Description<textarea data-me-field="description" rows="2" maxlength="1000" placeholder="À quoi sert cette tâche : lu par vous et par l’IA qui applique la méthode.">${esc(step.description || '')}</textarea></label>
      <label>Exécutant<select data-me-field="executor">${Object.entries(EXECUTOR_LABELS).map(([k, v]) => `<option value="${k}" ${step.executor === k ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
      ${step.executor === 'profile' ? ui`<label>Profil<select data-me-field="profile_id"><option value="">Choisir…</option>${profiles.map(p => `<option value="${esc(p.id)}" ${p.id === step.profile_id ? 'selected' : ''}>${p.icon ? esc(p.icon) + ' ' : ''}${esc(p.name)} · ${esc(agentName(p.connector))}</option>`).join('')}</select><small class="field-help">Ses consignes, son connecteur et son modèle tiennent la tâche.</small></label>` : ''}
      ${step.executor === 'connector' ? ui`<div class="two-fields"><label>Connecteur<select data-me-field="connector">${connectors.map(c => `<option value="${esc(c.id)}" ${c.id === step.connector ? 'selected' : ''}>${esc(agentName(c.id))}${c.enabled ? '' : ui(' · désactivé')}</option>`).join('')}</select></label><label>Modèle<input data-me-field="model" value="${esc(step.model || '')}" list="me-models" placeholder="par défaut"><datalist id="me-models">${(state.data?.models_cache?.[step.connector] || []).map(m => `<option value="${esc(m.id || m)}">`).join('')}</datalist></label></div>` : ''}
      ${step.executor === 'any' ? ui('<p class="field-help">L’IA et le modèle seront choisis au moment d’appliquer la méthode : elle reste utilisable par n’importe qui.</p>') : ''}
      <div class="me-field"><div class="me-field-head"><span>Consigne${step.attachments?.length ? ' · 📎 ' + step.attachments.length : ''}</span><button type="button" class="text-button" data-mw-open="step">⤢ Ouvrir en grand, avec l’assistant</button></div>
        <textarea data-me-field="instruction" rows="9">${esc(step.instruction)}</textarea><small class="field-help"><code>{objectif}</code> est remplacé par l’objectif donné en appliquant la méthode. Les entrées branchées sont ajoutées après la consigne ; les fichiers joints s’ajoutent en grand.</small></div>
      <label>Ce que reçoit la tâche<select data-me-field="receives"><option value="inputs" ${step.receives === 'inputs' ? 'selected' : ''}>Ses entrées branchées seulement (recommandé)</option><option value="chain" ${step.receives === 'chain' ? 'selected' : ''}>Toute la conversation de la chaîne</option></select></label>
      <div class="me-section"><b class="me-label">Entrées</b>${portsEditor('inputs', step.inputs, {sources: true})}<button type="button" class="secondary" data-me-pin-add="inputs">＋ Entrée</button></div>
      <div class="me-section"><b class="me-label">Sorties</b>${portsEditor('outputs', step.outputs)}<button type="button" class="secondary" data-me-pin-add="outputs">＋ Sortie</button>
        <small class="field-help">Avec plusieurs sorties texte, la tâche les rédige sous « ### Sortie : nom » et chaque entrée branchée ne reçoit que la sienne. Une sortie fichier est vérifiée à la fin de la tâche.</small></div>
      ${step.artifact ? ui`<label>Fichier attendu (ancien format)<input data-me-field="artifact" value="${esc(step.artifact)}" maxlength="400"></label>` : ''}
      ${helpersHTML(step, profiles)}
      ${typeof labStepHTML === 'function' ? labStepHTML(step) : ''}
      ${dependsHTML(step)}
      ${nodeWarnings(step).map(w => `<p class="me-warning">⚠ ${esc(w.message)}</p>`).join('')}
      <div class="row-actions"><button type="button" class="secondary" data-me-duplicate="${esc(step.key)}">Dupliquer</button><button type="button" class="text-button danger" data-me-delete="${esc(step.key)}">Supprimer la tâche</button></div>
    </div>`;
}
function methodNodeInspectorHTML(step) {
  const choices = methodEditor.library.filter(m => m.id !== methodEditor.id);
  const sub = methodEditor.library.find(m => m.id === step.method_id);
  return ui`<div class="me-inspector-head"><span class="me-exec">${EXECUTOR_ICONS.method}</span><h3>Sous-méthode</h3><button type="button" class="text-button" data-me-select="">Méthode ↩</button></div>
    <div class="fields">
      <label>Nom du nœud<input data-me-field="name" value="${esc(step.name)}" maxlength="120"></label>
      <label>Méthode appelée<select data-me-field="method_id">${choices.map(m => `<option value="${esc(m.id)}" ${m.id === step.method_id ? 'selected' : ''}>${esc(m.name)}</option>`).join('')}</select></label>
      ${sub ? `<p class="field-help">${esc(sub.description || ui('Sans description.'))}${sub.usage ? ui('<br><b>Mode d’emploi :</b> ') + esc(sub.usage) : ''}</p>` : ui('<p class="me-warning">⚠ Méthode absente de la bibliothèque.</p>')}
      <button type="button" class="secondary" data-me-open-sub="${esc(step.method_id)}">Ouvrir la sous-méthode</button>
      <div class="me-section"><b class="me-label">Ses entrées</b>${portsEditor('inputs', step.inputs, {sources: true, locked: true})}</div>
      <div class="me-section"><b class="me-label">Ses sorties</b>${step.outputs.map(p => `<div class="me-source"><span class="me-kind k-${esc(p.kind)}"></span> ${esc(p.name)}</div>`).join('') || ui('<small class="muted">Elle ne déclare aucune sortie.</small>')}</div>
      ${dependsHTML(step)}
      ${nodeWarnings(step).map(w => `<p class="me-warning">⚠ ${esc(w.message)}</p>`).join('')}
      <div class="row-actions"><button type="button" class="secondary" data-me-duplicate="${esc(step.key)}">Dupliquer</button><button type="button" class="text-button danger" data-me-delete="${esc(step.key)}">Retirer du graphe</button></div>
    </div>`;
}
function ioInspectorHTML(key) {
  const m = methodEditor.draft;
  if (key === IN_NODE) return ui`<div class="me-inspector-head"><span class="me-exec">▶</span><h3>Entrées de la méthode</h3><button type="button" class="text-button" data-me-select="">Méthode ↩</button></div>
    <div class="fields"><p class="field-help">Ce qu’on donne en appliquant la méthode. Un contexte peut exister en plusieurs versions — complet, simplifié, spécial : branchez chacune aux tâches qui en ont besoin. Une tâche sans fil n’en reçoit aucune.</p>
      ${portsEditor('min', m.inputs)}
      <div class="row-actions"><button type="button" class="secondary" data-me-pin-add="min" data-kind="context">＋ Contexte</button><button type="button" class="secondary" data-me-pin-add="min" data-kind="text">＋ Texte</button><button type="button" class="secondary" data-me-pin-add="min" data-kind="file">＋ Fichier</button></div></div>`;
  return ui`<div class="me-inspector-head"><span class="me-exec">■</span><h3>Sorties de la méthode</h3><button type="button" class="text-button" data-me-select="">Méthode ↩</button></div>
    <div class="fields"><p class="field-help">Ce que la méthode rend. Utilisée comme sous-méthode, ce sont les sorties de son nœud ; en test, ce qui est évalué.</p>
      ${portsEditor('mout', m.outputs, {sources: true})}
      <button type="button" class="secondary" data-me-pin-add="mout">＋ Sortie</button></div>`;
}
function methodInspectorHTML() {
  const m = methodEditor.draft, revisions = methodEditor.revisions;
  return ui`<div class="me-inspector-head"><h3>Méthode</h3></div>
    <div class="fields">
      <div class="me-field"><div class="me-field-head"><span>Description</span><button type="button" class="text-button" data-mw-open="description">⤢ En grand</button></div><textarea data-me-method="description" rows="3" maxlength="4000" placeholder="Ce que fait la méthode, en quelques lignes.">${esc(m.description)}</textarea></div>
      <div class="me-field"><div class="me-field-head"><span>Mode d’emploi</span><button type="button" class="text-button" data-mw-open="usage">⤢ En grand</button></div><textarea data-me-method="usage" rows="5" maxlength="8000" placeholder="Pour l’IA ou la personne qui applique la méthode : quand l’utiliser, comment préparer ses contextes, ce qu’il faut vérifier avant.">${esc(m.usage || '')}</textarea></div>
      <div class="me-field"><div class="me-field-head"><span>Prompt de base</span><button type="button" class="text-button" data-mw-open="preprompt">⤢ En grand</button></div><textarea data-me-method="preprompt" rows="6" maxlength="20000" placeholder="Le cadre commun : style, conventions, ce que chaque tâche doit respecter.">${esc(m.preprompt)}</textarea><small class="field-help">Placé devant la consigne de chaque tâche de cette méthode ; <code>{objectif}</code> y est aussi remplacé.</small></div>
      <label class="me-check me-option"><input type="checkbox" data-me-option="proposals" ${m.options?.proposals ? 'checked' : ''}> Inviter les agents à proposer des améliorations</label>
      <small class="field-help">Chaque tâche pourra finir sa réponse par une section « Proposition d’amélioration », jamais transmise à la suite de la chaîne. Vous les lisez dans « Tests & affinage ». Quelques lignes de plus dans chaque consigne.</small>
      <div class="me-section"><b class="me-label">Entrées et sorties</b><div class="row-actions"><button type="button" class="secondary" data-me-select="${IN_NODE}">Entrées (${m.inputs.length})</button><button type="button" class="secondary" data-me-select="${OUT_NODE}">Sorties (${m.outputs.length})</button></div></div>
      <div class="me-section"><b class="me-label">Prérequis sur la machine</b><p class="field-help">Ce qu’il faut pour que la méthode tourne ailleurs. Un prérequis manquant donne un avertissement, jamais un refus.</p>
        ${m.requirements.map((r, i) => ui`<div class="me-requirement"><select data-me-req="${i}" data-me-req-field="kind">${[['software', ui('Logiciel')], ['plugin', 'Plugin'], ['connector', ui('Connecteur')], ['note', ui('À vérifier')]].map(([k, v]) => `<option value="${k}" ${r.kind === k ? 'selected' : ''}>${v}</option>`).join('')}</select><input data-me-req="${i}" data-me-req-field="name" value="${esc(r.name)}" placeholder="Blender" maxlength="120"><input data-me-req="${i}" data-me-req-field="executable" value="${esc(r.executable || '')}" placeholder="${r.kind === 'software' ? 'blender ou C:\\…\\blender.exe' : r.kind === 'note' ? '' : 'identifiant'}" maxlength="400" ${r.kind === 'note' ? 'hidden' : ''}><button type="button" class="text-button danger" data-me-req-remove="${i}" aria-label="Retirer">✕</button></div>`).join('')}
        <button type="button" class="secondary" data-me-req-add>＋ Prérequis</button></div>
      <div class="me-section"><b class="me-label">Agents qui la préfèrent ou doivent l’utiliser</b>${!methodEditor.id ? ui('<small class="muted">Enregistrez la méthode pour la lier à des agents.</small>')
        : (methodEditor.agents || []).map(a => `<div class="pm-row"><div class="pm-head"><div><b>${a.icon ? esc(a.icon) + ' ' : ''}${esc(a.name)}</b>${a.archived ? ui('<small>archivé</small>') : ''}</div>${modeSelect(a.mode, a.profile_id + ':' + methodEditor.id)}</div>${noteBlock('method', a.note, a.note_author, a.note_updated_at, a.profile_id + ':' + methodEditor.id)}</div>`).join('')
          + ui`<select data-ma-add><option value="">＋ Lier à un agent…</option>${methodProfiles().filter(p => !(methodEditor.agents || []).some(a => a.profile_id === p.id)).map(p => `<option value="${esc(p.id)}">${p.icon ? esc(p.icon) + ' ' : ''}${esc(p.name)}</option>`).join('')}</select>`}</div>
      <div class="me-section"><b class="me-label">Versions</b>${!methodEditor.id ? ui('<small class="muted">Enregistrez la méthode pour garder ses versions.</small>')
        : revisions ? (revisions.map(r => `<div class="me-revision"><span>v${r.revision} · ${esc(r.source === 'user' ? ui('vous') : r.source === 'restore' ? ui('retour') : r.source)}${r.note ? ' · ' + esc(r.note) : ''}<small>${esc(new Date(r.created_at).toLocaleString(CYAI_FORMAT_LOCALE))}</small></span>${r.revision === revisions[0].revision ? '<small class="muted">actuelle</small>' : ui`<button type="button" class="text-button" data-me-restore="${r.revision}">Rétablir</button>`}</div>`).join('') || ui('<small class="muted">Aucune.</small>'))
        : ui('<button type="button" class="secondary" data-me-history>Voir les versions</button>')}</div>
      <p class="field-help">${m.steps.length} nœud(s). <b>Clic droit</b> sur le fond : ajouter une tâche, une sous-méthode, une entrée. Glissez d’une sortie vers une entrée pour brancher ; déposer un fil sur une tâche lui crée l’entrée. Les points de l’en-tête règlent l’ordre seul. Suppr retire ce qui est sélectionné. Une IA peut aussi créer et modifier cette méthode par le MCP CyAI (<code>method_save</code>), avec votre autorisation.</p>
    </div>`;
}
function renderInspectorPanel() {
  const panel = $('me-inspector');
  if (!panel) return;
  const key = methodEditor.selected, step = key && stepByKey(key);
  panel.innerHTML = key === IN_NODE || key === OUT_NODE ? ioInspectorHTML(key) : step ? (step.kind === 'method' ? methodNodeInspectorHTML(step) : taskInspectorHTML(step)) : methodInspectorHTML();
}
async function loadMethodAgents() {
  if (!methodEditor.id) return;
  methodEditor.agents = (await action('method_agents', {id: methodEditor.id})).agents;
  if (!methodEditor.selected) renderInspectorPanel();
}
function renderWarnings() {
  const box = $('me-warnings');
  if (!box) return;
  const list = methodEditor.warnings, m = methodEditor.draft;
  box.innerHTML = !methodEditor.id ? ui('<span class="muted">Enregistrez la méthode pour la vérifier sur cette machine.</span>')
    : list.length ? list.map(w => {
      const program = w.level === 'warning' && /^Prérequis « (.+) »$/.exec(w.where) && m?.requirements.find(r => r.kind === 'software' && 'Prérequis « ' + r.name + ' »' === w.where);
      return `<span class="me-w ${esc(w.level)}">${w.level === 'warning' ? '⚠' : 'ℹ'} <b>${esc(w.where)}</b> : ${esc(w.message)}${program ? ui` <button type="button" class="text-button" data-software-path="${esc(program.name)}">Indiquer le chemin…</button>` : ''}</span>`;
    }).join('')
    : ui('<span class="me-w ok">✓ Rien ne manque sur cette machine.</span>');
}

async function renderMethodEditor() {
  if (!teamsState.profiles) teamsState.profiles = (await action('agent_profile_list')).profiles;
  if (state.view !== 'method') return;
  if ($('me-canvas') && methodEditor.mounted === methodEditor.id + ':' + methodEditor.draft.name) return;
  $('page-title').textContent = ui('Éditeur de méthode');
  const m = methodEditor.draft, parent = methodEditor.stack[methodEditor.stack.length - 1];
  $('page').innerHTML = ui`<div class="method-editor">
    <header class="me-toolbar">
      <button type="button" class="secondary" data-me-close>← ${esc(parent ? parent.name : ui('Bibliothèque'))}</button>
      <input id="me-name" data-me-method="name" value="${esc(m.name)}" maxlength="120" aria-label="Nom de la méthode">
      <input id="me-category" data-me-method="category" value="${esc(m.category || '')}" maxlength="60" placeholder="Catégorie" aria-label="Catégorie">
      <span id="me-dirty" class="me-dirty" ${methodEditor.dirty ? '' : 'hidden'}>● modifications non enregistrées</span>
      <span class="me-spacer"></span>
      <button type="button" class="secondary" data-me-add>＋ Tâche</button>
      <button type="button" class="secondary" data-me-layout title="Ranger les nœuds selon ce qu’ils attendent">Ranger</button>
      <button type="button" class="secondary" data-me-fit title="Tout afficher">Cadrer</button>
      <button type="button" class="secondary" data-lab-open title="Tests enregistrés avec la méthode, notes, amélioration par une IA, boucle d’affinage, propositions des agents">🧪 Tests & affinage${methodEditor.proposalsNew ? ui` <span class="lab-count" title="Propositions d’amélioration à lire">${methodEditor.proposalsNew}</span>` : ''}</button>
      <button type="button" class="secondary" data-me-export>Exporter</button>
      <button type="button" class="secondary" data-me-apply>Appliquer…</button>
      <button type="button" class="primary" data-me-save>Enregistrer</button>
    </header>
    <div class="me-body">
      <div id="me-canvas" class="me-canvas" tabindex="0"><div id="me-world" class="me-world"><svg class="me-edges" width="20000" height="20000" viewBox="-10000 -10000 20000 20000"><g id="me-edges"></g></svg><div id="me-nodes"></div></div>
        <div id="me-menu" class="me-menu" hidden></div>
        <div class="me-zoom"><button type="button" class="icon" data-me-zoom="1.2" aria-label="Zoomer">＋</button><button type="button" class="icon" data-me-zoom="0.83" aria-label="Dézoomer">－</button></div></div>
      <aside id="me-inspector" class="me-inspector"></aside>
    </div>
    <footer id="me-warnings" class="me-warnings"></footer>
  </div>`;
  methodEditor.mounted = methodEditor.id + ':' + m.name;
  renderGraph(); renderInspectorPanel(); renderWarnings();
}

function draftFrom(m) {
  return {name: m.name, description: m.description || '', category: m.category || '', preprompt: m.preprompt || '', usage: m.usage || '',
    requirements: (m.requirements || []).map(x => ({...x})),
    inputs: (m.inputs || []).map(p => ({...p})), outputs: (m.outputs || []).map(p => ({...p, source: p.source ? {...p.source} : null})),
    layout: {...(m.layout || {})}, options: {...(m.options || {})},
    steps: m.steps.map(s => ({key: s.key, kind: s.kind || 'task', name: s.name, description: s.description || '', executor: s.executor,
      profile_id: s.profile_id || '', connector: s.connector || '', model: s.model || '', instruction: s.instruction || '',
      depends_on: [...s.depends_on], artifact: s.artifact || '', helpers: [...(s.helpers || [])], receives: s.receives || 'chain',
      method_id: s.method_id || '', attachments: [...(s.attachments || [])], adaptations: {...(s.adaptations || {})}, inputs: (s.inputs || []).map(p => ({...p, source: p.source ? {...p.source} : null})),
      outputs: (s.outputs || []).map(p => ({...p})), position: s.position ? {...s.position} : null}))};
}
async function openMethodGraph(id, keepStack = false) {
  if (!teamsState.profiles || !teamsState.profiles.length) teamsState.profiles = (await action('agent_profile_list')).profiles;
  methodEditor.library = (await action('method_list')).methods;
  if (!keepStack) methodEditor.stack = [];
  if (typeof writer !== 'undefined') { writer.open = false; clearInterval(writer.timer); writer.mission = null; }
  if (typeof lab !== 'undefined') { lab.open = false; clearInterval(lab.timer); lab.tests = []; lab.runs = []; lab.checks = []; lab.selected = null; }
  methodEditor.workshop = ''; methodEditor.agents = []; methodEditor.proposalsNew = 0;
  if (id) {
    const m = (await action('method_get', {id})).method;
    methodEditor.workshop = m.workshop || '';
    methodEditor.proposalsNew = m.proposals_new || 0;
    methodEditor.agents = (await action('method_agents', {id})).agents;
    if (typeof loadChecks === 'function') { methodEditor.id = id; await loadChecks(); }
    methodEditor.draft = draftFrom(m);
    methodEditor.warnings = m.warnings || [];
    if (methodEditor.draft.steps.some(s => !s.position)) autoLayout();
    ensureLayout();
  } else {
    methodEditor.draft = blankMethod();
    methodEditor.warnings = [];
  }
  methodEditor.id = id || null;
  methodEditor.selected = null; methodEditor.edge = null; methodEditor.dirty = false; methodEditor.mounted = null;
  methodEditor.menu = null; methodEditor.revisions = null;
  methodEditor.view = {x: 40, y: 40, z: 1};
  showView('method');
  setTimeout(fitView, 0);
}

function payload() {
  const m = methodEditor.draft;
  return {...(methodEditor.id ? {id: methodEditor.id} : {}), name: m.name, description: m.description, category: m.category,
    preprompt: m.preprompt, usage: m.usage, requirements: m.requirements.filter(r => r.name.trim()), layout: m.layout, options: m.options || {},
    inputs: m.inputs.map(p => ({key: p.key, name: p.name, kind: p.kind, description: p.description || '', required: !!p.required, prepare: p.prepare || ''})),
    outputs: m.outputs.map(p => ({key: p.key, name: p.name, kind: p.kind, description: p.description || '', source: p.source})),
    steps: m.steps.map(s => s.kind === 'method'
      ? {key: s.key, kind: 'method', name: s.name, description: s.description, method_id: s.method_id,
        inputs: s.inputs.map(p => ({key: p.key, source: p.source})), depends_on: s.depends_on, position: s.position}
      : {key: s.key, kind: 'task', name: s.name, description: s.description, executor: s.executor, profile_id: s.profile_id,
        connector: s.connector, model: s.model, instruction: s.instruction, depends_on: s.depends_on, artifact: s.artifact,
        helpers: s.helpers, receives: s.receives, position: s.position, attachments: s.attachments || [], adaptations: s.adaptations || {},
        inputs: s.inputs.map(p => ({key: p.key, name: p.name, kind: p.kind, description: p.description || '', source: p.source})),
        outputs: s.outputs.map(p => ({key: p.key, name: p.name, kind: p.kind, description: p.description || '', ...(p.kind === 'file' ? {path: p.path || ''} : {})}))})};
}
async function saveMethodGraph() {
  const r = await action('method_save', payload());
  methodEditor.id = r.id; methodEditor.dirty = false; methodEditor.warnings = r.warnings || []; methodEditor.revisions = null;
  methodEditor.library = (await action('method_list')).methods;
  methodEditor.mounted = methodEditor.id + ':' + methodEditor.draft.name;
  $('me-dirty').hidden = true;
  renderGraph(); renderInspectorPanel(); renderWarnings();
  toast(r.notice);
  return r;
}
function fitView() {
  const canvas = $('me-canvas'), m = methodEditor.draft;
  if (!canvas) return;
  const nodes = [...m.steps, ioNode(IN_NODE), ioNode(OUT_NODE)].filter(n => n.position);
  const xs = nodes.map(n => n.position.x), ys = nodes.map(n => n.position.y);
  const width = Math.max(...nodes.map(n => n.position.x + nodeWidth(n))) - Math.min(...xs);
  const height = Math.max(...nodes.map(n => n.position.y + nodeHeight(n))) - Math.min(...ys);
  const z = Math.max(0.35, Math.min(1.1, Math.min((canvas.clientWidth - 80) / width, (canvas.clientHeight - 80) / height)));
  methodEditor.view = {z, x: 40 - Math.min(...xs) * z, y: 40 - Math.min(...ys) * z};
  renderGraph();
}
function addTask(position, wireFrom) {
  const key = nextKey(), previous = !wireFrom && methodEditor.selected && stepByKey(methodEditor.selected);
  const step = newStep(key, ui('Tâche ') + key.slice(1),
    position || (previous ? {x: previous.position.x + 320, y: previous.position.y} : {x: 80, y: 80 + methodEditor.draft.steps.length * 40}));
  const source = wireFrom || (previous && previous.kind === 'task' && previous.outputs[0] ? {step: previous.key, port: previous.outputs[0].key} : null);
  if (source) {
    const port = nodeByKey(source.step)?.outputs.find(p => p.key === source.port);
    step.inputs.push({key: 'e1', name: port?.name || ui('Entrée'), kind: port?.kind || 'text', description: '', source: {...source}});
  }
  methodEditor.draft.steps.push(step);
  methodEditor.selected = key; redraw();
}
function addSubMethod(id, position) {
  const sub = methodEditor.library.find(m => m.id === id);
  if (!sub) return;
  const key = nextKey();
  methodEditor.draft.steps.push({key, kind: 'method', name: sub.name, description: '', executor: 'any', profile_id: '', connector: '', model: '',
    instruction: '', depends_on: [], artifact: '', helpers: [], receives: 'inputs', method_id: id,
    inputs: sub.inputs.map(p => ({key: p.key, name: p.name, kind: p.kind, description: p.description, required: p.required, source: null})),
    outputs: sub.outputs.map(p => ({key: p.key, name: p.name, kind: p.kind, description: p.description || ''})),
    position: position || {x: 80, y: 80 + methodEditor.draft.steps.length * 40}});
  methodEditor.selected = key; redraw();
}
function unwireFrom(stepKey) {
  sinks().forEach(([, p]) => { if (p.source && p.source.step === stepKey) p.source = null; });
}
function removeTask(key) {
  methodEditor.draft.steps = methodEditor.draft.steps.filter(s => s.key !== key);
  methodEditor.draft.steps.forEach(s => { s.depends_on = s.depends_on.filter(k => k !== key); });
  unwireFrom(key);
  if (methodEditor.selected === key) methodEditor.selected = null;
  redraw();
}
function worldPoint(event) {
  const rect = $('me-canvas').getBoundingClientRect(), {x, y, z} = methodEditor.view;
  return {x: (event.clientX - rect.left - x) / z, y: (event.clientY - rect.top - y) / z};
}
function leaveMethodEditor(then) {
  if (!methodEditor.dirty) { then(); return; }
  openDialog(ui('Modifications non enregistrées'), ui('<p>Les modifications de cette méthode seront perdues.</p>'), async () => {
    methodEditor.dirty = false; setTimeout(then, 0);
  }, ui('Quitter sans enregistrer'));
}
function closeMethodEditor() {
  const parent = methodEditor.stack.pop();
  if (parent) { leaveMethodEditor(() => openMethodGraph(parent.id, true)); return; }
  leaveMethodEditor(() => { teamsState.libraryFilter = 'methods'; $('page')._rendered = null; showView('agents'); });
}
function openSubMethod(id) {
  if (!id) return;
  const here = {id: methodEditor.id, name: methodEditor.draft.name};
  leaveMethodEditor(() => { if (here.id) methodEditor.stack.push(here); openMethodGraph(id, true); });
}

// --- wires ------------------------------------------------------------------------------------------------------

function parsePin(value) { const i = value.lastIndexOf(':'); return {node: value.slice(0, i), port: value.slice(i + 1)}; }
function sinkPort(node, port) { return nodeByKey(node)?.inputs.find(p => p.key === port); }
function connect(source, target) {
  if (target.node === IN_NODE) return;
  if (target.node === source.step) { toast(ui('Une tâche ne peut pas recevoir sa propre sortie.')); return; }
  if (target.node !== OUT_NODE && source.step !== IN_NODE && wouldLoop(source.step, target.node)) {
    toast(ui('Ce fil créerait une boucle : une méthode avance, une reprise se pilote sur le board.')); return;
  }
  const port = sinkPort(target.node, target.port);
  if (!port) return;
  port.source = {step: source.step, port: source.port};
  methodEditor.edge = null; redraw();
}
// A wire dropped on a node rather than on a pin: the node gets the input it needs.
function connectToNode(source, nodeKey) {
  const from = nodeByKey(source.step)?.outputs.find(p => p.key === source.port);
  if (!from || nodeKey === IN_NODE || nodeKey === source.step) return;
  if (nodeKey === OUT_NODE) {
    const list = methodEditor.draft.outputs, key = slugKey(from.name, list, ui('sortie'));
    list.push({key, name: from.name, kind: from.kind, description: '', source: null});
    connect(source, {node: OUT_NODE, port: key});
    return;
  }
  const step = stepByKey(nodeKey);
  if (!step) return;
  const free = step.inputs.find(p => !p.source && p.kind === from.kind) || (step.kind === 'method' && step.inputs.find(p => !p.source));
  if (free) { connect(source, {node: nodeKey, port: free.key}); return; }
  if (step.kind === 'method') { toast(ui('Toutes les entrées de cette sous-méthode sont déjà branchées.')); return; }
  if (step.inputs.length >= 12) { toast(ui('Douze entrées au plus par tâche.')); return; }
  const key = pinKey(step.inputs, 'e');
  step.inputs.push({key, name: from.name, kind: from.kind, description: '', source: null});
  connect(source, {node: nodeKey, port: key});
}
function removeEdge(id) {
  if (id.startsWith('o:')) {
    const [from, to] = id.slice(2).split('>'), step = stepByKey(to);
    if (step) step.depends_on = step.depends_on.filter(k => k !== from);
  } else {
    const {node, port} = parsePin(id.slice(2)), sink = sinkPort(node, port);
    if (sink) sink.source = null;
  }
  methodEditor.edge = null; redraw();
}

// --- right-click menu ---------------------------------------------------------------------------------------

function menuItems(ctx) {
  const items = [];
  if (ctx.type === 'canvas') {
    if (ctx.wireFrom) items.push({label: ui('＋ Nouvelle tâche branchée ici'), act: 'task-wired'}, {sep: true});
    items.push({label: ui('＋ Tâche ici'), act: 'task'});
    const subs = methodEditor.library.filter(m => m.id !== methodEditor.id);
    items.push({title: ui('Sous-méthode ici')}, ...(subs.length ? subs.map(m => ({label: '⧉ ' + m.name, act: 'sub', arg: m.id})) : [{label: ui('Aucune autre méthode enregistrée'), disabled: true}]));
    items.push({sep: true}, {label: ui('＋ Entrée de méthode · contexte'), act: 'min', arg: 'context'}, {label: ui('＋ Entrée de méthode · texte'), act: 'min', arg: 'text'},
      {label: ui('＋ Entrée de méthode · fichier'), act: 'min', arg: 'file'}, {label: ui('＋ Sortie de méthode'), act: 'mout'},
      {sep: true}, {label: ui('Ranger'), act: 'layout'}, {label: ui('Cadrer'), act: 'fit'});
  } else if (ctx.type === 'node') {
    const step = stepByKey(ctx.key);
    if (ctx.key === IN_NODE) items.push({label: ui('＋ Contexte'), act: 'min', arg: 'context'}, {label: ui('＋ Texte'), act: 'min', arg: 'text'}, {label: ui('＋ Fichier'), act: 'min', arg: 'file'});
    else if (ctx.key === OUT_NODE) items.push({label: ui('＋ Sortie'), act: 'mout'});
    else if (step?.kind === 'method') items.push({label: ui('Ouvrir la sous-méthode'), act: 'open-sub', arg: step.method_id}, {label: ui('Dupliquer'), act: 'duplicate'}, {sep: true}, {label: ui('Retirer du graphe'), act: 'delete', danger: true});
    else if (step) items.push({label: ui('⤢ Écrire la consigne en grand'), act: 'writer'}, {sep: true}, {label: ui('＋ Entrée'), act: 'node-in'}, {label: ui('＋ Sortie'), act: 'node-out'}, {label: ui('Dupliquer'), act: 'duplicate'}, {sep: true}, {label: ui('Supprimer la tâche'), act: 'delete', danger: true});
  } else if (ctx.type === 'pin') {
    const node = nodeByKey(ctx.node), list = ctx.side === 'in' ? node.inputs : node.outputs, port = list.find(p => p.key === ctx.port);
    const fixed = node.kind === 'method' || (ctx.node === IN_NODE && ctx.port === 'objectif');
    if (!port) return items;
    items.push({title: port.name});
    if (!fixed) items.push({label: ui('Renommer…'), act: 'pin-rename'}, ...Object.entries(KIND_LABELS).filter(([k]) => k !== port.kind).map(([k, v]) => ({label: 'Type : ' + v, act: 'pin-kind', arg: k})));
    if (ctx.side === 'in' && port.source) items.push({label: ui('Débrancher'), act: 'pin-unwire'});
    if (!fixed) items.push({sep: true}, {label: ui('Supprimer la broche'), act: 'pin-remove', danger: true});
  }
  return items;
}
function openMenu(event, ctx) {
  const menu = $('me-menu'), canvas = $('me-canvas');
  if (!menu) return;
  const items = menuItems(ctx);
  if (!items.length) return;
  methodEditor.menu = {...ctx, point: worldPoint(event)};
  menu.innerHTML = items.map((item, i) => item.sep ? '<hr>' : item.title ? `<div class="me-menu-title">${esc(item.title)}</div>`
    : `<button type="button" data-me-menu="${i}" class="${item.danger ? 'danger' : ''}" ${item.disabled ? 'disabled' : ''}>${esc(item.label)}</button>`).join('');
  methodEditor.menu.items = items;
  menu.hidden = false;
  const rect = canvas.getBoundingClientRect();
  const left = Math.min(event.clientX - rect.left, rect.width - menu.offsetWidth - 8), top = Math.min(event.clientY - rect.top, rect.height - menu.offsetHeight - 8);
  menu.style.left = Math.max(4, left) + 'px'; menu.style.top = Math.max(4, top) + 'px';
}
function closeMenu() { const menu = $('me-menu'); if (menu) menu.hidden = true; methodEditor.menu = null; }
function pinList(ctx) { const node = nodeByKey(ctx.node); return ctx.side === 'in' ? node.inputs : node.outputs; }
function addPin(scope, kind) {
  const m = methodEditor.draft, step = stepByKey(methodEditor.selected);
  if (scope === 'min') { const name = {context: ui('Contexte'), text: ui('Texte'), file: ui('Fichier')}[kind] || ui('Entrée'); m.inputs.push({key: slugKey(name, m.inputs, 'entree'), name, kind: kind || 'text', description: '', required: false, prepare: ''}); }
  else if (scope === 'mout') m.outputs.push({key: slugKey(ui('Sortie'), m.outputs, ui('sortie')), name: ui('Sortie ') + (m.outputs.length + 1), kind: 'text', description: '', source: null});
  else if (step && scope === 'inputs') step.inputs.push({key: pinKey(step.inputs, 'e'), name: ui('Entrée ') + (step.inputs.length + 1), kind: kind || 'text', description: '', source: null});
  else if (step && scope === 'outputs') step.outputs.push({key: pinKey(step.outputs, 's'), name: ui('Sortie ') + (step.outputs.length + 1), kind: kind || 'text', description: ''});
  redraw();
}
function removePin(list, index, nodeKey, side) {
  const [port] = list.splice(index, 1);
  if (port && side === 'out') sinks().forEach(([, p]) => { if (p.source && p.source.step === nodeKey && p.source.port === port.key) p.source = null; });
  redraw();
}
function duplicateStep(key) {
  const source = stepByKey(key), copy = nextKey();
  methodEditor.draft.steps.push({...source, key: copy, name: source.name + ' (copie)', depends_on: [...source.depends_on], helpers: [...source.helpers],
    inputs: source.inputs.map(p => ({...p, source: p.source ? {...p.source} : null})), outputs: source.outputs.map(p => ({...p})),
    position: {x: source.position.x + 40, y: source.position.y + nodeHeight(source) + 30}});
  methodEditor.selected = copy; redraw();
}
function runMenu(index) {
  const ctx = methodEditor.menu, item = ctx?.items[index];
  closeMenu();
  if (!item || item.disabled) return;
  const at = {x: Math.round(ctx.point.x - NODE_WIDTH / 2), y: Math.round(ctx.point.y - 20)};
  const port = ctx.type === 'pin' ? pinList(ctx).find(p => p.key === ctx.port) : null;
  switch (item.act) {
    case 'task': addTask(at); break;
    case 'task-wired': addTask({x: Math.round(ctx.point.x + 20), y: Math.round(ctx.point.y - PIN_TOP - 10)}, ctx.wireFrom); break;
    case 'sub': addSubMethod(item.arg, at); break;
    case 'min': methodEditor.selected = IN_NODE; addPin('min', item.arg); break;
    case 'mout': methodEditor.selected = OUT_NODE; addPin('mout'); break;
    case 'layout': autoLayout(); markDirty(); fitView(); break;
    case 'fit': fitView(); break;
    case 'open-sub': openSubMethod(item.arg); break;
    case 'writer': methodEditor.selected = ctx.key; openWriter({step: ctx.key}).catch(fail); break;
    case 'duplicate': duplicateStep(ctx.key); break;
    case 'delete': removeTask(ctx.key); break;
    case 'node-in': methodEditor.selected = ctx.key; addPin('inputs'); break;
    case 'node-out': methodEditor.selected = ctx.key; addPin('outputs'); break;
    case 'pin-unwire': if (port) { port.source = null; redraw(); } break;
    case 'pin-kind': if (port) { port.kind = item.arg; redraw(); } break;
    case 'pin-remove': { const list = pinList(ctx); removePin(list, list.indexOf(port), ctx.node, ctx.side); break; }
    case 'pin-rename':
      if (port) openDialog(ui('Renommer la broche'), ui`<div class="fields"><label>Nom<input name="name" value="${esc(port.name)}" maxlength="80" required></label><p class="field-help">Les fils restent branchés : ils suivent la broche, pas son nom.</p></div>`,
        async form => { port.name = String(form.get('name')).trim() || port.name; redraw(); }, ui('Renommer'));
      break;
  }
}

// --- pointer interactions: drag nodes, draw wires, pan and zoom -------------------------------------------------

function setWire(a, b) { $('me-wire')?.setAttribute('d', a && b ? curve(a.x, a.y, b.x, b.y) : ''); }
document.addEventListener('pointerdown', e => {
  if (methodEditor.menu && !e.target.closest?.('#me-menu')) closeMenu();
  const canvas = e.target.closest?.('#me-canvas');
  if (!canvas || e.button !== 0 || e.target.closest('#me-menu')) return;
  const out = e.target.closest('[data-port-out]'), pinOut = e.target.closest('[data-pin-out]'), pinIn = e.target.closest('[data-pin-in]');
  const head = e.target.closest('[data-node-drag]'), node = e.target.closest('[data-node]'), edge = e.target.closest('[data-edge]');
  if (pinOut) {
    const {node: step, port} = parsePin(pinOut.dataset.pinOut);
    methodEditor.drag = {type: 'data', from: {step, port}, sx: e.clientX, sy: e.clientY};
  } else if (pinIn) {
    const target = parsePin(pinIn.dataset.pinIn), sink = sinkPort(target.node, target.port);
    // Pulling a wired input picks its wire up again; an empty input starts a wire towards an output.
    if (sink?.source) methodEditor.drag = {type: 'data', from: {...sink.source}, pick: target, sx: e.clientX, sy: e.clientY};
    else methodEditor.drag = {type: 'data', to: target, sx: e.clientX, sy: e.clientY};
  } else if (out) {
    methodEditor.drag = {type: 'wire', from: out.dataset.portOut};
  } else if (head || node) {
    const key = (head || node).dataset.nodeDrag || node.dataset.node, target = nodeByKey(key), point = worldPoint(e);
    methodEditor.drag = {type: 'node', key, dx: point.x - target.position.x, dy: point.y - target.position.y, moved: false};
  } else if (edge) {
    methodEditor.edge = edge.dataset.edge; methodEditor.selected = null; renderEdgesOnly(); renderInspectorPanel();
    document.querySelectorAll('.me-node.selected').forEach(n => n.classList.remove('selected'));
    return;
  } else {
    methodEditor.drag = {type: 'pan', sx: e.clientX, sy: e.clientY, ox: methodEditor.view.x, oy: methodEditor.view.y, moved: false};
  }
  canvas.setPointerCapture(e.pointerId);
  canvas.focus();
});
document.addEventListener('pointermove', e => {
  const drag = methodEditor.drag;
  if (!drag || !$('me-canvas')) return;
  if (drag.type === 'node') {
    const target = nodeByKey(drag.key), point = worldPoint(e);
    const position = {x: Math.round(point.x - drag.dx), y: Math.round(point.y - drag.dy)};
    if (target.io) methodEditor.draft.layout[drag.key === IN_NODE ? 'in' : 'out'] = position; else target.position = position;
    const el = document.querySelector(`[data-node="${CSS.escape(drag.key)}"]`);
    if (el) { el.style.left = position.x + 'px'; el.style.top = position.y + 'px'; }
    drag.moved = true;
    renderEdgesOnly();
  } else if (drag.type === 'pan') {
    methodEditor.view.x = drag.ox + e.clientX - drag.sx; methodEditor.view.y = drag.oy + e.clientY - drag.sy;
    drag.moved = drag.moved || Math.abs(e.clientX - drag.sx) + Math.abs(e.clientY - drag.sy) > 3;
    const {x, y, z} = methodEditor.view;
    $('me-world').style.transform = `translate(${x}px,${y}px) scale(${z})`;
    $('me-canvas').style.backgroundPosition = `${x}px ${y}px`;
  } else if (drag.type === 'wire') {
    const from = stepByKey(drag.from), point = worldPoint(e);
    setWire({x: from.position.x + NODE_WIDTH, y: from.position.y + PORT_Y}, point);
  } else if (drag.type === 'data') {
    const point = worldPoint(e);
    if (!drag.moved && Math.abs(e.clientX - drag.sx) + Math.abs(e.clientY - drag.sy) < 4) return;
    if (!drag.moved && drag.pick) {
      // Pulling a wired input picks its wire up again, to drop it elsewhere.
      const sink = sinkPort(drag.pick.node, drag.pick.port);
      if (sink) sink.source = null;
      drag.picked = true; markDirty(); renderEdgesOnly();
    }
    drag.moved = true;
    if (drag.from) setWire(pinPoint(drag.from.step, drag.from.port, 'out'), point);
    else setWire(point, pinPoint(drag.to.node, drag.to.port, 'in'));
  }
});
document.addEventListener('pointerup', e => {
  const drag = methodEditor.drag;
  if (!drag) return;
  methodEditor.drag = null;
  if (drag.type === 'node') {
    if (drag.moved) markDirty();
    if (methodEditor.selected !== drag.key || methodEditor.edge) {
      methodEditor.selected = drag.key; methodEditor.edge = null;
      document.querySelectorAll('.me-node').forEach(n => n.classList.toggle('selected', n.dataset.node === drag.key));
      renderEdgesOnly(); renderInspectorPanel();
    }
  } else if (drag.type === 'pan' && !drag.moved) {
    if (methodEditor.selected || methodEditor.edge) { methodEditor.selected = null; methodEditor.edge = null; renderGraph(); renderInspectorPanel(); }
  } else if (drag.type === 'wire') {
    setWire();
    const target = document.elementFromPoint(e.clientX, e.clientY)?.closest('[data-node]');
    const to = target && stepByKey(target.dataset.node);
    if (!to || to.key === drag.from || to.depends_on.includes(drag.from)) return;
    if (wouldLoop(drag.from, to.key)) { toast(ui('Ce lien créerait une boucle : une méthode avance, une reprise se pilote sur le board.')); return; }
    to.depends_on.push(drag.from);
    redraw();
  } else if (drag.type === 'data') {
    setWire();
    if (!drag.moved) return;  // a click on a pin is not a wire
    const hit = document.elementFromPoint(e.clientX, e.clientY);
    if (drag.from) {
      const pin = hit?.closest('[data-pin-in]'), node = hit?.closest('[data-node]');
      if (pin) connect(drag.from, parsePin(pin.dataset.pinIn));
      else if (node) connectToNode(drag.from, node.dataset.node);
      else if (hit?.closest('#me-canvas')) { if (drag.picked) redraw(); openMenu(e, {type: 'canvas', wireFrom: drag.from}); }
      else if (drag.picked) redraw();
    } else {
      const pin = hit?.closest('[data-pin-out]');
      if (pin) { const {node, port} = parsePin(pin.dataset.pinOut); connect({step: node, port}, drag.to); }
    }
  }
});
document.addEventListener('contextmenu', e => {
  if (!e.target.closest?.('#me-canvas') || e.target.closest('#me-menu')) return;
  e.preventDefault();
  const pinIn = e.target.closest('[data-pin-in]'), pinOut = e.target.closest('[data-pin-out]'), node = e.target.closest('[data-node]');
  if (pinIn || pinOut) { const {node: key, port} = parsePin((pinIn || pinOut).dataset[pinIn ? 'pinIn' : 'pinOut']); openMenu(e, {type: 'pin', node: key, port, side: pinIn ? 'in' : 'out'}); }
  else if (node) { methodEditor.selected = node.dataset.node; renderGraph(); renderInspectorPanel(); openMenu(e, {type: 'node', key: node.dataset.node}); }
  else openMenu(e, {type: 'canvas'});
});
document.addEventListener('dblclick', e => {
  if (!e.target.closest?.('#me-canvas') || e.target.closest('#me-menu')) return;
  const node = e.target.closest('[data-node]');
  if (node) {
    const step = stepByKey(node.dataset.node);
    if (step?.kind === 'method') openSubMethod(step.method_id);
    else if (step) { methodEditor.selected = step.key; openWriter({step: step.key}).catch(fail); }
    return;
  }
  const point = worldPoint(e);
  addTask({x: Math.round(point.x - NODE_WIDTH / 2), y: Math.round(point.y - 20)});
});
document.addEventListener('wheel', e => {
  if (!e.target.closest?.('#me-canvas') || e.target.closest('#me-menu')) return;
  e.preventDefault();
  const rect = $('me-canvas').getBoundingClientRect(), view = methodEditor.view;
  const z = Math.max(0.3, Math.min(2, view.z * (e.deltaY < 0 ? 1.1 : 0.9)));
  const px = e.clientX - rect.left, py = e.clientY - rect.top;
  view.x = px - (px - view.x) * z / view.z; view.y = py - (py - view.y) * z / view.z; view.z = z;
  renderGraph();
}, {passive: false});
document.addEventListener('keydown', e => {
  if (state.view !== 'method' || $('dialog').open || e.target.closest?.('input,textarea,select')) return;
  if (e.key === 'Escape' && methodEditor.menu) { closeMenu(); return; }
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (methodEditor.edge) removeEdge(methodEditor.edge);
    else if (methodEditor.selected && stepByKey(methodEditor.selected)) removeTask(methodEditor.selected);
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveMethodGraph().catch(fail); }
});

// --- inspector edits ------------------------------------------------------------------------------------------------

function pinTarget(value) {
  const [scope, index] = value.split(':'), step = stepByKey(methodEditor.selected), m = methodEditor.draft;
  const list = scope === 'min' ? m.inputs : scope === 'mout' ? m.outputs : scope === 'inputs' ? step?.inputs : step?.outputs;
  return {scope, list, index: Number(index), port: list?.[Number(index)]};
}
function refreshNode() {
  const key = methodEditor.selected, el = key && document.querySelector(`[data-node="${CSS.escape(key)}"]`);
  if (!el) return;
  el.outerHTML = key === IN_NODE || key === OUT_NODE ? ioHTML(key) : nodeHTML(stepByKey(key));
  placeNodes(); renderEdgesOnly();
}
document.addEventListener('input', e => {
  if (state.view !== 'method' || !methodEditor.draft) return;
  const t = e.target, d = t.dataset;
  if (d.meMethod) { methodEditor.draft[d.meMethod] = t.value; markDirty(); if (d.meMethod === 'name') methodEditor.mounted = methodEditor.id + ':' + t.value; }
  if (d.meField && methodEditor.selected && t.tagName !== 'SELECT') {
    stepByKey(methodEditor.selected)[d.meField] = t.value; markDirty(); refreshNode();
  }
  if (d.mePin && d.mePinField && t.tagName !== 'SELECT' && t.type !== 'checkbox') {
    const {port} = pinTarget(d.mePin);
    if (port) { port[d.mePinField] = t.value; markDirty(); if (d.mePinField === 'name') refreshNode(); }
  }
  if (d.meReq !== undefined && d.meReqField && t.tagName !== 'SELECT') { methodEditor.draft.requirements[Number(d.meReq)][d.meReqField] = t.value; markDirty(); }
});
document.addEventListener('change', e => {
  if (state.view !== 'method' || !methodEditor.draft) return;
  const t = e.target, d = t.dataset, step = methodEditor.selected && stepByKey(methodEditor.selected);
  if (d.meField && step && t.tagName === 'SELECT') {
    step[d.meField] = t.value;
    // The list shows every connector; default to an enabled one, else to the first shown, so what you see is what is saved.
    if (d.meField === 'executor' && t.value === 'connector' && !step.connector) step.connector = ((state.data?.connectors || []).find(c => c.enabled) || (state.data?.connectors || [])[0])?.id || '';
    if (d.meField === 'profile_id') { const p = methodProfiles().find(x => x.id === t.value); if (p && /^Tâche \d+$/.test(step.name)) step.name = p.name; }
    if (d.meField === 'method_id') {
      // Another sub-method: its pins replace the old ones; wires to pins it does not have are dropped.
      const sub = methodEditor.library.find(m => m.id === t.value), wired = Object.fromEntries(step.inputs.map(p => [p.key, p.source]));
      if (sub) {
        step.inputs = sub.inputs.map(p => ({key: p.key, name: p.name, kind: p.kind, description: p.description, required: p.required, source: wired[p.key] || null}));
        const kept = new Set(sub.outputs.map(p => p.key));
        step.outputs.filter(p => !kept.has(p.key)).forEach(p => sinks().forEach(([, s]) => { if (s.source && s.source.step === step.key && s.source.port === p.key) s.source = null; }));
        step.outputs = sub.outputs.map(p => ({key: p.key, name: p.name, kind: p.kind, description: p.description || ''}));
        if (step.name === methodEditor.library.find(m => step.name === m.name)?.name) step.name = sub.name;
      }
    }
    redraw();
  }
  if (d.mePin && d.mePinField === 'kind') { const {port} = pinTarget(d.mePin); if (port) { port.kind = t.value; redraw(); } }
  if (d.mePin && d.mePinField === 'required') { const {port} = pinTarget(d.mePin); if (port) { port.required = t.checked; refreshNode(); markDirty(); } }
  if (d.meHelper !== undefined && step) {
    step.helpers = t.checked ? [...step.helpers, d.meHelper].slice(0, 6) : step.helpers.filter(h => h !== d.meHelper);
    if (t.checked && step.helpers.length >= 6 && !step.helpers.includes(d.meHelper)) toast(ui('Six agents appelables au plus par tâche.'));
    redraw();
  }
  if (t.hasAttribute('data-me-depend') && step && t.value) { step.depends_on.push(t.value); redraw(); }
  if (t.hasAttribute('data-ma-add') && t.value && methodEditor.id) {
    action('profile_method_set', {profile_id: t.value, method_id: methodEditor.id, mode: 'preferred'}).then(r => { toast(r.notice); return loadMethodAgents(); }).catch(fail);
  }
  if (d.meOption) { methodEditor.draft.options = {...(methodEditor.draft.options || {}), [d.meOption]: t.checked}; markDirty(); }
  if (d.meReq !== undefined && d.meReqField === 'kind') { methodEditor.draft.requirements[Number(d.meReq)].kind = t.value; markDirty(); renderInspectorPanel(); }
});

// --- applying, importing ---------------------------------------------------------------------------------------------

async function methodApplyDialog(method) {
  const free = method.steps.filter(s => s.kind !== 'method' && s.executor === 'any');
  const connectors = (state.data?.connectors || []).filter(c => c.enabled);
  const extra = (method.inputs || []).filter(p => p.key !== 'objectif');
  openDialog(ui('Appliquer · ') + method.name, ui`<div class="fields">
    ${method.usage ? ui`<div class="me-usage"><b>Mode d’emploi</b><p>${esc(method.usage)}</p></div>` : ''}
    <label>Projet<select name="project_id">${projectOptions(state.project)}</select></label>
    <label>Objectif<textarea name="objective" rows="3" maxlength="4000" required placeholder="Ce que la chaîne doit produire, par exemple : un croiseur minier cyberpunk"></textarea></label>
    ${extra.map(p => p.kind === 'file'
      ? ui`<label>${esc(p.name)}${p.required ? ' *' : ''}<input name="in:${esc(p.key)}" maxlength="400" placeholder="Chemin dans le projet" ${p.required ? 'required' : ''}>${p.prepare || p.description ? `<small class="field-help">${esc(p.prepare || p.description)}</small>` : ''}</label>`
      : `<label>${esc(p.name)}${p.kind === 'context' ? ' (contexte)' : ''}${p.required ? ' *' : ''}<textarea name="in:${esc(p.key)}" rows="${p.kind === 'context' ? 5 : 2}" maxlength="50000" placeholder="${esc(p.description || '')}" ${p.required ? 'required' : ''}></textarea>${p.prepare ? ui`<small class="field-help">Préparation : ${esc(p.prepare)}</small>` : ''}</label>`).join('')}
    ${extra.some(p => p.kind !== 'file') && connectors.length ? ui`<details class="me-prepare"><summary>Préparer ces entrées avec une IA…</summary>
      <p class="field-help">Une IA lit le mode d’emploi et la préparation de chaque entrée, puis rédige les entrées à partir de l’objectif et de la matière que vous collez ici. Elle remplit ce formulaire : vous relisez avant d’appliquer. Cela consomme des crédits de l’IA choisie.</p>
      <textarea name="material" rows="4" maxlength="50000" placeholder="Matière brute : brief, notes, extraits…"></textarea>
      <div class="two-fields"><select name="prep_connector" aria-label="IA">${connectors.map(c => `<option value="${esc(c.id)}">${esc(agentName(c.id))}</option>`).join('')}</select><input name="prep_model" placeholder="modèle par défaut" aria-label="Modèle"></div>
      <div class="row-actions"><button type="button" class="secondary" data-me-prepare="${esc(method.id)}">Préparer</button><span id="me-prepare-status" class="field-help"></span></div></details>` : ''}
    ${free.length && !connectors.length ? ui('<p class="me-warning">⚠ Aucun connecteur activé : activez-en un dans Connecteurs pour les tâches confiées à n’importe quelle IA.</p>') : ''}
    ${free.length && connectors.length ? ui`<div class="two-fields"><label>IA des tâches libres (${free.length})<select name="connector" required>${connectors.map(c => `<option value="${esc(c.id)}">${esc(agentName(c.id))}</option>`).join('')}</select></label><label>Modèle<input name="model" placeholder="par défaut"></label></div>` : ''}
    <label>Tâches simultanées<input name="concurrency" type="number" min="1" max="32" value="1" required></label>
    ${(method.warnings || []).filter(w => w.level === 'warning').map(w => `<p class="me-warning">⚠ <b>${esc(w.where)}</b> : ${esc(w.message)}</p>`).join('')}
    <p class="field-help">La chaîne est préparée dans sa propre conversation et <b>n’est pas lancée</b>. Relisez les instructions et les livrables attendus, puis lancez-la depuis le suivi de mission.</p>
  </div>`, async form => {
    const values = Object.fromEntries(form), inputs = {};
    delete values.material; delete values.prep_connector; delete values.prep_model;
    Object.entries(values).forEach(([k, v]) => { if (k.startsWith('in:') && String(v).trim()) inputs[k.slice(3)] = v; });
    const r = await action('method_apply', {project_id: values.project_id, id: method.id, objective: values.objective, inputs,
      concurrency: Number(values.concurrency), ...(values.connector ? {connector: values.connector, model: values.model || ''} : {})});
    methodEditor.dirty = false;
    state.home = false; state.project = values.project_id;
    toast(r.notice);
    await selectConversation(r.conversation_id);
  }, ui('Préparer la chaîne'));
}
// The AI drafts; the form shows what it wrote. Nothing is applied until you press the dialog's button.
async function prepareMethodInputs(id, button) {
  const form = button.closest('form'), status = $('me-prepare-status'), objective = form.querySelector('[name="objective"]').value.trim();
  if (!objective) { status.textContent = ui('Écrivez d’abord l’objectif.'); return; }
  button.disabled = true; status.textContent = ui('Préparation en cours…');
  try {
    const started = await action('method_prepare_inputs', {id, objective, material: form.querySelector('[name="material"]').value,
      connector: form.querySelector('[name="prep_connector"]').value, model: form.querySelector('[name="prep_model"]').value});
    let mission;
    do { await new Promise(r => setTimeout(r, 1200)); mission = await api('mission/' + started.mission_id); }
    while (!['succeeded', 'failed', 'cancelled', 'interrupted'].includes(mission.status) && $('dialog').open);
    const r = await action('method_prepared_inputs', {id, mission_id: started.mission_id});
    if (r.status !== 'succeeded') { status.textContent = ui('La préparation n’a pas abouti (') + (L.states?.[r.status] || r.status) + ').'; return; }
    Object.entries(r.inputs).forEach(([key, value]) => { const field = form.querySelector(`[name="in:${CSS.escape(key)}"]`); if (field) field.value = value; });
    status.textContent = Object.keys(r.inputs).length + ui(' entrée(s) remplie(s) — relisez-les.') + (r.missing.length ? ui(' Non trouvées dans la réponse : ') + r.missing.join(', ') + '.' : '');
  } finally { button.disabled = false; }
}
function methodFileName(name) { return (name || 'methode').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^\w-]+/g, '-').replace(/^-|-$/g, '').toLowerCase() + '.cyai-method.json'; }
function importMethodFile() {
  const input = document.createElement('input');
  input.type = 'file'; input.accept = '.json,application/json';
  input.onchange = async () => {
    const file = input.files[0];
    if (!file) return;
    if (file.size > 24000000) { fail(new Error(ui('Fichier de méthode trop volumineux (24 Mo au plus).'))); return; }
    const text = await file.text();
    openDialog(ui('Importer « ') + file.name + ' »', ui`<div class="fields">
      <label><span><input type="checkbox" name="create_profiles" checked> Créer dans la bibliothèque les profils absents, à partir de l’export</span></label>
      <p class="field-help">Sinon, leurs tâches sont confiées à n’importe quelle IA. Les sous-méthodes incluses sont importées aussi. Tout ce qui manque sur cette machine (connecteur, plugin, logiciel) sera signalé par un avertissement, sans bloquer l’import.</p></div>`,
      async form => {
        const r = await action('method_import', {data: text, create_profiles: !!form.get('create_profiles')});
        toast(r.notice);
        setTimeout(async () => {
          await openMethodGraph(r.id);
          if (r.warnings.length) openDialog(ui('Import · ce qu’il faut savoir'), `<ul class="board-history">${r.warnings.map(w => `<li>${w.level === 'warning' ? '⚠' : 'ℹ'} <b>${esc(w.where)}</b> : ${esc(w.message)}</li>`).join('')}</ul>`, null);
        }, 0);
      }, ui('Importer'));
  };
  input.click();
}

document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button) return;
  const d = button.dataset;
  try {
    if (d.methodGraph !== undefined) await openMethodGraph(d.methodGraph || null);
    if (button.hasAttribute('data-method-import')) importMethodFile();
    if (d.methodExport) { const r = await action('method_export', {id: d.methodExport}); download(methodFileName(r.method.name), r); toast(r.notice); }
    if (d.mePrepare) await prepareMethodInputs(d.mePrepare, button);
    if (state.view !== 'method') return;
    if (d.meMenu !== undefined) { runMenu(Number(d.meMenu)); return; }
    if (button.hasAttribute('data-me-close')) closeMethodEditor();
    if (button.hasAttribute('data-me-add')) addTask();
    if (button.hasAttribute('data-me-layout')) { autoLayout(); markDirty(); fitView(); }
    if (button.hasAttribute('data-me-fit')) fitView();
    if (d.meZoom) { methodEditor.view.z = Math.max(0.3, Math.min(2, methodEditor.view.z * Number(d.meZoom))); renderGraph(); }
    if (button.hasAttribute('data-me-save')) await saveMethodGraph();
    if (button.hasAttribute('data-me-export')) {
      if (!methodEditor.id || methodEditor.dirty) await saveMethodGraph();
      const r = await action('method_export', {id: methodEditor.id});
      download(methodFileName(r.method.name), r); toast(r.notice);
    }
    if (button.hasAttribute('data-me-apply')) {
      if (!methodEditor.id || methodEditor.dirty) await saveMethodGraph();
      await methodApplyDialog((await action('method_get', {id: methodEditor.id})).method);
    }
    if (d.meSelect !== undefined) { methodEditor.selected = d.meSelect || null; methodEditor.edge = null; renderGraph(); renderInspectorPanel(); }
    if (d.meDelete) removeTask(d.meDelete);
    if (d.meDuplicate) duplicateStep(d.meDuplicate);
    if (d.meOpenSub) openSubMethod(d.meOpenSub);
    if (d.meUndepend) { const step = stepByKey(methodEditor.selected); step.depends_on = step.depends_on.filter(k => k !== d.meUndepend); redraw(); }
    if (d.mePinAdd) addPin(d.mePinAdd, d.kind);
    if (d.mePinRemove) {
      const {scope, list, index} = pinTarget(d.mePinRemove);
      removePin(list, index, scope === 'min' ? IN_NODE : methodEditor.selected, scope === 'outputs' || scope === 'min' ? 'out' : 'in');
    }
    if (d.meUnwire) { const {port} = pinTarget(d.meUnwire); if (port) { port.source = null; redraw(); } }
    if (button.hasAttribute('data-me-history')) { methodEditor.revisions = (await action('method_history', {id: methodEditor.id})).revisions; renderInspectorPanel(); }
    if (d.meRestore) {
      const revision = Number(d.meRestore);
      openDialog(ui('Rétablir la version ') + revision, ui`<p>La version ${revision} redevient la méthode actuelle, enregistrée comme une nouvelle version. Rien n’est effacé${methodEditor.dirty ? ui(' — sauf vos modifications non enregistrées') : ''}.</p>`, async () => {
        const r = await action('method_restore', {id: methodEditor.id, revision});
        toast(r.notice);
        methodEditor.dirty = false;
        setTimeout(() => openMethodGraph(methodEditor.id, true), 0);
      }, ui('Rétablir'));
    }
    if (button.hasAttribute('data-me-req-add')) { methodEditor.draft.requirements.push({kind: 'software', name: '', executable: '', detail: ''}); markDirty(); renderInspectorPanel(); }
    if (d.meReqRemove !== undefined) { methodEditor.draft.requirements.splice(Number(d.meReqRemove), 1); markDirty(); renderInspectorPanel(); }
  } catch (error) { fail(error); }
});
