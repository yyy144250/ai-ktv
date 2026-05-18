import { Loader2, RefreshCw, ArrowLeft } from 'lucide-react'

export default function RenderStep({ progress, message, error, onRetry, onBack }) {
  return (
    <div className="glass-card p-8 text-center">
      <div className="text-4xl mb-4">🎬</div>
      <h2 className="text-xl font-semibold text-white mb-2">
        {error ? '视频合成失败' : '正在生成 KTV 视频'}
      </h2>
      <p className="text-gray-400 text-sm mb-6">{message || '合成中...'}</p>

      {/* 进度条 */}
      <div className="max-w-md mx-auto mb-6">
        <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              error
                ? 'bg-red-500'
                : 'bg-gradient-to-r from-primary-500 via-accent-500 to-primary-500 bg-[length:200%_100%] animate-[shimmer_2s_linear_infinite]'
            }`}
            style={{ width: `${Math.max(2, progress)}%` }}
          />
        </div>
        <div className="flex justify-between mt-2 text-xs text-gray-500">
          <span>字幕生成</span>
          <span>{progress}%</span>
          <span>视频编码</span>
        </div>
      </div>

      {/* 失败时显示重试和返回 */}
      {error ? (
        <div className="flex justify-center gap-3 mt-4">
          {onRetry && (
            <button onClick={onRetry} className="btn-primary text-sm flex items-center gap-1.5">
              <RefreshCw size={14} />
              重试合成
            </button>
          )}
          {onBack && (
            <button onClick={onBack} className="btn-secondary text-sm flex items-center gap-1.5">
              <ArrowLeft size={14} />
              返回编辑歌词
            </button>
          )}
        </div>
      ) : (
        <>
          <Loader2 size={24} className="text-accent-400 animate-spin mx-auto" />
          <div className="mt-6 text-xs text-gray-600 space-y-1">
            <p>正在将字幕嵌入视频...</p>
            <p>视频越长，处理时间越久</p>
          </div>
        </>
      )}
    </div>
  )
}
