import { useSyncExternalStore } from 'react'

import type { Signal } from './feed-types'

let signals: Signal[] = []
const listeners = new Set<() => void>()

function notify(): void {
  for (const listener of listeners) listener()
}

export function getSignals(): Signal[] {
  return signals
}

export function addSignal(signal: Signal): void {
  signals = [signal, ...signals]
  notify()
}

export function updateSignal(
  id: string,
  update: (signal: Signal) => Signal,
): void {
  signals = signals.map((signal) => (signal.id === id ? update(signal) : signal))
  notify()
}

export function removeSignal(id: string): void {
  signals = signals.filter((signal) => signal.id !== id)
  notify()
}

function subscribeSignals(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useSignals(): Signal[] {
  return useSyncExternalStore(subscribeSignals, getSignals, getSignals)
}

export type NewSignalInput = Pick<
  Signal,
  'category' | 'title' | 'entity' | 'summary'
> &
  Partial<
    Pick<
      Signal,
      | 'body'
      | 'subject'
      | 'sender'
      | 'sourceUrl'
      | 'reason'
      | 'actions'
      | 'hot'
      | 'pinned'
    >
  >

export function emitSignal(input: NewSignalInput): Signal {
  const signal: Signal = {
    id: `sig-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    read: false,
    pinned: false,
    hot: false,
    timestamp: Date.now(),
    actions: [],
    reason: '',
    ...input,
  }
  addSignal(signal)
  return signal
}