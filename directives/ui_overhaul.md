# UI/UX Overhaul Directive

> **Status: completed** (glassmorphism + deep dark mode shipped; verification panel with claims/verdicts/confidence added to Dashboard). Kept as design reference only.

## Goal
Transform the Vanta frontend into a premium, award-winning styling implementation using Glassmorphism, Deep Dark Mode, and Vibrant Gradients.

## Inspiration
- **Style**: Modern Glassmorphism (Apple Vision Pro OS style / Linear.app style).
- **Reference**: Awwwards winning dashboards.
- **Key Elements**:
    - **Background**: Deep, rich dark gradients (Mesh gradients).
    - **Cards**: Translucent backgrounds with subtle white borders (`backdrop-blur`).
    - **Typography**: Clean, high-contrast sans-serif (Inter).
    - **Interactions**: Subtle hover glows, smooth transitions.

## Implementation Steps

### 1. Foundation (`index.css` & `tailwind.config.js`)
- [ ] Update `tailwind.config.js` with a "Space" color palette (Deep violets, blacks, neon accents).
- [ ] Add `backdrop-blur` utilities and custom animations.
- [ ] Apply a global mesh gradient background in `index.css`.
- [ ] Create a `.glass-panel` utility class within `@layer components` for reusability.

### 2. Layout Structure
- [ ] Redesign Sidebar: Floating glass panel on the left (or top if mobile).
- [ ] Redesign Header: Minimalist, transparent.

### 3. Component Design
- [ ] **Dashboard Cards**: Replace flat white/gray cards with glass containers.
- [ ] **Metrics**: Use gradient text for key numbers.
- [ ] **Data Viz**: Update Recharts to use the new color palette (Neon lines/bars).

### 4. Polish
- [ ] Add loading skeletons (shimmer effect with lower opacity).
- [ ] meaningful hover states for all interactive elements.

## Rules
- **Do not break functionality**: The app must still fetch and display platform data.
- **Mobile First**: Ensure glass view works on mobile (or degrades gracefully).
- **Performance**: Avoid excessive blur on large areas if it causes lag (use `will-change`).
