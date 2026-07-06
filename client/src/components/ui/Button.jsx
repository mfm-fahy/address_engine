import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  danger: 'btn-danger',
  ghost: 'btn-ghost',
  outline: 'btn-outline',
}

const SIZES = {
  sm: 'btn-sm',
  md: 'btn-md',
  lg: 'btn-lg',
  icon: 'btn-icon',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  className = '',
  ...props
}) {
  return (
    <button
      className={`btn ${VARIANTS[variant] || VARIANTS.primary} ${SIZES[size] || SIZES.md} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader2 size={size === 'sm' ? 12 : 14} className="spin" /> : icon || null}
      {children && <span>{children}</span>}
    </button>
  )
}
