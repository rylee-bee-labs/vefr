// ---- speech box: whoever is talking, in a box over the game ----
// `shownAs` is the name the box prints, for a line nobody is saying TO you:
// the rumor from the Listen button is overheard, so it reads "You overhear
// <speaker>" while the portrait hook still gets the speaker itself and finds
// the picture by the speaker's own name. Omitted, the box prints the speaker.
function showSpeech(speaker, line, note, shownAs) {
  // A skin's portrait hangs off this hook (540-the-skin.js draws it). The
  // hook is read here, when the box is shown, and never when the skin loads,
  // so it does not matter which of the two parts the page loads first: a
  // speech box declared after the skin still gets its portrait. A player
  // with no skin has no hook, and this is one read and nothing more.
  if (typeof window.VEFR_SPEECH_BOX === 'function') window.VEFR_SPEECH_BOX(speaker);
  document.getElementById('npc-name').textContent = shownAs || speaker || '';
  document.getElementById('npc-line').textContent = line || '';
  var n = document.getElementById('npc-note');
  n.textContent = note || ''; n.hidden = !note;
  // Whoever is talking, their line lands on the Journal's quiet page
  // (vefr#484) with its own name as the caption - a whisper reads
  // "You overhear <the speaker>", the way the box itself prints it.
  // The note stays in the box: it says where the line came from, not
  // something the world said.
  // The quiet page (part 245) may be absent from a partial build (skin and part-order harnesses).
  if (typeof journalSay === 'function') journalSay(line, shownAs || speaker || '');
  document.getElementById('npc-box').hidden = false;
  document.getElementById('npc-close').focus();
}

