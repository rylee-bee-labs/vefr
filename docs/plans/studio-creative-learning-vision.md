# VEFR Studio: a game about learning to make games

**Status:** Owner-confirmed product vision, recorded 2026-10-12 after a 12-question design workshop and one focused outside-research pass. **Proposal for roadmap review, not authorization to refactor, deploy, reorder active work, or change game contracts.**

**In one sentence:** VEFR is a playable Norse-inspired creative studio where a person learns to make games by imagining, experimenting, choosing, playing, and refining alongside helpful companions.

The purpose is not to generate a whole game from the fewest prompts. It is for someone with an idea and no game-development background to leave saying, **"I made that, I understand something about how it works, and I want to make more."**

This is a product-experience direction layered over the existing VEFR Journey, not a replacement for Cottage of the Breeze, the engine roadmap, or the existing studio tools.

## Owner decisions: twelve questions

| # | Decision |
| --- | --- |
| 1. First magic | **A creative partner.** The player feels understood by an AI character who helps develop an idea. |
| 2. First conversation | **Understand, then create.** Ask thoughtful questions about imagination and interests, then make something tangible together. |
| 3. Emerging project | **All three:** a living storybook, visual inspiration canvas, and playable world, connected as views of the same project. |
| 4. Initiative | **Explore together in a sandbox; delegate later.** A trusted companion may run with an assignment only within approved boundaries, with consequences reviewed before promotion. |
| 5. Locks | **All four:** canon/story truth, creative/art direction, scoped assignment, and approved milestone. A lock is revisable by its owner, not casually overridable by a companion. |
| 6. Navigation | **Two ways in:** an explorable Norse Studio and instant, accessible navigation to the practical workspace. Same project and state. |
| 7. Companions | **Shapable companions:** the creator tunes personality, initiative, creative style, and help style. This does not itself decide how many residents exist or replace owner-authored resident canon. |
| 8. More intelligence | **In-world specialists first; controls optional.** Model/provider/task settings, privacy, quality, and cost are available for interested creators, not prerequisites for newcomers. |
| 9. First product slice | **Visual workshop:** see, compare, refine, and approve art, mood, and mockups with a companion. |
| 10. Primary audience | **Non-technical beginners.** VEFR must stay a game about learning to make games, not merely a game-making AI front end. |
| 11. Learning | **All four:** curiosity-driven discovery, hands-on experimentation, clear explanation of what happened, and optional resident commissions/adventures. |
| 12. First adventure | **Player-chosen idea with a guided route to playability.** An open creative starting point should lead to a small playable slice, not force everyone to make the same character or room. |

The choices above describe a destination. They do not establish that the connected visual canvas, persistent creative memory, companion-personality controls, or explorable 3D/2D Studio are already implemented.

## The learner experience

### One project, three connected perspectives

- **Storybook:** ideas, characters, relationships, threads, established facts, drafts, and decisions.
- **Canvas:** references, sketches, moods, game-specific art rules, alternatives, mockups, and asset provenance.
- **Playable world:** the working scene, gameplay features, playtest, and shareable output.

These perspectives should cross-reference the same approved creative decisions; they should not become three unrelated databases or a new competing source of truth. A picture is a proposal until kept. A brainstormed event does not silently become canon. Playing should reveal whether the chosen art, story, and mechanics work together.

### The flexible path from idea to playable slice

1. **Imagine:** Ask what excites the creator. Start with any idea, from a person or place to a strange mechanic or a whole fictional world.
2. **Find the smallest playable heart:** With the companion, identify a place, an action or choice, a response or consequence, and a reason to care. Not every game needs combat, inventory, or dialogue.
3. **See and compare:** Offer several distinct visual directions using available or imported artwork; explain the tradeoffs. Choose a game-specific look, not a universal VEFR house style.
4. **Make a little thing:** Use supported VEFR authoring tools to express the idea as one real interaction; keep the first loop tiny and honest about which gameplay features exist.
5. **Play, reflect, revise:** Preview, check, keep, play in the Studio, change one thing, and play again. Explain how the change affected the result when requested.
6. **Keep and share:** Preserve the approved work, records, and editable sources; weave a standalone playable HTML artifact.

The stages are **helpful scaffolding, not doors that must be unlocked**. Makers can jump into a room, skip lessons, reopen creative choices, or use the Studio with no model. A companion should offer the next sensible step without seizing control of the story.

### Teaching is embedded in creation

At a decision point, the Studio can offer four overlapping modes:

- **Discover:** ask why a choice matters and show accessible examples.
- **Experiment:** change a color, lighting, expression, layout, or rule, and immediately compare.
- **Understand:** optionally reveal the rule, tool, template, record, and reasoning behind the outcome.
- **Adventure:** accept a small, optional commission from a resident to practice something in context.

A novice should never have to learn terms like prompt, model broker, pack schema, or DSL before making a playable scene. Advanced makers can inspect the machinery. No lessons, reward stickers, or resident quests gate the editor or the ability to publish.

### In-world experience with direct access

Walking through the old-Norse Studio, meeting residents, and interacting with creative departments should be pleasurable in its own right. **Instant navigation and practical workspace views must work equally well**. Immersion is optional, never an accessibility penalty. Preserve keyboard and touch operation, readable focus, reduced motion, contrast, screen-reader names, and the ability to complete a task without navigating spatially.

### Companions, agency, and locks

Companions are **relationships and helpful roles, not individual model instances**. Creator-adjustable style and initiative are separate from the underlying inference provider. Existing owner-authored resident voice notes remain the default character source; user customization should not silently replace them.

- **Draft:** an unapproved suggestion or generated experiment.
- **Approved:** chosen material that is eligible to be kept, validated, and used.
- **Locked:** an explicit protection around approved canon, a creative direction, an assignment's scope, or a known-good milestone. This is a proposed additional user-facing concept, not a claim of a fully implemented lock system.
- **Delegated work:** an assignment constrained by those protections; the owner still sees and approves consequential promotion.

Follow **preview -> check -> keep -> play -> undo**. When a creative rule changes, make its downstream consequences visible rather than rewriting silently. Personal preferences may tune how bold, gentle, whimsical, or dark suggestions become, without forcing a game's canon to follow an unreviewed model preference.

A companion may suggest consulting another in-world specialist. Underneath, Studio Jobs and model connections should be replaceable. Cloud requests require permission and clear data/privacy/cost expectations. No local download, cloud subscription, account, network, or model is required to author and run a completed game. Do not treat a consumer chat subscription as an API entitlement.

## Repository alignment: what is real today

The primary authority for existing delivery order remains the top-level [ROADMAP](../../ROADMAP.md); this section is a product-experience crosswalk rather than a new assertion of shipped work.

| Existing evidence | What it supports | What is **not** proved built by that evidence |
| --- | --- | --- |
| [The Journey](../guides/journey.md) | A Norse Studio, rooms, learner-chosen route, visible result at each stop, standalone game. | Seamless storybook/canvas/playable-world synchronization. |
| [Making art](../guides/making-art.md) | Proofs, comparison, picking, style kits, provenance, in-game review and keeping records. | One finished beginner-facing visual comparison workspace with conversational image generation. |
| [Studio edits](../guides/studio-edits.md) | Preview, validation, approved writes, one-step undo, playable embedded preview. | Arbitrary sandbox branches, universal editing of every creative artifact, or advanced locks. |
| [Studio modules](../guides/studio-modules.md) | A commission board first slice and agreed maker-friendly learning philosophy. | All listed modules, rewards, or the full learning ladder; the guide calls most of them plan. |
| [Studio Jobs and models](studio-jobs-and-models.md) | Proposed resident -> Job -> tools -> broker boundary, local-first policy, incremental migration. | A finished per-job model broker or first-run hardware recommender. |
| [Gameplay features ADR 0012](../adr/0012-gameplay-features.md) | Game -> reusable gameplay feature -> VEFR core, promoting abstractions only after independent uses. | A general game-feature plugin architecture or automatic game-mechanic invention. |
| [Residents](../guides/residents.md) | Authored Norse residents with specific, owner-approved voices. | User-editable companion identity, cross-model continuity or durable project memory. |

The first work item is to inventory exactly which art and scene paths can be connected **without introducing a competing editor, new pack language, new model framework, or changes to the standalone runtime**.

## Proposed phases and exit proofs

These phases are **proposed Studio experience sequencing**, not a command to stop current gameplay, interface, QA, or Cottage work. Each slice should leave something genuinely usable.

### Phase 0: Record, inventory, and protect

**Now, docs and evidence only.** Review this vision against the existing Journey, art workflow, studio rooms, active issue board, current art/asset handling, supported interactions, and accessibility contract. Mark built/partial/proposed with file-level evidence. Name one Studio surface to extend. Maintain the existing Cottage/engine order and the second-real-consumer architecture rule.

**Exit proof:** a short capability crosswalk and one bounded, reviewed first-slice plan; no required runtime or pack change.

### Phase 1: The first visual workshop

Make one native-feeling resident-guided flow: ask a beginner what they imagine, present **three distinct visual directions** from curated/imported/existing sources (generation is optional), compare and iterate, select one, record provenance and draft/approved status, and show the choice in context at actual game scale.

Reuse the art guide's proof/pick/process/record loop and existing Studio rooms. Keep an accessible direct-workspace route. Offer plain-language learning and optional "show me how it works".

**Exit proof:** a novice can explore, compare, revise, and keep a game-specific visual decision without editing JSON or having a cloud account. Do not mark complete with a static mockup alone.

### Phase 2: One idea becomes one playable interaction

Join the visual choice to an actually supported map/place, character or object, and **one action -> consequence**. Reuse VEFR's existing preview/check/keep, embedded playtest, undo, and standalone weave. If a requested mechanic cannot be expressed through current gameplay features, offer an honest smaller alternative instead of inventing engine support.

**Exit proof:** a new maker can see their choice in a tiny game, play it, change something, understand one cause-and-effect relationship, and share the model-free result. Aim for a friendly ~20-minute first experience; validate the timing with real users rather than declaring it shipped.

### Phase 3: Connected storybook and creative decisions

Link visual choices, lore and character threads, approved canon, and playable state through existing authoritative project data, without a second truth store. Begin with the smallest real draft/approved/locked interaction that demonstrates a genuine conflict or rollback; do not build a broad permissions system by assumption.

**Exit proof:** changing a draft leaves canon intact; a locked choice cannot be silently replaced; approved content and its provenance survive reload.

### Phase 4: Trusted companion growth

Demonstrate a companion performing a validated native Studio Job. Inventory existing model seams before extracting them, and build a broker **only once two Jobs duplicate the same selection/fallback needs**, as the current model plan requires. Then explore shapeable companion controls, scoped assignments, local model setup, and explicit cloud connections as concrete needs emerge.

**Exit proof:** the creator can keep their project and companion intent while changing appropriate model connections; offline/no-model paths still function; trusted work cannot bypass owner approval or protected decisions.

### Phase 5: The living game studio

Deepen the explorable Studio, authored resident reactions, optional commissions, evolving World Tree, and advanced specialist interactions **after** the core learning/playable loop proves joyful and accessible. Optional external integrations belong at stable boundaries, not an internal MCP bus.

**Exit proof:** Studio exploration adds delight without making creation slower or less accessible. Complete games remain standalone and model-independent.

## The smallest proposed milestone

**"From imagination to a visible, playable little moment."**

Example acceptance walkthrough:

1. A newcomer says, "I want a dragon's bakery to feel safe, with an unsettling basement."
2. A companion asks one or two useful clarifying questions and offers three visual moods.
3. The maker compares them, changes a detail, chooses one, and approves the visual direction.
4. With existing VEFR primitives, the maker adds a small scene and one meaningful interaction or choice.
5. They press **Play it here**, experience the consequence, revise something, and play again.
6. They can inspect why the change worked, view what was kept, undo it, and weave a shareable HTML game.

The bakery is an **illustrative acceptance story**, not engine sample content to hard-code, and it must not displace an existing game's style or voice.

**Success signal:** a first-time creator can explain their own visual decision and the game's small interaction; the flow is keyboard/touch usable; no compulsory AI account, paid service, or source-code editing; the shipped bundle works disconnected from VEFR.

## Boundaries and unanswered implementation questions

- **Do not** turn Cottage's current production schedule into a Studio overhaul. Cottage remains a real game and a source of engine evidence.
- **Do not** implement a general agent framework, plugin loader, internal MCP bus, duplicate art database, or new pack DSL to fulfill this vision.
- **Do not** let model output edit authoritative content or change creative locks without a human keep/approve step.
- **Do not** make a subscription, GPU, paid image generator, visual navigation, tutorial lesson, or cloud model a prerequisite for first creation or finished-game play.
- **Do not** claim every arbitrary idea can be converted into any mechanic in twenty minutes. Teach honest scope and supported feature composition.
- **Resolve during Phase 0:** accessible visual comparison surface; lawful/licensed first-run example assets; how selected art maps into real packs; which initial action/consequence is fully supported; provenance/status placement; and the smallest state model for drafts and locks.
- **Preserve the existing promotion rule:** a reusable gameplay feature follows evidence from two unrelated games; VEFR core grows only when several genuine uses need it.

## One focused research pass (2026-10-12)

These are **outside design references**, not proof of VEFR implementation:

- [Scratch Foundation: Creative Learning Philosophy](https://www.scratchfoundation.org/learn/learning-library/scratch-creative-learning-philosophy): passion/projects/play; many paths through a low-floor, wide-walls, high-ceiling experience; imagination -> creation -> play -> sharing -> reflection. **Apply:** creator-chosen ideas and fast reflective play loops.
- [GDevelop Academy](https://gdevelop.io/academy) and [GDevelop docs](https://wiki.gdevelop.io/gdevelop5/): progressive practical learning, events and behavior composition, no-code entry with more depth available. **Apply:** teach a first visible cause/effect rather than requiring engine vocabulary upfront. Do not copy its whole editor or tutorial catalog.
- [Twine](https://twinery.org/): approachable nonlinear story creation, optional scripting for depth, portable HTML publishing. **Apply:** tiny playable outputs and graduated complexity.
- [Human-AI co-creation and agency: review of 134 HCI/CSCW papers](https://doi.org/10.1145/3757594): agency, control patterns, and trust are fundamental co-creation design concerns. **Apply:** creator approvals, reversibility, scoped autonomy, and clarity about changes.

Research synthesis: **The differentiator is a playful, relational Studio that teaches through making**, not AI that automatically replaces the maker. This synthesis is a product judgment drawn from the sources above and the owner workshop, not a measured usability result.

## Review path

1. Confirm this doc faithfully captures the twelve answers and respects current shipped/plan boundaries.
2. Inventory Phase 0 surfaces and identify the tiniest feasible native UI + scene demonstration.
3. Make a focused implementation issue/PR with an explicit acceptance walkthrough and accessibility/no-model checks.
4. Leave this vision as a compass, and let independent game-making evidence continue to decide when architectural generalization is earned.
