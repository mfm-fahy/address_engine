const VARIANTS = {
  insta: 'badge-insta',
  whats: 'badge-whats',
  bill: 'badge-bill',
  f3: 'badge-f3',
  success: 'pill-success',
  warning: 'pill-warning',
  danger: 'pill-danger',
  info: 'pill-info',
  vip: 'badge-vip',
  default: 'badge-default',
}

export default function Badge({ children, variant = 'default', className = '', ...props }) {
  return (
    <span className={`badge ${VARIANTS[variant] || VARIANTS.default} ${className}`} {...props}>
      {children}
    </span>
  )
}
