# Frontend Rules

## Framework

- React 19 (Create React App) — do NOT migrate to Next.js or Vite without approval
- Tailwind CSS for all styling — follow `design_guidelines.json`

## Design System (Non-Negotiable)

- Color palette: "Venture Obsidian" — always use hex values from `design_guidelines.json`
- Forbidden colors: `#1B93A4`, `#7351B7` — never use these
- Headings: `Chivo` font — never use `Inter` for headings
- Body text: `Inter` font
- Monospace (data/scores/financial): `JetBrains Mono`
- Border radius: `rounded-sm` — no rounded-lg or rounded-full on containers
- Icons: `lucide-react` only
- Charts: `recharts` only (radar for scoring, area for traction)
- Dark theme only — background `#09090b`, surface `#18181b`

## Component Rules

- All components MUST use **named exports** (no default exports)
- All interactive elements MUST have `data-testid` attributes
- Never duplicate UI logic — extract to `components/` or `components/ui/`
- Keep components focused and single-responsibility
- UI primitives: `ScoreRing`, `TierBadge`, `StatusBadge`, `MetricCard`

## Page Structure

| Page | Purpose |
|------|---------|
| `Dashboard.js` | Bento grid: pipeline stats, tier distribution, recent deals |
| `Upload.js` | **Multi-input**: drag file + website URL + LinkedIn URL + raw text paste |
| `Companies.js` | Table: logo, name, tier badge, score, status filter |
| `CompanyDetail.js` | Tabbed: Overview / Intel / Scoring / Memo / Competitors / Export |

## Tier Badge Colors

| Tier | Color | Label |
|------|-------|-------|
| TIER_1 | Green (`#10b981`) | Generational |
| TIER_2 | Blue (`#3b82f6`) | Strong |
| TIER_3 | Amber (`#f59e0b`) | Consider |
| PASS | Red (`#ef4444`) | Pass |

## Layout

- Grid system: Bento Grid Mode B (High Density)
- Container: `max-w-[1600px] mx-auto px-4 md:px-8`
- Glassmorphism: `bg-[#09090b]/80 backdrop-blur-md` for sticky headers
- Subtle noise texture on backgrounds

## Forbidden

- No AI assistant emoji (🤖🧠) in the UI
- No generic centered layouts — create depth with z-index hierarchy
- No random hex codes outside the palette
- No full-background gradients (subtle glows only)
- No placeholder images — generate or use real assets

## Dependencies

Required: `lucide-react`, `recharts`, `clsx`, `tailwind-merge`
