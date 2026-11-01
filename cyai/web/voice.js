// Voice in conversations. The microphone opens only on your click (🎙 for a dictation, 🗣 for a direct discussion), the answers are
// read only when you switch the reading on. A dictation is sent like a typed message: same agent, model and context
// as the composer.
const voiceUI = {state: null, timer: null, taken: '', pendingSend: null, fromVoice: false, pressed: 0, startedByPress: false, jobsTimer: null, polling: false};
const voicePhases = {listening: ui('● Micro ouvert : parlez'), transcribing: ui('Transcription…'), pending: ui('Dictée prête'), speaking: ui('🔊 Lecture'),
  thinking: ui('Réponse en cours…'), approval: ui('Autorisation demandée dans la conversation'), idle: ui('Voix en veille')};

function voiceOn(v) {
  return !!v && (v.microphone_open || v.reading || v.talking || !!v.transcript || ['transcribing', 'speaking', 'listening', 'pending'].includes(v.phase));
}

function startVoicePoll() {
  if (!voiceUI.timer) voiceUI.timer = setInterval(voicePoll, 300);
  voicePoll();
}

function stopVoicePoll() {
  clearInterval(voiceUI.timer);
  voiceUI.timer = null;
}

async function voicePoll() {
  if (voiceUI.polling) return;
  voiceUI.polling = true;
  try { await voicePollOnce(); } finally { voiceUI.polling = false; }
}

async function voicePollOnce() {
  let v;
  try { v = await action('voice_state', {}); } catch (e) { stopVoicePoll(); return; }
  voiceUI.state = v;
  // The voice belongs to the conversation on screen: opening another one switches it off.
  if (v.conversation_id && v.conversation_id !== state.conversation) {
    voiceUI.pendingSend = null;
    try { await action('voice_off', {}); } catch (e) { /* the next poll shows the real state */ }
    return;
  }
  await takeTranscript(v);
  paintVoice(v);
  if (!voiceOn(v) && !voiceUI.pendingSend) stopVoicePoll();
}

async function takeTranscript(v) {
  const t = v.transcript;
  if (voiceUI.pendingSend && !v.busy_mission) return sendDictation(voiceUI.pendingSend);
  if (!t || voiceUI.taken === t.id) return;
  voiceUI.taken = t.id;
  if (t.conversation_id !== state.conversation) return action('voice_transcript_done', {id: t.id});
  const input = $('instruction');
  if (!t.send) {
    input.value = (input.value.trim() ? input.value.trimEnd() + ' ' : '') + t.text;
    voiceUI.fromVoice = true;
    rememberDraft(); fitInstruction(); input.focus();
    return action('voice_transcript_done', {id: t.id});
  }
  if (v.busy_mission) {
    // One answer at a time per conversation: the dictation waits for the end of the current one.
    input.value = t.text;
    voiceUI.fromVoice = true;
    voiceUI.pendingSend = t;
    return;
  }
  return sendDictation(t);
}

async function sendDictation(t) {
  voiceUI.pendingSend = null;
  $('instruction').value = t.text;
  voiceUI.fromVoice = true;
  $('composer').requestSubmit();
  try { await action('voice_transcript_done', {id: t.id}); } catch (e) { fail(e); }
}

function paintVoice(v) {
  if (voiceUI.preview && $('voice-test-result')) {
    $('voice-test-result').textContent = v.error || v.loading || (v.phase === 'speaking' ? ui('Synthèse / lecture en cours…') : ui('Essai terminé.'));
    const busy = !v.error && (v.phase === 'speaking' || !!v.loading);
    const button = $('voice-form')?.querySelector('[data-voice-test]');
    if (button) { button.disabled = busy; button.textContent = busy ? ui('Synthèse / lecture en cours…') : ui('Enregistrer et écouter la voix'); }
    if (!busy) voiceUI.preview = false;
  }
  const mic = $('voice-mic'), talk = $('voice-direct'), read = $('voice-read'), bar = $('voice-bar');
  if (!mic || !bar) return;
  mic.classList.toggle('listening', !!v?.microphone_open && v.listening_for === 'dictation');
  mic.style.setProperty('--voice-level', String(v?.level || 0));
  mic.title = v?.microphone_open && v.listening_for === 'dictation' ? ui('Micro ouvert : cliquez pour terminer la dictée') : ui('Dicter dans la saisie : le texte arrive dans la zone de saisie, vous relisez puis envoyez. Cliquez pour parler, recliquez pour terminer (ou maintenez appuyé).');
  talk.classList.toggle('on', !!v?.talking);
  talk.classList.toggle('listening', !!v?.talking && !!v.microphone_open);
  talk.style.setProperty('--voice-level', String(v?.talking ? v.level || 0 : 0));
  talk.setAttribute('aria-pressed', v?.talking ? 'true' : 'false');
  talk.title = v?.talking ? ui('Discussion directe en cours : cliquez pour l’arrêter') : ui('Discussion directe : parlez, votre phrase part toute seule, la réponse est lue à voix haute, puis le micro se rouvre. Sans toucher au clavier. Recliquez pour arrêter.');
  read.classList.toggle('on', !!v?.reading);
  read.textContent = v?.reading ? '🔊' : '🔈';
  read.title = v?.reading ? ui('Désactiver la lecture des réponses') : ui('Lire les réponses à voix haute');
  read.setAttribute('aria-label',read.title);
  read.setAttribute('aria-pressed',v?.reading?'true':'false');
  const visible = voiceOn(v) || !!voiceUI.pendingSend || !!v?.notice || !!v?.error;
  bar.hidden = !visible;
  if (!visible) { bar.innerHTML = ''; return; }
  const label = v.phase === 'speaking' && v.speaking ? '🔊 ' + v.speaking : voicePhases[v.phase] || '';
  const buttons = [];
  if (v.microphone_open && v.listening_for === 'dictation') buttons.push(ui('<button type="button" class="secondary" data-voice="dictate-stop">Terminer la dictée</button><button type="button" class="text-button" data-voice="dictate-cancel">Annuler</button>'));
  if (v.phase === 'speaking' || v.speaking) buttons.push(ui('<button type="button" class="secondary" data-voice="stop">Arrêter la voix</button>'));
  if (v.talking && !v.microphone_open && v.phase !== 'transcribing') buttons.push(ui('<button type="button" class="secondary" data-voice="resume-listening">Reprendre la parole</button>'));
  if (v.diagnostics?.length) buttons.push(ui('<button type="button" class="text-button" data-voice="timings">Mesures vocales</button>'));
  if (v.talking) buttons.push(ui('<button type="button" class="secondary" data-voice="talk-off">Arrêter la discussion directe</button>'));
  if (voiceOn(v)) buttons.push(ui('<button type="button" class="text-button" data-voice="off">Tout couper</button>'));
  const pending = voiceUI.pendingSend ? ui`<div class="voice-pending"><span>Message vocal en attente : « ${esc(voiceUI.pendingSend.text)} ». Il partira à la fin de la réponse en cours.</span><button type="button" class="secondary" data-voice="cancel-and-send">Annuler la réponse et envoyer</button><button type="button" class="text-button" data-voice="keep">Ne pas envoyer</button></div>` : '';
  const html = `<div class="voice-line"><span class="voice-phase ${v.microphone_open ? 'open' : ''}">${esc(label)}</span>${v.microphone_open ? '<span class="voice-meter"><span></span></span>' : ''}<span class="voice-actions">${buttons.join('')}</span></div>${v.partial ? `<p class="voice-partial">${esc(v.partial.trim())}…</p>` : ''}${v.loading ? `<p class="voice-note">${esc(v.loading)}</p>` : ''}${pending}${v.notice ? `<p class="voice-note">${esc(v.notice)}</p>` : ''}${v.error ? `<p class="voice-note error">${esc(v.error)}</p>` : ''}`;
  if (bar._html !== html) { bar.innerHTML = html; bar._html = html; }
  const meter = bar.querySelector('.voice-meter span');
  if (meter) meter.style.width = Math.round((v.level || 0) * 100) + '%';
}

async function voiceCommand(kind) {
  const v = voiceUI.state || {};
  try {
    if (kind === 'dictate-stop') await action('voice_dictate_stop', {});
    if (kind === 'dictate-cancel') await action('voice_dictate_stop', {cancel: true});
    if (kind === 'resume-listening') await action('voice_resume_listening', {conversation_id: state.conversation});
    if (kind === 'timings') openDialog(ui('Mesures vocales · événements récents'), ui`<p>Temps relatifs en millisecondes. Lecture = remise au pilote audio, pas mesure acoustique. Aucun enregistrement sonore dans ce journal.</p><pre>${esc(JSON.stringify(v.diagnostics || [], null, 2))}</pre>`, null);
    if (kind === 'stop') await action('voice_stop', {});
    if (kind === 'talk-off') await action('voice_conversation', {conversation_id: state.conversation, on: false});
    if (kind === 'off') { voiceUI.pendingSend = null; await action('voice_off', {}); }
    if (kind === 'cancel-and-send' && v.busy_mission) await action('cancel_mission', {mission_id: v.busy_mission});
    if (kind === 'keep' && voiceUI.pendingSend) { await action('voice_transcript_done', {id: voiceUI.pendingSend.id}); voiceUI.pendingSend = null; }
  } catch (e) { fail(e); }
  startVoicePoll();
}

function voiceFail(e) {
  // Something to install is not a failed execution: say what is missing and where to get it.
  if (!/Paramètres › Voix/.test(e.message || '')) return fail(e);
  openDialog(ui('La voix n’est pas encore prête'), ui`<p>${esc(e.message)}</p><p class="field-help">Les moteurs et modèles se téléchargent depuis leur source officielle ; rien n’est installé sans votre clic.</p>`,
    () => { state.settingsTab = 'voice'; showView('settings'); }, ui('Ouvrir Paramètres › Voix'));
}

async function startDictation() {
  if (!state.conversation) return toast(ui('Ouvrez ou créez d’abord une conversation.'));
  try { voiceUI.state = await action('voice_dictate', {conversation_id: state.conversation}); paintVoice(voiceUI.state); startVoicePoll(); }
  catch (e) { voiceUI.startedByPress = false; voiceFail(e); }
}

function bindVoice() {
  const mic = $('voice-mic');
  if (!mic || mic._bound) return;
  mic._bound = true;
  paintVoice(null);  // Titles of 🎙 and 🗣 before any use.
  // Click to start and click again to finish, or hold the button while you speak.
  mic.onpointerdown = async e => {
    if (e.button !== 0 || voiceUI.state?.microphone_open || voiceUI.state?.talking) return;
    voiceUI.pressed = Date.now(); voiceUI.startedByPress = true;
    await startDictation();
  };
  mic.onpointerup = async () => {
    if (voiceUI.startedByPress) {
      voiceUI.startedByPress = false;
      if (Date.now() - voiceUI.pressed > 600) await voiceCommand('dictate-stop');
      return;
    }
    if (voiceUI.state?.microphone_open) await voiceCommand('dictate-stop');
  };
  mic.onclick = async e => {
    if (e.detail !== 0) return; // Pointer clicks are handled above; this is the keyboard (Entrée, Espace).
    if (voiceUI.state?.microphone_open) await voiceCommand('dictate-stop'); else await startDictation();
  };
  $('voice-direct').onclick = async () => {
    if (!state.conversation) return toast(ui('Ouvrez ou créez d’abord une conversation.'));
    try { voiceUI.state = await action('voice_conversation', {conversation_id: state.conversation, on: !voiceUI.state?.talking}); paintVoice(voiceUI.state); startVoicePoll(); }
    catch (e) { voiceFail(e); }
  };
  $('voice-read').onclick = async () => {
    if (!state.conversation) return toast(ui('Ouvrez ou créez d’abord une conversation.'));
    try { voiceUI.state = await action('voice_read', {conversation_id: state.conversation, on: !voiceUI.state?.reading}); paintVoice(voiceUI.state); startVoicePoll(); }
    catch (e) { fail(e); }
  };
  $('voice-bar').addEventListener('click', e => { const b = e.target.closest('[data-voice]'); if (b) voiceCommand(b.dataset.voice); });
  document.addEventListener('click', async e => {
    const b = e.target.closest('[data-msg-speak]');
    if (!b) return;
    try { await action('voice_read_message', {message_id: b.dataset.msgSpeak}); startVoicePoll(); } catch (err) { fail(err); }
  });
}

// ----- Paramètres › Voix -----
const voiceKinds = {stt_engine: ui('Moteurs de dictée'), tts_engine: ui('Moteurs de voix locales'), stt_runtime: ui('Dictée Whisper · moteur'), stt_model: ui('Modèles Whisper'), tts_runtime: ui('Voix légères · moteur Piper'), tts_voice: ui('Voix Piper')};
function voiceSize(n) { return n >= 1024 ** 3 ? (n / 1024 ** 3).toFixed(2) + ui(' Go') : Math.max(1, Math.round(n / 1024 ** 2)) + ui(' Mo'); }

function voiceItemHTML(item) {
  const record = item.record || {};
  const status = item.installed ? ui('✓ Installé') + (record.version ? ' · ' + esc(record.version) : '') + (record.published_sha === false ? ui(' · empreinte calculée ici, la source n’en publie pas') : '') + (item.in_use ? ui(' · utilisé') : '') : ui('Non installé');
  return ui`<article data-voice-item="${esc(item.id)}" class="card voice-item" data-voice-kind="${esc(item.kind)}" data-language="${esc(item.language || '')}" data-quality="${esc(item.quality || '')}" data-name="${esc(item.name.toLowerCase())}"><strong>${esc(item.name)}</strong><p>${esc(item.note || '')}</p><p class="field-help">${item.approx ? '≈ ' : ''}${voiceSize(item.bytes)} · Licence : ${esc(item.license)} · <a href="${esc(item.source)}" target="_blank" rel="noopener">Source</a>${item.sha256 ? ' · SHA-256 ' + esc(item.sha256.slice(0, 12)) + '…' : ''}</p><p data-voice-job role="status">${status}</p><div class="row-actions">${item.installed ? ui`<button type="button" class="secondary" data-voice-verify="${esc(item.id)}">Vérifier</button><button type="button" class="text-button danger" data-voice-remove="${esc(item.id)}">Supprimer</button>` : ui`<button type="button" class="primary" data-voice-install="${esc(item.id)}">Télécharger</button>`}</div></article>`;
}

async function renderVoiceSettings(refreshVoices) {
  try { await renderVoiceSettingsContent(refreshVoices); }
  catch (error) {
    const host = $('voice-settings');
    if (state.view !== 'settings' || state.settingsTab !== 'voice' || !host) return;
    host.innerHTML = ui`<h3>Voix</h3><p class="voice-note error" role="alert">Impossible d’afficher les réglages : ${esc(error.message || String(error))}</p><button type="button" class="secondary" data-voice-retry>Réessayer</button>`;
    host.querySelector('[data-voice-retry]').onclick = () => renderVoiceSettings(refreshVoices);
  }
}

async function renderVoiceSettingsContent(refreshVoices) {
  const request = voiceUI.settingsRequest = (voiceUI.settingsRequest || 0) + 1;
  const [s, c] = await Promise.all([action('voice_settings', {refresh: !!refreshVoices}), action('voice_catalog', {})]);
  const host = $('voice-settings');
  if (request !== voiceUI.settingsRequest || state.view !== 'settings' || state.settingsTab !== 'voice' || !host) return;
  const v = s.settings;
  const options = (list, selected) => list.map(([value, label]) => `<option value="${esc(value)}" ${value === selected ? 'selected' : ''}>${esc(label)}</option>`).join('');
  let voiceGroups = [...new Set(s.voices.map(x => x.backend))];
  const voiceOptions = (selected, empty) => (selected && !s.voices.some(x=>x.key===selected) ? ui`<option value="${esc(selected)}" selected>Voix enregistrée · ${esc(selected)} (à vérifier)</option>` : '') + `<option value="">${esc(empty)}</option>` + voiceGroups.map(group => `<optgroup label="${esc(group)}">${s.voices.filter(x => x.backend === group).map(x => `<option class="${x.memory?.warning ? 'memory-warning' : ''}" value="${esc(x.key)}" ${x.key === selected ? 'selected' : ''} ${x.available === false ? 'disabled' : ''}>${x.memory?.warning ? '⚠ ' : ''}${esc(x.name)} · ${esc(x.language)} · ${esc(ui.system(x.memory?.label || ''))}${x.available === false ? ui(' (installez le moteur Piper)') : ''}</option>`).join('')}</optgroup>`).join('');
  const models = c.items.filter(i => i.kind === 'stt_model' && i.installed).map(i => [i.id, i.name]);
  const devices = (list, selected, empty) => `<option value="">${esc(empty)}</option>` + list.map(name => `<option value="${esc(name)}" ${name === selected ? 'selected' : ''}>${esc(name)}</option>`).join('') + (selected && !list.includes(selected) ? `<option value="${esc(selected)}" selected>${esc(selected)} (absent)</option>` : '');
  host.innerHTML = ui`<h3>Voix</h3><p>Dictée et lecture des réponses, entièrement sur cet ordinateur. Le micro ne s’ouvre que lorsque vous cliquez sur 🎙 (dictée à relire) ou sur 🗣 (discussion directe) ; les réponses ne sont lues que si vous activez la lecture. Le son dicté est transcrit puis oublié, il n’est jamais enregistré.</p>
  <p class="field-help">${s.windows_pending ? ui('<span id="voice-windows-detection">Détection des voix Windows en arrière-plan…</span> <button type="button" class="text-button" data-voice-detected-refresh>Actualiser la liste</button><br>') : ''}<span id="voice-stt-status">Dictée : ${s.stt.ready ? ui('prête') : esc(ui.system(s.stt.reason))}</span></p>
  <form id="voice-form" class="fields">
    <h4>Dictée</h4>
    <div class="two-fields"><label>Micro<select name="input_device">${devices(s.inputs, v.input_device, ui('Micro par défaut de Windows'))}</select></label><label>Langue<select name="language">${options([['fr', ui('Français')], ['en', ui('Anglais')], ['auto', ui('Détection automatique')]], v.stt.language)}</select></label></div>
    <label>Moteur de dictée<select name="stt_engine">${options([['phonon', ui('Phonon · dictée légère sur CPU') + (s.engines.phonon ? '' : ui(' (à installer ci-dessous)'))], ['whisper', ui('Whisper : le texte arrive quand vous avez fini de parler')], ['kyutai', ui('Kyutai : les mots s’affichent pendant que vous parlez') + (s.engines.kyutai ? '' : ui(' (à installer ci-dessous)'))]], v.stt.engine)}</select></label>
    <div data-stt-options="phonon"><label>Modèle Phonon<select name="phonon_model">${options([['phonon-2.5',ui('Phonon-2.5 · français et 24 autres langues')],['phonon-2',ui('Phonon-2 · anglais uniquement')]],v.stt.phonon_model || 'phonon-2.5')}</select></label><p class="field-help">CPU sous Windows. Les poids font environ 156–158 Mo par modèle ; Python et PyTorch sont installés séparément. La transcription apparaît après la phrase. Phonon-2.5 détecte la langue depuis l’audio.</p></div>
    <div class="two-fields"><label>Modèle Whisper<select name="stt_model">${options([['', ui('Le plus précis des modèles installés')], ...models], v.stt.model)}</select></label><label>Calcul<select name="device">${options([['auto', ui('Automatique : processeur si un modèle local occupe la carte graphique')], ['cpu', ui('Processeur')], ['gpu', ui('Carte graphique NVIDIA')]], v.stt.device)}</select></label></div>
    <div class="two-fields"><label>Fin de phrase en conversation vocale (silence, en ms)<input type="number" name="silence_ms" min="500" max="4000" step="100" value="${v.silence_ms}"></label><label>Fermer le micro après (secondes sans parole, 0 = écoute continue)<input type="number" name="listen_timeout_s" min="0" max="86400" value="${v.listen_timeout_s}"></label></div>
    <label><span><input type="checkbox" name="dictation_send" ${v.dictation_send ? 'checked' : ''}> Envoyer une dictée dès qu’elle est transcrite (sinon elle reste dans la saisie, à relire)</span></label>
    <p class="field-help">Une pause plus longue évite de couper une hésitation ; elle ajoute la même attente avant l’envoi. Le seuil actuel est conservé : ajustez-le à votre rythme.</p>
    <label><span><input type="checkbox" name="barge_in" ${v.barge_in ? 'checked' : ''}> Interrompre la lecture quand je parle (casque requis)</span></label>
    <p class="field-help">Ce mode garde le micro ouvert pendant la réponse. Sans annulation d’écho acoustique, les haut-parleurs risquent de déclencher une interruption. La voix s’arrête ; le travail de l’agent continue, et votre nouvelle phrase attend ou peut annuler la réponse avec le bouton prévu.</p>
    <h4>Lecture des réponses</h4>
    <p class="field-help">Mémoire indicative, hors autres modèles. ${esc(s.hardware?.gpu_name || ui('GPU NVIDIA non détecté'))} : ${s.hardware?.gpu_free_gib?.toFixed(1) || '?'} Gio libres / ${s.hardware?.gpu_total_gib?.toFixed(1) || '?'} Gio. Orange : marge faible, chargement possible. Rouge : VRAM totale inférieure au minimum estimé. Ces estimations ne bloquent pas le lancement.</p><div class="two-fields"><label>Voix<select name="voice">${voiceOptions(v.tts.voice, ui('Automatique : une voix dans la langue de la dictée'))}</select></label><label>Sortie audio<select name="output_device">${devices(s.outputs, v.output_device, ui('Sortie par défaut de Windows'))}</select></label></div>
    <p id="voice-memory-choice" role="status"></p><div class="two-fields"><label data-voice-speed>Vitesse (1 = normale)<input type="number" name="speed" min="0.5" max="2" step="0.05" value="${v.tts.speed}"></label><label>Volume (%)<input type="number" name="volume" min="0" max="100" value="${v.tts.volume}"></label></div>
    <p id="voice-capabilities" class="field-help" aria-live="polite"></p>
    <div data-engine-options="pocket"><label>Variation Pocket TTS — température (vide = recommandation du modèle)<input type="number" name="pocket_temperature" min="0" max="2" step="0.05" value="${v.tts.pocket_temperature ?? ''}" placeholder="Automatique"></label><p class="field-help">Une valeur plus élevée diversifie la voix, mais peut réduire la qualité. Ce réglage ne commande pas une émotion. La vitesse reste naturelle.</p></div>
    <div data-engine-options="piper" class="two-fields"><label>Variation sonore Piper (vide = modèle)<input type="number" name="piper_noise_scale" min="0" max="2" step="0.05" value="${v.tts.piper_noise_scale ?? ''}" placeholder="Automatique"></label><label>Variation du rythme Piper (vide = modèle)<input type="number" name="piper_noise_w" min="0" max="2" step="0.05" value="${v.tts.piper_noise_w ?? ''}" placeholder="Automatique"></label></div>
    <div data-engine-options="qwen"><label>Description ou consigne de style Qwen<textarea name="qwen_instruct" rows="3" placeholder="A warm adult voice, soft and playful, speaking calmly.">${esc(v.tts.qwen_instruct || '')}</textarea></label><p class="field-help">VoiceDesign : décrivez la voix à créer. CustomVoice : indiquez le ton de la voix choisie. Base/clonage : cette consigne ne s’applique pas ; le timbre vient de l’échantillon. Français parlé, consigne en anglais conseillée. La synthèse attend chaque phrase complète.</p></div>
    <div data-engine-options="chatterbox"><label>Intensité expressive Chatterbox (0 à 2)<input name="chatterbox_exaggeration" type="number" min="0" max="2" step="0.05" value="${v.tts.chatterbox_exaggeration}"></label><label>Guidage CFG (0 à 1)<input name="chatterbox_cfg" type="number" min="0" max="1" step="0.05" value="${v.tts.chatterbox_cfg}"></label><label>Variation Chatterbox (température)<input name="chatterbox_temperature" type="number" min="0.05" max="2" step="0.05" value="${v.tts.chatterbox_temperature}"></label><p class="field-help">L’intensité expressive ne sélectionne pas une émotion précise. Clonage depuis Mes voix ; génération par phrase.</p></div>
    <div data-engine-options="fish"><label>Style Fish<select name="fish_style">${options([['',ui('Naturel')],['whisper',ui('Chuchoté')],['excited',ui('Enthousiaste')],['angry',ui('En colère')],['sad',ui('Triste')],['happy',ui('Joyeux')]],v.tts.fish_style || '')}</select></label><label>Variation Fish (température)<input name="fish_temperature" type="number" min="0.1" max="1" step="0.05" value="${v.tts.fish_temperature}"></label><label>Diversité Fish (top-p)<input name="fish_top_p" type="number" min="0.1" max="1" step="0.05" value="${v.tts.fish_top_p}"></label><p class="field-help">S2 Pro recommande 24 Go de VRAM : libérez les autres modèles GPU si nécessaire. Sans référence, le timbre peut varier. Une référence exige sa transcription exacte. Audio progressif, sans compilation Triton sous Windows.</p></div>
    <p class="field-help">Les réglages propres à chaque moteur s’appliquent aussi aux voix attribuées aux agents. Un seul de ces nouveaux moteurs est conservé chargé à la fois. Le volume fonctionne avec tous ; les émotions demandées restent à écouter et à valider.</p>
    <label>Texte pour essayer la voix<textarea name="preview_text" rows="2">Bonjour, je suis la voix de CyAI. Prenons le temps de discuter ensemble.</textarea></label>
    <label>Lire au plus (caractères par réponse, 0 = tout)<input type="number" name="read_limit" min="0" max="20000" step="100" value="${v.read_limit}"></label>
    ${Object.values(Object.fromEntries(s.voices.filter(x=>x.memory?.warning).map(x=>[x.backend,x]))).map(x=>`<p class="memory-warning ${x.memory.severity === 'danger' ? 'memory-danger' : ''}">⚠ ${esc(x.backend)} : ${esc(ui.system(x.memory.label))} — ${esc(ui.system(x.memory.warning))}. ${esc(ui.system(x.memory.basis))}</p>`).join('')}<details><summary>Voix par agent</summary><p class="field-help">Chaque réponse est lue avec la voix de son agent ; sans choix, avec la voix ci-dessus.</p>${s.connectors.map(id => `<label>${esc(agentName(id))}<select name="cv:${esc(id)}">${voiceOptions((v.connector_voices || {})[id] || '', ui('Voix générale'))}</select></label>`).join('')}</details>
    <div class="row-actions"><button class="primary">Enregistrer</button><button type="button" class="secondary" data-voice-test>Enregistrer et écouter la voix</button><button type="button" class="secondary" data-voice-preview-stop>Arrêter la lecture</button><button type="button" class="secondary" data-voice-mic-test>Tester le micro (3 s)</button><button type="button" class="text-button" data-voice-refresh>Actualiser les voix Windows</button></div>
    <p id="voice-test-result" class="field-help" aria-live="polite"></p>
  </form>
  <details class="voice-section"><summary>Mes voix — clonage et références</summary>
  <p>Pocket, Qwen Base, Chatterbox et Fish peuvent utiliser un échantillon de référence lorsque leurs modèles sont installés. Pour Fish, renseignez aussi les mots exacts prononcés. L’échantillon reste dans le dossier de données de CyAI. Utilisez uniquement votre voix ou celle d’une personne qui vous a donné son accord.</p>
  <div class="card-grid">${s.samples.map(sample => ui`<article class="card voice-sample"><strong>${esc(sample.name)}</strong><p class="field-help">${sample.seconds} s · créée le ${date(sample.created_at)}</p><div class="row-actions"><button type="button" class="secondary" data-voice-sample-use="${esc(sample.id)}">Utiliser cette voix</button><button type="button" class="secondary" data-voice-sample-text="${esc(sample.id)}">Transcription</button><button type="button" class="text-button danger" data-voice-sample-delete="${esc(sample.id)}">Supprimer</button></div></article>`).join('') || ui('<p class="field-help">Aucune voix copiée.</p>')}</div>
  <form id="voice-sample-form" class="fields"><div class="two-fields"><label>Nom de la voix<input name="name" maxlength="60" placeholder="Ma voix" required></label><label>Durée de l’enregistrement (secondes)<input type="number" name="seconds" min="5" max="30" value="12"></label></div>
    <label><span><input type="checkbox" name="consent" required> Cette voix est la mienne, ou la personne enregistrée m’a donné son accord.</span></label>
    <div class="row-actions"><button type="button" class="secondary" data-voice-sample="record" ${['pocket','qwen','chatterbox','fish'].some(k=>s.engines[k]) ? '' : 'disabled'}>Enregistrer au micro</button><button type="button" class="secondary" data-voice-sample="import" ${['pocket','qwen','chatterbox','fish'].some(k=>s.engines[k]) ? '' : 'disabled'}>Importer un WAV</button></div>
    ${['pocket','qwen','chatterbox','fish'].some(k=>s.engines[k]) ? '' : ui('<p class="field-help">Installez un moteur avec clonage ci-dessous.</p>')}<p id="voice-sample-result" class="field-help" aria-live="polite"></p></form>
  <form id="voice-token-form" class="fields"><p class="field-help">La copie de voix utilise la version du modèle dont Kyutai demande d’accepter les conditions : acceptez-les sur <a href="https://huggingface.co/kyutai/pocket-tts" target="_blank" rel="noopener">huggingface.co/kyutai/pocket-tts</a>, créez un jeton de lecture sur <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener">huggingface.co/settings/tokens</a>, puis indiquez-le ici. Il est chiffré par Windows avec les autres secrets et n’est donné qu’au moteur de voix. Un jeton enregistré ne garantit pas l’accès : les droits du compte et les poids réellement chargés doivent permettre le clonage. Des poids déjà en cache peuvent fonctionner hors ligne. La première préécoute d’une voix clonée peut télécharger les poids autorisés ; le WAV reste local. L’import du WAV seul ne valide pas la synthèse : utilisez « Enregistrer et écouter la voix ».</p>
    <div class="two-fields"><label>Jeton Hugging Face ${s.hf_token ? ui('(enregistré)') : ''}<input type="password" name="token" autocomplete="new-password" placeholder="${s.hf_token ? ui('Laisser vide pour conserver') : 'hf_…'}"></label><span class="row-actions"><button class="secondary">Enregistrer le jeton</button>${s.hf_token ? ui('<button type="button" class="text-button danger" data-voice-token-clear>Oublier le jeton</button>') : ''}</span></div></form>
  </details><h4>Moteurs et modèles</h4><p class="field-help">Pour essayer les meilleurs : <b>Kyutai STT</b> pour la dictée en direct (carte graphique NVIDIA) et <b>Pocket TTS</b> pour les voix naturelles. Pour Whisper sur une carte NVIDIA : le moteur CUDA avec <b>Large v3 Turbo</b>.</p><p>Téléchargés depuis leur source officielle, vérifiés avec les empreintes publiées (MD5 pour le catalogue Piper ; SHA-256 calculée localement), et rangés dans ${esc(c.folder)} (moteurs : ${esc(c.runtimes_folder)}). Ils ne font jamais partie de l’installateur. Les voix installées dans Windows sont utilisables sans téléchargement. Progression : <button type="button" class="text-button" data-workspace-action="settings-tab" data-tab="downloads">Téléchargements</button>.</p>
  ${Object.entries(voiceKinds).map(([kind, title]) => `<h4>${esc(title)}</h4>${kind === 'tts_voice' ? ui`<div class="row-actions"><label>Langue<select id="piper-language">${options([['', ui('Toutes les langues')], ...[...new Set(c.items.filter(i=>i.kind==='tts_voice').map(i=>i.language))].sort().map(k=>[k,k])], voiceUI.piperLanguage ?? 'fr_FR')}</select></label><label>Qualité<select id="piper-quality">${options([['',ui('Toutes')],['x_low','x_low'],['low','low'],['medium','medium'],['high','high']],voiceUI.piperQuality || '')}</select></label><label>Rechercher<input id="piper-search" value="${esc(voiceUI.piperSearch || '')}" placeholder="Nom de voix"></label><button type="button" class="secondary" id="piper-refresh">Actualiser le catalogue officiel</button></div><p class="field-help">Un seul téléchargement par modèle multivoix : ses locuteurs seront ensuite proposés dans les voix des agents. Le catalogue reste disponible hors ligne.</p><p id="piper-count" class="field-help"></p>` : ''}<div class="card-grid">${c.items.filter(i => i.kind === kind).map(voiceItemHTML).join('')}</div>`).join('')}
  ${c.jobs.filter(j => ['queued', 'running'].includes(j.status)).length ? `<p class="field-help">${c.jobs.filter(j => ['queued', 'running'].includes(j.status)).map(j => esc(ui.system(j.name)) + (j.total ? ' · ' + Math.round(j.received / j.total * 100) + ' %' : '') + (j.detail ? ' · ' + esc(ui.system(j.detail)) : '')).join(' · ')}</p>` : ''}${c.jobs.filter(j => j.status === 'failed').map(j => `<p class="voice-note error">${esc(ui.system(j.name))} : ${esc(j.error || ui('échec'))}</p>`).join('')}`;
  host.querySelector('[data-voice-detected-refresh]')?.addEventListener('click', () => renderVoiceSettings());
  const filterPiper = () => {
    voiceUI.piperLanguage = $('piper-language').value;
    voiceUI.piperQuality = $('piper-quality').value;
    voiceUI.piperSearch = $('piper-search').value;
    let visible = 0;
    host.querySelectorAll('[data-voice-kind="tts_voice"]').forEach(card => {
      const show = (!voiceUI.piperLanguage || card.dataset.language === voiceUI.piperLanguage) && (!voiceUI.piperQuality || card.dataset.quality === voiceUI.piperQuality) && card.dataset.name.includes(voiceUI.piperSearch.toLowerCase());
      card.hidden = !show; card.style.display = show ? '' : 'none';
      if (show) visible++;
    });
    $('piper-count').textContent = visible + ui(' modèles affichés');
  };
  ['piper-language', 'piper-quality', 'piper-search'].forEach(id => $(id).oninput = filterPiper);
  filterPiper();
  $('piper-refresh').onclick = async () => {
    $('piper-refresh').disabled = true;
    try { await action('voice_piper_refresh', {}); toast(ui('Actualisation Piper en cours.')); watchVoiceJobs(); }
    catch (e) { fail(e); $('piper-refresh').disabled = false; }
  };
  const form = $('voice-form');
  const updateSTT = () => {
    const mode = form.elements.stt_engine.value, phonon = mode === 'phonon';
    const model = form.elements.phonon_model?.value || 'phonon-2.5', language = form.elements.language?.value || v.stt.language;
    const readiness = phonon ? model === 'phonon-2' && language === 'fr' ? ui('Phonon-2 est anglais uniquement : choisissez Phonon-2.5 pour le français.') : s.engines.phonon ? ui('Phonon sur CPU prêt.') : ui('Installez Phonon dans les moteurs de dictée ci-dessous.') : mode === v.stt.engine ? s.stt.ready ? ui('prête') : ui.system(s.stt.reason) : mode === 'kyutai' ? s.engines.kyutai ? ui('Kyutai prêt.') : ui('Installez Kyutai ci-dessous.') : ui('Sélectionnez le moteur et le modèle Whisper installés.');
    $('voice-stt-status').textContent = ui('Dictée : ') + readiness;
    form.querySelector('[data-stt-options="phonon"]').hidden = !phonon;
    form.elements.stt_model.closest('label').hidden = form.elements.device.closest('label').hidden = form.elements.stt_engine.value !== 'whisper';
  };
  form.elements.stt_engine.onchange = updateSTT;
  for (const name of ['language','phonon_model']) if (form.elements[name]) form.elements[name].onchange = updateSTT;
  updateSTT();
  const updateCapabilities = () => {
    const key = form.elements.voice.value;
    const engine = key.split(':')[0];
    const memory = s.voices.find(x => x.key === key)?.memory;
    $('voice-memory-choice').textContent = memory ? ui.system(memory.label) + (memory.warning ? ' — ⚠ ' + ui.system(memory.warning) : '') + '. ' + ui.system(memory.basis) : '';
    $('voice-memory-choice').className = memory?.warning ? 'memory-warning' + (memory.severity === 'danger' ? ' memory-danger' : '') : 'field-help';
    form.querySelector('[data-voice-speed]').hidden = ['pocket','qwen','chatterbox','fish'].includes(engine);
    form.querySelectorAll('[data-engine-options]').forEach(el => { el.hidden = el.dataset.engineOptions !== engine; el.querySelectorAll('input,textarea,select').forEach(input => input.disabled = el.hidden); });
    $('voice-capabilities').textContent = engine === 'qwen' ? ui('Qwen : style décrit pour Design/Custom ; référence audio pour Base. CUDA.') : engine === 'chatterbox' ? ui('Chatterbox : expression, guidage, température et référence audio. CUDA.') : engine === 'fish' ? ui('Fish S2 Pro : balises de style et référence audio transcrite. CUDA.') : engine === 'pocket' ? ui('Pocket TTS : volume, variation et clonage selon les poids disponibles. Pas de commande d’émotion ou de vitesse.') : engine === 'piper' ? ui('Piper : vitesse, volume, variation sonore et variation du rythme. Pas de clonage instantané.') : engine === 'windows' ? ui('Windows : vitesse et volume. Pas de clonage dans cette intégration.') : ui('Voix automatique : chaque moteur utilise uniquement ses propres réglages. Les champs vides conservent les valeurs du modèle.');
  };
  form.elements.voice.onchange = updateCapabilities;
  updateCapabilities();
  const saveVoiceForm = async () => {
    const f = new FormData(form), voices = {};
    for (const [key, value] of f.entries()) if (key.startsWith('cv:') && value) voices[key.slice(3)] = value;
    try {
      await action('voice_settings_save', {stt: {engine: f.get('stt_engine'), phonon_model: f.get('phonon_model'), model: f.get('stt_model'), language: f.get('language'), device: f.get('device')},
        tts: {voice: f.get('voice'), speed: Number(f.get('speed')), volume: Number(f.get('volume')), ...Object.fromEntries(['qwen_instruct','fish_style'].filter(k=>f.has(k)).map(k=>[k,f.get(k)])), ...Object.fromEntries(['chatterbox_exaggeration','chatterbox_cfg','chatterbox_temperature','fish_temperature','fish_top_p'].filter(k=>f.has(k)).map(k=>[k,Number(f.get(k))])), ...Object.fromEntries(['pocket_temperature', 'piper_noise_scale', 'piper_noise_w'].filter(k=>f.has(k)).map(k => [k, f.get(k) === '' ? null : Number(f.get(k))]))},
        input_device: f.get('input_device'), output_device: f.get('output_device'), silence_ms: Number(f.get('silence_ms')),
        listen_timeout_s: Number(f.get('listen_timeout_s')), read_limit: Number(f.get('read_limit')), dictation_send: f.has('dictation_send'), barge_in: f.has('barge_in'), connector_voices: voices});
    } catch (err) { throw err; }
  };
  form.onsubmit = async e => { e.preventDefault(); const b = e.submitter; if (b) { b.disabled = true; b.textContent = ui('Enregistrement…'); } try { await saveVoiceForm(); toast(ui('Réglages de la voix enregistrés.')); } catch (err) { fail(err); } finally { if (b) { b.disabled = false; b.textContent = ui('Enregistrer'); } } };
  form.querySelector('[data-voice-test]').onclick = async e => {
    if (!form.reportValidity()) return;
    const b = e.currentTarget; b.disabled = true; b.textContent = ui('Chargement de la voix…');
    $('voice-test-result').textContent = ui('Préparation du moteur et de la synthèse…');
    try { if (!form.reportValidity()) return; await saveVoiceForm(); await action('voice_test', {voice: new FormData(form).get('voice'), text: form.elements.preview_text.value}); $('voice-test-result').textContent = ui('Synthèse en cours…'); voiceUI.preview = true; startVoicePoll(); } catch (e) { $('voice-test-result').textContent = e.message; fail(e); } finally { if (!voiceUI.preview) { b.disabled = false; b.textContent = ui('Enregistrer et écouter la voix'); } }
  };
  form.querySelector('[data-voice-preview-stop]').onclick = async () => { try { await action('voice_stop', {}); startVoicePoll(); } catch (e) { fail(e); } };
  form.querySelector('[data-voice-mic-test]').onclick = async e => {
    const button = e.currentTarget; button.disabled = true; $('voice-test-result').textContent = ui('Micro ouvert pendant 3 secondes : parlez normalement…');
    try { const r = await action('voice_microphone_test', {}); $('voice-test-result').textContent = r.detail + ' (niveau ' + Math.round(r.peak * 100) + ' %)'; } catch (err) { $('voice-test-result').textContent = ''; fail(err); }
    finally { button.disabled = false; }
  };
  form.querySelector('[data-voice-refresh]').onclick = () => renderVoiceSettings(true);
  host.querySelectorAll('[data-voice-install]').forEach(b => b.onclick = async () => {
    b.disabled = true; b.textContent = ui('Démarrage…');
    try { await action('voice_install', {id: b.dataset.voiceInstall}); b.textContent = ui('En attente…'); toast(ui('Téléchargement ajouté aux opérations.')); watchVoiceJobs(); } catch (e) { fail(e); b.disabled = false; b.textContent = ui('Réessayer'); }
  });
  host.querySelectorAll('[data-voice-verify]').forEach(b => b.onclick = async () => {
    b.disabled = true; b.textContent = ui('Vérification…');
    try { const r = await action('voice_verify', {id: b.dataset.voiceVerify}); toast(r.detail); } catch (e) { fail(e); } finally { b.disabled = false; b.textContent = ui('Vérifier'); }
  });
  host.querySelectorAll('[data-voice-remove]').forEach(b => b.onclick = () => {
    const item = c.items.find(i => i.id === b.dataset.voiceRemove);
    openDialog(ui('Supprimer ') + item.name, ui`<p>Les fichiers de « ${esc(item.name)} » seront supprimés de cet ordinateur. Vous pourrez le télécharger de nouveau.</p>`, async () => { await action('voice_remove', {id: item.id}); renderVoiceSettings(); }, ui('Supprimer'));
  });
  const sampleForm = $('voice-sample-form');
  sampleForm.querySelectorAll('[data-voice-sample]').forEach(b => b.onclick = async () => {
    const f = new FormData(sampleForm), result = $('voice-sample-result');
    if (!f.has('consent')) return toast(ui('Cochez la case d’accord avant de créer une voix.'));
    b.disabled = true;
    result.textContent = b.dataset.voiceSample === 'record' ? ui`Micro ouvert pendant ${f.get('seconds')} secondes : lisez un texte à voix haute, normalement…` : ui('Choisissez un fichier WAV…');
    try {
      const r = await action(b.dataset.voiceSample === 'record' ? 'voice_sample_record' : 'voice_sample_import', {name: f.get('name') || ui('Ma voix'), consent: true, seconds: Number(f.get('seconds'))});
      if (r.cancelled) { result.textContent = ''; return; }
      toast(ui('Échantillon « ') + r.name + ui(' » enregistré. Choisissez la voix puis testez la synthèse.')); renderVoiceSettings();
    } catch (e) { result.textContent = ''; fail(e); } finally { b.disabled = false; }
  });
  host.querySelectorAll('[data-voice-sample-use]').forEach(b => b.onclick = () => {
    const selectedEngine = form.elements.voice.value.split(':')[0];
    const engine = ['pocket','qwen','chatterbox','fish'].includes(selectedEngine) ? selectedEngine : ['pocket','qwen','chatterbox','fish'].find(k=>s.engines[k]);
    const language = selectedEngine === 'pocket' ? form.elements.voice.value.split(':')[1] : (v.stt.language === 'en' ? 'english' : 'french_24l');
    form.elements.voice.value = `${engine}:${engine==='pocket'?language+':':''}clone:${b.dataset.voiceSampleUse}`;
    updateCapabilities(); form.elements.voice.focus(); toast(ui('Voix sélectionnée. Enregistrez ou écoutez pour appliquer.'));
  });
  host.querySelectorAll('[data-voice-sample-text]').forEach(b=>b.onclick=()=> { const sample=s.samples.find(x=>x.id===b.dataset.voiceSampleText); openDialog(ui('Transcription de la référence'), ui`<p>Écrivez exactement les mots prononcés dans l’échantillon. Nécessaire pour Fish ; facultatif pour Qwen.</p><label>Transcription<textarea name="reference_text" rows="4">${esc(sample.text||'')}</textarea></label>`, async f=>{await action('voice_sample_text',{id:sample.id,text:f.get('reference_text')});renderVoiceSettings();}, ui('Enregistrer')); });
  host.querySelectorAll('[data-voice-sample-delete]').forEach(b => b.onclick = () => openDialog(ui('Supprimer cette voix copiée'), ui('<p>L’échantillon enregistré est supprimé de cet ordinateur.</p>'), async () => { await action('voice_sample_delete', {id: b.dataset.voiceSampleDelete}); renderVoiceSettings(); }, ui('Supprimer')));
  $('voice-token-form').onsubmit = async e => {
    e.preventDefault();
    const token = new FormData(e.target).get('token');
    if (!token) return toast(ui('Aucun nouveau jeton saisi.'));
    try { await action('voice_hf_token', {token}); toast(ui('Jeton enregistré.')); renderVoiceSettings(); } catch (err) { fail(err); }
  };
  const clear = host.querySelector('[data-voice-token-clear]');
  if (clear) clear.onclick = async () => { try { await action('voice_hf_token', {token: ''}); renderVoiceSettings(); } catch (e) { fail(e); } };
  clearInterval(voiceUI.discoveryTimer);
  if (s.windows_pending) voiceUI.discoveryTimer = setInterval(async () => {
    if (state.view !== 'settings' || state.settingsTab !== 'voice' || $('voice-form') !== form) { clearInterval(voiceUI.discoveryTimer); return; }
    try {
      const found = await action('voice_settings', {});
      if (found.windows_pending || $('voice-form') !== form) return;
      clearInterval(voiceUI.discoveryTimer);
      s.voices = found.voices; voiceGroups = [...new Set(s.voices.map(x=>x.backend))];
      form.querySelectorAll('select[name="voice"], select[name^="cv:"]').forEach(select=>{const selected=select.value;select.innerHTML=voiceOptions(selected,select.name==='voice'?ui('Automatique : une voix dans la langue de la dictée'):ui('Voix générale'));});
      if ($('voice-windows-detection')) $('voice-windows-detection').textContent = ui('Détection des voix Windows terminée.');
      updateCapabilities();
    } catch (error) { clearInterval(voiceUI.discoveryTimer); if ($('voice-windows-detection')) $('voice-windows-detection').textContent = error.message; }
  }, 2000);
  paintVoiceJobs(c);
  if (c.jobs.some(j => ['queued', 'running'].includes(j.status))) watchVoiceJobs();
}

function paintVoiceJobs(c) {
  const host = $('voice-settings');
  if (!host) return;
  host.querySelectorAll('[data-voice-item]').forEach(card => {
    const item = c.items.find(x => x.id === card.dataset.voiceItem);
    if (!item) return;
    const job = [...c.jobs].reverse().find(j => j.name === 'Voix · ' + item.name);
    if (!job) return;
    const busy = ['queued', 'running'].includes(job.status);
    const label = job.status === 'queued' ? ui('En attente…') : job.status === 'running' ? ui('Installation en cours') + (job.total ? ' · ' + Math.min(100, Math.round(job.received / job.total * 100)) + ' %' : '…') : job.status === 'failed' ? ui('Échec : ') + (job.error || ui('installation interrompue')) : ui('✓ Installé');
    card.querySelector('[data-voice-job]').textContent = label + (busy && job.detail ? ' · ' + job.detail : '');
    const b = card.querySelector('[data-voice-install]');
    if (b) { b.disabled = busy || item.installed; b.textContent = busy ? label : item.installed ? ui('✓ Installé') : ui('Réessayer'); }
  });
}

function watchVoiceJobs() {
  if (voiceUI.jobsTimer) return;
  voiceUI.jobsTimer = setInterval(async () => {
    if (state.view !== 'settings' || state.settingsTab !== 'voice') { clearInterval(voiceUI.jobsTimer); voiceUI.jobsTimer = null; return; }
    const c = await action('voice_catalog', {}).catch(() => null);
    if (!c || !c.jobs.some(j => ['queued', 'running'].includes(j.status))) { clearInterval(voiceUI.jobsTimer); voiceUI.jobsTimer = null; }
    if (c) { paintVoiceJobs(c); if (!voiceUI.jobsTimer && !voiceUI.preview && !$('voice-form')?.contains(document.activeElement)) renderVoiceSettings(); }
  }, 1500);
}

bindVoice();
