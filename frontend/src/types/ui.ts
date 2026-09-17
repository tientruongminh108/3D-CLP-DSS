export * from './api'

import type { PackingListPreview, RunResult, RunOptions } from './api'

export interface WizardState {
  step: number
  packingList: {
    mode: 'existing' | 'upload' | 'paste'
    selectedId?: string
    file?: File
    pasteText: string
    preview?: PackingListPreview
  }
  container: {
    selectedId?: number
    selectedType?: string
  }
  options: RunOptions
  isRunning: boolean
  progress: RunProgress | null
  result?: RunResult
}

export interface RunProgress {
  stage: 'parse' | 'sort' | 'blocks' | 'ga' | 'ga_progress' | 'sa' | 'sa_progress' | 'decode' | 'complete'
  progress: number
  message: string
  data?: {
    generation?: number
    totalGenerations?: number
    bestFitness?: number
    placed?: number
    unplaced?: number
    totalBoxes?: number
    iteration?: number
  }
}

export type WizardStep = 1 | 2 | 3