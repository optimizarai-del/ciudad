import HUD from '../HUD'
import Sidebar from './Sidebar'

export default function Layout({ children, fullWidth = false }) {
  return (
    <div className="min-h-screen bg-bg">
      <HUD />
      <div className="flex">
        <Sidebar />
        <main className={`flex-1 overflow-x-hidden ${fullWidth ? '' : 'px-10 py-12'}`}>
          {children}
        </main>
      </div>
    </div>
  )
}
