import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { Layout } from './Layout'
import { RunWizard } from './RunWizard'
import { useToastStore } from './Toast'
import { act } from 'react'

// Mock the hooks
vi.mock('../hooks/useApi', () => ({
  containerApi: { list: vi.fn().mockResolvedValue([]) },
  itemApi: { list: vi.fn().mockResolvedValue([]) },
  packingListApi: { list: vi.fn().mockResolvedValue([]) },
  runApi: { list: vi.fn().mockResolvedValue([]) },
}))

const mockWizardState = {
  packingList: { preview: null, selectedId: null, mode: 'existing' },
  container: { selectedId: null, selectedType: '40HC' },
  options: { population_size: 30, generations: 40, tolerance_gap_cm: 2.0 },
  isRunning: false,
  progress: null,
  result: null,
  setPackingListSelected: vi.fn(),
  setContainerSelected: vi.fn(),
  setPackingListPreview: vi.fn(),
  setPackingListMode: vi.fn(),
  setOptions: vi.fn(),
  canRun: () => false,
  reset: vi.fn(),
}

vi.mock('../hooks/useRunWizard', () => {
  const fn = () => mockWizardState
  fn.getState = () => mockWizardState
  return { useWizardStore: fn }
})


const renderWithRouter = (ui: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {ui}
    </BrowserRouter>
  )
}

describe('Navigation Structure (Section 6.1 - FE-01 to FE-03b)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useToastStore.getState().toasts = []
    })
  })

  it('FE-01: Exactly one navigation surface with 3 top-level items', () => {
    renderWithRouter(<Layout />)

    const nav = screen.getByRole('navigation', { name: /main navigation/i })
    expect(nav).toBeInTheDocument()

    expect(screen.getByRole('link', { name: /new run/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /run history/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /data management/i })).toBeInTheDocument()

    const topLevelLinks = screen.getAllByRole('link', { name: /new run|run history/i })
    expect(topLevelLinks).toHaveLength(2)

    const allNavs = screen.getAllByRole('navigation')
    expect(allNavs).toHaveLength(1)
  })

  it('FE-02: Landing page IS the wizard (Step 1 visible immediately)', () => {
    renderWithRouter(<RunWizard />)

    expect(screen.getByText(/configure loading plan/i)).toBeInTheDocument()
    expect(screen.getByText(/select packing list/i)).toBeInTheDocument()
    expect(screen.getByText(/select target container/i)).toBeInTheDocument()
  })

  it('FE-03: Data Management groups Item Master and Containers', () => {
    renderWithRouter(<Layout />)

    const dataMgmtButton = screen.getByRole('button', { name: /data management/i })
    expect(dataMgmtButton).toBeInTheDocument()

    fireEvent.click(dataMgmtButton)

    expect(screen.getByRole('link', { name: /items/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /containers/i })).toBeInTheDocument()
  })

  it('FE-03b: No standalone Packing Lists page outside Data Management', () => {
    renderWithRouter(<Layout />)

    const topLevelLinks = screen.getAllByRole('link')
    const topLevelTexts = topLevelLinks.map((l: HTMLElement) => l.textContent?.toLowerCase() || '')
    const packingListsTopLevel = topLevelTexts.filter((t: string) => t.includes('packing list'))
    expect(packingListsTopLevel).toHaveLength(0)
  })
})