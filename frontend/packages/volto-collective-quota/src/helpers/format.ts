// Mirrors plone.base.utils.human_readable_size, so sizes computed in the
// browser (e.g. the space freed by a delete) read like the backend's.
const UNITS: [string, number][] = [
  ['PB', 1024 ** 5],
  ['TB', 1024 ** 4],
  ['GB', 1024 ** 3],
  ['MB', 1024 ** 2],
  ['KB', 1024],
];

// One decimal like Python's f"{x:.1f}": exact ties round to even (2.25 → 2.2),
// where Number.toFixed would round them up.
function oneDecimal(value: number): string {
  const scaled = value * 10;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;
  const tenths = diff === 0.5 ? floor + (floor % 2) : Math.round(scaled);
  return (tenths / 10).toFixed(1);
}

export function human(size: number): string {
  if (!size || size < 0) return '0 KB';
  if (size < 1024) return '1 KB';
  const [unit, factor] = UNITS.find(([, f]) => Math.floor(size / f) > 0)!;
  return `${oneDecimal(size / factor)} ${unit}`;
}
