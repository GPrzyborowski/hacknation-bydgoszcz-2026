# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Officials who coordinate requests for public information (wnioski o udostępnienie informacji publicznej, UDIP) at Urząd Miasta Bydgoszczy. They receive incoming requests, pass them to the right departments, keep track of statutory deadlines, collect what the departments send back, and prepare the final reply to the requester. They use desktop browsers on the city hall's office network, as part of routine administrative work.

No other audiences are confirmed. Department staff and citizens do not use the tool directly.

## Product Purpose

UDIPilot takes the routine work out of handling a public-information request while leaving every decision with the official. The flow, as the product describes it:

1. **Wgraj wniosek:** the official uploads the request (PDF, DOC, DOCX).
2. **Analiza i podobne sprawy:** the assistant reads the request, finds similar requests in the archive and suggests which departments should handle it.
3. **Termin w kalendarzu:** the request goes into a register, with its answer deadline counted from the date it was received.
4. **Projekt odpowiedzi:** once the departments' answers are uploaded, the assistant drafts the reply and suggests what to anonymise.

Success means the official answers on time and correctly, with less manual searching, routing and redaction work, and stays fully in control of the outcome.

## Positioning

An assistant built around the actual legal procedure for public-information requests: deadlines counted the way the law counts them, precedent drawn from the office's own archive of earlier cases, and anonymisation suggestions applied to the reply. It is not a general-purpose document AI. It suggests and the official decides. Nothing is sent automatically to departments or requesters.

## Operating Context

- A hackathon prototype answering a city challenge at Hacknation Bydgoszcz 2026, presented to a jury.
- Requests come in as PDF and Word documents, up to 20 MB per file. Several files can be uploaded at once.
- The answer deadline is statutory: 14 days from receipt, which can be extended to at most 2 months with notice to the requester. This deadline is central to the product.
- An archive of past requests and their answers exists, or will be supplied, as the basis for finding similar cases.
- The interface language is Polish.

## Capabilities and Constraints

- **Built (frontend):** the upload screen, which handles drag-and-drop, file validation and the received date, and posts the file to `POST /api/intake/analyze`.
- **Built (backend API, see `backend/README.md`):** request analysis with OCR, archive search for similar cases, department suggestions, the deadline register with year filter and urgency, intake of department answers, reply drafting in the BKS letter format (answer, kwerenda, doprecyzowanie, nie dysponent), anonymisation following the UMB list, DOCX/PDF export, an editable knowledge base.
- **Built (frontend):** tabs Nowy wniosek / Rejestr wniosków / Baza wiedzy; analysis result with registration, register table with urgency highlighting, case view with department answer intake, letters, anonymisation review (grey proposal, black accepted) and DOCX/PDF export.
- **Deadline rule:** the UMB register counts the deadline as received date + 14 days (`=E+14`). A deadline on a non-working day is flagged, not shifted (art. 57 § 4 KPA shown as information).
- **Core capability:** anonymisation of personal data in draft replies is a key feature, not an add-on.
- **Stack:** React 19, TypeScript and Vite frontend; FastAPI backend; Docker Compose for local development.
- **Language model:** the hackathon build runs on Google Gemini (`gemini-2.5-flash`) with organiser test data only. The challenge requires the target concept to work fully locally without internet; `OFFLINE_MODE=true` blocks sending content to Gemini, and the backend falls back to rule-based analysis when no model is available.

## Brand Commitments

- Product name: **UDIPilot**. Owning organisation as shown in the UI: Urząd Miasta Bydgoszczy.
- Voice: plain, procedural Polish in the register of public administration, always stating that the official decides. Existing copy example: "Ostateczną decyzję zawsze podejmuje urzędnik."
- No official city logo or brand assets are in the repository. Do not invent or imitate one.
- **Standing visual commitment (chosen 2026-11-21):** every screen follows the standard Polish e-government look, played straight and at full craft. The quality bar is gov.pl and mObywatel. Follow their conventions: plain forms, strong inputs, clear steps, high-contrast focus. Do not copy their logos, emblem or branding.

## Evidence on Hand

- Product copy and the four-step flow in `frontend/src/App.tsx`.
- Organiser test data from the challenge materials ("Hacknation 2026 - UMB"): 10 cases from the register `WNIOSKI O UDOSTĘPNIANIE INFORMACJI PUBLICZNEJ.xlsx` with their requests, the BKS answers (anonymised by UMB), one kwerenda and one doprecyzowanie letter, Zarządzenie nr 535/2024 and the UMB list of data to anonymise. Converted to `backend/app/seed/umb_demo.json` by `backend/scripts/build_demo_seed.py` and marked in the database as `dane_testowe_umb`.
- No statistics, testimonials or measurements of time saved. Do not fabricate any of these.

## Product Principles

1. **The official decides.** Every output is a suggestion the official can see, edit and reject. Nothing leaves the tool on its own.
2. **The deadline always shows.** Wherever a request appears, its statutory deadline and the time left must be visible.
3. **Show the evidence behind suggestions.** Suggested departments and draft text point back to the similar archive cases and the source passages they came from.
4. **Treat personal data with care by default.** Anonymisation is part of drafting a reply, not a separate step done afterwards.
5. **Fit the procedure.** The terminology and steps follow the legal process officials already know.

## Accessibility & Inclusion

WCAG 2.1 AA, the standard Polish law requires of public bodies (ustawa o dostępności cyfrowej). It applies to the prototype too, since it is held to the bar of a real public-sector tool.
