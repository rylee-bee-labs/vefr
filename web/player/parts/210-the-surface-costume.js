// ---- the surface costume (hp bar, encounter prompt, verbs) ----
// The hero's health is real now: `VEFR_HERO.hp` is the max, the
// current value is carried per world in browser storage
// (`vefr-hp-<world>`), and the bar shows it honestly. Deterministic:
// fixed numbers, no randomness, no clock. A drop to zero is Cozy
// (see setupTown).
// Both Cozy death lines, worded side by side so a pack can change
// either: the temple line says the pack's wake place, the stair line
// says the foot of the up-stair of a descent floor, where the descent
// wakes the hero instead (see `deathResume`).
var DEATH_LINE = 'You wake in the temple. You lost nothing that mattered.';
var STAIR_DEATH_LINE = 'You wake at the foot of the stair, whole again. '
  + 'You lost nothing that mattered.';

