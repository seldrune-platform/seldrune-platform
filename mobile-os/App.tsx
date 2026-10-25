import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator, Alert, Animated, AppState, BackHandler, KeyboardAvoidingView, PanResponder,
  Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View, useWindowDimensions,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { BlurTargetView, BlurView } from 'expo-blur';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import {
  ApiError, canNavigate, OPEN_REMOTE_KEYBOARD_SCRIPT, request, shouldEndSession, streamMatchesSession,
  STREAM_CHROME_SCRIPT, validateApiUrl, validateStreamUrl,
  type AvailablePod, type LoginResult, type PodStatus, type Session,
} from './src/api';

type Phase = 'locked' | 'booting' | 'desktop';
type WindowId = 'workstation' | 'performance' | 'about';
type FrameState = { id: WindowId; title: string; maximized: boolean; minimized: boolean };
type IconName = React.ComponentProps<typeof Ionicons>['name'];
const apps: { id: WindowId; title: string; icon: IconName; color: string }[] = [
  { id: 'workstation', title: 'GPU Workstation', icon: 'desktop-outline', color: '#6ed7ff' },
  { id: 'performance', title: 'Performance', icon: 'pulse-outline', color: '#a8ffca' },
  { id: 'about', title: 'System', icon: 'settings-outline', color: '#dfc1ff' },
];
const percent = (value: number | null | undefined) => value == null ? '—' : `${Math.round(value)}%`;

function IconButton({ icon, label, onPress, danger = false }: {
  icon: IconName; label: string; onPress: () => void; danger?: boolean;
}) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress}
    style={({ pressed }) => [styles.iconButton, pressed && styles.pressed, danger && styles.dangerButton]}>
    <Ionicons name={icon} size={19} color="#edf6ff" />
  </Pressable>;
}

function AppFrame({ frame, focused, immersive = false, onFocus, onMinimize, onMaximize, onClose, children }: {
  frame: FrameState; focused: boolean; onFocus: () => void; onMinimize: () => void;
  onMaximize: () => void; onClose: () => void; immersive?: boolean; children: React.ReactNode;
}) {
  const { width, height } = useWindowDimensions();
  const position = useRef(new Animated.ValueXY()).current;
  const offset = useRef({ x: 0, y: 0 });
  const drag = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponder: (_event, gesture) => !frame.maximized &&
      (Math.abs(gesture.dx) > 5 || Math.abs(gesture.dy) > 5),
    onPanResponderGrant: () => { onFocus(); },
    onPanResponderMove: (_event, gesture) => {
      position.setValue({ x: Math.max(-width * 0.15, Math.min(width * 0.15, offset.current.x + gesture.dx)),
        y: Math.max(0, Math.min(height * 0.35, offset.current.y + gesture.dy)) });
    },
    onPanResponderRelease: (_event, gesture) => {
      offset.current = { x: Math.max(-width * 0.15, Math.min(width * 0.15, offset.current.x + gesture.dx)),
        y: Math.max(0, Math.min(height * 0.35, offset.current.y + gesture.dy)) };
    },
  }), [frame.maximized, width, height, onFocus, position]);
  useEffect(() => {
    offset.current = { x: 0, y: 0 };
    position.setValue({ x: 0, y: 0 });
  }, [frame.maximized, width, height, position]);
  return <Animated.View onTouchStart={onFocus} pointerEvents={frame.minimized ? 'none' : 'auto'}
    style={[styles.frame, immersive ? styles.immersiveFrame : frame.maximized ? styles.maximized : styles.floating,
      { zIndex: focused ? 10 : 5, opacity: frame.minimized ? 0 : 1,
        transform: frame.maximized ? [] : position.getTranslateTransform() }]}>
    {!immersive && <View style={styles.titlebar}>
      <View style={styles.dragHandle} {...drag.panHandlers}>
        <Ionicons name="logo-windows" size={15} color="#79ccff" />
        <Text numberOfLines={1} style={styles.windowTitle}>{frame.title}</Text>
      </View>
      <IconButton icon="remove-outline" label={`Minimize ${frame.title}`} onPress={onMinimize} />
      <IconButton icon={frame.maximized ? 'copy-outline' : 'square-outline'}
        label={`Resize ${frame.title}`} onPress={onMaximize} />
      <IconButton icon="close-outline" label={`Close ${frame.title}`} onPress={onClose} danger />
    </View>}
    <View style={styles.frameContent}>{children}</View>
  </Animated.View>;
}

function Shell() {
  const [phase, setPhase] = useState<Phase>('locked');
  const [session, setSession] = useState<Session | null>(null);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [status, setStatus] = useState<PodStatus | null>(null);
  const [startOpen, setStartOpen] = useState(false);
  const [frames, setFrames] = useState<FrameState[]>([]);
  const [active, setActive] = useState<WindowId>('workstation');
  const [immersive, setImmersive] = useState(Platform.OS !== 'web');
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false);
  const [clock, setClock] = useState(new Date());
  const [streamError, setStreamError] = useState('');
  const [streamLoaded, setStreamLoaded] = useState(false);
  const [streamAuthPrompt, setStreamAuthPrompt] = useState(false);
  const [streamUsername, setStreamUsername] = useState('kasm_user');
  const [streamPassword, setStreamPassword] = useState('');
  const [streamAuthAttempted, setStreamAuthAttempted] = useState(false);
  const [streamReloadVersion, setStreamReloadVersion] = useState(0);
  const [keyboardPending, setKeyboardPending] = useState(false);
  const [availablePods, setAvailablePods] = useState<AvailablePod[]>([]);
  const [selectedPodId, setSelectedPodId] = useState('');
  const [chromeHidden, setChromeHidden] = useState(true);
  const webview = useRef<WebView<object>>(null);
  const wallpaper = useRef<React.ComponentRef<typeof View>>(null);
  const progress = useRef(new Animated.Value(0.08)).current;
  const bootPulse = useRef(new Animated.Value(0.35)).current;
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const workstationImmersive = Platform.OS !== 'web' && phase === 'desktop' &&
    active === 'workstation' && immersive;
  const apiConfig = useMemo(() => {
    try { return { url: validateApiUrl(process.env.EXPO_PUBLIC_API_URL), error: '' }; }
    catch (cause) { return { url: '', error: (cause as Error).message }; }
  }, []);

  const lock = useCallback((message = '') => {
    setSession(null); setPhase('locked'); setFrames([]); setStatus(null);
    setStartOpen(false); setPassword(''); setNotice(message); setStreamLoaded(false);
    setStreamAuthPrompt(false); setStreamPassword(''); setStreamAuthAttempted(false);
    setKeyboardPending(false);
    setAvailablePods([]); setSelectedPodId('');
  }, []);
  useEffect(() => {
    if (workstationImmersive) return;
    const timer = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(timer);
  }, [workstationImmersive]);
  useEffect(() => {
    if (phase !== 'booting') return;
    const animation = Animated.loop(Animated.sequence([
      Animated.timing(bootPulse, { toValue: 1, duration: 900, useNativeDriver: true }),
      Animated.timing(bootPulse, { toValue: 0.35, duration: 900, useNativeDriver: true }),
    ]));
    animation.start();
    return () => animation.stop();
  }, [phase, bootPulse]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let heartbeatTimer: ReturnType<typeof setTimeout> | undefined;
    let foreground = AppState.currentState === 'active';
    let generation = 0;
    const controllers = new Set<AbortController>();
    const bootStarted = Date.now();
    const call = async <T,>(path: string, body?: unknown) => {
      const controller = new AbortController();
      controllers.add(controller);
      try { return await request<T>(apiConfig.url, path, session.token, body, controller.signal); }
      finally { controllers.delete(controller); }
    };
    const handleFailure = (cause: unknown, run: number) => {
      if (cancelled || !foreground || run !== generation) return;
      if (cause instanceof ApiError && cause.status === 401) lock('Session ended. Sign in to wake your GPU.');
      else setNotice((cause as Error).message);
    };
    const poll = async (run = generation) => {
      if (cancelled || !foreground) return;
      try {
        const next = await call<PodStatus>('/api/status');
        if (cancelled || !foreground || run !== generation) return;
        if (!streamMatchesSession(next, session)) {
          lock('Workstation configuration changed. Sign in again.'); return;
        }
        setStatus(next);
        if (shouldEndSession(next.desiredStatus,
          phaseRef.current === 'desktop' ? 'desktop' : 'booting', Date.now() - bootStarted)) {
          lock('Workstation is stopped. Sign in to resume.'); return;
        }
        const ready = next.streamReady || (next.isRunning && next.streamHealth === 'authentication_required');
        Animated.timing(progress, { toValue: ready ? 1 : next.isRunning ? 0.78 : 0.35,
          duration: 600, useNativeDriver: true }).start();
        if (ready && phaseRef.current === 'booting') {
          setFrames([{ id: 'workstation', title: 'GPU Workstation', maximized: true, minimized: false }]);
          setPhase('desktop');
          setNotice(next.streamHealth === 'authentication_required'
            ? 'Sign in to the desktop stream using its separate credentials.' : '');
        } else if (phaseRef.current === 'booting' && Date.now() - bootStarted > 180_000) {
          setNotice('Startup is taking longer than usual. Still checking; you can shut down below.');
        } else { setNotice(''); }
      } catch (cause) { handleFailure(cause, run); }
      if (!cancelled && foreground && run === generation) {
        pollTimer = setTimeout(() => { void poll(run); }, phaseRef.current === 'booting' ? 3000 : 30_000);
      }
    };
    const heartbeat = async (run = generation) => {
      if (cancelled || !foreground) return;
      try { await call('/api/heartbeat', {}); }
      catch (cause) { handleFailure(cause, run); }
      if (!cancelled && foreground && run === generation) {
        heartbeatTimer = setTimeout(() => { void heartbeat(run); }, 30_000);
      }
    };
    void poll(); void heartbeat();
    const subscription = AppState.addEventListener('change', state => {
      generation++;
      foreground = state === 'active';
      clearTimeout(pollTimer); clearTimeout(heartbeatTimer);
      for (const controller of controllers) controller.abort();
      if (foreground) { void poll(); void heartbeat(); }
    });
    return () => {
      cancelled = true; subscription.remove(); clearTimeout(pollTimer); clearTimeout(heartbeatTimer);
      for (const controller of controllers) controller.abort();
    };
  }, [session, apiConfig.url, lock, progress]);

  async function login(podChoice?: string) {
    if (busy || apiConfig.error) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const chosenPodId = podChoice || (availablePods.length ? selectedPodId : '');
      const next = await request<LoginResult>(apiConfig.url, '/api/login', undefined,
        { username, password, ...(chosenPodId ? { podId: chosenPodId } : {}) });
      if ('requiresPodSelection' in next) {
        setAvailablePods(next.pods);
        setSelectedPodId(previous => next.pods.some(pod => pod.id === previous)
          ? previous : next.pods[0]?.id || '');
        setNotice('Choose the RunPod workstation you want to open.');
        return;
      }
      validateStreamUrl(next.streamUrl, next.podId, next.streamPort);
      setAvailablePods([]); setSelectedPodId('');
      setPassword(''); setStatus(null); setStreamError(''); setStreamLoaded(false);
      setStreamAuthPrompt(false); setStreamPassword(''); setStreamAuthAttempted(false);
      progress.setValue(0.08); setSession(next); setPhase('booting');
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  async function shutdown() {
    if (!session || busy) return;
    setBusy(true);
    try {
      await request(apiConfig.url, '/api/shutdown', session.token, {});
      lock('Stop acknowledged. Storage charges may continue.');
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) lock('Session already ended.');
      else setNotice('Shutdown could not be confirmed. The Pod may still be running; retry to confirm.');
    } finally { setBusy(false); }
  }
  function confirmShutdown() {
    Alert.alert('Shut down workstation?', 'Unsaved remote work may be lost. Persistent storage may still be billed.', [
      { text: 'Cancel', style: 'cancel' }, { text: 'Shut down', style: 'destructive', onPress: () => { void shutdown(); } },
    ]);
  }
  function openApp(id: WindowId) {
    setFrames(previous => previous.some(frame => frame.id === id)
      ? previous.map(frame => frame.id === id ? { ...frame, minimized: false } : frame)
      : [...previous, { id, title: apps.find(app => app.id === id)!.title, maximized: id === 'workstation', minimized: false }]);
    setActive(id); setStartOpen(false);
  }
  function patchFrame(id: WindowId, patch: Partial<FrameState>) {
    setFrames(previous => previous.map(frame => frame.id === id ? { ...frame, ...patch } : frame));
  }
  function toggleTaskbarApp(id: WindowId) {
    const frame = frames.find(item => item.id === id);
    if (frame && active === id && !frame.minimized) {
      patchFrame(id, { minimized: true });
      return;
    }
    openApp(id);
  }
  function lockWorkstation() {
    setStartOpen(false);
    lock('Workstation locked. Sign in again to reconnect.');
  }

  function openRemoteKeyboard() {
    if (!webview.current) return;
    if (chromeHidden) {
      setKeyboardPending(true);
      setChromeHidden(false);
      setStreamLoaded(false);
      setStreamReloadVersion(version => version + 1);
      return;
    }
    webview.current.injectJavaScript(OPEN_REMOTE_KEYBOARD_SCRIPT);
  }

  function toggleRemoteToolbar() {
    setChromeHidden(value => !value);
    setMobileToolsOpen(false);
    setStreamLoaded(false);
    setStreamReloadVersion(version => version + 1);
  }

  useEffect(() => {
    if (phase !== 'desktop') return;
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      if (startOpen) {
        setStartOpen(false);
        return true;
      }
      if (workstationImmersive) {
        setImmersive(false);
        return true;
      }
      const focused = frames.find(frame => frame.id === active && !frame.minimized);
      if (focused) {
        patchFrame(active, { minimized: true });
        return true;
      }
      return false;
    });
    return () => subscription.remove();
  }, [phase, startOpen, frames, active, workstationImmersive]);

  return <View style={styles.root}>
    {!workstationImmersive && <BlurTargetView ref={wallpaper} style={StyleSheet.absoluteFill}>
      <LinearGradient colors={['#091a38', '#142760', '#41265e']} style={styles.root}>
        <View pointerEvents="none" style={styles.orbOne} /><View pointerEvents="none" style={styles.orbTwo} />
      </LinearGradient>
    </BlurTargetView>}
    <StatusBar style="light" hidden={workstationImmersive} />
    <SafeAreaView edges={workstationImmersive ? ['bottom'] : undefined} style={styles.safe}>
      {phase === 'locked' ? <KeyboardAvoidingView style={styles.lockLayout}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.lockScroll} keyboardShouldPersistTaps="handled">
          <Text style={styles.eyebrow}>CLOUD GPU OS</Text>
          <Text style={styles.clock}>{clock.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</Text>
          <Text style={styles.date}>{clock.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}</Text>
          <BlurView blurTarget={wallpaper} blurMethod="dimezisBlurViewSdk31Plus" intensity={55} tint="dark" style={styles.loginCard}>
            <View style={styles.avatar}><Ionicons name="person-outline" size={31} color="#d8eeff" /></View>
            <Text style={styles.heading}>Your workspace, anywhere.</Text>
            <Text style={styles.subtitle}>Unlock to wake your cloud GPU.</Text>
            <TextInput accessibilityLabel="Host username" value={username} onChangeText={setUsername}
              placeholder="Host username" placeholderTextColor="#99abc5" autoCapitalize="none"
              autoCorrect={false} textContentType="username" editable={!busy} style={styles.input} />
            <TextInput accessibilityLabel="Host password" value={password} onChangeText={setPassword}
              placeholder="Host password" placeholderTextColor="#99abc5" secureTextEntry
              textContentType="password" editable={!busy} onSubmitEditing={() => { void login(); }} style={styles.input} />
            {!!(apiConfig.error || error) && <Text accessibilityRole="alert" style={styles.error}>{apiConfig.error || error}</Text>}
            {!!notice && <Text style={styles.notice}>{notice}</Text>}
            {!!availablePods.length && <View style={styles.podChoices}>
              <Text style={styles.podChoicesTitle}>RunPod workstations</Text>
              {availablePods.map(pod => <Pressable key={pod.id} accessibilityRole="radio"
                accessibilityState={{ checked: selectedPodId === pod.id }}
                onPress={() => setSelectedPodId(pod.id)} style={[styles.podChoice,
                  selectedPodId === pod.id && styles.podChoiceSelected]}>
                <View style={styles.podChoiceCopy}>
                  <Text numberOfLines={1} style={styles.podChoiceName}>{pod.name}</Text>
                  <Text numberOfLines={1} style={styles.podChoiceMeta}>{pod.id} · {pod.desiredStatus}</Text>
                </View>
                <Ionicons name={selectedPodId === pod.id ? 'radio-button-on' : 'radio-button-off'}
                  size={18} color={selectedPodId === pod.id ? '#89d1ff' : '#9bb0cd'} />
              </Pressable>)}
            </View>}
            <Pressable accessibilityRole="button" disabled={busy || !password || !!apiConfig.error}
              style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed,
                (busy || !password || !!apiConfig.error) && styles.disabled]} onPress={() => { void login(); }}>
              {busy ? <ActivityIndicator color="#0b1933" /> : <><Ionicons name="arrow-forward" size={20} color="#0b1933" />
                <Text style={styles.primaryLabel}>{availablePods.length ? 'Open selected workstation' : 'Unlock workstation'}</Text></>}
            </Pressable>
          </BlurView>
          <Text style={styles.footnote}>On demand compute · Private workspace</Text>
        </ScrollView>
      </KeyboardAvoidingView> : phase === 'booting' ? <View style={styles.bootLayout}>
        <Animated.View style={{ opacity: bootPulse }}><Ionicons name="logo-windows" size={64} color="#76cfff" /></Animated.View>
        <Text style={styles.heading}>Waking your workstation</Text>
        <Text style={styles.subtitle}>{status?.isRunning ? 'GPU online. Connecting the desktop…' : 'Allocating your cloud GPU…'}</Text>
        <View style={styles.progressTrack}><Animated.View style={[styles.progressBar,
          { transform: [{ scaleX: progress }] }]} /></View>
        <Text style={styles.eyebrow}>{status?.desiredStatus || 'CONNECTING'}</Text>
        {!!notice && <Text style={styles.notice}>{notice}</Text>}
        <Pressable accessibilityRole="button" onPress={confirmShutdown} disabled={busy} style={styles.secondaryButton}>
          <Text style={styles.body}>{busy ? 'Stopping…' : 'Cancel and shut down'}</Text>
        </Pressable>
      </View> : <View style={styles.desktop}>
        {!workstationImmersive && <View style={styles.desktopHeader}><View><Text style={styles.eyebrow}>PERSONAL CLOUD</Text>
          <Text style={styles.desktopTitle}>A little more possibility.</Text></View>
          <Pressable accessibilityRole="button" accessibilityLabel="Open GPU performance" onPress={() => openApp('performance')}
            style={styles.telemetry}><View style={styles.onlineDot} /><Text style={styles.telemetryText}>
              GPU {percent(status?.gpu.gpuUtilPercent)}{ '\n' }VRAM {percent(status?.gpu.memoryUtilPercent)}</Text></Pressable>
        </View>}
        {!workstationImmersive && <View style={styles.desktopIcons}>{apps.map(app => <Pressable key={app.id} accessibilityRole="button"
          onPress={() => openApp(app.id)} style={styles.desktopIcon}>
          <View style={styles.appTile}><Ionicons name={app.icon} size={30} color={app.color} /></View>
          <Text style={styles.appLabel}>{app.title}</Text>
        </Pressable>)}</View>}
        <View style={workstationImmersive ? styles.immersiveWorkspace : styles.workspace}>
          {!workstationImmersive && frames.length === 0 && <View style={styles.emptyWorkspace}>
            <View style={styles.emptyCard}>
              <View style={styles.appTile}><Ionicons name="desktop-outline" size={30} color="#6ed7ff" /></View>
              <Text style={styles.panelTitle}>Your workspace is ready</Text>
              <Text style={styles.body}>Open the GPU workstation to continue on your cloud desktop.</Text>
              <Pressable accessibilityRole="button" onPress={() => openApp('workstation')} style={styles.emptyAction}>
                <Text style={styles.emptyActionLabel}>Open GPU Workstation</Text>
              </Pressable>
            </View>
          </View>}
          {frames.map(frame => <AppFrame key={frame.id} frame={frame}
          immersive={workstationImmersive && frame.id === 'workstation'}
          focused={active === frame.id} onFocus={() => setActive(frame.id)}
          onMinimize={() => patchFrame(frame.id, { minimized: true })}
          onMaximize={() => {
            if (Platform.OS !== 'web' && frame.id === 'workstation') {
              patchFrame(frame.id, { maximized: true }); setImmersive(true);
            } else patchFrame(frame.id, { maximized: !frame.maximized });
          }}
          onClose={() => setFrames(previous => previous.filter(item => item.id !== frame.id))}>
          {frame.id === 'workstation' && session ? <View style={styles.streamContainer}>
            {!workstationImmersive && <View style={styles.streamToolbar}><Text style={styles.smallText}>{streamLoaded ? 'Remote desktop' : 'Connecting stream…'}</Text>
              <IconButton icon="refresh-outline" label="Reload desktop stream" onPress={() => {
                setStreamError(''); setStreamLoaded(false); webview.current?.reload();
              }} />
              {!workstationImmersive && <IconButton icon={chromeHidden ? 'eye-outline' : 'eye-off-outline'} label="Toggle stream toolbar"
                onPress={toggleRemoteToolbar} />}
            </View>}
            {Platform.OS === 'web' ? <View style={styles.panel}><Text style={styles.body}>
              Use the Android or iOS app for the hardware-accelerated desktop stream.</Text></View> : <WebView<object>
              key={`${chromeHidden ? 'hidden-chrome' : 'visible-chrome'}-${streamReloadVersion}`} ref={webview}
              source={{ uri: session.streamUrl }}
              basicAuthCredential={streamAuthAttempted ? { username: streamUsername, password: streamPassword } : undefined}
              style={styles.webview} androidLayerType="hardware" javaScriptEnabled domStorageEnabled
              keyboardDisplayRequiresUserAction={false}
              scrollEnabled={false} bounces={false}
              originWhitelist={[new URL(session.streamUrl).origin, 'about:blank']}
              onShouldStartLoadWithRequest={navigation => canNavigate(navigation.url, session.streamUrl)}
              injectedJavaScript={chromeHidden ? STREAM_CHROME_SCRIPT : 'true;'}
              allowsInlineMediaPlayback mediaPlaybackRequiresUserAction={false}
              mixedContentMode="never" setSupportMultipleWindows={false}
              allowFileAccess={false} allowUniversalAccessFromFileURLs={false}
              onLoadEnd={() => {
                setStreamLoaded(true);
                if (keyboardPending) {
                  setKeyboardPending(false);
                  webview.current?.injectJavaScript(OPEN_REMOTE_KEYBOARD_SCRIPT);
                }
              }}
              onError={event => {
                if (event.nativeEvent.description === 'net::ERR_HTTP_RESPONSE_CODE_FAILURE') return;
                setStreamError('Stream disconnected. Reload to reconnect.');
              }}
              onHttpError={event => {
                const statusCode = event.nativeEvent.statusCode;
                if (statusCode === 401) {
                  setStreamAuthPrompt(true);
                  setStreamError(streamAuthAttempted
                    ? 'The desktop rejected these credentials. Check the Kasm username and Pod password.' : '');
                } else {
                  setStreamError(`Stream returned HTTP ${statusCode}. Check the desktop service.`);
                }
              }}
              onContentProcessDidTerminate={() => { setStreamError('Stream process restarted. Reload to reconnect.'); }}
            />}
            {workstationImmersive && <View pointerEvents="box-none" style={styles.mobileControlDock}>
              {mobileToolsOpen && <View style={styles.mobileControlGroup}>
                <Pressable accessibilityRole="button" accessibilityLabel="Reload remote desktop"
                  onPress={() => { setMobileToolsOpen(false); setStreamError(''); setStreamLoaded(false); webview.current?.reload(); }}
                  style={styles.mobileControlButton}>
                  <Ionicons name="refresh-outline" size={21} color="#f2f7ff" />
                </Pressable>
                <Pressable accessibilityRole="button" accessibilityLabel={chromeHidden ? 'Show remote desktop controls' : 'Hide remote desktop controls'}
                  onPress={toggleRemoteToolbar} style={styles.mobileControlButton}>
                  <Ionicons name={chromeHidden ? 'eye-outline' : 'eye-off-outline'} size={21} color="#f2f7ff" />
                </Pressable>
                <Pressable accessibilityRole="button" accessibilityLabel="Exit full screen"
                  onPress={() => { setMobileToolsOpen(false); setImmersive(false); }} style={styles.mobileControlButton}>
                  <Ionicons name="contract-outline" size={21} color="#f2f7ff" />
                </Pressable>
              </View>}
              <Pressable accessibilityRole="button" accessibilityLabel="Show remote keyboard"
                onPress={openRemoteKeyboard} style={styles.mobileControlButton}>
                <Ionicons name="keypad-outline" size={22} color="#f2f7ff" />
              </Pressable>
              <Pressable accessibilityRole="button" accessibilityLabel={mobileToolsOpen ? 'Hide remote desktop options' : 'Show remote desktop options'}
                onPress={() => setMobileToolsOpen(value => !value)} style={styles.mobileControlButton}>
                <Ionicons name={mobileToolsOpen ? 'close-outline' : 'ellipsis-horizontal'} size={22} color="#f2f7ff" />
              </Pressable>
            </View>}
            {Platform.OS !== 'web' && streamAuthPrompt && <View style={styles.streamAuthShade}>
              <View style={styles.streamAuthPanel}>
                <Text style={styles.panelTitle}>Sign in to the desktop</Text>
                <Text style={styles.body}>Use the Kasm credentials configured for this RunPod Pod. They are separate from your Cloud GPU OS login.</Text>
                <TextInput accessibilityLabel="Kasm username" value={streamUsername} onChangeText={setStreamUsername}
                  placeholder="Kasm username" placeholderTextColor="#99abc5" autoCapitalize="none"
                  autoCorrect={false} textContentType="username" style={styles.input} />
                <TextInput accessibilityLabel="Kasm password" value={streamPassword} onChangeText={setStreamPassword}
                  placeholder="Desktop password (VNC_PW)" placeholderTextColor="#99abc5" secureTextEntry
                  textContentType="password" onSubmitEditing={() => {
                    if (!streamUsername || !streamPassword) return;
                    setStreamError(''); setStreamAuthPrompt(false); setStreamAuthAttempted(true);
                    setStreamReloadVersion(version => version + 1);
                  }} style={styles.input} />
                {!!streamError && <Text accessibilityRole="alert" style={styles.error}>{streamError}</Text>}
                <Pressable accessibilityRole="button" disabled={!streamUsername || !streamPassword}
                  style={({ pressed }) => [styles.streamAuthButton, pressed && styles.pressed,
                    (!streamUsername || !streamPassword) && styles.disabled]}
                  onPress={() => {
                    setStreamError(''); setStreamAuthPrompt(false); setStreamAuthAttempted(true);
                    setStreamReloadVersion(version => version + 1);
                  }}>
                  <Text style={styles.primaryLabel}>Connect desktop</Text>
                </Pressable>
              </View>
            </View>}
            {!!streamError && <View style={styles.streamError}><Text style={styles.error}>{streamError}</Text>
              <Pressable accessibilityRole="button" onPress={() => { setStreamError(''); webview.current?.reload(); }}>
                <Text style={styles.link}>Reconnect</Text></Pressable></View>}
          </View> : frame.id === 'performance' ? <ScrollView contentContainerStyle={styles.panel}>
            <Text style={styles.panelTitle}>GPU performance</Text>
            <Text style={styles.metric}>{percent(status?.gpu.gpuUtilPercent)}</Text><Text style={styles.body}>GPU utilization</Text>
            <Text style={styles.metric}>{percent(status?.gpu.memoryUtilPercent)}</Text><Text style={styles.body}>VRAM utilization</Text>
            <Text style={styles.notice}>Uptime {Math.floor((status?.uptime || 0) / 60)} min · {status?.containerHealth || 'Unknown'}</Text>
            <Text style={styles.smallText}>Missing telemetry is shown as —. Refreshes every 10 seconds.</Text>
          </ScrollView> : <ScrollView contentContainerStyle={styles.panel}>
            <Ionicons name="logo-windows" size={42} color="#79ccff" /><Text style={styles.panelTitle}>Cloud GPU OS</Text>
            <Text style={styles.body}>A Windows 11 inspired mobile shell for your own cloud workstation.</Text>
            <Text style={styles.notice}>Pod: {session?.podId}</Text>
            <Text style={styles.body}>Native animations adapt to your display. Remote frame rate and latency depend on the stream, device and network.</Text>
            <Text style={styles.notice}>Automatic idle shutdown is off. Locking or closing the app leaves this Pod running. Shut it down explicitly from the Start menu when you are finished.</Text>
          </ScrollView>}
        </AppFrame>)}
        </View>
        {!workstationImmersive && !!notice && <View style={styles.noticeBanner}><Text style={styles.smallText}>{notice}</Text></View>}
        {!workstationImmersive && startOpen && <BlurView blurTarget={wallpaper} blurMethod="dimezisBlurViewSdk31Plus" intensity={80} tint="dark" style={styles.startMenu}>
          <Text style={styles.panelTitle}>Pinned</Text><View style={styles.pinnedApps}>{apps.map(app =>
            <Pressable accessibilityRole="button" key={app.id} style={styles.pinnedApp} onPress={() => openApp(app.id)}>
              <Ionicons name={app.icon} color={app.color} size={27} /><Text style={styles.appLabel}>{app.title}</Text>
            </Pressable>)}</View>
          <View style={styles.startFooter}>
            <Pressable accessibilityRole="button" accessibilityLabel="Lock workstation" onPress={lockWorkstation}
              style={styles.lockAction}>
              <View style={styles.lockAvatar}><Ionicons name="person-outline" size={17} color="#d8eeff" /></View>
              <View><Text numberOfLines={1} style={styles.body}>{username}</Text>
                <Text style={styles.lockHint}>Lock workstation</Text></View>
            </Pressable>
            <Pressable accessibilityRole="button" onPress={confirmShutdown} disabled={busy} style={styles.powerButton}>
              <Ionicons name="power-outline" size={20} color="#fff" /><Text style={styles.body}>{busy ? 'Stopping…' : 'Shut down'}</Text>
            </Pressable></View>
        </BlurView>}
        {!workstationImmersive && <BlurView blurTarget={wallpaper} blurMethod="dimezisBlurViewSdk31Plus" intensity={70} tint="dark" style={styles.taskbar}>
          <IconButton icon="logo-windows" label="Toggle Start menu" onPress={() => setStartOpen(value => !value)} />
          {apps.map(app => <Pressable key={app.id} accessibilityRole="button"
            accessibilityLabel={frames.some(frame => frame.id === app.id && active === app.id && !frame.minimized)
              ? `Minimize ${app.title}` : `Open ${app.title}`}
            style={[styles.taskIcon, frames.some(frame => frame.id === app.id) && styles.taskActive,
              frames.some(frame => frame.id === app.id && frame.minimized) && styles.taskMinimized]}
            onPress={() => toggleTaskbarApp(app.id)}>
            <Ionicons name={app.icon} size={23} color={app.color} /></Pressable>)}
          <View style={styles.taskClock}><Text style={styles.smallText}>{clock.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</Text></View>
        </BlurView>}
      </View>}
    </SafeAreaView>
  </View>;
}

export default function App() { return <SafeAreaProvider><Shell /></SafeAreaProvider>; }

const styles = StyleSheet.create({
  root: { flex: 1 }, safe: { flex: 1 }, body: { color: '#dce9ff', fontSize: 14, lineHeight: 21 },
  orbOne: { position: 'absolute', width: 550, height: 550, borderRadius: 275, backgroundColor: '#156dc2', opacity: 0.2, top: '12%', left: '-60%', transform: [{ rotate: '-30deg' }] },
  orbTwo: { position: 'absolute', width: 460, height: 460, borderRadius: 230, borderWidth: 65, borderColor: '#91abff', opacity: 0.12, bottom: '-15%', right: '-55%' },
  lockLayout: { flex: 1 }, lockScroll: { flexGrow: 1, alignItems: 'center', justifyContent: 'center', padding: 24, paddingVertical: 36 },
  eyebrow: { color: '#a5c5eb', fontSize: 10, fontWeight: '700', letterSpacing: 2.5 },
  clock: { color: '#fff', fontSize: 72, fontWeight: '200', letterSpacing: -3, marginTop: 18 },
  date: { color: '#c4d6f1', fontSize: 16, marginBottom: 32 },
  loginCard: { width: '100%', maxWidth: 400, borderRadius: 24, padding: 24, overflow: 'hidden', alignItems: 'center', backgroundColor: '#172946a0', borderWidth: 1, borderColor: '#b7d1ff26' },
  avatar: { width: 66, height: 66, borderRadius: 33, backgroundColor: '#7caef12b', alignItems: 'center', justifyContent: 'center', marginBottom: 20 },
  heading: { color: '#fff', fontSize: 22, fontWeight: '600', textAlign: 'center', marginBottom: 8 },
  subtitle: { color: '#a8bedb', fontSize: 13, textAlign: 'center', lineHeight: 20, marginBottom: 24 },
  input: { backgroundColor: '#0a152c80', color: '#fff', borderWidth: 1, borderColor: '#7994b94d', borderRadius: 9, width: '100%', padding: 14, marginBottom: 12, fontSize: 15 },
  podChoices: { width: '100%', marginBottom: 8 },
  podChoicesTitle: { color: '#dce9ff', fontSize: 13, fontWeight: '700', marginBottom: 8 },
  podChoice: { width: '100%', minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingHorizontal: 12, paddingVertical: 8, marginBottom: 7, borderRadius: 9,
    borderWidth: 1, borderColor: '#7994b94d', backgroundColor: '#0a152c80' },
  podChoiceSelected: { borderColor: '#89d1ff', backgroundColor: '#4b8eb533' },
  podChoiceCopy: { flex: 1, minWidth: 0 },
  podChoiceName: { color: '#f0f6ff', fontSize: 13, fontWeight: '600' },
  podChoiceMeta: { color: '#a9bddb', fontSize: 10, marginTop: 3 },
  primaryButton: { minHeight: 48, backgroundColor: '#89d1ff', borderRadius: 9, width: '100%', flexDirection: 'row', gap: 9, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  primaryLabel: { color: '#0b1933', fontWeight: '700', fontSize: 14 }, pressed: { opacity: 0.65 }, disabled: { opacity: 0.45 },
  error: { color: '#ffb7b7', fontSize: 13, lineHeight: 19, marginVertical: 8 },
  notice: { color: '#b8ccea', fontSize: 13, lineHeight: 20, marginVertical: 12 },
  footnote: { color: '#a2b9d8', fontSize: 11, marginTop: 24, letterSpacing: 0.6 },
  bootLayout: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 18 },
  progressTrack: { height: 4, width: '80%', maxWidth: 320, backgroundColor: '#6482ad50', borderRadius: 4, overflow: 'hidden' },
  progressBar: { height: 4, width: '100%', backgroundColor: '#8bd6ff', transformOrigin: 'left' },
  secondaryButton: { marginTop: 24, padding: 14, borderRadius: 10, borderWidth: 1, borderColor: '#9fc2ed50' },
  desktop: { flex: 1 }, desktopHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 18, gap: 12 },
  desktopTitle: { color: '#e3eeff', fontSize: 16, marginTop: 8, fontWeight: '300' },
  telemetry: { flexDirection: 'row', alignItems: 'center', gap: 7, borderRadius: 12, padding: 10, backgroundColor: '#08162c90', borderWidth: 1, borderColor: '#8fb6f52b' },
  telemetryText: { color: '#a8dbff', fontSize: 10, fontWeight: '600', lineHeight: 16 },
  onlineDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: '#9af4c4' },
  desktopIcons: { flexDirection: 'row', paddingHorizontal: 16, gap: 12, marginBottom: 12 },
  desktopIcon: { width: 85, alignItems: 'center', gap: 7, padding: 6 },
  appTile: { height: 52, width: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: '#d1e9ff12', borderWidth: 1, borderColor: '#cbe5ff24' },
  appLabel: { color: '#e1edff', fontSize: 11, textAlign: 'center', lineHeight: 15 },
  workspace: { flex: 1, marginHorizontal: 10, marginBottom: 8 },
  immersiveWorkspace: { flex: 1, margin: 0, overflow: 'hidden' },
  emptyWorkspace: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 },
  emptyCard: { width: '100%', maxWidth: 360, alignItems: 'center', gap: 12, padding: 24,
    borderRadius: 18, backgroundColor: '#12223bd9', borderWidth: 1, borderColor: '#9dc5f22b' },
  emptyAction: { minHeight: 44, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center',
    borderRadius: 10, backgroundColor: '#89d1ff', marginTop: 4 },
  emptyActionLabel: { color: '#0b1933', fontSize: 13, fontWeight: '700' },
  frame: { position: 'absolute', backgroundColor: '#101e35', borderWidth: 1, borderColor: '#8bacdf55', borderRadius: 12, overflow: 'hidden', shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 18, elevation: 6 },
  immersiveFrame: { top: 0, left: 0, right: 0, bottom: 0, borderWidth: 0, borderRadius: 0, elevation: 0, shadowOpacity: 0 },
  maximized: { top: 0, left: 0, right: 0, bottom: 0 },
  floating: { top: 12, left: '4%', width: '92%', height: '78%', minHeight: 180 },
  titlebar: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#233654', height: 42 },
  dragHandle: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 9, paddingLeft: 12, height: '100%' },
  windowTitle: { color: '#e7f0ff', fontSize: 11, flex: 1 },
  iconButton: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center', borderRadius: 6 },
  dangerButton: { backgroundColor: '#bc354120' }, frameContent: { flex: 1 },
  streamContainer: { flex: 1, backgroundColor: '#050d19' }, streamToolbar: { flexDirection: 'row', alignItems: 'center', paddingLeft: 12, backgroundColor: '#14223b' },
  smallText: { color: '#bbcde6', fontSize: 11, lineHeight: 16, flexShrink: 1 },
  webview: { flex: 1, backgroundColor: '#050d19' },
  mobileControlDock: { position: 'absolute', right: 12, bottom: 12, zIndex: 30,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 8 },
  mobileControlGroup: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  mobileControlButton: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#0a1732df', borderWidth: 1, borderColor: '#b6d5ff55' },
  streamError: { position: 'absolute', left: 8, right: 8, bottom: 8, padding: 16, borderRadius: 10, backgroundColor: '#17243af5' },
  streamAuthShade: { ...StyleSheet.absoluteFill, justifyContent: 'center', padding: 12, backgroundColor: '#071226d9' },
  streamAuthPanel: { borderRadius: 14, padding: 18, gap: 12, backgroundColor: '#17243af5', borderWidth: 1, borderColor: '#8bacdf55' },
  streamAuthButton: { minHeight: 46, marginTop: 4, borderRadius: 9, alignItems: 'center', justifyContent: 'center', backgroundColor: '#89d1ff' },
  link: { color: '#85d4ff', fontWeight: '600', paddingVertical: 8 },
  panel: { padding: 22, gap: 12 }, panelTitle: { color: '#f1f6ff', fontSize: 18, fontWeight: '600' },
  metric: { fontSize: 40, color: '#8bd6ff', fontWeight: '300' },
  noticeBanner: { paddingHorizontal: 18, paddingVertical: 8, backgroundColor: '#13223bc0' },
  startMenu: { position: 'absolute', bottom: 65, left: 12, right: 12, padding: 22, borderRadius: 18, overflow: 'hidden', borderWidth: 1, borderColor: '#8bacdf55', backgroundColor: '#162641ec', zIndex: 30 },
  pinnedApps: { flexDirection: 'row', justifyContent: 'space-around', marginVertical: 26, gap: 12 },
  pinnedApp: { alignItems: 'center', gap: 12, flex: 1 },
  startFooter: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderTopWidth: 1, borderColor: '#8bacdf30', paddingTop: 16 },
  lockAction: { flexDirection: 'row', alignItems: 'center', gap: 10, flexShrink: 1, paddingVertical: 4, paddingRight: 8 },
  lockAvatar: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', backgroundColor: '#7caef12b' },
  lockHint: { color: '#91afd2', fontSize: 10, marginTop: 1 },
  powerButton: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 8 },
  taskbar: { height: 58, flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 8, paddingHorizontal: 12, backgroundColor: '#1b2c4799', borderTopWidth: 1, borderColor: '#b5d4ff26', overflow: 'hidden', zIndex: 40 },
  taskIcon: { width: 40, height: 40, justifyContent: 'center', alignItems: 'center', borderRadius: 8 },
  taskActive: { backgroundColor: '#e1eeff18', borderBottomWidth: 2, borderColor: '#8bd6ff' },
  taskMinimized: { opacity: 0.6 },
  taskClock: { marginLeft: 'auto', alignItems: 'flex-end' },
});
