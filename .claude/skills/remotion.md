---
name: remotion
description: Use when building, rendering, or compositing programmatic videos using React and the Remotion framework.
---

# Remotion

## Overview

Remotion is a framework for creating videos programmatically using React. Leverage CSS, Canvas, SVG, WebGL, and the full React ecosystem to build video compositions in code.

Source: [remotion-dev/remotion](https://github.com/remotion-dev/remotion)

## When to Use

- Building video compositions with React components
- Rendering MP4/WebM videos or PNG/JPEG stills programmatically
- Creating data-driven or templated videos
- Animating content with frame-based timing
- **Not for:** real-time streaming, live video editing, non-React stacks

## Core Concepts

| Concept | Description |
|---------|-------------|
| `<Composition>` | Defines a named video with dimensions, fps, and duration |
| `useCurrentFrame()` | Returns the current frame number (0-indexed) |
| `useVideoConfig()` | Returns `fps`, `width`, `height`, `durationInFrames` |
| `interpolate()` | Maps frame ranges to value ranges (like animation keyframes) |
| `spring()` | Physics-based animation helper |
| `<Sequence>` | Offsets child components in time |
| `<AbsoluteFill>` | Full-size positioned container |

## Project Setup

```bash
bun create video@latest   # scaffold new project
bun install               # install dependencies
bun run dev               # open Remotion Studio at localhost:3000
```

## Key Commands

```bash
# Development
bunx remotion studio      # Open visual preview

# Rendering
bunx remotion render <composition-id> output.mp4   # Render video
bunx remotion still <composition-id> output.png    # Render single frame
bunx remotion compositions                         # List compositions
```

## Animation Pattern

```tsx
import { useCurrentFrame, interpolate, AbsoluteFill } from 'remotion';

export const MyComp = () => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ opacity }}>
      <h1>Hello world</h1>
    </AbsoluteFill>
  );
};
```

## Common Mistakes

| Problem | Fix |
|---------|-----|
| Animations running at wrong speed | Always derive timing from `useCurrentFrame()` / fps, never real time |
| Video renders differently than preview | Avoid `Date.now()`, `Math.random()`, or side effects — keep compositions deterministic |
| Audio/video sync issues | Use `<OffthreadVideo>` or `<Audio>` with `startFrom` prop |
| Composition not appearing | Ensure it is registered in `src/Root.tsx` via `<Composition>` |
| Build errors after install | Run `bun run build` before testing |
