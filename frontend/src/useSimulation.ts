import { useEffect, useRef, useState } from 'react'
import type { LabEvent, Snapshot } from './types'

export function useSimulation() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [events, setEvents] = useState<LabEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const epoch = useRef('')
  const lastCollection = useRef(0)
  useEffect(() => {
    let disposed = false
    let socket: WebSocket | undefined
    let retry: ReturnType<typeof setTimeout>
    function connect() {
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/events`)
      socket.onopen = () => setConnected(true)
      socket.onmessage = ({ data }) => {
        const incoming = JSON.parse(data) as Snapshot
        if (incoming.epoch !== epoch.current) {
          epoch.current = incoming.epoch
          lastCollection.current = 0
          setEvents([])
        }
        const fresh = (incoming.events ?? []).filter(e => e.collection_id > lastCollection.current)
        if (fresh.length) {
          lastCollection.current = fresh[fresh.length - 1].collection_id
          setEvents(old => [...old, ...fresh].slice(-1500))
        }
        setSnapshot(incoming)
      }
      socket.onclose = () => {
        if (disposed) return
        setConnected(false)
        retry = setTimeout(connect, 1500)
      }
      socket.onerror = () => socket?.close()
    }
    connect()
    return () => { disposed = true; clearTimeout(retry); socket?.close() }
  }, [])

  async function call(path: string, body?: object) {
    const response = await fetch(`/api/${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Tham số không hợp lệ.')
    }
    return response.json()
  }
  async function action(operation: () => Promise<unknown>) {
    setBusy(true); setError('')
    try { await operation() } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }
  return { snapshot, events, connected, error, busy, call, action, clear: () => setEvents([]), dismiss: () => setError('') }
}
