import { onMounted, onUnmounted, ref, type Ref } from 'vue'
import {
  getWorkingStoreId,
  onWorkingStoreChange,
  resolveFilterStoreId,
  resolveRequiredStoreId,
} from '../utils/workingStore'

/** 必须单店：与顶栏工作门店同步 */
export function useRequiredStoreId(
  storeId: Ref<number | null>,
  getFirstId: () => number | null | undefined,
  onChange?: () => void | Promise<void>,
) {
  const apply = () => {
    const next = resolveRequiredStoreId(getFirstId())
    if (next && next !== storeId.value) {
      storeId.value = next
      void onChange?.()
    } else if (next && !storeId.value) {
      storeId.value = next
    }
  }

  let off: (() => void) | undefined
  onMounted(() => {
    apply()
    off = onWorkingStoreChange(() => {
      const next = resolveRequiredStoreId(getFirstId())
      if (next != null && next !== storeId.value) {
        storeId.value = next
        void onChange?.()
      }
    })
  })
  onUnmounted(() => off?.())

  return { apply }
}

/** 可选筛选：顶栏变更时更新 filter 并回调 */
export function useFilterStoreId(
  filterStoreId: Ref<number | null>,
  onChange?: () => void | Promise<void>,
) {
  const apply = () => {
    filterStoreId.value = resolveFilterStoreId()
  }

  let off: (() => void) | undefined
  onMounted(() => {
    apply()
    off = onWorkingStoreChange(() => {
      filterStoreId.value = resolveFilterStoreId()
      void onChange?.()
    })
  })
  onUnmounted(() => off?.())

  return { apply, workingStoreId: () => getWorkingStoreId() }
}

export function useWorkingStoreReload(reload: () => void | Promise<void>) {
  const tick = ref(0)
  let off: (() => void) | undefined
  onMounted(() => {
    off = onWorkingStoreChange(() => {
      tick.value += 1
      void reload()
    })
  })
  onUnmounted(() => off?.())
  return tick
}
