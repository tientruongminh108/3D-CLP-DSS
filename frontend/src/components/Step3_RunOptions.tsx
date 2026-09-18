import { useState, useEffect } from 'react'
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

  const [populationSize, setPopulationSize] = useState(
    options.population_size !== undefined ? String(options.population_size) : ''
  )
  const [generations, setGenerations] = useState(
    options.generations !== undefined ? String(options.generations) : ''
  )
  const [toleranceGap, setToleranceGap] = useState(
    options.tolerance_gap_cm !== undefined ? String(options.tolerance_gap_cm) : ''
  )

  useEffect(() => {
    setPopulationSize(options.population_size !== undefined ? String(options.population_size) : '')
  }, [options.population_size])

  useEffect(() => {
    setGenerations(options.generations !== undefined ? String(options.generations) : '')
  }, [options.generations])

  useEffect(() => {
    setToleranceGap(options.tolerance_gap_cm !== undefined ? String(options.tolerance_gap_cm) : '')
  }, [options.tolerance_gap_cm])

  const handleInputChange = (key: keyof RunOptions, value: string) => {
    if (key === 'population_size') setPopulationSize(value)
    else if (key === 'generations') setGenerations(value)
    else if (key === 'tolerance_gap_cm') setToleranceGap(value)
  }

  const handleBlur = (key: keyof RunOptions) => {
    const rawValue = 
      key === 'population_size' ? populationSize :
      key === 'generations' ? generations : toleranceGap

    if (rawValue === '') {
      onChange({ [key]: undefined })
      return
    }

    const value = Number(rawValue)
    if (!Number.isFinite(value)) {
      const current = options[key]
      handleInputChange(key, current !== undefined ? String(current) : '')
      return
    }

    const clamped = clamp(key, value)
    handleInputChange(key, String(clamped))
    onChange({ [key]: clamped })
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm">
      <button
        type="button"
        className="w-full px-5 py-4 flex items-center justify-between text-left hover:bg-slate-50 transition-colors rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
        onClick={() => setExpanded((current) => !current)}
        aria-expanded={expanded}
        aria-controls="run-options-content"
      >
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 text-sm font-medium">3</span>
          <h2 className="text-base font-semibold text-slate-900">Step 3 - Run Options (Advanced)</h2>
        </div>
        <div className="flex items-center gap-2">
          {!expanded && (
            <span className="hidden sm:inline-flex text-xs font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
              Pop: {options.population_size ?? DEFAULTS.population_size} &bull; Gen: {options.generations ?? DEFAULTS.generations} &bull; Gap: {options.tolerance_gap_cm ?? DEFAULTS.tolerance_gap_cm}cm
            </span>
          )}
          <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600">
            {expanded ? 'Hide options' : 'Optional / Advanced'}
          </span>
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`text-slate-400 transform transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
          >
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
      </button>

      {expanded && (
        <div id="run-options-content" className="p-5 border-t border-slate-200 space-y-4">
          <p className="text-sm text-slate-500">
            Advanced optimization settings. Default parameters are tuned for optimal balance of speed and container fill rate.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-slate-700" htmlFor="population">
                Population Size
              </label>
              <input
                id="population"
                type="number"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors hover:border-slate-400"
                min={LIMITS.population_size.min}
                max={LIMITS.population_size.max}
                value={populationSize}
                onChange={(event) => handleInputChange('population_size', event.target.value)}
                onBlur={() => handleBlur('population_size')}
              />
              <p className="text-xs text-slate-500">Candidate solutions per generation (10–200, default: 30)</p>
            </div>

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-slate-700" htmlFor="generations">
                Generations
              </label>
              <input
                id="generations"
                type="number"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors hover:border-slate-400"
                min={LIMITS.generations.min}
                max={LIMITS.generations.max}
                value={generations}
                onChange={(event) => handleInputChange('generations', event.target.value)}
                onBlur={() => handleBlur('generations')}
              />
              <p className="text-xs text-slate-500">Number of GA iterations (10–500, default: 40)</p>
            </div>

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-slate-700" htmlFor="gap">
                Tolerance Gap (cm)
              </label>
              <input
                id="gap"
                type="number"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors hover:border-slate-400"
                min={LIMITS.tolerance_gap_cm.min}
                max={LIMITS.tolerance_gap_cm.max}
                step="0.5"
                value={toleranceGap}
                onChange={(event) => handleInputChange('tolerance_gap_cm', event.target.value)}
                onBlur={() => handleBlur('tolerance_gap_cm')}
              />
              <p className="text-xs text-slate-500">Clearance between boxes and walls (0–10 cm, default: 2.0)</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
