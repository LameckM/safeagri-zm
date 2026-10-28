import {
  DRY_AT_OR_BELOW,
  OFFLINE_AFTER_MS,
  WET_AT_OR_ABOVE,
  classifyMoisture,
  getFieldStatus,
  parseTime,
} from '../status';

const NOW = Date.parse('2026-10-13T09:30:00.000+00:00');
const minutesAgo = (m: number) => new Date(NOW - m * 60000).toISOString();

const reading = (soil_moisture: number | null, recorded_at: string | null = minutesAgo(1)) => ({
  soil_moisture,
  recorded_at,
  received_at: recorded_at,
});

describe('classifyMoisture', () => {
  it('uses the thresholds from the dashboard', () => {
    expect(DRY_AT_OR_BELOW).toBe(25);
    expect(WET_AT_OR_ABOVE).toBe(60);
  });

  it('marks moisture at or below 25 as Needs water (red)', () => {
    for (const m of [0, 12, 24.9, 25]) {
      const s = classifyMoisture(m);
      expect(s.label).toBe('Needs water');
      expect(s.tone).toBe('red');
    }
  });

  it('marks moisture at or above 60 as Wet (blue)', () => {
    for (const m of [60, 60.1, 85, 100]) {
      const s = classifyMoisture(m);
      expect(s.label).toBe('Wet');
      expect(s.tone).toBe('blue');
    }
  });

  it('marks anything in between as Healthy (green)', () => {
    for (const m of [25.1, 34.2, 42, 59.9]) {
      const s = classifyMoisture(m);
      expect(s.label).toBe('Healthy');
      expect(s.tone).toBe('green');
    }
  });
});

describe('getFieldStatus', () => {
  it('says No data yet (grey) when there is no reading at all', () => {
    for (const r of [null, undefined]) {
      const s = getFieldStatus(r, NOW);
      expect(s.label).toBe('No data yet');
      expect(s.tone).toBe('grey');
    }
  });

  it('says No data yet when the reading has no moisture value', () => {
    expect(getFieldStatus(reading(null), NOW).key).toBe('no_data');
  });

  it('classifies a fresh reading by moisture', () => {
    expect(getFieldStatus(reading(10), NOW).key).toBe('needs_water');
    expect(getFieldStatus(reading(40), NOW).key).toBe('healthy');
    expect(getFieldStatus(reading(75), NOW).key).toBe('wet');
  });

  it('keeps a reading of exactly 15 minutes old as live', () => {
    expect(OFFLINE_AFTER_MS).toBe(15 * 60 * 1000);
    expect(getFieldStatus(reading(40, minutesAgo(15)), NOW).key).toBe('healthy');
  });

  it('says Node offline (red) when the newest reading is older than 15 minutes', () => {
    const s = getFieldStatus(reading(40, minutesAgo(15.1)), NOW);
    expect(s.label).toBe('Node offline');
    expect(s.tone).toBe('red');
  });

  it('prefers Node offline over the moisture status', () => {
    expect(getFieldStatus(reading(5, minutesAgo(60)), NOW).key).toBe('offline');
    expect(getFieldStatus(reading(90, minutesAgo(60)), NOW).key).toBe('offline');
  });

  it('falls back to received_at when recorded_at is missing', () => {
    const r = { soil_moisture: 40, recorded_at: null, received_at: minutesAgo(2) };
    expect(getFieldStatus(r, NOW).key).toBe('healthy');
  });

  it('treats a reading with no usable time as Node offline', () => {
    const r = { soil_moisture: 40, recorded_at: null, received_at: null };
    expect(getFieldStatus(r, NOW).key).toBe('offline');
    expect(getFieldStatus(reading(40, 'not a date'), NOW).key).toBe('offline');
  });

  it('does not call a reading from the future offline (phone clock behind the node)', () => {
    expect(getFieldStatus(reading(40, minutesAgo(-5)), NOW).key).toBe('healthy');
  });

  it('never relies on color alone: every status has a label and an icon', () => {
    const readings = [null, reading(null), reading(10), reading(40), reading(80), reading(40, minutesAgo(99))];
    for (const r of readings) {
      const s = getFieldStatus(r, NOW);
      expect(s.label.length).toBeGreaterThan(0);
      expect(s.icon.length).toBeGreaterThan(0);
    }
  });
});

describe('parseTime', () => {
  it('parses the backend timestamp format', () => {
    expect(parseTime('2026-10-13T09:15:00.000+00:00')).toBe(Date.parse('2026-10-13T09:15:00Z'));
  });

  it('returns null for missing or invalid values', () => {
    expect(parseTime(null)).toBeNull();
    expect(parseTime(undefined)).toBeNull();
    expect(parseTime('')).toBeNull();
    expect(parseTime('garbage')).toBeNull();
  });
});
