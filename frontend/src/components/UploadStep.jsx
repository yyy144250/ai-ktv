import { useState, useRef } from 'react'
import { Upload, Film, Loader2 } from 'lucide-react'

export default function UploadStep({ onUpload, loading }) {
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) onUpload(file)
  }

  const handleChange = (e) => {
    const file = e.target.files[0]
    if (file) onUpload(file)
  }

  return (
    <div className="glass-card p-8">
      <div
        className={`border-2 border-dashed rounded-xl p-12 text-center transition-all cursor-pointer
          ${dragOver
            ? 'border-primary-400 bg-primary-600/10'
            : 'border-gray-600 hover:border-gray-400 hover:bg-white/5'
          }
          ${loading ? 'pointer-events-none opacity-60' : ''}
        `}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".mp4,.mkv,.avi,.webm,.mov,.flv,.wmv"
          onChange={handleChange}
          className="hidden"
        />

        {loading ? (
          <div className="flex flex-col items-center gap-4">
            <Loader2 size={48} className="text-primary-400 animate-spin" />
            <p className="text-gray-300">上传中...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center">
              <Film size={32} className="text-primary-300" />
            </div>
            <div>
              <p className="text-lg font-medium text-white">拖拽或点击上传 MV 视频</p>
              <p className="text-sm text-gray-400 mt-1">
                支持 MP4, MKV, AVI, WebM, MOV 格式
              </p>
            </div>
            <button className="btn-primary mt-2" disabled={loading}>
              <Upload size={16} className="inline mr-2" />
              选择文件
            </button>
          </div>
        )}
      </div>

      {/* 使用说明 */}
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4 text-center text-xs text-gray-400">
        <div className="p-3 rounded-lg bg-white/5">
          <div className="text-lg mb-1">🎵</div>
          <p>AI 去除人声</p>
          <p className="text-gray-500">Demucs 深度学习模型</p>
        </div>
        <div className="p-3 rounded-lg bg-white/5">
          <div className="text-lg mb-1">あ</div>
          <p>自动振り仮名标注</p>
          <p className="text-gray-500">汉字→假名 自动注音</p>
        </div>
        <div className="p-3 rounded-lg bg-white/5">
          <div className="text-lg mb-1">🎬</div>
          <p>KTV 风格字幕</p>
          <p className="text-gray-500">逐字变色 + 假名标注</p>
        </div>
      </div>
    </div>
  )
}
