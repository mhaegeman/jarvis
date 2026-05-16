---
name: remotion
description: Use when building, rendering, or compositing programmatic videos using React and the Remotion framework.
---

# Remotion

## Overview

React framework for programmatic video. Use CSS, Canvas, SVG, WebGL + React ecosystem.

Source: [remotion-dev/remotion](https://github.com/remotion-dev/remotion)

## When to Use

- Video compositions w/ React components
- Render MP4/WebM or PNG/JPEG stills programmatically
- Data-driven/templated videos
- Frame-based animation
- **Not for:** real-time streaming, live editing, non-React stacks

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
