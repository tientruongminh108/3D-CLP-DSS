import { useState } from 'react'
import { ItemMasterTable } from './ItemMasterTable'
import { ContainerTable } from './ContainerTable'

export function DataManagement() {
  const [activeTab, setActiveTab] = useState<'items' | 'containers'>('items')

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Data Management</h1>

      <div className="data-management-tabs">
        <button
          className={`data-tab ${activeTab === 'items' ? 'active' : ''}`}
          onClick={() => setActiveTab('items')}
        >
          Item Master
        </button>
        <button
          className={`data-tab ${activeTab === 'containers' ? 'active' : ''}`}
          onClick={() => setActiveTab('containers')}
        >
          Containers
        </button>
      </div>

      {activeTab === 'items' && <ItemMasterTable />}
      {activeTab === 'containers' && <ContainerTable />}
    </div>
  )
}