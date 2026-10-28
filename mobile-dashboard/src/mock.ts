/** Sample data for EXPO_PUBLIC_MOCK=1. Times are relative to now so the UI always looks live. */

const iso = (minutesAgo: number) => new Date(Date.now() - minutesAgo * 60000).toISOString();

const FIELDS = [
  { id: 1, name: 'Field 1', node_id: 'node-01', crop: 'maize' },
  { id: 2, name: 'Field 2', node_id: 'node-02', crop: 'maize' },
  { id: 3, name: 'Field 3', node_id: 'node-03', crop: 'maize' },
  { id: 4, name: 'Field 4', node_id: 'node-04', crop: 'maize' },
];

function latest() {
  const make = (id: number, field_id: number, moisture: number, temp: number, hum: number, ago: number) => ({
    id,
    field_id,
    field_name: `Field ${field_id}`,
    soil_moisture: moisture,
    temperature: temp,
    humidity: hum,
    recorded_at: iso(ago),
    received_at: iso(ago),
    valid: 1,
    flag: null,
  });
  return [
    make(12, 1, 34.2, 28.5, 55.1, 3), // healthy
    make(13, 2, 64.8, 27.9, 61.4, 5), // wet
    make(14, 3, 41.0, 29.3, 52.0, 42), // node offline
    make(15, 4, 12.0, 31.2, 40.3, 2), // needs water
  ];
}

function alerts() {
  return [
    {
      id: 8,
      field_id: 3,
      kind: 'node_offline',
      message: 'Field 3: no readings received for 15 minutes',
      created_at: iso(27),
      resolved: 0,
    },
    {
      id: 7,
      field_id: 2,
      kind: 'sensor_fault',
      message: 'Field 2: soil moisture reading 999.0 is out of range',
      created_at: iso(95),
      resolved: 0,
    },
  ];
}

function events() {
  return [
    { id: 3, field_id: 4, field_name: 'Field 4', action: 'open', source: 'rule', duration_min: 30, created_at: iso(20) },
    { id: 2, field_id: 1, field_name: 'Field 1', action: 'open', source: 'rule', duration_min: 20, created_at: iso(60 * 26) },
    { id: 1, field_id: 4, field_name: 'Field 4', action: 'open', source: 'rule', duration_min: 30, created_at: iso(60 * 50) },
  ];
}

export function mockGet(path: string): unknown {
  switch (path) {
    case '/health':
      return { status: 'ok' };
    case '/fields':
      return FIELDS;
    case '/latest':
      return latest();
    case '/alerts':
      return alerts();
    case '/schedule/events':
      return events();
    default:
      return [];
  }
}

export function mockRun(): unknown {
  return [
    { field_id: 1, field_name: 'Field 1', action: 'skip', reason: 'moisture_within_range', duration_min: null, moisture: 34.2 },
    { field_id: 2, field_name: 'Field 2', action: 'skip', reason: 'soil_already_wet', duration_min: null, moisture: 64.8 },
    { field_id: 3, field_name: 'Field 3', action: 'skip', reason: 'node_offline', duration_min: null, moisture: null },
    { field_id: 4, field_name: 'Field 4', action: 'irrigate', reason: 'soil_below_dry_threshold', duration_min: 30, moisture: 12.0 },
  ];
}
