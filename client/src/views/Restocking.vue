<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="gapItems.length === 0" class="card empty-state">
      {{ t('restocking.empty') }}
    </div>
    <div v-else>
      <div v-if="successMessage" class="banner banner-success" role="status">{{ successMessage }}</div>
      <div v-if="submitError" class="error" role="alert">{{ submitError }}</div>

      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
        </div>
        <div class="budget-value">{{ formatCurrency(budget, currentCurrency) }}</div>
        <input
          id="restocking-budget"
          v-model.number="budget"
          class="budget-slider"
          type="range"
          min="0"
          :max="maxBudget"
          :step="BUDGET_STEP"
          :aria-label="t('restocking.budgetLabel')"
        />
        <div class="budget-scale">
          <span>{{ formatCurrency(0, currentCurrency) }}</span>
          <span>{{ t('restocking.budgetMax') }}: {{ formatCurrency(maxBudget, currentCurrency) }}</span>
        </div>
        <p class="budget-help">{{ t('restocking.budgetHelp') }}</p>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.selectedItems') }}</div>
          <div class="stat-value">{{ selectedItems.length }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.totalCost') }}</div>
          <div class="stat-value">{{ formatCurrencyWithDecimals(totalCost, currentCurrency, 2) }}</div>
        </div>
        <div :class="['stat-card', isOverBudget ? 'danger' : 'success']">
          <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
          <div class="stat-value">{{ remainingDisplay }}</div>
          <div v-if="isOverBudget" class="stat-note">
            {{ t('restocking.overBudget', { amount: formatCurrencyWithDecimals(Math.abs(remainingBudget), currentCurrency, 2) }) }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.longestLeadTime') }}</div>
          <div class="stat-value">{{ longestLeadTime === null ? '-' : t('restocking.days', { count: longestLeadTime }) }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }}</h3>
          <span class="selection-count">
            {{ t('restocking.selectedOfTotal', { selected: selectedItems.length, total: gapItems.length }) }}
          </span>
        </div>
        <div class="table-container">
          <table class="restocking-table">
            <thead>
              <tr>
                <th class="col-check">{{ t('restocking.table.select') }}</th>
                <th>{{ t('restocking.table.item') }}</th>
                <th class="num">{{ t('restocking.table.gap') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="col-qty">{{ t('restocking.table.quantity') }}</th>
                <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                <th>{{ t('restocking.table.supplier') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in gapItems" :key="item.item_sku" :class="{ 'row-selected': selected[item.item_sku] }">
                <td class="col-check">
                  <input
                    v-model="selected[item.item_sku]"
                    type="checkbox"
                    :aria-label="item.item_sku"
                  />
                </td>
                <td>
                  <strong>{{ item.item_sku }}</strong>
                  <div class="item-subname">{{ translateProductName(item.item_name) }}</div>
                </td>
                <td class="num">{{ item.gap }}</td>
                <td class="num">{{ formatCurrencyWithDecimals(item.unit_cost, currentCurrency, 2) }}</td>
                <td class="col-qty">
                  <input
                    v-model.number="quantities[item.item_sku]"
                    :class="['qty-input', { invalid: !isValidQuantity(quantities[item.item_sku]) }]"
                    type="number"
                    min="1"
                    step="1"
                    :aria-label="t('restocking.table.quantity') + ' ' + item.item_sku"
                    :title="isValidQuantity(quantities[item.item_sku]) ? '' : t('restocking.invalidQuantity')"
                  />
                </td>
                <td class="num">{{ formatCurrencyWithDecimals(lineTotal(item), currentCurrency, 2) }}</td>
                <td>{{ item.supplier_name }}</td>
                <td class="num">{{ t('restocking.days', { count: item.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="actions">
          <button
            type="button"
            class="place-order-btn"
            :disabled="!canPlaceOrder"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

// Budget slider granularity (USD)
const BUDGET_STEP = 100
// Tolerance for floating point comparisons on USD amounts
const EPSILON = 0.005

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale, translateProductName } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])

    const budget = ref(0)
    // Keyed by SKU
    const selected = ref({})
    const quantities = ref({})

    const submitting = ref(false)
    const successMessage = ref('')
    const submitError = ref('')

    // Only items whose forecast exceeds current demand need restocking.
    // Sorted by gap descending (SKU as tie-breaker for a stable order).
    const gapItems = computed(() => {
      return forecasts.value
        .map(f => ({ ...f, gap: f.forecasted_demand - f.current_demand }))
        .filter(f => f.gap > 0)
        .sort((a, b) => b.gap - a.gap || a.item_sku.localeCompare(b.item_sku))
    })

    // Cost of buying every item's full gap, rounded up to the slider step
    const maxBudget = computed(() => {
      const full = gapItems.value.reduce((sum, i) => sum + i.gap * i.unit_cost, 0)
      return Math.ceil(full / BUDGET_STEP - EPSILON) * BUDGET_STEP
    })

    // Greedy recommendation: walk items from largest gap to smallest and buy the
    // full gap quantity when it still fits in the remaining budget. An item that
    // does not fit is skipped (not a stop condition), so smaller gaps can still fill leftovers.
    const recommendedSkus = (budgetValue) => {
      let remaining = budgetValue
      const skus = new Set()
      for (const item of gapItems.value) {
        const cost = item.gap * item.unit_cost
        if (cost <= remaining + EPSILON) {
          skus.add(item.item_sku)
          remaining -= cost
        }
      }
      return skus
    }

    // Moving the slider discards any manual edits: selection and quantities are
    // rebuilt from the recommendation for the new budget. Items that are not
    // recommended stay in the table, unchecked, with quantity = gap so they can be added.
    const applyRecommendation = () => {
      const skus = recommendedSkus(budget.value)
      const nextSelected = {}
      const nextQuantities = {}
      for (const item of gapItems.value) {
        nextSelected[item.item_sku] = skus.has(item.item_sku)
        nextQuantities[item.item_sku] = item.gap
      }
      selected.value = nextSelected
      quantities.value = nextQuantities
    }

    const isValidQuantity = (q) => Number.isInteger(q) && q >= 1

    const lineTotal = (item) => {
      const q = quantities.value[item.item_sku]
      return isValidQuantity(q) ? q * item.unit_cost : 0
    }

    const selectedItems = computed(() => gapItems.value.filter(i => selected.value[i.item_sku]))

    const hasInvalidQuantity = computed(() => {
      return selectedItems.value.some(i => !isValidQuantity(quantities.value[i.item_sku]))
    })

    // All amounts are USD internally; formatCurrency converts for display only
    const totalCost = computed(() => {
      return selectedItems.value.reduce((sum, i) => sum + lineTotal(i), 0)
    })

    const remainingBudget = computed(() => budget.value - totalCost.value)
    const isOverBudget = computed(() => totalCost.value > budget.value + EPSILON)

    const remainingDisplay = computed(() => {
      const formatted = formatCurrencyWithDecimals(Math.abs(remainingBudget.value), currentCurrency.value, 2)
      return remainingBudget.value < -EPSILON ? `-${formatted}` : formatted
    })

    const longestLeadTime = computed(() => {
      if (selectedItems.value.length === 0) return null
      return Math.max(...selectedItems.value.map(i => i.lead_time_days))
    })

    const canPlaceOrder = computed(() => {
      return selectedItems.value.length > 0 &&
        !hasInvalidQuantity.value &&
        !isOverBudget.value &&
        !submitting.value
    })

    const formatDate = (dateString) => {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return dateString
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
    }

    const loadForecasts = async () => {
      try {
        loading.value = true
        error.value = null
        forecasts.value = await api.getDemandForecasts()
        // Default budget: about half of the maximum, on a step boundary
        budget.value = Math.round(maxBudget.value / 2 / BUDGET_STEP) * BUDGET_STEP
        applyRecommendation()
      } catch (err) {
        error.value = t('restocking.loadError') + ': ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      if (!canPlaceOrder.value) return
      submitting.value = true
      successMessage.value = ''
      submitError.value = ''
      try {
        const order = await api.createRestockingOrder({
          budget: budget.value,
          items: selectedItems.value.map(i => ({
            sku: i.item_sku,
            quantity: quantities.value[i.item_sku]
          }))
        })
        successMessage.value = t('restocking.success', {
          orderNumber: order.order_number,
          date: formatDate(order.expected_delivery)
        })
        // Uncheck everything and restore default quantities
        const nextSelected = {}
        const nextQuantities = {}
        for (const item of gapItems.value) {
          nextSelected[item.item_sku] = false
          nextQuantities[item.item_sku] = item.gap
        }
        selected.value = nextSelected
        quantities.value = nextQuantities
      } catch (err) {
        const detail = err.response?.data?.detail
        submitError.value = typeof detail === 'string' && detail ? detail : t('restocking.error')
        console.error('Failed to place restocking order:', err)
      } finally {
        submitting.value = false
      }
    }

    watch(budget, () => {
      successMessage.value = ''
      submitError.value = ''
      applyRecommendation()
    })

    onMounted(loadForecasts)

    return {
      t,
      currentCurrency,
      translateProductName,
      formatCurrency,
      formatCurrencyWithDecimals,
      BUDGET_STEP,
      loading,
      error,
      gapItems,
      budget,
      maxBudget,
      selected,
      quantities,
      selectedItems,
      totalCost,
      remainingBudget,
      remainingDisplay,
      isOverBudget,
      longestLeadTime,
      canPlaceOrder,
      submitting,
      successMessage,
      submitError,
      isValidQuantity,
      lineTotal,
      placeOrder
    }
  }
}
</script>

<style scoped>
.empty-state {
  text-align: center;
  color: #64748b;
  padding: 2rem;
}

.banner {
  padding: 1rem;
  border-radius: 8px;
  margin: 0 0 1rem;
  font-size: 0.938rem;
}

.banner-success {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
}

.budget-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
  margin-bottom: 0.75rem;
}

.budget-slider {
  width: 100%;
  accent-color: #0f172a;
  cursor: pointer;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.813rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.budget-help {
  margin-top: 0.75rem;
  font-size: 0.875rem;
  color: #64748b;
}

.stat-note {
  margin-top: 0.375rem;
  font-size: 0.813rem;
  font-weight: 600;
  color: #991b1b;
}

.selection-count {
  font-size: 0.875rem;
  color: #64748b;
}

.restocking-table th.num,
.restocking-table td.num {
  text-align: right;
  white-space: nowrap;
}

.col-check {
  width: 64px;
  text-align: center;
}

.col-qty {
  width: 120px;
}

.item-subname {
  color: #64748b;
  font-size: 0.813rem;
}

.row-selected {
  background: #f8fafc;
}

.qty-input {
  width: 100%;
  padding: 0.375rem 0.5rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.875rem;
  color: #0f172a;
  text-align: right;
}

.qty-input:focus {
  outline: 2px solid #94a3b8;
  outline-offset: 1px;
}

.qty-input.invalid {
  border-color: #dc2626;
  background: #fef2f2;
}

.actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.place-order-btn {
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.625rem 1.5rem;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1e293b;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  color: #64748b;
  cursor: not-allowed;
}
</style>
