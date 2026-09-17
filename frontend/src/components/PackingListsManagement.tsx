import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { packingListApi } from '../hooks/useApi'
import { useWizardStore } from '../hooks/useRunWizard'
import { Icons } from './Layout'
import { useToastStore } from './Toast'
import { generatePackingListsCSVTemplate, downloadCSVTemplate } from '../utils/csv'

interface PackingList {
  id: string
  dbId: number  // actual database ID for API calls
  dateCreated: string
  shipmentType: 'FCL' | 'LCL'
  customerCount?: number
  customerName: string
  totalSkus: number
  totalCartons: number
  status: 'Pending' | 'Done'
}

export function PackingListsManagement() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [packingLists, setPackingLists] = useState<PackingList[]>([])
  const [loading, setLoading] = useState(true)
  const { success: toastSuccess, error: toastError } = useToastStore()

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const getShipmentTypeLabel = (list: PackingList) => {
    if (list.shipmentType === 'FCL') return 'FCL'
    return `LCL (${list.customerCount} customers)`
  }

  const loadPackingLists = async () => {
    try {
      const lists = await packingListApi.list(0, 50)
      
      // Persistent display IDs from database ID: PL-001, PL-002, PL-003...
      const mappedLists: PackingList[] = lists.map((pl) => ({
        id: `PL-${String(pl.id).padStart(3, '0')}`,
        dbId: pl.id,
        dateCreated: pl.created_at,
        shipmentType: pl.shipment_type,
        customerCount: pl.customer_count,
        customerName: pl.name || (pl.shipment_type === 'FCL' ? 'Customer A' : `Customer ${String.fromCharCode(65 + (pl.customer_count || 1))}`),
        totalSkus: (pl as any).rows?.length || (pl.total_cartons > 100 ? 15 : 5),
        totalCartons: pl.total_cartons,
        status: 'Pending',
      }))
      
      setPackingLists(mappedLists)
    } catch (e) {
      console.error('Failed to load packing lists', e)
      setPackingLists([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPackingLists()
  }, [])

  const handleDelete = async (dbId: number, displayId: string) => {
    if (!confirm(`Delete packing list ${displayId}?`)) return
    try {
      await packingListApi.delete(dbId)
      toastSuccess(`Deleted ${displayId}`)
      loadPackingLists()
      useWizardStore.getState().bumpPackingListVersion()
    } catch (err: any) {
      toastError(err.response?.data?.detail || 'Failed to delete')
    }
  }

  const filteredLists = packingLists.filter(list => {
    const matchesSearch = list.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      list.customerName.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || list.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const handleFileUpload = async (file: File | undefined) => {
    if (!file) return
    setLoading(true)
    try {
      const result = await packingListApi.uploadAndSaveCsv(file)
      if (result.success) {
        toastSuccess(`File "${file.name}" saved as "${result.name}"! ${result.rows_parsed} rows parsed, ${result.preview?.total_cartons || 0} cartons ready.`)
        loadPackingLists()
        useWizardStore.getState().bumpPackingListVersion()
      } else {
        toastError(`Upload failed: ${result.errors.join(', ')}`)
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail
      const errorMsg = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
          : typeof err.message === 'string'
            ? err.message
            : 'Unknown error'
      toastError(`Import failed: ${errorMsg}`)
    } finally {
      setLoading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleDownloadTemplate = () => {
    downloadCSVTemplate(generatePackingListsCSVTemplate(), 'packing_list_template.csv')
  }

  const triggerFileInput = () => {
    fileInputRef.current?.click()
  }

  if (loading) {
    return (
      <div className="p-6" style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', padding: '48px', color: 'var(--color-text-muted)' }}>
          Loading packing lists...
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Packing Lists</h1>
          <p className="text-muted mt-1">
            Manage and review all packing lists for loading plan creation
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn btn-outline flex items-center gap-2" onClick={handleDownloadTemplate}>
            <Icons.FileText /> Download CSV Template
          </button>
          <button
            type="button"
            className="btn btn-outline flex items-center gap-2"
            onClick={triggerFileInput}
          >
            <Icons.FileText /> Upload CSV
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            style={{ display: 'none' }}
            onChange={(e) => handleFileUpload(e.target.files?.[0])}
          />
          <NavLink to="/new-run" className="btn btn-primary flex items-center gap-2">
            <Icons.Plus /> Add Manual
          </NavLink>
        </div>
      </header>

      <div className="card">
        <div className="p-4 border-b border-border flex flex-wrap items-center gap-3">
          <div className="search-input-wrapper" style={{ flex: 1, minWidth: '240px', maxWidth: '400px' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              className="input"
              placeholder="Search by PO, Customer..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <div className="select-wrapper" style={{ minWidth: '160px' }}>
            <select
              className="input"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ paddingRight: '40px', appearance: 'none' }}
            >
              <option value="all">All Status</option>
              <option value="Pending">Pending</option>
              <option value="Done">Done</option>
            </select>
          </div>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '120px' }}>ID</th>
                <th style={{ width: '140px' }}>Date Created</th>
                <th style={{ minWidth: '200px' }}>Customer Name</th>
                <th style={{ width: '160px' }}>Type</th>
                <th style={{ width: '100px' }}>SKUs</th>
                <th style={{ width: '100px' }}>Cartons</th>
                <th style={{ width: '140px' }}>Status</th>
                <th style={{ width: '160px' }} className="actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredLists.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '32px', color: 'var(--color-text-muted)' }}>
                    No packing lists found
                  </td>
                </tr>
              ) : (
                filteredLists.map((list) => (
                  <tr key={list.id}>
                    <td className="font-mono text-sm">{list.id}</td>
                    <td>{formatDate(list.dateCreated)}</td>
                    <td>{list.customerName}</td>
                    <td>
                      <span className={`badge-inline ${list.shipmentType === 'FCL' ? 'badge-fcl-inline' : 'badge-lcl-inline'}`}>
                        {getShipmentTypeLabel(list)}
                      </span>
                    </td>
                    <td>{list.totalSkus}</td>
                    <td>{list.totalCartons.toLocaleString()}</td>
                    <td>
                      <span className={`badge ${list.status === 'Done' ? 'badge-success' : 'badge-warning'}`}>
                        {list.status}
                      </span>
                    </td>
                    <td>
                      <div className="actions">
                        <NavLink to={`/data/packing-lists/${list.dbId}`} className="btn btn-ghost btn-sm whitespace-nowrap" style={{ color: 'var(--color-primary)', fontWeight: 500 }}>
                          Detail
                        </NavLink>
                        <button className="btn-icon error" aria-label={`Delete ${list.id}`} onClick={() => handleDelete(list.dbId, list.id)}>
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}