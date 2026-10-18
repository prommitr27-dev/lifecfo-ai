import { useColorScheme } from 'react-native';

const light = {
  bg: '#F6F7F9',
  card: '#FFFFFF',
  text: '#111827',
  muted: '#6B7280',
  border: '#E5E7EB',
  accent: '#0F766E',
  accentText: '#FFFFFF',
  good: '#047857',
  goodBg: '#ECFDF5',
  warn: '#B45309',
  warnBg: '#FFFBEB',
  bad: '#B91C1C',
  badBg: '#FEF2F2',
  info: '#1D4ED8',
  infoBg: '#EFF6FF',
  chartA: '#0F766E',
  chartB: '#94A3B8',
};

const dark: typeof light = {
  bg: '#0B0F14',
  card: '#151B23',
  text: '#F3F4F6',
  muted: '#9CA3AF',
  border: '#263040',
  accent: '#2DD4BF',
  accentText: '#04201D',
  good: '#34D399',
  goodBg: '#06261C',
  warn: '#FBBF24',
  warnBg: '#2A1F05',
  bad: '#F87171',
  badBg: '#2A0E0E',
  info: '#93C5FD',
  infoBg: '#0B1B33',
  chartA: '#2DD4BF',
  chartB: '#64748B',
};

export type Theme = typeof light;

export function useTheme(): Theme {
  return useColorScheme() === 'dark' ? dark : light;
}
