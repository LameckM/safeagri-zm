import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { describeEvent, formatDateTime, sourceLabel } from '../format';
import { colors, headingFont, size } from '../theme';
import type { IrrigationEvent } from '../types';

export function LogRow({ event }: { event: IrrigationEvent }) {
  const name = event.field_name ?? (event.field_id !== null ? `Field ${event.field_id}` : 'Field');
  const what = describeEvent(event.action, event.duration_min);

  return (
    <View
      style={styles.card}
      accessible
      accessibilityLabel={`${name}. ${what}. ${sourceLabel(event.source)}. ${formatDateTime(event.created_at)}.`}
    >
      <View style={styles.titleRow}>
        <Ionicons name="water" size={22} color={colors.blue} />
        <Text style={styles.name}>{name}</Text>
      </View>
      <Text style={styles.what}>{what}</Text>
      <Text style={styles.meta}>
        {sourceLabel(event.source)}, {formatDateTime(event.created_at)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    borderLeftColor: colors.blue,
    borderRadius: 8,
    padding: size.pad,
    minHeight: size.touch,
  },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  name: { fontFamily: headingFont, fontSize: size.heading, fontWeight: '700', color: colors.text },
  what: { fontSize: size.body, fontWeight: '600', color: colors.text },
  meta: { fontSize: size.body, color: colors.muted, marginTop: 4 },
});
