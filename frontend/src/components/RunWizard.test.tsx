import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { RunWizard } from './RunWizard'
import { useToastStore } from './Toast'
import { packingListApi, containerApi, runApi } from '../services/api'

const renderWithRouter = (ui: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {ui}
    </BrowserRouter>
  )
}

describe('Run Wizard (Section 6.2 - FE-04 to FE-12)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useToastStore.getState().toasts = []
    })
  })

  afterEach(() => {
    vi.resetModules()
  })

  it('FE-05: Shipment type badge appears after resolution', async () => {
    packingListApi.get = vi.fn().mockResolvedValue({
      id: 1, name: 'Test PL', filename: 'test.csv', total_cartons: 10, total_weight_kg: 200, total_volume_cm3: 400000, shipment_type: 'FCL', customer_count: 0,
      rows: [{ item_id: 'ITEM-1', po_no: 'PO-1', customer_code: null, description: 'Test Item', qty_pcs: 10, qty_cartons: 10 }],
      created_at: '', updated_at: ''
    })
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])

    renderWithRouter(<RunWizard />)

    const select = screen.getByRole('combobox', { name: /packing list/i })
    fireEvent.change(select, { target: { value: '1' } })

    await waitFor(() => {
      expect(screen.getByText(/fcl/i)).toBeInTheDocument()
    })
  })

  it('FE-06: Run button disabled when Step 1 empty', () => {
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])

    renderWithRouter(<RunWizard />)

    const runButton = screen.getByRole('button', { name: /execute loading plan/i })
    expect(runButton).toBeDisabled()
  })

  it('FE-07: Run button disabled when Step 2 empty', async () => {
    packingListApi.get = vi.fn().mockResolvedValue({
      id: 1, name: 'Test PL', filename: 'test.csv', total_cartons: 10, total_weight_kg: 200, total_volume_cm3: 400000, shipment_type: 'FCL', customer_count: 0,
      rows: [{ item_id: 'ITEM-1', po_no: 'PO-1', customer_code: null, description: 'Test Item', qty_pcs: 10, qty_cartons: 10 }],
      created_at: '', updated_at: ''
    })

    renderWithRouter(<RunWizard />)

    const select = screen.getByRole('combobox', { name: /packing list/i })
    fireEvent.change(select, { target: { value: '1' } })

    await waitFor(() => {
      const runButton = screen.getByRole('button', { name: /execute loading plan/i })
      expect(runButton).toBeDisabled()
    })
  })

  it('FE-08: Run button enabled when both steps filled', async () => {
    packingListApi.get = vi.fn().mockResolvedValue({
      id: 1, name: 'Test PL', filename: 'test.csv', total_cartons: 10, total_weight_kg: 200, total_volume_cm3: 400000, shipment_type: 'FCL', customer_count: 0,
      rows: [{ item_id: 'ITEM-1', po_no: 'PO-1', customer_code: null, description: 'Test Item', qty_pcs: 10, qty_cartons: 10 }],
      created_at: '', updated_at: ''
    })
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])

    renderWithRouter(<RunWizard />)

    const plSelect = screen.getByRole('combobox', { name: /packing list/i })
    fireEvent.change(plSelect, { target: { value: '1' } })

    await waitFor(() => {
      const containerSelect = screen.getByRole('combobox', { name: /container/i })
      fireEvent.change(containerSelect, { target: { value: '1' } })
    })

    await waitFor(() => {
      const runButton = screen.getByRole('button', { name: /execute loading plan/i })
      expect(runButton).toBeEnabled()
    })
  })

  it('FE-09: Step 3 collapsed by default with Section 7 defaults', () => {
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])

    renderWithRouter(<RunWizard />)

    expect(screen.queryByText(/population/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/generations/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/tolerance gap/i)).not.toBeInTheDocument()
  })

  it('FE-09b: Step 3 has only Population, Generations, Tolerance gap - no SA toggle', () => {
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])

    renderWithRouter(<RunWizard />)

    const step3Toggle = screen.getByRole('button', { name: /run options/i })
    fireEvent.click(step3Toggle)

    expect(screen.getByText(/population/i)).toBeInTheDocument()
    expect(screen.getByText(/generations/i)).toBeInTheDocument()
    expect(screen.getByText(/tolerance gap/i)).toBeInTheDocument()
    expect(screen.queryByText(/simulated annealing/i)).not.toBeInTheDocument()
  })

  it('FE-10: Run transitions in place to progress then result', async () => {
    packingListApi.get = vi.fn().mockResolvedValue({
      id: 1, name: 'Test PL', filename: 'test.csv', total_cartons: 10, total_weight_kg: 200, total_volume_cm3: 400000, shipment_type: 'FCL', customer_count: 0,
      rows: [{ item_id: 'ITEM-1', po_no: 'PO-1', customer_code: null, description: 'Test Item', qty_pcs: 10, qty_cartons: 10 }],
      created_at: '', updated_at: ''
    })
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])
    runApi.createQuick = vi.fn().mockResolvedValue({
      run_id: 'test-run-1',
      status: 'completed',
      container: { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' },
      metrics: { placed_count: 10, unplaced_count: 0, total_cartons: 10, fill_rate: 0.85, used_weight_kg: 10000, max_weight_kg: 28000, weight_utilization: 35.7, cog_x: 601.6, cog_y: 117.6, cog_z: 135.0, cog_deviation_xy: 0, cog_deviation_z: 0 },
      placed_boxes: [],
      unplaced_cartons: [],
      layers: [],
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    })

    renderWithRouter(<RunWizard />)

    const plSelect = screen.getByRole('combobox', { name: /packing list/i })
    fireEvent.change(plSelect, { target: { value: '1' } })

    await waitFor(() => {
      const containerSelect = screen.getByRole('combobox', { name: /container/i })
      fireEvent.change(containerSelect, { target: { value: '1' } })
    })

    const runButton = screen.getByRole('button', { name: /execute loading plan/i })
    fireEvent.click(runButton)

    await waitFor(() => {
      expect(screen.getByText(/running optimization/i)).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText(/loading plan result/i)).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  it('FE-11: Block Generation phase shows indeterminate spinner', async () => {
    packingListApi.get = vi.fn().mockResolvedValue({
      id: 1, name: 'Test PL', filename: 'test.csv', total_cartons: 10, total_weight_kg: 200, total_volume_cm3: 400000, shipment_type: 'FCL', customer_count: 0,
      rows: [{ item_id: 'ITEM-1', po_no: 'PO-1', customer_code: null, description: 'Test Item', qty_pcs: 10, qty_cartons: 10 }],
      created_at: '', updated_at: ''
    })
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])
    runApi.createQuick = vi.fn().mockImplementation(async () => {
      await new Promise(r => setTimeout(r, 100))
      return { run_id: 'test', status: 'completed' }
    })

    renderWithRouter(<RunWizard />)

    const plSelect = screen.getByRole('combobox', { name: /packing list/i })
    fireEvent.change(plSelect, { target: { value: '1' } })

    await waitFor(() => {
      const containerSelect = screen.getByRole('combobox', { name: /container/i })
      fireEvent.change(containerSelect, { target: { value: '1' } })
    })

    const runButton = screen.getByRole('button', { name: /execute loading plan/i })
    fireEvent.click(runButton)

    await waitFor(() => {
      const spinner = screen.getByRole('status')
      expect(spinner).toBeInTheDocument()
    })
  })
})