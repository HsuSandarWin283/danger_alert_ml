'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import BackgroundMonitor from './background-monitor';
import { Capacitor } from '@capacitor/core';

type PredictionResponse = {
  prediction: string;
  confidence: number;
  probabilities?: Record<string, number>;
  rms?: number;
};

export type DangerAlertPayload = {
  detectedAnswer: string;
  confidence: number;
  probabilities?: Record<string, number>;
  rms: number;
};

type PredictionApiResponse = {
  prediction?: string;
  detectedAnswer?: string;
  answer?: string;
  confidence?: number;
  score?: number;
  probability?: number;
  probabilities?: Record<string, number>;
  [key: string]: unknown;
};

type UseDangerSoundMonitorReturn = {
  isMonitoring: boolean;
  isRecording: boolean;
  rmsLevel: number;
  lastPrediction: PredictionResponse | null;
  error: string | null;
  startMonitoring: () => Promise<void>;
  stopMonitoring: () => void;
};

const DEFAULT_PREDICT_URL = 'http://192.168.99.112:8000/predict';
const WINDOW_SECONDS = 3;
const ANALYSIS_HOP_MS = 1000;
const RMS_CHECK_MS = 200;
const SCRIPT_PROCESSOR_BUFFER_SIZE = 4096;
const RMS_THRESHOLD = 0.004;
const CONFIDENCE_THRESHOLD = 0.88;
const DUPLICATE_ALERT_MS = 10000;
const DANGER_COOLDOWN_MS = 3000;
const DANGER_LABELS = new Set(['accident', 'gunshot', 'scream']);
const MAX_BUFFER_SECONDS = 7;

function getPredictUrl() {
  return process.env.NEXT_PUBLIC_DANGER_PREDICT_URL || DEFAULT_PREDICT_URL;
}

function calculateRms(samples: Float32Array | number[]) {
  if (samples.length === 0) return 0;

  let sum = 0;

  for (let i = 0; i < samples.length; i += 1) {
    const sample = Number(samples[i]);
    sum += sample * sample;
  }

  return Math.sqrt(sum / samples.length);
}

const TARGET_RMS = 0.05;

function normalizeSamples(samples: number[]): number[] {
  const rms = calculateRms(samples);
  if (rms < 0.0001 || rms === 0) return samples;

  const gain = TARGET_RMS / rms;
  const clampedGain = Math.min(gain, 10.0);

  return samples.map((s) => Math.max(-1, Math.min(1, s * clampedGain)));
}

function samplesToWavBlob(samples: number[], sampleRate: number) {
  const numberOfChannels = 1;
  const bytesPerSample = 2;
  const blockAlign = numberOfChannels * bytesPerSample;
  const dataSize = samples.length * blockAlign;
  const arrayBuffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(arrayBuffer);

  const writeString = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i));
    }
  };

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, numberOfChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bytesPerSample * 8, true);
  writeString(36, 'data');
  view.setUint32(40, dataSize, true);

  let offset = 44;

  for (let i = 0; i < samples.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    offset += 2;
  }

  return new Blob([view], { type: 'audio/wav' });
}

function normalizeLabel(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[\s-]+/g, '_');
}

function formatLabel(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function normalizePrediction(data: PredictionApiResponse): PredictionResponse {
  const prediction = normalizeLabel(
    String(data?.prediction ?? data?.detectedAnswer ?? data?.answer ?? ''),
  );
  const confidence = Number(data?.confidence ?? data?.score ?? data?.probability ?? 0);

  return {
    prediction,
    confidence,
    probabilities: data?.probabilities || {},
  };
}

export function useDangerSoundMonitor(
  onDangerDetected?: (payload: DangerAlertPayload) => void,
): UseDangerSoundMonitorReturn {
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [rmsLevel, setRmsLevel] = useState(0);
  const [lastPrediction, setLastPrediction] = useState<PredictionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const silentGainRef = useRef<GainNode | null>(null);
  const intervalRef = useRef<number | null>(null);
  const rmsIntervalRef = useRef<number | null>(null);
  const pendingSamplesRef = useRef<number[]>([]);
  const currentRmsRef = useRef(0);
  const isPredictingRef = useRef(false);
  const lastAlertRef = useRef<{ label: string; timestamp: number } | null>(null);
  const mountedRef = useRef(false);
  const closingAudioContextsRef = useRef<WeakSet<AudioContext>>(new WeakSet());
  const startTimeRef = useRef<number>(0);
  const lastAnalysisTimeRef = useRef<number>(0);
  const dangerStateRef = useRef<'NORMAL' | 'DANGER'>('NORMAL');
  const lastDangerTimeRef = useRef<number>(0);
  const WARMUP_MS = 5000;
  const MONITORING_KEY = 'danger_monitoring_active';

  const stopMonitoring = useCallback(() => {
    setIsRecording(false);
    setIsMonitoring(false);
    localStorage.removeItem(MONITORING_KEY);

    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (rmsIntervalRef.current !== null) {
      window.clearInterval(rmsIntervalRef.current);
      rmsIntervalRef.current = null;
    }

    try {
      processorRef.current?.disconnect();
      sourceRef.current?.disconnect();
      analyserRef.current?.disconnect();
      silentGainRef.current?.disconnect();
    } catch {
    }

    processorRef.current = null;
    sourceRef.current = null;
    analyserRef.current = null;
    silentGainRef.current = null;

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    const audioContext = audioContextRef.current;
    audioContextRef.current = null;

    if (
      audioContext &&
      audioContext.state !== 'closed' &&
      !closingAudioContextsRef.current.has(audioContext)
    ) {
      closingAudioContextsRef.current.add(audioContext);
      void audioContext
        .close()
        .catch(() => undefined)
        .finally(() => closingAudioContextsRef.current.delete(audioContext));
    }

    pendingSamplesRef.current = [];
    isPredictingRef.current = false;
    lastAlertRef.current = null;
    dangerStateRef.current = 'NORMAL';
    lastDangerTimeRef.current = 0;
    lastAnalysisTimeRef.current = 0;
    startTimeRef.current = 0;

    if (Capacitor.isNativePlatform()) {
 BackgroundMonitor.stopMonitoring().catch(() => {});
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    const checkNativeState = async () => {
      if (Capacitor.isNativePlatform()) {
        try {
          const { running } = await BackgroundMonitor.isRunning();
          if (running) {
            setIsMonitoring(true);
            setIsRecording(true);
            localStorage.setItem(MONITORING_KEY, 'true');
            await startMonitoring();
            return;
          }
          localStorage.removeItem(MONITORING_KEY);
        } catch {}
      }

      const wasMonitoring = localStorage.getItem(MONITORING_KEY) === 'true';
      if (wasMonitoring) {
        setTimeout(() => {
          startMonitoring();
        }, 1000);
      }
    };

    checkNativeState();

    return () => {
      mountedRef.current = false;
      if (!Capacitor.isNativePlatform()) {
        stopMonitoring();
      }
    };
  }, [stopMonitoring]);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    if (!isMonitoring) return;

    const startBg = async () => {
      try {
        await BackgroundMonitor.startMonitoring({ apiUrl: getPredictUrl().replace('/predict', '') });
      } catch (e) { console.error('Background service failed:', e); }
    };
    startBg();

    const fetchMembers = async () => {
      try {
        const { getAuth } = await import('firebase/auth');
        const { getFirestore, collection, query, where, getDocs, doc, getDoc } = await import('firebase/firestore');
        const auth = getAuth();
        const user = auth.currentUser;
        if (!user) return;

        const db = getFirestore();
        const q = query(collection(db, 'group_members'), where('groupId', '==', user.uid));
        const snapshot = await getDocs(q);
        console.log('Trusted group docs found:', snapshot.size);

        const memberUids: { uid: string }[] = [];
        for (const d of snapshot.docs) {
          const data = d.data();
          const uid = data.userId;
          if (!uid) continue;
          memberUids.push({ uid });
        }

        console.log('Saving', memberUids.length, 'member UIDs for native alert');
        await BackgroundMonitor.saveTrustedMembers({ members: JSON.stringify(memberUids) });
      } catch (e) {
        console.error('Failed to fetch trusted members:', e);
      }
    };
    fetchMembers();
  }, [isMonitoring]);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;

    let prev: boolean | null = null;

    const check = async () => {
      try {
        const { running } = await BackgroundMonitor.isRunning();
        if (prev === running) return;
        prev = running;

        setIsMonitoring(running);
        setIsRecording(running);
        if (running) {
          localStorage.setItem(MONITORING_KEY, 'true');
        } else {
          localStorage.removeItem(MONITORING_KEY);
        }
      } catch {}
    };

    check();
    const poll = setInterval(check, 2000);

    return () => clearInterval(poll);
  }, []);

  const startMonitoring = useCallback(async () => {
    setError(null);

    if (Capacitor.isNativePlatform()) {
      setIsMonitoring(true);
      setIsRecording(true);
      localStorage.setItem(MONITORING_KEY, 'true');
    }

    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (rmsIntervalRef.current !== null) {
      window.clearInterval(rmsIntervalRef.current);
      rmsIntervalRef.current = null;
    }
    try {
      processorRef.current?.disconnect();
      sourceRef.current?.disconnect();
      analyserRef.current?.disconnect();
      silentGainRef.current?.disconnect();
    } catch {}
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    const prevCtx = audioContextRef.current;
    audioContextRef.current = null;
    if (prevCtx && prevCtx.state !== 'closed') {
      prevCtx.close().catch(() => {});
    }
    pendingSamplesRef.current = [];

    if (!window.navigator?.mediaDevices?.getUserMedia) {
      if (!Capacitor.isNativePlatform()) {
        setError('Microphone API is not available in this browser.');
      }
      return;
    }

    const AudioContextConstructor =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;

    if (!AudioContextConstructor) {
      setError('AudioContext API is not available in this browser.');
      return;
    }

    try {
      const stream = await window.navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: true,
          autoGainControl: false,
        },
      });

      streamRef.current = stream;

      const audioContext = new AudioContextConstructor();
      audioContextRef.current = audioContext;

      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 1024;
      analyserRef.current = analyser;

      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      const processor = audioContext.createScriptProcessor(SCRIPT_PROCESSOR_BUFFER_SIZE, 1, 1);
      processorRef.current = processor;

      const silentGain = audioContext.createGain();
      silentGain.gain.value = 0;
      silentGainRef.current = silentGain;

      source.connect(analyser);
      source.connect(processor);
      processor.connect(silentGain);
      silentGain.connect(audioContext.destination);

      const analyserData = new Float32Array(analyser.fftSize);

      rmsIntervalRef.current = window.setInterval(() => {
        analyser.getFloatTimeDomainData(analyserData);
        const rms = calculateRms(analyserData);
        currentRmsRef.current = rms;
        setRmsLevel(rms);
      }, RMS_CHECK_MS);

      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);
        const maxSamples = audioContext.sampleRate * 7;

        for (let i = 0; i < input.length; i += 1) {
          pendingSamplesRef.current.push(input[i]);
        }

        if (pendingSamplesRef.current.length > maxSamples) {
          pendingSamplesRef.current.splice(0, pendingSamplesRef.current.length - maxSamples);
        }
      };

      const maxBufferSamples = audioContext.sampleRate * MAX_BUFFER_SECONDS;

      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);

        for (let i = 0; i < input.length; i += 1) {
          pendingSamplesRef.current.push(input[i]);
        }

        if (pendingSamplesRef.current.length > maxBufferSamples) {
          pendingSamplesRef.current.splice(
            0,
            pendingSamplesRef.current.length - maxBufferSamples,
          );
        }
      };

      const analyzeWindow = () => {
        if (Date.now() - startTimeRef.current < WARMUP_MS) {
          return;
        }

        const targetSamples = Math.floor(audioContext.sampleRate * WINDOW_SECONDS);

        if (pendingSamplesRef.current.length < targetSamples) {
          return;
        }

        if (isPredictingRef.current) {
          return;
        }

        const samples = pendingSamplesRef.current.slice(-targetSamples);
        const rms = calculateRms(samples);
        currentRmsRef.current = rms;
        setRmsLevel(rms);

        const rmsPassed = rms >= RMS_THRESHOLD;
        console.log(
          `[danger-monitor] RMS=${rms.toFixed(4)} threshold=${RMS_THRESHOLD} rmsPassed=${rmsPassed}`,
        );

        if (!rmsPassed) {
          if (dangerStateRef.current === 'DANGER') {
            const timeSinceDanger = Date.now() - lastDangerTimeRef.current;
            if (timeSinceDanger > DANGER_COOLDOWN_MS) {
              dangerStateRef.current = 'NORMAL';
              console.log(`[danger-monitor] STATE=NORMAL cooldownExpired=true`);
            } else {
              console.log(
                `[danger-monitor] STATE=DANGER cooldownRemaining=${DANGER_COOLDOWN_MS - timeSinceDanger}ms`,
              );
            }
          }
          return;
        }

        console.log(`[danger-monitor] RMS PASS rms=${rms.toFixed(4)} threshold=${RMS_THRESHOLD}`);

        isPredictingRef.current = true;

        const sendPrediction = async () => {
          try {
            const normalized = normalizeSamples(samples);
            const wavBlob = samplesToWavBlob(normalized, audioContext.sampleRate);
            const formData = new FormData();
            formData.append('file', wavBlob, `monitoring-${Date.now()}.wav`);

            const response = await fetch(getPredictUrl(), {
              method: 'POST',
              body: formData,
            });

            if (!response.ok) {
              throw new Error(`Prediction failed with status ${response.status}`);
            }

            const data = await response.json();
            const prediction = normalizePrediction(data);
            prediction.rms = rms;
            setLastPrediction(prediction);

            const serverIsDanger = Boolean(data.is_danger);
            const now = Date.now();

            console.log(
              `[danger-monitor] label=${prediction.prediction} confidence=${prediction.confidence.toFixed(4)} ` +
                `rms=${rms.toFixed(4)} rmsPassed=true serverIsDanger=${serverIsDanger} reason=${data.reason || 'unknown'} ` +
                `state=${dangerStateRef.current}`,
            );

            if (serverIsDanger) {
              lastDangerTimeRef.current = now;

              if (dangerStateRef.current === 'NORMAL') {
                const lastAlert = lastAlertRef.current;
                const isDuplicate =
                  lastAlert &&
                  lastAlert.label === prediction.prediction &&
                  now - lastAlert.timestamp < DUPLICATE_ALERT_MS;

                if (!isDuplicate) {
                  dangerStateRef.current = 'DANGER';
                  lastAlertRef.current = {
                    label: prediction.prediction,
                    timestamp: now,
                  };

                  const payload: DangerAlertPayload = {
                    detectedAnswer: formatLabel(prediction.prediction),
                    confidence: prediction.confidence,
                    probabilities: prediction.probabilities,
                    rms,
                  };

                  console.log(
                    `[danger-monitor] STATE=DANGER ACTION=TRIGGER_DANGER label=${prediction.prediction} confidence=${prediction.confidence.toFixed(4)}`,
                  );

                  if (!Capacitor.isNativePlatform()) {
                    window.dispatchEvent(
                      new CustomEvent('danger-detected', {
                        detail: payload,
                      }),
                    );
                  }

                  if (mountedRef.current) {
                    onDangerDetected?.(payload);
                  }
                } else {
                  console.log(
                    `[danger-monitor] STATE=DANGER ACTION=DUPLICATE_SUPPRESSED label=${prediction.prediction}`,
                  );
                }
              } else {
                console.log(
                  `[danger-monitor] STATE=DANGER ACTION=IGNORE label=${prediction.prediction}`,
                );
              }
            } else {
              if (dangerStateRef.current === 'DANGER') {
                const timeSinceDanger = now - lastDangerTimeRef.current;
                if (timeSinceDanger > DANGER_COOLDOWN_MS) {
                  dangerStateRef.current = 'NORMAL';
                  console.log(`[danger-monitor] STATE=NORMAL cooldownExpired=true`);
                } else {
                  console.log(
                    `[danger-monitor] STATE=DANGER cooldownRemaining=${DANGER_COOLDOWN_MS - timeSinceDanger}ms`,
                  );
                }
              } else {
                console.log(
                  `[danger-monitor] STATE=NORMAL ACTION=IGNORE label=${prediction.prediction} confidence=${prediction.confidence.toFixed(4)}`,
                );
              }
            }
          } catch (err) {
            const message = err instanceof Error ? err.message : 'Prediction failed';
            setError(message);
            console.error(`[danger-monitor] ERROR=${message}`);
          } finally {
            isPredictingRef.current = false;
          }
        };

        void sendPrediction();
      };

      const scheduleAnalysis = () => {
        const now = Date.now();
        if (now - lastAnalysisTimeRef.current >= ANALYSIS_HOP_MS) {
          lastAnalysisTimeRef.current = now;
          analyzeWindow();
        }
      };

      intervalRef.current = window.setInterval(scheduleAnalysis, ANALYSIS_HOP_MS);
      startTimeRef.current = Date.now();
      lastAnalysisTimeRef.current = Date.now();
      setIsRecording(true);
      setIsMonitoring(true);
      localStorage.setItem(MONITORING_KEY, 'true');
    } catch (err) {
      stopMonitoring();
      const message = err instanceof Error ? err.message : 'Failed to start microphone monitoring';
      setError(message);
    }
  }, [onDangerDetected, stopMonitoring]);

  return {
    isMonitoring,
    isRecording,
    rmsLevel,
    lastPrediction,
    error,
    startMonitoring,
    stopMonitoring,
  };
}
