# Device Center 2.5D Asset Pack V2

This pack is rebuilt around one canonical workstation.

## Exact layer order

1. `01-background`
2. `02-desk-base`
3. `03-screen-overlay`
4. `04-actor`
5. `05-foreground-mask`
6. `06-light-overlay`
7. `07-fx-overlay`
8. `08-label-ui`

## Geometry consistency

- `desk-light-base.webp` and `desk-dark-base.webp` are color variants of the same source pixels.
- `desk-foreground-mask-light.webp` and `desk-foreground-mask-dark.webp` use the same alpha geometry.
- An empty workstation is always `02 + 05`; no separate mismatched desk is used.
- Nine positions reuse the same workstation asset.
- Screen state overlays are aligned to the same monitor rectangle.

## Preview

- `preview/preview-light-9-slots.webp`
- `preview/preview-dark-9-slots.webp`

These previews are included only to verify alignment and theme consistency.
