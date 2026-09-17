import { useCallback, useEffect, useRef } from 'react'
import type { RunProgress } from '../types/ui'

interface UseWebSocketOptions {
  runId: string | null
  onProgress: (progress: RunProgress) => void
  onComplete: (result: unknown) => void
  onError: (error: string) => void
}

export function useWebSocket({ runId, onProgress, onComplete, onError }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const mountedRef = useRef(false)
  const runIdRef = useRef<string | null>(runId)
  const connectRef = useRef<() => void>(() => undefined)
  const onProgressRef = useRef(onProgress)
  const onCompleteRef = useRef(onComplete)
  const onErrorRef = useRef(onError)

  onProgressRef.current = onProgress
  onCompleteRef.current = onComplete
  onErrorRef.current = onError

  const closeSocket = useCallback((socket: WebSocket | null) => {
    if (!socket) return
    socket.onopen = null
    socket.onmessage = null
    socket.onclose = null
    socket.onerror = null
    if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
      socket.close()
    }
  }, [])

  const connect = useCallback(() => {
    const currentRunId = runIdRef.current
    if (!mountedRef.current || !currentRunId || typeof WebSocket === 'undefined') return

    const existingSocket = wsRef.current
    if (existingSocket && (existingSocket.readyState === WebSocket.OPEN || existingSocket.readyState === WebSocket.CONNECTING)) return

    closeSocket(existingSocket)
    wsRef.current = null

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${protocol}//${window.location.host}/api/runs/${encodeURIComponent(currentRunId)}/ws`)
    wsRef.current = socket

    socket.onopen = () => {
      reconnectAttemptsRef.current = 0
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as {
          type?: string
          payload?: unknown
        }
        if (data.type === 'progress') {
          onProgressRef.current(data.payload as RunProgress)
        } else if (data.type === 'complete') {
          onCompleteRef.current(data.payload)
        } else if (data.type === 'error') {
          onErrorRef.current(data.payload instanceof Error ? data.payload.message : String(data.payload ?? 'WebSocket error'))
        }
      } catch (error) {
        onErrorRef.current(error instanceof Error ? `Invalid WebSocket message: ${error.message}` : 'Invalid WebSocket message')
      }
    }

    socket.onclose = () => {
      if (wsRef.current === socket) wsRef.current = null
      if (!mountedRef.current || runIdRef.current !== currentRunId) return

      const attempts = reconnectAttemptsRef.current
      if (attempts >= 5) {
        onErrorRef.current('Unable to maintain the run status connection')
        return
      }

      reconnectAttemptsRef.current = attempts + 1
      reconnectTimeoutRef.current = setTimeout(() => connectRef.current(), 1000 * (attempts + 1))
    }

    socket.onerror = () => {
      onErrorRef.current('Unable to connect to the run status service')
    }
  }, [closeSocket])

  connectRef.current = connect

  useEffect(() => {
    mountedRef.current = true
    runIdRef.current = runId

    if (runId) connect()

    return () => {
      mountedRef.current = false
      runIdRef.current = null
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      closeSocket(wsRef.current)
      wsRef.current = null
    }
  }, [connect, runId, closeSocket])

  const send = useCallback((message: unknown) => {
    const socket = wsRef.current
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message))
      return true
    }
    return false
  }, [])

  return { send }
}
