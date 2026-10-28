import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { formatClock } from '../format';
import { colors, size } from '../theme';

/** "Offline, showing data from 10:42". */
export function OfflineBanner({ savedAt }: { savedAt: number | null }) {
  const text = savedAt ? `Offline, showing data from ${formatClock(savedAt)}` : 'Offline, showing saved data';
  return (
    <View style={styles.banner} accessibilityRole="alert" accessible accessibilityLabel={text}>
      <Ionicons name="cloud-offline" size={24} color={colors.white} />
      <Text style={styles.bannerText}>{text}</Text>
    </View>
  );
}

/** Friendly error with a big retry button. Shown only when there is nothing saved to display. */
export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={styles.error}>
      <Ionicons name="cloud-offline-outline" size={40} color={colors.muted} />
      <Text style={styles.errorText}>{message}</Text>
      <Pressable onPress={onRetry} style={styles.retry} accessibilityRole="button">
        <Text style={styles.retryText}>Try again</Text>
      </Pressable>
    </View>
  );
}

export function EmptyState({ icon, title, hint }: { icon: keyof typeof Ionicons.glyphMap; title: string; hint?: string }) {
  return (
    <View style={styles.error}>
      <Ionicons name={icon} size={40} color={colors.green} />
      <Text style={styles.emptyTitle}>{title}</Text>
      {hint ? <Text style={styles.errorText}>{hint}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: colors.amber,
    borderRadius: 8,
    paddingHorizontal: size.pad,
    paddingVertical: 12,
    minHeight: size.touch,
  },
  bannerText: { flex: 1, color: colors.white, fontSize: size.body, fontWeight: '700' },
  error: { alignItems: 'center', gap: 12, paddingVertical: 48, paddingHorizontal: 24 },
  errorText: { fontSize: size.body, color: colors.muted, textAlign: 'center', lineHeight: 22 },
  emptyTitle: { fontSize: size.heading, fontWeight: '700', color: colors.text, textAlign: 'center' },
  retry: {
    minHeight: size.touch,
    minWidth: 160,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.green,
    borderRadius: 8,
    paddingHorizontal: 20,
  },
  retryText: { color: colors.white, fontSize: size.body, fontWeight: '700' },
});
