# Design System Handoff Guide

## Claude Code + shadcn/ui: From Design to Production

A practical guide for **Design** and **Engineering** teams to collaborate using Claude Code as the bridge between design intent and production code.

---

## Table of Contents

1. [The Workflow at a Glance](#the-workflow-at-a-glance)
2. [Environment Setup for Designers](#environment-setup-for-designers)
3. [How Designers Should Prompt Claude Code](#how-designers-should-prompt-claude-code)
4. [Component Maturity Levels](#component-maturity-levels)
5. [What Designers Own vs. What Eng Owns](#what-designers-own-vs-what-eng-owns)
6. [shadcn/ui Component Patterns](#shadcnui-component-patterns)
7. [File & Folder Conventions](#file--folder-conventions)
8. [The Handoff Checklist](#the-handoff-checklist)
9. [Prompting Recipes for Common Components](#prompting-recipes-for-common-components)
10. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
11. [FAQ](#faq)

---

## The Workflow at a Glance

```
Design Team (Claude Code)              Engineering Team
─────────────────────────              ────────────────
1. Scaffold component                  5. Review PR / design spec
2. Build visual states & variants      6. Wire up data, APIs, state
3. Add interactions & animations       7. Add error handling & edge cases
4. Open PR with preview screenshots    8. Integration test & ship
```

**Core principle:** Designers take components as far as possible visually and interactively. Engineers connect them to real data, business logic, and infrastructure.

---

## Environment Setup for Designers

### Prerequisites

Designers need a **component playground project** set up once by Engineering. This is a standalone Next.js + shadcn/ui project specifically for design work.

Ask Engineering to create this once:

```bash
npx create-next-app@latest design-playground --typescript --tailwind --eslint --app --src-dir
cd design-playground
npx shadcn@latest init
```

### Required shadcn/ui components to pre-install

Install the full library up front so designers never hit missing-component errors:

```bash
npx shadcn@latest add --all
```

### Designer's daily workflow

```bash
# 1. Open the project
cd design-playground

# 2. Start the dev server (keep this running in a separate terminal)
npm run dev

# 3. Open Claude Code and start building
claude
```

> **Tip:** Designers should always have `npm run dev` running so they can preview changes in the browser at `localhost:3000` as Claude Code writes them.

---

## How Designers Should Prompt Claude Code

### The anatomy of a good design prompt

A good prompt has **four parts**:

1. **What** the component is
2. **Where** it lives (page context)
3. **Visual spec** (layout, colors, spacing, typography)
4. **States** it needs (default, hover, loading, empty, error)

### Example: Good prompt

> Build a user profile card component using shadcn Card, Avatar, and Badge.
>
> - Card has a subtle border, rounded-xl, and a hover shadow transition
> - Top section: Avatar (48px) left-aligned, next to name (text-lg font-semibold) and role (text-sm text-muted-foreground)
> - Middle section: 3-column stat grid showing "Workouts", "Streak", "Score" with large numbers and small labels
> - Bottom section: Two buttons side by side using shadcn Button — "View Profile" (default variant) and "Message" (outline variant)
> - States needed: default, loading (skeleton), empty (no avatar placeholder)
> - Use the default shadcn theme colors, no custom colors

### Example: Bad prompt

> Make me a profile card that looks nice

### Prompt templates designers can copy-paste

**For a new component:**
```
Build a [component name] using shadcn [specific components].

Layout:
- [describe structure top to bottom or left to right]

Visual details:
- [spacing, colors, typography, borders, shadows]

States:
- Default: [describe]
- Hover: [describe]
- Loading: [describe]
- Empty: [describe]
- Disabled: [describe if applicable]

Responsive:
- Mobile: [describe changes]
- Desktop: [describe changes]

Place this in src/components/[folder]/[name].tsx
Create a demo page at src/app/preview/[name]/page.tsx that shows all states.
```

**For iterating on an existing component:**
```
Read src/components/[path].tsx.

Make these changes:
1. [specific change with exact values]
2. [specific change with exact values]

Keep everything else the same.
```

---

## Component Maturity Levels

Every component goes through these levels. Designers are responsible for Levels 1-3. Engineers take over at Level 4.

### Level 1: Structure (Designer)

- Correct shadcn components chosen and composed
- Semantic HTML structure (headings, sections, lists)
- Basic layout with Tailwind (flex, grid, spacing)
- Component accepts props for all variable content

### Level 2: Visual Polish (Designer)

- All spacing, typography, and colors finalized
- Responsive breakpoints working (mobile-first)
- Dark mode support (if applicable)
- Animations and transitions added (hover, focus, enter/exit)
- Consistent with existing components in the system

### Level 3: States & Variants (Designer)

- All visual states built: default, hover, active, focus, disabled, loading, empty, error
- Skeleton/loading placeholders using shadcn Skeleton
- Variants defined as props (size="sm|md|lg", variant="default|outline|ghost")
- Demo page showing every state and variant side by side

### Level 4: Data & Logic (Engineering)

- Replace hardcoded strings/numbers with real data
- Connect to APIs, state management, context
- Add form validation, error handling, retry logic
- Accessibility audit (keyboard nav, screen readers, ARIA)
- Unit and integration tests

### Level 5: Production (Engineering)

- Performance optimization (lazy loading, memoization)
- Analytics and tracking events
- Feature flags if needed
- Production error boundaries

---

## What Designers Own vs. What Eng Owns

| Aspect | Designer | Engineer |
|--------|----------|----------|
| Component structure & layout | Yes | Review |
| Tailwind classes & styling | Yes | Review |
| shadcn component selection | Yes | May swap if needed |
| Prop interface (shape of data) | Draft | Finalize |
| Hardcoded demo content | Yes | Replace with real data |
| Hover / focus / transition states | Yes | Review |
| Loading skeletons | Yes | Wire to real loading state |
| Responsive breakpoints | Yes | Test on real devices |
| API calls & data fetching | No | Yes |
| Form validation logic | No | Yes |
| Error handling & retries | No | Yes |
| Auth-gated visibility | No | Yes |
| Unit / integration tests | No | Yes |
| Accessibility (ARIA, keyboard) | Basic | Full audit |
| Performance optimization | No | Yes |

---

## shadcn/ui Component Patterns

### Use shadcn primitives, not raw HTML

```tsx
// DO: Use shadcn components
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

// DON'T: Rebuild what shadcn already provides
<button className="rounded-md bg-primary px-4 py-2 text-white">Click</button>
<div className="rounded-lg border p-4 shadow">...</div>
```

### Compose, don't customize

Build complex components by **composing** shadcn primitives, not by overriding their internals:

```tsx
// DO: Compose shadcn components together
function MetricCard({ label, value, trend }: MetricCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold">{value}</p>
        <Badge variant={trend > 0 ? "default" : "destructive"}>
          {trend > 0 ? "+" : ""}{trend}%
        </Badge>
      </CardContent>
    </Card>
  )
}
```

### Keep styling in Tailwind, not inline styles

```tsx
// DO
<div className="flex items-center gap-4 p-6">

// DON'T
<div style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '24px' }}>
```

### Use CSS variables from the shadcn theme

Reference theme tokens, not raw color values:

```tsx
// DO: Theme-aware colors
className="text-foreground"
className="bg-muted"
className="border-border"
className="text-muted-foreground"
className="bg-primary text-primary-foreground"

// DON'T: Hardcoded colors that break in dark mode
className="text-gray-900"
className="bg-gray-100"
className="text-white"
```

### Common shadcn theme tokens

| Token | Usage |
|-------|-------|
| `background` / `foreground` | Page background and default text |
| `card` / `card-foreground` | Card surfaces |
| `primary` / `primary-foreground` | Primary actions, buttons |
| `secondary` / `secondary-foreground` | Secondary actions |
| `muted` / `muted-foreground` | Subtle backgrounds, helper text |
| `accent` / `accent-foreground` | Hover states, highlights |
| `destructive` / `destructive-foreground` | Errors, delete actions |
| `border` | Borders and dividers |
| `ring` | Focus rings |

---

## File & Folder Conventions

### Directory structure for design components

```
src/
├── components/
│   ├── ui/                    # shadcn primitives (DO NOT EDIT)
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   └── ...
│   │
│   └── custom/                # Designer-built components go here
│       ├── profile-card.tsx
│       ├── metric-dashboard.tsx
│       ├── activity-feed.tsx
│       └── ...
│
├── app/
│   └── preview/               # Demo pages for each component
│       ├── profile-card/
│       │   └── page.tsx       # Shows all states and variants
│       ├── metric-dashboard/
│       │   └── page.tsx
│       └── ...
```

### Naming rules

| Item | Convention | Example |
|------|-----------|---------|
| Component files | kebab-case | `profile-card.tsx` |
| Component names | PascalCase | `ProfileCard` |
| Props interfaces | PascalCase + Props | `ProfileCardProps` |
| Preview pages | Match component name | `app/preview/profile-card/page.tsx` |
| CSS classes | Tailwind only | `className="flex gap-4"` |

### What NOT to create

- No `.css` or `.scss` files (Tailwind only)
- No files inside `components/ui/` (shadcn-managed)
- No `utils/` or `lib/` files (that's Eng's domain)
- No API route files
- No context providers or stores

---

## The Handoff Checklist

Before opening a PR or notifying Eng, designers should verify:

### Structure
- [ ] Component uses shadcn primitives (not raw HTML equivalents)
- [ ] Props interface is defined with TypeScript types
- [ ] All variable text/numbers are passed as props (not hardcoded in the component — hardcoded values belong in the demo page only)
- [ ] Component has a clear, single responsibility

### Visual
- [ ] Uses shadcn theme tokens (not hardcoded colors)
- [ ] Spacing uses Tailwind scale (p-4, gap-6, etc. — not arbitrary values)
- [ ] Typography uses Tailwind scale (text-sm, text-lg, font-semibold, etc.)
- [ ] Responsive: looks correct at mobile (375px), tablet (768px), desktop (1280px)

### States
- [ ] Default state renders correctly
- [ ] Loading state uses shadcn Skeleton components
- [ ] Empty state has a meaningful placeholder
- [ ] Hover and focus states are visible
- [ ] Disabled state (if applicable) looks distinct

### Demo page
- [ ] Preview page exists at `app/preview/[component-name]/page.tsx`
- [ ] Shows every variant (size, color, type)
- [ ] Shows every state (default, loading, empty, error, disabled)
- [ ] Uses realistic dummy content (not "Lorem ipsum" — use plausible names, numbers, text)

### PR description
- [ ] Screenshots of every state attached
- [ ] List of shadcn components used
- [ ] Notes on any design decisions or tradeoffs
- [ ] Callout of anything Eng needs to decide (e.g., "animation duration TBD")

---

## Prompting Recipes for Common Components

### Recipe 1: Data table

```
Build a data table for displaying workout history using shadcn Table.

Columns: Date, Activity Type, Duration, Distance, Calories, Strain Score.

Features:
- Sortable column headers (click to toggle asc/desc, show arrow indicator)
- Alternating row backgrounds using muted/background
- Hover highlight on rows
- Badge for activity type (Run = default, Cycle = secondary, Swim = outline)
- Empty state: illustration placeholder + "No workouts yet" text + CTA button

Place component in src/components/custom/workout-table.tsx
Create preview at src/app/preview/workout-table/page.tsx with 10 rows of
realistic demo data, plus an empty state view.
```

### Recipe 2: Dashboard metric cards

```
Build a responsive dashboard grid of metric cards using shadcn Card.

Grid: 2 columns on mobile, 4 columns on desktop.

Each card shows:
- Icon placeholder (24px, text-muted-foreground) top-left
- Metric label (text-sm text-muted-foreground)
- Metric value (text-3xl font-bold)
- Trend badge: green Badge for positive, red (destructive) for negative
- Sparkline placeholder area (h-12 bg-muted rounded, Eng will replace with chart)

Cards: Recovery Score, HRV, Resting HR, Sleep Score
Loading state: Skeleton for every element in each card.

Place in src/components/custom/metric-grid.tsx
Preview at src/app/preview/metric-grid/page.tsx showing loaded and loading states.
```

### Recipe 3: Settings form

```
Build a settings/preferences form using shadcn form components.

Sections (use Card for each section):
1. Profile: Avatar upload area + name Input + email Input
2. Notifications: Switch toggles for "Email", "Push", "Weekly Digest"
3. Connected Accounts: List items showing Whoop and Strava
   with connection status Badge and Connect/Disconnect Button

Footer: "Save changes" Button (default) + "Cancel" Button (ghost)

Use shadcn: Card, Input, Label, Switch, Button, Badge, Separator, Avatar

Loading state: Skeleton over entire form.
Disabled state: All inputs disabled, save button shows loading spinner.

Place in src/components/custom/settings-form.tsx
Preview at src/app/preview/settings-form/page.tsx
```

### Recipe 4: Navigation header

```
Build a responsive navigation header using shadcn components.

Desktop (>= 768px):
- Logo text left-aligned ("AppName", text-xl font-bold)
- Nav links center: Dashboard, Activity, Settings (text-sm, underline on active)
- Right side: Avatar dropdown using shadcn DropdownMenu
  - Menu items: Profile, Settings, Separator, Sign Out

Mobile (< 768px):
- Logo left, hamburger Button (ghost, Menu icon) right
- Sheet component slides in from left with stacked nav links

Use shadcn: Button, DropdownMenu, Sheet, Avatar, Separator

Place in src/components/custom/nav-header.tsx
Preview at src/app/preview/nav-header/page.tsx showing both breakpoints.
```

---

## Anti-Patterns to Avoid

### For Designers

| Anti-Pattern | Why It's Bad | Do This Instead |
|---|---|---|
| Writing API calls or fetch logic | Will be rewritten by Eng; wastes time | Use hardcoded demo data in preview page |
| Installing new npm packages | May conflict with Eng's choices | Ask Eng first; stick to shadcn + Tailwind |
| Editing files in `components/ui/` | These are shadcn-managed and will be overwritten on update | Compose ui/ components in `components/custom/` |
| Using arbitrary Tailwind values (`w-[347px]`) | Breaks responsive design, hard to maintain | Use Tailwind scale values (`w-80`, `max-w-sm`) |
| Hardcoding text inside the component | Makes the component single-use | Pass all content as props; hardcode only in the demo page |
| Putting everything in one giant component | Hard for Eng to work with | Break into smaller, focused components |
| Skipping the preview page | Eng can't see what you intended | Always create the preview page with all states |
| Using `any` for TypeScript types | Defeats the purpose of typed props | Define explicit types for every prop |
| Adding `onClick` handlers with business logic | That's Eng's job | Use `onClick` only for visual state toggles (e.g., tabs, accordions) |

### For Engineers

| Anti-Pattern | Why It's Bad | Do This Instead |
|---|---|---|
| Rewriting designer components from scratch | Wastes designer's work, creates conflict | Modify in place; keep the visual layer intact |
| Changing Tailwind classes without design review | May break intended design | Flag visual changes in PR for design review |
| Skipping the designer's prop interface | Breaks the component contract | Extend the interface, don't replace it |
| Removing loading/empty states | "We'll add them later" = never | Keep all states; wire them to real conditions |

---

## FAQ

### "Can designers use Claude Code for prototyping without the playground?"

Yes, but it's less efficient. Claude Code can scaffold a component as a standalone file, but without a running dev server, there's no way to preview it. The playground project is a small investment that pays off immediately.

### "What if I need a component that shadcn doesn't have?"

Ask Claude Code to build it from shadcn primitives. Most complex UI (charts, calendars, kanban boards) can be composed from Card, Button, Badge, and basic HTML + Tailwind. For truly complex widgets (rich text editors, map views), flag it for Eng to choose the right library.

### "How do I handle icons?"

Use [Lucide React](https://lucide.dev/), which ships with shadcn/ui:

```tsx
import { Activity, Heart, Moon } from "lucide-react"

<Activity className="h-4 w-4 text-muted-foreground" />
```

Tell Claude Code which icon you want by name, or describe what it should represent and ask it to pick from Lucide.

### "Should designers write tests?"

No. Tests are Eng's responsibility. Designers should focus on visual completeness and the preview page.

### "How detailed should the PR description be?"

Very. Think of the PR as the design spec. Include:
- Screenshot of every state
- Explanation of any non-obvious design decisions
- List of questions or things that are TBD
- Which shadcn components were used

### "What if Eng needs to change the visual design?"

Eng should comment on the PR or open a follow-up issue. Visual changes should loop in the designer so the component stays consistent with the design system.

### "Can designers branch and push code?"

Yes. The recommended flow:
1. Designer creates a branch: `design/[component-name]`
2. Designer pushes component + preview page
3. Designer opens a PR with screenshots and notes
4. Eng reviews, then creates a branch off the designer's branch for wiring up logic
5. Eng opens a separate PR to merge the finished component to main

---

## Quick Reference Card

**Designer's Claude Code Cheat Sheet:**

```
Start building:     "Build a [component] using shadcn [primitives]..."
Iterate:            "Read src/components/custom/[name].tsx. Change [specific thing]."
Add a state:        "Add a loading state using Skeleton components."
Add responsive:     "Make this stack vertically on mobile (< 768px)."
Preview page:       "Create a preview page showing all states and variants."
Check your work:    Open localhost:3000/preview/[name] in browser
Prepare handoff:    "Take a screenshot of this page." (if using browser tools)
```

**Branch naming:**
```
design/profile-card
design/metric-dashboard
design/settings-form
```

**File locations:**
```
Component:  src/components/custom/[name].tsx
Preview:    src/app/preview/[name]/page.tsx
```
