import { Music4 } from 'lucide-react'

export default function Header() {
  return (
    <header className="text-center mb-10">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-accent-500 mb-4 shadow-lg shadow-primary-500/30">
        <Music4 size={32} className="text-white" />
      </div>
      <h1 className="text-3xl font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
        AI-KTV
      </h1>
      <p className="text-gray-400 mt-2 text-sm">
        上传 MV → 去人声 → 日本語字幕（振り仮名付き） → KTV 動画
      </p>
    </header>
  )
}
