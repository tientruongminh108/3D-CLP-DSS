import React from 'react'
import type { PackingListPreview } from '../types/api'

interface PackingListState {
  mode: 'existing' | 'upload' | 'paste'
  selectedId?: string
  file?: File
  pasteText?: string
  preview?: PackingListPreview
}

interface Step1_PackingListProps {
  packingList: PackingListState
  onSelectExisting: (id: string) => void
  onFileUpload: (file: File) => void
  onDownloadTemplate: () => void
}

export function Step1_PackingList({
  packingList,
  onSelectExisting,
  onFileUpload,
  onDownloadTemplate,
}: Step1_PackingListProps) {
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const { preview } = packingList

  const triggerFileInput = () => {
    fileInputRef.current?.click()
  }

  return (
    <section className="step active">
      <header className="step-header active">
        <span className="step-number">1</span>
        <span className="step-title">Step 1 - Select Packing List</span>
        {preview && <span className="step-badge badge badge-done">done</span>}
      </header>

      <div className="step-content expanded">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3 mb-4">
          <div className="flex-1 select-wrapper">
            <label className="label" htmlFor="existing-list">Packing List</label>
            <select
              id="existing-list"
              className="input"
              value={packingList.selectedId || ''}
              onChange={(e) => onSelectExisting(e.target.value)}
            >
              <option value="">-- Select a packing list --</option>
              <option value="pl-1">PO-1001 (CUST-A) - 15 cartons</option>
              <option value="pl-2">PO-2001 (CUST-A, CUST-B, CUST-C) - 10 cartons</option>
            </select>
          </div>

          <button
            type="button"
            className="btn btn-primary flex items-center justify-center gap-2 whitespace-nowrap"
            onClick={triggerFileInput}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            Upload CSV
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            style={{ display: 'none' }}
            onChange={(e) => e.target.files?.[0] && onFileUpload(e.target.files[0])}
          />
        </div>

        <div className="flex items-center justify-between text-xs text-muted">
          <span>Columns: <code>Item_ID, PO_No, Qty_Pcs, Qty_Cartons</code></span>
          <button type="button" className="btn btn-ghost p-0 text-primary" onClick={onDownloadTemplate}>
            Download CSV Template
          </button>
        </div>

        {preview && (
          <div className="mt-6">
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <span className="badge-inline badge-fcl-inline">
                {preview.shipment_type === 'FCL' ? 'FCL' : `LCL - ${preview.customer_count} customers`}
              </span>
              <span className="text-sm text-muted">
                {preview.total_cartons} cartons &bull; {preview.total_weight_kg.toFixed(1)} kg &bull; {(preview.total_volume_cm3 / 1e6).toFixed(2)} m&sup3;
              </span>
            </div>

            <div style={{ maxHeight: '300px', overflow: 'auto' }}>
              <table className="preview-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>PO</th>
                    <th>Customer</th>
                    <th>Qty</th>
                    <th>Dims (L×W×H) cm</th>
                    <th>Weight (kg)</th>
                    <th>Stack</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row: any, index: number) => {
                    const isNewGroup = index === 0 || 
                      (preview.rows[index - 1].customer_code !== row.customer_code)
                    return (
                      <tr key={`${row.item_id}-${index}`} className={isNewGroup && index > 0 ? 'customer-group' : ''}>
                        <td>{row.description}</td>
                        <td>{row.po_no}</td>
                        <td>
                          {row.customer_code ? (
                            <span className="badge-inline badge-fcl-inline">{row.customer_code}</span>
                          ) : (
                            <span className="text-light">&mdash;</span>
                          )}
                        </td>
                        <td>{row.qty_cartons}</td>
                        <td>{row.length_cm}&times;{row.width_cm}&times;{row.height_cm}</td>
                        <td>{row.weight_kg}</td>
                        <td>Group {row.stacking_group}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}