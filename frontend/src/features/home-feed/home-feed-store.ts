import { useSyncExternalStore } from 'react'

import type { HomeSignal } from './home-feed-types'

let signals: HomeSignal[] = []
const listeners = new Set<() => void>()

function notify(): void {
  for (const listener of listeners) listener()
}

export function getHomeSignals(): HomeSignal[] {
  return signals
}

export function updateHomeSignal(
  id: string,
  update: (signal: HomeSignal) => HomeSignal,
): void {
  signals = signals.map((signal) => (signal.id === id ? update(signal) : signal))
  notify()
}

export function removeHomeSignal(id: string): void {
  signals = signals.filter((signal) => signal.id !== id)
  notify()
}

function subscribeHomeSignals(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useHomeSignals(): HomeSignal[] {
  return useSyncExternalStore(subscribeHomeSignals, getHomeSignals, getHomeSignals)
}
