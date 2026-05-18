import { useState } from 'react'
import { Mic, Keyboard, Search, Loader2, Music, Clock, ChevronRight, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react'

// 分离状态横幅组件
function SeparationBanner({ status, progress, message, onRetry }) {
  if (status === 'idle') return null

  if (status === 'running') {
    return (
      <div className="mb-6 p-3 rounded-xl bg-blue-500/10 border border-blue-500/20">
        <div className="flex items-center gap-3">
          <Loader2 size={16} className="text-blue-400 animate-spin flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-blue-300">{message || '人声分离中...'}</span>
              <span className="text-xs text-blue-400 font-mono">{progress}%</span>
            </div>
            <div className="h-1.5 bg-blue-900/30 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-500"
                style={{ width: `${Math.max(2, progress)}%` }}
              />
            </div>
          </div>
        </div>
        <p className="text-xs text-blue-400/60 mt-2 ml-7">分离完成后可使用 AI 识别功能，搜索和手动输入不受影响</p>
      </div>
    )
  }

  if (status === 'done') {
    return (
      <div className="mb-6 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
        <div className="flex items-center gap-2">
          <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0" />
          <span className="text-sm text-emerald-300">人声分离完成，所有功能可用</span>
        </div>
      </div>
    )
  }

  if (status === 'failed') {
    return (
      <div className="mb-6 p-3 rounded-xl bg-red-500/10 border border-red-500/20">
        <div className="flex items-center gap-2">
          <AlertCircle size={16} className="text-red-400 flex-shrink-0" />
          <span className="text-sm text-red-300 flex-1">{message || '人声分离失败'}</span>
          {onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-1 px-3 py-1 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 text-xs font-medium transition-all flex-shrink-0"
            >
              <RefreshCw size={12} />
              重试
            </button>
          )}
        </div>
      </div>
    )
  }

  return null
}

export default function LyricsStep({
  onSubmit, onRecognize, onSearchLyrics, onFetchLyrics,
  recognizing, progress, message,
  separationStatus, separationProgress, separationMessage,
  onRetrySeparation,
}) {
  const [mode, setMode] = useState(null) // null | 'search' | 'manual' | 'ai'
  const [text, setText] = useState('')
  const [format, setFormat] = useState('plain')

  // 搜索状态
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchArtist, setSearchArtist] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [fetching, setFetching] = useState(null) // 正在获取的歌曲ID

  const separationDone = separationStatus === 'done'

  // AI 识别中
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

  // 模式选择
  if (!mode) {
    return (
      <div className="glass-card p-8">
        <h2 className="text-xl font-semibold text-white text-center mb-2">歌词来源</h2>
        <p className="text-gray-400 text-sm text-center mb-6">
          请选择歌词输入方式，可以边等人声分离边搜索歌词
        </p>

        {/* 分离状态横幅 */}
        <SeparationBanner
          status={separationStatus}
          progress={separationProgress}
          message={separationMessage}
          onRetry={onRetrySeparation}
        />

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* 搜索在线歌词 */}
          <button
            onClick={() => setMode('search')}
            className="p-6 rounded-xl border border-primary-500/30 bg-primary-600/10 hover:bg-primary-600/20 hover:border-primary-500/50 transition-all text-left group"
          >
            <div className="w-12 h-12 rounded-lg bg-primary-600/20 flex items-center justify-center mb-4 group-hover:bg-primary-600/30">
              <Search size={24} className="text-primary-400" />
            </div>
            <h3 className="font-medium text-white mb-1">🔍 搜索在线歌词</h3>
            <p className="text-xs text-gray-400">
              从网易云等平台搜索带时间轴的 LRC 歌词，自动导入
            </p>
            <span className="text-xs text-primary-400 mt-2 inline-block">推荐 · 最省力最准</span>
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
            <span className="text-xs text-gray-500 mt-2 inline-block">适合有现成歌词</span>
          </button>

          {/* AI 识别 */}
          <button
            onClick={separationDone ? onRecognize : undefined}
            disabled={!separationDone}
            className={`p-6 rounded-xl border transition-all text-left group relative ${
              separationDone
                ? 'border-white/10 bg-white/5 hover:bg-white/10 hover:border-white/20 cursor-pointer'
                : 'border-white/5 bg-white/[0.02] cursor-not-allowed opacity-60'
            }`}
          >
            <div className={`w-12 h-12 rounded-lg flex items-center justify-center mb-4 ${
              separationDone ? 'bg-white/10 group-hover:bg-white/15' : 'bg-white/5'
            }`}>
              <Mic size={24} className={separationDone ? 'text-gray-300' : 'text-gray-600'} />
            </div>
            <h3 className={`font-medium mb-1 ${separationDone ? 'text-white' : 'text-gray-500'}`}>
              🤖 AI 自动识别
            </h3>
            <p className={`text-xs ${separationDone ? 'text-gray-400' : 'text-gray-600'}`}>
              使用 Whisper 从人声中自动识别日语歌词并对齐
            </p>
            {separationDone ? (
              <span className="text-xs text-gray-500 mt-2 inline-block">全自动 · 需要对齐</span>
            ) : (
              <span className="text-xs text-amber-500/70 mt-2 inline-flex items-center gap-1">
                <Loader2 size={10} className="animate-spin" />
                等待人声分离完成...
              </span>
            )}
          </button>
        </div>
      </div>
    )
  }

  // ========== 搜索在线歌词模式 ==========
  if (mode === 'search') {
    const handleSearch = async () => {
      if (!searchKeyword.trim()) return
      setSearching(true)
      setSearchResults([])
      try {
        const results = await onSearchLyrics(searchKeyword.trim(), searchArtist.trim())
        setSearchResults(results)
      } finally {
        setSearching(false)
      }
    }

    const handleSelect = async (song) => {
      setFetching(song.id)
      try {
        await onFetchLyrics(song.source, song.id)
      } finally {
        setFetching(null)
      }
    }

    const formatDuration = (sec) => {
      if (!sec) return ''
      const m = Math.floor(sec / 60)
      const s = sec % 60
      return `${m}:${String(s).padStart(2, '0')}`
    }

    return (
      <div className="glass-card p-8">
        <h2 className="text-xl font-semibold text-white mb-4">🔍 搜索在线歌词</h2>
        <p className="text-gray-400 text-sm mb-6">
          输入歌曲名搜索带时间轴的 LRC 歌词，选择后自动导入
        </p>

        {/* 分离状态横幅 */}
        <SeparationBanner
          status={separationStatus}
          progress={separationProgress}
          message={separationMessage}
          onRetry={onRetrySeparation}
        />

        {/* 搜索表单 */}
        <div className="flex gap-3 mb-6">
          <input
            type="text"
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="歌曲名（如：可愛くてごめん）"
            className="flex-1 px-4 py-3 rounded-xl bg-black/30 border border-white/10 text-white text-sm
                       placeholder:text-gray-600 focus:outline-none focus:border-primary-500/50"
          />
          <input
            type="text"
            value={searchArtist}
            onChange={(e) => setSearchArtist(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="歌手名（可选）"
            className="w-40 px-4 py-3 rounded-xl bg-black/30 border border-white/10 text-white text-sm
                       placeholder:text-gray-600 focus:outline-none focus:border-primary-500/50"
          />
          <button
            onClick={handleSearch}
            disabled={searching || !searchKeyword.trim()}
            className="btn-primary px-6 flex items-center gap-2"
          >
            {searching ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Search size={16} />
            )}
            搜索
          </button>
        </div>

        {/* 搜索结果 */}
        {searching && (
          <div className="text-center py-8">
            <Loader2 size={28} className="text-primary-400 animate-spin mx-auto mb-3" />
            <p className="text-gray-400 text-sm">正在搜索...</p>
          </div>
        )}

        {!searching && searchResults.length > 0 && (
          <div className="space-y-2 mb-6">
            <p className="text-xs text-gray-500 mb-3">找到 {searchResults.length} 个结果，点击选择：</p>
            {searchResults.map((song) => (
              <button
                key={song.id}
                onClick={() => handleSelect(song)}
                disabled={fetching !== null}
                className="w-full p-4 rounded-xl border border-white/10 bg-white/5 hover:bg-primary-600/10
                           hover:border-primary-500/30 transition-all text-left flex items-center gap-4 group
                           disabled:opacity-50 disabled:cursor-wait"
              >
                <div className="w-10 h-10 rounded-lg bg-primary-600/20 flex items-center justify-center flex-shrink-0">
                  {fetching === song.id ? (
                    <Loader2 size={18} className="text-primary-400 animate-spin" />
                  ) : (
                    <Music size={18} className="text-primary-400" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-white text-sm truncate">{song.title}</div>
                  <div className="text-xs text-gray-400 truncate">
                    {song.artist}
                    {song.album && <span className="text-gray-600"> · {song.album}</span>}
                  </div>
                </div>
                {song.duration > 0 && (
                  <div className="flex items-center gap-1 text-xs text-gray-500 flex-shrink-0">
                    <Clock size={12} />
                    {formatDuration(song.duration)}
                  </div>
                )}
                <ChevronRight size={16} className="text-gray-600 group-hover:text-primary-400 flex-shrink-0" />
              </button>
            ))}
          </div>
        )}

        {!searching && searchResults.length === 0 && searchKeyword && (
          <div className="text-center py-6 text-gray-500 text-sm">
            没有找到结果，试试换个关键词或使用手动输入
          </div>
        )}

        <div className="flex justify-between items-center mt-4">
          <button onClick={() => { setMode(null); setSearchResults([]) }} className="btn-secondary text-sm">
            ← 返回选择
          </button>
          <button
            onClick={() => { setMode('manual'); setSearchResults([]) }}
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            切换到手动输入 →
          </button>
        </div>
      </div>
    )
  }

  // ========== 手动输入模式 ==========
  return (
    <div className="glass-card p-8">
      <h2 className="text-xl font-semibold text-white mb-4">输入歌词</h2>

      {/* 分离状态横幅 */}
      <SeparationBanner
        status={separationStatus}
        progress={separationProgress}
        message={separationMessage}
        onRetry={onRetrySeparation}
      />

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
