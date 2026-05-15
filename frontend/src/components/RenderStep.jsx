import { Loader2, Film } from 'lucide-react'

export default function RenderStep({ progress, message }) {
  return (
    <div className="glass-card p-8 text-center">
      <div className="text-4xl mb-4">🎬</div>
      <h2 className="text-xl font-semibold text-white mb-2">正在生成 KTV 视频</h2>
      <p className="text-gray-400 text-sm mb-6">{message || '合成中...'}</p>

      {/* 进度条 */}
      <div className="max-w-md mx-auto mb-6">
        <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-primary-500 via-accent-500 to-primary-500 rounded-full transition-all duration-500 ease-out
                       bg-[length:200%_100%] animate-[shimmer_2s_linear_infinite]"
            style={{ width: `${Math.max(2, progress)}%` }}
          />
        </div>
        <div className="flex justify-between mt-2 text-xs text-gray-500">
          <span>字幕生成</span>
          <span>{progress}%</span>
          <span>视频编码</span>
        </div>
      </div>

      <Loader2 size={24} className="text-accent-400 animate-spin mx-auto" />

      <div className="mt-6 text-xs text-gray-600 space-y-1">
        <p>正在将字幕烧入视频画面...</p>
        <p>视频越长，处理时间越久</p>
      </div>
    </div>
  )
}
