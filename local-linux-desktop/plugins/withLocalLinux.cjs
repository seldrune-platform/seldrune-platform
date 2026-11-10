const { withAndroidManifest, withDangerousMod, withMainApplication } = require('@expo/config-plugins');
const fs = require('node:fs');
const path = require('node:path');

// A legacy React Native package is registered in the Expo-generated Android app.
// Fail loudly if Expo changes the generated template instead of producing an APK
// that looks usable but is missing its bridge.
function withLocalLinux(config) {
  config = withAndroidManifest(config, (mod) => {
    const manifest = mod.modResults.manifest;
    manifest['uses-permission'] ||= [];
    if (!manifest['uses-permission'].some((entry) => entry.$?.['android:name'] === 'com.termux.permission.RUN_COMMAND')) {
      manifest['uses-permission'].push({ $: { 'android:name': 'com.termux.permission.RUN_COMMAND' } });
    }
    manifest.queries ||= [{}];
    manifest.queries[0].package ||= [];
    for (const packageName of ['com.termux', 'com.termux.x11']) {
      if (!manifest.queries[0].package.some((entry) => entry.$?.['android:name'] === packageName)) {
        manifest.queries[0].package.push({ $: { 'android:name': packageName } });
      }
    }
    return mod;
  });
  config = withMainApplication(config, (mod) => {
    if (mod.modResults.language !== 'kt') throw new Error('Local Linux bridge requires the Kotlin Expo MainApplication template.');
    let contents = mod.modResults.contents;
    if (!contents.includes('com.seldrune.locallinux.LocalLinuxPackage()')) {
      const marker = /PackageList\(this\)\.packages\.apply\s*\{/;
      if (!marker.test(contents)) throw new Error('Could not locate React Native package list to register LocalLinuxBridge.');
      contents = contents.replace(marker, (match) => `${match}\n              add(com.seldrune.locallinux.LocalLinuxPackage())`);
    }
    mod.modResults.contents = contents;
    return mod;
  });
  return withDangerousMod(config, ['android', async (mod) => {
    const source = path.join(__dirname, 'android', 'com', 'seldrune', 'locallinux');
    const target = path.join(mod.modRequest.platformProjectRoot, 'app', 'src', 'main', 'java', 'com', 'seldrune', 'locallinux');
    fs.mkdirSync(target, { recursive: true });
    for (const filename of ['LocalLinuxBridgeModule.java', 'LocalLinuxPackage.java']) {
      fs.copyFileSync(path.join(source, filename), path.join(target, filename));
    }
    return mod;
  }]);
}

module.exports = withLocalLinux;
