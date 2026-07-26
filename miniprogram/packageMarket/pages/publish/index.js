const {
  request,
  routes,
  auth,
  guardMarketplace,
  uploadMarketImage,
  absUrl,
} = require('../../utils/market')

Page({
  data: {
    id: 0,
    stores: [],
    examCategories: [],
    materialCategories: [],
    storeIndex: 0,
    examIndex: 0,
    materialIndex: 0,
    title: '',
    description: '',
    price: '',
    images: [],
    imageViews: [],
    copyright_declared: false,
    copyright_text: '',
    phone_bound: false,
    submitting: false,
  },

  onLoad(options) {
    if (!guardMarketplace(this)) return
    const id = Number(options.id || 0)
    this.setData({ id })
    this.bootstrap(id)
  },

  async bootstrap(id) {
    try {
      const meta = await request({ url: '/market/meta' })
      if (!meta.enabled) {
        guardMarketplace(this)
        return
      }
      const stores = meta.stores || []
      let storeIndex = 0
      if (meta.preferred_store_id) {
        const idx = stores.findIndex((s) => s.id === meta.preferred_store_id)
        if (idx >= 0) storeIndex = idx
      }
      this.setData({
        stores,
        examCategories: meta.exam_categories || [],
        materialCategories: meta.material_categories || [],
        storeIndex,
        copyright_text: meta.copyright_text || '',
        phone_bound: !!meta.phone_bound,
      })
      if (id) await this.loadListing(id)
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  async loadListing(id) {
    const data = await request({ url: `/market/listings/${id}` })
    const listing = data.listing
    if (!listing || !listing.is_owner) {
      wx.showToast({ title: '无法编辑', icon: 'none' })
      return
    }
    const storeIndex = Math.max(
      0,
      this.data.stores.findIndex((s) => s.id === listing.store_id)
    )
    const examIndex = Math.max(
      0,
      this.data.examCategories.findIndex((s) => s.id === listing.exam_category_id)
    )
    const materialIndex = Math.max(
      0,
      this.data.materialCategories.findIndex((s) => s.id === listing.material_category_id)
    )
    this.setData({
      storeIndex,
      examIndex,
      materialIndex,
      title: listing.title,
      description: listing.description,
      price: String(listing.price ?? ''),
      images: listing.images || [],
      copyright_declared: !!listing.copyright_declared,
    })
    this.setImages(listing.images || [])
  },

  setImages(images) {
    this.setData({
      images,
      imageViews: (images || []).map(absUrl),
    })
  },

  onStore(e) { this.setData({ storeIndex: Number(e.detail.value) }) },
  onExam(e) { this.setData({ examIndex: Number(e.detail.value) }) },
  onMaterial(e) { this.setData({ materialIndex: Number(e.detail.value) }) },
  onTitle(e) { this.setData({ title: e.detail.value }) },
  onDesc(e) { this.setData({ description: e.detail.value }) },
  onPrice(e) { this.setData({ price: e.detail.value }) },
  onCopyright(e) { this.setData({ copyright_declared: !!e.detail.value.length }) },

  chooseImage() {
    const remain = 9 - this.data.images.length
    if (remain <= 0) return
    wx.chooseMedia({
      count: remain,
      mediaType: ['image'],
      success: async (res) => {
        wx.showLoading({ title: '上传中' })
        try {
          const paths = []
          for (const f of res.tempFiles || []) {
            const path = await uploadMarketImage(f.tempFilePath)
            if (path) paths.push(path)
          }
          this.setImages(this.data.images.concat(paths))
        } catch (e) {
          wx.showToast({ title: e.message || '上传失败', icon: 'none' })
        } finally {
          wx.hideLoading()
        }
      },
    })
  },

  removeImage(e) {
    const idx = e.currentTarget.dataset.index
    const images = this.data.images.slice()
    images.splice(idx, 1)
    this.setImages(images)
  },

  previewImage(e) {
    const urls = this.data.imageViews || []
    if (!urls.length) return
    const index = Number(e.currentTarget.dataset.index || 0)
    wx.previewImage({
      current: urls[index] || urls[0],
      urls,
    })
  },

  buildBody(submit) {
    const store = this.data.stores[this.data.storeIndex]
    const exam = this.data.examCategories[this.data.examIndex]
    const material = this.data.materialCategories[this.data.materialIndex]
    return {
      store_id: store && store.id,
      exam_category_id: exam && exam.id,
      material_category_id: material && material.id,
      title: this.data.title,
      description: this.data.description,
      price: this.data.price === '' ? 0 : Number(this.data.price),
      images: this.data.images,
      copyright_declared: this.data.copyright_declared,
      submit: !!submit,
    }
  },

  async save(submit) {
    if (!auth.requireLogin(routes.marketPublish)) return
    if (!this.data.phone_bound) {
      wx.showModal({
        title: '需要绑定手机号',
        content: '发布资料前请先在「我的」绑定手机号',
        confirmText: '去绑定',
        success: (res) => {
          if (res.confirm) wx.switchTab({ url: '/pages/profile/index' })
        },
      })
      return
    }
    if (this.data.submitting) return
    this.setData({ submitting: true })
    try {
      const body = this.buildBody(submit)
      if (this.data.id) {
        await request({
          url: `/market/listings/${this.data.id}`,
          method: 'PUT',
          data: body,
        })
        if (submit) {
          await request({ url: `/market/listings/${this.data.id}/submit`, method: 'POST' })
        }
      } else {
        const created = await request({
          url: '/market/listings',
          method: 'POST',
          data: body,
        })
        this.setData({ id: created.id })
      }
      wx.showToast({ title: submit ? '已提交审核' : '已保存', icon: 'success' })
      setTimeout(() => wx.navigateBack({ fail: () => wx.redirectTo({ url: routes.marketMine }) }), 500)
    } catch (e) {
      wx.showToast({ title: e.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  saveDraft() { this.save(false) },
  submit() { this.save(true) },
})
