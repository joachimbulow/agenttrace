// Tones for known scalar shapes. Components map these to classes/color.

export function isUnitInterval(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1;
}

/** Red at 0 → green at 1. oklch so it tracks the rest of the palette. */
export function unitIntervalOklch(value: number): string {
  const t = Math.min(1, Math.max(0, value));
  const hue = 25 + t * (152 - 25);
  return `oklch(0.48 0.16 ${hue})`;
}

export function booleanTone(value: boolean): 'true' | 'false' {
  return value ? 'true' : 'false';
}
