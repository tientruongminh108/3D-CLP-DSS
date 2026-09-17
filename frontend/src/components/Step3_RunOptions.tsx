import { useState } from 'react'
import type { RunOptions } from '../types/ui'

interface Step3_RunOptionsProps {
  options: RunOptions
  onChange: (options: Partial<RunOptions>) => void
}

const DEFAULTS: Required<RunOptions> = {
  population_size: 30,
  generations: 40,
  tolerance_gap_cm: 2.0,
}

const LIMITS = {
  population_size: { min: 10, max: 200 },
  generations: { min: 10, max: 500 },
  tolerance_gap_cm: { min: 0, max: 10 },
} as const

function clamp(key: keyof RunOptions, value: number) {
  const limit = LIMITS[key]
  if (!Number.isFinite(value)) return DEFAULTS[key]
  return Math.min(limit.max, Math.max(limit.min, value))
}

export function Step3_RunOptions({ options, onChange }: Step3_RunOptionsProps) {
  const [expanded, setExpanded] = useState(false)

  const handleChange = (key: keyof RunOptions, rawValue: string) => {
    if (rawValue === '') {
      onChange({ [key]: undefined })
      return
    }

    const value = Number(rawValue)
    if (!Number.isFinite(value)) return

    onChange({ [key]: clamp(key, value) })
  }

  return (
    <section className="step">
      <button
        type="button"
        className={`step-header ${expanded ? 'active' : ''}`}
        onClick={() => setExpanded((current) => !current)}
        aria-expanded={expanded}
        aria-controls="run-options-content"
      >
        <span className="step-number">3</span>
        <span className="step-title">Step 3 - Run Options</span>
        <span className={`step-badge badge ${expanded ? 'badge-active' : 'badge-collapsed'}`}>
          {expanded ? 'expanded' : 'collapsed'}
        </span>
      </button>

      {expanded && (
        <div id="run-options-content" className="step-content expanded">
          <p className="text-sm text-muted mb-4">
            Advanced options. Most runs work well with defaults.
          </p>

          <div className="step-fields">
            <div className="field">
              <label className="label" htmlFor="population">Population Size</label>
              <input
                id="population"
                type="number"
                className="input"
                min={LIMITS.population_size.min}
                max={LIMITS.population_size.max}
                value={options.population_size ?? DEFAULTS.population_size}
                onChange={(event) => handleChange('population_size', event.target.value)}
              />
              <p className="text-sm text-light mt-1">Number of candidate solutions per generation (10-200, default: 30)</p>
            </div>

            <div className="field">
              <label className="label" htmlFor="generations">Generations</label>
              <input
                id="generations"
                type="number"
                className="input"
                min={LIMITS.generations.min}
                max={LIMITS.generations.max}
                value={options.generations ?? DEFAULTS.generations}
                onChange={(event) => handleChange('generations', event.target.value)}
              />
              <p className="text-sm text-light mt-1">Number of GA iterations (10-500, default: 40)</p>
            </div>

            <div className="field">
              <label className="label" htmlFor="gap">Tolerance Gap (cm)</label>
              <input
                id="gap"
                type="number"
                className="input"
                min={LIMITS.tolerance_gap_cm.min}
                max={LIMITS.tolerance_gap_cm.max}
                step="0.5"
                value={options.tolerance_gap_cm ?? DEFAULTS.tolerance_gap_cm}
                onChange={(event) => handleChange('tolerance_gap_cm', event.target.value)}
              />
              <p className="text-sm text-light mt-1">Minimum clearance between boxes and walls (0-10 cm, default: 2.0)</p>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
