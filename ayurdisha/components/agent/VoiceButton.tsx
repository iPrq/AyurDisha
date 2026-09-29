"use client";

import { useEffect, useRef, useState } from "react";
import { concatChunks, downsample, encodeWav } from "@/lib/agent/wav";
import { languageApi } from "@/lib/formulation/api";

export type VoiceState = "idle" | "listening" | "transcribing" | "error";

const MAX_SECONDS = 30;

/**
 * Records speech, encodes 16 kHz WAV and sends it to the server-side ASR.
 * Disabled (with the reason shown) when the backend reports no ASR capability.
 */
export function VoiceButton({
  language,
  asrAvailable,
  unavailableReason,
  onTranscript,
  disabled,
}: {
  language: string;
  asrAvailable: boolean;
  unavailableReason: string;
  onTranscript: (text: string, detectedLanguage: string) => void;
  disabled?: boolean;
}) {
  const [state, setState] = useState<VoiceState>("idle");
  const [error, setError] = useState<string | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const nodeRef = useRef<ScriptProcessorNode | null>(null);
  const chunksRef = useRef<Float32Array[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => cleanup(), []);

  function cleanup() {
    if (timerRef.current) clearTimeout(timerRef.current);
    nodeRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    void ctxRef.current?.close();
    nodeRef.current = null;
    streamRef.current = null;
    ctxRef.current = null;
  }

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const node = ctx.createScriptProcessor(4096, 1, 1);
      chunksRef.current = [];
      node.onaudioprocess = (e) => chunksRef.current.push(new Float32Array(e.inputBuffer.getChannelData(0)));
      source.connect(node);
      node.connect(ctx.destination);
      ctxRef.current = ctx;
      streamRef.current = stream;
      nodeRef.current = node;
      setState("listening");
      timerRef.current = setTimeout(() => void stop(), MAX_SECONDS * 1000);
    } catch {
      setError("Microphone permission was denied.");
      setState("error");
    }
  }

  async function stop() {
    const ctx = ctxRef.current;
    if (!ctx) return;
    const rate = ctx.sampleRate;
    const samples = downsample(concatChunks(chunksRef.current), rate, 16000);
    cleanup();
    if (samples.length < 16000 * 0.4) {
      setState("idle");
      setError("That was too short — hold the mic a little longer.");
      return;
    }
    setState("transcribing");
    try {
      const res = await languageApi.transcribe(encodeWav(samples, 16000), language);
      setState("idle");
      if (!res.text.trim()) {
        setError("No speech was recognised.");
        return;
      }
      onTranscript(res.text, res.detected?.language ?? res.language);
    } catch (e) {
      setState("error");
      setError(e instanceof Error ? e.message : "Transcription failed.");
    }
  }

  const title = !asrAvailable
    ? unavailableReason
    : state === "listening"
      ? "Stop and transcribe"
      : "Speak your request";

  return (
    <div className="relative">
      <button
        type="button"
        disabled={!asrAvailable || disabled || state === "transcribing"}
        onClick={() => (state === "listening" ? void stop() : void start())}
        title={title}
        aria-label={title}
        aria-pressed={state === "listening"}
        className={`flex h-8 w-8 items-center justify-center rounded-full border text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
          state === "listening"
            ? "border-red-500 bg-red-50 text-red-600 dark:bg-red-950"
            : "border-neutral-300 text-neutral-600 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
        }`}
      >
        {state === "transcribing" ? (
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-neutral-400 border-t-transparent" />
        ) : (
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="9" y="3" width="6" height="12" rx="3" />
            <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
          </svg>
        )}
      </button>
      {(state === "listening" || state === "transcribing") && (
        <span className="absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] font-medium text-red-600">
          {state === "listening" ? "Listening…" : "Transcribing…"}
        </span>
      )}
      {error && (
        <span role="alert" className="absolute bottom-10 right-0 w-52 rounded bg-neutral-900 px-2 py-1 text-[11px] text-white">
          {error}
        </span>
      )}
    </div>
  );
}
