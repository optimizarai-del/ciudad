import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import HUD from '../HUD'
import Sidebar from './Sidebar'

/**
 * Layout principal con sidebar fijo en desktop y drawer en mobile/tablet.
 *
 * Breakpoints:
 *   < 1024px (lg): sidebar oculto por default, se abre con hamburger del HUD,
 *                  overlay con backdrop. Cierra al navegar.
 *   >= 1024px:     sidebar fijo lateral, layout flex normal.
 */
export default function Layout({ children, fullWidth = false }) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { pathname } = useLocation()

  // Cerrar drawer al navegar
  useEffect(() => { setDrawerOpen(false) }, [pathname])

  // Cerrar con Escape
  useEffect(() => {
    if (!drawerOpen) return
    const onEsc = e => { if (e.key === 'Escape') setDrawerOpen(false) }
    document.addEventListener('keydown', onEsc)
    return () => document.removeEventListener('keydown', onEsc)
  }, [drawerOpen])

  return (
    <div className="min-h-screen bg-[#F7F7F7] dark:bg-[#0A0A0A] transition-colors duration-300">
      <HUD onToggleSidebar={() => setDrawerOpen(o => !o)} drawerOpen={drawerOpen} />

      <div className="flex">
        {/* Sidebar desktop fijo */}
        <div className="hidden lg:block">
          <Sidebar />
        </div>

        {/* Drawer mobile/tablet con backdrop */}
        {drawerOpen && (
          <>
            <div
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 lg:hidden animate-fade-in"
              onClick={() => setDrawerOpen(false)}
            />
            <div
              className="fixed top-12 left-0 bottom-0 z-50 lg:hidden animate-slide-in-left"
              style={{ animation: 'slideInLeft 200ms ease-out' }}
            >
              <Sidebar onNavigate={() => setDrawerOpen(false)} />
            </div>
          </>
        )}

        <main className={`flex-1 overflow-x-hidden ${
          fullWidth ? '' : 'px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-12'
        }`}>
          {children}
        </main>
      </div>

      <style>{`
        @keyframes slideInLeft {
          from { transform: translateX(-100%); }
          to   { transform: translateX(0); }
        }
      `}</style>
    </div>
  )
}
