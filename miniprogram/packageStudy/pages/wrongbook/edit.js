const { request } = require('../../../utils/request')
const { uploadWrongbookImage, decorateQuestion } = require('../../utils/wrongbook')

Page({
  data: {
    id: 0,
    subjects: [],
    subjectIndex: 0,
    imageUrls: [],
    displayImages: [],
    ocrText: '',
    answerText: '',
    answerImageUrls: [],
    displayAnswers: [],
    reason: '',
    tags: [],
    tagInput: '',
    historyTags: [],
    submitting: false,
  },

  onLoad(options) {
    const id = Number(options.id || 0)
    this.setData({ id })
    this.bootstrap(id)
  },

  async bootstrap(id) {
    try {
      const [subjects, historyTags] = await Promise.all([
        request({ url: '/wrongbook/subjects', force: true }),
        request({ url: '/wrongbook/tags', force: true, silent: true }).catch(() => []),
      ])
      this.setData({
        subjects: subjects || [],
        historyTags: historyTags || [],
      })
      if (id) await this.loadQuestion(id)
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  async loadQuestion(id) {
    const row = await request({ url: `/wrongbook/${id}`, force: true })
    const item = await decorateQuestion(row)
    const subjectIndex = Math.max(
      0,
      this.data.subjects.findIndex((s) => s.id === item.subject_id)
    )
    this.setData({
      subjectIndex,
      imageUrls: item.image_urls || [],
      displayImages: item.display_images || [],
      ocrText: item.ocr_text || '',
      answerText: item.answer_text || '',
      answerImageUrls: item.answer_image_urls || [],
      displayAnswers: item.display_answers || [],
      reason: item.reason || '',
      tags: item.tags || [],
    })
    wx.setNavigationBarTitle({ title: '编辑错题' })
  },

  onSubject(e) {
    this.setData({ subjectIndex: Number(e.detail.value) })
  },
  onOcr(e) { this.setData({ ocrText: e.detail.value }) },
  onAnswer(e) { this.setData({ answerText: e.detail.value }) },
  onReason(e) { this.setData({ reason: e.detail.value }) },
  onTagInput(e) { this.setData({ tagInput: e.detail.value }) },

  addTag(name) {
    const tag = String(name || '').trim().slice(0, 20)
    if (!tag || this.data.tags.includes(tag) || this.data.tags.length >= 20) return
    this.setData({ tags: this.data.tags.concat(tag), tagInput: '' })
  },

  onAddTag() {
    this.addTag(this.data.tagInput)
  },

  onHistoryTag(e) {
    this.addTag(e.currentTarget.dataset.tag)
  },

  removeTag(e) {
    const idx = Number(e.currentTarget.dataset.index)
    const tags = this.data.tags.slice()
    tags.splice(idx, 1)
    this.setData({ tags })
  },

  chooseImages(kind) {
    const isQuestion = kind === 'question'
    const urls = isQuestion ? this.data.imageUrls : this.data.answerImageUrls
    const remain = 6 - urls.length
    if (remain <= 0) return
    wx.chooseMedia({
      count: remain,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: async (res) => {
        wx.showLoading({ title: '上传中', mask: true })
        let ocrHint = ''
        try {
          let ocrText = this.data.ocrText
          const nextUrls = urls.slice()
          const nextViews = (isQuestion ? this.data.displayImages : this.data.displayAnswers).slice()
          for (const file of res.tempFiles || []) {
            const data = await uploadWrongbookImage(file.tempFilePath, kind)
            if (data.url) {
              nextUrls.push(data.url)
              nextViews.push(file.tempFilePath)
            }
            if (isQuestion && data.ocr_text) {
              ocrText = ocrText ? `${ocrText}\n${data.ocr_text}` : data.ocr_text
            } else if (isQuestion) {
              ocrHint = data.ocr_error || '未识别到文字，可手填题干'
            }
          }
          if (isQuestion) {
            this.setData({ imageUrls: nextUrls, displayImages: nextViews, ocrText })
          } else {
            this.setData({ answerImageUrls: nextUrls, displayAnswers: nextViews })
          }
        } catch (e) {
          ocrHint = e.message || '上传失败'
        } finally {
          wx.hideLoading()
        }
        if (ocrHint) {
          wx.showModal({
            title: '识别结果',
            content: ocrHint,
            showCancel: false,
          })
        }
      },
    })
  },

  chooseQuestion() { this.chooseImages('question') },
  chooseAnswer() { this.chooseImages('answer') },

  removeImage(e) {
    const kind = e.currentTarget.dataset.kind
    const idx = Number(e.currentTarget.dataset.index)
    if (kind === 'question') {
      const imageUrls = this.data.imageUrls.slice()
      const displayImages = this.data.displayImages.slice()
      imageUrls.splice(idx, 1)
      displayImages.splice(idx, 1)
      this.setData({ imageUrls, displayImages })
      return
    }
    const answerImageUrls = this.data.answerImageUrls.slice()
    const displayAnswers = this.data.displayAnswers.slice()
    answerImageUrls.splice(idx, 1)
    displayAnswers.splice(idx, 1)
    this.setData({ answerImageUrls, displayAnswers })
  },

  preview(e) {
    const urls = e.currentTarget.dataset.urls || []
    const current = e.currentTarget.dataset.current || urls[0]
    if (!urls.length) return
    wx.previewImage({ current, urls })
  },

  async submit() {
    if (this.data.submitting) return
    const subject = this.data.subjects[this.data.subjectIndex]
    if (!subject) {
      wx.showToast({ title: '请选择学科', icon: 'none' })
      return
    }
    if (!this.data.imageUrls.length) {
      wx.showToast({ title: '请至少上传一张题目原图', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    const payload = {
      subject_id: subject.id,
      image_urls: this.data.imageUrls,
      ocr_text: this.data.ocrText,
      answer_text: this.data.answerText,
      answer_image_urls: this.data.answerImageUrls,
      reason: this.data.reason,
      tags: this.data.tags,
    }
    try {
      if (this.data.id) {
        await request({ url: `/wrongbook/${this.data.id}`, method: 'PUT', data: payload })
      } else {
        await request({ url: '/wrongbook', method: 'POST', data: payload })
      }
      wx.showToast({ title: '已保存', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 400)
    } catch (e) {
      this.setData({ submitting: false })
    }
  },
})
