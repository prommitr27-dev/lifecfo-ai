// Display helpers only. All money figures are computed by the server.

export function thb(satang: number, decimals = 0): string {
  const value = satang / 100;
  return (
    value.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }) + ' ฿'
  );
}

export function compactThb(satang: number): string {
  const value = satang / 100;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(0)}k`;
  return value.toFixed(0);
}

export function titleCase(code: string): string {
  return code
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}
