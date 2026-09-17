import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { WizardState, RunProgress, RunOptions, PackingListPreview, RunResult } from '../types/ui'

const DEFAULT_OPTIONS: RunOptions = {
  population_size: 30,
  generations: 40,
  tolerance_gap_cm: 2.0,
}

interface WizardStore extends WizardState {
  setStep: (step: number) => void
  setPackingListMode: (mode: 'existing' | 'upload' | 'paste') => void
  setPackingListSelected: (id: string) => void
  setPackingListFile: (file: File) => void
  setPackingListPaste: (text: string) => void
  setPackingListPreview: (preview: PackingListPreview | undefined) => void
  setContainerSelected: (id: number, type: string) => void
  setOptions: (options: Partial<RunOptions>) => void
  setProgress: (progress: RunProgress | null) => void
  setResult: (result: RunResult | undefined) => void
  setRunning: (running: boolean) => void
  reset: () => void
  canRun: () => boolean
  packingListVersion: number
  bumpPackingListVersion: () => void
}

const initialState: WizardState = {
  step: 1,
  packingList: {
    mode: 'existing',
    pasteText: '',
  },
  container: {},
  options: DEFAULT_OPTIONS,
  isRunning: false,
  progress: null,
  result: undefined,
}

export const useWizardStore = create<WizardStore>()(
  persist(
    (set, get) => ({
      ...initialState,
      packingListVersion: 0,

      setStep: (step) => set({ step }),

      setPackingListMode: (mode) =>
        set((state) => ({
          packingList: { ...state.packingList, mode },
        })),

      setPackingListSelected: (selectedId) =>
        set((state) => ({
          packingList: { ...state.packingList, selectedId },
        })),

      setPackingListFile: (file) =>
        set((state) => ({
          packingList: { ...state.packingList, file },
        })),

      setPackingListPaste: (pasteText) =>
        set((state) => ({
          packingList: { ...state.packingList, pasteText },
        })),

      setPackingListPreview: (preview) =>
        set((state) => ({
          packingList: { ...state.packingList, preview },
        })),

      setContainerSelected: (selectedId, selectedType) =>
        set((state) => ({
          container: { ...state.container, selectedId, selectedType },
        })),

      setOptions: (options) =>
        set((state) => ({
          options: { ...state.options, ...options },
        })),

      setProgress: (progress) => set({ progress }),

      setResult: (result) => set({ result }),

      setRunning: (isRunning) => set({ isRunning }),

      reset: () => set({ ...initialState, result: undefined, packingListVersion: get().packingListVersion }),

      bumpPackingListVersion: () => set((state) => ({ packingListVersion: state.packingListVersion + 1 })),

      canRun: () => {
        const { packingList, container } = get()
        return !!packingList.preview && !!container.selectedId
      },
    }),
    {
      name: 'wizard-storage',
      partialize: (state) => ({
        options: state.options,
        container: state.container,
        packingListVersion: state.packingListVersion,
      }),
    }
  )
)