# Whole Process — Visio Flowchart Specs

Specification of how `FCM Documentation\Whole Process.vsdx` is built: page setup, theme, colors, typography, shape vocabulary, connectors, lanes, and layout rules. Use it as the style guide when you draw new flowcharts or edit this one.

All values come from the `.vsdx` XML and from Visio's resolved cell values (`ResultStr`). Units are inches unless noted.

---

## 1. Document setup

| Setting | Value |
|---|---|
| Application | Microsoft Visio (Office 16) |
| Template | Basic Diagram (`NEW_BASICD_U.vstx`) |
| Docked stencils | Arrow Shapes, Basic Shapes, Decorative Shapes, Graph and Math Shapes |
| Pages | 2 (`Page-1`, `Page-2`) |
| Page size | 16.54 × 11.69 in (**A3, landscape**) |
| Print margins | 0.25 in on all sides |
| Drawing scale | 1 : 1 (no scaling), US units (inches) |
| Background | None (plain white, `#FFFFFF`) |
| Theme | **Office** theme (Office 2023+ palette), variant 1, no embellishment |
| Layers (auto) | `Flowchart`, `Connector`, `Container` |
| View | Grid **off**, rulers on, guides on, connection points visible, dynamic grid on, zoom 133% |
| Routing style | Right angle (page `RouteStyle = 1`) |
| Line jumps | Horizontal lines jump (`LineJumpCode = 1`), arc style |

---

## 2. Color palette

| Role | Hex | Where it's used |
|---|---|---|
| Accent 1 (primary teal-blue) | `#156082` | Connector lines and arrowheads; fill of the emphasized parallelogram |
| Shape outline / body text | `#115472` | Outline of every flowchart shape; all shape and connector-label text; fill of the emphasized diamond |
| Dark heading teal | `#0C445E` | Lane heading text; outline of the emphasized diamond |
| Emphasis outline | `#0E4A65` | Outline of the emphasized parallelogram |
| Accent 2 (light blue) | `#61CBF4` | Lane (container) borders |
| Shape gradient (start) | `#E9ECEE` | Top-left corner of normal shapes |
| Shape gradient (end) | `#FEFFFF` | Rest of normal shapes (near-white) |
| White | `#FFFFFF` | Page background, lane fill, connector-label background, text on emphasized shapes |

Full theme color scheme (for reference): dk1 `#000000`, lt1 `#FEFFFF`, dk2 `#44546A`, lt2 `#E7E6E6`, accent1 `#156082`, accent2 `#61CBF4`, accent3 `#0B76A0`, accent4 `#96DCF8`, accent5 `#E97132`, accent6 `#4EA72E`.

The diagram is **monochrome teal/blue**. Accent 5 (orange) and Accent 6 (green) are never used.

---

## 3. Typography

All text is **Calibri** (theme font). Nothing is italic or underlined. Bold is used only in lane headings.

| Element | Size | Weight | Color | Alignment |
|---|---|---|---|---|
| Lane heading | 12 pt | **Bold** | `#0C445E` | Left, top of lane |
| Process / Input / Start-End / Subprocess text | 8 pt | Regular | `#115472` | Centered (horizontal + vertical) |
| Decision (diamond) text | **6 pt** | Regular | `#115472` | Centered |
| Connector labels (`Yes` / `No`) | 8 pt | Regular | `#115472` on white background | Centered on the line |
| Reference circles (`A`, `B`) | 10 pt | Regular | `#115472` | Centered |
| Text on emphasized shapes | Same size as shape type | Regular | `#FEFFFF` (white) | Centered |

Text margins inside shapes: 4 pt on all four sides.

---

## 4. Shape vocabulary

| Shape (master) | Meaning in this chart | Size (W × H) | Examples |
|---|---|---|---|
| **Start/End** (stadium/terminator) | Start of a flow, or `End Process` | 0.75 × 0.281 | `Start`, `End Process` |
| **Rectangle** | A UI action or process step | 1.40 × 0.583 (some 1.2125 × 0.583) | `Open Case Item`, `Hover to Search Bar`, `Click Case Field` |
| **Parallelogram** | Data entry / input / output (typing a value, printing) | 1.55 × 0.583 (field list on Page-2: 1.55 × 1.29) | `Enter [Claim Number]`, `Print All Cases Related (…)` |
| **Diamond** | Yes/No decision | 1.2125 × 0.583 (some 1.0625; one 1.40 for long text) | `Is there a Result?`, `Would you like to proceed?` |
| **Subprocess** (box with double side bars) | Hand-off to another process or tool | 1.2125 × 0.583 | `Transfer to AI Process (AI PDF Analyzer)`, `CEM Process` |
| **Circle** | On-page reference / continuation marker | 0.3125 × 0.3125 | `A`, `B` (Page-2) |
| **Plain container** | Lane that groups one system's steps | 15.75 wide, height varies | `CMS Case Management (Customer Search)` |
| **Dynamic connector** | Flow arrow | n/a | Every arrow |

Rules:
- Every box, diamond, and parallelogram is **0.583 in (7/12 in) tall**, so rows line up cleanly. Only width varies.
- Shapes have **no shadow**, **no rounding**, and **0.75 pt** outlines.

### Normal shape style
- Quick Style value 101 (Variant Style 2) on all fill, line, font, and effect cells.
- Fill: subtle **linear gradient at 60°**, from `#E9ECEE` in the top-left corner to `#FEFFFF`. The shape reads as almost white with a faint cool tint.
- Outline: `#115472`, 0.75 pt, solid.
- Text: `#115472`.

### Emphasis style (call-out shapes)
Two shapes are filled dark to call them out:

| Shape | Quick Style | Fill | Outline | Text |
|---|---|---|---|---|
| Parallelogram `Enter [Customer Name]` (the valid-customer result) | 100 (Variant Style 1) | Solid `#156082`, no gradient | `#0E4A65`, **0.25 pt** | White |
| Diamond `Did you perform a Manual Research` | 102 (Variant Style 3) | Solid `#115472`, no gradient | `#0C445E`, 0.75 pt | White |

Use this dark, solid fill with white text only for a few key pivot steps, never for whole rows.

---

## 5. Lanes (containers)

Lanes are Visio **containers** (Insert → Container → **Plain**). They are not cross-functional swimlanes.

| Property | Value |
|---|---|
| Container style | Plain |
| Width | 15.75 in (the full printable width, centered at x = 8.28) |
| Left / right edge | x ≈ 0.41 in / x ≈ 16.16 in |
| Fill | White `#FFFFFF`, no gradient |
| Border | `#61CBF4`, 0.75 pt, solid |
| Heading | Text in the top-left corner: Calibri 12 pt bold `#0C445E`, heading band 0.3125 in tall |
| Inner margin | 0.125 in |
| Stacking | Lanes are stacked **flush** top to bottom, with no gap, so they share border lines |
| Heading text pattern | `<System> (<Purpose>)`, e.g. `Referral Routing System (Start Point)` |

Page-1 lane geometry:

| Lane | Heading | Height | Y span | Rows |
|---|---|---|---|---|
| 1 | Referral Routing System (Start Point) | 1.35 | 10.00 – 11.35 | 1 |
| 2 | CMS Case Management (Customer Search) | 3.875 | 6.125 – 10.00 | 3 |
| 3 | Referral Routing System (Subject Line Builder) | 4.31 | 1.81 – 6.125 | 2 |

Page-2 has a single lane, `Provider Info Checker` (15.75 × 4.56, Y span 6.90 – 11.46).

---

## 6. Connectors

| Property | Value |
|---|---|
| Type | Dynamic connector |
| Routing | Right-angle (orthogonal), square corners (rounding 0) |
| Line | `#156082`, **1 pt**, solid |
| Arrowhead | End only: filled triangle (Visio arrow 4), medium size. No begin arrow. |
| Labels | `Yes` / `No` only, 8 pt `#115472`, **opaque white text background**, so the label sits inline and visually breaks the line (`──Yes──▶`) |
| Crossings | Horizontal line jumps over vertical lines (arc), e.g. where `Is there a Multiple Result?` drops down across the `No` line |
| Layout spacing | Avenue 0.375 in, line-to-node 0.125 in, line-to-line 0.125 in, block 0.25 in |

Every connector on both pages uses exactly this style (47 on Page-1, 4 on Page-2). There are no dashed or colored variants.

### Gluing / connection points
Connectors are glued to the **midpoint of a side**. The main flow always **leaves the right side and enters the left side**. Branches leave from the bottom or top point of a diamond.

| Shape | Connection points (index → side) |
|---|---|
| Rectangle, Diamond | 1 = bottom, 2 = right, 3 = top, 4 = left (Rectangle also has 5 = center) |
| Parallelogram | 1 = left, 2 = right, 3 = bottom, 4 = top |
| Start/End | 2 = top, 3 = left, 4 = right |
| Subprocess | 1 = left, 2 = right |

---

## 7. Layout conventions

1. **Left-to-right flow.** Each lane reads left to right. When a sub-flow needs another row, it wraps to a new row inside the same lane.
2. **Rows are center-aligned.** Every shape in a row shares the exact same center Y (for example, all of lane 1 sits at y = 10.52), so main-path connectors are perfectly straight.
3. **Even spacing.** Shapes in a row are about **0.45 – 0.70 in apart** edge to edge, which leaves just enough room for a short arrow plus a `Yes`/`No` label. Row pitch inside a lane is about **1.06 – 1.39 in**.
4. **First row offset.** The first row sits about 0.8 – 1.0 in below the top of its lane. This leaves room for the heading and the hand-off connector coming in from the lane above.
5. **Start point.** `Start` is the left-most shape in the first lane, about 1.0 in from the page's left edge.
6. **Decision branching:**
   - The path that continues the process goes **straight out the right side**.
   - The alternate path leaves from the **bottom** (or **top**) point and routes around the row with right-angle bends.
   - Every branch is labeled `Yes` or `No`.
7. **Terminators.** `End Process` stadiums sit at the right end of a row, or directly under the decision that ends the flow. Several branches can share one `End Process`.
8. **Lane hand-off.** To move to the next lane, the connector leaves the **bottom** (or right side) of the last shape. It drops into the gap at the top of the next lane, runs left across the full width, and enters the **left side** of that lane's first shape.
9. **Row wrap / loop-back.** A `Yes` that restarts or continues a sub-flow, such as `Would you like to proceed? → Yes`, routes out to the right, drops down, runs back left, and enters the first shape of the next row.
10. **Wait loops.** A polling check loops back on itself: `Is Loading Text Still exist? → Yes` leaves from the bottom and re-enters on the left.
11. **Continuation markers.** On Page-2, lettered circles (`A`, `B`) mark where a branch continues elsewhere instead of drawing a long connector.

### Label writing style
- **Action steps** start with a verb: `Open …`, `Hover to …`, `Click …`, `Enter …`, `Print …`.
- **Field values** go in square brackets: `Enter [Claim Number]`, `Enter [Customer Name]`.
- **Literal UI text or typed values** go in quotes: `Click "Like Item Search"`, `Enter "Liberty Mutual Commercial Market"`.
- **Clarifiers** go in parentheses: `Transfer to AI Process (AI PDF Analyzer)`, `(Open, Closed [within 365 days])`.
- **Decisions** are Yes/No questions, usually `Is there a …?` or `Would you like to …?`.
- Title Case is used for most nouns (`Open Case Item`, `Click Case Field`).

---

## 8. Quick recipe: drawing a new flowchart in this style

1. New Visio drawing → **Basic Diagram** → Design → Theme **Office**, variant 1. Page size **A3 landscape**, margins 0.25 in.
2. Design → Connectors → **Right Angle**. Turn on line jumps for horizontal lines.
3. Add one **Plain** container per system/stage, 15.75 in wide, stacked flush. Title each one `<System> (<Purpose>)`, 12 pt bold `#0C445E`, border `#61CBF4` 0.75 pt.
4. Place shapes left to right on a shared center line. Use Start/End 0.75 × 0.281, Rectangle 1.40 × 0.583, Parallelogram 1.55 × 0.583, Diamond 1.2125 × 0.583, Subprocess 1.2125 × 0.583. Keep them about 0.5 – 0.7 in apart.
5. Apply Quick Style **Variant Style 2** to normal shapes: light 60° gradient, `#115472` outline 0.75 pt, Calibri 8 pt `#115472` (6 pt in diamonds).
6. Connect with Dynamic connectors: 1 pt `#156082`, filled end arrow, medium. Label every decision branch `Yes`/`No` (8 pt, white text background).
7. Main path goes right side → left side. Alternate branches leave from the bottom or top. Lane hand-offs leave from the bottom and enter the next lane's first shape from the left.
8. Emphasize at most one or two pivot steps with a solid dark fill (`#156082` or `#115472`) and white text.
