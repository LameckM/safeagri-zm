import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { alertMeta, formatDateTime, timeAgo } from '../format';
import { colors, headingFont, size } from '../theme';
import type { AlertItem } from '../types';

type Props = {
  alert: AlertItem;
  now: number;
  onOpen: () => void;
  onDismiss: () => void;
};

export function AlertRow({ alert, now, onOpen, onDismiss }: Props) {
  const meta = alertMeta(alert.kind);
  const tint = meta.tone === 'red' ? colors.red : colors.amber;

  return (
    <View style={[styles.card, { borderLeftColor: tint }]}>
      <Pressable
        onPress={onOpen}
        style={styles.body}
        accessibilityRole="button"
        accessibilityLabel={`${meta.label}. ${alert.message}. ${timeAgo(alert.created_at, now)}.`}
        accessibilityHint="Opens the Fields tab"
      >
        <View style={styles.titleRow}>
          <Ionicons name={meta.icon} size={24} color={tint} />
          <Text style={styles.kind}>{meta.label}</Text>
        </View>
        <Text style={styles.message}>{alert.message}</Text>
        <Text style={styles.time}>
          {timeAgo(alert.created_at, now)}, {formatDateTime(alert.created_at)}
        </Text>
      </Pressable>
      <Pressable
        onPress={onDismiss}
        style={({ pressed }) => [styles.dismiss, pressed && styles.pressed]}
        accessibilityRole="button"
        accessibilityLabel={`Dismiss ${meta.label} alert`}
        accessibilityHint="Hides this alert on this phone only"
      >
        <Text style={styles.dismissText}>Dismiss</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    borderRadius: 8,
    padding: size.pad,
  },
  body: { minHeight: size.touch },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  kind: { fontFamily: headingFont, fontSize: size.heading, fontWeight: '700', color: colors.text },
  message: { fontSize: size.body, color: colors.text, lineHeight: 22 },
  time: { fontSize: size.body, color: colors.muted, marginTop: 6 },
  dismiss: {
    minHeight: size.touch,
    marginTop: 10,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: colors.green,
    borderRadius: 8,
  },
  pressed: { opacity: 0.6 },
  dismissText: { fontSize: size.body, fontWeight: '700', color: colors.green },
});
