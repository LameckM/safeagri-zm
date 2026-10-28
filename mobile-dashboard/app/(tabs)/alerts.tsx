import { useRouter } from 'expo-router';
import React, { useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { useAlerts } from '../../src/AlertsProvider';
import { AlertRow } from '../../src/components/AlertRow';
import { EmptyState, ErrorState, OfflineBanner } from '../../src/components/Notices';
import { colors, size } from '../../src/theme';
import { useNow } from '../../src/useNow';

export default function AlertsScreen() {
  const router = useRouter();
  const now = useNow();
  const { alerts, stale, savedAt, error, loaded, refresh, dismiss } = useAlerts();
  const [pulling, setPulling] = useState(false);

  const pull = async () => {
    setPulling(true);
    await refresh();
    setPulling(false);
  };

  if (!loaded) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.green} />
      </View>
    );
  }

  return (
    <FlatList
      data={alerts}
      keyExtractor={(a) => String(a.id)}
      contentContainerStyle={styles.content}
      ItemSeparatorComponent={() => <View style={{ height: size.gap }} />}
      refreshControl={<RefreshControl refreshing={pulling} onRefresh={pull} colors={[colors.green]} />}
      ListHeaderComponent={
        stale ? (
          <View style={{ marginBottom: size.gap }}>
            <OfflineBanner savedAt={savedAt} />
          </View>
        ) : null
      }
      ListEmptyComponent={
        error ? (
          <ErrorState message={error} onRetry={pull} />
        ) : (
          <EmptyState icon="checkmark-circle-outline" title="No active alerts" hint="Everything looks fine right now." />
        )
      }
      renderItem={({ item }) => (
        <AlertRow
          alert={item}
          now={now}
          onOpen={() => router.navigate('/')}
          onDismiss={() => dismiss(item.id)}
        />
      )}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  content: { padding: size.pad, flexGrow: 1 },
});
