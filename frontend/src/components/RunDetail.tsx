import { useEffect, useState } from 'react'
import { useParams, useNavigate, NavLink } from 'react-router-dom'
import { runApi } from '../hooks/useApi'
import { LoadingPlanViewer } from './LoadingPlanViewer'
import { Icons } from './Layout'
import type { RunResult } from '../types/api'

export function RunDetail() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [result, setResult] = useState<RunResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchRun = async (id: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await runApi.get(id)
      setResult(data)
    } catch (err: any) {
      console.error('Failed to fetch run result', err)
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err.message || 'Failed to load loading plan')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (runId) {
      fetchRun(runId)
    } else {
      setError('No Run ID provided')
      setLoading(false)
    }
  }, [runId])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-80 space-y-4">
        <div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
        <p className="text-slate-500 text-sm">Loading plan details for {runId?.slice(0, 8)}...</p>
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <NavLink to="/history" className="btn btn-outline btn-sm flex items-center gap-1.5">
            <Icons.ChevronLeft /> Back to Run History
          </NavLink>
        </div>

        <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-700 space-y-3">
          <div className="flex items-center gap-2 font-semibold">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>Error Loading Run Result</span>
          </div>
          <p className="text-sm">{error || 'Run details could not be found.'}</p>
          <div className="pt-2">
            <button onClick={() => runId && fetchRun(runId)} className="btn btn-secondary btn-sm">
              Retry
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (result.status === 'running') {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <NavLink to="/history" className="btn btn-outline btn-sm flex items-center gap-1.5">
            <Icons.ChevronLeft /> Back to Run History
          </NavLink>
        </div>

        <div className="p-8 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 space-y-4 text-center">
          <div className="w-12 h-12 border-4 border-amber-300 border-t-amber-600 rounded-full animate-spin mx-auto" />
          <h2 className="text-lg font-semibold">Optimization In Progress</h2>
          <p className="text-sm text-amber-700 max-w-md mx-auto">
            This loading plan run is currently being calculated by the solver. Check back shortly.
          </p>
          <div className="flex justify-center gap-3">
            <button onClick={() => runId && fetchRun(runId)} className="btn btn-primary btn-sm">
              Refresh Status
            </button>
            <NavLink to="/history" className="btn btn-outline btn-sm">
              View History
            </NavLink>
          </div>
        </div>
      </div>
    )
  }

  if (result.status === 'failed') {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <NavLink to="/history" className="btn btn-outline btn-sm flex items-center gap-1.5">
            <Icons.ChevronLeft /> Back to Run History
          </NavLink>
        </div>

        <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-800 space-y-4">
          <div className="flex items-center gap-2 font-semibold text-lg">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-red-600">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="15" y1="9" x2="9" y2="15"></line>
              <line x1="9" y1="9" x2="15" y2="15"></line>
            </svg>
            <span>Optimization Run Failed</span>
          </div>
          <p className="text-sm text-red-700">
            {result.error_message || 'The solver encountered an error while processing this run.'}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-white p-3 rounded-lg border border-red-100 text-xs">
            <div>
              <span className="text-slate-500 block">Run ID</span>
              <span className="font-mono font-medium">{result.run_id.slice(0, 8)}...</span>
            </div>
            <div>
              <span className="text-slate-500 block">Container</span>
              <span className="font-medium">{result.container?.container_type || '—'}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Created</span>
              <span className="font-medium">{new Date(result.created_at).toLocaleTimeString()}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Status</span>
              <span className="font-semibold text-red-600 uppercase">{result.status}</span>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <NavLink to="/new-run" className="btn btn-primary btn-sm flex items-center gap-1.5">
              <Icons.Play /> Create New Run
            </NavLink>
            <NavLink to="/history" className="btn btn-outline btn-sm">
              Back to History
            </NavLink>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3 pb-2 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <NavLink to="/history" className="btn btn-outline btn-sm flex items-center gap-1.5">
            <Icons.ChevronLeft /> Back to History
          </NavLink>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded">
              Run: {result.run_id}
            </span>
            <span className="text-xs text-slate-500">
              {new Date(result.created_at).toLocaleString()}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <NavLink to="/new-run" className="btn btn-primary btn-sm flex items-center gap-1.5">
            <Icons.Play /> New Run
          </NavLink>
        </div>
      </div>

      <LoadingPlanViewer
        result={result}
        onNewRun={() => navigate('/new-run')}
      />
    </div>
  )
}
