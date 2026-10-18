import { useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';

import { WhatIf } from '../../components/WhatIf';
import { MarkdownText } from '../../components/ui';
import type { ChatReply } from '../../lib/api';
import { useConnection } from '../../lib/connection';
import { useTheme } from '../../lib/theme';

type Entry = { id: number; role: 'user' | 'assistant'; text: string; reply?: ChatReply; error?: boolean };

const SUGGESTIONS = [
  'How am I doing this month?',
  'What if my income drops 30%?',
  'Compare the three plans',
  'Can I afford a 20,000 baht trip?',
];

export default function ChatScreen() {
  const t = useTheme();
  const { client, incomeChange, changed } = useConnection();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);
  const list = useRef<FlatList<Entry>>(null);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    const history = entries.filter((e) => !e.error).map((e) => ({ role: e.role, text: e.text }));
    setEntries((all) => [...all, { id: nextId.current++, role: 'user', text: message }]);
    setInput('');
    setBusy(true);
    try {
      const reply = await client.chat(message, history, incomeChange);
      setEntries((all) => [...all, { id: nextId.current++, role: 'assistant', text: reply.text, reply }]);
      // The agent may have proposed a plan; let other screens reload.
      if (reply.tools.some((tool) => tool.tier === 'PROPOSE' || tool.tier === 'EXECUTE')) changed();
    } catch (e) {
      setEntries((all) => [
        ...all,
        { id: nextId.current++, role: 'assistant', text: (e as Error).message, error: true },
      ]);
    } finally {
      setBusy(false);
      setTimeout(() => list.current?.scrollToEnd({ animated: true }), 50);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: t.bg }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      <FlatList
        ref={list}
        data={entries}
        keyExtractor={(e) => String(e.id)}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        ListHeaderComponent={
          <View style={{ gap: 10, marginBottom: 6 }}>
            <WhatIf />
            {entries.length === 0 ? (
              <View style={{ gap: 8 }}>
                <Text style={{ color: t.muted }}>
                  Ask about your plan, goals, bills, or a what-if. Numbers come from the engines,
                  not the AI.
                </Text>
                {SUGGESTIONS.map((s) => (
                  <Pressable
                    key={s}
                    onPress={() => send(s)}
                    style={{ borderWidth: 1, borderColor: t.border, borderRadius: 12, padding: 10, backgroundColor: t.card }}
                  >
                    <Text style={{ color: t.text }}>{s}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
          </View>
        }
        renderItem={({ item }) =>
          item.role === 'user' ? (
            <View style={{ alignSelf: 'flex-end', maxWidth: '85%', backgroundColor: t.accent, borderRadius: 14, padding: 10 }}>
              <Text style={{ color: t.accentText, fontSize: 15 }}>{item.text}</Text>
            </View>
          ) : (
            <View
              style={{
                alignSelf: 'flex-start',
                maxWidth: '92%',
                backgroundColor: item.error ? t.badBg : t.card,
                borderColor: t.border,
                borderWidth: 1,
                borderRadius: 14,
                padding: 10,
                gap: 6,
              }}
            >
              {item.reply?.notice ? <Text style={{ color: t.muted, fontSize: 12 }}>{item.reply.notice}</Text> : null}
              <MarkdownText text={item.text} />
              {item.reply ? (
                <Text style={{ color: t.muted, fontSize: 11 }}>
                  {item.reply.mode === 'offline' ? 'Offline engine' : `${item.reply.provider} / ${item.reply.model}`}
                  {item.reply.tools.length ? ` · tools: ${item.reply.tools.map((x) => x.name).join(', ')}` : ''}
                </Text>
              ) : null}
            </View>
          )
        }
        ListFooterComponent={busy ? <ActivityIndicator style={{ marginTop: 8 }} /> : undefined}
      />
      <View
        style={{
          flexDirection: 'row',
          gap: 8,
          padding: 10,
          borderTopWidth: 1,
          borderTopColor: t.border,
          backgroundColor: t.card,
        }}
      >
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Message your AI CFO"
          placeholderTextColor={t.muted}
          onSubmitEditing={() => send(input)}
          returnKeyType="send"
          maxLength={2000}
          style={{
            flex: 1,
            minHeight: 44,
            color: t.text,
            borderWidth: 1,
            borderColor: t.border,
            borderRadius: 22,
            paddingHorizontal: 14,
          }}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Send"
          onPress={() => send(input)}
          disabled={busy || !input.trim()}
          style={{
            minWidth: 64,
            borderRadius: 22,
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: t.accent,
            opacity: busy || !input.trim() ? 0.5 : 1,
          }}
        >
          <Text style={{ color: t.accentText, fontWeight: '700' }}>Send</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}
