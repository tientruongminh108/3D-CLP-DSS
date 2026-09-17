import type { Container } from '../types/api'

interface Step2_ContainerProps {
  container: {
    selectedId?: number
    selectedType?: string
  }
  onSelect: (id: number, type: string) => void
}

export function Step2_Container({ container, onSelect }: Step2_ContainerProps) {
  const isExpanded = true

  const containers: Container[] = [
    { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' },
    { id: 2, container_type: '40FT', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 239.3, max_weight_kg: 28000, created_at: '', updated_at: '' },
    { id: 3, container_type: '20FT', internal_length_cm: 589.8, internal_width_cm: 235.2, internal_height_cm: 239.3, max_weight_kg: 28000, created_at: '', updated_at: '' },
    { id: 4, container_type: '45HC', internal_length_cm: 1355.6, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' },
  ]

  const selected = containers.find(c => c.id === container.selectedId) || containers[0]

  return (
    <section className={`step ${isExpanded ? 'active' : ''}`}>
      <header className="step-header active">
        <span className="step-number">2</span>
        <span className="step-title">Step 2 - Container</span>
        <span className="step-badge badge badge-done">done</span>
      </header>

      <div className="step-content expanded">
        <div className="flex gap-4 items-end flex-wrap">
          <div className="flex-1 select-wrapper" style={{ minWidth: '280px' }}>
            <label className="label" htmlFor="container-select">Select a container</label>
            <select
              id="container-select"
              className="input"
              value={container.selectedId || selected.id}
              onChange={(e) => {
                const id = parseInt(e.target.value, 10)
                const c = containers.find(x => x.id === id)
                if (c) onSelect(id, c.container_type)
              }}
            >
              {containers.map(c => (
                <option key={c.id} value={c.id}>
                  {c.container_type} ({c.internal_length_cm}×{c.internal_width_cm}×{c.internal_height_cm} cm, {c.max_weight_kg} kg)
                </option>
              ))}
            </select>
          </div>
          <button className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-end' }}>
            New Container
          </button>
        </div>

        <div className="mt-4 p-4 bg-background rounded-md">
          <div className="flex flex-wrap gap-6 text-sm">
            <div>
              <span className="text-muted">Type:</span> <span className="font-medium">{selected.container_type}</span>
            </div>
            <div>
              <span className="text-muted">Internal dims:</span> <span className="font-medium">{selected.internal_length_cm} × {selected.internal_width_cm} × {selected.internal_height_cm} cm</span>
            </div>
            <div>
              <span className="text-muted">Max weight:</span> <span className="font-medium">{selected.max_weight_kg.toLocaleString()} kg</span>
            </div>
            <div>
              <span className="text-muted">Volume:</span> <span className="font-medium">{(selected.internal_length_cm * selected.internal_width_cm * selected.internal_height_cm / 1e6).toFixed(1)} m³</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}