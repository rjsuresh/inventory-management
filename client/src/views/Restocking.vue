<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div class="card budget-card">
      <div class="card-header">
        <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
        <span class="budget-value">{{ formattedBudget }}</span>
      </div>
      <input
        type="range"
        min="0"
        max="100000"
        step="500"
        v-model.number="budget"
        class="budget-slider"
      />
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="successMessage" class="success-message">{{ successMessage }}</div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }}</h3>
        </div>

        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <template v-else>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>{{ t('restocking.table.sku') }}</th>
                  <th>{{ t('restocking.table.itemName') }}</th>
                  <th>{{ t('restocking.table.category') }}</th>
                  <th>{{ t('restocking.table.trend') }}</th>
                  <th>{{ t('restocking.table.forecastedDemand') }}</th>
                  <th>{{ t('restocking.table.recommendedQuantity') }}</th>
                  <th>{{ t('restocking.table.unitCost') }}</th>
                  <th>{{ t('restocking.table.subtotal') }}</th>
                  <th>{{ t('restocking.table.leadTime') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in recommendations" :key="item.sku">
                  <td><strong>{{ item.sku }}</strong></td>
                  <td>{{ item.item_name }}</td>
                  <td>{{ item.category }}</td>
                  <td>
                    <span :class="['badge', item.trend]">
                      {{ t(`trends.${item.trend}`) }}
                    </span>
                  </td>
                  <td>{{ item.forecasted_demand }}</td>
                  <td><strong>{{ item.recommended_quantity }}</strong></td>
                  <td>${{ item.unit_cost.toLocaleString() }}</td>
                  <td>${{ item.estimated_cost.toLocaleString() }}</td>
                  <td>{{ item.lead_time_days }} {{ t('dashboard.inventoryShortages.days') }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="summary-bar">
            <div class="summary-item">
              <span class="summary-label">{{ t('restocking.estimatedTotal') }}</span>
              <span class="summary-value">${{ estimatedTotal.toLocaleString() }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">{{ t('restocking.remainingBudget') }}</span>
              <span :class="['summary-value', { negative: remainingBudget < 0 }]">
                ${{ remainingBudget.toLocaleString() }}
              </span>
            </div>
            <button
              class="place-order-btn"
              :disabled="loading || submitting || recommendations.length === 0"
              @click="placeOrder"
            >
              {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t } = useI18n()

    const budget = ref(20000)
    const recommendations = ref([])
    const loading = ref(true)
    const submitting = ref(false)
    const error = ref(null)
    const successMessage = ref(null)

    let debounceTimer = null

    const formattedBudget = computed(() => {
      return budget.value.toLocaleString('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0
      })
    })

    const estimatedTotal = computed(() => {
      return recommendations.value.reduce((sum, item) => sum + item.estimated_cost, 0)
    })

    const remainingBudget = computed(() => {
      return budget.value - estimatedTotal.value
    })

    const loadRecommendations = async () => {
      try {
        loading.value = true
        error.value = null
        recommendations.value = await api.getRestockRecommendations(budget.value)
      } catch (err) {
        error.value = 'Failed to load restock recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    watch(budget, () => {
      successMessage.value = null
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
        loadRecommendations()
      }, 400)
    })

    const placeOrder = async () => {
      try {
        submitting.value = true
        error.value = null
        successMessage.value = null

        await api.submitRestockOrder({
          items: recommendations.value.map(r => ({
            sku: r.sku,
            item_name: r.item_name,
            category: r.category,
            warehouse: r.warehouse,
            quantity: r.recommended_quantity,
            unit_cost: r.unit_cost
          })),
          budget: budget.value
        })

        successMessage.value = t('restocking.orderSubmitted')
        await loadRecommendations()
      } catch (err) {
        error.value = 'Failed to submit restocking order: ' + err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadRecommendations)

    return {
      t,
      budget,
      formattedBudget,
      recommendations,
      loading,
      submitting,
      error,
      successMessage,
      estimatedTotal,
      remainingBudget,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  accent-color: #2563eb;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.938rem;
}

.success-message {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.938rem;
}

.summary-bar {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 1rem 0.75rem 0;
  margin-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.summary-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.summary-value {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
}

.summary-value.negative {
  color: #dc2626;
}

.place-order-btn {
  margin-left: auto;
  background: #2563eb;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}
</style>
