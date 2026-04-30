import HUD from '../HUD'
import Sidebar from './Sidebar'

export default function Layout({ children, fullWidth = false }) {
  return (
    <div className="min-h-screen bg-[#F7F7F7] dark:bg-[#0A0A0A] transition-colors duration-300">
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
