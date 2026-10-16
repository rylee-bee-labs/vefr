// ---- whisper ----
// The name the player pressed is Listen (issue #470): it hears a rumor from
// anywhere in town, it does not whisper to whoever happens to be standing
// there. The box says which of the two it is, so the speech reads
// "You overhear <the speaker>" and not a reply from whoever is nearby.
function overheardName(speaker) {
  return 'You overhear ' + (speaker || 'someone in town');
}

function bindWhisper() {
  var btn = document.getElementById('whisper');
  var status = document.getElementById('status');
  // The Journal keeps the whispers - as plain lines on its quiet page
  // (vefr#484), written by showSpeech when the box opens - so it can ask
  // for one too: a phone draws no Whisper button over the world. The menu
  // closes first, so the whisper's speech box opens over the game, as it
  // does from the button.
  var fromJournal = document.getElementById('journal-whisper');
  if (fromJournal) fromJournal.addEventListener('click', function () {
    if (window.closeMenu) window.closeMenu();
    if (!btn.disabled) btn.click();
  });
  btn.addEventListener('click', async function () {
    btn.disabled = true;
    status.textContent = 'Listening\u2026';
    var ph = STATE.get().phase;
    var tone = window.VEFR_WORLD.phases[ph] || '';
    var system = 'You are the whisper that flies out every day and comes home.\n'
      + 'Write ONE tavern rumor from the world described below, in-world,\n'
      + 'spoken by a named minor character. Follow the Contract strictly:\n'
      + 'never explain, never label, never use modern words. Show only.\n\n'
      + 'CURRENT PHASE: ' + tone + '\n\n'
      + (window.VEFR_LOGBOK || '').slice(0, 4000) + '\n\n'
      + 'Whispers already collected - match their cadence, do not repeat them:\n\n'
      + (window.VEFR_LEDGER || '');
    var schema = { type: 'object', properties: {
      speaker: { type: 'string' },
      whisper: { type: 'string' },
      is_true: { type: 'boolean' },
    }, required: ['speaker', 'whisper', 'is_true'], additionalProperties: false };
    try {
      var body = {
        model: llmModel,
        messages: [
          { role: 'system', content: system },
          { role: 'user', content: 'Whisper one tavern rumor. Reply with only the JSON object.' },
        ],
        response_format: { type: 'json_schema', json_schema: { schema: schema, strict: true } },
        max_tokens: 200, temperature: 0.95, stream: false,
        chat_template_kwargs: { reasoning_effort: 'low' },
      };
      var r = await llmPost(body);
      if (!r.ok) throw new Error('LLM ' + r.status);
      var j = await r.json();
      var card = JSON.parse(j.choices[0].message.content);
      status.textContent = '';
      showSpeech(card.speaker, '\u201C' + card.whisper + '\u201D', card.is_true ? '' : 'A lie, or close enough.',
        overheardName(card.speaker));
    } catch (err) {
      // No live endpoint (or it failed): draw from the woven pool -
      // real model output, pre-generated at weave time. Pool spent?
      // The composer re-weaves the pool's own cloth. No pool cloth
      // at all? The pack's own fragments speak. Nothing anywhere?
      // The pack's own grammar speaks. Still nothing? The honest
      // silence stays.
      var phaseKey = 'rumor:' + (STATE.get().phase || '');
      var pooled = poolDraw(phaseKey);
      var respliced = pooled ? null : composeWhisper(phaseKey);
      var fromFragments = false;
      var fromGrammar = false;
      var card = pooled || respliced;
      if (!card) { card = whisperFromFragments(); fromFragments = true; }
      if (!card) { card = whisperFromGrammar(); fromGrammar = true; }
      if (card) {
        status.textContent = '';
        showSpeech(card.speaker, '\u201C' + card.whisper + '\u201D',
          (pooled ? "From the game's saved lines."
            : respliced ? "Mixed from the game's saved lines."
            : fromFragments ? "From the characters' own lines."
            : fromGrammar ? "From the world's own words." : '')
          + (card.is_true ? '' : ' A lie, or close enough.'),
          overheardName(card.speaker));
      } else {
        status.textContent = 'Nothing came back (' + (err.message || 'failed') + ').';
      }
    } finally {
      btn.disabled = false;
    }
  });
}

