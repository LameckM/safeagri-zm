import Constants, { ExecutionEnvironment } from 'expo-constants';

/**
 * True inside the Expo Go app. Since SDK 53, Expo Go on Android cannot load
 * expo-notifications (and background tasks are unreliable there), so those features
 * switch off in Expo Go and work in a development build or an APK.
 */
export const IN_EXPO_GO = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;
