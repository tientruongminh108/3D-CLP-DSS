import { useCallback, useEffect, useRef, useState } from 'react'
import { useWizardStore } from '../hooks/useRunWizard'
import { containerApi, runApi, packingListApi } from '../services/api'
import type {
  Container,
  PackingListPreview,
  PackingListPreviewRow,
  PackingListRow,
  PackingListSummary,
  RunCreateQuick,
} from '../types/api'
import { ProgressView } from './ProgressView'
import { LoadingPlanViewer } from './LoadingPlanViewer'
import { Step3_RunOptions } from './Step3_RunOptions'
import { useToastStore } from './Toast'

function Step1PackingList({
  packingList,
  onSelectExisting,
  setPackingListPreview,
  setPackingListMode,
}: {
  packingList: {
    preview?: PackingListPreview
    selectedId?: string
  }
  onSelectExisting: (id: string) => void
  setPackingListPreview: (preview: PackingListPreview | undefined) => void
  setPackingListMode?: (mode: 'existing' | 'upload' | 'paste') => void
}) {
  const { preview, selectedId } = packingList
  const fileInputRef = useRef<HTMLInputElement>(null)
  const selectionRequestRef = useRef(0)
  const uploadRequestRef = useRef(0)
  const [uploading, setUploading] = useState(false)
  const [selectingId, setSelectingId] = useState<string | null>(null)
  const [isDragActive, setIsDragActive] = useState(false)
  const [savedLists, setSavedLists] = useState<PackingListSummary[]>([])
  const [loadingLists, setLoadingLists] = useState(true)
  const [listsError, setListsError] = useState<string | null>(null)
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const { success: toastSuccess, error: toastError } = useToastStore()
  const packingListVersion = useWizardStore((s) => s.packingListVersion)

  const handleDownloadTemplate = () => {
    const templateContent = 'Item_ID,PO_No,Customer_Code,Description,Qty_Pcs,Qty_Cartons\nDT-8411,PO-1001,CUST-A,Dining Table,4,4\nCH-2205,PO-1001,CUST-A,Chair,8,8\n'
    const blob = new Blob([templateContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.setAttribute('href', url)
    link.setAttribute('download', 'packing_list_template.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  useEffect(() => {
    let active = true

    setLoadingLists(true)
    setListsError(null)
    packingListApi
      .list(0, 50)
      .then((lists) => {
        if (active) setSavedLists(lists)
      })
      .catch((error: unknown) => {
        if (active) {
          setSavedLists([])
          setListsError(error instanceof Error ? error.message : 'Unable to load packing lists')
        }
      })
      .finally(() => {
        if (active) setLoadingLists(false)
      })

    return () => {
      active = false
    }
  }, [packingListVersion])

  const handleSelectSaved = useCallback(async (id: string) => {
    const requestId = ++selectionRequestRef.current
    setSelectionError(null)

    if (!id) {
      onSelectExisting('')
      setPackingListPreview(undefined)
      setSelectingId(null)
      return
    }

    const numericId = Number(id)
    if (!Number.isInteger(numericId) || numericId <= 0) {
      onSelectExisting('')
      setPackingListPreview(undefined)
      setSelectionError('Invalid packing list identifier')
      return
    }

    onSelectExisting(id)
    setPackingListPreview(undefined)
    setSelectingId(id)

    try {
      const fullList = await packingListApi.get(numericId)
      if (requestId !== selectionRequestRef.current) return

      const previewData: PackingListPreview = {
        rows: fullList.rows.map((row: PackingListRow & Partial<PackingListPreviewRow>) => ({
          item_id: row.item_id,
          po_no: row.po_no,
          customer_code: row.customer_code,
          description: row.description || row.item_id,
          qty_cartons: row.qty_cartons,
          length_cm: row.length_cm ?? 0,
          width_cm: row.width_cm ?? 0,
          height_cm: row.height_cm ?? 0,
          weight_kg: row.weight_kg ?? 0,
          this_way_up: row.this_way_up ?? false,
          stacking_group: row.stacking_group ?? 1,
          max_load_bearing_kg: row.max_load_bearing_kg ?? undefined,
        })),
        shipment_type: fullList.shipment_type,
        customer_count: fullList.customer_count,
        total_cartons: fullList.total_cartons,
        total_weight_kg: fullList.total_weight_kg,
        total_volume_cm3: fullList.total_volume_cm3,
      }

      setPackingListPreview(previewData)
      setPackingListMode('existing')
    } catch (error: unknown) {
      if (requestId !== selectionRequestRef.current) return
      onSelectExisting('')
      setPackingListPreview(undefined)
      setSelectionError(error instanceof Error ? error.message : 'Failed to load packing list details')
      toastError('Failed to load packing list details')
    } finally {
      if (requestId === selectionRequestRef.current) setSelectingId(null)
    }
  }, [onSelectExisting, setPackingListMode, setPackingListPreview, toastError])

  const handleFileUpload = async (file: File | undefined) => {
    if (!file) return

    const requestId = ++uploadRequestRef.current
    setUploading(true)
    setSelectionError(null)

    try {
      const result = await packingListApi.uploadAndSaveCsv(file)
      if (requestId !== uploadRequestRef.current) return

      if (result.success && result.preview) {
        setPackingListPreview(result.preview)
        setPackingListMode('upload')
        onSelectExisting('')
        toastSuccess(`Successfully loaded ${result.preview.total_cartons} cartons (${result.preview.rows.length} items) from file`)

        try {
          const updatedLists = await packingListApi.list(0, 50)
          if (requestId === uploadRequestRef.current) setSavedLists(updatedLists)
        } catch (error: unknown) {
          setListsError(error instanceof Error ? error.message : 'Unable to refresh packing lists')
        }
      } else {
        toastError(result.errors?.join(', ') || 'Failed to parse file')
      }
    } catch (error: unknown) {
      if (requestId !== uploadRequestRef.current) return
      toastError(error instanceof Error ? error.message : 'Failed to upload file')
    } finally {
      if (requestId === uploadRequestRef.current) {
        setUploading(false)
        if (fileInputRef.current) fileInputRef.current.value = ''
      }
    }
  const triggerFileInput = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 text-sm font-medium">1</span>
          <h2 className="text-base font-semibold text-slate-900">Select Packing List</h2>
        </div>
      </div>
      <div className="p-5 space-y-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="existing-list">
              Packing List
            </label>
            {selectingId && (
              <span className="text-xs text-slate-500">Loading details...</span>
            )}
          </div>

          <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
            <div className="relative flex-1">
              <select
                id="existing-list"
                className="w-full px-4 py-2.5 pr-10 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none cursor-pointer transition-colors hover:border-slate-400 disabled:opacity-60"
                value={selectedId || ''}
                onChange={(event) => void handleSelectSaved(event.target.value)}
                disabled={loadingLists || Boolean(selectingId)}
              >
                <option value="">-- Select a packing list --</option>
                {loadingLists ? (
                  <option value="" disabled>Loading...</option>
                ) : savedLists.map((pl) => (
                  <option key={pl.id} value={String(pl.id)}>
                    PL-{String(pl.id).padStart(3, '0')} - {pl.name} ({pl.total_cartons} cartons)
                  </option>
                ))}
              </select>
              <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-slate-400">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </div>
            </div>

            <button
              type="button"
              className="btn btn-primary flex items-center justify-center gap-2 whitespace-nowrap px-4 py-2.5"
              onClick={triggerFileInput}
              disabled={uploading}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
              {uploading ? 'Uploading...' : 'Upload CSV'}
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              style={{ display: 'none' }}
              onChange={(e) => e.target.files?.[0] && void handleFileUpload(e.target.files[0])}
            />
          </div>

          {listsError && (
            <div className="mt-2 flex items-center justify-between gap-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              <span>{listsError}</span>
              <button type="button" className="font-medium underline" onClick={() => { setListsError(null); void packingListApi.list(0, 50).then(setSavedLists).catch(() => setListsError('Unable to reload packing lists')) }}>
                Retry
              </button>
            </div>
          )}

          {selectionError && (
            <p className="mt-2 text-sm text-red-700" role="alert">{selectionError}</p>
          )}
        </div>

        <div
          className={`border border-dashed rounded-lg p-3 text-center transition-colors text-xs flex flex-wrap items-center justify-between gap-2 cursor-pointer ${
            isDragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-slate-50 hover:border-slate-300'
          }`}
          onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragActive(true); }}
          onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragActive(false); }}
          onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragActive(true); }}
          onDrop={async (e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragActive(false);
            const files = e.dataTransfer.files;
            if (files.length > 0) {
              await handleFileUpload(files[0]);
            }
          }}
          onClick={triggerFileInput}
        >
          <span className="text-slate-500">
            Or drag &amp; drop a CSV file here (columns: <code>Item_ID, PO_No, Qty_Pcs, Qty_Cartons</code>)
          </span>
          <button
            type="button"
            className="text-blue-600 hover:underline font-medium"
            onClick={(e) => {
              e.stopPropagation();
              handleDownloadTemplate();
            }}
          >
            Download CSV Template
          </button>
        </div>
        
        {preview && (
          <div className="mt-4 pt-4 border-t border-slate-200">
            <div className="flex items-center gap-2 flex-wrap mb-3">
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                preview.shipment_type === 'FCL' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
              }`}>
                {preview.shipment_type === 'FCL' ? 'FCL' : `LCL - ${preview.customer_count} customers`}
              </span>
              <span className="text-sm text-slate-500">
                {preview.total_cartons} cartons &bull; {preview.total_weight_kg.toFixed(1)} kg &bull; {(preview.total_volume_cm3 / 1e6).toFixed(2)} m&sup3;
              </span>
            </div>
            
            <div className="overflow-x-auto" style={{ maxHeight: '200px' }}>
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-50">
                    <th className="px-3 py-2 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Item</th>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">PO</th>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Customer</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600 uppercase tracking-wider text-xs">Qty</th>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Dims (L×W×H) cm</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600 uppercase tracking-wider text-xs">Weight (kg)</th>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600 uppercase tracking-wider text-xs">Stack</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row: PackingListPreviewRow, index: number) => {
                    const isNewGroup = index === 0 ||
                      (preview.rows[index - 1].customer_code !== row.customer_code)
                    return (
                      <tr key={`${row.item_id}-${row.po_no}-${index}`} className={`${isNewGroup && index > 0 ? 'border-t-2 border-blue-500' : ''} hover:bg-slate-50`}>
                        <td className="px-3 py-2 text-slate-700">{row.description}</td>
                        <td className="px-3 py-2 text-slate-700">{row.po_no}</td>
                        <td className="px-3 py-2">
                          {row.customer_code ? (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">{row.customer_code}</span>
                          ) : (
                            <span className="text-slate-400">&mdash;</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right text-slate-700">{row.qty_cartons}</td>
                        <td className="px-3 py-2 font-mono text-sm text-slate-700">{row.length_cm}&times;{row.width_cm}&times;{row.height_cm}</td>
                        <td className="px-3 py-2 text-right text-slate-700">{row.weight_kg}</td>
                        <td className="px-3 py-2 text-slate-700">Group {row.stacking_group}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Step2Container({
  container,
  onSelect,
  canRun,
  isLoading,
  onRun,
}: {
  container: {
    selectedId?: number
    selectedType?: string
  }
  onSelect: (id: number, type: string) => void
  canRun: () => boolean
  isLoading: boolean
  onRun: () => void
}) {
  const [containers, setContainers] = useState<Container[]>([])
  const [loadingContainers, setLoadingContainers] = useState(true)
  const [containersError, setContainersError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    setLoadingContainers(true)
    setContainersError(null)
    containerApi
      .list()
      .then((data) => {
        if (active) setContainers(data)
      })
      .catch((error: unknown) => {
        if (active) setContainersError(error instanceof Error ? error.message : 'Unable to load containers')
      })
      .finally(() => {
        if (active) setLoadingContainers(false)
      })

    return () => {
      active = false
    }
  }, [])

  if (loadingContainers) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm mt-4">
        <div className="px-5 py-4 border-b border-slate-200">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 text-sm font-medium">2</span>
            <h2 className="text-base font-semibold text-slate-900">Select Target Container</h2>
          </div>
        </div>
        <div className="p-5 text-center text-slate-500 py-8">
          Loading containers...
        </div>
      </div>
    )
  }

  if (containersError) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm mt-4 p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Select Target Container</h2>
            <p className="mt-2 text-sm text-red-700" role="alert">{containersError}</p>
          </div>
          <button type="button" className="btn btn-secondary" onClick={() => void containerApi.list().then(setContainers).then(() => setContainersError(null)).catch(() => setContainersError('Unable to reload containers'))}>
            Retry
          </button>
        </div>
      </div>
    )
  }

  const selectedContainer = containers.find((item) => item.id === container.selectedId)
  const hasInvalidSelection = Boolean(container.selectedId) && !selectedContainer
  const isReady = canRun() && Boolean(selectedContainer)

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm mt-4">
      <div className="px-5 py-4 border-b border-slate-200">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 text-sm font-medium">2</span>
          <h2 className="text-base font-semibold text-slate-900">Select Target Container</h2>
        </div>
      </div>
      <div className="p-5">
        <label className="block text-sm font-medium text-slate-700 mb-2" htmlFor="container-select">
          Container
        </label>
        <div className="relative">
          <select
            id="container-select"
            className="w-full px-4 py-3 pr-12 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none cursor-pointer transition-colors hover:border-slate-400 disabled:opacity-60"
            value={container.selectedId ?? ''}
            onChange={(event) => {
              const id = Number(event.target.value)
              const selected = containers.find((item) => item.id === id)
              if (selected) onSelect(selected.id, selected.container_type)
            }}
            disabled={containers.length === 0 || isLoading}
          >
            <option value="" disabled>
              {containers.length === 0 ? 'No containers available' : '-- Select a container --'}
            </option>
            {containers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.container_type} ({item.internal_length_cm}&times;{item.internal_width_cm}&times;{item.internal_height_cm} cm, {item.max_weight_kg.toLocaleString()} kg)
              </option>
            ))}
          </select>
          <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-slate-400">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>
        </div>

        {hasInvalidSelection && (
          <p className="mt-3 text-sm text-amber-700" role="alert">
            The previously selected container is no longer available. Select a container to continue.
          </p>
        )}

        <div className="mt-6 pt-4 border-t border-slate-200">
          <button
            type="button"
            onClick={onRun}
            disabled={!isReady || isLoading}
            className="w-full btn btn-primary btn-lg flex items-center justify-center gap-2 py-3.5 transition-all hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-none disabled:hover:translate-y-0"
          >
            {isLoading && (
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                <path d="M12 2a10 10 0 0 1 10 10" strokeOpacity="1" />
              </svg>
            )}
            {isLoading ? 'Running Optimization...' : 'Execute Loading Plan'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function RunWizard() {
  const {
    packingList,
    container,
    options,
    isRunning,
    progress,
    result,
    setPackingListSelected,
    setContainerSelected,
    setPackingListPreview,
    setPackingListMode,
    setProgress,
    setResult,
    setRunning,
    canRun,
    reset,
  } = useWizardStore()

  const { success: toastSuccess, error: toastError } = useToastStore()
  const [isLoading, setIsLoading] = useState(false)
  const runRequestRef = useRef(0)
  const cancelledRef = useRef(false)

  const handleRun = useCallback(async () => {
    if (!canRun() || !packingList.preview || isLoading) return

    const requestId = ++runRequestRef.current
    const preview = packingList.preview
    const selectedType = container.selectedType
    const runOptions = options
    cancelledRef.current = false

    setIsLoading(true)
    setRunning(true)
    setProgress({
      stage: 'parse',
      progress: 0.05,
      message: 'Parsing inputs...',
    })

    try {
      await Promise.resolve()

      const runData: RunCreateQuick = {
        packing_list: {
          rows: preview.rows.map((row) => ({
            item_id: row.item_id,
            po_no: row.po_no,
            customer_code: row.customer_code,
            description: row.description,
            qty_pcs: row.qty_cartons,
            qty_cartons: row.qty_cartons,
          })),
        },
        container_type: selectedType || '40HC',
        options: {
          population_size: runOptions.population_size,
          generations: runOptions.generations,
          tolerance_gap_cm: runOptions.tolerance_gap_cm,
        },
      }

      const response = await runApi.createQuick(runData)
      if (requestId !== runRequestRef.current || cancelledRef.current) return

      setProgress({
        stage: 'complete',
        progress: 1,
        message: 'Optimization complete',
      })
      setResult(response)
      toastSuccess('Loading plan optimization completed successfully')
    } catch (error: unknown) {
      if (requestId !== runRequestRef.current || cancelledRef.current) return
      toastError(error instanceof Error ? error.message : 'Failed to run loading plan')
    } finally {
      if (requestId === runRequestRef.current) {
        setIsLoading(false)
        setRunning(false)
        setProgress(null)
      }
    }
  }, [canRun, container.selectedType, isLoading, options, packingList.preview, setProgress, setResult, setRunning, toastError, toastSuccess])

  const handleCancelRun = useCallback(() => {
    cancelledRef.current = true
    runRequestRef.current += 1
    setIsLoading(false)
    setRunning(false)
    setProgress(null)
    toastError('Run cancellation is unavailable after submission; the request will continue on the server')
  }, [setProgress, setRunning, toastError])

  const handleNewRun = useCallback(() => {
    cancelledRef.current = true
    runRequestRef.current += 1
    setIsLoading(false)
    setRunning(false)
    setProgress(null)
    reset()
  }, [reset, setProgress, setRunning])

  if (isRunning && progress) {
    return <ProgressView progress={progress} onCancel={handleCancelRun} />
  }

  if (result) {
    return (
      <LoadingPlanViewer
        result={result}
        onNewRun={handleNewRun}
      />
    )
  }

  return (
    <div className="h-full flex flex-col">
      <header className="mb-6 flex-shrink-0">
        <h1 className="text-xl font-bold text-slate-900">Configure Loading Plan</h1>
        <p className="text-sm text-slate-500 mt-1">Select a packing list and container, then execute the optimization.</p>
      </header>

      <main className="flex-1 overflow-y-auto min-h-0">
        <div className="max-w-3xl mx-auto space-y-6">
          <Step1PackingList
            packingList={packingList}
            onSelectExisting={setPackingListSelected}
            setPackingListPreview={setPackingListPreview}
            setPackingListMode={setPackingListMode}
          />
          <Step3_RunOptions options={options} onChange={useWizardStore.getState().setOptions} />
          <Step2Container
            container={container}
            onSelect={setContainerSelected}
            canRun={canRun}
            isLoading={isLoading}
            onRun={() => void handleRun()}
          />
        </div>
      </main>
    </div>
  )
}
