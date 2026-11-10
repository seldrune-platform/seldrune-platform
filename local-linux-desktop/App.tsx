import React, { useCallback, useEffect, useState } from 'react';
import { Alert, AppState, Linking, NativeModules, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { SETUP_SCRIPT, START_SCRIPT } from './src/termux-scripts';

type BridgeStatus = { termuxInstalled: boolean; x11Installed: boolean; permissionGranted: boolean };
type LinuxBridge = {
  status(): Promise<BridgeStatus>;
  requestPermission(): Promise<boolean>;
  installScripts(setupScript: string, startScript: string): Promise<void>;
  copyText(text: string): Promise<void>;
  runScript(path: string): Promise<void>;
  openTermux(): Promise<void>;
  openX11(): Promise<void>;
};
type Icon = React.ComponentProps<typeof Ionicons>['name'];

const bridge = NativeModules.LocalLinuxBridge as LinuxBridge | undefined;
const enableCommand = "mkdir -p ~/.termux && printf '\\nallow-external-apps=true\\n' >> ~/.termux/termux.properties && termux-reload-settings";

function Action({ title, icon, onPress, secondary = false, disabled = false }: {
  title: string; icon: Icon; onPress: () => void; secondary?: boolean; disabled?: boolean;
}) {
  return <Pressable accessibilityRole="button" accessibilityLabel={title} disabled={disabled} onPress={onPress}
    style={({ pressed }) => [styles.button, secondary && styles.secondaryButton, disabled && styles.disabled, pressed && styles.pressed]}>
    <Ionicons name={icon} size={19} color={secondary ? '#d8e9ff' : '#06172c'} />
    <Text style={[styles.buttonText, secondary && styles.secondaryButtonText]}>{title}</Text>
  </Pressable>;
}

function Step({ number, title, children }: { number: string; title: string; children: React.ReactNode }) {
  return <View style={styles.step}>
    <View style={styles.stepHeader}><Text style={styles.number}>{number}</Text><Text style={styles.stepTitle}>{title}</Text></View>
    <View style={styles.stepContent}>{children}</View>
  </View>;
}

function AppContent() {
  const [status, setStatus] = useState<BridgeStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    if (Platform.OS !== 'android' || !bridge) { setStatus(null); return; }
    try { setStatus(await bridge.status()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not check the companion apps.'); }
  }, []);
  useEffect(() => {
    void refresh();
    const sub = AppState.addEventListener('change', value => { if (value === 'active') void refresh(); });
    return () => sub.remove();
  }, [refresh]);

  const perform = async (fn: () => Promise<void>, message?: string) => {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await fn(); if (message) { setNotice(message); Alert.alert('Local desktop', message); } await refresh(); }
    catch (cause) { const text = cause instanceof Error ? cause.message : 'The action could not be completed.'; setError(text); Alert.alert('Could not continue', text); }
    finally { setBusy(false); }
  };
  const nativeAction = (fn: (b: LinuxBridge) => Promise<void>, message?: string) => {
    void perform(async () => {
      if (Platform.OS !== 'android' || !bridge) throw new Error('Use the installed Android build. This feature is not available in Expo Go.');
      await fn(bridge);
    }, message);
  };

  return <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
    <StatusBar style="light" />
    <LinearGradient colors={['#091834', '#101d3e', '#201d3c']} style={StyleSheet.absoluteFill} />
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.topline}><View style={styles.brandIcon}><Ionicons name="terminal-outline" size={22} color="#98dcff" /></View>
        <Text style={styles.brand}>LOCAL DESKTOP</Text><View style={styles.localBadge}><View style={styles.dot} /><Text style={styles.localBadgeText}>ON DEVICE</Text></View></View>
      <Text style={styles.eyebrow}>LINUX ON YOUR PHONE</Text>
      <Text style={styles.hero}>A desktop in your pocket.</Text>
      <Text style={styles.intro}>Run a Debian Linux desktop and compatible Linux apps on your phone's CPU. No cloud computer is needed.</Text>

      <View style={styles.info}><Ionicons name="information-circle-outline" size={21} color="#99d8ff" /><Text style={styles.infoText}>First-time setup needs internet, storage space, Termux and Termux:X11. The desktop opens in Termux:X11.</Text></View>
      {Platform.OS !== 'android' || !bridge ? <View style={styles.warning}><Text style={styles.warningText}>Install a built Android APK to use the local Linux connection. Expo Go cannot provide its native bridge.</Text></View> : null}

      <View style={styles.sectionHeading}><Text style={styles.sectionTitle}>Set up your desktop</Text><Pressable onPress={() => void refresh()} accessibilityRole="button" accessibilityLabel="Refresh app status"><Ionicons name="refresh-outline" size={21} color="#9ad9ff" /></Pressable></View>
      <Step number="01" title="Install the companion apps">
        <Text style={styles.body}>Install both apps from their official GitHub releases, then open Termux once to finish its initial setup.</Text>
        <View style={styles.statusRow}><View style={[styles.statusDot, status?.termuxInstalled && styles.statusGood]} /><Text style={styles.statusText}>Termux {status?.termuxInstalled ? 'installed' : 'not detected'}</Text></View>
        <View style={styles.statusRow}><View style={[styles.statusDot, status?.x11Installed && styles.statusGood]} /><Text style={styles.statusText}>Termux:X11 {status?.x11Installed ? 'installed' : 'not detected'}</Text></View>
        <Action title="Get Termux" icon="open-outline" secondary onPress={() => void perform(() => Linking.openURL('https://github.com/termux/termux-app/releases'))} />
        <Action title="Get Termux:X11" icon="open-outline" secondary onPress={() => void perform(() => Linking.openURL('https://github.com/termux/termux-x11/releases'))} />
      </Step>
      <Step number="02" title="Allow the connection">
        <Text style={styles.body}>In Termux, paste and run this command. Long-press the text to copy it.</Text>
        <View style={styles.codeBox}><Text selectable style={styles.code}>{enableCommand}</Text></View>
        <Action title="Copy command" icon="copy-outline" secondary disabled={busy} onPress={() => nativeAction(b => b.copyText(enableCommand), 'Command copied. Open Termux and paste it.')} />
        <Action title="Open Termux" icon="terminal-outline" secondary disabled={busy} onPress={() => nativeAction(b => b.openTermux())} />
        <Text style={styles.body}>Return here, then grant the Termux command permission when Android asks.</Text>
        <Action title={status?.permissionGranted ? 'Permission granted' : 'Grant permission'} icon="shield-checkmark-outline" secondary disabled={busy || !!status?.permissionGranted}
          onPress={() => nativeAction(async b => { if (!await b.requestPermission()) throw new Error('Permission was not granted. Enable the Termux command permission in Android app settings.'); }, 'Permission granted.')} />
      </Step>
      <Step number="03" title="Install Debian and XFCE">
        <Text style={styles.body}>This downloads Linux and desktop packages to your phone. Keep Termux open and wait for its setup to finish. Your existing Termux data is preserved.</Text>
        <Action title={busy ? 'Please wait…' : 'Start Linux setup'} icon="download-outline" disabled={busy} onPress={() => nativeAction(b => b.installScripts(SETUP_SCRIPT, START_SCRIPT), 'Setup was sent to Termux. Open Termux and wait for it to finish before starting the desktop.')} />
      </Step>
      <View style={styles.launchCard}>
        <View style={styles.launchIcon}><Ionicons name="desktop-outline" size={27} color="#a8e5ff" /></View>
        <Text style={styles.launchTitle}>Your local desktop</Text>
        <Text style={styles.body}>After setup finishes, start Linux and then open the desktop. In Termux:X11, Android Back toggles the keyboard.</Text>
        <Action title="Start Linux" icon="play-outline" disabled={busy} onPress={() => nativeAction(b => b.runScript('~/local-linux-desktop/start.sh'), 'Start was sent to Termux. Open the desktop after it begins. Check Termux if it does not appear.')} />
        <Action title="Open desktop" icon="expand-outline" secondary disabled={busy} onPress={() => nativeAction(b => b.openX11())} />
      </View>
      {notice ? <View accessibilityLiveRegion="polite" style={styles.notice}><Text style={styles.noticeText}>{notice}</Text></View> : null}
      {error ? <View accessibilityLiveRegion="assertive" style={styles.error}><Text style={styles.errorText}>{error}</Text></View> : null}
      <Text style={styles.footer}>Linux runs locally using Android's kernel. Compatible ARM Linux apps can be installed inside Debian.</Text>
    </ScrollView>
  </SafeAreaView>;
}

export default function App() { return <SafeAreaProvider><AppContent /></SafeAreaProvider>; }

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#091834' }, content: { paddingHorizontal: 22, paddingTop: 18, paddingBottom: 42, maxWidth: 720, alignSelf: 'center', width: '100%' },
  topline: { flexDirection: 'row', alignItems: 'center', marginBottom: 43, gap: 10 }, brandIcon: { width: 40, height: 40, borderRadius: 13, backgroundColor: '#193454', alignItems: 'center', justifyContent: 'center' }, brand: { color: '#e9f4ff', fontSize: 12, fontWeight: '800', letterSpacing: 2, flex: 1 },
  localBadge: { flexDirection: 'row', alignItems: 'center', gap: 7, borderColor: '#375574', borderWidth: 1, borderRadius: 20, paddingVertical: 7, paddingHorizontal: 10 }, dot: { width: 7, height: 7, borderRadius: 5, backgroundColor: '#89e8b5' }, localBadgeText: { color: '#c0dfec', fontSize: 10, fontWeight: '700', letterSpacing: 0.8 },
  eyebrow: { color: '#8bd7ff', fontSize: 11, fontWeight: '800', letterSpacing: 2.2, marginBottom: 11 }, hero: { color: '#f5f9ff', fontSize: 39, lineHeight: 44, fontWeight: '800', letterSpacing: -1.5, maxWidth: 390 }, intro: { color: '#b3c6df', fontSize: 16, lineHeight: 24, marginTop: 16, maxWidth: 530 },
  info: { marginTop: 25, borderRadius: 16, padding: 15, borderColor: '#2f516d', borderWidth: 1, backgroundColor: '#102e49', flexDirection: 'row', alignItems: 'flex-start', gap: 10 }, infoText: { color: '#c7e0ee', fontSize: 13, lineHeight: 20, flex: 1 }, warning: { marginTop: 14, backgroundColor: '#4c382a', padding: 15, borderRadius: 14 }, warningText: { color: '#ffe1bb', lineHeight: 20 },
  sectionHeading: { marginTop: 36, marginBottom: 14, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, sectionTitle: { color: '#f2f7ff', fontSize: 21, fontWeight: '700' },
  step: { backgroundColor: '#111f39', borderRadius: 19, borderColor: '#293b59', borderWidth: 1, padding: 18, marginBottom: 12 }, stepHeader: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 12 }, number: { color: '#8cd9ff', fontWeight: '800', fontSize: 12, letterSpacing: 1 }, stepTitle: { color: '#f4f7ff', fontSize: 17, fontWeight: '700', flex: 1 }, stepContent: { gap: 10 }, body: { color: '#b9c9df', fontSize: 14, lineHeight: 21 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8 }, statusDot: { width: 8, height: 8, borderRadius: 5, backgroundColor: '#8a94a7' }, statusGood: { backgroundColor: '#85dfb0' }, statusText: { fontSize: 13, color: '#d1deee' },
  codeBox: { backgroundColor: '#091328', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#293f5f' }, code: { color: '#b1e4ff', fontFamily: Platform.OS === 'android' ? 'monospace' : undefined, fontSize: 12, lineHeight: 19 },
  button: { minHeight: 48, borderRadius: 12, backgroundColor: '#9bdcff', flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 8, paddingHorizontal: 14 }, buttonText: { fontSize: 14, fontWeight: '800', color: '#06172c' }, secondaryButton: { backgroundColor: '#1b304d', borderWidth: 1, borderColor: '#375270' }, secondaryButtonText: { color: '#e1efff' }, disabled: { opacity: 0.55 }, pressed: { opacity: 0.75 },
  launchCard: { marginTop: 13, padding: 20, backgroundColor: '#173452', borderWidth: 1, borderColor: '#3e6580', borderRadius: 21, gap: 12 }, launchIcon: { height: 49, width: 49, backgroundColor: '#244b6b', borderRadius: 15, alignItems: 'center', justifyContent: 'center' }, launchTitle: { color: '#f2f8ff', fontSize: 21, fontWeight: '800' },
  notice: { marginTop: 16, padding: 14, backgroundColor: '#173e39', borderRadius: 12 }, noticeText: { color: '#c5f4d9', lineHeight: 20 }, error: { marginTop: 16, padding: 14, backgroundColor: '#492d39', borderRadius: 12 }, errorText: { color: '#ffd0d4', lineHeight: 20 }, footer: { color: '#879db9', fontSize: 12, lineHeight: 19, marginTop: 24, textAlign: 'center' },
});
