# SafeAgri ZM

Phone companion for the smart irrigation system in Kafubu Block, Luanshya. It reads the existing FastAPI backend and warns the farmer when something is wrong. Built with Expo SDK 57, TypeScript and Expo Router. Light theme only.

The app uses only the endpoints that already exist: `/health`, `/fields`, `/latest`, `/alerts`, `/schedule/events` and `POST /schedule/run`. Nothing was added to the backend.

## 1. Run it with Expo Go on your phone

You need Node 20 or newer on the laptop and the Expo Go app on an Android phone.

**Important:** since SDK 53, Expo Go on Android cannot load notifications. In Expo Go the app opens and every screen works (fields, alerts list, log, settings, offline cache), but notifications and background alerts are switched off, and Settings says so. To get real alerts on the phone, build the app as described in section 3.

```bash
npm install
npx expo start
```

Scan the QR code with Expo Go. The phone and the laptop must be on the same Wi-Fi.

No server yet? Use sample data. Every screen works and nothing touches the network:

```bash
EXPO_PUBLIC_MOCK=1 npx expo start
```

(On Windows PowerShell: `$env:EXPO_PUBLIC_MOCK=1; npx expo start`)

## 2. Point the app at your server

The server must listen on the network, not only on localhost. Start the backend with host `0.0.0.0`, for example `uvicorn main:app --host 0.0.0.0 --port 8000`.

Find the laptop's local IP address:

- Windows: run `ipconfig` and read "IPv4 Address".
- macOS: run `ipconfig getifaddr en0`.
- Linux: run `hostname -I`.

In the app open **Settings**, type the address with the port, for example `http://192.168.1.50:8000`, tap **Save**, then tap **Test connection**. You should see "Connected. The server is working."

If the test fails, check that the phone is on the same Wi-Fi, and that the laptop firewall allows port 8000. A phone on mobile data cannot reach a laptop's local address.

To change the default address that new installs start with, set `EXPO_PUBLIC_API_URL` before starting.

## 3. Get notifications working: build a development app

Notifications need a real build of the app, not Expo Go. The easiest way on Windows, with no Android Studio, is an EAS cloud build. You need a free Expo account.

```bash
npm install -g eas-cli
eas login
eas build:configure
eas build --profile development --platform android
```

When the build finishes, EAS gives you a link and a QR code. Open it on the phone, download the APK and install it (allow installs from your browser if asked). This is your own copy of the app, with notifications included. Then start the dev server and open the installed app instead of Expo Go:

```bash
npx expo start --dev-client
```

For a copy that does not need the dev server at all (the one a farmer would use), build the preview profile instead: `eas build --profile preview --platform android`.

If you have Android Studio set up, `npx expo run:android` also works and builds on your own machine.

## 3b. Test a notification

Do this in the development app or the APK, not in Expo Go.

1. Open the app and wait a few seconds. The first successful check only records the alerts that already exist, so nothing is announced for old alerts.
2. Send a bad reading from the laptop:

```bash
curl -X POST http://192.168.1.50:8000/readings \
  -H "Content-Type: application/json" \
  -d '{"node_id":"node-01","soil_moisture":999,"temperature":28,"humidity":55}'
```

3. Within 30 seconds the app polls `/alerts` and shows a notification such as "Sensor fault, Field 1". The Alerts tab shows a badge with the count.

If nothing appears, open `/alerts` in a browser and confirm there is a new alert with a higher id than before. Only alerts with a higher id than the highest one already seen are announced. Also check that notifications are allowed for the app in the phone settings.

## 4. How alerts work

- **Foreground:** while the app is open it calls `GET /alerts` every 30 seconds. Every alert with an id higher than the highest one seen gets a local notification right away. Polling stops while the app is in the background.
- **Background:** a task registered with `expo-background-fetch` and `expo-task-manager` runs the same check (`checkAlerts` in `src/notifications.ts`).
- **Android channel:** a channel with id `alerts` and high importance is created on startup.
- **Expo Go:** notifications and the background task are turned off there, and the app tells you so in Settings.
- **Permission:** asked once on first launch, with a one line explanation. If it is denied the app keeps working, and Settings shows how to open the phone settings. Turning the Settings switch on asks again if the phone still allows it.
- **Dismiss:** hides an alert on this phone only, because the backend has no resolve endpoint. Dismissed ids are stored locally and cleared automatically once the alert is no longer active.

### Limits of background alerts

Background alerts are best effort. Do not rely on them for anything urgent.

- The operating system decides when the background task runs. On Android it is usually 15 minutes or more, and it can be much longer.
- Battery saver, Doze and the aggressive app killers on many low cost phones can stop the task completely. Allowing the app to run in the background and turning off battery optimisation for it helps, but does not guarantee anything.
- iOS is stricter. It runs background tasks rarely, based on how often the app is used, and not at all if the app was force closed.
- Background alerts do not run in Expo Go at all. Test them in a development build or the preview APK.
- The 30 second polling only happens while the app is open. If the app is closed, the next alert may wait for the next background run.
- `expo-background-fetch` is marked deprecated in SDK 57 in favour of `expo-background-task`. It still works and is what this project was asked to use. Moving to the newer package later is a small change in `src/background.ts`.

The fix for real time alerts is remote push, which needs a small backend addition. The place where it would plug in is marked in `src/notifications.ts` under "REMOTE PUSH PLUG-IN POINT". It is not built.

## 5. Weak internet

- Every request times out after 8 seconds.
- The last good response of each endpoint is saved on the phone. When the network fails the saved data is shown with a banner such as "Offline, showing data from 10:42".
- If there is nothing saved and the server cannot be reached, the app shows "Cannot reach the server. Check the address in Settings." Empty lists and missing fields never crash the app.
- Saved data belongs to one server address. Changing the address in Settings does not show data from the old server.

## 6. Status rules

Same as the web dashboard, in `src/status.ts`:

| Situation | Label | Color |
| --- | --- | --- |
| No reading at all | No data yet | grey |
| Newest reading older than 15 minutes | Node offline | red |
| Moisture 25 or below | Needs water | red |
| Moisture 60 or above | Wet | blue |
| Anything else | Healthy | green |

Every status also has a text label and an icon, so color is never the only signal.

## 7. Tests and checks

```bash
npm test          # unit tests for src/status.ts and the text helpers
npm run typecheck # TypeScript
```

## 8. Notes on builds

`eas.json` has two profiles: `development` (dev client APK) and `preview` (plain APK). The backend is plain HTTP on a local address. `app.json` allows this through `expo-build-properties` (Android cleartext traffic) and an iOS transport security setting. Expo Go does not need it. If you ship the app publicly later, put the backend behind HTTPS and tighten both settings.

No app icon or splash image is included. Add them to `app.json` before building for a store.

## Code layout

```
app/                  Expo Router screens (tabs: Fields, Alerts, Log, Settings)
src/api.ts            typed fetch, 8 second timeout, cache fallback
src/types.ts          response types
src/status.ts         status rules as pure functions
src/format.ts         time and text helpers
src/notifications.ts  channel, permission, new alert check, remote push plug-in point
src/background.ts     background task
src/storage.ts        everything saved on the phone
src/theme.ts          colors, fonts, sizes
src/mock.ts           sample data for EXPO_PUBLIC_MOCK=1
src/AlertsProvider.tsx  30 second poll shared by the Alerts tab and the badge
src/components/       FieldCard, AlertRow, LogRow, StatusBadge, Button, Notices
```
