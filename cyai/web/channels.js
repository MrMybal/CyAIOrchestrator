'use strict';
// The Discord-style shell: projects as servers on the rail, typed channels in the list, the team on the right.
// Every channel opens an existing view; presence comes from project_channels and never says "online".
const shell = {channels: {}, fetchedAt: {}, loading: false, profiles: [], profilesAt: 0};
// Views that open over everything, like Discord's settings.
const OVERLAY_VIEWS = ['settings', 'agents', 'method', 'logs'];
L.views.home = ui('Accueil');
L.views.help = ui('Documentation');
const CHANNEL_ICONS = {assistant: '✦', conversation: '#', orchestrator: '◈', agent: '@', board: '▦', team: '⚑', overview: '◎', memory: '◇',
  pins: '✦', media: '▣', skills: '✎', plugins: '⊞', plugin: '⧉', settings: '⚙', whiteboard: '▢', graph: '⌘'};
const OVERVIEW_TABS = ['overview', 'usage', 'history', 'statistics'];
const MEMBER_GROUPS = {chief: ui('Chef de projet'), lead: 'Leads', member: ui('Membres'), consultant: 'Consultants'};

function shellHome() {
  const project = state.data?.projects.find(p => p.id === state.project);
  return !!state.home || !project || !!project.free_chat;
}
function showMembers(home) {
  return !home && state.rightPanel === 'members';
}

function railHTML(home) {
  const busy = {}, conversations = Object.fromEntries(state.data.conversations.map(c => [c.id, c.project_id]));
  for (const m of state.data.missions.filter(m => active(m.status))) {
    const project = conversations[m.conversation_id];
    if (project) busy[project] = busy[project] === 'awaiting_approval' ? busy[project] : m.status;
  }
  const item = p => `<button draggable="true" class="rail-item ${!home && p.id === state.project ? 'selected' : ''}" data-project="${p.id}" data-color="${esc(p.color)}" title="${esc(p.name)}${p.archived ? ' · archive' : ''}" aria-label="${esc(p.name)}">${projectLogo(p)}${busy[p.id] ? `<span class="rail-activity ${busy[p.id] === 'awaiting_approval' ? 'awaiting' : 'running'}" title="${busy[p.id] === 'awaiting_approval' ? ui('Autorisation requise') : ui('Exécution en cours')}"></span>` : ''}</button>`;
  const groups = ['', ...(state.data.categories || [])].map(category => state.data.projects
    .filter(p => !p.free_chat && (p.category || '') === category && (!p.archived || state.archives)).map(item).join('')).filter(Boolean);
  return ui`<button class="rail-item rail-home ${home ? 'selected' : ''}" data-shell-home="true" title="Accueil · agents et discussions libres" aria-label="Accueil"><img src="/cyai-logo.png" alt=""></button>
    <div class="rail-sep"></div>
    <div class="rail-projects">${groups.join('<div class="rail-sep"></div>')}</div>
    <button class="rail-item rail-add" data-shell-action="new-project" title="Ajouter un projet" aria-label="Ajouter un projet">＋</button>
    <div class="rail-tools"><button class="rail-tool" data-new-window title="Ouvrir une nouvelle fenêtre de CyAI" aria-label="Ouvrir une nouvelle fenêtre de CyAI">⧉</button>${[['agents', '☰', ui('Bibliothèque d’agents')], ['logs', '≡', 'Logs'], ['settings', '⚙', ui('Données & paramètres')], ['help', '?', ui('Documentation')]]
      .map(([view, glyph, label]) => `<button class="rail-tool ${state.view === view ? 'selected' : ''}" data-view="${view}" title="${label}" aria-label="${label}">${glyph}</button>`).join('')}</div>`;
}

function channelSelected(channel) {
  if (channel.type === 'assistant') return state.view === 'chat' && !!channel.id && state.conversation === channel.id;
  if (channel.space) return state.view === 'space' && state.spaceId === channel.id;
  if (channel.type === 'conversation' || channel.type === 'agent') return state.view === 'chat' && state.conversation === channel.id;
  if (state.view !== 'project') return false;
  return channel.id === state.projectTab || (channel.id === 'overview' && OVERVIEW_TABS.includes(state.projectTab));
}
function channelHTML(channel) {
  const selected = channelSelected(channel) ? 'selected' : '';
  if (channel.type === 'assistant') {
    // The project's assistant, first of the list; it shimmers until you have written to it.
    return ui`<div class="channel-row"><button class="channel assistant-channel ${selected} ${channel.fresh ? 'fresh' : ''}" data-assistant="${esc(channel.id)}" title="Assistant du projet : mise en place, présentation, consignes, équipe"><span class="ch-icon">${CHANNEL_ICONS.assistant}</span><span class="ch-name">${esc(channel.name)}</span>${channel.fresh ? ui('<span class="assistant-dot" title="À découvrir : vous ne lui avez pas encore écrit"></span>') : ''}</button>${channel.id ? conversationActivity(channel.id) : ''}</div>`;
  }
  const badge = channel.badge ? `<span class="channel-badge ${esc(channel.tone || '')}">${channel.badge}</span>` : '';
  if (channel.type === 'conversation' || channel.type === 'agent') {
    const glyph = channel.type === 'agent' ? CHANNEL_ICONS.agent : channel.mode === 'orchestrator' ? CHANNEL_ICONS.orchestrator : CHANNEL_ICONS.conversation;
    return ui`<div class="channel-row"><button draggable="true" class="channel ${selected}" data-conversation="${esc(channel.id)}" title="${esc(channel.name)}"><span class="ch-icon">${glyph}</span><span class="ch-name">${channel.favorite ? '★ ' : ''}${esc(channel.name)}</span></button>${conversationActivity(channel.id)}<button class="icon item-options" data-item-kind="conversation" data-item-id="${esc(channel.id)}" aria-label="Actions de ${esc(channel.name)}">⋯</button></div>`;
  }
  if (channel.space) return ui`<div class="channel-row"><button class="channel ${selected}" data-space="${esc(channel.id)}" title="${esc(channel.name)}"><span class="ch-icon">${CHANNEL_ICONS[channel.type] || '▢'}</span><span class="ch-name">${esc(channel.name)}</span></button><button class="icon item-options" data-space-menu="${esc(channel.id)}" aria-label="Options de ${esc(channel.name)}">⋯</button></div>`;
  return `<div class="channel-row"><button class="channel ${selected}" data-channel="${esc(channel.id)}" title="${esc(channel.name)}"><span class="ch-icon">${CHANNEL_ICONS[channel.type] || '#'}</span><span class="ch-name">${esc(channel.name)}</span>${badge}</button></div>`;
}
function channelListHTML(data) {
  const byCategory = {};
  for (const channel of data.channels) (byCategory[channel.category] ??= []).push(channel);
  // Memory plugins enabled for the project are channels of their own, like before in the project tabs.
  for (const plugin of projectMemoryPlugins()) (byCategory['Projet'] ??= []).push({type: 'plugin', id: 'plugin:' + plugin.id, name: plugin.name.toLowerCase(), category: ui('Projet')});
  const adders = {
    Conversations: ui`<button class="icon" data-new-conversation="${esc(data.project_id)}" title="Nouvelle conversation" aria-label="Nouvelle conversation">＋</button>`,
    Agents: ui`<button class="icon" data-shell-action="agent-chat" title="Discuter avec un agent" aria-label="Discuter avec un agent">＋</button>`,
    Espaces: ui`<button class="icon" data-shell-action="new-space" title="Nouveau salon" aria-label="Nouveau salon">＋</button>`};
  const empty = {Conversations: ui('Aucune conversation. ＋ pour en créer une.'), Agents: ui('Aucune conversation d’agent. ＋ pour solliciter un membre ou un profil.'),
    Espaces: ui('Aucun salon. ＋ pour créer un tableau blanc.')};
  return data.categories.map(category => {
    const rows = byCategory[category] || [];
    if (category === 'Assistant') return rows.length ? `<section class="channel-group assistant-group">${rows.map(channelHTML).join('')}</section>` : '';
    if (!rows.length && !adders[category]) return '';
    return `<section class="channel-group"><div class="channel-category"><span>${esc(category)}</span>${adders[category] || ''}</div>${rows.map(channelHTML).join('') || `<p class="channel-empty">${empty[category]}</p>`}</section>`;
  }).join('');
}

function avatarHTML(member, big = false) {
  return `<span class="member-avatar ${big ? 'big' : ''}">${esc(member.icon || member.name[0].toUpperCase())}<span class="presence ${esc(member.state)}" title="${esc(member.state_label)}"></span></span>`;
}
function memberListHTML(data) {
  const legend = ui`<p class="member-legend"><span class="presence-key running"></span>exécution en cours · <span class="presence-key awaiting"></span>attend votre autorisation · <span class="presence-key idle"></span>au repos · <span class="presence-key unavailable"></span>connecteur indisponible.<br>La présence vient des exécutions réellement en cours : un agent n’est jamais « en ligne ».</p>`;
  if (!data.team.exists) return ui`<div class="member-heading">Membres</div><div class="member-empty"><p>Aucune équipe dans ce projet.</p><button class="secondary" data-channel="team">Composer l’équipe</button></div>${legend}`;
  const groups = Object.entries(MEMBER_GROUPS).map(([role, label]) => {
    const members = data.members.filter(m => m.role === role);
    return members.length ? `<section class="member-group"><h4>${label} — ${members.length}</h4>${members.map(m => `<button class="member ${m.state}" data-shell-member="${esc(m.id)}" title="${esc(m.name + ' · ' + m.state_label)}">${avatarHTML(m)}<span class="member-text"><span class="member-name">${esc(m.name)}</span><span class="member-sub">${m.state === 'idle' ? esc(m.model || agentName(m.connector)) : esc(m.state_label)}</span></span></button>`).join('')}</section>` : '';
  }).join('');
  return ui`<div class="member-heading">Membres — ${data.members.length}</div>${groups || ui('<p class="channel-empty">Aucun membre actif.</p>')}${legend}`;
}

async function loadChannels() {
  const id = state.project;
  if (shell.loading || !id || shellHome()) return;
  shell.loading = true;
  try {
    shell.channels[id] = await action('project_channels', {project_id: id});
    shell.fetchedAt[id] = Date.now();
  } catch (error) {
    shell.fetchedAt[id] = Date.now();  // keep the last known list; the next refresh retries
  } finally {
    shell.loading = false;
  }
  if (state.project === id) renderShell();
}

function renderShell() {
  if (!state.data || !$('server-rail')) return;
  const overlay = OVERLAY_VIEWS.includes(state.view);
  document.querySelector('.app').classList.add('shell');
  document.querySelector('.app').classList.toggle('overlay-open', overlay);
  $('settings-close').hidden = !overlay || ['method','logs','agents'].includes(state.view);
  if (!overlay) shell.lastView = state.view;
  htmlIfChanged('home-list', homeListHTML());
  const home = shellHome(), project = state.data.projects.find(p => p.id === state.project);
  htmlIfChanged('server-rail', railHTML(home));
  $('home-channels').hidden = !home;
  $('project-channels').hidden = home;
  htmlIfChanged('channel-header', home
    ? ui('<button class="channel-title" data-shell-home="true">Messages privés</button>')
    : ui`<span class="project-mark" data-color="${esc(project.color)}">${projectLogo(project)}</span><button class="channel-title" data-channel="overview" title="Vue d’ensemble · ${esc(project.root)}">${esc(project.name)}</button><button class="icon item-options" data-item-kind="project" data-item-id="${esc(project.id)}" aria-label="Actions du projet">⋯</button>`);
  const data = home ? null : shell.channels[state.project];
  if (!home) {
    htmlIfChanged('project-channels', data ? channelListHTML(data) : ui('<p class="channel-empty">Chargement des salons…</p>'));
    if (Date.now() - (shell.fetchedAt[state.project] || 0) > 1400) loadChannels();
  }
  const members = showMembers(home);
  $('member-list').hidden = !members;
  if (members) htmlIfChanged('member-list', data ? memberListHTML(data) : '');
  const toggle = $('toggle-members'), label = members ? ui('Masquer les membres') : ui('Membres');
  toggle.hidden = home;
  toggle.title = label;
  toggle.setAttribute('aria-label', label);
  toggle.setAttribute('aria-expanded', String(members));
  toggle.classList.toggle('active', members);
  $('open-pins').hidden = home;
  $('topbar-glyph').textContent = topbarGlyph();
  fitInstruction();
  const search = home ? ui('Rechercher partout') : ui('Rechercher ') + project.name;
  if ($('header-search-input').placeholder !== search) $('header-search-input').placeholder = search;
  paintProjectColors();
}

function topbarGlyph() {
  if (state.view === 'chat') {
    if (!state.detail) return '#';
    return state.detail.member_id || state.detail.profile_id ? CHANNEL_ICONS.agent : state.detail.mode === 'orchestrator' ? CHANNEL_ICONS.orchestrator : CHANNEL_ICONS.conversation;
  }
  if (state.view === 'project') {
    const tab = state.projectTab || 'overview';
    return OVERVIEW_TABS.includes(tab) ? CHANNEL_ICONS.overview : CHANNEL_ICONS[tab.startsWith('plugin:') ? 'plugin' : tab] || '#';
  }
  return {help: '?', agents: '☰', logs: '≡', settings: '⚙', search: '⌕', memory: '◇', home: '✉', space: '▢'}[state.view] || '#';
}

// Settings and the library open over everything, like Discord; Échap or ✕ goes back to where the user was.
function closeOverlay() {
  if (state.view === 'method') { closeMethodEditor(); return; }
  showView(shell.lastView && !OVERLAY_VIEWS.includes(shell.lastView) ? shell.lastView : 'project');
}
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || !OVERLAY_VIEWS.includes(state.view) || document.querySelector('dialog[open]') || $('item-menu')) return;
  // In the method editor, Échap in a field only leaves the field.
  if (state.view === 'method' && e.target.closest?.('input,textarea,select')) { e.target.blur(); return; }
  // …and with the right-click menu open, Échap only closes the menu; with the writer open, only the writer.
  if (state.view === 'method' && methodEditor.menu) { closeMenu(); return; }
  if (state.view === 'method' && typeof writer !== 'undefined' && writer.open) { closeWriter(); return; }
  if (state.view === 'method' && typeof lab !== 'undefined' && lab.open) { closeLab(); return; }
  closeOverlay();
});

// --- home: direct messages, like Discord ------------------------------------------------------------
// A direct message is a discussion outside any project: with an agent of the library, or with the AI of your choice.
function directMessages() {
  const free = new Set(state.data.projects.filter(p => p.free_chat).map(p => p.id));
  return state.data.conversations.filter(c => free.has(c.project_id) && (state.archives ? !!c.archived : !c.archived));
}
function dmAvatar(c) {
  const profile = c.profile_id && shell.profiles.find(p => p.id === c.profile_id);
  if (profile) return esc(profile.icon || profile.name[0].toUpperCase());
  return c.agent_id ? esc(agentName(c.agent_id)[0] || '◌') : '◌';
}
function dmSubtitle(c) {
  const profile = c.profile_id && shell.profiles.find(p => p.id === c.profile_id);
  if (profile) return ui('Agent · révision ') + (c.profile_revision || profile.revision);
  return c.agent_id ? ui('Discussion libre · ') + agentName(c.agent_id) : ui('Discussion libre');
}
async function loadProfiles() {
  if (Date.now() - shell.profilesAt < 15000) return;
  shell.profilesAt = Date.now();
  try { shell.profiles = (await action('agent_profile_list')).profiles; } catch (error) { return; }
  renderShell();
}
function homeListHTML() {
  if (!state.data) return '';
  if (state.detail?.profile_id) loadProfiles();
  if (directMessages().some(c => c.profile_id)) loadProfiles();
  const rows = directMessages().map(c => ui`<div class="channel-row"><button class="channel dm ${state.view === 'chat' && state.conversation === c.id ? 'selected' : ''}" data-conversation="${esc(c.id)}" title="${esc(c.title)}"><span class="member-avatar small">${dmAvatar(c)}</span><span class="ch-name">${c.favorite ? '★ ' : ''}${esc(c.title)}</span></button>${conversationActivity(c.id)}<button class="icon item-options" data-item-kind="conversation" data-item-id="${esc(c.id)}" aria-label="Actions de ${esc(c.title)}">⋯</button></div>`).join('');
  return ui`<button data-view="agents" class="channel home-link ${state.view === 'agents' ? 'selected' : ''}"><span class="ch-icon">☰</span><span class="ch-name">Bibliothèque d’agents</span></button>
    <button class="channel home-link ${state.view === 'home' ? 'selected' : ''}" data-shell-home="true"><span class="ch-icon">✉</span><span class="ch-name">Tous les messages</span></button>
    <div class="channel-category"><span>Messages privés</span><button class="icon" data-shell-action="new-dm" title="Nouveau message privé" aria-label="Nouveau message privé">＋</button></div>
    ${rows || ui('<p class="channel-empty">Aucun message privé. ＋ pour écrire à un agent de la bibliothèque ou ouvrir une discussion libre.</p>')}`;
}
async function renderHomePage() {
  shell.profilesAt = 0;
  await loadProfiles();
  if (state.view !== 'home') return;
  $('page-title').textContent = ui('Messages privés');
  const cards = directMessages().map(c => `<button class="dm-card" data-conversation="${esc(c.id)}"><span class="member-avatar">${dmAvatar(c)}</span><span class="member-text"><b>${esc(c.title)}</b><small>${esc(dmSubtitle(c))} · ${date(c.created_at)}</small></span>${conversationActivity(c.id)}</button>`).join('');
  const agents = shell.profiles.filter(p => !p.archived).map(p => ui`<button class="dm-agent" data-profile-dm="${esc(p.id)}" title="Écrire à ${esc(p.name)}"><span class="member-avatar">${esc(p.icon || p.name[0].toUpperCase())}</span><span>${esc(p.name)}</span></button>`).join('');
  htmlIfChanged('page', ui`<div class="page-intro"><h2>Messages privés</h2><p>Des discussions hors de tout projet, chacune dans son propre espace de travail et sans mémoire de projet : avec un agent de votre bibliothèque, comme on écrit à une personne, ou avec l’IA de votre choix.</p>
    <div class="row-actions"><button class="primary" data-shell-action="new-dm">＋ Nouveau message</button><button class="secondary" data-view="agents">☰ Bibliothèque d’agents</button></div></div>
    ${agents ? ui`<h3>Écrire à un agent</h3><div class="dm-agents">${agents}</div>` : ''}
    <h3>Discussions</h3><div class="dm-list">${cards || ui('<div class="empty-state">Aucune discussion pour l’instant.</div>')}</div>`);
}
async function newDirectMessageDialog() {
  shell.profilesAt = 0;
  await loadProfiles();
  const agents = shell.profiles.filter(p => !p.archived).map(p => ui`<li class="agent-choice"><span class="member-avatar">${esc(p.icon || p.name[0].toUpperCase())}</span><span><b>${esc(p.name)}</b> <small>${esc((p.description || '').slice(0, 90))}</small></span><button type="button" class="secondary" data-profile-dm="${esc(p.id)}">Écrire</button></li>`).join('');
  openDialog(ui('Nouveau message privé'), ui`<p class="field-help">Hors de tout projet : un espace de travail isolé, sans mémoire de projet.</p>
    <h3>À un agent de la bibliothèque</h3><p class="field-help">Il répond avec ses consignes, son connecteur et son modèle, dans la révision actuelle, figée pour cette discussion.</p>
    <ul class="agent-choices">${agents || ui('<li class="muted">Aucun profil actif. Créez-en un dans la bibliothèque.</li>')}</ul>
    <h3>Discussion libre</h3><p class="field-help">Avec l’IA et le modèle de votre choix, sans profil.</p>
    <button type="button" class="secondary" id="new-free-conversation">＋ Discussion libre</button>`, null);
}

// --- messages, grouped by author like Discord ---------------------------------------------------------
// In an agent's conversation the author is the agent itself — its name, icon and role — not the connector.
function messageAuthor(m) {
  if (m.role === 'user') return {key: 'user', name: ui('Vous'), initial: 'V', role: 'user'};
  const detail = state.detail || {};
  const member = detail.member_id && (shell.channels[detail.project_id]?.members || []).find(x => x.id === detail.member_id);
  if (member) return {key: 'member:' + member.id, name: member.name, initial: member.icon || member.name[0], role: member.role};
  const profile = detail.profile_id && shell.profiles.find(x => x.id === detail.profile_id);
  if (profile) return {key: 'profile:' + profile.id, name: profile.name, initial: profile.icon || profile.name[0], role: profile.role};
  const name = agentName(m.connector) || 'Agent';
  return {key: 'connector:' + m.connector, name, initial: name[0], role: 'agent'};
}
function messageGrouped(messages, index) {
  const m = messages[index], previous = messages[index - 1];
  if (!previous || previous.role === 'failure' || m.role === 'failure') return false;
  return messageAuthor(previous).key === messageAuthor(m).key && (m.model || '') === (previous.model || '')
    && new Date(m.created_at) - new Date(previous.created_at) < 7 * 60 * 1000;
}

// --- the task a conversation works on --------------------------------------------------------------
// An agent launched on a card works in a conversation tied to it: the card stays visible at the top of the thread.
shell.tasks = {};
function taskBannerHTML() {
  const id = state.detail?.task_id;
  if (!id) return '';
  const cached = shell.tasks[id];
  if (!cached || Date.now() - cached.at > 5000) loadTaskBanner(id, state.detail.project_id);
  const task = cached?.task;
  if (!task) return ui('<div class="task-banner"><small>Carte de tâche…</small></div>');
  return ui`<div class="task-banner status-${esc(task.status)}"><span class="status ${esc(task.status)}">${esc(task.status_label)}</span>
    <div class="task-banner-text"><b>${esc(task.objective)}</b><small>Carte de tâche · responsable ${esc(task.assignee || '—')} · ${task.reports?.length || 0} rapport(s)${task.executions?.some(e => e.running) ? ui(' · exécution en cours') : ''}</small></div>
    <button type="button" class="secondary" data-task-open="${esc(task.id)}">Ouvrir la carte</button></div>`;
}
async function loadTaskBanner(id, projectId) {
  shell.tasks[id] = {...(shell.tasks[id] || {}), at: Date.now()};
  try {
    const task = await action('task_get', {project_id: projectId, id});
    const changed = JSON.stringify(task) !== JSON.stringify(shell.tasks[id].task);
    shell.tasks[id] = {task, at: Date.now()};
    if (changed && state.view === 'chat' && state.detail?.task_id === id) renderMessages();
  } catch (error) { /* the card may have been deleted; the thread stays readable */ }
}

// --- conversation tools, on each message ---------------------------------------------------------------------
function messageById(id) { return (state.detail?.messages || []).find(m => m.id === id); }
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return; } catch (error) { /* the desktop window may refuse: fall back */ }
  const area = document.createElement('textarea');
  area.value = text; document.body.append(area); area.select(); document.execCommand('copy'); area.remove();
}
document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button) return;
  const d = button.dataset;
  try {
    if (d.msgReply) {
      const m = messageById(d.msgReply), input = $('instruction');
      const excerpt = m.content.length > 600 ? m.content.slice(0, 600) + '…' : m.content;
      const quote = '> ' + messageAuthor(m).name + ' :\n' + excerpt.split('\n').map(line => '> ' + line).join('\n') + '\n\n';
      input.value = quote + input.value; input.focus(); input.setSelectionRange(input.value.length, input.value.length);
      rememberDraft(); fitInstruction();
    }
    if (d.msgCopy) { await copyText(messageById(d.msgCopy).content); toast(ui('Message copié.')); }
    if (d.msgPin) {
      const m = messageById(d.msgPin);
      await action('save_memory', {project_id: state.project, content: m.content.slice(0, 8000), source_ids: [m.id], category: ui('Épinglé')});
      shell.fetchedAt[state.project] = 0;
      toast(ui('Épinglé. La note reste à valider dans Mémoire avant d’être transmise aux agents.'));
    }
  } catch (error) { fail(error); }
});
document.addEventListener('change', e => {
  if (e.target.dataset?.select) e.target.closest('.message')?.classList.toggle('in-context', e.target.checked);
});

function openChannel(tab) {
  if ($('dialog').open) $('dialog').close();
  state.projectTab = tab;
  $('page')._rendered = null;
  showView('project');
}

async function agentChatDialog() {
  const data = shell.channels[state.project] || await action('project_channels', {project_id: state.project});
  const library = (await action('agent_profile_list')).profiles.filter(p => !p.archived);
  const members = data.members.map(m => ui`<li class="agent-choice">${avatarHTML(m)}<span><b>${esc(m.name)}</b> <small>${esc(m.role_label)} · ${esc(m.state_label)}</small></span><button type="button" class="secondary" data-member-chat="${esc(m.id)}">Discuter</button></li>`).join('');
  const profiles = library.map(p => ui`<li class="agent-choice"><span class="member-avatar">${esc(p.icon || p.name[0].toUpperCase())}</span><span><b>${esc(p.name)}</b> <small>${esc(p.description || '').slice(0, 90)}</small></span><button type="button" class="secondary" data-profile-chat="${esc(p.id)}">Solliciter</button></li>`).join('');
  openDialog(ui('Discuter avec un agent'), ui`
    <h3>Membres de l’équipe</h3>
    <p class="field-help">Sa conversation d’affectation : il y travaille avec sa révision figée, ses réglages locaux et sa mémoire dans ce projet.</p>
    <ul class="agent-choices">${members || ui('<li class="muted">Aucun membre actif dans ce projet.</li>')}</ul>
    <h3>Profils de la bibliothèque</h3>
    <p class="field-help">Un spécialiste sollicité directement, sans l’ajouter à l’équipe ni passer par un lead : une nouvelle conversation dans ce projet, avec la révision actuelle du profil figée pour cette conversation.</p>
    <ul class="agent-choices">${profiles || ui('<li class="muted">Aucun profil actif dans la bibliothèque.</li>')}</ul>`, null);
}

function memberDialog(id) {
  const member = shell.channels[state.project]?.members.find(m => m.id === id);
  if (!member) return;
  openDialog(member.name, ui`<div class="member-card">${avatarHTML(member, true)}<div>
      <p><b>${esc(member.role_label)}</b> · ${esc(member.state_label)}</p>
      <p class="field-help">${esc(agentName(member.connector) || member.connector || ui('Connecteur non renseigné'))}${member.model ? ' · ' + esc(member.model) : ''}${member.overridden ? ui(' · réglages locaux appliqués à cette affectation') : ''}</p>
      ${member.last_signal ? ui`<p class="field-help">Dernier signal enregistré : ${date(member.last_signal)}</p>` : ''}</div></div>
    <div class="row-actions"><button type="button" class="primary" data-member-chat="${esc(member.id)}">Discuter</button><button type="button" class="secondary" data-channel="board">Board</button><button type="button" class="secondary" data-channel="team">Fiche dans l’équipe</button></div>`, null);
}

async function pinsHTML(project=state.project) {
  const r = await action('project_pins', {project_id: project});
  if(state.project!==project)return '';
  state.memory = r.pins.map(p => ({...p, source_ids: JSON.stringify(p.source_ids)}));
  return ui`<div class="page-intro"><h2>Épinglés</h2><p>Les messages proposés en mémoire depuis une conversation, avec leur origine. Une note non validée n’est pas transmise aux agents.</p></div>
    ${r.pins.map(p => ui`<article class="card memory-card"><div class="card-header"><span class="status ${p.validated ? 'succeeded' : 'queued'}">${p.validated ? ui('Validée') : ui('Proposée')}</span><small>${esc(p.category || '')} · ${date(p.created_at)}</small></div><div class="memory-text">${esc(p.content)}</div><div class="row-actions">${p.conversation_id ? `<button class="text-button" data-conversation="${esc(p.conversation_id)}"># ${esc(p.conversation)}</button>` : ui('<small class="muted">Conversation d’origine supprimée</small>')}<button class="text-button" data-memory-edit="${esc(p.id)}">Modifier</button></div></article>`).join('') || ui('<div class="empty-state">Rien d’épinglé. Dans une conversation, « ◇ Proposer en mémoire » sous un message l’ajoute ici.</div>')}`;
}

async function mediaHTML(project=state.project) {
  const r = await action('project_media', {project_id: project});
  return ui`<div class="page-intro"><h2>Médias</h2><p>Les fichiers joints aux conversations de ce projet, du plus récent au plus ancien.</p></div>
    <div class="media-grid">${r.media.map(m => `<div class="media-item">${mediaCard(m)}<button class="text-button" data-conversation="${esc(m.conversation_id)}"># ${esc(m.conversation)}</button></div>`).join('') || ui('<div class="empty-state">Aucun média joint dans ce projet.</div>')}</div>`;
}

// Captured first, so that the handlers of app.js already render the right shell when they switch view.
document.addEventListener('click', e => {
  const d = e.target.closest('button')?.dataset;
  if (d && (d.project || d.conversation || d.channel || d.space || d.assistant !== undefined)) state.home = false;
}, true);
document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button) return;
  const d = button.dataset;
  try {
    if (d.shellHome) { state.home = true; showView('home'); }
    if (d.shellAction === 'new-dm') await newDirectMessageDialog();
    if (d.channel) await openChannel(d.channel);
    if (d.assistant !== undefined) {
      const id = d.assistant || (await action('project_assistant', {project_id: state.project})).conversation_id;
      if (!d.assistant) { shell.fetchedAt = {}; await refresh(true); }
      await selectConversation(id);
    }
    if (d.assistantPrompt !== undefined) useAssistantPrompt(Number(d.assistantPrompt));
    if (d.shellMember) memberDialog(d.shellMember);
    if (d.shellAction === 'new-project') newProject();
    if (d.shellAction === 'agent-chat') await agentChatDialog();
    if (d.profileDm && $('dialog').open) $('dialog').close();
    if (d.profileChat) {
      const r = await action('profile_conversation', {project_id: state.project, profile_id: d.profileChat});
      if ($('dialog').open) $('dialog').close();
      await refresh(true);
      await selectConversation(r.id);
    }
    if (button.id === 'toggle-members') setRightPanel('members');
    if (button.id === 'settings-close') closeOverlay();
    if (button.id === 'open-pins') openChannel('pins');
  } catch (error) { fail(error); }
});

// Projects are reordered on the rail the same way as in the project tree.
document.addEventListener('dragover', e => { if (draggedItem?.kind === 'project' && e.target.closest('#server-rail')) e.preventDefault(); });
document.addEventListener('drop', async e => {
  if (draggedItem?.kind !== 'project' || !e.target.closest('#server-rail')) return;
  e.preventDefault();
  const item = draggedItem, target = e.target.closest('[data-project]');
  draggedItem = null;
  try { if (target && target.dataset.project !== item.id) await moveItem('project', item.id, 0, target.dataset.project); } catch (error) { fail(error); }
});

// The header search opens the history search, scoped to the project being viewed.
$('header-search').addEventListener('submit', e => {
  e.preventDefault();
  const text = $('header-search-input').value.trim(), project = shellHome() ? '' : state.project;
  showView('search');
  const form = $('search-form');
  if (!form) return;
  form.elements.namedItem('text').value = text;
  form.elements.namedItem('project_id').value = project || '';
  form.requestSubmit();
});

$('header-search-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); $('header-search').requestSubmit(); }
});

// One line by default, growing with the message like a chat input.
// Refitted only when the text or the available width changed, and never while the input is hidden.
// The assistant's first screen: starting points that fill the composer. You complete them and send.
const ASSISTANT_PROMPTS = [
  ['🔁', ui('Reprise d’un projet'), ui('Le dossier existe déjà : l’assistant le lit pour comprendre.'), ui('C’est une reprise de projet existant. Explore le dossier du projet pour comprendre ce qu’il contient (structure, technologies, documentation, état d’avancement), résume-moi ce que tu as compris et ce qui manque, puis propose une présentation du projet, des consignes pour ses agents et une équipe adaptée. ')],
  ['✨', ui('Nouveau projet'), ui('Vous décrivez ce que vous voulez faire.'), ui('C’est un nouveau projet. Voici ce que je veux faire : ')],
  ['👥', ui('Composer l’équipe'), ui('Rôles, profils de la bibliothèque, affectations.'), ui('Aide-moi à composer l’équipe de ce projet : propose les rôles, les profils à réutiliser ou à créer dans la bibliothèque, puis crée-les avec mon accord. ')],
  ['⚙', ui('Configurer le projet'), ui('Présentation, consignes, mémoire, méthodes.'), ui('Aide-moi à configurer ce projet : présentation, consignes pour les agents, mémoire de départ et méthodes utiles. ')]];
function assistantWelcomeHTML() {
  const project = state.data.projects.find(p => p.id === (state.detail?.project_id || state.project));
  return ui`<div class="welcome assistant-welcome"><div class="welcome-logo"><img src="/cyai-logo.png" width="64" height="64" alt=""></div><div class="eyebrow">ASSISTANT DU PROJET</div>
    <h2>Mettons <em>${esc(project?.name || ui('ce projet'))}</em> en place.</h2>
    <p>Dites à l’assistant s’il s’agit d’une reprise ou d’un nouveau projet. Il peut lire le dossier, proposer une présentation et des consignes, composer l’équipe et préparer les premières cartes. Il propose ; chaque création passe par votre autorisation. Choisissez votre IA en bas, puis un point de départ — ou écrivez directement.</p>
    <div class="welcome-cards">${ASSISTANT_PROMPTS.map(([glyph, title, help], i) => `<button class="welcome-card" data-assistant-prompt="${i}"><span>${glyph}</span>${esc(title)}<small>${esc(help)}</small></button>`).join('')}</div></div>`;
}
function useAssistantPrompt(index) {
  const prompt = ASSISTANT_PROMPTS[index], box = $('instruction');
  if (!prompt || !box) return;
  box.value = prompt[3];
  box.dispatchEvent(new Event('input', {bubbles: true}));
  box.focus();
  box.setSelectionRange(box.value.length, box.value.length);
}
function fitInstruction() {
  const input = $('instruction'), key = input.value + '|' + input.offsetWidth;
  if (!input.offsetWidth || key === shell.fitted) return;
  shell.fitted = key;
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 220) + 'px';
}
window.addEventListener('resize', fitInstruction);
document.addEventListener('input', e => { if (e.target.id === 'instruction') fitInstruction(); });
