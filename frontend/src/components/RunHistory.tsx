import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { runApi } from '../hooks/useApi'
import { Icons } from './Layout'
import type { RunSummary } from '../types/api'

export function RunHistory() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    runApi.list().then(setRuns).finally(() => setLoading(false))
  }, [])

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
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Run History</h1>
      </header>

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
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Run ID</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Container</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Type</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Cartons</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Placed</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Fill Rate</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Status</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Created</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.run_id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-sm text-slate-700">{run.run_id.slice(0, 8)}...</td>
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