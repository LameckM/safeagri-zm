import { Ionicons } from '@expo/vector-icons';
import Constants from 'expo-constants';
import { useFocusEffect } from 'expo-router';
import React, { useCallback, useEffect, useState } from 'react';
import { Linking, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { ApiError, MOCK, OFFLINE_MESSAGE, checkHealth, describeError, normalizeServerUrl } from '../../src/api';
import { useAlerts } from '../../src/AlertsProvider';
import { registerAlertTask, unregisterAlertTask } from '../../src/background';
import { Button } from '../../src/components/Button';
import {
  PermissionState,
  getPermissionState,
  notificationsAvailable,
  requestPermission,
} from '../../src/notifications';
import { getNotificationsEnabled, getServerUrl, setNotificationsEnabled, setServerUrl } from '../../src/storage';
import { colors, headingFont, size } from '../../src/theme';

type Note = { text: string; ok: boolean };

export default function SettingsScreen() {
  const { refresh } = useAlerts();
  const [url, setUrl] = useState('');
  const [savedUrl, setSavedUrl] = useState('');
  const [saveNote, setSaveNote] = useState<Note | null>(null);
  const [testNote, setTestNote] = useState<Note | null>(null);
  const [testing, setTesting] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const [permission, setPermission] = useState<PermissionState>('undetermined');

  useEffect(() => {
    getServerUrl().then((u) => {
      setUrl(u);
      setSavedUrl(u);
    });
    getNotificationsEnabled().then(setEnabled);
  }, []);

  // Check again each time the tab opens, in case the farmer changed it in phone settings.
  useFocusEffect(
    useCallback(() => {
      getPermissionState().then(setPermission);
    }, []),
  );

  const save = async () => {
    const clean = normalizeServerUrl(url);
    if (!clean) {
      setSaveNote({ text: 'Type the server address first, for example http://192.168.1.50:8000', ok: false });
      return;
    }
    await setServerUrl(clean);
    setUrl(clean);
    setSavedUrl(clean);
    setSaveNote({ text: 'Saved on this phone.', ok: true });
    refresh();
  };

  const test = async () => {
    const clean = normalizeServerUrl(url);
    if (!MOCK && !clean) {
      setTestNote({ text: 'Type the server address first, for example http://192.168.1.50:8000', ok: false });
      return;
    }
    setTesting(true);
    setTestNote(null);
    try {
      const answer = await checkHealth(clean);
      if (answer === 'ok') {
        const unsaved = clean !== savedUrl ? ' Tap Save to keep this address.' : '';
        setTestNote({ text: `Connected. The server is working.${unsaved}`, ok: true });
      } else {
        setTestNote({ text: 'The server answered, but not with OK. Check that this is the SafeAgri server.', ok: false });
      }
    } catch (e) {
      const text =
        e instanceof ApiError && (e.kind === 'network' || e.kind === 'timeout')
          ? `${OFFLINE_MESSAGE} Your phone and the server must be on the same network.`
          : describeError(e);
      setTestNote({ text, ok: false });
    } finally {
      setTesting(false);
    }
  };

  const available = notificationsAvailable();

  const toggleNotifications = async (on: boolean) => {
    if (!available) return;
    setEnabled(on);
    await setNotificationsEnabled(on);
    if (on) {
      let state = await getPermissionState();
      if (state === 'undetermined') state = await requestPermission();
      setPermission(state);
      await registerAlertTask();
    } else {
      await unregisterAlertTask();
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.section}>
        <Text style={styles.heading}>Server address</Text>
        <Text style={styles.hint}>The address of the irrigation server, for example http://192.168.1.50:8000</Text>
        {MOCK ? <Text style={styles.hint}>Sample data mode is on. No real server is used.</Text> : null}
        <TextInput
          value={url}
          onChangeText={setUrl}
          style={styles.input}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          placeholder="http://192.168.1.50:8000"
          placeholderTextColor={colors.muted}
          accessibilityLabel="Server address"
        />
        <Button title="Save" onPress={save} />
        {saveNote ? <NoteView note={saveNote} /> : null}
        <Button title="Test connection" variant="secondary" busy={testing} onPress={test} />
        {testNote ? <NoteView note={testNote} /> : null}
      </View>

      <View style={styles.section}>
        <Text style={styles.heading}>Notifications</Text>
        <View style={styles.switchRow}>
          <View style={styles.switchText}>
            <Text style={styles.switchTitle}>Alert notifications</Text>
            <Text style={styles.hint}>Get a notification when a field has a problem.</Text>
          </View>
          <Switch
            value={available && enabled}
            disabled={!available}
            onValueChange={toggleNotifications}
            trackColor={{ false: colors.border, true: colors.green }}
            thumbColor={colors.white}
            accessibilityLabel="Alert notifications"
          />
        </View>
        {!available ? (
          <Text style={styles.hint}>
            Notifications are off because the app is running inside Expo Go. Install the full app (a development build
            or the APK) to get alerts.
          </Text>
        ) : null}
        {available && enabled && permission === 'denied' ? (
          <View style={styles.warning}>
            <Ionicons name="alert-circle" size={24} color={colors.red} />
            <Text style={styles.warningText}>Your phone is blocking notifications for this app.</Text>
          </View>
        ) : null}
        {available && enabled && permission === 'denied' ? (
          <Button title="Open phone settings" variant="secondary" onPress={() => Linking.openSettings()} />
        ) : null}
      </View>

      <View style={styles.section}>
        <Text style={styles.heading}>About</Text>
        <Text style={styles.body}>SafeAgri ZM, version {Constants.expoConfig?.version ?? '1.0.0'}</Text>
      </View>
    </ScrollView>
  );
}

function NoteView({ note }: { note: Note }) {
  const color = note.ok ? colors.green : colors.red;
  return (
    <View style={[styles.note, { borderLeftColor: color }]} accessibilityLiveRegion="polite">
      <Ionicons name={note.ok ? 'checkmark-circle' : 'alert-circle'} size={24} color={color} />
      <Text style={styles.noteText}>{note.text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: size.pad, gap: 20 },
  section: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: size.pad,
    gap: size.gap,
  },
  heading: { fontFamily: headingFont, fontSize: size.heading, fontWeight: '700', color: colors.text },
  hint: { fontSize: size.body, color: colors.muted, lineHeight: 22 },
  body: { fontSize: size.body, color: colors.text },
  input: {
    minHeight: size.touch + 4,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    backgroundColor: colors.white,
    paddingHorizontal: 14,
    fontSize: size.body,
    color: colors.text,
  },
  note: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderLeftWidth: 4,
    backgroundColor: colors.background,
    borderRadius: 8,
    padding: 12,
  },
  noteText: { flex: 1, fontSize: size.body, color: colors.text, lineHeight: 22 },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: size.touch + 8 },
  switchText: { flex: 1, gap: 2 },
  switchTitle: { fontSize: size.body, fontWeight: '700', color: colors.text },
  warning: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  warningText: { flex: 1, fontSize: size.body, color: colors.red, fontWeight: '600', lineHeight: 22 },
});
