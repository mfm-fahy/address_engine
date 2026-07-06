import { useState, useMemo } from 'react'
import { Search, X, SlidersHorizontal, ChevronDown } from 'lucide-react'

export default function FilterPanel({
  search,
  onSearchChange,
  searchPlaceholder = 'Search...',
  filters,
  onFilterChange,
  filterConfig = [],
  activeFilterCount = 0,
  onClearAll,
}) {
  const [open, setOpen] = useState(false)

  const activeChips = useMemo(() => {
    const chips = []
    if (search) chips.push({ key: 'search', label: `"${search}"`, onRemove: () => onSearchChange('') })
    filterConfig.forEach(cfg => {
      if (cfg.type === 'chips') {
        const activeVal = filters[cfg.key]
        if (Array.isArray(activeVal)) {
          activeVal.forEach(v => {
            const opt = cfg.options?.find(o => o.value === v)
            chips.push({ key: `${cfg.key}-${v}`, label: opt?.label || v, onRemove: () => onFilterChange(cfg.key, activeVal.filter(x => x !== v)) })
          })
        }
      }
      if (cfg.type === 'toggle') {
        if (filters[cfg.key]) {
          chips.push({ key: cfg.key, label: cfg.label, onRemove: () => onFilterChange(cfg.key, false) })
        }
      }
      if (cfg.type === 'range') {
        const min = filters[cfg.minKey]
        const max = filters[cfg.maxKey]
        if (min || max) {
          chips.push({ key: `${cfg.key}-range`, label: `${cfg.label}: ${min || '0'} - ${max || '∞'}`, onRemove: () => { onFilterChange(cfg.minKey, ''); onFilterChange(cfg.maxKey, '') } })
        }
      }
    })
    return chips
  }, [search, filters, filterConfig, onFilterChange, onSearchChange])

  return (
    <div className="filter-system">
      <div className="filter-bar">
        <div className="filter-search-wrapper">
          <Search size={16} className="filter-search-icon" />
          <input
            type="text"
            className="filter-search-input"
            placeholder={searchPlaceholder}
            value={search}
            onChange={e => onSearchChange(e.target.value)}
            aria-label="Search"
          />
          {search && (
            <button className="filter-search-clear" onClick={() => onSearchChange('')} aria-label="Clear search">
              <X size={14} />
            </button>
          )}
        </div>
        <div className="filter-actions">
          <button
            className={`btn btn-outline btn-sm ${activeFilterCount > 0 ? 'btn-active' : ''}`}
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            aria-label="Toggle filters"
          >
            <SlidersHorizontal size={14} />
            <span>Filters</span>
            {activeFilterCount > 0 && <span className="filter-count-badge">{activeFilterCount}</span>}
          </button>
        </div>
      </div>

      {activeChips.length > 0 && (
        <div className="active-filter-chips" role="list" aria-label="Active filters">
          {activeChips.map(chip => (
            <span key={chip.key} className="filter-chip" role="listitem">
              {chip.label}
              <button className="filter-chip-remove" onClick={chip.onRemove} aria-label={`Remove filter ${chip.label}`}>
                <X size={12} />
              </button>
            </span>
          ))}
          {activeChips.length > 1 && (
            <button className="filter-chip-clear-all" onClick={onClearAll}>
              Clear all
            </button>
          )}
        </div>
      )}

      {open && (
        <div className="filter-dropdown-panel" role="region" aria-label="Filter options">
          <div className="filter-sections">
            {filterConfig.map((cfg, i) => (
              <div key={i} className="filter-group">
                <span className="filter-group-label">{cfg.label}</span>
                {cfg.type === 'chips' && (
                  <div className="filter-chips-row">
                    {cfg.options.map(opt => {
                      const active = Array.isArray(filters[cfg.key]) && filters[cfg.key].includes(opt.value)
                      return (
                        <button
                          key={opt.value}
                          className={`chip ${active ? 'chip-active' : ''}`}
                          style={active && opt.color ? { borderColor: opt.color, color: opt.color, background: `${opt.color}18` } : {}}
                          onClick={() => {
                            const current = filters[cfg.key] || []
                            const next = current.includes(opt.value)
                              ? current.filter(v => v !== opt.value)
                              : [...current, opt.value]
                            onFilterChange(cfg.key, next)
                          }}
                        >
                          {opt.icon && <opt.icon size={12} />}
                          {opt.label}
                        </button>
                      )
                    })}
                  </div>
                )}
                {cfg.type === 'toggle' && (
                  <div className="filter-toggles">
                    {cfg.options.map(opt => (
                      <label key={opt.value} className="filter-toggle-label">
                        <input
                          type="checkbox"
                          className="filter-checkbox"
                          checked={!!filters[opt.value]}
                          onChange={() => onFilterChange(opt.value, !filters[opt.value])}
                        />
                        <span className="filter-toggle-text">{opt.label}</span>
                      </label>
                    ))}
                  </div>
                )}
                {cfg.type === 'select' && (
                  <select
                    className="filter-select"
                    value={filters[cfg.key] || ''}
                    onChange={e => onFilterChange(cfg.key, e.target.value)}
                    aria-label={cfg.label}
                  >
                    {cfg.options.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                )}
                {cfg.type === 'range' && (
                  <div className="filter-range-row">
                    <input
                      type="number"
                      className="filter-range-input"
                      placeholder={cfg.minPlaceholder || 'Min'}
                      value={filters[cfg.minKey] || ''}
                      onChange={e => onFilterChange(cfg.minKey, e.target.value)}
                      aria-label={cfg.minPlaceholder || 'Minimum'}
                    />
                    <span className="filter-range-sep">to</span>
                    <input
                      type="number"
                      className="filter-range-input"
                      placeholder={cfg.maxPlaceholder || 'Max'}
                      value={filters[cfg.maxKey] || ''}
                      onChange={e => onFilterChange(cfg.maxKey, e.target.value)}
                      aria-label={cfg.maxPlaceholder || 'Maximum'}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
          {activeFilterCount > 0 && (
            <div className="filter-panel-actions">
              <button className="btn btn-ghost btn-sm" onClick={onClearAll}>
                <X size={12} /> Reset all
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
