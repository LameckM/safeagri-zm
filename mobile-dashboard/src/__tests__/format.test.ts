import { alertMeta, describeEvent, formatValue, sourceLabel, summarizeRun, timeAgo } from '../format';

const NOW = Date.parse('2026-10-13T09:30:00.000+00:00');
const minutesAgo = (m: number) => new Date(NOW - m * 60000).toISOString();

describe('timeAgo', () => {
  it('reads naturally', () => {
    expect(timeAgo(minutesAgo(0.2), NOW)).toBe('just now');
    expect(timeAgo(minutesAgo(1), NOW)).toBe('1 minute ago');
    expect(timeAgo(minutesAgo(3), NOW)).toBe('3 minutes ago');
    expect(timeAgo(minutesAgo(60), NOW)).toBe('1 hour ago');
    expect(timeAgo(minutesAgo(180), NOW)).toBe('3 hours ago');
    expect(timeAgo(minutesAgo(60 * 49), NOW)).toBe('2 days ago');
  });

  it('survives missing or future times', () => {
    expect(timeAgo(null, NOW)).toBe('at an unknown time');
    expect(timeAgo(minutesAgo(-10), NOW)).toBe('just now');
  });
});

describe('alertMeta', () => {
  it('labels known kinds', () => {
    expect(alertMeta('sensor_fault').label).toBe('Sensor fault');
    expect(alertMeta('node_offline').label).toBe('Node offline');
  });

  it('gives unknown kinds a generic label', () => {
    expect(alertMeta('something_new').label).toBe('Alert');
  });
});

describe('describeEvent and sourceLabel', () => {
  it('describes an opening', () => {
    expect(describeEvent('open', 30)).toBe('Opened for 30 minutes');
    expect(describeEvent('open', 1)).toBe('Opened for 1 minute');
    expect(describeEvent('open', null)).toBe('Opened');
  });

  it('names the source', () => {
    expect(sourceLabel('rule')).toBe('Automatic rule');
    expect(sourceLabel('manual')).toBe('Manual');
    expect(sourceLabel('some_thing')).toBe('Some thing');
  });
});

describe('formatValue', () => {
  it('shows one decimal, or N/A when missing', () => {
    expect(formatValue(34.2, '%')).toBe('34.2%');
    expect(formatValue(null, '%')).toBe('N/A');
    expect(formatValue(undefined, '%')).toBe('N/A');
    expect(formatValue(NaN, '%')).toBe('N/A');
  });
});

describe('summarizeRun', () => {
  const base = { moisture: null, duration_min: null };
  it('reports irrigation', () => {
    const text = summarizeRun([
      { ...base, field_id: 4, field_name: 'Field 4', action: 'irrigate', reason: 'soil_below_dry_threshold', duration_min: 30 },
      { ...base, field_id: 1, field_name: 'Field 1', action: 'skip', reason: 'moisture_within_range' },
    ]);
    expect(text).toBe('Irrigating: Field 4 for 30 minutes.');
  });

  it('reports when nothing is needed and flags offline nodes', () => {
    const text = summarizeRun([
      { ...base, field_id: 1, field_name: 'Field 1', action: 'skip', reason: 'soil_already_wet' },
      { ...base, field_id: 3, field_name: 'Field 3', action: 'skip', reason: 'node_offline' },
    ]);
    expect(text).toBe('No irrigation needed right now. Node offline: Field 3.');
  });

  it('handles an empty answer', () => {
    expect(summarizeRun([])).toContain('no fields');
  });
});
