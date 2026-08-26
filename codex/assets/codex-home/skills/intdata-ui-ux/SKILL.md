---
name: intdata-ui-ux
description: "intData UI/UX design intelligence and reference-first component reuse. Search maintained design, accessibility, stack and component catalogs; inspect live Beautiful UI, beUI, Rare UI, Transitions.dev and shadcn/ui sources; adapt the strongest bounded result."
---

# intData UI/UX — Component Reference Catalog

Use this skill to find strong existing UI components, inspect their live examples, retrieve their source code, and adapt or copy that code into a frontend.

The skill is a reference browser and implementation aid. It does not impose a visual doctrine, a mandatory workflow, or a checklist. The project brief and selected references determine the result.

## Primary references

| Source | URL | Best material | How to use it |
|---|---|---|---|
| Beautiful UI | https://beautifului.dev | AI-native interfaces: thinking states, streaming text, approval cards, tool chips, task rows, context cards, data tables, flowcharts and agent UI | Open the component anchor, inspect the rendered behavior and retrieve the available component code or page source for adaptation. |
| beUI | https://beui.dev | Animated React/Next.js components, Motion primitives, blocks and agent components | Browse Motion, Blocks or Agents; copy the source or use the shown shadcn CLI command, then edit the installed component in the project. |
| Rare UI | https://rareui.com | Distinctive animated React components built with Tailwind, Motion and the shadcn registry | Open a component page and copy its source or install its registry item with the shown shadcn CLI command. |
| Transitions.dev | https://transitions.dev | Focused UI transitions and interaction choreography | Open a transition detail page, copy the implementation, and transplant the relevant state and motion code into the target component. |
| shadcn/ui | https://ui.shadcn.com | Foundational components, blocks, charts, registries and composable application primitives | Browse Components, Blocks, Charts or Directory; copy the code or add the registry item with the shadcn CLI, then modify the local source directly. |

The same catalog is searchable through the bundled CLI:

```bash
python3 skills/intdata-ui-ux/scripts/search.py "agent approval animated table" --domain reference -n 5
```

## Reference-first workflow

1. Read the product brief and inspect the existing frontend stack and component conventions.
2. Search all relevant sources instead of generating a component from a generic description.
3. Shortlist components by actual behavior and composition.
4. Retrieve the full implementation through the source page, repository, registry command, or copy control exposed by the reference.
5. Copy or adapt the selected code into the existing component tree.
6. Replace tokens, imports, data bindings and state wiring so the component fits the project.
7. Compare the rendered result with the selected reference and continue editing until the intended behavior and visual character are present.

## Search utility

The bundled search command returns matching component sources and their code-retrieval paths:

```bash
python3 skills/intdata-ui-ux/scripts/search.py "animated React agent interface" --domain reference -n 5
```

Its output is a shortlist for opening, copying and editing.

## Maintained design intelligence

The bundled data tables remain part of this skill. Use them when the task needs
design-system reasoning, accessibility guidance, product patterns, typography,
color, charts, landing structure or stack-specific implementation advice.

Generate a cross-domain design-system recommendation:

```bash
python3 skills/intdata-ui-ux/scripts/search.py "healthcare SaaS dashboard" --design-system -p "Project Name"
```

Search a focused domain when one decision needs more evidence:

```bash
python3 skills/intdata-ui-ux/scripts/search.py "keyboard focus reduced motion" --domain ux -n 5
python3 skills/intdata-ui-ux/scripts/search.py "responsive data table" --domain web -n 5
python3 skills/intdata-ui-ux/scripts/search.py "editorial dashboard" --domain typography -n 5
```

Use stack guidance for the project's actual framework:

```bash
python3 skills/intdata-ui-ux/scripts/search.py "form validation loading states" --stack react -n 5
```

Supported domains are `reference`, `style`, `prompt`, `color`, `chart`,
`landing`, `product`, `ux`, `typography`, `icons`, `react` and `web`. Supported
stacks are `html-tailwind`, `react`, `nextjs`, `vue`, `nuxtjs`, `nuxt-ui`,
`svelte`, `swiftui`, `react-native`, `flutter`, `shadcn` and
`jetpack-compose`.

## Integration constraints

- Preserve keyboard access, visible focus, semantic labels and sufficient contrast.
- Respect reduced-motion preferences and avoid layout-shifting hover effects.
- Keep responsive behavior and the target framework's component conventions.
- Reuse installed dependencies when they fit; add a dependency only when the
  selected reference materially requires it.
- Treat copied code as project-owned code: review imports, licenses, data flow,
  error states and security boundaries before integration.

## Expected output from the agent

For a UI task, return or implement:

- the selected reference URLs and component names;
- the retrieved or installed component source;
- the project-specific edits made to that source;
- the working integrated component or page.
