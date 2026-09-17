import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Item, Container, PackingListRow } from '../types/api'

interface DataState {
  // Items
  items: Item[]
  itemsLoading: boolean
  setItems: (items: Item[]) => void
  addItems: (items: Item[]) => void
  updateItem: (item: Item) => void
  removeItem: (id: number) => void
  setItemsLoading: (loading: boolean) => void

  // Containers
  containers: Container[]
  containersLoading: boolean
  setContainers: (containers: Container[]) => void
  addContainers: (containers: Container[]) => void
  updateContainer: (container: Container) => void
  removeContainer: (id: number) => void
  setContainersLoading: (loading: boolean) => void

  // Packing Lists
  packingLists: PackingListRow[]
  packingListsLoading: boolean
  setPackingLists: (lists: PackingListRow[]) => void
  addPackingListRows: (rows: PackingListRow[]) => void
  setPackingListsLoading: (loading: boolean) => void

  // CSV Import helpers
  importItemsFromCSV: (file: File) => Promise<{ success: number; errors: string[] }>
  importContainersFromCSV: (file: File) => Promise<{ success: number; errors: string[] }>
  importPackingListsFromCSV: (file: File) => Promise<{ success: number; errors: string[] }>
}

const initialState = {
  items: [],
  itemsLoading: false,
  containers: [],
  containersLoading: false,
  packingLists: [],
  packingListsLoading: false,
}

export const useDataStore = create<DataState>()(
  persist(
    (set, get) => ({
      ...initialState,

      // Items
      setItems: (items) => set({ items }),
      addItems: (newItems) => set((state) => ({ items: [...newItems, ...state.items] })),
      updateItem: (updatedItem) =>
        set((state) => ({
          items: state.items.map((i) => (i.id === updatedItem.id ? updatedItem : i)),
        })),
      removeItem: (id) =>
        set((state) => ({
          items: state.items.filter((i) => i.id !== id),
        })),
      setItemsLoading: (loading) => set({ itemsLoading: loading }),

      // Containers
      setContainers: (containers) => set({ containers }),
      addContainers: (newContainers) =>
        set((state) => ({ containers: [...newContainers, ...state.containers] })),
      updateContainer: (updatedContainer) =>
        set((state) => ({
          containers: state.containers.map((c) =>
            c.id === updatedContainer.id ? updatedContainer : c
          ),
        })),
      removeContainer: (id) =>
        set((state) => ({
          containers: state.containers.filter((c) => c.id !== id),
        })),
      setContainersLoading: (loading) => set({ containersLoading: loading }),

      // Packing Lists
      setPackingLists: (packingLists) => set({ packingLists }),
      addPackingListRows: (rows) =>
        set((state) => ({ packingLists: [...rows, ...state.packingLists] })),
      setPackingListsLoading: (loading) => set({ packingListsLoading: loading }),

      // CSV Import Functions
      importItemsFromCSV: async (file) => {
        const { parseItemsCSV } = await import('../utils/csvParser')
        const result = await parseItemsCSV(file)
        
        if (!result.success || !result.data) {
          return { success: 0, errors: result.errors || [result.error || 'Import failed'] }
        }

        // Convert ItemCreate[] to Item[] with generated IDs
        const newItems: Item[] = result.data.map((item, index) => ({
          id: Date.now() + index,
          ...item,
          stacking_group: item.stacking_group as 1 | 2,
          max_load_bearing_kg: item.max_load_bearing_kg ?? null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }))

        get().addItems(newItems)
        return { success: newItems.length, errors: result.errors || [] }
      },

      importContainersFromCSV: async (file) => {
        const { parseContainersCSV } = await import('../utils/csvParser')
        const result = await parseContainersCSV(file)
        
        if (!result.success || !result.data) {
          return { success: 0, errors: result.errors || [result.error || 'Import failed'] }
        }

        const newContainers: Container[] = result.data.map((container, index) => ({
          id: Date.now() + index,
          ...container,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }))

        get().addContainers(newContainers)
        return { success: newContainers.length, errors: result.errors || [] }
      },

      importPackingListsFromCSV: async (file) => {
        const { parsePackingListsCSV } = await import('../utils/csvParser')
        const result = await parsePackingListsCSV(file)
        
        if (!result.success || !result.data) {
          return { success: 0, errors: result.errors || [result.error || 'Import failed'] }
        }

        get().addPackingListRows(result.data)
        return { success: result.data.length, errors: result.errors || [] }
      },
    }),
    {
      name: 'data-storage',
      partialize: (state) => ({
        items: state.items,
        containers: state.containers,
        packingLists: state.packingLists,
      }),
    }
  )
)