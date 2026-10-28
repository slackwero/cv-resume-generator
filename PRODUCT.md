# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Today: a single user, the author.** Someone who applies
to specific postings and needs each CV to speak that posting's language without
rewriting their history from scratch every time. They run the application locally,
against their own data.

**Stated intention (2026-09-20): turn it into a product** for other applicants. The user
confirmed it explicitly when asking for the redesign. This is a product direction, not an
existing capability: today there are no accounts, no data isolation and no deployment.
See *Capabilities and Constraints*.

The artifact's second reader never touches the application: **the recruiter and the
ATS** that receive the PDF. They are the ones who judge the output, and they have no
voice in the interface.

## Product Purpose

Generate PDF résumés **tailored to each job application**, and keep an immutable history
of what was actually sent.

The mechanism: each achievement is written **only once** in a master profile. When
creating a CV, you tick which ones go in, depending on the job. The master profile is
never modified when generating, and each CV stays frozen exactly as it came out.

Success is the user applying faster without degrading what they send, and being able,
six months from now, to answer with certainty what the CV sent to a specific company
said.

## Positioning

Three things a neighboring product could not copy while telling the truth:

1. **The history is immutable and real.** Each generated CV keeps a frozen snapshot
   (`data/cvs/<id>.json`), not a recipe that is run again. What was sent can be recovered
   as it was.
2. **The sync reconciles in four cases, it does not overwrite.** Each achievement keeps
   the text as it came from LinkedIn (`imported_value`). That lets it tell "you edited it"
   from "it changed on LinkedIn" from "conflict", and in a conflict the app names the loss
   instead of warning about it.
3. **No language model or external service is involved.** Matching against the posting
   extracts terms by their *shape* (inner capitals, acronyms, technical symbols) and
   their frequency. It is a declared help, not a verdict.

## Operating Context

- **Input**: LinkedIn's ZIP export (the main path, structured CSVs) or the profile PDF
  (best-effort, anchored on the date lines). LinkedIn's official API does not expose work
  experience, and that path is closed by LinkedIn, not by the code.
- **During**: the user pastes the text of the job ad and chooses what goes in.
- **Output**: a PDF in `output/`, with the format `initials-role-monthyear.pdf`
  (e.g. `jd-devsecops-march2026.pdf`), read later by an ATS and by a person.
- **Current routes**: `/` (history), `/new` (six-step wizard), `/profile`, `/sync`.

## Capabilities and Constraints

**Confirmed and working**: ZIP and PDF import, sync with reconciliation and a conflict
dialog, a six-step wizard (template, application, presentation, experience, rest,
sections), five PDF templates, a customizable style per CV (color, font, font size and
line height, saved in the recipe and copied when cloning), an optional photo per CV,
matching against the posting, a history with cloning, and CVs generated in English or
Spanish (`i18n/`). The interface itself is in English.

**Hard constraints the redesign cannot break**:

- **LinkedIn's text is placed as is.** It is not rewritten and no sentences are
  fabricated. It is the user's rule, not a technical limitation.
- **The PDF must stay readable by an ATS.** `tests/test_templates.py` checks it: a high
  `letter-spacing` makes the extractor return text split letter by letter, and no
  automated filter recognizes the section.
- **No database.** Everything is JSON under `data/`, which holds personal data and is
  excluded from git.
- **No external services or LLMs** in the generation path.
- **A field the importer did not bring is shown empty**, never with the word "PENDING"
  inside the field.

**Explicitly undecided, do not make it up**: how it becomes a multi-user product. No
accounts, authentication, data isolation, pricing, license or deployment target have
been decided. The 2026-09-20 redesign covers the **interface**, not multi-tenancy.

**Known debt when the redesign started**: imported education is left without dates
(LinkedIn only gives the year and the model requires year-month; leaving them empty was
preferred to making up the month). The phone never comes from LinkedIn. A
`data/profile.json` older than the achievement splitting fix needs to be synced again.

## Brand Commitments

- **Name**: "CV Generator". The typographic accent falls on **CV**, the noun that names
  what the application produces, not on the generic word.
- **Interface language**: English, with `html_lang="en"`, including the `aria-label`s.
- **Voice**: honest and literal. The application does not promise what it does not do —
  three messages that over-promised were a P1 finding in the 2026-08-28 critique. A help
  is declared as a help ("it is not a verdict"), not disguised as intelligence.

## Evidence on Hand

- `data/profile.json` — the user's real profile (personal data, outside git).
- `data/history.json` and `data/cvs/` — CVs actually generated.
- `templates/{modern,executive,technical,sidebar,direct}/` — five live templates, with
  63 text color rules measured (9 + 10 + 11 + 19 + 14, in that order), each against its
  background, with the template's colors and with every palette color: all pass AA.
  `direct` is the one marked as ATS in the wizard.
- Two earlier interface critiques (20/40 and 25/40), kept as local notes outside the
  repository.
- `i18n/es.json`, `i18n/en.json` — the output strings.

**Does not exist and must not be fabricated**: testimonials, customers, usage metrics,
pricing, competitor comparisons, or a logo. Today the brand is the name and nothing else.

## Product Principles

1. **The master profile is the source of truth; generating never modifies it.**
2. **What was sent is immutable.** The history recovers, it does not rebuild.
3. **Name the loss before causing it**, and put the ceremony on what is irreversible
   (writing a permanent PDF) and not on what is reversible.
4. **Declare the limits of the help.** Counting word occurrences is not understanding the
   text, and the interface says so.
5. **The artifact rules.** What decides success is a PDF an ATS reads and a person
   judges; the tool exists to produce it.

## Accessibility & Inclusion

- **ATS readability** of the generated PDF: a product requirement verified by tests.
- A minimum 44px touch target on touch screens (`touch_target()`); the critique found it
  was only applied to buttons and not to the inputs.
- State already held that must not be lost: `html_lang="en"`, one `h1` per route,
  `:focus-visible` across the interface, `aria-current` in the navigation, 0 console
  errors.
