import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { runApi } from '../hooks/useApi'
import { Icons } from './Layout'
import type { RunSummary } from '../types/api'
import { parsePackingListFile } from '../utils/fileUpload'
import { useToastStore } from './Toast'

export function Dashboard() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { success: toastSuccess, error: toastError } = useToastStore()
  const [stats, setStats] = useState({
    totalRunsToday: 0,
    avgFillRate: 0,
    totalVolumePlanned: 0,
    pendingPackingLists: 0,
  })
  const [recentRuns, setRecentRuns] = useState<RunSummary[]>([])
  const [loading, setLoading] = useState(true)

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const loadDashboardData = async () => {
    try {
      const runs = await runApi.list(0, 10)
      setRecentRuns(runs)

      const today = new Date().toDateString()
      const todayRuns = runs.filter(r => new Date(r.created_at).toDateString() === today)
      const completedRuns = runs.filter(r => r.status === 'completed')
      
      setStats({
        totalRunsToday: todayRuns.length,
        avgFillRate: completedRuns.length > 0 
          ? Math.round(completedRuns.reduce((sum, r) => sum + r.fill_rate, 0) / completedRuns.length * 100) / 100
          : 0,
        totalVolumePlanned: completedRuns.reduce((sum, r) => sum + (r.total_cartons * 0.15), 0),
        pendingPackingLists: runs.filter(r => r.status === 'pending').length,
      })
    } catch (e) {
      console.error('Failed to load dashboard data', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboardData()
  }, [])

  const handleFileUpload = async (file: File | undefined) => {
    if (!file) return

    const result = await parsePackingListFile(file)

    if (result.success && result.data) {
      toastSuccess(`Successfully loaded ${result.data.preview.total_cartons} cartons (${result.data.preview.rows.length} items) from CSV`)
    } else {
      toastError(result.error || 'Failed to parse file')
    }
    // Reset file input to allow re-uploading same file
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const triggerFileInput = () => {
    fileInputRef.current?.click()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center text-slate-500">
          Loading dashboard...
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard Overview</h1>
          <p className="text-slate-500 mt-1">
            Welcome back. Here's a summary of your loading plans.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
          <NavLink to="/new-run" className="btn btn-primary flex items-center justify-center gap-2">
            <Icons.Play /> Create New Plan
          </NavLink>
          <button
            type="button"
            className="btn btn-secondary flex items-center justify-center gap-2"
            onClick={triggerFileInput}
          >
            <Icons.FileText /> Import CSV
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.json"
            className="hidden"
            style={{ display: 'none' }}
            onChange={(e) => handleFileUpload(e.target.files?.[0])}
          />
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-5 h-full">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Total Runs Today</div>
          <div className="text-3xl font-bold text-slate-900">{stats.totalRunsToday}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-5 h-full">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Avg. Fill Rate</div>
          <div className="text-3xl font-bold text-green-700">{(stats.avgFillRate * 100).toFixed(1)}%</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-5 h-full">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Total Volume Planned</div>
          <div className="text-3xl font-bold text-slate-900">{stats.totalVolumePlanned.toFixed(1)}<span className="text-base font-normal text-slate-500"> CBM</span></div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-5 h-full">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Pending Packing Lists</div>
          <div className="text-3xl font-bold text-slate-900">{stats.pendingPackingLists}</div>
        </div>
      </div>

      <div className="w-full mt-6">
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-medium text-slate-900">Recent Runs</h2>
            <NavLink to="/history" className="btn btn-ghost btn-sm flex items-center gap-2">
              View All
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </NavLink>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50">
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Run ID</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Date</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Container</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Type</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Cartons</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Fill Rate</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Status</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-12 text-center text-slate-500">
                      No runs yet. <NavLink to="/new-run" className="text-blue-600 hover:underline">Create your first run</NavLink>
                    </td>
                  </tr>
                ) : (
                  recentRuns.map((run) => (
                    <tr key={run.run_id} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono text-sm text-slate-700">{run.run_id.slice(0, 8)}...</td>
                      <td className="px-4 py-3 text-slate-600">{formatDate(run.created_at)}</td>
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
                      <td className="px-4 py-3 text-slate-700">{(run.fill_rate * 100).toFixed(1)}%</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          run.status === 'completed' ? 'bg-green-100 text-green-700' :
                          run.status === 'running' ? 'bg-amber-100 text-amber-700' :
                          'bg-slate-100 text-slate-700'
                        }`}>
                          {run.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}