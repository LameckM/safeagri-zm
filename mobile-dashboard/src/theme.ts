import { Platform } from 'react-native';
import type { StatusTone } from './status';

export const colors = {
  background: '#EFEAD9',
  card: '#F8F5EA',
  border: '#DCD5C0',
  text: '#2A241C',
  muted: '#6B6252',
  green: '#2F5233',
  blue: '#3E7C97',
  amber: '#B8792B',
  red: '#B3402C',
  grey: '#6B6252',
  white: '#FFFFFF',
};

export const toneColor: Record<StatusTone, string> = {
  red: colors.red,
  blue: colors.blue,
  green: colors.green,
  grey: colors.grey,
};

/** Rockwell is a slab serif on iOS. Android has no built in slab, so use its sturdy serif. */
export const headingFont = Platform.select({
  ios: 'Rockwell',
  android: 'serif',
  default: 'serif',
});

export const size = {
  body: 16,
  small: 14,
  heading: 20,
  bigNumber: 56,
  touch: 48,
  gap: 12,
  pad: 16,
};

export const tabular = ['tabular-nums' as const];
