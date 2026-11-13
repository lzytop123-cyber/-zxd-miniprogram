from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


OUT = Path(__file__).parent
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
_fonts = {}


def f(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(FONT_BOLD if bold else FONT), size)
    return _fonts[key]


def text(d, xy, value, size=20, color="#1C2B20", bold=False, anchor=None):
    d.text(xy, value, font=f(size, bold), fill=color, anchor=anchor)


def rr(d, box, radius, fill, outline=None, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def shadow(img, box, radius=24, blur=18, opacity=40, offset=(0, 8)):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    x1, y1, x2, y2 = box
    ld.rounded_rectangle((x1 + offset[0], y1 + offset[1], x2 + offset[0], y2 + offset[1]), radius, fill=(21, 32, 29, opacity))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def chevron(d, x, y, color="#8A958C", size=7):
    d.line((x, y-size, x+size, y, x, y+size), fill=color, width=2, joint="curve")


def topbar(d, x, y, w, name, back=False):
    text(d, (x+20, y+22), "9:41", 14, "#1C2B20", True)
    d.ellipse((x+w-83, y+25, x+w-76, y+32), fill="#1C2B20")
    d.ellipse((x+w-69, y+22, x+w-59, y+32), fill="#1C2B20")
    rr(d, (x+w-49, y+21, x+w-24, y+33), 6, None, "#1C2B20", 2)
    rr(d, (x+w-23, y+25, x+w-20, y+29), 1, "#1C2B20")
    if back:
        d.line((x+29,y+71,x+21,y+79,x+29,y+87), fill="#1C2B20", width=3)
    text(d, (x+w//2, y+80), name, 20, "#1C2B20", True, "mm")
    rr(d, (x+w-83,y+61,x+w-19,y+98), 18, "#FFFFFF", "#E2E8E0")
    text(d, (x+w-65,y+80), "···", 19, "#1C2B20", True, "mm")
    d.line((x+w-45,y+68,x+w-45,y+90),fill="#E2E8E0",width=1)
    d.ellipse((x+w-38,y+73,x+w-25,y+86),outline="#1C2B20",width=2)


def store_illustration(d, box, variant=0):
    x1,y1,x2,y2=box
    rr(d,box,14,"#D8F3DC" if variant else "#DDECE0")
    d.polygon([(x1,y2),(x1,y1+43),(x2,y1+18),(x2,y2)],fill="#BDE3CB" if variant else "#BFD7C7")
    d.rectangle((x1+21,y1+35,x2-22,y2),fill="#F6F3E8")
    d.polygon([(x1+10,y1+45),(x1+70,y1+13),(x2-8,y1+45)],fill="#4D8A66" if variant else "#658A71")
    for i in range(3):
        xx=x1+43+i*31
        rr(d,(xx,y1+53,xx+20,y1+80),3,"#A7D6C4")
        d.line((xx+10,y1+53,xx+10,y1+80),fill="#F6F3E8",width=2)
    d.ellipse((x2-28,y1+12,x2-17,y1+23),fill="#FAF5C4")


def store_card(d, x, y, w, name, addr, distance, variant=0):
    rr(d,(x,y,x+w,y+155),18,"#FFFFFF", "#E6EBE6")
    store_illustration(d,(x+14,y+14,x+132,y+141),variant)
    text(d,(x+146,y+22),name,20,"#1C2B20",True)
    rr(d,(x+w-65,y+19,x+w-17,y+46),13,"#E4F5E9")
    text(d,(x+w-41,y+32),"营业中",12,"#2D6A4F",True,"mm")
    text(d,(x+146,y+62),addr,13,"#6F7D73")
    d.line((x+146,y+98,x+w-18,y+98),fill="#EFF2ED",width=1)
    text(d,(x+146,y+114),"可预约",13,"#2D6A4F",True)
    text(d,(x+w-45,y+114),distance,13,"#6F7D73",anchor="ra")
    chevron(d,x+w-24,y+121)


def phone_base(img, x, y, w=400, h=846):
    shadow(img,(x,y,x+w,y+h),36,22,42,(0,12))
    d=ImageDraw.Draw(img)
    rr(d,(x,y,x+w,y+h),36,"#F7F8F4", "#D9E1DA",2)
    return d


def mini_program():
    im=Image.new("RGBA",(1500,1190),"#EFF4EE")
    d=ImageDraw.Draw(im)
    rr(d,(70,58,1430,1158),34,"#F8FBF8")
    rr(d,(103,97,229,133),18,"#E1F2E6")
    text(d,(166,115),"小程序 · 原型",15,"#2D6A4F",True,"mm")
    text(d,(105,156),"同一个小程序，选择不同门店",38,"#1C2B20",True)
    text(d,(107,217),"上线后的用户端示意：沿用现有门店卡片与绿色选座页；新分店拥有自己的座位图。",18,"#6F7D73")
    px1,py=250,285
    px2=850
    w,h=400,846
    d=phone_base(im,px1,py,w,h)
    topbar(d,px1,py,w,"知行岛自习室")
    text(d,(px1+25,py+126),"附近门店",29,"#1C2B20",True)
    text(d,(px1+25,py+171),"选一家喜欢的自习室，开始专注时间",14,"#6F7D73")
    rr(d,(px1+23,py+211,px1+w-23,py+254),13,"#FFFFFF","#E2EAE2")
    d.ellipse((px1+35,py+222,px1+47,py+234),outline="#809588",width=2)
    d.line((px1+46,py+233,px1+52,py+239),fill="#809588",width=2)
    text(d,(px1+63,py+232),"搜索门店",14,"#9AA69B",anchor="lm")
    store_card(d,px1+23,py+279,w-46,"知行岛 · 原门店","市中心 · 学府路 18 号","1.2 km",0)
    store_card(d,px1+23,py+449,w-46,"知行岛 · 新分店","新城区 · 地址待配置","3.8 km",1)
    rr(d,(px1+23,py+635,px1+w-23,py+691),15,"#E8F5E9")
    text(d,(px1+43,py+663),"每家门店独立管理座位与订单",15,"#2D6A4F",True,"lm")
    d.rectangle((px1+1,py+h-75,px1+w-1,py+h-1),fill="#FFFFFF")
    d.line((px1+1,py+h-75,px1+w-1,py+h-75),fill="#E9EEE8",width=1)
    for cx,label,active in [(px1+68,"首页",True),(px1+199,"订单",False),(px1+333,"我的",False)]:
        col="#2D6A4F" if active else "#98A49A"
        d.ellipse((cx-9,py+h-61,cx+9,py+h-43),outline=col,width=2)
        text(d,(cx,py+h-23),label,12,col,active,"mm")
    rr(d,(px1+148,py+h-9,px1+252,py+h-5),2,"#223229")

    d=phone_base(im,px2,py,w,h)
    topbar(d,px2,py,w,"选择座位",True)
    rr(d,(px2+20,py+116,px2+w-20,py+199),17,"#FFFFFF")
    text(d,(px2+38,py+133),"知行岛 · 新分店",19,"#1C2B20",True)
    rr(d,(px2+38,py+169,px2+137,py+191),11,"#E4F5E9")
    text(d,(px2+87,py+179),"当前门店",12,"#2D6A4F",True,"mm")
    text(d,(px2+w-49,py+173),"切换 ›",13,"#2D6A4F",True,"mm")
    text(d,(px2+22,py+225),"请选择座位",24,"#1C2B20",True)
    text(d,(px2+23,py+260),"座位图示意 · 平面图可在后台替换",13,"#6F7D73")
    rr(d,(px2+20,py+292,px2+w-20,py+675),17,"#FFFFFF","#E2EAE2")
    text(d,(px2+w//2,py+316),"入口",13,"#718477",anchor="mm")
    d.line((px2+101,py+330,px2+w-101,py+330),fill="#DDE7DD",width=2)
    rr(d,(px2+45,py+355,px2+160,py+376),5,"#E6F0E7")
    text(d,(px2+102,py+365),"公共区",12,"#75967D",anchor="mm")
    for row in range(4):
        for col in range(4):
            idx=row*4+col+1
            sx=px2+52+col*77
            sy=py+397+row*61
            if idx in (3,11):
                fill,outline,fg="#EEF0EE",None,"#A3AAA4"
            elif idx==8:
                fill,outline,fg="#2D6A4F",None,"#FFFFFF"
            else:
                fill,outline,fg="#E6F4E9","#CBE5D0","#2D6A4F"
            rr(d,(sx,sy,sx+62,sy+44),9,fill,outline)
            text(d,(sx+31,sy+22),f"{idx:02d}",15,fg,True,"mm")
    text(d,(px2+49,py+655),"●  可选",12,"#2D6A4F")
    text(d,(px2+148,py+655),"●  已选",12,"#1C5B3E")
    text(d,(px2+253,py+655),"●  不可选",12,"#9AA59C")
    rr(d,(px2+20,py+694,px2+w-20,py+760),16,"#FFFFFF")
    text(d,(px2+39,py+708),"已选座位",13,"#6F7D73")
    text(d,(px2+39,py+732),"08 号 · 公共区",17,"#1C2B20",True)
    rr(d,(px2+226,py+708,px2+w-36,py+748),13,"#52B788")
    text(d,(px2+292,py+727),"下一步",16,"#FFFFFF",True,"mm")
    rr(d,(px2+148,py+h-9,px2+252,py+h-5),2,"#223229")

    text(d,(px1+200,py-23),"① 选门店",18,"#426F50",True,"mm")
    text(d,(px2+200,py-23),"② 进分店选座",18,"#426F50",True,"mm")
    im.convert("RGB").save(OUT/"branch-mini-program.png",quality=95)


def field(d, x, y, w, label, value, small=False):
    text(d,(x,y),label,13,"#62666D")
    rr(d,(x,y+26,x+w,y+65),7,"#FFFFFF","#DCE0E4")
    text(d,(x+13,y+45),value,13 if small else 15,"#24262B",anchor="lm")


def admin():
    im=Image.new("RGBA",(1600,1000),"#F6F7F9")
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,240,1000),fill="#17191F")
    rr(d,(24,23,214,69),9,"#FFD000")
    text(d,(119,46),"知行岛 · 管理后台",18,"#16171D",True,"mm")
    text(d,(28,105),"工作台",13,"#7E828A")
    for yy,label in [(145,"概览"),(196,"门店管理"),(247,"座位管理"),(298,"订单管理"),(349,"会员管理"),(400,"财务报表")]:
        if label=="座位管理":
            rr(d,(14,yy-8,226,yy+37),8,"#373A42")
            rr(d,(14,yy-8,19,yy+37),2,"#FFD000")
        d.ellipse((36,yy+8,45,yy+17),outline="#FFD000" if label=="座位管理" else "#9B9DA3",width=2)
        text(d,(69,yy+13),label,16,"#FFFFFF" if label=="座位管理" else "#BFC1C6",label=="座位管理", "lm")
    d.line((20,912,220,912),fill="#35383F")
    d.ellipse((28,932,64,968),fill="#FFD000")
    text(d,(46,949),"管",14,"#17191F",True,"mm")
    text(d,(76,940),"管理员",14,"#ECEDEF")
    text(d,(76,958),"总店账号",11,"#93969E")

    d.rectangle((240,0,1600,67),fill="#FFFFFF")
    d.line((240,67,1600,67),fill="#E7E9EC",width=1)
    text(d,(275,33),"门店管理  /  座位管理  /  座位图设置",14,"#7A7E85",anchor="lm")
    rr(d,(1412,18,1543,50),16,"#F4F5F6")
    text(d,(1477,34),"新分店",14,"#2C2E34",True,"mm")
    d.ellipse((1555,19,1588,52),fill="#FFD000")
    text(d,(1571,35),"管",13,"#16171D",True,"mm")

    text(d,(277,104),"座位图设置",30,"#16171D",True)
    text(d,(279,152),"为每家门店单独上传平面图、摆放座位，确认后发布。",15,"#737780")
    rr(d,(1392,103,1543,143),7,"#FFD000")
    text(d,(1467,123),"预览小程序",15,"#16171D",True,"mm")

    rr(d,(270,185,1570,249),12,"#FFFFFF","#E8EAED")
    text(d,(292,217),"当前门店",14,"#737780",anchor="lm")
    rr(d,(373,197,579,238),7,"#FFFFFF","#DDE0E4")
    text(d,(392,217),"知行岛 · 新分店",15,"#1E2026",True,"lm")
    d.line((551,213,558,220,565,213),fill="#737780",width=2)
    rr(d,(597,205,670,231),13,"#F6F0DB")
    text(d,(633,218),"未营业",12,"#866C11",True,"mm")
    rr(d,(688,205,778,231),13,"#E8F2EB")
    text(d,(733,218),"草稿状态",12,"#407452",True,"mm")
    text(d,(1539,217),"每店独立配置",14,"#92969C",anchor="rm")

    rr(d,(270,271,1161,927),12,"#FFFFFF","#E8EAED")
    text(d,(292,302),"座位平面图",20,"#202228",True)
    text(d,(293,333),"拖动座位到正确位置，点击座位可编辑编号与区域",13,"#858991")
    rr(d,(885,292,1006,331),7,"#FFFFFF","#DCE0E4")
    text(d,(945,311),"替换平面图",14,"#2B2D32",anchor="mm")
    rr(d,(1022,292,1136,331),7,"#FFD000")
    text(d,(1079,311),"添加座位",14,"#1D1F23",True,"mm")

    mx1,my1,mx2,my2=294,359,1137,846
    rr(d,(mx1,my1,mx2,my2),10,"#F8F9F6","#E1E5E1")
    d.rectangle((mx1+41,my1+32,mx2-40,my2-45),fill="#FBFBF7")
    d.line((mx1+41,my1+32,mx2-40,my1+32),fill="#B3BEB4",width=8)
    d.line((mx1+41,my1+32,mx1+41,my2-45),fill="#B3BEB4",width=8)
    d.line((mx2-40,my1+32,mx2-40,my2-45),fill="#B3BEB4",width=8)
    d.line((mx1+41,my2-45,mx1+337,my2-45),fill="#B3BEB4",width=8)
    d.line((mx1+437,my2-45,mx2-40,my2-45),fill="#B3BEB4",width=8)
    d.line((mx1+337,my2-45,mx1+437,my2-45),fill="#F8F9F6",width=12)
    rr(d,(mx1+65,my1+61,mx1+290,my1+104),8,"#EBF2EC")
    text(d,(mx1+177,my1+82),"开放座位区",16,"#738F7A",True,"mm")
    rr(d,(mx1+511,my1+62,mx1+749,my1+104),8,"#EDF0EB")
    text(d,(mx1+630,my1+82),"安静座位区",16,"#829388",True,"mm")
    d.line((mx1+420,my1+47,mx1+420,my2-125),fill="#C9D2C9",width=5)
    for row in range(3):
        for col in range(4):
            idx=row*4+col+1
            xx=mx1+85+col*78
            yy=my1+143+row*88
            chosen=idx==8
            rr(d,(xx,yy,xx+58,yy+50),7,"#FFD000" if chosen else "#FFFFFF","#E0B800" if chosen else "#AFC3B4",2)
            text(d,(xx+29,yy+25),f"{idx:02d}",16,"#1A1D20" if chosen else "#447357",True,"mm")
            if chosen:
                d.rounded_rectangle((xx-6,yy-6,xx+64,yy+56),radius=10,outline="#FFD000",width=2)
    for row in range(3):
        for col in range(3):
            idx=13+row*3+col
            xx=mx1+491+col*77
            yy=my1+143+row*88
            rr(d,(xx,yy,xx+58,yy+50),7,"#FFFFFF","#AFC3B4",2)
            text(d,(xx+29,yy+25),f"{idx:02d}",16,"#447357",True,"mm")
    rr(d,(mx1+355,my2-88,mx1+455,my2-53),8,"#F8F9F6")
    text(d,(mx1+405,my2-70),"入口",15,"#758176",True,"mm")
    text(d,(mx1+70,my2-72),"示意底图 · 实际平面图确定后可替换",13,"#909B91")
    text(d,(292,880),"当前底图：示意平面图.png",13,"#858991")
    text(d,(1107,880),"缩放  －   100%   ＋",13,"#676B72",anchor="ra")

    rr(d,(1182,271,1570,927),12,"#FFFFFF","#E8EAED")
    text(d,(1206,303),"座位属性",20,"#202228",True)
    rr(d,(1465,287,1543,318),15,"#FFF5CA")
    text(d,(1504,302),"已选 08",13,"#715B00",True,"mm")
    d.line((1206,336,1544,336),fill="#EDF0F1")
    field(d,1207,357,335,"座位编号","08")
    field(d,1207,446,335,"所属区域","开放座位区")
    text(d,(1207,538),"座位状态",13,"#62666D")
    rr(d,(1207,566,1367,605),7,"#FFF7D7","#FFD000")
    text(d,(1287,585),"可预约",14,"#5E4D06",True,"mm")
    rr(d,(1381,566,1542,605),7,"#FFFFFF","#DCE0E4")
    text(d,(1461,585),"暂不可约",14,"#676B72",anchor="mm")
    rr(d,(1207,640,1543,729),8,"#F8F9FA")
    text(d,(1224,660),"关于替换底图",14,"#45494F",True)
    text(d,(1224,687),"替换底图会保留座位编号与订单。",13,"#777C84")
    text(d,(1224,710),"请检查座位位置后再发布。",13,"#777C84")
    rr(d,(1207,823,1543,869),7,"#FFFFFF","#E3E6E8")
    text(d,(1375,846),"删除当前座位",14,"#B95443",anchor="mm")
    text(d,(1207,897),"图上座位：21 个",13,"#858991")

    rr(d,(270,942,1570,994),0,"#FFFFFF")
    d.line((270,942,1570,942),fill="#E8EAED")
    text(d,(291,968),"座位图发布后，新店仍需完成营业与收款配置才能对用户开放。",13,"#777C84",anchor="lm")
    rr(d,(1207,951,1321,987),7,"#FFFFFF","#DCE0E4")
    text(d,(1264,969),"保存草稿",14,"#2A2C32",anchor="mm")
    rr(d,(1333,951,1430,987),7,"#FFFFFF","#DCE0E4")
    text(d,(1381,969),"预览",14,"#2A2C32",anchor="mm")
    rr(d,(1442,951,1551,987),7,"#FFD000")
    text(d,(1496,969),"发布座位图",14,"#17191F",True,"mm")
    im.convert("RGB").save(OUT/"branch-admin-seat-editor.png",quality=95)


def admin_store_settings():
    im=Image.new("RGBA",(1600,1000),"#F6F7F9")
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,240,1000),fill="#17191F")
    rr(d,(24,23,214,69),9,"#FFD000")
    text(d,(119,46),"知行岛 · 管理后台",18,"#16171D",True,"mm")
    text(d,(28,105),"工作台",13,"#7E828A")
    for yy,label in [(145,"概览"),(196,"门店管理"),(247,"座位管理"),(298,"订单管理"),(349,"会员管理"),(400,"财务报表")]:
        if label=="门店管理":
            rr(d,(14,yy-8,226,yy+37),8,"#373A42")
            rr(d,(14,yy-8,19,yy+37),2,"#FFD000")
        d.ellipse((36,yy+8,45,yy+17),outline="#FFD000" if label=="门店管理" else "#9B9DA3",width=2)
        text(d,(69,yy+13),label,16,"#FFFFFF" if label=="门店管理" else "#BFC1C6",label=="门店管理","lm")
    d.line((20,912,220,912),fill="#35383F")
    d.ellipse((28,932,64,968),fill="#FFD000")
    text(d,(46,949),"管",14,"#17191F",True,"mm")
    text(d,(76,940),"管理员",14,"#ECEDEF")
    text(d,(76,958),"总店账号",11,"#93969E")
    d.rectangle((240,0,1600,67),fill="#FFFFFF")
    d.line((240,67,1600,67),fill="#E7E9EC")
    text(d,(275,33),"门店管理  /  知行岛 · 新分店",14,"#7A7E85",anchor="lm")
    rr(d,(1412,18,1543,50),16,"#F4F5F6")
    text(d,(1477,34),"新分店",14,"#2C2E34",True,"mm")
    d.ellipse((1555,19,1588,52),fill="#FFD000")
    text(d,(1571,35),"管",13,"#16171D",True,"mm")

    text(d,(277,104),"门店设置 · 新分店",30,"#16171D",True)
    rr(d,(592,111,665,140),14,"#F6F0DB")
    text(d,(628,125),"未营业",12,"#866C11",True,"mm")
    text(d,(279,152),"分店资料、座位图和收款账户分别配置，检查通过后再开放预约。",15,"#737780")
    rr(d,(1404,103,1543,143),7,"#ECEEF0")
    text(d,(1473,123),"开放营业",15,"#9A9EA4",True,"mm")
    rr(d,(270,185,1570,244),11,"#FFFFFF","#E8EAED")
    for xx,w,label,active in [(288,125,"基本信息",False),(427,125,"座位图",False),(566,145,"收款配置",True),(725,125,"店员权限",False)]:
        text(d,(xx+w//2,212),label,16,"#1F2127" if active else "#7D8188",active,"mm")
        if active:
            rr(d,(xx+22,239,xx+w-22,243),2,"#FFD000")

    rr(d,(270,264,1008,909),12,"#FFFFFF","#E8EAED")
    text(d,(294,295),"本店收款主体",21,"#202228",True)
    rr(d,(849,282,981,313),15,"#FFF4D8")
    text(d,(915,297),"待开通商户号",13,"#8D6815",True,"mm")
    text(d,(294,330),"新分店订单将结算到这里绑定的公司商户账户。",14,"#81858C")
    d.line((294,357,982,357),fill="#EDF0F1")
    field(d,294,381,332,"收款公司","姐姐公司的名称（待填写）",True)
    field(d,650,381,332,"微信支付商户号","取得后填写",True)
    field(d,294,478,688,"结算银行卡","待商户号审核通过后确认；此处仅展示尾号与账户名",True)
    rr(d,(294,575,982,660),8,"#F7F8FA")
    text(d,(314,594),"小程序 AppID 关联",15,"#33363C",True)
    text(d,(314,625),"商户平台完成小程序关联与授权后，后台显示“已绑定”。",13,"#72777E")
    rr(d,(860,595,962,630),17,"#ECEEF0")
    text(d,(911,612),"待绑定",13,"#8A8F96",True,"mm")
    rr(d,(294,683,982,772),8,"#FFF9E7")
    text(d,(314,703),"上线前检查",15,"#66500E",True)
    text(d,(314,732),"商户号已开通、主体已确认、AppID 已关联、支付测试通过。",13,"#756329")
    text(d,(294,803),"原门店继续使用原有收款配置；各店订单和对账按门店查看。",14,"#72777E")
    rr(d,(842,841,982,885),7,"#FFD000")
    text(d,(912,863),"保存配置",15,"#1B1D21",True,"mm")

    rr(d,(1027,264,1570,909),12,"#FFFFFF","#E8EAED")
    text(d,(1053,295),"开店进度",21,"#202228",True)
    text(d,(1054,331),"完成以下设置后，再开放新店预约",14,"#81858C")
    d.line((1053,357,1543,357),fill="#EDF0F1")
    steps=[("门店基本信息","已保存","#398759"),("座位平面图","草稿中","#AD7B13"),("分店收款账户","待配置","#A56B1B"),("店员账号与权限","待配置","#8B9096"),("预约与支付测试","未开始","#8B9096")]
    for i,(label,status,col) in enumerate(steps):
        yy=390+i*80
        rr(d,(1053,yy,1543,yy+63),8,"#FAFBFB","#ECEFF0")
        d.ellipse((1071,yy+20,1095,yy+44),fill="#E6F3E9" if i==0 else "#F3F4F5")
        text(d,(1083,yy+32),"✓" if i==0 else str(i+1),13,"#328450" if i==0 else "#8B9096",True,"mm")
        text(d,(1111,yy+24),label,15,"#32353B",True)
        text(d,(1514,yy+30),status,13,col,True,"rm")
    rr(d,(1053,817,1543,878),8,"#F7F8FA")
    text(d,(1072,837),"座位图可先用示意底图制作草稿，",13,"#656A71")
    text(d,(1072,858),"正式平面图确定后替换，再发布。",13,"#656A71")
    im.convert("RGB").save(OUT/"branch-admin-store-settings.png",quality=95)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    mini_program()
    admin()
    admin_store_settings()
