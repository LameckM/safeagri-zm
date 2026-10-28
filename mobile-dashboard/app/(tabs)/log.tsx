import React from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { loadEvents } from '../../src/api';
import { LogRow } from '../../src/components/LogRow';
import { EmptyState, ErrorState, OfflineBanner } from '../../src/components/Notices';
import { parseTime } from '../../src/status';
import { colors, size } from '../../src/theme';
import type { IrrigationEvent, Result } from '../../src/types';
import { useResource } from '../../src/useResource';

/** Newest first, whatever order the server used. */
async function loadSortedEvents(): Promise<Result<IrrigationEvent[]>> {
  const result = await loadEvents();
  const data = [...result.data].sort(
    (a, b) => (parseTime(b.created_at) ?? 0) - (parseTime(a.created_at) ?? 0) || b.id - a.id,
  );
  return { ...result, data };
}

export default function LogScreen() {
  const events = useResource(loadSortedEvents, []);

  if (!events.loaded) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.green} />
      </View>
    );
  }

  return (
    <FlatList
      data={events.data}
      keyExtractor={(e) => String(e.id)}
      contentContainerStyle={styles.content}
      ItemSeparatorComponent={() => <View style={{ height: size.gap }} />}
      initialNumToRender={10}
      refreshControl={<RefreshControl refreshing={events.pulling} onRefresh={events.pull} colors={[colors.green]} />}
      ListHeaderComponent={
        events.stale && !events.error ? (
          <View style={{ marginBottom: size.gap }}>
            <OfflineBanner savedAt={events.savedAt} />
          </View>
        ) : null
      }
      ListEmptyComponent={
        events.error ? (
          <ErrorState message={events.error} onRetry={events.reload} />
        ) : (
          <EmptyState icon="water-outline" title="No irrigation yet" hint="Irrigation events will show up here." />
        )
      }
      renderItem={({ item }) => <LogRow event={item} />}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  content: { padding: size.pad, flexGrow: 1 },
});
