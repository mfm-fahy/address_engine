export default function Card({ children, className = '', accent, hover, padding = 'lg', ...props }) {
  const padMap = { none: '', sm: 'p-3', md: 'p-4', lg: 'p-5', xl: 'p-6' }
  return (
    <div
      className={`card ${padMap[padding] || 'p-5'} ${accent ? `card-accent-${accent}` : ''} ${hover ? 'card-hover' : ''} ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
