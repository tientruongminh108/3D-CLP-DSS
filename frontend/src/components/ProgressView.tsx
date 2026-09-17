import type { RunProgress } from '../types/ui'

interface ProgressViewProps {
  progress: RunProgress
  onCancel: () => void
}

const STAGE_LABELS: Record<RunProgress['stage'], string> = {
  parse: 'Parsing inputs',
  sort: 'Sorting boxes',
  blocks: 'Generating blocks',
  ga: 'Starting Genetic Algorithm',
  ga_progress: 'Running Genetic Algorithm',
  sa: 'Running Simulated Annealing',
  sa_progress: 'Refining with Simulated Annealing',
  decode: 'Building final solution',
  complete: 'Complete',
}

export function ProgressView({ progress, onCancel }: ProgressViewProps) {
  const label = STAGE_LABELS[progress.stage] || progress.message
  const genInfo = progress.data?.generation && progress.data?.totalGenerations
    ? ` (Gen ${progress.data.generation}/${progress.data.totalGenerations})`
    : ''

  return (
    <div className="progress-container">
      <div className="flex items-center gap-4 mb-6">
        <div className="progress-spinner" role="status" aria-label="Loading" />
        <div>
          <h2 className="text-xl font-semibold">Running Optimization &ndash; {label}{genInfo}</h2>
          <p className="text-muted text-sm">{progress.message}</p>
        </div>
      </div>

      <div className="progress-bar" role="progressbar" aria-valuenow={Math.round(progress.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
        <div
          className="progress-bar-fill"
          style={{ width: `${progress.progress * 100}%` }}
        />
      </div>

      <div className="flex justify-between mt-4">
        <span className="progress-text">{Math.round(progress.progress * 100)}%</span>
        <button className="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
      </div>

      {progress.data && (
        <div className="progress-detail mt-4">
          {progress.data.placed !== undefined && progress.data.unplaced !== undefined && (
            <div>Placed: {progress.data.placed} / Unplaced: {progress.data.unplaced} / Total: {progress.data.totalBoxes}</div>
          )}
          {progress.data.bestFitness !== undefined && (
            <div>Best fitness: {progress.data.bestFitness.toFixed(4)}</div>
          )}
          {progress.data.iteration !== undefined && (
            <div>SA iteration: {progress.data.iteration}</div>
          )}
        </div>
      )}
    </div>
  )
}