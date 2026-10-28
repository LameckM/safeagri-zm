import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';
import { colors, size } from '../theme';

type Props = {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary';
  busy?: boolean;
};

export function Button({ title, onPress, variant = 'primary', busy = false }: Props) {
  const primary = variant === 'primary';
  return (
    <Pressable
      onPress={onPress}
      disabled={busy}
      accessibilityRole="button"
      accessibilityState={{ busy, disabled: busy }}
      style={({ pressed }) => [
        styles.button,
        primary ? styles.primary : styles.secondary,
        (pressed || busy) && styles.dim,
      ]}
    >
      {busy ? <ActivityIndicator color={primary ? colors.white : colors.green} /> : null}
      <Text style={[styles.text, { color: primary ? colors.white : colors.green }]}>{title}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: size.touch + 4,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    borderRadius: 8,
    paddingHorizontal: 20,
  },
  primary: { backgroundColor: colors.green },
  secondary: { borderWidth: 2, borderColor: colors.green, backgroundColor: 'transparent' },
  dim: { opacity: 0.6 },
  text: { fontSize: size.body, fontWeight: '700' },
});
