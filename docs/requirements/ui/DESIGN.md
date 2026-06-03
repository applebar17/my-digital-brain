---
name: Cerebral Cartography
colors:
  surface: '#fbf8ff'
  surface-dim: '#dad9e3'
  surface-bright: '#fbf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f2fd'
  surface-container: '#eeedf7'
  surface-container-high: '#e8e7f1'
  surface-container-highest: '#e3e1ec'
  on-surface: '#1a1b22'
  on-surface-variant: '#46464b'
  inverse-surface: '#2f3038'
  inverse-on-surface: '#f1effa'
  outline: '#77767b'
  outline-variant: '#c7c6cb'
  surface-tint: '#5f5e61'
  primary: '#121315'
  on-primary: '#ffffff'
  primary-container: '#27272a'
  on-primary-container: '#8f8e91'
  inverse-primary: '#c8c6c9'
  secondary: '#4b41e1'
  on-secondary: '#ffffff'
  secondary-container: '#645efb'
  on-secondary-container: '#fffbff'
  tertiary: '#111415'
  on-tertiary: '#ffffff'
  tertiary-container: '#262829'
  on-tertiary-container: '#8e8f90'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e4e1e5'
  primary-fixed-dim: '#c8c6c9'
  on-primary-fixed: '#1b1b1e'
  on-primary-fixed-variant: '#47464a'
  secondary-fixed: '#e2dfff'
  secondary-fixed-dim: '#c3c0ff'
  on-secondary-fixed: '#0f0069'
  on-secondary-fixed-variant: '#3323cc'
  tertiary-fixed: '#e2e2e3'
  tertiary-fixed-dim: '#c6c6c7'
  on-tertiary-fixed: '#1a1c1d'
  on-tertiary-fixed-variant: '#454748'
  background: '#fbf8ff'
  on-background: '#1a1b22'
  surface-variant: '#e3e1ec'
typography:
  headline-lg:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Geist
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin: 24px
  panel-width: 320px
  max-content-width: 1200px
---

## Brand & Style
The design system is anchored in the concept of a "digital commonplace book"—a private, high-fidelity workspace for personal knowledge. It rejects the dopamine-driven patterns of social media and the cold sterility of enterprise dashboards in favor of an atmosphere that is **calm, compact, and functional**.

The visual language draws from **Modern Minimalism** with a **Tactile** edge, mimicking the clarity of architectural blueprints and the focus of high-end editorial design. It prioritizes the user's data above all else, using generous whitespace not just for aesthetics, but to provide cognitive breathing room within dense information networks. The emotional response is one of "focused intimacy"—a secure, quiet place where one can think deeply and organize the complexities of life.

## Colors
The palette is built on a "Paper & Ink" foundation. The background utilizes an off-white (`#FAFAFA`) to reduce eye strain and provide a workspace feel that is softer than pure white. 

- **Primary (Charcoal):** Used for structural elements, headers, and primary text to ground the interface.
- **Secondary (Muted Indigo):** Used sparingly for interactive cues and focus states.
- **Semantic Provenance:** 
    - **Trustworthy Green:** Indicates user-verified data.
    - **Soft Amber:** Signals inferred or AI-suggested connections that require review.
    - **Muted Purple:** Reserved strictly for privacy indicators and sensitive "vaulted" content.
    - **Subtle Coral:** Marks contradictions or outdated nodes.

## Typography
This design system employs **Geist** for its technical precision and humanist warmth. The typography is designed for high-density reading. 

The scale is intentionally conservative to maintain a "compact" feel. Labels use slightly tighter tracking and uppercase styling for metadata to differentiate them clearly from the primary narrative text. Body copy uses a generous line-height to ensure that long-form notes remain legible during deep work sessions.

## Layout & Spacing
The layout follows a **Fixed-Fluid Hybrid** model. Navigation and detail panels occupy fixed widths on the periphery to ensure the primary "Memory Graph" or "Note Canvas" remains stable.

- **Grid:** A 12-column grid is used for document views, while the graph view utilizes a layout-agnostic coordinate system.
- **Side Panels:** Detail inspection happens in right-aligned drawers that slide over content or push the main canvas, depending on screen width.
- **Rhythm:** An 8px base unit is used for component spacing, while a 4px "micro-unit" is used for compact elements like badges and metadata clusters.
- **Breakpoints:**
    - **Mobile (<640px):** Single column, full-screen drawers.
    - **Tablet (640px - 1024px):** Permanent left nav, overlay right panels.
    - **Desktop (>1024px):** Multi-pane workflow with side-by-side inspection.

## Elevation & Depth
Depth is conveyed through **Tonal Layers** rather than shadows. This maintains the "flat paper" aesthetic while clarifying hierarchy.

1.  **Level 0 (Canvas):** The base `#FAFAFA` workspace.
2.  **Level 1 (Cards/Nodes):** Pure white (`#FFFFFF`) with a subtle 1px border (`#E4E4E7`).
3.  **Level 2 (Panels/Modals):** A slight tint or a high-precision 1px stroke. 

Shadows, if used, are restricted to "Level 2" elements and are extremely diffuse: `0px 4px 12px rgba(0,0,0,0.03)`. This provides just enough lift to indicate an interactive layer without breaking the calm, flat aesthetic.

## Shapes
Shapes are **Soft (0.25rem)** to strike a balance between professional precision and organic intimacy. 

- **Graph Nodes:** Use a rounded-square base. The "type" of information is encoded through the stroke style (solid for verified, dashed for inferred).
- **Interactive Elements:** Buttons and inputs use a standard `4px` radius.
- **Badges:** Use a slightly more rounded `6px` or "pill" shape to distinguish them from functional UI buttons.

## Components
- **Graph Nodes:** Minimalist squares with a 1px border. The top-right corner features a 4px semantic dot indicating provenance (e.g., amber for uncertain).
- **Metadata Badges:** Extremely compact labels with `label-sm` typography. They use low-saturation background tints from the semantic palette (e.g., a pale purple background with dark purple text for "Private").
- **Chat Bubbles:**
    - **User:** Right-aligned, charcoal background, white text. Sharp corners on the outer edge, rounded on the inner.
    - **Assistant:** Left-aligned, light grey background, primary text. Subtle indigo left-border to indicate "system" provenance.
- **Input Fields:** Minimalist "Underline" or "Ghost" style. They only show a full border on focus to reduce visual noise on a crowded page.
- **Lists:** High-density with 1px dividers. Hover states use a subtle `#F4F4F5` fill.
- **Drawers:** Slide-in panels from the right for "Deep Inspection." They include a header with breadcrumbs to maintain the user's sense of place within the graph.