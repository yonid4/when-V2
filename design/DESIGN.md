# Design System Document: The Warm Editorial

## 1. Overview & Creative North Star
This design system is built to transform the functional stress of scheduling into the emotional anticipation of gathering. Moving away from the rigid, cold grids of corporate productivity tools, we embrace a philosophy of **"Tactile Hospitality."**

**Creative North Star: The Digital Concierge**
The UI should feel like a high-end, heavy-stock paper invitation resting on a wooden table. We achieve this through "Organic Asymmetry"—placing key actions slightly off-center or using varying border radii to break the "app-template" feel. We prioritize breathing room over information density, ensuring every interaction feels intentional and unhurried.

---

2. Colors & Surface Philosophy
Our palette is rooted in earth tones, anchored by a signature Terracotta (`primary: #9b4428`). It is designed to feel "sun-drenched" rather than backlit.

### The "No-Line" Rule
**Strict Mandate:** Traditional 1px solid borders (`border-gray-200`) are prohibited for sectioning. 
Boundaries must be defined through:
*   **Background Shifts:** Place a `surface-container-low` card against a `surface` background.
*   **Tonal Transitions:** Use a soft gradient transition between `surface` and `surface-container-highest` to indicate a change in context.

### Surface Hierarchy & Nesting
Treat the UI as physical layers of fine stationery. 
*   **Base Layer:** `surface` (#fdf8f5) – The "table" everything sits on.
*   **Mid Layer:** `surface-container-low` (#f7f3f0) – Large content areas or sidebar backgrounds.
*   **Top Layer:** `surface-container-lowest` (#ffffff) – High-priority cards or active input areas. This creates a "lifted" effect without artificial shadows.

### The "Glass & Gradient" Rule
To add soul to the "When." experience, use semi-transparent `surface-container-lowest` (80% opacity) with a `backdrop-blur-md` for floating navigation bars. Main CTAs should utilize a subtle linear gradient from `primary` (#9b4428) to `primary-container` (#e67e5d) at a 135-degree angle to provide depth.

---

## 3. Typography: Editorial Warmth
We utilize two typefaces to balance character with extreme readability.

*   **Display & Headlines:** *Plus Jakarta Sans*. This is our "voice." Use `headline-lg` (2rem) with a slightly tighter tracking (-0.02em) for a modern, confident look.
*   **Body & Utility:** *Be Vietnam Pro*. Selected for its humanist terminals. Apply generous letter spacing (`tracking-wide`) to all body text to ensure the UI feels "airy."

**Hierarchy Tip:** Avoid using pure black for text. Use `on-surface-variant` (#55423d) for secondary text to maintain the warm, organic tonality of the system.

---

## 4. Elevation & Depth
In this system, depth is a feeling, not a feature.

*   **Tonal Layering:** Instead of shadows, nest a `surface-container-high` element inside a `surface-container-low` parent. This "recessed" look is perfect for group chat areas or secondary event details.
*   **Ambient Shadows:** If an element must float (e.g., a "Create Event" FAB), use a custom shadow: `shadow-[0_20px_40px_-15px_rgba(155,68,40,0.08)]`. Note the tint—we use a fraction of the primary color rather than gray to simulate natural light.
*   **The "Ghost Border":** For essential accessibility in form fields, use `outline-variant` (#dcc1b9) at 20% opacity. It should feel like a faint pencil mark, not a structural beam.

---

## 5. Components
Our components are built on the `shadcn/ui` logic but heavily customized for high-end hospitality.

### Buttons & Chips
*   **Primary Action:** High-radius (`rounded-xl`), using the Primary-to-Container gradient. 
*   **Secondary Action:** No background, `text-primary`, with a `surface-container-highest` hover state.
*   **Status Chips:** 
    *   *Planning:* `bg-surface-container-high` / `text-on-surface-variant`
    *   *Confirmed:* `bg-secondary-container` (#c8e7d9) / `text-on-secondary-container` (#4c685d)
    *   *Cancelled:* `bg-error-container` (#ffdad6) / `text-on-error-container` (#93000a)

### Input Fields
Inputs should never look like "boxes." Use a `surface-container-lowest` fill with a high `rounded-md` (1.5rem) corner. On focus, transition the background to `primary-fixed` (#ffdbd0) at 30% opacity—never just a blue ring.

### Cards & Lists
**Rule:** Zero dividers. Separate event list items using `spacing-4` (1.4rem) and subtle background shifts. An active event card should use `surface-container-lowest` with a "Ghost Border," while inactive events remain flat against the `surface`.

### Unique Component: The "Availability Heatmap"
Instead of a standard grid, use rounded-sm cells. Low availability uses `primary-fixed`, while high availability uses `primary`. The cells should have a `gap-0.5` (0.175rem) to look like a woven textile.

---

## 6. Do’s and Don’ts

### Do
*   **Do** use asymmetrical margins. A layout that is slightly "off-grid" feels more human and less like a database.
*   **Do** use `rounded-xl` (3rem) for large image containers (like restaurant photos) to soften the UI.
*   **Do** lean into the "Warm Amber" and "Terracotta" tones for icons; avoid neutral gray iconography.

### Don't
*   **Don't** use `border-t` or `border-b` to separate list items. Use whitespace or tonal blocks.
*   **Don't** use pure white (`#ffffff`) for backgrounds unless it is a "raised" card sitting on a tinted surface.
*   **Don't** use standard "blue" for links. All interactive elements must derive from the `primary` or `tertiary` palettes.
*   **Don't** use sharp corners. Even "small" rounded corners should be at least `0.5rem`.

---

## 7. Motion & Interaction
Interactions should mimic physical momentum.
*   **Hover States:** When hovering over an event card, do not just change the color. Use a `translate-y-[-4px]` transform with a `duration-500` ease-out to make it feel like the card is being "picked up."
*   **Micro-copy:** Use "human" language. Instead of "Submit," use "Let's go." Instead of "Error," use "Something's not quite right."