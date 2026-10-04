import { useState } from 'react';
import type { Pin } from './schematic-types';

export interface RemoteObservation {
  id: string; document: string; revision: string; pins: Pin[]; time: number | null; frequency: number | null;
}

/** A request stays pending until a mounted observation session actually applies it. */
export function useRemoteObservation() {
  const [remoteView, setRemoteView] = useState<RemoteObservation | null>(null);
  return { remoteView, receiveView: setRemoteView };
}
