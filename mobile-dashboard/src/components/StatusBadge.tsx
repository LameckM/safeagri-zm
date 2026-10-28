import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { StatusInfo } from '../status';
import { colors, size, toneColor } from '../theme';

/** Icon plus text on a solid color, so the status never depends on color alone. */
export function StatusBadge({ status }: { status: StatusInfo }) {
  return (
    <View
      style={[styles.badge, { backgroundColor: toneColor[status.tone] }]}
      accessible
      accessibilityLabel={`Status: ${status.label}`}
    >
      <Ionicons name={status.icon} size={22} color={colors.white} />
      <Text style={styles.label}>{status.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    minHeight: 36,
  },
  label: { color: colors.white, fontSize: size.body, fontWeight: '700' },
});
