import { useState } from 'react'
import { Mic, Keyboard, Loader2 } from 'lucide-react'

export default function LyricsStep({ onSubmit, onRecognize, recognizing, progress, message }) {
  const [mode, setMode] = useState(null) // null | 'manual' | 'ai'
  const [text, setText] = useState('')
  const [format, setFormat] = useState('plain')

  if (recognizing) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="text-4xl mb-4">🎤</div>
        <h2 className="text-xl font-semibold text-white mb-2">AI 歌词识别中</h2>
        <p className="text-gray-400 text-sm mb-6">{message || '正在使用 Whisper 识别日语歌词...'}</p>
        <div className="max-w-md mx-auto">
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary-500 to-accent-500 rounded-full transition-all duration-500"
              style={{ width: `${Math.max(2, progress)}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-2">{progress}%</p>
        </div>
        <Loader2 size={24} className="text-primary-400 animate-spin mx-auto mt-6" />
        <p className="text-xs text-gray-600 mt-4">
          首次加载 Whisper 模型可能较慢，请耐心等待...
        </p>
      </div>
    )
  }

  if (!mode) {
    return (
      <div className="glass-card p-8">
        <h2 className="text-xl font-semibold text-white text-center mb-2">歌词来源</h2>
        <p className="text-gray-400 text-sm text-center mb-8">
          人声分离完成！请选择歌词输入方式
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* AI 识别 */}
          <button
            onClick={onRecognize}
            className="p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-primary-600/10 hover:border-primary-500/30 transition-all text-left group"
          >
            <div className="w-12 h-12 rounded-lg bg-primary-600/20 flex items-center justify-center mb-4 group-hover:bg-primary-600/30">
              <Mic size={24} className="text-primary-400" />
            </div>
            <h3 className="font-medium text-white mb-1">🤖 AI 自动识别</h3>
            <p className="text-xs text-gray-400">
              使用 Whisper 从人声中自动识别日语歌词，并自动对齐时间轴
            </p>
            <span className="text-xs text-primary-400 mt-2 inline-block">推荐 · 全自动</span>
          </button>

          {/* 手动输入 */}
          <button
            onClick={() => setMode('manual')}
            className="p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 hover:border-white/20 transition-all text-left group"
          >
            <div className="w-12 h-12 rounded-lg bg-white/10 flex items-center justify-center mb-4 group-hover:bg-white/15">
              <Keyboard size={24} className="text-gray-300" />
            </div>
            <h3 className="font-medium text-white mb-1">✍️ 手动输入/粘贴</h3>
            <p className="text-xs text-gray-400">
              粘贴已有歌词文本，支持纯文本、LRC、ASS 格式
            </p>
            <span className="text-xs text-gray-500 mt-2 inline-block">适合有现成歌词时</span>
          </button>
        </div>
      </div>
    )
  }

  // 手动输入模式
  return (
    <div className="glass-card p-8">
      <h2 className="text-xl font-semibold text-white mb-4">输入歌词</h2>

      {/* 格式选择 */}
      <div className="flex gap-2 mb-4">
        {[
          { value: 'plain', label: '纯文本' },
          { value: 'lrc', label: 'LRC 格式' },
          { value: 'ass', label: 'ASS 格式' },
        ].map(opt => (
          <button
            key={opt.value}
            onClick={() => setFormat(opt.value)}
            className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
              format === opt.value
                ? 'bg-primary-600 text-white'
                : 'bg-white/10 text-gray-400 hover:bg-white/15'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* 歌词输入框 */}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={
          format === 'plain'
            ? '每行一句歌词，例如：\n夜に駆ける\n沈むように溶けてゆくように\n二人だけの空が広がる夜に'
            : format === 'lrc'
            ? '[00:15.00]夜に駆ける\n[00:18.50]沈むように溶けてゆくように\n[00:22.00]二人だけの空が広がる夜に'
            : 'Dialogue: 0,0:00:15.00,0:00:18.50,Default,,0,0,0,,夜に駆ける'
        }
        className="w-full h-64 p-4 rounded-xl bg-black/30 border border-white/10 text-white text-sm font-mono
                   placeholder:text-gray-600 focus:outline-none focus:border-primary-500/50 resize-none"
      />

      <div className="flex justify-between items-center mt-4">
        <button onClick={() => setMode(null)} className="btn-secondary text-sm">
          ← 返回选择
        </button>
        <button
          onClick={() => onSubmit(text, format)}
          disabled={!text.trim()}
          className="btn-primary"
        >
          提交歌词（自动标注假名）
        </button>
      </div>
    </div>
  )
}
