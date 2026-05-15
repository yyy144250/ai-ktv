const STEPS = [
  { label: '上传', icon: '📤' },
  { label: '分离', icon: '🎵' },
  { label: '歌词', icon: '📝' },
  { label: '标注', icon: 'あ' },
  { label: '对齐', icon: '⏱️' },
  { label: '合成', icon: '🎬' },
  { label: '完成', icon: '✅' },
]

export default function StepIndicator({ currentStep }) {
  return (
    <div className="flex items-center justify-center mb-8 gap-1">
      {STEPS.map((s, i) => (
        <div key={i} className="flex items-center">
          <div
            className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs transition-all ${
              i < currentStep
                ? 'bg-primary-600/30 text-primary-300'
                : i === currentStep
                ? 'bg-primary-600/50 text-white font-medium ring-1 ring-primary-400/50'
                : 'bg-white/5 text-gray-500'
            }`}
          >
            <span>{s.icon}</span>
            <span className="hidden sm:inline">{s.label}</span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={`w-4 h-[2px] mx-0.5 ${
              i < currentStep ? 'bg-primary-500' : 'bg-gray-700'
            }`} />
          )}
        </div>
      ))}
    </div>
  )
}
