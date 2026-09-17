import Papa from 'papaparse'
import type { PackingListRow } from '../types/api'

export function parseCSV(text: string): Promise<PackingListRow[]> {
  return new Promise((resolve, reject) => {
    Papa.parse(text, {
      header: true,
      skipEmptyLines: true,
      transformHeader: (header) => header.trim(),
      complete: (results) => {
        const rows: PackingListRow[] = results.data.map((row: any) => ({
          item_id: String(row.Item_ID || row.item_id || '').trim(),
          po_no: String(row.PO_No || row.po_no || '').trim(),
          customer_code: row.Customer_Code || row.customer_code ? String(row.Customer_Code || row.customer_code).trim() : undefined,
          description: row.Description || row.description ? String(row.Description || row.description).trim() : undefined,
          qty_pcs: parseInt(String(row.Qty_Pcs || row.qty_pcs || '0'), 10),
          qty_cartons: parseInt(String(row.Qty_Cartons || row.qty_cartons || '0'), 10),
        }))
        resolve(rows)
      },
      error: (error: Error) => reject(error),
    })
  })
}

export function generateCSVTemplate(): string {
  return 'Item_ID,PO_No,Customer_Code,Description,Qty_Pcs,Qty_Cartons\nDT-8411,PO-1001,CUST-A,Dining Table,4,4\nCH-2205,PO-1001,CUST-A,Chair,8,8'
}

export function downloadCSV(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}

export function validatePackingListRows(rows: PackingListRow[]): string[] {
  const errors: string[] = []
  rows.forEach((row, index) => {
    if (!row.item_id) errors.push(`Row ${index + 1}: Item_ID is required`)
    if (!row.po_no) errors.push(`Row ${index + 1}: PO_No is required`)
    if (row.qty_pcs <= 0) errors.push(`Row ${index + 1}: Qty_Pcs must be > 0`)
    if (row.qty_cartons <= 0) errors.push(`Row ${index + 1}: Qty_Cartons must be > 0`)
  })
  return errors
}