import { type ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type ViewStyle,
} from 'react-native';
import Svg, { Line, Polyline, Text as SvgText } from 'react-native-svg';

import { compactThb } from '../lib/format';
import { type Theme, useTheme } from '../lib/theme';

export function Screen({
  children,
  refreshing = false,
  onRefresh,
}: {
  children: ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const t = useTheme();
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: t.bg }}
      contentContainerStyle={styles.screen}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} /> : undefined
      }
    >
      {children}
    </ScrollView>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  const t = useTheme();
  return (
    <View style={[styles.card, { backgroundColor: t.card, borderColor: t.border }, style]}>
      {children}
    </View>
  );
}

export function H2({ children }: { children: ReactNode }) {
  const t = useTheme();
  return <Text style={[styles.h2, { color: t.text }]}>{children}</Text>;
}

export function Body({ children, muted }: { children: ReactNode; muted?: boolean }) {
  const t = useTheme();
  return <Text style={[styles.body, { color: muted ? t.muted : t.text }]}>{children}</Text>;
}

export type Tone = 'good' | 'warn' | 'bad' | 'info';

function toneColors(t: Theme, tone: Tone) {
  return {
    good: { fg: t.good, bg: t.goodBg },
    warn: { fg: t.warn, bg: t.warnBg },
    bad: { fg: t.bad, bg: t.badBg },
    info: { fg: t.info, bg: t.infoBg },
  }[tone];
}

export function Banner({ tone, title, children }: { tone: Tone; title?: string; children?: ReactNode }) {
  const t = useTheme();
  const c = toneColors(t, tone);
  return (
    <View style={[styles.banner, { backgroundColor: c.bg, borderLeftColor: c.fg }]}>
      {title ? <Text style={[styles.bannerTitle, { color: c.fg }]}>{title}</Text> : null}
      {children ? <Text style={[styles.body, { color: t.text }]}>{children}</Text> : null}
    </View>
  );
}

export function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  const t = useTheme();
  return (
    <View style={[styles.metric, { backgroundColor: t.card, borderColor: t.border }]}>
      <Text style={[styles.metricLabel, { color: t.muted }]}>{label}</Text>
      <Text style={[styles.metricValue, { color: t.text }]} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </Text>
      {hint ? <Text style={[styles.metricHint, { color: t.muted }]}>{hint}</Text> : null}
    </View>
  );
}

export function Row({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.row, style]}>{children}</View>;
}

export function Button({
  label,
  onPress,
  kind = 'primary',
  disabled,
  busy,
}: {
  label: string;
  onPress: () => void;
  kind?: 'primary' | 'secondary' | 'danger';
  disabled?: boolean;
  busy?: boolean;
}) {
  const t = useTheme();
  const bg = kind === 'primary' ? t.accent : 'transparent';
  const fg = kind === 'primary' ? t.accentText : kind === 'danger' ? t.bad : t.text;
  const border = kind === 'primary' ? t.accent : kind === 'danger' ? t.bad : t.border;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={disabled || busy}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: bg, borderColor: border, opacity: disabled ? 0.45 : pressed ? 0.75 : 1 },
      ]}
    >
      {busy ? (
        <ActivityIndicator color={fg} />
      ) : (
        <Text style={[styles.buttonText, { color: fg }]}>{label}</Text>
      )}
    </Pressable>
  );
}

export function Chips<T extends string | number>({
  options,
  value,
  onChange,
  format = String,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
  format?: (v: T) => string;
}) {
  const t = useTheme();
  return (
    <View style={styles.chips}>
      {options.map((o) => {
        const active = o === value;
        return (
          <Pressable
            key={String(o)}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            onPress={() => onChange(o)}
            style={[
              styles.chip,
              { borderColor: active ? t.accent : t.border, backgroundColor: active ? t.accent : t.card },
            ]}
          >
            <Text style={{ color: active ? t.accentText : t.text, fontWeight: '600' }}>{format(o)}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Progress({ value }: { value: number }) {
  const t = useTheme();
  const pct = Math.max(0, Math.min(1, value));
  return (
    <View style={[styles.track, { backgroundColor: t.border }]}>
      <View style={{ width: `${pct * 100}%`, height: '100%', backgroundColor: t.accent, borderRadius: 4 }} />
    </View>
  );
}

export function Loading() {
  return (
    <View style={{ padding: 32 }}>
      <ActivityIndicator />
    </View>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Banner tone="bad" title="Could not load">
      {message}
      {'\n'}
      <Text onPress={onRetry} style={{ fontWeight: '700', textDecorationLine: 'underline' }}>
        Try again
      </Text>
    </Banner>
  );
}

/** Renders the small Markdown subset the engine writes: **bold**, "- " bullets, paragraphs. */
export function MarkdownText({ text }: { text: string }) {
  const t = useTheme();
  const lines = text.split('\n');
  return (
    <View style={{ gap: 6 }}>
      {lines.map((line, i) => {
        if (!line.trim()) return null;
        const bullet = /^\s*[-*]\s+/.test(line);
        const content = line.replace(/^\s*[-*]\s+/, '').replace(/^#+\s*/, '');
        const parts = content.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
        return (
          <View key={i} style={{ flexDirection: 'row', gap: 6 }}>
            {bullet ? <Text style={[styles.body, { color: t.muted }]}>•</Text> : null}
            <Text style={[styles.body, { color: t.text, flex: 1 }]}>
              {parts.map((p, j) =>
                p.startsWith('**') ? (
                  <Text key={j} style={{ fontWeight: '700' }}>
                    {p.slice(2, -2)}
                  </Text>
                ) : (
                  p.replace(/`/g, '')
                ),
              )}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

/** Two-series line chart of daily balances (satang). */
export function BalanceChart({
  series,
  width,
  height = 180,
}: {
  series: { label: string; values: number[]; color: string }[];
  width: number;
  height?: number;
}) {
  const t = useTheme();
  const pad = { left: 40, right: 8, top: 8, bottom: 18 };
  const all = series.flatMap((s) => s.values);
  if (!all.length || width <= 0) return null;
  const min = Math.min(0, ...all);
  const max = Math.max(...all, 1);
  const n = Math.max(...series.map((s) => s.values.length));
  const x = (i: number) => pad.left + (i / Math.max(1, n - 1)) * (width - pad.left - pad.right);
  const y = (v: number) => pad.top + (1 - (v - min) / (max - min)) * (height - pad.top - pad.bottom);
  return (
    <View>
      <Svg width={width} height={height} accessibilityLabel="Projected daily balances">
        {[min, (min + max) / 2, max].map((v, i) => (
          <SvgText key={i} x={pad.left - 4} y={y(v) + 4} fontSize={10} fill={t.muted} textAnchor="end">
            {compactThb(v)}
          </SvgText>
        ))}
        {min < 0 ? (
          <Line x1={pad.left} x2={width - pad.right} y1={y(0)} y2={y(0)} stroke={t.bad} strokeDasharray="4 4" />
        ) : null}
        {series.map((s) => (
          <Polyline
            key={s.label}
            points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(' ')}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
          />
        ))}
      </Svg>
      <View style={styles.legend}>
        {series.map((s) => (
          <View key={s.label} style={styles.legendItem}>
            <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: s.color }} />
            <Text style={{ color: t.muted, fontSize: 12 }}>{s.label}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { padding: 16, gap: 12, paddingBottom: 40 },
  card: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 14, padding: 14, gap: 8 },
  h2: { fontSize: 17, fontWeight: '700', marginTop: 4 },
  body: { fontSize: 15, lineHeight: 21 },
  banner: { borderLeftWidth: 4, borderRadius: 10, padding: 12, gap: 4 },
  bannerTitle: { fontWeight: '700', fontSize: 14 },
  metric: {
    flex: 1,
    minWidth: 100,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 12,
    padding: 10,
    gap: 2,
  },
  metricLabel: { fontSize: 12 },
  metricValue: { fontSize: 18, fontWeight: '700' },
  metricHint: { fontSize: 11 },
  row: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  button: {
    minHeight: 44,
    paddingHorizontal: 16,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: { fontSize: 15, fontWeight: '700' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 8 },
  track: { height: 8, borderRadius: 4, overflow: 'hidden' },
  legend: { flexDirection: 'row', gap: 16, justifyContent: 'center' },
  legendItem: { flexDirection: 'row', gap: 6, alignItems: 'center' },
});
