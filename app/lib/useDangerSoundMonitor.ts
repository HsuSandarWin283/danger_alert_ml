'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

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

const DEFAULT_PREDICT_URL = 'https://danger-alert-ml.onrender.com/predict';
const CHUNK_MS = 5000;
const RMS_CHECK_MS = 200;
const SCRIPT_PROCESSOR_BUFFER_SIZE = 4096;
const RMS_THRESHOLD = 0.003;
const CONFIDENCE_THRESHOLD = 0.6;
const DUPLICATE_ALERT_MS = 10000;
const DANGER_LABELS = new Set(['accident', 'gunshot', 'scream', 'glass_break']);

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

  const stopMonitoring = useCallback(() => {
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
      // Ignore disconnect errors during cleanup.
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
    setIsRecording(false);
    setIsMonitoring(false);
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      stopMonitoring();
    };
  }, [stopMonitoring]);

  const startMonitoring = useCallback(async () => {
    setError(null);
    stopMonitoring();

    if (!window.navigator?.mediaDevices?.getUserMedia) {
      setError('Microphone API is not available in this browser.');
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
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
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

      const processChunk = () => {
        const targetSamples = audioContext.sampleRate * 5;

        if (pendingSamplesRef.current.length < audioContext.sampleRate * 1) {
          return;
        }

        if (isPredictingRef.current) {
          return;
        }

        const count = Math.min(pendingSamplesRef.current.length, targetSamples);
        const samples = pendingSamplesRef.current.slice(0, count);
        const rms = calculateRms(samples);

        currentRmsRef.current = rms;
        setRmsLevel(rms);

        if (rms < RMS_THRESHOLD) {
          return;
        }

        pendingSamplesRef.current.splice(0, count);
        isPredictingRef.current = true;

        const sendPrediction = async () => {
          try {
            const formData = new FormData();
            const wavBlob = samplesToWavBlob(samples, audioContext.sampleRate);
            console.log('sampleRate', audioContext.sampleRate);
            console.log('wav size', wavBlob.size);
            console.log('wav type', wavBlob.type);
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

            if (
              DANGER_LABELS.has(prediction.prediction) &&
              prediction.confidence >= CONFIDENCE_THRESHOLD
            ) {
              const now = Date.now();
              const lastAlert = lastAlertRef.current;
              const isDuplicate =
                lastAlert &&
                lastAlert.label === prediction.prediction &&
                now - lastAlert.timestamp < DUPLICATE_ALERT_MS;

              if (!isDuplicate) {
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

                window.dispatchEvent(
                  new CustomEvent('danger-detected', {
                    detail: payload,
                  }),
                );

                if (mountedRef.current) {
                  onDangerDetected?.(payload);
                }
              }
            }
          } catch (err) {
            const message = err instanceof Error ? err.message : 'Prediction failed';
            setError(message);
          } finally {
            isPredictingRef.current = false;
          }
        };

        void sendPrediction();
      };

      intervalRef.current = window.setInterval(processChunk, 1000);
      setIsRecording(true);
      setIsMonitoring(true);
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
