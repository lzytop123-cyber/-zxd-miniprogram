import json
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
items=json.load(open(r'F:/zxd-pro/SOP模板/templates.json',encoding='utf-8'))
d=Document(); sec=d.sections[0]; sec.page_height=Cm(29.7); sec.page_width=Cm(21); sec.top_margin=Cm(1.8); sec.bottom_margin=Cm(1.8); sec.left_margin=Cm(2); sec.right_margin=Cm(2)
for name in ['Normal','Title','Heading 1','Heading 2']:
 s=d.styles[name]; s.font.name='Microsoft YaHei'; s._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft YaHei'); s.font.color.rgb=RGBColor(0,0,0)
 s.font.size=Pt({'Normal':10.5,'Title':24,'Heading 1':17,'Heading 2':11}[name]); s.paragraph_format.space_after=Pt(6)
d.styles['Normal'].paragraph_format.line_spacing=1.15
p=d.add_paragraph('全栈开发与项目管理 SOP 产出物模板',style='Title')
d.add_paragraph('适用于个人开发者与小型团队的项目交付和长期维护')
d.add_heading('使用方法',1)
d.add_paragraph('本模板集包含 8 个核心 SOP 对应的 22 份产出物，以及 2 份选用模板。每次使用时复制相关模板，替换方括号提示并补充记录；不适用的内容填写“不适用”及理由。')
d.add_paragraph('同一项目可由同一人兼任执行人与项目负责人；涉及范围承诺、业务验收和重大风险接受时，仍应记录相应业务决策人的明确确认。')
d.add_paragraph('统一填写：项目名称、记录编号、版本、维护人、日期与资料位置。日期建议使用 YYYY-MM-DD，故障时间注明时区。链接到实际资料即可，避免重复维护。')
d.add_paragraph('工作量与日历排期分别填写。记录之间用编号关联：需求 → 任务 → 代码变更 → 测试 → 验收 → 发布；故障和变更记录关联对应版本。')
d.add_heading('模板索引',1)
for group in dict.fromkeys(i[2] for i in items):
 d.add_paragraph(group+'：'+'、'.join(i[0]+' '+i[1] for i in items if i[2]==group))
d.add_paragraph('文档版本：1.0    项目名称：[填写]    模板维护人：[填写]')
for ident,title,group,when,fields,sections,cols,done in items:
 d.add_page_break(); d.add_heading(ident+' '+title,1)
 d.add_paragraph('所属流程：'+group+'。'+when)
 d.add_paragraph('项目：[填写]    记录编号：[填写]    版本：[填写]')
 d.add_paragraph('维护人：[填写]    更新日期：[填写]    资料位置：[填写]')
 d.add_heading('基本信息',2)
 d.add_paragraph('  /  '.join(x+'：[填写]' for x in fields.split('；')))
 for line in sections.split('\n'):
  h,txt=line.split('|',1); d.add_heading(h,2); d.add_paragraph(txt+'\n[在此填写]')
 d.add_heading('执行与跟踪记录',2)
 heads=cols.split('｜'); t=d.add_table(rows=1, cols=len(heads)); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.autofit=False
 widths=([3.2,4.6,5,4.2] if len(heads)==4 else [3.1,3.6,3.8,3.4,3.1])
 for c,w in zip(t.columns,widths): c.width=Cm(w)
 for c,txt in zip(t.rows[0].cells,heads): c.text=txt
 for n in range(2):
  row=t.add_row()
  for c in row.cells: c.text='[填写]'
 for ri,row in enumerate(t.rows):
  trPr=row._tr.get_or_add_trPr(); no=OxmlElement('w:cantSplit'); trPr.append(no)
  if ri==0: trPr.append(OxmlElement('w:tblHeader'))
  for c in row.cells:
   c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   pr=c._tc.get_or_add_tcPr(); shade=OxmlElement('w:shd'); shade.set(qn('w:fill'),'DFEAF4' if ri==0 else ('F5F7F9' if ri%2==0 else 'FFFFFF')); pr.append(shade)
   borders=OxmlElement('w:tcBorders')
   for edge in ['top','left','bottom','right']:
    e=OxmlElement('w:'+edge); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4'); e.set(qn('w:color'),'D9D9D9'); borders.append(e)
   pr.append(borders)
   for p in c.paragraphs:
    p.paragraph_format.space_before=Pt(4); p.paragraph_format.space_after=Pt(4)
    for r in p.runs: r.font.size=Pt(9); r.bold=ri==0
 d.add_paragraph('可按需增加记录行。')
 d.add_heading('完成检查与确认',2); d.add_paragraph('□ '+done+'\n结论：[填写]    确认人：[填写]    确认日期或证据：[填写]')
d.save(r'F:/zxd-pro/SOP模板/全栈开发与项目管理SOP产出物模板.docx')
print('Saved',len(items),'templates')
