import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { RunHistory } from './RunHistory'
import { useToastStore } from './Toast'
import { runApi } from '../services/api'
import { RunStatus, ShipmentType, type RunSummary } from '../types/api'

const renderWithRouter = (ui: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {ui}
    </BrowserRouter>
  )
}

const mockRuns: RunSummary[] = [
  {
    run_id: 'run-completed-12345678',
    container_type: '40HC',
    shipment_type: ShipmentType.FCL,
    total_cartons: 100,
    placed_count: 95,
    unplaced_count: 5,
    customer_count: 1,
    fill_rate: 0.82,
    status: RunStatus.COMPLETED,
    created_at: '2026-09-20T10:00:00Z',
  },
  {
    run_id: 'run-running-abcdefgh',
    container_type: '20GP',
    shipment_type: ShipmentType.LCL,
    total_cartons: 50,
    placed_count: 0,
    unplaced_count: 50,
    customer_count: 2,
    fill_rate: 0.0,
    status: RunStatus.RUNNING,
    created_at: '2026-09-20T11:00:00Z',
  },
  {
    run_id: 'run-failed-98765432',
    container_type: '40HC',
    shipment_type: ShipmentType.FCL,
    total_cartons: 80,
    placed_count: 0,
    unplaced_count: 80,
    customer_count: 1,
    fill_rate: 0.0,
    status: RunStatus.FAILED,
    created_at: '2026-09-20T09:00:00Z',
  },
]

describe('RunHistory Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useToastStore.getState().toasts = []
    })
    window.confirm = vi.fn().mockReturnValue(true)
  })

  it('renders runs and displays disabled delete controls for running runs', async () => {
    runApi.list = vi.fn().mockResolvedValue(mockRuns)

    renderWithRouter(<RunHistory />)

    await waitFor(() => {
      expect(screen.getByText('Run History')).toBeInTheDocument()
    })

    // Find row checkboxes
    const completedCheckbox = screen.getByLabelText('Select run run-completed-12345678') as HTMLInputElement
    const runningCheckbox = screen.getByLabelText('Select run run-running-abcdefgh') as HTMLInputElement
    const failedCheckbox = screen.getByLabelText('Select run run-failed-98765432') as HTMLInputElement

    expect(completedCheckbox).toBeInTheDocument()
    expect(completedCheckbox.disabled).toBe(false)

    expect(runningCheckbox).toBeInTheDocument()
    expect(runningCheckbox.disabled).toBe(true)
    expect(runningCheckbox.getAttribute('title')).toBe('Cannot delete an active run')

    expect(failedCheckbox).toBeInTheDocument()
    expect(failedCheckbox.disabled).toBe(false)

    // Delete buttons
    const deleteCompletedBtn = screen.getByLabelText('Delete run run-completed-12345678') as HTMLButtonElement
    const deleteRunningBtn = screen.getByLabelText('Delete run run-running-abcdefgh') as HTMLButtonElement

    expect(deleteCompletedBtn.disabled).toBe(false)
    expect(deleteRunningBtn.disabled).toBe(true)
    expect(deleteRunningBtn.getAttribute('title')).toBe('Cannot delete an active run')
  })

  it('performs single run delete when confirmed', async () => {
    runApi.list = vi.fn().mockResolvedValue(mockRuns)
    runApi.delete = vi.fn().mockResolvedValue({})

    renderWithRouter(<RunHistory />)

    await waitFor(() => {
      expect(screen.getByText('run-comp...')).toBeInTheDocument()
    })

    const deleteBtn = screen.getByLabelText('Delete run run-completed-12345678')
    fireEvent.click(deleteBtn)

    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('run-comp'))
    await waitFor(() => {
      expect(runApi.delete).toHaveBeenCalledWith('run-completed-12345678')
    })
  })

  it('performs bulk delete for selected completed/failed runs', async () => {
    runApi.list = vi.fn().mockResolvedValue(mockRuns)
    runApi.delete = vi.fn().mockResolvedValue({})

    renderWithRouter(<RunHistory />)

    await waitFor(() => {
      expect(screen.getByText('run-comp...')).toBeInTheDocument()
    })

    // Click "Select all completed runs"
    const selectAllCheckbox = screen.getByLabelText('Select all completed runs')
    fireEvent.click(selectAllCheckbox)

    // Verify bulk delete banner appears with count 2 (running run excluded)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Delete Selected \(2\)/i })).toBeInTheDocument()
    })

    const bulkDeleteBtn = screen.getByRole('button', { name: /Delete Selected \(2\)/i })
    fireEvent.click(bulkDeleteBtn)

    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('2 selected runs'))
    await waitFor(() => {
      expect(runApi.delete).toHaveBeenCalledWith('run-completed-12345678')
      expect(runApi.delete).toHaveBeenCalledWith('run-failed-98765432')
    })
  })
})
