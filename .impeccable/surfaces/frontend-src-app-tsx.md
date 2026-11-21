---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

# Surface: request intake (frontend/src/App.tsx)

Mode: Operate. Audience: coordinating UDIP officials, desktop, daylight office. Task: register one incoming request (main file + attachments) with its date of receipt so the statutory 14-day clock starts correctly. Must keep: all existing behaviour and Polish copy, "Jak to działa" section content, footer promise. Open: "Tryb lokalny" claim unconfirmed (kept as-is at user's instruction, flagged).

## Direction contract

THESIS: The category standard, played straight: a Polish e-government intake form at gov.pl / mObywatel craft. Refuses the SaaS look (soft cards, pill badges, icon tiles, nested dashed card), not the convention.

OWN-WORLD: White ground, near-black text #1b1b1b, one institutional blue #0052a5 for actions, links and the header rule; light grey #f2f2f2 bands for secondary content. 2px dark input borders, square corners (max 4px), strong 3px blue focus outline with offset. System sans, generous 16-18px body, bold h1 at 32px. State colours green #00703c / red #b3261e only for outcomes.

STORY: The official sees which step they are on, sets data wpływu (defaults to today), adds the request file and attachments, marks which file is the wniosek, sees the computed answer deadline update live, submits, and gets a confirmation panel with date, deadline and next step, or a plain-Polish error with retry.

FIRST VIEWPORT: White header with product name and Urząd Miasta Bydgoszczy, 4px blue rule beneath. Centred 760px column: h1, lead, 4-segment step indicator (step 1 active), "Data wpływu" date field with the live "Termin odpowiedzi" line beside it, dropzone, then the blue "Analizuj wniosek" button left-aligned beneath. Signature: the deadline readout bound to the date field.

FORM: canon card (category standard) chosen from the decision round, seed:cd915aa7c5d82142.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Recorded adaptations (finish review round 1)

- Container is 880px (816px content) instead of 760px: file rows carry radio, role, extension, long names and size on one line, and the deadline readout sits beside the date field; 760 forced both to wrap at desktop.
- Deadline readout is a tinted panel, not a bare line: it carries date, weekday, legal basis, remaining days and, when the 14th day is a non-working day, the art. 115 KC note. Tones: blue (default), amber when 3 or fewer days remain, red when passed. Amber is added to OWN-WORLD's state colours under PRODUCT.md principle 2 (the deadline always shows); it also marks skipped-file notices.
- Primary action stays enabled (gov.pl pattern); missing file and invalid date surface as inline field errors with focus moved to the field.
