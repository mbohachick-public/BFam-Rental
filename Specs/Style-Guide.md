# BFam Rental — Style Guide

This guide aligns the website with the current logo (`assets/bfam-rental-logo.png`): dump-trailer mark and wordmark in **forest green**, **“RENTAL”** in **charcoal**, **orange** accent bars, on **warm cream**.

## Brand principles

- **Feel:** Heavy-duty, dependable, straightforward — equipment rental, not lifestyle travel.
- **Clarity:** High contrast for outdoor brightness and quick scanning on phones.
- **Restraint:** Orange is for **accents and actions**; green anchors **brand and structure**.

---

## Color palette

Use these tokens across CSS (or design tools). Hex values are starting points; tweak slightly after side-by-side comparison with the logo file.

| Token | Hex | Usage |
|--------|-----|--------|
| `--color-brand-green` | `#1E4D3A` | Primary brand, headers, key UI chrome, trailer-mark mood |
| `--color-brand-green-dark` | `#16382A` | Hover states, dark sections, footer |
| `--color-accent-orange` | `#E85D04` | Primary buttons, focus rings, badges, “Book / Request” CTAs |
| `--color-accent-orange-hover` | `#C54E03` | Button hover |
| `--color-text-primary` | `#1C1917` | Body copy, “RENTAL”-weight secondary headlines |
| `--color-text-muted` | `#57534E` | Supporting text, captions |
| `--color-border` | `#D6D3D1` | Dividers, card outlines |
| `--color-surface` | `#FFFFFF` | Cards, modals, form fields |
| `--color-canvas` | `#FAF8F3` | Page background (matches logo cream) |
| `--color-success` | `#166534` | Confirmations (distinct from brand green if needed) |
| `--color-danger` | `#B91C1C` | Errors, destructive actions |
| `--color-focus` | `#E85D04` | Focus outline (same as accent or 2px ring + offset) |

**Accessibility:** Pair `--color-text-primary` on `--color-canvas` or `--color-surface` for main content. For **orange text on cream**, use only at **large sizes** (e.g. headings ≥18px bold) or prefer **orange backgrounds with white text** for small labels.

### CSS custom properties (drop-in)

```css
:root {
  --color-brand-green: #1e4d3a;
  --color-brand-green-dark: #16382a;
  --color-accent-orange: #e85d04;
  --color-accent-orange-hover: #c54e03;
  --color-text-primary: #1c1917;
  --color-text-muted: #57534e;
  --color-border: #d6d3d1;
  --color-surface: #ffffff;
  --color-canvas: #faf8f3;
  --color-success: #166534;
  --color-danger: #b91c1c;
  --radius-sm: 6px;
  --radius-md: 10px;
  --shadow-card: 0 1px 3px rgb(28 25 23 / 8%);
}
```

---

## Typography

**Logo alignment:** Bold geometric **sans-serif** — clean, no serifs, industrial stability.

**Web stack (recommended):**

- **Headings:** [Outfit](https://fonts.google.com/specimen/Outfit) or [DM Sans](https://fonts.google.com/specimen/DM+Sans) — semibold/bold for H1–H2, medium for H3.
- **Body / UI:** Same family as headings for cohesion, or **DM Sans** body + **Outfit** headings.

**Scale (fluid where helpful):**

| Role | Weight | Size (desktop) | Notes |
|------|--------|----------------|--------|
| H1 | 700 | clamp(1.75rem, 4vw, 2.25rem) | Page title; optional green |
| H2 | 600 | 1.25–1.5rem | Section titles |
| H3 | 600 | 1.1–1.25rem | Card titles |
| Body | 400–500 | 1rem (16px min on mobile) | Line-height 1.5–1.6 |
| Small / meta | 500 | 0.875rem | Labels, captions; muted color |
| Button | 600 | 0.9375rem | All caps optional for primary only |

**Rules**

- Avoid light gray body text below **#57534E** on cream.
- Use **sentence case** for UI strings; **ALL CAPS** sparingly (e.g. “RENTAL”-style micro-labels only).

---

## Logo usage

- **Clear space:** At least **0.5×** the height of the “BFam” wordmark on all sides.
- **Minimum width:** ~**120px** wide for web; below that, use a **simplified mark** (future: icon-only asset).
- **Backgrounds:** Prefer **cream** (`#FAF8F3`) or **white**; on **dark green** header, provide a **white or cream logo variant** if contrast fails (export alternate from source art).
- **Don’t:** Stretch, rotate, change green/orange proportions, or place on busy photos without a solid backing plate.

---

## Layout and spacing

- **Max content width:** `72rem` (1152px) for marketing/catalog; forms can be narrower (`min(32rem, 100%)`).
- **Spacing scale:** `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64px` — default section vertical rhythm **32–48px**.
- **Grid:** Catalog cards **1 col** mobile, **2** tablet, **3–4** desktop; consistent **gap: 1rem–1.5rem**.

---

## Components

**Primary button**

- Background: `--color-accent-orange`; text: **white**; hover: `--color-accent-orange-hover`.
- Padding: `0.625rem 1.25rem`; radius: `--radius-md`; font-weight **600**.

**Secondary button**

- Border: `2px solid var(--color-brand-green)`; text: `--color-brand-green`; background transparent; hover: light green tint background (`#1e4d3a0d`).

**Links (inline)**

- Default: `--color-brand-green`; underline on hover; focus: **2px orange outline**.

**Cards (catalog items)**

- Background `--color-surface`; border `1px solid var(--color-border)` or subtle `--shadow-card`; radius `--radius-md`.

**Header / nav**

- Background `--color-brand-green` or `--color-surface` on cream canvas; if green bar, nav links **white** or **cream**, hover **orange** underline or tint.

**Tags / status (calendar)**

- Map booking states to calm, distinct colors (e.g. open = green tint, booked = neutral, out = muted red, readying = amber) — keep legend next to calendar.

---

## Imagery

- **Photography:** Real equipment, yards, and hands-on context; natural light; slightly warm white balance to match cream UI.
- **Icons:** Simple line icons **1.5px** stroke, rounded caps; color `--color-text-muted` or `--color-brand-green`.

---

## Voice (microcopy)

- **Direct:** “Request dates,” “Cost per day,” “Deposit,” not fluffy marketing filler.
- **Trust:** Mention minimum days, deposit, and requirements where the spec calls for it.
- **Friendly:** Short sentences; “we” optional for small family-business tone.

---

## Files

| Asset | Path |
|--------|------|
| Primary logo | `assets/bfam-rental-logo.png` |
| Named copy | `assets/bfam-rental-logo-dump-trailer.png` |

When the frontend ships, import the **CSS variables** block into global styles and apply **Outfit/DM Sans** via `@font-face` or Google Fonts.
