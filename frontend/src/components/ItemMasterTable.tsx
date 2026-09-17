import { useEffect, useRef, useState, FormEvent } from 'react'
import { itemApi } from '../hooks/useApi'
import type { Item, ItemCreate } from '../types/api'
import { Icons } from './Layout'
import { useToastStore } from './Toast'
import { generateItemsCSVTemplate, downloadCSVTemplate } from '../utils/csvParser'

export function ItemMasterTable() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingItem, setEditingItem] = useState<Item | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState<ItemCreate>({
    item_id: '',
    description: '',
    length_cm: 0,
    width_cm: 0,
    height_cm: 0,
    weight_kg: 0,
    this_way_up: true,
    stacking_group: 1,
    max_load_bearing_kg: undefined,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const { success: toastSuccess, error: toastError } = useToastStore()

  useEffect(() => {
    itemApi.list()
      .then((data) => {
        setItems(data)
        setLoading(false)
      })
      .catch(() => {
        setLoading(false)
      })
  }, [])

  const handleMasterDataUpload = async (file: File | undefined) => {
    if (!file) return
    setLoading(true)
    try {
      const result = await itemApi.uploadCsv(file)
      if (result.created > 0 || result.updated > 0) {
        toastSuccess(`Imported ${result.created} new items, updated ${result.updated} existing items`)
      }
      if (result.errors && result.errors.length > 0) {
        toastError(`${result.errors.length} rows had errors: ${result.errors.slice(0, 3).join('; ')}`)
      }
      // Reload from API to get server-generated IDs
      const updated = await itemApi.list()
      setItems(updated)
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

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setErrors({})

    const newErrors: Record<string, string> = {}
    if (!formData.item_id) newErrors.item_id = 'Item ID is required'
    if (!formData.description) newErrors.description = 'Description is required'
    if (formData.length_cm <= 0) newErrors.length_cm = 'Length must be > 0'
    if (formData.width_cm <= 0) newErrors.width_cm = 'Width must be > 0'
    if (formData.height_cm <= 0) newErrors.height_cm = 'Height must be > 0'
    if (formData.weight_kg <= 0) newErrors.weight_kg = 'Weight must be > 0'
    if (formData.max_load_bearing_kg !== undefined && formData.max_load_bearing_kg <= 0) {
      newErrors.max_load_bearing_kg = 'Must be > 0'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    try {
      if (editingItem) {
        const updated = await itemApi.update(editingItem.id, formData)
        setItems(items.map(i => i.id === editingItem.id ? updated : i))
        toastSuccess('Item updated successfully')
      } else {
        const created = await itemApi.create(formData)
        setItems([created, ...items])
        toastSuccess('Item created successfully')
      }
      setShowModal(false)
      setEditingItem(null)
      resetForm()
    } catch (e: any) {
      toastError(e.response?.data?.detail || 'Failed to save')
    }
  }

  const handleEdit = (item: Item) => {
    setEditingItem(item)
    setFormData({
      item_id: item.item_id,
      description: item.description,
      length_cm: item.length_cm,
      width_cm: item.width_cm,
      height_cm: item.height_cm,
      weight_kg: item.weight_kg,
      this_way_up: item.this_way_up,
      stacking_group: item.stacking_group,
      max_load_bearing_kg: item.max_load_bearing_kg || undefined,
    })
    setShowModal(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this item?')) return
    try {
      await itemApi.delete(id)
      setItems(items.filter(i => i.id !== id))
      toastSuccess('Item deleted successfully')
    } catch (e: any) {
      toastError(e.response?.data?.detail || 'Failed to delete')
    }
  }

  const handleNew = () => {
    setEditingItem(null)
    resetForm()
    setShowModal(true)
  }

  const handleDownloadTemplate = () => {
    downloadCSVTemplate(generateItemsCSVTemplate(), 'items_template.csv')
  }

  const resetForm = () => {
    setFormData({
      item_id: '',
      description: '',
      length_cm: 0,
      width_cm: 0,
      height_cm: 0,
      weight_kg: 0,
      this_way_up: true,
      stacking_group: 1,
      max_load_bearing_kg: undefined,
    })
    setErrors({})
  }

  const filteredItems = items.filter(item =>
    item.item_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.description.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const triggerFileInput = () => {
    fileInputRef.current?.click()
  }

  if (loading) return <div className="p-8 text-center text-muted">Loading...</div>

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h2 className="text-2xl font-bold">Item Master</h2>
        <div className="flex items-center gap-2 flex-nowrap">
          <div className="search-input-wrapper" style={{ minWidth: '160px', maxWidth: '220px', width: '100%' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              className="input"
              placeholder="Search Item..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn btn-secondary flex items-center gap-2 whitespace-nowrap"
            onClick={handleDownloadTemplate}
          >
            <Icons.FileText /> Download Template
          </button>
          <button
            type="button"
            className="btn btn-secondary flex items-center gap-2 whitespace-nowrap"
            onClick={triggerFileInput}
          >
            <Icons.Upload /> Upload CSV
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            style={{ display: 'none' }}
            onChange={(e) => handleMasterDataUpload(e.target.files?.[0])}
          />
          <button className="btn btn-primary flex items-center gap-2 whitespace-nowrap" onClick={handleNew}>
            <Icons.Plus /> New Item
          </button>
        </div>
      </header>

      <div className="card">
        <div className="table-container overflow-y-auto">
          <table className="data-table">
          <thead>
            <tr>
              <th>Item ID</th>
              <th>Description</th>
              <th>Dims (L×W×H)</th>
              <th>Weight</th>
              <th>This Way Up</th>
              <th>Stack Group</th>
              <th>Max Load</th>
              <th className="actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((item) => (
              <tr key={item.id}>
                <td className="font-mono">{item.item_id}</td>
                <td>{item.description}</td>
                <td>{item.length_cm}×{item.width_cm}×{item.height_cm}</td>
                <td>{item.weight_kg} kg</td>
                <td>{item.this_way_up ? 'Yes' : 'No'}</td>
                <td>Group {item.stacking_group}</td>
                <td>{item.max_load_bearing_kg ? `${item.max_load_bearing_kg} kg` : '—'}</td>
                <td className="actions">
                  <button className="btn-icon" onClick={() => handleEdit(item)} title="Edit">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                  </button>
                  <button className="btn-icon error" onClick={() => handleDelete(item.id)} title="Delete">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>

        {showModal && (
          <div className="modal-overlay" onClick={() => setShowModal(false)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3 className="modal-title">{editingItem ? 'Edit Item' : 'New Item'}</h3>
                <button className="modal-close" onClick={() => setShowModal(false)}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
              <form onSubmit={handleSubmit}>
                <div className="modal-body">
                  <div className="mb-4">
                    <label className="label" htmlFor="item_id">Item ID *</label>
                    <input
                      id="item_id"
                      type="text"
                      className={`input ${errors.item_id ? 'input-error' : ''}`}
                      value={formData.item_id}
                      onChange={(e) => setFormData({ ...formData, item_id: e.target.value })}
                      disabled={!!editingItem}
                    />
                    {errors.item_id && <p className="error-text">{errors.item_id}</p>}
                  </div>

                  <div className="mb-4">
                    <label className="label" htmlFor="description">Description *</label>
                    <input
                      id="description"
                      type="text"
                      className={`input ${errors.description ? 'input-error' : ''}`}
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    />
                    {errors.description && <p className="error-text">{errors.description}</p>}
                  </div>

                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div>
                      <label className="label" htmlFor="length">Length (cm) *</label>
                      <input
                        id="length"
                        type="number"
                        step="0.1"
                        className={`input ${errors.length_cm ? 'input-error' : ''}`}
                        value={formData.length_cm}
                        onChange={(e) => setFormData({ ...formData, length_cm: parseFloat(e.target.value) || 0 })}
                      />
                      {errors.length_cm && <p className="error-text">{errors.length_cm}</p>}
                    </div>
                    <div>
                      <label className="label" htmlFor="width">Width (cm) *</label>
                      <input
                        id="width"
                        type="number"
                        step="0.1"
                        className={`input ${errors.width_cm ? 'input-error' : ''}`}
                        value={formData.width_cm}
                        onChange={(e) => setFormData({ ...formData, width_cm: parseFloat(e.target.value) || 0 })}
                      />
                      {errors.width_cm && <p className="error-text">{errors.width_cm}</p>}
                    </div>
                    <div>
                      <label className="label" htmlFor="height">Height (cm) *</label>
                      <input
                        id="height"
                        type="number"
                        step="0.1"
                        className={`input ${errors.height_cm ? 'input-error' : ''}`}
                        value={formData.height_cm}
                        onChange={(e) => setFormData({ ...formData, height_cm: parseFloat(e.target.value) || 0 })}
                      />
                      {errors.height_cm && <p className="error-text">{errors.height_cm}</p>}
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div>
                      <label className="label" htmlFor="weight">Weight (kg) *</label>
                      <input
                        id="weight"
                        type="number"
                        step="0.1"
                        className={`input ${errors.weight_kg ? 'input-error' : ''}`}
                        value={formData.weight_kg}
                        onChange={(e) => setFormData({ ...formData, weight_kg: parseFloat(e.target.value) || 0 })}
                      />
                      {errors.weight_kg && <p className="error-text">{errors.weight_kg}</p>}
                    </div>
                    <div>
                      <label className="label">This Way Up</label>
                      <select
                        className="input"
                        value={formData.this_way_up ? 'true' : 'false'}
                        onChange={(e) => setFormData({ ...formData, this_way_up: e.target.value === 'true' })}
                      >
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                      </select>
                    </div>
                    <div>
                      <label className="label" htmlFor="stacking">Stacking Group *</label>
                      <select
                        id="stacking"
                        className="input"
                        value={formData.stacking_group}
                        onChange={(e) => setFormData({ ...formData, stacking_group: parseInt(e.target.value, 10) })}
                      >
                        <option value={1}>1 (Sturdy)</option>
                        <option value={2}>2 (Fragile)</option>
                      </select>
                    </div>
                  </div>

                  <div className="mb-4">
                    <label className="label" htmlFor="max_load">Max Load Bearing (kg)</label>
                    <input
                      id="max_load"
                      type="number"
                      step="0.1"
                      className={`input ${errors.max_load_bearing_kg ? 'input-error' : ''}`}
                      value={formData.max_load_bearing_kg || ''}
                      onChange={(e) => setFormData({ ...formData, max_load_bearing_kg: e.target.value ? parseFloat(e.target.value) : undefined })}
                    />
                    {errors.max_load_bearing_kg && <p className="error-text">{errors.max_load_bearing_kg}</p>}
                    <p className="text-sm text-light mt-1">Leave empty for unlimited</p>
                  </div>
                </div>

                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                  <button type="submit" className="btn btn-primary">{editingItem ? 'Update' : 'Create'}</button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}