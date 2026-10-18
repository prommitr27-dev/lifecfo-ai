import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { Tabs } from 'expo-router/js-tabs';
import { Pressable } from 'react-native';

import { useTheme } from '../../lib/theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

const TABS: { name: string; title: string; icon: IconName }[] = [
  { name: 'index', title: 'Cash flow', icon: 'trending-up' },
  { name: 'plan', title: 'Personal CFO', icon: 'git-compare' },
  { name: 'chat', title: 'AI CFO', icon: 'chatbubbles' },
  { name: 'rewards', title: 'Rewards', icon: 'trophy' },
  { name: 'sandbox', title: 'Sandbox', icon: 'shield-checkmark' },
];

export default function TabsLayout() {
  const t = useTheme();
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: t.card },
        headerTintColor: t.text,
        tabBarStyle: { backgroundColor: t.card, borderTopColor: t.border },
        tabBarActiveTintColor: t.accent,
        tabBarInactiveTintColor: t.muted,
        sceneStyle: { backgroundColor: t.bg },
        headerRight: () => (
          <Pressable
            accessibilityLabel="Server settings"
            onPress={() => router.push('/settings')}
            style={{ paddingHorizontal: 16 }}
            hitSlop={8}
          >
            <Ionicons name="settings-outline" size={22} color={t.text} />
          </Pressable>
        ),
      }}
    >
      {TABS.map((tab) => (
        <Tabs.Screen
          key={tab.name}
          name={tab.name}
          options={{
            title: tab.title,
            tabBarIcon: ({ color, size }) => <Ionicons name={tab.icon} color={typeof color === "string" ? color : t.muted} size={size} />,
          }}
        />
      ))}
    </Tabs>
  );
}
