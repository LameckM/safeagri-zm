import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import React from 'react';
import type { ColorValue } from 'react-native';
import { useAlerts } from '../../src/AlertsProvider';
import { colors, headingFont } from '../../src/theme';

type IconName = keyof typeof Ionicons.glyphMap;

const icon =
  (name: IconName, outline: IconName) =>
  ({ color, focused }: { color: ColorValue; focused: boolean }) => (
    <Ionicons name={focused ? name : outline} size={26} color={color} />
  );

export default function TabsLayout() {
  const { count } = useAlerts();

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerShadowVisible: false,
        headerTitleStyle: { fontFamily: headingFont, fontWeight: '700', fontSize: 22, color: colors.text },
        headerTitleAlign: 'left',
        tabBarActiveTintColor: colors.green,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.card, borderTopColor: colors.border },
        tabBarLabelStyle: { fontSize: 14, fontWeight: '700' },
        sceneStyle: { backgroundColor: colors.background },
      }}
    >
      <Tabs.Screen name="index" options={{ title: 'Fields', tabBarIcon: icon('leaf', 'leaf-outline') }} />
      <Tabs.Screen
        name="alerts"
        options={{
          title: 'Alerts',
          tabBarIcon: icon('notifications', 'notifications-outline'),
          tabBarBadge: count > 0 ? count : undefined,
          tabBarBadgeStyle: { backgroundColor: colors.red, color: colors.white, fontSize: 13, fontWeight: '700' },
          tabBarAccessibilityLabel: count > 0 ? `Alerts, ${count} active` : 'Alerts',
        }}
      />
      <Tabs.Screen name="log" options={{ title: 'Log', tabBarIcon: icon('water', 'water-outline') }} />
      <Tabs.Screen name="settings" options={{ title: 'Settings', tabBarIcon: icon('settings', 'settings-outline') }} />
    </Tabs>
  );
}
