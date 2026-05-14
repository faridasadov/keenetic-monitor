# Keenetic Monitor Android APK

Bu qovluq Keenetic Monitor dashboard-u üçün sadə Android WebView wrapper-dir.

## URL seçimi

Default URL emulator üçündür:

```text
http://10.0.2.2:8000
```

Real telefonda server URL-ni build zamanı ver:

```bash
./gradlew assembleDebug -PdashboardUrl=http://SERVER-IP:8000
```

HTTPS domain varsa:

```bash
./gradlew assembleRelease -PdashboardUrl=https://monitor.example.com
```

## Android Studio ilə build

1. Android Studio-da `android-app/` qovluğunu aç.
2. Sync bitəndən sonra `Build > Build APK(s)` seç.
3. APK burada yaranır:

```text
android-app/app/build/outputs/apk/debug/app-debug.apk
```

## CLI ilə build

Bu maşında Java, Gradle və Android SDK quraşdırılmalıdır. Sonra:

```bash
cd android-app
gradle wrapper
./gradlew assembleDebug -PdashboardUrl=http://SERVER-IP:8000
```

Release imzalama üçün env-lər:

```bash
export ANDROID_KEYSTORE=/path/release.keystore
export ANDROID_KEYSTORE_PASSWORD=...
export ANDROID_KEY_ALIAS=keenetic-monitor
export ANDROID_KEY_PASSWORD=...
./gradlew assembleRelease -PdashboardUrl=https://monitor.example.com
```
