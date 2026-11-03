<template>
  <div class="reports">
    <div class="page-header">
      <h2>{{ t('reports.title') }}</h2>
      <p>{{ t('reports.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('reports.loading') }}</div>
    <div v-else-if="hasError" class="error">{{ t('reports.error') }}</div>
    <div v-else>
      <!-- Quarterly Performance -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.quarterly.title') }}</h3>
        </div>
        <div v-if="quarterRows.length === 0" class="empty-message">
          {{ t('reports.quarterly.empty') }}
        </div>
        <div v-else class="table-container">
          <table class="reports-table">
            <thead>
              <tr>
                <th>{{ t('reports.quarterly.quarter') }}</th>
                <th>{{ t('reports.quarterly.totalOrders') }}</th>
                <th>{{ t('reports.quarterly.totalRevenue') }}</th>
                <th>{{ t('reports.quarterly.avgOrderValue') }}</th>
                <th>{{ t('reports.quarterly.fulfillmentRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in quarterRows" :key="q.key">
                <td><strong>{{ q.label }}</strong></td>
                <td>{{ q.orders }}</td>
                <td>{{ q.revenue }}</td>
                <td>{{ q.avgOrderValue }}</td>
                <td>
                  <span :class="q.badgeClass">{{ q.rate }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Monthly Trends Chart -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthly.chartTitle') }}</h3>
        </div>
        <div v-if="bars.length === 0" class="empty-message">
          {{ t('reports.monthly.empty') }}
        </div>
        <div v-else class="chart-container">
          <div class="bar-chart" role="img" :aria-label="chartAriaLabel">
            <div v-for="bar in bars" :key="bar.key" class="bar-wrapper">
              <div class="bar-container">
                <div
                  class="bar"
                  :style="{ height: bar.height + 'px' }"
                  :title="bar.description"
                  :aria-label="bar.description"
                ></div>
              </div>
              <div class="bar-label">{{ bar.label }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Month-over-Month Comparison -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthly.momTitle') }}</h3>
        </div>
        <div v-if="monthRows.length === 0" class="empty-message">
          {{ t('reports.monthly.empty') }}
        </div>
        <div v-else class="table-container">
          <table class="reports-table">
            <thead>
              <tr>
                <th>{{ t('reports.monthly.month') }}</th>
                <th>{{ t('reports.monthly.orders') }}</th>
                <th>{{ t('reports.monthly.revenue') }}</th>
                <th>{{ t('reports.monthly.change') }}</th>
                <th>{{ t('reports.monthly.growthRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in monthRows" :key="row.key">
                <td><strong>{{ row.label }}</strong></td>
                <td>{{ row.orders }}</td>
                <td>{{ row.revenue }}</td>
                <td>
                  <span :class="row.changeClass">{{ row.change }}</span>
                </td>
                <td>
                  <span :class="row.changeClass">{{ row.growth }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Summary Stats -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.totalRevenue') }}</div>
          <div class="stat-value">{{ formatMoney(totalRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.avgMonthlyRevenue') }}</div>
          <div class="stat-value">{{ formatMoney(avgMonthlyRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.totalOrders') }}</div>
          <div class="stat-value">{{ totalOrders }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.stats.bestQuarter') }}</div>
          <div class="stat-value">{{ bestQuarter }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, convertAmount } from '../utils/currency'

// Max bar height in px; must match .bar-container height in the styles
const MAX_BAR_HEIGHT = 200

// Returns a finite number, or null for null/undefined/NaN/non-numeric values
const toNumber = (value) => {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export default {
  name: 'Reports',
  setup() {
    const { t, currentLocale, currentCurrency } = useI18n()

    const loading = ref(true)
    const hasError = ref(false)
    const quarterlyData = ref([])
    const monthlyData = ref([])

    // Use shared filters
    const {
      selectedPeriod,
      selectedLocation,
      selectedCategory,
      selectedStatus,
      getCurrentFilters
    } = useFilters()

    // Incremented on every load; lets an older, slower response detect that it is stale
    let latestRequestId = 0

    const loadData = async () => {
      const requestId = ++latestRequestId
      loading.value = true
      hasError.value = false
      try {
        const filters = getCurrentFilters()
        const [quarterly, monthly] = await Promise.all([
          api.getQuarterlyReports(filters),
          api.getMonthlyTrends(filters)
        ])
        // Filters changed while this request was in flight: a newer load owns the state
        if (requestId !== latestRequestId) return
        quarterlyData.value = Array.isArray(quarterly) ? quarterly : []
        monthlyData.value = Array.isArray(monthly) ? monthly : []
      } catch (err) {
        if (requestId !== latestRequestId) return
        hasError.value = true
        console.error('Failed to load reports:', err)
      } finally {
        if (requestId === latestRequestId) loading.value = false
      }
    }

    // Reload when any global filter changes
    watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus], () => {
      loadData()
    })

    // ---- Formatting helpers (read locale/currency refs so templates stay reactive) ----

    // Currency amount (USD base), '-' for missing/invalid values
    const formatMoney = (value) => {
      const n = toNumber(value)
      if (n === null) return t('reports.noValue')
      return formatCurrency(n, currentCurrency.value)
    }

    // Signed currency change: sign is decided on the converted, rounded amount so
    // a tiny USD delta never renders as "+JPY 0" / "-$0"
    const formatSignedMoney = (change) => {
      const shown = Math.round(convertAmount(change, currentCurrency.value))
      if (shown > 0) return '+' + formatCurrency(change, currentCurrency.value)
      if (shown < 0) return '-' + formatCurrency(Math.abs(change), currentCurrency.value)
      return formatCurrency(0, currentCurrency.value)
    }

    // 'YYYY-MM' -> localized "Jan 2025" / "2025年1月". Falls back to the raw value if invalid.
    const formatMonth = (monthStr) => {
      const match = /^(\d{4})-(\d{2})$/.exec(String(monthStr ?? ''))
      if (!match) return monthStr ? String(monthStr) : t('reports.noValue')
      const year = Number(match[1])
      const month = Number(match[2])
      if (month < 1 || month > 12) return String(monthStr)
      const date = new Date(Date.UTC(year, month - 1, 1))
      if (isNaN(date.getTime())) return String(monthStr)
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      // UTC so the month never shifts with the browser time zone
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', timeZone: 'UTC' })
    }

    // 'Q1-2025' -> translated quarter label. Falls back to the raw value if it does not match.
    const formatQuarter = (quarterStr) => {
      const match = /^Q([1-4])-(\d{4})$/.exec(String(quarterStr ?? ''))
      if (!match) return quarterStr ? String(quarterStr) : t('reports.noValue')
      return t('reports.quarterLabel', { quarter: match[1], year: match[2] })
    }

    const formatCount = (value) => {
      const n = toNumber(value)
      return n === null ? t('reports.noValue') : n.toLocaleString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US')
    }

    const formatPercent = (value) => {
      const n = toNumber(value)
      return n === null ? t('reports.noValue') : `${Math.round(n * 10) / 10}%`
    }

    const getFulfillmentClass = (rate) => {
      const n = toNumber(rate)
      if (n === null) return 'badge info'
      if (n >= 90) return 'badge success'
      if (n >= 75) return 'badge warning'
      return 'badge danger'
    }

    // ---- Derived data ----

    // Months in chronological order ('YYYY-MM' sorts lexicographically); copy so the ref is not mutated
    const sortedMonthly = computed(() =>
      [...monthlyData.value].sort((a, b) => String(a.month).localeCompare(String(b.month)))
    )

    const quarterRows = computed(() =>
      quarterlyData.value.map(q => ({
        key: q.quarter,
        label: formatQuarter(q.quarter),
        orders: formatCount(q.total_orders),
        revenue: formatMoney(q.total_revenue),
        avgOrderValue: formatMoney(q.avg_order_value),
        rate: formatPercent(q.fulfillment_rate),
        badgeClass: getFulfillmentClass(q.fulfillment_rate)
      }))
    )

    // Month-over-month rows are computed once here (previous month looked up by position)
    // instead of calling per-cell methods with monthlyData[index - 1] from the template
    const monthRows = computed(() =>
      sortedMonthly.value.map((m, index) => {
        const row = {
          key: m.month,
          label: formatMonth(m.month),
          orders: formatCount(m.order_count),
          revenue: formatMoney(m.revenue),
          change: t('reports.noValue'),
          growth: t('reports.noValue'),
          changeClass: ''
        }
        if (index === 0) return row

        const current = toNumber(m.revenue)
        const previous = toNumber(sortedMonthly.value[index - 1].revenue)
        if (current === null || previous === null) return row

        const change = current - previous
        row.change = formatSignedMoney(change)
        const shown = Math.round(convertAmount(change, currentCurrency.value))
        row.changeClass = shown > 0 ? 'positive-change' : shown < 0 ? 'negative-change' : ''
        if (previous === 0) {
          row.growth = t('reports.notAvailable')
        } else {
          const rate = (change / previous) * 100
          row.growth = (rate > 0 ? '+' : '') + rate.toFixed(1) + '%'
        }
        return row
      })
    )

    // Max revenue is computed once. Bar heights are precomputed from it so the template
    // does not rescan the whole series for every bar on every render (was O(n^2)).
    const maxRevenue = computed(() =>
      sortedMonthly.value.reduce((max, m) => Math.max(max, toNumber(m.revenue) ?? 0), 0)
    )

    const bars = computed(() =>
      sortedMonthly.value.map(m => {
        const revenue = toNumber(m.revenue) ?? 0
        const label = formatMonth(m.month)
        return {
          key: m.month,
          label,
          height: maxRevenue.value > 0 ? Math.max(0, (revenue / maxRevenue.value) * MAX_BAR_HEIGHT) : 0,
          description: t('reports.monthly.barLabel', { month: label, revenue: formatMoney(m.revenue) })
        }
      })
    )

    const chartAriaLabel = computed(() => {
      if (bars.value.length === 0) return t('reports.monthly.empty')
      const peak = sortedMonthly.value.reduce(
        (best, m) => ((toNumber(m.revenue) ?? 0) > (toNumber(best.revenue) ?? 0) ? m : best),
        sortedMonthly.value[0]
      )
      return t('reports.monthly.chartAriaLabel', {
        count: bars.value.length,
        first: bars.value[0].label,
        last: bars.value[bars.value.length - 1].label,
        peakMonth: formatMonth(peak.month),
        peak: formatMoney(peak.revenue)
      })
    })

    const totalRevenue = computed(() =>
      monthlyData.value.reduce((sum, m) => sum + (toNumber(m.revenue) ?? 0), 0)
    )

    const avgMonthlyRevenue = computed(() =>
      monthlyData.value.length > 0 ? totalRevenue.value / monthlyData.value.length : 0
    )

    const totalOrders = computed(() => {
      const total = monthlyData.value.reduce((sum, m) => sum + (toNumber(m.order_count) ?? 0), 0)
      return formatCount(total)
    })

    const bestQuarter = computed(() => {
      const best = quarterlyData.value.reduce(
        (top, q) => ((toNumber(q.total_revenue) ?? 0) > (top ? toNumber(top.total_revenue) : 0) ? q : top),
        null
      )
      return best ? formatQuarter(best.quarter) : t('reports.noValue')
    })

    onMounted(loadData)

    return {
      t,
      loading,
      hasError,
      quarterRows,
      monthRows,
      bars,
      chartAriaLabel,
      totalRevenue,
      avgMonthlyRevenue,
      totalOrders,
      bestQuarter,
      formatMoney
    }
  }
}
</script>

<style scoped>
/* Shared styles (.card, .stat-card, .badge, .loading, .error, table) come from App.vue */
.reports {
  padding: 0;
}

.empty-message {
  text-align: center;
  color: #64748b;
  padding: 1.5rem;
  font-size: 0.938rem;
}

.chart-container {
  /* Extra bottom/left padding leaves room for the rotated month labels */
  padding: 1.5rem 1rem 4.5rem 3rem;
}

.bar-chart {
  display: flex;
  align-items: flex-start;
  justify-content: space-around;
  gap: 0.5rem;
}

.bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  max-width: 80px;
}

.bar-container {
  height: 200px;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.bar {
  width: 100%;
  background: linear-gradient(to top, #475569, #64748b);
  border-radius: 4px 4px 0 0;
  transition: height 0.3s, background 0.2s;
  cursor: pointer;
}

.bar:hover {
  background: linear-gradient(to top, #334155, #475569);
}

.bar-label {
  width: 100%;
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #64748b;
  text-align: right;
  white-space: nowrap;
  /* Rotate around the top-right corner so the text extends down-left into the padding */
  transform: rotate(-45deg);
  transform-origin: top right;
}

.positive-change {
  color: #16a34a;
  font-weight: 600;
}

.negative-change {
  color: #dc2626;
  font-weight: 600;
}
</style>
