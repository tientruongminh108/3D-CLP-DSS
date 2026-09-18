import { UnplacedReason } from '../types/api'
import type { UnplacedCarton } from '../types/api'

interface UnplacedCartonsProps {
  unplacedCartons: UnplacedCarton[]
}

export function UnplacedCartons({ unplacedCartons }: UnplacedCartonsProps) {
  if (unplacedCartons.length === 0) return null

  const byReason = unplacedCartons.reduce((acc, carton) => {
    if (!acc[carton.reason]) acc[carton.reason] = []
    acc[carton.reason].push(carton)
    return acc
  }, {} as Record<UnplacedReason, UnplacedCarton[]>)

  const reasonLabels: Record<UnplacedReason, { label: string; description: string }> = {
    [UnplacedReason.NO_SPACE]: {
      label: 'No Space',
      description: 'Container is full. Consider a larger container or splitting the shipment.',
    },
    [UnplacedReason.LIFO_BLOCKED]: {
      label: 'LIFO Blocked',
      description: 'Cargo blocked by later customer\'s cargo. Reconsider delivery order or accept shortfall.',
    },
  }

  return (
    <div className="unplaced-section">
      <div className="unplaced-title">
        <span aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{color:'#f59e0b',verticalAlign:'middle'}}>
            <path d="M8 1.333a.667.667 0 0 1 .577.334l6.667 11.556A.667.667 0 0 1 14.667 14H1.333a.667.667 0 0 1-.577-.777L7.423 1.667A.667.667 0 0 1 8 1.333zm0 1.38L2.163 13.333h11.674L8 2.713zM7.333 10V7.333a.667.667 0 0 1 1.334 0V10a.667.667 0 1 1-1.334 0zm.667 1.667a.667.667 0 1 1 0 1.333.667.667 0 0 1 0-1.333z"/>
          </svg>
        </span>
        <span>Unplaced Cartons</span>
        <span className="unplaced-count">{unplacedCartons.length}</span>
      </div>

      {Object.entries(byReason).map(([reason, cartons]) => {
        const info = reasonLabels[reason as UnplacedReason]
        return (
          <div key={reason} className="unplaced-group">
            <div className="unplaced-group-title">
              <span>{info.label}</span>
              <span className="text-sm text-muted">({cartons.length})</span>
            </div>
            <p className="text-sm text-muted mb-4">{info.description}</p>
            <div className="unplaced-list">
              {cartons.map((carton) => (
                <div key={carton.box_id} className="unplaced-item">
                  <div className="unplaced-item-info">
                    <span className="unplaced-item-id">{carton.box_id}</span>
                    <span className="unplaced-item-details">
                      {carton.item_id} • {carton.length_cm}×{carton.width_cm}×{carton.height_cm} cm • {carton.weight_kg} kg
                      {carton.customer_code && ` • ${carton.customer_code}`}
                    </span>
                  </div>
                  <span className={`badge-inline ${reason === UnplacedReason.LIFO_BLOCKED ? 'badge-lcl-inline' : ''}`}>
                    {info.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}