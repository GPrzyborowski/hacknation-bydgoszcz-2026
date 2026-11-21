---
name: Asystent UDIP
description: Polish e-government intake craft for officials handling public-information requests; plain forms, one institutional blue, deadlines always in view.
colors:
  bg: "#ffffff"
  surface-muted: "#f2f2f2"
  surface-tint: "#eef3f9"
  tint-border: "#b9cbe0"
  text: "#1b1b1b"
  text-secondary: "#4b5257"
  rule: "#b8bdc2"
  rule-light: "#dde0e3"
  accent: "#0052a5"
  accent-hover: "#003d7a"
  accent-active: "#002e5c"
  accent-tint: "#e5edf6"
  success: "#00703c"
  success-tint: "#e9f4ee"
  warning: "#8a4b00"
  warning-border: "#c27c00"
  warning-tint: "#fff6e0"
  danger: "#b3261e"
  danger-tint: "#fcefee"
typography:
  headline:
    fontFamily: "Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "34px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.25
  readout:
    fontFamily: "Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "21px"
    fontWeight: 700
    lineHeight: 1.3
    fontFeature: "tnum"
  label:
    fontFamily: "Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1.3
  lead:
    fontFamily: "Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: 1.5
  button:
    fontFamily: "Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: "Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: "Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  caption:
    fontFamily: "Segoe UI, system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  none: "0px"
  sm: "4px"
  round: "50%"
spacing:
  xxs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  field-gap: "28px"
  gutter: "32px"
  section: "64px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.bg}"
    typography: "{typography.button}"
    rounded: "{rounded.sm}"
    padding: "10px 24px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-primary-active:
    backgroundColor: "{colors.accent-active}"
  button-primary-disabled:
    backgroundColor: "{colors.rule-light}"
    textColor: "{colors.text-secondary}"
  button-secondary:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.accent}"
    typography: "{typography.button}"
    rounded: "{rounded.sm}"
    padding: "10px 24px"
    height: "44px"
  button-secondary-hover:
    backgroundColor: "{colors.accent-tint}"
  button-link:
    textColor: "{colors.accent}"
    padding: "4px 0"
  button-link-hover:
    textColor: "{colors.accent-hover}"
  button-icon:
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.sm}"
    size: "40px"
  button-icon-hover:
    backgroundColor: "{colors.danger-tint}"
    textColor: "{colors.danger}"
  input:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "8px 10px"
    height: "48px"
  input-disabled:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.text-secondary}"
  dropzone:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "24px 28px"
  dropzone-hover:
    backgroundColor: "{colors.accent-tint}"
  deadline-readout:
    backgroundColor: "{colors.surface-tint}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "12px 18px"
  deadline-readout-near:
    backgroundColor: "{colors.warning-tint}"
    textColor: "{colors.warning}"
  deadline-readout-late:
    backgroundColor: "{colors.danger-tint}"
    textColor: "{colors.danger}"
  notice-warning:
    backgroundColor: "{colors.warning-tint}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "14px 18px"
  notice-error:
    backgroundColor: "{colors.danger-tint}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "14px 18px"
  file-row:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.text}"
    padding: "8px 8px 8px 12px"
    height: "56px"
  file-row-selected:
    backgroundColor: "{colors.surface-tint}"
  stepper-segment:
    backgroundColor: "{colors.rule-light}"
    height: "6px"
  stepper-segment-current:
    backgroundColor: "{colors.accent}"
  confirmation-panel:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "28px 32px 32px"
  footer-band:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.text}"
    typography: "{typography.body-sm}"
    padding: "20px 0"
---

# Design System: Asystent UDIP

## Overview

**Creative North Star: "The Public Counter Form"**

The system is the Polish e-government intake form, played straight and built to gov.pl / mObywatel craft. It reads like a well-made public-administration service: a white page, near-black text, one institutional blue that means "act here", and form fields with strong, unmistakable edges. The official is at a desk in a daylight office doing routine procedural work, so the interface stays calm, legible and literal. Nothing decorates; every visible element is a label, a field, a status or an action.

Density is moderate and generous at once: a single centred column, large labels (19px bold), 16px body with 1.5 leading, and 28px between form fields. Hierarchy comes from size and weight, never from colour or ornament. Colour beyond the blue appears only to report an outcome: green for accepted, red for error or a missed deadline, amber for a near deadline or skipped files.

The convention is the point. The system refuses the SaaS look (soft floating cards, pill badges, icon tiles, nested dashed cards, shadows) while keeping every e-government convention intact: a header with a heavy blue rule, a segmented step indicator, numbered step circles, bordered status notices, a grey footer band. It follows those conventions without copying any gov.pl or mObywatel logo, emblem or branding. The scheme is light-only by design (`color-scheme: light`).

**Key Characteristics:**
- White ground, near-black text, one institutional blue for actions, links, focus and the header rule.
- 2px near-black input borders with square corners; nothing rounder than 4px except true circles.
- Flat: no shadows anywhere; depth is borders, 1px rules and tinted fills.
- Outcome colours (green, red, amber) report state and never decorate.
- 3px blue focus outline with 2px offset on every focusable element.
- Dates, sizes and counts always set in tabular figures.

## Colors

A public-administration palette: white, near-black and a single deep institutional blue, with three muted outcome colours held in reserve for state.

### Primary
- **Institutional Blue** (accent): every action and every "you are here" signal: primary button fill, secondary button border and text, links, the 4px header rule, the current stepper segment, the selected radio, the dropzone icon, text selection, caret and the focus outline.
- **Deep Institutional Blue** (accent-hover) and **Darkest Institutional Blue** (accent-active): hover and pressed fills of the primary button; hover colour of text links.
- **Blue Wash** (accent-tint): hover fill of the dropzone and the secondary button.

### Neutral
- **Paper White** (bg): page ground, input fill, confirmation panel.
- **Office Grey** (surface-muted): secondary bands and passive areas: the footer band, the resting dropzone, disabled inputs.
- **Pale Registry Blue** (surface-tint) with **Registry Blue Edge** (tint-border): informational panels that are not actions: the default deadline readout and the selected file row.
- **Ink** (text): all primary text, input borders, the step-number circle stroke, the skip link fill.
- **Slate** (text-secondary): hints, metadata, file sizes and extensions, unselected file roles, the dropzone's resting dashed border; also the disabled text colour.
- **Rule Grey** (rule): 1px dividers between file rows, summary rows, the "Jak to działa" section and the footer.
- **Light Rule** (rule-light): inactive stepper segments and the disabled button fill.

### Outcome colours
- **Registry Green** (success) on **Green Wash** (success-tint): accepted outcomes only: the confirmation panel border and its filled check circle.
- **Official Red** (danger) on **Red Wash** (danger-tint): errors and passed deadlines: field error text, error borders on inputs and the dropzone, the error notice, the late deadline readout, the remove-file icon hover.
- **Amber Text** (warning) with **Amber Edge** (warning-border) on **Amber Wash** (warning-tint): caution: a deadline with 3 or fewer days left, and the skipped-files notice.

### Named Rules
**The One Blue Rule.** Institutional Blue is the only hue that invites action. There is no second accent; links, buttons, focus and the header rule all share it.

**The Outcome Only Rule.** Green, red and amber appear only to report a state (accepted, error or late, near deadline or skipped). They never decorate, never tint a heading and never carry branding.

## Typography

**Body Font:** Segoe UI (with system-ui, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif)

**Character:** One plain sans for everything, the way public-service forms are set: legible, unmannered, weight-driven hierarchy. Weights are 400 for reading, 600 for controls and emphasis, 700 for headings, labels and key values.

### Hierarchy
- **Headline** (700, 34px, 1.25, -0.01em; 27px under 640px): the page h1, one per screen.
- **Title** (700, 24px, 1.25): section headings such as "Jak to działa". The confirmation heading sits slightly larger at 26px.
- **Readout** (700, 21px, 1.3, tabular): key values the official must read at a glance: the computed deadline date; also the product name in the header.
- **Label** (700, 19px, 1.3): form field labels and the dropzone title.
- **Lead** (400, 19px, 1.5, max 62ch; 17px under 640px): the one introductory paragraph under the h1.
- **Button** (600, 17px): primary and secondary button text. Step titles in the steps list also sit at 17px bold.
- **Body** (400, 16px, 1.5): default reading text; hints capped at 75ch.
- **Body small** (400, 15px): hints, metadata, file sizes, the stepper label, the footer.
- **Caption** (400, 14px): the small label above the deadline date, the header status tag. File-type tags drop to 13px 600.

### Named Rules
**The Tabular Figures Rule.** Every date, deadline, file size, count and register number uses `font-variant-numeric: tabular-nums`, so numbers line up and never jitter as they update.

**The Weight Not Colour Rule.** Hierarchy is carried by size and weight. Headings are Ink, never blue; emphasis inside a status uses bold, not a new colour.

## Layout

A single centred column: container max 880px with 32px side gutters (816px of content), narrowing to 16px gutters at 640px and below. The width is set by the widest real content: a file row carrying radio, role, extension, a long filename and size on one line, and the deadline readout sitting beside the date field.

Vertical rhythm runs on a 4px base: 4 / 8 / 12 / 16 / 20 / 24 / 28 / 32 / 40 / 64. Within a field, label, hint, error and control stack with 8px gaps; fields stack 28px apart; the "Jak to działa" section opens 64px below the form with a 1px rule and 32px padding. Main content starts 32px under the header and ends with 72px of space before the footer.

The page is three bands: a white header (min 72px tall) closed by a 4px Institutional Blue rule; the white main column; an Office Grey footer band with a 1px top rule. Actions are left-aligned beneath the form, never centred or floated.

Under 640px: the dropzone stacks its icon above the text, the date input and deadline readout each go full width, file rows wrap the filename to its own line and hide the extension tag, the primary button spans the full width, the steps grid collapses from two columns to one, and summary rows stack term over value.

## Elevation & Depth

The system is flat. No element casts a shadow. Depth and grouping come from three devices only: 1px Rule Grey dividers between rows and sections, 2px borders on fields, notices and the confirmation panel, and tinted fills (Office Grey, Pale Registry Blue, outcome washes) that set a region apart from the white ground.

### Named Rules
**The Flat Page Rule.** No `box-shadow` on any surface or control. If something needs to stand apart, give it a border or a tinted fill.

## Shapes

Corners are square or nearly square. Inputs have 0 radius; buttons, notices, the dropzone, the deadline readout, the confirmation panel and the header status tag share a single 4px radius. True circles are reserved for objects that are circular by convention: radio buttons, the numbered step markers (36px, 2px Ink stroke), the success check (40px, filled Registry Green) and the loading spinner. The stepper is four flat 6px bars with 4px gaps.

Borders are structural and heavy where they mark something the official acts on: 2px on inputs, buttons, notices and the confirmation panel. The dropzone is the only dashed border in the system.

### Named Rules
**The Square Ground Rule.** Nothing rounder than 4px unless it is a true circle. No pills.

**The One Dash Rule.** A dashed border means "drop files here". It is used by the dropzone and nowhere else, and it is never nested inside another bordered box.

## Components

### Buttons
Plain, solid and confident; the gov.pl action button.
- **Shape:** gently squared corners (4px), 2px border matching the fill.
- **Primary:** Institutional Blue fill, white 17px/600 text, 48px minimum height, 10px 24px padding. Left-aligned under the form; full width under 640px. Stays enabled while the form is incomplete: pressing it surfaces inline field errors and moves focus to the first problem.
- **Hover / Active:** fill darkens to Deep then Darkest Institutional Blue over 0.15s ease-out. **Disabled** (only while uploading): Light Rule fill, Slate text, a spinner (18px, 0.8s linear rotation) beside "Przesyłanie…".
- **Secondary:** white fill, 2px Institutional Blue border and text, 44px minimum height; hover adds Blue Wash. Used for recovery actions inside notices ("Spróbuj ponownie").
- **Link button:** underlined Institutional Blue 600 text with no box (offset 3px); hover deepens the colour and thickens the underline to 2px. For low-stakes list actions such as "Wyczyść".
- **Icon button:** 40px square, transparent, Slate 18px stroked SVG; hover turns Red Wash with Official Red icon. Used for removing a file.

### Inputs / Fields
- **Style:** 2px Ink border, square corners, white fill, 8px 10px padding, 44px minimum height (date input 48px, 200px wide).
- **Field anatomy:** bold 19px label, Slate hint beneath (max 75ch), then a bold Official Red error line when present, then the control.
- **Focus:** the global 3px Institutional Blue outline with 2px offset.
- **Error:** border turns Official Red; the error message sits above the control and is announced to assistive tech. **Disabled:** Office Grey fill, Slate text, not-allowed cursor.

### Deadline Readout (signature)
The statutory answer deadline, bound live to the date-of-receipt field and set beside it.
- Pale Registry Blue panel with a 1px Registry Blue Edge, 4px corners, 12px 18px padding.
- Content: 14px Slate caption "Termin odpowiedzi", the date and weekday in the 21px bold tabular readout style, then a 15px meta line with the legal basis and days remaining. When the 14th day is a non-working day, a note states the shifted date in bold.
- **Near** (3 or fewer days left): Amber Wash with Amber Edge; meta line in Amber Text 600. **Late:** Red Wash with Official Red border and meta line. **Empty:** the date shows a Slate dash.

### Dropzone
- Office Grey fill, 2px dashed Slate border, 4px corners, 24px 28px padding; a 48px stroked blue document-upload icon left of the text.
- Text: bold 19px title, a line with an underlined blue "wybierz plik z dysku", a 15px Slate format hint.
- **Hover:** border turns Institutional Blue and the fill Blue Wash. **Dragging:** the border goes solid blue and the title changes to the drop instruction. **Invalid:** red border. **Disabled:** Rule Grey border, Slate text and icon.

### File List
- A list ruled with 1px Rule Grey above and between rows; 56px minimum row height.
- Row content left to right: radio (22px) with role label ("Wniosek" / "Załącznik"), uppercase 13px extension tag, filename (truncated with ellipsis, full name on hover), tabular size, remove icon button.
- **Selected row** (the main request file): Pale Registry Blue fill and the role label in bold Ink.
- A 15px 600 tabular legend states the count and total size above the list.

### Notices
- Bordered status boxes: 2px border, 4px corners, 14px 18px padding, items stacked with 6px gaps.
- **Warning:** Amber Edge on Amber Wash (skipped files, each named in 600 with its reason). **Error:** Official Red border on Red Wash, the headline sentence in bold red, followed by a plain-Polish explanation and a secondary retry button.

### Stepper
- A 15px Slate label "Krok n z 4:" with the current step name in bold Ink, above four equal 6px bars with 4px gaps. Completed and current bars are Institutional Blue; upcoming bars are Light Rule. Step names are carried as visually hidden text.

### Confirmation Panel
- White panel with a 2px Registry Green border, 4px corners, 28px 32px 32px padding (20px under 640px).
- Head: 40px filled green check circle beside a 26px bold heading that receives focus on arrival.
- A definition list of results ruled with 1px Rule Grey: 200px bold term column, value column; tabular numbers for dates and register number. A primary button starts the next request.

### Header and Footer
- **Header:** white, min 72px tall, product name (21px bold) over the organisation name (15px Slate), closed by a 4px Institutional Blue bottom rule. No logo or emblem.
- **Footer:** Office Grey band with a 1px Rule Grey top rule, 20px vertical padding, 15px Ink text.
- **Skip link:** Ink fill, white 600 text, slides into view on focus.

### Motion
Motion is minimal and functional: 0.15s ease-out colour and border transitions on buttons and the dropzone, and the 0.8s linear upload spinner. Under `prefers-reduced-motion: reduce`, transitions are removed and the spinner stops as a static ring.

## Do's and Don'ts

### Do:
- **Do** use Institutional Blue (#0052a5) for every action, link, focus outline and the header rule, and for nothing decorative.
- **Do** give every text input a 2px Ink border with square corners and the 3px blue focus outline at 2px offset.
- **Do** keep all radii at 4px or 0, except true circles (radios, step numbers, success check, spinner).
- **Do** show errors inline: red bold message above the control, red border on the control, focus moved to the first invalid field.
- **Do** set dates, sizes, counts and register numbers in tabular figures.
- **Do** keep the deadline visible wherever a request appears, using the deadline readout with its blue, amber and red tones.
- **Do** separate regions with 1px Rule Grey dividers, 2px borders or tinted fills.
- **Do** follow e-government conventions (heavy header rule, segmented stepper, numbered step circles, bordered notices, grey footer band) at gov.pl / mObywatel craft.

### Don't:
- **Don't** copy or imitate gov.pl, mObywatel or city logos, emblems or branding, and don't invent a logo.
- **Don't** add a second accent hue or use outcome colours (green, red, amber) as decoration.
- **Don't** use shadows, floating cards, pill badges or icon tiles.
- **Don't** use a dashed border anywhere but the dropzone, and never nest a dashed box inside another bordered box.
- **Don't** colour headings blue or add uppercase letter-spaced labels above headings.
- **Don't** disable the primary submit button to signal an incomplete form; let it surface the errors.
- **Don't** introduce a dark theme; the system is light-only by design.
