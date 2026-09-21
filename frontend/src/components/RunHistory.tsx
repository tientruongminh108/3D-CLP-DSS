import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { runApi } from '../hooks/useApi'
import { Icons } from './Layout'
import { useToastStore } from './Toast'
import type { RunSummary } from '../types/api'

export function RunHistory() {
  const navigate = useNavigate()
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deleting, setDeleting] = useState(false)
  const { success: toastSuccess, error: toastError } = useToastStore()

  const loadRuns = async () => {
    try {
      const data = await runApi.list()
      setRuns(data)
    } catch (err) {
      console.error('Failed to load runs', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRuns()
  }, [])

  const selectableRuns = runs.filter((r) => r.status !== 'running')
  const allSelectableSelected = selectableRuns.length > 0 && selectableRuns.every((r) => selectedIds.has(r.run_id))
  const someSelectableSelected = selectableRuns.some((r) => selectedIds.has(r.run_id)) && !allSelectableSelected

  const handleToggleSelect = (runId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(runId)) {
        next.delete(runId)
      } else {
        next.add(runId)
      }
      return next
    })
  }

  const handleSelectAll = () => {
    if (allSelectableSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(selectableRuns.map((r) => r.run_id)))
    }
  }

  const handleDelete = async (runId: string) => {
    const shortId = runId.slice(0, 8)
    if (!window.confirm(`Delete run ${shortId}...?`)) return
    try {
      setDeleting(true)
      await runApi.delete(runId)
      toastSuccess(`Deleted run ${shortId}...`)
      setSelectedIds((prev) => {
        if (prev.has(runId)) {
          const next = new Set(prev)
          next.delete(runId)
          return next
        }
        return prev
      })
      setRuns((prev) => prev.filter((r) => r.run_id !== runId))
    } catch (err: any) {
      toastError(err.response?.data?.detail || 'Failed to delete run')
    } finally {
      setDeleting(false)
    }
  }

  const handleBulkDelete = async () => {
    const count = selectedIds.size
    if (count === 0) return
    if (!window.confirm(`Delete ${count} selected run${count > 1 ? 's' : ''}?`)) return

    try {
      setDeleting(true)
      const idsToDelete = Array.from(selectedIds)
      const results = await Promise.allSettled(idsToDelete.map((id) => runApi.delete(id)))

      const succeededIds = new Set<string>()
      let failedCount = 0

      results.forEach((res, index) => {
        if (res.status === 'fulfilled') {
          succeededIds.add(idsToDelete[index])
        } else {
          failedCount++
        }
      })

      const succeededCount = succeededIds.size
      if (failedCount === 0) {
        toastSuccess(`Successfully deleted ${succeededCount} run${succeededCount > 1 ? 's' : ''}`)
      } else if (succeededCount > 0) {
        toastError(`${succeededCount} run${succeededCount > 1 ? 's' : ''} deleted, ${failedCount} failed`)
      } else {
        toastError('Failed to delete selected runs')
      }

      setRuns((prev) => prev.filter((r) => !succeededIds.has(r.run_id)))
      setSelectedIds(new Set())
    } catch (err: any) {
      toastError('Failed to delete selected runs')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center text-slate-500">
          Loading...
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Run History</h1>
          <p className="text-sm text-slate-500 mt-1">
            Review past loading plans, container fill rates, and execution status
          </p>
        </div>
        <div>
          <NavLink to="/new-run" className="btn btn-primary flex items-center gap-2">
            <Icons.Play /> Create New Run
          </NavLink>
        </div>
      </header>

      {selectedIds.size > 0 && (
        <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-950">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-blue-800">{selectedIds.size}</span>
            <span className="text-slate-700">run{selectedIds.size > 1 ? 's' : ''} selected</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={deleting}
              className="btn btn-ghost btn-sm text-slate-600 hover:text-slate-900"
              onClick={() => setSelectedIds(new Set())}
            >
              Clear Selection
            </button>
            <button
              type="button"
              disabled={deleting}
              className="btn btn-sm bg-red-600 hover:bg-red-700 text-white border-none flex items-center gap-1.5 font-medium shadow-sm disabled:opacity-50"
              onClick={handleBulkDelete}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              {deleting ? 'Deleting...' : `Delete Selected (${selectedIds.size})`}
            </button>
          </div>
        </div>
      )}

      {runs.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 bg-white border border-slate-200 rounded-xl">
          <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4 text-slate-400">
            <Icons.Clock />
          </div>
          <h2 className="text-lg font-medium text-slate-900 mb-2">No Runs Yet</h2>
          <p className="text-slate-500 mb-6 text-center max-w-md">
            You haven't created any loading plans yet. Get started by creating your first run.
          </p>
          <NavLink to="/new-run" className="btn btn-primary flex items-center gap-2">
            <Icons.Play /> Create New Run
          </NavLink>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50">
                  <th className="px-4 py-3 text-center w-10">
                    <input
                      type="checkbox"
                      className="rounded border-slate-300 text-blue-600 cursor-pointer disabled:opacity-40"
                      checked={allSelectableSelected}
                      disabled={selectableRuns.length === 0}
                      ref={(el) => {
                        if (el) el.indeterminate = someSelectableSelected
                      }}
                      onChange={handleSelectAll}
                      aria-label="Select all completed runs"
                    />
                  </th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Run ID</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Container</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Type</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Cartons</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Placed</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Fill Rate</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Status</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Created</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-600 uppercase tracking-wider text-xs">Action</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.run_id}
                    onClick={() => navigate(`/history/${run.run_id}`)}
                    className={`border-t border-slate-100 hover:bg-blue-50/40 cursor-pointer transition-colors ${
                      selectedIds.has(run.run_id) ? 'bg-blue-50/30' : ''
                    }`}
                  >
                    <td className="px-4 py-3 text-center w-10" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        className="rounded border-slate-300 text-blue-600 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                        disabled={run.status === 'running'}
                        title={run.status === 'running' ? 'Cannot delete an active run' : `Select run ${run.run_id.slice(0, 8)}`}
                        checked={selectedIds.has(run.run_id)}
                        onChange={() => handleToggleSelect(run.run_id)}
                        aria-label={`Select run ${run.run_id}`}
                      />
                    </td>
                    <td className="px-4 py-3 font-mono text-sm font-medium text-blue-600">{run.run_id.slice(0, 8)}...</td>
                    <td className="px-4 py-3 text-slate-700">{run.container_type}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        run.shipment_type === 'FCL' 
                          ? 'bg-green-100 text-green-700' 
                          : 'bg-amber-100 text-amber-700'
                      }`}>
                        {run.shipment_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{run.total_cartons}</td>
                    <td className="px-4 py-3 text-slate-700">{run.placed_count}</td>
                    <td className="px-4 py-3 text-slate-700">{(run.fill_rate * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        run.status === 'completed' ? 'bg-green-100 text-green-700' :
                        run.status === 'running' ? 'bg-amber-100 text-amber-700' :
                        run.status === 'failed' ? 'bg-red-100 text-red-700' :
                        'bg-slate-100 text-slate-700'
                      }`}>
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{new Date(run.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="inline-flex items-center justify-end gap-2">
                        <NavLink
                          to={`/history/${run.run_id}`}
                          className="btn btn-outline btn-xs inline-flex items-center gap-1 font-medium text-blue-600 hover:bg-blue-600 hover:text-white"
                        >
                          View Plan &rarr;
                        </NavLink>
                        <button
                          type="button"
                          disabled={run.status === 'running' || deleting}
                          title={run.status === 'running' ? 'Cannot delete an active run' : 'Delete run'}
                          onClick={() => handleDelete(run.run_id)}
                          className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-slate-400 disabled:cursor-not-allowed"
                          aria-label={`Delete run ${run.run_id}`}
                        >
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}