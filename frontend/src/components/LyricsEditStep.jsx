import { useState } from 'react'
import { Edit3, Clock, Film } from 'lucide-react'

export default function LyricsEditStep({ job, onUpdate, onAlign, onRender }) {
  const [editing, setEditing] = useState(null) // 编辑中的行索引
  const [editReading, setEditReading] = useState('')
  const [style, setStyle] = useState('classic_blue')

  const lyrics = job?.lyrics
  const lines = lyrics?.lines || []
  const isAligned = lyrics?.aligned

  // 修改某行某字的假名
  const handleEditFurigana = (lineIdx, charIdx, newReading) => {
    const updatedLines = [...lines]
    const ruby = [...updatedLines[lineIdx].ruby]
    ruby[charIdx] = { ...ruby[charIdx], reading: newReading }
    updatedLines[lineIdx] = { ...updatedLines[lineIdx], ruby }
    onUpdate(updatedLines)
  }

  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-white">歌词预览 & 编辑</h2>
        <div className="flex gap-2">
          {!isAligned && (
            <button onClick={onAlign} className="btn-primary text-sm">
              <Clock size={14} className="inline mr-1" />
              自动对齐时间轴
            </button>
          )}
          {isAligned && (
            <button onClick={() => onRender({ style })} className="btn-accent text-sm">
              <Film size={14} className="inline mr-1" />
              生成 KTV 视频
            </button>
          )}
        </div>
      </div>

      {/* 字幕样式选择 */}
      {isAligned && (
        <div className="flex gap-2 mb-4">
          <span className="text-xs text-gray-400 self-center">样式:</span>
          {[
            { value: 'classic_blue', label: '蓝白经典', color: 'bg-blue-500' },
            { value: 'pink', label: '粉红', color: 'bg-pink-500' },
            { value: 'gold', label: '金色', color: 'bg-yellow-500' },
          ].map(s => (
            <button
              key={s.value}
              onClick={() => setStyle(s.value)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-all ${
                style === s.value
                  ? 'bg-white/20 text-white ring-1 ring-white/30'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${s.color}`} />
              {s.label}
            </button>
          ))}
        </div>
      )}

      {/* 状态提示 */}
      <div className={`text-xs px-3 py-2 rounded-lg mb-4 ${
        isAligned ? 'bg-green-500/10 text-green-400' : 'bg-yellow-500/10 text-yellow-400'
      }`}>
        {isAligned
          ? '✅ 时间轴已对齐，可以生成视频'
          : '⚠️ 时间轴尚未对齐，请先对齐或直接生成（如已有 LRC 时间信息）'
        }
      </div>

      {/* 歌词列表 */}
      <div className="space-y-3 max-h-[450px] overflow-y-auto pr-2">
        {lines.map((line, lineIdx) => (
          <div
            key={lineIdx}
            className="group p-3 rounded-lg bg-black/20 border border-white/5 hover:border-white/10 transition-all"
          >
            {/* 时间信息 */}
            {line.start_time != null && (
              <div className="text-[10px] text-gray-500 mb-1 font-mono">
                {formatTime(line.start_time)} → {formatTime(line.end_time)}
              </div>
            )}

            {/* 假名 + 歌词展示 (Ruby) */}
            <div className="text-lg leading-relaxed">
              {(line.ruby || []).map((item, charIdx) => (
                <ruby
                  key={charIdx}
                  className="cursor-pointer hover:bg-primary-600/20 rounded px-0.5 transition-colors"
                  onClick={() => {
                    if (item.reading || isKanji(item.char)) {
                      setEditing({ lineIdx, charIdx })
                      setEditReading(item.reading || '')
                    }
                  }}
                >
                  {item.char}
                  {item.reading && <rt className="text-gray-400">{item.reading}</rt>}
                </ruby>
              ))}
            </div>

            {/* 编辑假名弹出 */}
            {editing?.lineIdx === lineIdx && (
              <div className="mt-2 flex items-center gap-2 p-2 rounded bg-primary-900/30 border border-primary-500/20">
                <span className="text-xs text-gray-400">
                  「{lines[lineIdx].ruby[editing.charIdx]?.char}」的读音:
                </span>
                <input
                  autoFocus
                  value={editReading}
                  onChange={(e) => setEditReading(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleEditFurigana(lineIdx, editing.charIdx, editReading)
                      setEditing(null)
                    } else if (e.key === 'Escape') {
                      setEditing(null)
                    }
                  }}
                  className="px-2 py-1 bg-black/30 border border-white/20 rounded text-sm text-white w-24 focus:outline-none focus:border-primary-500"
                  placeholder="假名"
                />
                <button
                  onClick={() => {
                    handleEditFurigana(editing.lineIdx, editing.charIdx, editReading)
                    setEditing(null)
                  }}
                  className="text-xs text-primary-400 hover:text-primary-300"
                >
                  确认
                </button>
                <button
                  onClick={() => setEditing(null)}
                  className="text-xs text-gray-500 hover:text-gray-400"
                >
                  取消
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {lines.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          暂无歌词数据
        </div>
      )}
    </div>
  )
}

function formatTime(seconds) {
  if (seconds == null) return '--:--'
  const m = Math.floor(seconds / 60)
  const s = (seconds % 60).toFixed(2)
  return `${m}:${s.padStart(5, '0')}`
}

function isKanji(char) {
  const code = char.charCodeAt(0)
  return (code >= 0x4E00 && code <= 0x9FFF) ||
         (code >= 0x3400 && code <= 0x4DBF)
}
