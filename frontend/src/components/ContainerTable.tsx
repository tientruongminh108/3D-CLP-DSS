import { useEffect, useRef, useState, FormEvent } from 'react'
import { containerApi } from '../hooks/useApi'
import type { Container, ContainerCreate } from '../types/api'
import { Icons } from './Layout'
import { useToastStore } from './Toast'
import { generateContainersCSVTemplate, downloadCSVTemplate } from '../utils/csv'

export function ContainerTable() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [containers, setContainers] = useState<Container[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingContainer, setEditingContainer] = useState<Container | null>(null)
  const [formData, setFormData] = useState<ContainerCreate>({
    container_type: '',
    internal_length_cm: 0,
    internal_width_cm: 0,
    internal_height_cm: 0,
    max_weight_kg: 0,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const { success: toastSuccess, error: toastError } = useToastStore()

  const loadContainers = async () => {
    try {
      const data = await containerApi.list()
      setContainers(data)
    } catch (err: any) {
      console.error('Failed to load containers', err)
      toastError('Failed to load containers from server')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadContainers()
  }, [])

  const handleMasterDataUpload = async (file: File | undefined) => {
    if (!file) return
    setLoading(true)
    let uploadSuccess = false
    try {
      const result = await containerApi.uploadCsv(file)
      uploadSuccess = true
      if (result.created > 0 || result.updated > 0) {
        toastSuccess(`Imported ${result.created} new containers, updated ${result.updated} existing containers`)
      }
      if (result.errors && result.errors.length > 0) {
        toastError(`${result.errors.length} rows had errors: ${result.errors.slice(0, 3).join('; ')}`)
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

    if (uploadSuccess) {
      try {
        const updated = await containerApi.list()
        setContainers(updated)
      } catch (err: any) {
        console.error('Failed to refresh containers', err)
        toastError('Failed to refresh containers table')
      }
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setErrors({})

    const newErrors: Record<string, string> = {}
    if (!formData.container_type) newErrors.container_type = 'Container type is required'
    if (formData.internal_length_cm <= 0) newErrors.internal_length_cm = 'Length must be > 0'
    if (formData.internal_width_cm <= 0) newErrors.internal_width_cm = 'Width must be > 0'
    if (formData.internal_height_cm <= 0) newErrors.internal_height_cm = 'Height must be > 0'
    if (formData.max_weight_kg <= 0) newErrors.max_weight_kg = 'Max weight must be > 0'

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    try {
      if (editingContainer) {
        const updated = await containerApi.update(editingContainer.id, formData)
        setContainers(containers.map(c => c.id === editingContainer.id ? updated : c))
        toastSuccess('Container updated successfully')
      } else {
        const created = await containerApi.create(formData)
        setContainers([created, ...containers])
        toastSuccess('Container created successfully')
      }
      setShowModal(false)
      setEditingContainer(null)
      resetForm()
    } catch (e: any) {
      toastError(e.response?.data?.detail || 'Failed to save')
    }
  }

  const handleEdit = (container: Container) => {
    setEditingContainer(container)
    setFormData({
      container_type: container.container_type,
      internal_length_cm: container.internal_length_cm,
      internal_width_cm: container.internal_width_cm,
      internal_height_cm: container.internal_height_cm,
      max_weight_kg: container.max_weight_kg,
    })
    setShowModal(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this container?')) return
    try {
      await containerApi.delete(id)
      setContainers(containers.filter(c => c.id !== id))
      toastSuccess('Container deleted successfully')
    } catch (e: any) {
      toastError(e.response?.data?.detail || 'Failed to delete')
    }
  }

  const handleNew = () => {
    setEditingContainer(null)
    resetForm()
    setShowModal(true)
  }

  const handleDownloadTemplate = () => {
    downloadCSVTemplate(generateContainersCSVTemplate(), 'containers_template.csv')
  }

  const resetForm = () => {
    setFormData({
      container_type: '',
      internal_length_cm: 0,
      internal_width_cm: 0,
      internal_height_cm: 0,
      max_weight_kg: 0,
    })
    setErrors({})
  }

  const triggerFileInput = () => {
    fileInputRef.current?.click()
  }

  if (loading) return <div className="p-8 text-center text-muted">Loading...</div>

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h2 className="text-2xl font-bold">Containers</h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn btn-secondary flex items-center gap-2"
            onClick={handleDownloadTemplate}
          >
            <Icons.FileText /> Download Template
          </button>
          <button
            type="button"
            className="btn btn-secondary flex items-center gap-2"
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
          <button className="btn btn-primary flex items-center gap-2" onClick={handleNew}>
            <Icons.Plus /> New Container
          </button>
        </div>
      </header>

      <div className="card">
        <div className="table-container overflow-y-auto">
          <table className="data-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Internal Dims (L×W×H)</th>
              <th>Max Weight</th>
              <th>Volume</th>
              <th className="actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {containers.map((container) => (
              <tr key={container.id}>
                <td className="font-mono">{container.container_type}</td>
                <td>{container.internal_length_cm}×{container.internal_width_cm}×{container.internal_height_cm} cm</td>
                <td>{container.max_weight_kg.toLocaleString()} kg</td>
                <td>{(container.internal_length_cm * container.internal_width_cm * container.internal_height_cm / 1e6).toFixed(1)} m³</td>
                <td className="actions">
                  <button className="btn-icon" onClick={() => handleEdit(container)} title="Edit">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                  </button>
                  <button className="btn-icon error" onClick={() => handleDelete(container.id)} title="Delete">
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
            <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3 className="modal-title">{editingContainer ? 'Edit Container' : 'New Container'}</h3>
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
                    <label className="label" htmlFor="container_type">Container Type *</label>
                    <input
                      id="container_type"
                      type="text"
                      className={`input ${errors.container_type ? 'input-error' : ''}`}
                      value={formData.container_type}
                      onChange={(e) => setFormData({ ...formData, container_type: e.target.value })}
                      disabled={!!editingContainer}
                    />
                    {errors.container_type && <p className="error-text">{errors.container_type}</p>}
                  </div>

                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div>
                      <label className="label" htmlFor="length">Internal Length (cm) *</label>
                      <input
                        id="length"
                        type="number"
                        step="0.1"
                        className={`input ${errors.internal_length_cm ? 'input-error' : ''}`}
                        value={formData.internal_length_cm}
                        onChange={(e) => setFormData({ ...formData, internal_length_cm: parseFloat(e.target.value) || 0 })}
                      />
                      {errors.internal_length_cm && <p className="error-text">{errors.internal_length_cm}</p>}
                    </div>
                    <div>
                      <label className="label" htmlFor="width">Internal Width (cm) *</label>
                      <input
                        id="width"
                        type="number"
                        step="0.1"
                        className={`input ${errors.internal_width_cm ? 'input-error' : ''}`}
                        value={formData.internal_width_cm}
                        onChange={(e) => setFormData({ ...formData, internal_width_cm: parseFloat(e.target.value) || 0 })}
                      />
                      {errors.internal_width_cm && <p className="error-text">{errors.internal_width_cm}</p>}
                    </div>
                    <div>
                      <label className="label" htmlFor="height">Internal Height (cm) *</label>
                      <input
                        id="height"
                        type="number"
                        step="0.1"
                        className={`input ${errors.internal_height_cm ? 'input-error' : ''}`}
                        value={formData.internal_height_cm}
                        onChange={(e) => setFormData({ ...formData, internal_height_cm: parseFloat(e.target.value) || 0 })}
                      />
                      {errors.internal_height_cm && <p className="error-text">{errors.internal_height_cm}</p>}
                    </div>
                  </div>

                  <div className="mb-4">
                    <label className="label" htmlFor="max_weight">Max Weight (kg) *</label>
                    <input
                      id="max_weight"
                      type="number"
                      step="1"
                      className={`input ${errors.max_weight_kg ? 'input-error' : ''}`}
                      value={formData.max_weight_kg}
                      onChange={(e) => setFormData({ ...formData, max_weight_kg: parseFloat(e.target.value) || 0 })}
                    />
                    {errors.max_weight_kg && <p className="error-text">{errors.max_weight_kg}</p>}
                  </div>
                </div>

                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                  <button type="submit" className="btn btn-primary">{editingContainer ? 'Update' : 'Create'}</button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}