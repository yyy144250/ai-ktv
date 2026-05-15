import { Download, RefreshCw, FileText, Play } from 'lucide-react'

export default function DoneStep({ job, jobId, onReset }) {
  const output = job?.output
  const videoUrl = output?.video_url
  const subtitleUrl = output?.subtitle_url

  return (
    <div className="glass-card p-8">
      <div className="text-center mb-6">
        <div className="text-5xl mb-3">🎉</div>
        <h2 className="text-2xl font-bold text-white mb-2">KTV 视频制作完成！</h2>
        <p className="text-gray-400 text-sm">
          视频已包含伴奏音轨和振り仮名字幕，可直接投屏播放
        </p>
      </div>

      {/* 视频预览 */}
      {videoUrl && (
        <div className="mb-6 rounded-xl overflow-hidden bg-black">
          <video
            src={videoUrl}
            controls
            className="w-full max-h-[400px]"
            poster=""
          >
            您的浏览器不支持视频播放
          </video>
        </div>
      )}

      {/* 下载按钮 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        {videoUrl && (
          <a
            href={`/api/jobs/${jobId}/download`}
            download
            className="flex items-center justify-center gap-2 px-6 py-4 rounded-xl
                       bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600
                       text-white font-medium transition-all shadow-lg shadow-primary-600/20"
          >
            <Download size={20} />
            <span>下载 KTV 视频</span>
          </a>
        )}
        {subtitleUrl && (
          <a
            href={`/api/jobs/${jobId}/subtitle`}
            download
            className="flex items-center justify-center gap-2 px-6 py-4 rounded-xl
                       bg-white/10 hover:bg-white/15 text-white font-medium transition-all border border-white/10"
          >
            <FileText size={20} />
            <span>下载 ASS 字幕</span>
          </a>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="text-center">
        <button onClick={onReset} className="btn-secondary">
          <RefreshCw size={16} className="inline mr-2" />
          制作新视频
        </button>
      </div>

      {/* 使用提示 */}
      <div className="mt-6 p-4 rounded-lg bg-white/5 text-xs text-gray-400">
        <p className="font-medium text-gray-300 mb-2">💡 使用提示</p>
        <ul className="space-y-1 list-disc list-inside">
          <li>视频格式为 MP4 (H.264)，兼容大部分投屏设备</li>
          <li>ASS 字幕文件可在 Aegisub 中进一步编辑</li>
          <li>如果假名标注有误，可返回修正后重新生成</li>
        </ul>
      </div>
    </div>
  )
}
