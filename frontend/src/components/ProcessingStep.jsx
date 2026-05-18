import { Loader2, RefreshCw, ArrowLeft } from 'lucide-react'

export default function ProcessingStep({ title, progress, message, icon, error, onRetry, onBack }) {
  return (
    <div className="glass-card p-8 text-center">
      <div className="text-4xl mb-4">{icon}</div>
      <h2 className="text-xl font-semibold text-white mb-2">{title}</h2>
      <p className="text-gray-400 text-sm mb-6">{message}</p>

      {/* 进度条 */}
      <div className="max-w-md mx-auto">
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              error ? 'bg-red-500' : 'bg-gradient-to-r from-primary-500 to-accent-500'
            }`}
            style={{ width: `${Math.max(2, progress)}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-2">{progress}%</p>
      </div>

      {/* 失败时显示重试和返回 */}
      {error ? (
        <div className="flex justify-center gap-3 mt-6">
          {onRetry && (
            <button onClick={onRetry} className="btn-primary text-sm flex items-center gap-1.5">
              <RefreshCw size={14} />
              重试
            </button>
          )}
          {onBack && (
            <button onClick={onBack} className="btn-secondary text-sm flex items-center gap-1.5">
              <ArrowLeft size={14} />
              返回上一步
            </button>
          )}
        </div>
      ) : (
        <>
          {/* 加载动画 */}
          <div className="flex justify-center mt-6">
            <Loader2 size={24} className="text-primary-400 animate-spin" />
          </div>
          <p className="text-xs text-gray-600 mt-4">
            处理可能需要几分钟，请耐心等待...
          </p>
        </>
      )}
    </div>
  )
}
