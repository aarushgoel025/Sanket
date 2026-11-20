# Design

**Project:** Sanket (working name)
Covers: (1) signboard visual design, (2) task and difficulty design, (3) augmentation, (4) demo UI, (5) report figures.

---

## 1. Design principles

1. **Evidence must be visible.** Every task keeps its evidence (target label, arrow, closure mark or notice) unoccluded. Difficulty comes from layout and reasoning, never from hiding the answer.
2. **Vary relationships, not names.** Variety means different arrow angles, groupings, closures, overrides and turns, not renamed destinations.
3. **Realistic but fictional.** Boards follow common signage conventions but use fictional venues and issuers. A small "SYNTHETIC" mark appears on every image.
4. **Machine-checkable by design.** Every visual element that carries meaning has an HTML id so the renderer can export its geometry for verification.

## 2. Signboard visual system

### 2.1 Colours (board categories)

| Category | Background | Text and icon |
|---|---|---|
| General direction | Dark blue `#12355B` | White `#FFFFFF` |
| Platforms and transport | Dark green `#0F5132` | White |
| Medical and emergency | Red `#B3261E` | White |
| Facilities (toilet, lift, ticket) | Dark gray `#2E3338` | White |
| Temporary notice | Yellow `#F2C230` | Black `#111111` |
| Closed overlay | Semi-transparent red cross with the word CLOSED and the Hindi equivalent | Red `#B3261E` on white label |

### 2.2 Typography
- Latin: Noto Sans (bold for destination names).
- Hindi: Noto Sans Devanagari.
- Regional script (stretch): one of Noto Sans Tamil or Noto Sans Bengali.
- Minimum rendered text height: 18 px at the base 1280x720 render, before augmentation.
- Fonts are loaded from `assets/fonts` only; a missing glyph is a build error, not a fallback.

### 2.3 Arrows
- One SVG arrow shape, rotated by `arrow_angle` in 45-degree steps (0 = up = ahead, 90 = right).
- Arrow length at least 48 px, stroke at least 6 px, high contrast with the board.
- Each arrow element has `data-dest-id` and `data-angle` attributes for the fidelity check.

### 2.4 Board templates

| Template | Layout | Used for |
|---|---|---|
| `board_list` | Single column, arrow on the left of each text row | DIRECT, OVERRIDE, CLOSURE |
| `board_grid` | Two columns with pictograms and arrows | BINDING (grouped arrows, similar labels) |
| `board_gantry` | Wide overhead sign with arrows grouped by direction column | BINDING, EGOCENTRIC |

Arrow placement variants (left of text, right of text, shared arrow for a group) are a difficulty knob for BINDING.

### 2.5 Temporary notice
A yellow paper-style panel placed beside the main board with an arrow and a short text such as "Platform 4: use left corridor". It always carries its own `data-source="temporary_notice"` attribute.

### 2.6 Pictograms
Own simple SVG icons (train, hospital cross, exit, toilet, lift, ticket, pharmacy). No logos, no third-party brand marks.

## 3. Task and difficulty design

### 3.1 Knobs

| Knob | Range |
|---|---|
| `n_entries` | 2 to 8 |
| `scripts` | `en`; `en+hi`; `en+hi+regional` |
| `template` | list, grid, gantry |
| `perspective_deg` | 0 to 25 |
| `blur` | 0 to 2.5 |
| `noise` | 0 to 0.06 |
| `lighting` | 0 to 0.4 (gradient and shadow strength) |
| `clutter` | 0 to 6 distractors (ads, unrelated icons, numbers) |
| `occlusion` | 0 to 0.15 of board area, never over evidence |
| `jpeg_quality` | 95 down to 60 |

### 3.2 Skill tags
`arrow_reading`, `text_arrow_binding`, `multi_script`, `negation_closure`, `override_reasoning`, `egocentric_rotation`, `absence_detection`.

### 3.3 Balancing
- At least 50 tasks per question type in the final 400.
- Gold answers balanced across the 10 options within each type as far as the graph allows; a task is rejected if one answer exceeds 25% of its type.
- Each minimal pair changes one thing: an arrow angle, an open/closed status or a notice present/absent.

## 4. Augmentation order (seeded)

1. Render the clean board at 1280x720.
2. Paste distractors and decoration (ads, stickers) outside the evidence regions.
3. Apply lighting gradient and shadow.
4. Apply perspective warp (arrows stay readable at 25 degrees).
5. Apply blur, then noise.
6. Apply JPEG compression, then save as PNG with metadata stripped.

Every step takes the task's random generator; none uses global randomness.

## 5. Demo UI (Streamlit)

### Page 1: Generate and test
```
+-----------------------------------------------------------+
| Sanket                                  [venue v] [seed]  |
+---------------------+-------------------------------------+
| Controls            |  Board image                        |
|  question type  v   |                                     |
|  difficulty knobs   |                                     |
|  [Generate]         |                                     |
+---------------------+-------------------------------------+
| Question text                                             |
| Options: ( ) AHEAD ( ) LEFT ... ( ) NOT_INDICATED         |
| Model: [v]  Mode: (image)(text)   [Ask model]             |
+-----------------------------------------------------------+
| Result: model answer | gold | CORRECT / WRONG (colour+icon)|
| [Reveal proof] -> venue graph with the route highlighted, |
|                   receipt table (solver, independent,     |
|                   fidelity, visibility, blind test)       |
+-----------------------------------------------------------+
```

### Page 2: Findings
Loads cached results: heatmap (model by skill by difficulty), perception gap bars, pair-consistency table, failure gallery with the real-world consequence for each failure.

### Page 3: Pairs
Shows a minimal pair side by side with both gold answers and each model's answers.

### UX rules
- Correct versus wrong is shown with icon and text, never colour alone.
- Everything works from cached data when offline (demo safety).
- No login, no database, no hosted dependencies.

## 6. Report figures

| Figure | Chart | Message |
|---|---|---|
| F1 | Heatmap: model x skill | Where each model fails |
| F2 | Line: accuracy vs difficulty knob per model | How degradation hurts |
| F3 | Grouped bar: image vs text mode | Perception versus reasoning gap |
| F4 | Bar: hallucination rate on ABSENT | Models answering when the board has no answer |
| F5 | Scatter: synthetic vs real accuracy per model | Whether findings transfer |
| F6 | Table: pair consistency | Whether models actually look |

Style: colourblind-safe palette, labelled axes, sample size and 95% intervals shown, one takeaway sentence under each figure.

## 7. Accessibility and ethics
- Alt text for every demo image and figure.
- Real photos: no faces or people, EXIF stripped, only public signage.
- All issuers and venues fictional; "SYNTHETIC" mark on generated images.
