import { useEffect, useState } from 'react'
import { useParams, NavLink } from 'react-router-dom'
import { packingListApi } from '../hooks/useApi'
import { Icons } from './Layout'
import type { PackingList } from '../types/api'

export function PackingListDetail() {
  const { id } = useParams<{ id: string }>()
  const [packingList, setPackingList] = useState<PackingList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  const formatNumber = (num: number) => {
    return num.toLocaleString()
  }

  useEffect(() => {
    if (!id) return
    
    // Parse numeric ID from e.g. "PL-001" or "1"
    const numericId = parseInt(id.replace(/^PL-/i, ''), 10)
    
    if (isNaN(numericId) || numericId <= 0) {
      setError('Invalid packing list ID')
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    packingListApi.get(numericId)
      .then((data) => {
        setPackingList(data)
      })
      .catch((err: any) => {
        const detail = err.response?.data?.detail
        const msg = typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
            : err.message || 'Failed to load packing list details'
        setError(msg)
      })
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="p-6" style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', padding: '48px', color: 'var(--color-text-muted)' }}>
          Loading packing list details...
        </div>
      </div>
    )
  }

  if (error || !packingList) {
    return (
      <div className="p-6" style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <h2 style={{ color: 'var(--color-error-text)', marginBottom: '8px' }}>Not Found</h2>
          <p style={{ color: 'var(--color-text-muted)' }}>{error || 'Packing list not found or failed to load.'}</p>
          <NavLink to="/data/packing-lists" className="btn btn-primary" style={{ marginTop: '16px', display: 'inline-flex' }}>
            <Icons.ChevronRight /> Back to Packing Lists
          </NavLink>
        </div>
      </div>
    )
  }

  const displayId = `PL-${String(packingList.id).padStart(3, '0')}`
  const estVolumeCbm = (packingList.total_volume_cm3 || 0) / 1e6

  return (
    <div>
      <header className="mt-2 mb-6 flex items-start justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <NavLink to="/data/packing-lists" className="btn btn-ghost p-2" title="Back to packing lists">
            <Icons.ChevronRight />
          </NavLink>
          <div>
            <h1 className="text-2xl font-bold">{displayId} &ndash; {packingList.name || 'Packing List'}</h1>
            <p className="text-muted mt-1">
              {packingList.shipment_type} &bull; {formatNumber(packingList.total_cartons)} cartons &bull; {packingList.rows?.length || 0} line items
            </p>
          </div>
        </div>

        <NavLink to="/new-run" className="btn btn-primary btn-lg flex items-center gap-2">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
          </svg>
          CREATE 3D PLAN NOW
        </NavLink>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4 mb-6">
        <div className="stat-card">
          <div className="stat-label">Packing List ID</div>
          <div className="stat-value" style={{ fontSize: '18px', fontFamily: 'var(--font-mono)' }}>{displayId}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Created Date</div>
          <div className="stat-value" style={{ fontSize: '15px' }}>{formatDate(packingList.created_at)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Cartons</div>
          <div className="stat-value">{formatNumber(packingList.total_cartons)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Weight</div>
          <div className="stat-value">{formatNumber(packingList.total_weight_kg)}<span className="stat-unit"> kg</span></div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Est. Volume</div>
          <div className="stat-value">{estVolumeCbm.toFixed(1)}<span className="stat-unit"> CBM</span></div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Shipment Type</div>
          <div className="stat-value stat-value-success">{packingList.shipment_type}</div>
        </div>
      </div>

      <div className="card">
        <div className="p-4 border-b border-border flex justify-between items-center">
          <h2 className="text-base font-medium">Packing List Items ({packingList.rows?.length || 0} rows)</h2>
          {packingList.filename && (
            <span className="text-xs text-muted font-mono">Source: {packingList.filename}</span>
          )}
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '160px' }}>Item ID / SKU</th>
                <th style={{ minWidth: '220px' }}>Description</th>
                <th style={{ width: '140px' }}>PO Number</th>
                {packingList.shipment_type === 'LCL' && (
                  <th style={{ width: '140px' }}>Customer Code</th>
                )}
                <th style={{ width: '120px', textAlign: 'right' }}>Cartons</th>
                <th style={{ width: '120px', textAlign: 'right' }}>Pcs</th>
              </tr>
            </thead>
            <tbody>
              {!packingList.rows || packingList.rows.length === 0 ? (
                <tr>
                  <td colSpan={packingList.shipment_type === 'LCL' ? 6 : 5} style={{ textAlign: 'center', padding: '48px', color: 'var(--color-text-muted)' }}>
                    No rows found in this packing list
                  </td>
                </tr>
              ) : (
                packingList.rows.map((row, idx) => (
                  <tr key={idx}>
                    <td className="font-mono text-sm">{row.item_id}</td>
                    <td>{row.description || '-'}</td>
                    <td className="font-mono text-sm">{row.po_no}</td>
                    {packingList.shipment_type === 'LCL' && (
                      <td>
                        {row.customer_code ? (
                          <span className="badge-inline badge-lcl-inline">{row.customer_code}</span>
                        ) : '-'}
                      </td>
                    )}
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>{formatNumber(row.qty_cartons)}</td>
                    <td style={{ textAlign: 'right' }}>{formatNumber(row.qty_pcs)}</td>
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