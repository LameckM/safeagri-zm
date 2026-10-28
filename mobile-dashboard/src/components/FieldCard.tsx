import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { formatValue, timeAgo } from '../format';
import { getFieldStatus } from '../status';
import { colors, headingFont, size, tabular, toneColor } from '../theme';
import type { FieldView } from '../types';
import { StatusBadge } from './StatusBadge';

export function FieldCard({ view, now }: { view: FieldView; now: number }) {
  const { field, reading } = view;
  const status = getFieldStatus(reading, now);
  const moisture = reading?.soil_moisture ?? null;
  const updated = reading
    ? `Updated ${timeAgo(reading.recorded_at ?? reading.received_at, now)}`
    : 'No readings yet';

  return (
    <View
      style={[styles.card, { borderLeftColor: toneColor[status.tone] }]}
      accessible
      accessibilityLabel={`${field.name}. Soil moisture ${formatValue(moisture, ' percent')}. ${status.label}. ${updated}.`}
    >
      <View style={styles.header}>
        <Text style={styles.name}>{field.name}</Text>
        {field.crop ? <Text style={styles.crop}>{field.crop}</Text> : null}
      </View>

      <Text style={[styles.moisture, moisture === null && styles.moistureMissing]}>
        {formatValue(moisture, '%')}
      </Text>
      <Text style={styles.moistureLabel}>Soil moisture</Text>

      <View style={styles.statusRow}>
        <StatusBadge status={status} />
      </View>

      <View style={styles.readings}>
        <View style={styles.reading}>
          <Ionicons name="thermometer-outline" size={22} color={colors.muted} />
          <Text style={styles.readingText}>{formatValue(reading?.temperature, '°C')}</Text>
        </View>
        <View style={styles.reading}>
          <Ionicons name="water-outline" size={22} color={colors.muted} />
          <Text style={styles.readingText}>{formatValue(reading?.humidity, '%')}</Text>
          <Text style={styles.readingHint}>humidity</Text>
        </View>
      </View>

      <Text style={styles.updated}>{updated}</Text>
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
  header: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' },
  name: { fontFamily: headingFont, fontSize: size.heading, fontWeight: '700', color: colors.text },
  crop: { fontSize: size.body, color: colors.muted, textTransform: 'capitalize' },
  moisture: {
    fontSize: size.bigNumber,
    lineHeight: size.bigNumber + 8,
    fontWeight: '800',
    color: colors.text,
    fontVariant: tabular,
    marginTop: 4,
  },
  moistureMissing: { color: colors.muted },
  moistureLabel: { fontSize: size.body, color: colors.muted, marginBottom: 10 },
  statusRow: { flexDirection: 'row', marginBottom: 12 },
  readings: { flexDirection: 'row', flexWrap: 'wrap', columnGap: 24, rowGap: 8 },
  reading: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  readingText: { fontSize: size.body, color: colors.text, fontVariant: tabular, fontWeight: '600' },
  readingHint: { fontSize: size.body, color: colors.muted },
  updated: { fontSize: size.body, color: colors.muted, marginTop: 10 },
});
