import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { ToastProvider, ToastContainer } from './Toast'

// Lucide-style SVG icons (inline to avoid extra dependencies)
export const Icons = {
  Package: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
      <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
      <line x1="12" y1="22.08" x2="12" y2="12"></line>
    </svg>
  ),
  Home: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
      <polyline points="9 22 9 12 15 12 15 22"></polyline>
    </svg>
  ),
  Play: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="5 3 19 12 5 21 5 3"></polygon>
    </svg>
  ),
  Clock: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"></circle>
      <polyline points="12 6 12 12 16 14"></polyline>
    </svg>
  ),
  Database: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
    </svg>
  ),
  ChevronDown: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
  ),
  ChevronRight: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6"></polyline>
    </svg>
  ),
  ChevronLeft: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6"></polyline>
    </svg>
  ),
  Box: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
    </svg>
  ),
  Truck: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 19H5a2 2 0 0 1 0-4h15v-4H4a2 2 0 0 1 0-4h3"></path>
      <circle cx="6" cy="19" r="2"></circle>
      <circle cx="18" cy="19" r="2"></circle>
    </svg>
  ),
  FileText: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
      <polyline points="14 2 14 8 20 8"></polyline>
      <line x1="16" y1="13" x2="8" y2="13"></line>
      <line x1="16" y1="17" x2="8" y2="17"></line>
      <line x1="10" y1="9" x2="8" y2="9"></line>
    </svg>
  ),
  User: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path>
      <circle cx="12" cy="7" r="4"></circle>
    </svg>
  ),
  Settings: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"></circle>
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
    </svg>
  ),
  LogOut: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
      <polyline points="16 17 21 12 16 7"></polyline>
      <line x1="21" y1="12" x2="9" y2="12"></line>
    </svg>
  ),
  Plus: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19"></line>
      <line x1="5" y1="12" x2="19" y2="12"></line>
    </svg>
  ),
  Upload: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
      <polyline points="17 8 12 3 7 8"></polyline>
      <line x1="12" y1="3" x2="12" y2="15"></line>
    </svg>
  ),
  RotateCcw: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 4v6h6"></path>
      <path d="M23 20v-6h-6"></path>
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
    </svg>
  ),
}

interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  children?: NavItem[]
}

const navItems: NavItem[] = [
  { label: 'New Run', path: '/', icon: <Icons.Play /> },
  { label: 'Run History', path: '/history', icon: <Icons.Clock /> },
  {
    label: 'Data Management',
    path: '/data',
    icon: <Icons.Database />,
    children: [
      { label: 'Items', path: '/data/items', icon: <Icons.Box /> },
      { label: 'Containers', path: '/data/containers', icon: <Icons.Truck /> },
      { label: 'Packing Lists', path: '/data/packing-lists', icon: <Icons.FileText /> },
    ],
  },
]

export function Layout() {
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set(['/data']))
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const location = useLocation()

  const toggleGroup = (path: string) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }

  const isGroupExpanded = (path: string) => !collapsedGroups.has(path)
  const isActive = (path: string) => location.pathname === path || location.pathname.startsWith(path + '/')

  return (
    <ToastProvider>
      <div className="h-screen overflow-hidden flex bg-slate-50">
        <aside
          className={`bg-white border-r border-slate-200 flex flex-col h-full sticky top-0 z-50 transition-all duration-200 ${
            sidebarCollapsed ? 'w-20' : 'w-64'
          }`}
        >
          <div className="p-4 border-b border-slate-200">
            <div className="flex items-center gap-3">
              <span className="text-primary">
                <Icons.Package />
              </span>
              {!sidebarCollapsed && (
                <span className="text-lg font-semibold text-slate-900">
                  3D Loading DSS
                </span>
              )}
              <button
                className={`ml-auto p-1.5 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors ${
                  sidebarCollapsed ? 'ml-0' : ''
                }`}
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {sidebarCollapsed ? <Icons.ChevronRight /> : <Icons.ChevronLeft />}
              </button>
            </div>
          </div>

          <nav className="flex-1 p-4" aria-label="Main navigation">
            <ul className="list-none p-0 m-0">
              {navItems.map((item) => {
                const hasChildren = item.children && item.children.length > 0
                const expanded = isGroupExpanded(item.path)
                const active = isActive(item.path)

                return (
                  <li key={item.path} className="mb-2">
                    {hasChildren ? (
                      <>
                        {!sidebarCollapsed && (
                          <>
                            <button
                              onClick={() => toggleGroup(item.path)}
                              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                                active ? 'bg-blue-50 text-blue-600' : 'text-slate-600 hover:bg-slate-100'
                              }`}
                              aria-expanded={expanded}
                            >
                              <span className="flex-shrink-0">{item.icon}</span>
                              <span className="flex-1">{item.label}</span>
                              {expanded ? <Icons.ChevronDown /> : <Icons.ChevronRight />}
                            </button>
                            {expanded && (
                              <ul className="list-none m-0 pt-2 pl-9">
                                {item.children!.map((child) => (
                                  <li key={child.path} className="mb-1">
                                    <NavLink
                                      to={child.path}
                                      className={({ isActive }) => `
                                        flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-all
                                        ${isActive
                                          ? 'text-blue-600 bg-blue-50 font-semibold'
                                          : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700 font-normal'
                                        }
                                      `}
                                    >
                                      <span className="flex-shrink-0">{child.icon}</span>
                                      {child.label}
                                    </NavLink>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </>
                        )}
                        {sidebarCollapsed && (
                          <button
                            className={`w-full flex items-center justify-center px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                              active ? 'bg-blue-50 text-blue-600' : 'text-slate-600 hover:bg-slate-100'
                            }`}
                            title={item.label}
                          >
                            <span className="flex-shrink-0">{item.icon}</span>
                          </button>
                        )}
                      </>
                    ) : (
                      <NavLink
                        to={item.path}
                        className={({ isActive }) => `
                          flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all
                          ${isActive
                            ? 'text-blue-600 bg-blue-50 font-semibold'
                            : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 font-normal'
                          }
                          ${sidebarCollapsed ? 'justify-center' : ''}
                        `}
                        title={sidebarCollapsed ? item.label : undefined}
                      >
                        <span className="flex-shrink-0">{item.icon}</span>
                        {!sidebarCollapsed && <span>{item.label}</span>}
                      </NavLink>
                    )}
                  </li>
                )
              })}
            </ul>
          </nav>

          {!sidebarCollapsed && (
            <div className="p-4 border-t border-slate-200">
              <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-slate-50 mb-3">
                <div className="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                  <Icons.User />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-900 truncate">
                    Tien T.
                  </div>
                  <div className="text-xs text-slate-500">Planner</div>
                </div>
              </div>
              <div className="flex gap-2">
                <button className="btn btn-ghost btn-sm flex items-center justify-center gap-2 flex-1">
                  <Icons.Settings />
                  <span>Settings</span>
                </button>
                <button className="btn btn-ghost btn-sm flex items-center justify-center gap-2 flex-1">
                  <Icons.LogOut />
                  <span>Logout</span>
                </button>
              </div>
            </div>
          )}
        </aside>

        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="overflow-x-hidden p-6 bg-slate-50">
            <Outlet />
          </div>
        </main>
      </div>
      <ToastContainer />
    </ToastProvider>
  )
}