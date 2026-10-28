import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { describeError, loadFieldViews, runIrrigationCheck } from '../../src/api';
import { Button } from '../../src/components/Button';
import { FieldCard } from '../../src/components/FieldCard';
import { EmptyState, ErrorState, OfflineBanner } from '../../src/components/Notices';
import { summarizeRun } from '../../src/format';
import { colors, size } from '../../src/theme';
import { useNow } from '../../src/useNow';
import { useResource } from '../../src/useResource';

type Message = { text: string; ok: boolean };

export default function FieldsScreen() {
  const now = useNow();
  const fields = useResource(loadFieldViews, []);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState<Message | null>(null);

  const checkIrrigation = async () => {
    setRunning(true);
    setMessage(null);
    try {
      const results = await runIrrigationCheck();
      await fields.reload();
      setMessage({ text: summarizeRun(results), ok: true });
    } catch (e) {
      setMessage({ text: `Could not check irrigation. ${describeError(e)}`, ok: false });
    } finally {
      setRunning(false);
    }
  };

  if (!fields.loaded) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.green} />
      </View>
    );
  }

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={fields.pulling} onRefresh={fields.pull} colors={[colors.green]} />
      }
    >
      {fields.error ? (
        <ErrorState message={fields.error} onRetry={fields.reload} />
      ) : (
        <>
          {fields.stale ? <OfflineBanner savedAt={fields.savedAt} /> : null}

          <Button
            title={running ? 'Checking irrigation' : 'Check irrigation now'}
            variant="secondary"
            busy={running}
            onPress={checkIrrigation}
          />

          {message ? (
            <View
              style={[styles.message, { borderLeftColor: message.ok ? colors.green : colors.red }]}
              accessibilityLiveRegion="polite"
            >
              <Ionicons
                name={message.ok ? 'checkmark-circle' : 'alert-circle'}
                size={24}
                color={message.ok ? colors.green : colors.red}
              />
              <Text style={styles.messageText}>{message.text}</Text>
            </View>
          ) : null}

          {fields.data.length === 0 ? (
            <EmptyState icon="leaf-outline" title="No fields yet" hint="Pull down to refresh." />
          ) : (
            fields.data.map((view) => <FieldCard key={view.field.id} view={view} now={now} />)
          )}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  content: { padding: size.pad, gap: size.gap, flexGrow: 1 },
  message: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    borderRadius: 8,
    padding: size.pad,
  },
  messageText: { flex: 1, fontSize: size.body, color: colors.text, lineHeight: 22 },
});
