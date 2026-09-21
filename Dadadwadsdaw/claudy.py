import os, shutil, sys, zipfile, json, threading, base64
import urllib.request, urllib.error
from urllib.parse import quote
from PySide6.QtCore import Qt, QVariantAnimation, QEasingCurve, QTimer, QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QFrame, QMainWindow, QScrollArea, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QFileDialog, QGraphicsBlurEffect, QGraphicsOpacityEffect,
)

BG="#131313"; SUR="#191919"; BRD="#2a2a2a"; SEP="#1e1e1e"
TEXT="#ffffff"; BLUE="#0a6ec8"; MUTED="#8a8a8a"
FILE_HINT="Нажмите, чтобы выбрать файл."
S=1.0
BASE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(BASE)
CACHE_DIR=os.path.join(ROOT,"Cache"); APPS_DIR=os.path.join(ROOT,"apps")
os.makedirs(CACHE_DIR,exist_ok=True); os.makedirs(APPS_DIR,exist_ok=True)
sys.path.insert(0,BASE)
try: from token_store import embedded_token
except Exception: embedded_token=lambda:""
GIT="https://api.github.com/"

def _gh(method,url,data=None,timeout=15):
    req=urllib.request.Request(url,method=method); tok=embedded_token()
    if tok: req.add_header("Authorization","Bearer "+tok)
    req.add_header("Accept","application/vnd.github+json")
    req.add_header("User-Agent","Claudy")
    body=None
    if data is not None:
        body=json.dumps(data).encode("utf-8")
        req.add_header("Content-Type","application/json")
    try:
        with urllib.request.urlopen(req,body,timeout=timeout) as r:
            raw=r.read(); return r.status,(json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        try: return e.code,json.loads(e.read())
        except Exception: return e.code,{}
    except Exception: return -1,{}

def px(v): return int(v*S)
def stl(w,s): w.setStyleSheet(s)
def geo(w,x,y,a,b): w.setGeometry(px(x),px(y),px(a),px(b))
def lbl(t,p=None): return QLabel(t,p)
def hline(p,x,y,a):
    f=QFrame(p); geo(f,x,y,a,2); stl(f,f"background-color:{SEP};border:none;"); return f
def box(p,x,y,a,b):
    f=QFrame(p); geo(f,x,y,a,b)
    stl(f,f"background-color:{SUR};border:1px solid {BRD};border-radius:{px(8)}px;"); return f
def qfield(p,x,y,ph,n,width=330):
    e=QLineEdit(p); geo(e,x,y,width,30); e.setMaxLength(n); e.setPlaceholderText(ph)
    stl(e,"QLineEdit{color:#ffffff;background:#292929;border:1px solid #3a3a3a;"
          "border-radius:6px;font-size:13px;font-weight:700;padding-left:8px;}"
          "QLineEdit:focus{border:2px solid #0a6ec8;}"
          "QLineEdit::placeholder{color:#7a7a7a;font-weight:700;}")
    return e
def flbl(p,x,y,t,s,width=300):
    f=lbl(t,p); geo(f,x,y,width,22)
    stl(f,f"color:{TEXT};background:transparent;border:none;"
           f"font-size:{px(s)}px;font-weight:700;"); return f
def _hex(c):
    c=c.lstrip("#"); return tuple(int(c[i:i+2],16) for i in (0,2,4))
def _mix(a,b,t):
    A,B=_hex(a),_hex(b)
    return "#%02x%02x%02x"%(round(A[0]+(B[0]-A[0])*t),
                            round(A[1]+(B[1]-A[1])*t),
                            round(A[2]+(B[2]-A[2])*t))
def _fmt_size(n):
    if n<1<<10: return "%d Б"%n
    if n<1<<20: return "%.1f КБ"%(n/(1<<10))
    if n<1<<30: return "%.1f МБ"%(n/(1<<20))
    return "%.1f ГБ"%(n/(1<<30))

class NavItem(QLabel):
    def __init__(self,text,emoji,on_click):
        super().__init__(f"{emoji}  {text}")
        self.tt=text; self.on_click=on_click; self._active=False
        self.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.setFixedHeight(px(30)); self._apply()
    def _apply(self):
        stl(self,f"color:{TEXT};background:{'#313131' if self._active else 'transparent'};"
                f"border:none;border-radius:{px(6)}px;font-size:{px(14)}px;"
                "font-weight:600;padding-left:10px;")
    def enterEvent(self,e):
        if not self._active:
            stl(self,f"color:{TEXT};background:#313131;border:none;"
                    f"border-radius:{px(6)}px;font-size:{px(14)}px;"
                    "font-weight:600;padding-left:10px;")
        super().enterEvent(e)
    def leaveEvent(self,e): self._apply(); super().leaveEvent(e)
    def mousePressEvent(self,e): self.on_click(self); super().mousePressEvent(e)
    def set_active(self,active): self._active=active; self._apply()

class GhostRow(QLabel):
    def __init__(self,text,on_click=None):
        super().__init__(text); self.on_click=on_click
        self.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self._apply()
    def _apply(self):
        stl(self,f"color:#ffffff;background:transparent;border:none;"
                 f"border-radius:{px(6)}px;font-size:{px(15)}px;"
                 "font-weight:700;padding-left:12px;")
    def enterEvent(self,e):
        stl(self,f"color:#ffffff;background:#313131;border:none;"
                 f"border-radius:{px(6)}px;font-size:{px(15)}px;"
                 "font-weight:700;padding-left:12px;")
        super().enterEvent(e)
    def leaveEvent(self,e): self._apply(); super().leaveEvent(e)
    def mousePressEvent(self,e):
        if self.on_click: self.on_click()
        super().mousePressEvent(e)

class CardPipe(QLabel):
    def __init__(self):
        super().__init__("|"); self.setAlignment(Qt.AlignCenter)
        stl(self,"color:#55555a;background:transparent;border:none;"
                 "font-size:13px;font-weight:600;")

class BoxButton(QLabel):
    def __init__(self,text,on_click=None):
        super().__init__(text); self.on_click=on_click
        self.setAlignment(Qt.AlignCenter); self._h=False
        stl(self,"color:#bdbdbd;background:#2a2a30;border:1px solid #3a3a3a;"
                 "border-radius:6px;font-size:13px;font-weight:600;")
    def enterEvent(self,e):
        self._h=True
        stl(self,"color:#ffffff;background:#34343c;border:1px solid #4a4a4a;"
                 "border-radius:6px;font-size:13px;font-weight:600;")
        super().enterEvent(e)
    def leaveEvent(self,e):
        self._h=False
        stl(self,"color:#bdbdbd;background:#2a2a30;border:1px solid #3a3a3a;"
                 "border-radius:6px;font-size:13px;font-weight:600;")
        super().leaveEvent(e)
    def mousePressEvent(self,e):
        if self.on_click: self.on_click()
        super().mousePressEvent(e)

class DotsBox(QLabel):
    def __init__(self,on_click=None):
        super().__init__("···"); self.on_click=on_click
        self.setAlignment(Qt.AlignCenter); self.setFixedSize(px(26),px(26))
        self._h=False; self._apply()
    def _apply(self):
        stl(self,f"color:#9a9a9a;background:{'#313131' if self._h else 'transparent'};"
                 f"border:none;border-radius:{px(5)}px;font-size:{px(15)}px;font-weight:700;")
    def enterEvent(self,e): self._h=True; self._apply(); super().enterEvent(e)
    def leaveEvent(self,e): self._h=False; self._apply(); super().leaveEvent(e)
    def mousePressEvent(self,e):
        if self.on_click: self.on_click()
        super().mousePressEvent(e)

class StarBox(QLabel):
    def __init__(self,on_toggle=None):
        super().__init__("☆"); self.on_toggle=on_toggle; self._on=False
        self.setAlignment(Qt.AlignCenter); self.setFixedSize(px(26),px(26))
        self._h=False; self._apply()
    def _apply(self):
        ch="★" if self._on else "☆"
        stl(self,f"color:{'#f5c542' if self._on else '#9a9a9a'};"
                 f"background:{'#313131' if self._h or self._on else 'transparent'};"
                 f"border:{'1px solid #f5c542' if self._on and not self._h else 'none'};"
                 f"border-radius:{px(5)}px;font-size:{px(16)}px;font-weight:700;")
    def enterEvent(self,e): self._h=True; self._apply(); super().enterEvent(e)
    def leaveEvent(self,e): self._h=False; self._apply(); super().leaveEvent(e)
    def mousePressEvent(self,e):
        self._on=not self._on
        if self.on_toggle: self.on_toggle(self._on)
        self._apply(); super().mousePressEvent(e)

class HoverCell(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground,True)
        stl(self,"background:transparent;border:none;")

class GameCard(QFrame):
    def __init__(self,parent=None,name="",size="",typ="",on_library=None):
        super().__init__(parent)
        self.name=name
        self.on_library=on_library
        self.setAttribute(Qt.WA_StyledBackground,True)
        self.setFixedHeight(px(40))
        stl(self,"background:transparent;border:none;")
        lay=QHBoxLayout(self); lay.setContentsMargins(px(14),0,px(14),0)
        lay.setSpacing(px(8))
        def add_cell(stretch):
            c=HoverCell(self); c.setFixedHeight(px(40))
            lay.addWidget(c,stretch); return c
        def add_pipe():
            p=CardPipe(); p.setFixedWidth(px(12)); lay.addWidget(p)
        # 1 — Название
        c1=add_cell(20)
        l1=QVBoxLayout(c1); l1.setContentsMargins(px(10),0,px(10),0)
        nm=lbl(name); stl(nm,"color:#ffffff;background:transparent;border:none;"
                                "font-size:15px;font-weight:700;")
        l1.addWidget(nm,alignment=Qt.AlignLeft|Qt.AlignVCenter)
        add_pipe()
        # 2 — Кнопка
        c3=add_cell(4)
        l3=QVBoxLayout(c3); l3.setContentsMargins(px(6),0,px(6),0)
        lib=BoxButton("Добавить в библиотеку",self._on_library)
        lib.setFixedSize(px(170),px(26))
        l3.addWidget(lib,alignment=Qt.AlignCenter)
        add_pipe()
        # 3 — Размер
        c4=add_cell(1)
        l4=QVBoxLayout(c4); l4.setContentsMargins(px(10),0,px(10),0)
        szl=lbl(size); stl(szl,"color:#7a7a7a;background:transparent;border:none;"
                               "font-size:13px;font-weight:600;")
        l4.addWidget(szl,alignment=Qt.AlignCenter)
        add_pipe()
        # 4 — Тип (exe)
        c5=add_cell(1)
        l5=QVBoxLayout(c5); l5.setContentsMargins(px(10),0,px(10),0)
        tpl=lbl(typ); stl(tpl,"color:#7a7a7a;background:transparent;border:none;"
                              "font-size:13px;font-weight:600;")
        l5.addWidget(tpl,alignment=Qt.AlignCenter)
        add_pipe()
        # 5 — Точки
        c6=add_cell(1)
        l6=QVBoxLayout(c6); l6.setContentsMargins(0,0,px(6),0)
        l6.addWidget(DotsBox(),alignment=Qt.AlignCenter)
    def _on_library(self):
        if self.on_library: self.on_library()

class Switch(QFrame):
    def __init__(self,on_toggle=None,initial=False):
        super().__init__(); self._on=initial; self._v=1.0 if initial else 0.0
        self.on_toggle=on_toggle; self.setFixedSize(px(44),px(24))
        self.knob=QLabel(self); self.knob.setFixedSize(px(18),px(18)); self.knob.raise_()
        self.anim=QVariantAnimation(self); self.anim.setDuration(160)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._frame); self._frame(self._v)
    def set_state(self,on):
        self._on=on; cur=self.anim.currentValue()
        start=float(cur) if cur is not None else self._v
        target=1.0 if on else 0.0
        self.anim.stop(); self.anim.setStartValue(start); self.anim.setEndValue(target)
        self.anim.start()
        if self.on_toggle: self.on_toggle(on)
    def _frame(self,v):
        self._v=v; track=_mix("#3a3a3a","#55555a",v); knob=_mix("#9a9a9a","#d0d0d0",v)
        stl(self,f"background-color:{track};border:1px solid {BRD};"
                 f"border-radius:{px(12)}px;")
        self.knob.setGeometry(round(px(4)+px(18)*v),px(3),px(18),px(18))
        stl(self.knob,f"background-color:{knob};border:none;border-radius:{px(9)}px;")
    def mousePressEvent(self,e): self.set_state(not self._on); super().mousePressEvent(e)

class ResetButton(QLabel):
    def __init__(self,text,on_click,w=168):
        super().__init__(text); self.on_click=on_click; self._h=False; self._p=False
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(px(w),px(30)); self._apply()
    def _apply(self,bg="transparent",fg="#ff6b6b",bd="#5a3434"):
        stl(self,f"color:{fg};background:{bg};border:1px solid {bd};"
                 f"border-radius:{px(6)}px;font-size:{px(15)}px;font-weight:600;")
    def _drop(self): self._p=False; self._apply("#332222") if self._h else self._apply()
    def enterEvent(self,e):
        self._h=True
        if not self._p: self._apply("#332222")
        super().enterEvent(e)
    def leaveEvent(self,e):
        self._h=False
        if not self._p: self._apply()
        super().leaveEvent(e)
    def mousePressEvent(self,e):
        self.on_click(); self._p=True; self._apply("#411f1f","#ff8080","#7a4444")
        QTimer.singleShot(150,self._drop); super().mousePressEvent(e)

class AddButton(QLabel):
    def __init__(self,p,text,on_click,enabled=True,bg=None,hover=None,dim=None):
        super().__init__(text,p); self.on_click=on_click
        self.bg=bg or BLUE; self.hov=hover or "#0b78d6"; self.dim=dim or "#21374e"
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(px(140),px(30)); self._enabled=enabled; self._apply(self.bg)
    def _apply(self,bg):
        stl(self,f"color:#ffffff;background:{bg};border:none;"
                 f"border-radius:{px(6)}px;font-size:{px(15)}px;font-weight:700;")
    def set_enabled(self,on): self._enabled=on; self._apply(self.bg if on else self.dim)
    def enterEvent(self,e):
        if self._enabled: self._apply(self.hov)
        super().enterEvent(e)
    def leaveEvent(self,e):
        self._apply(self.bg if self._enabled else self.dim); super().leaveEvent(e)
    def mousePressEvent(self,e): self.on_click(); super().mousePressEvent(e)

class ChoiceButton(QLabel):
    def __init__(self,text,on_click,w=92,bold=False):
        super().__init__(text); self.on_click=on_click
        self._a=False; self._h=False; self._p=False; self._bold=bold
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(px(w),px(30)); self._apply()
    def _apply(self):
        if self._p: bg,fg,bd="#3d3d45","#ffffff","#60606a"
        elif self._a: bg,fg,bd="#45484f","#ffffff","#62676f"
        elif self._h: bg,fg,bd="#2a2a30","#e6e6e6","#4a4a4a"
        else: bg,fg,bd="#1f1f23","#9a9a9a","#3a3a3a"
        wt="700" if self._bold else "600"
        stl(self,f"color:{fg};background:{bg};border:1px solid {bd};"
                 f"border-radius:{px(6)}px;font-size:{px(15)}px;font-weight:{wt};")
    def set_active(self,active): self._a=active; self._apply()
    def _drop(self): self._p=False; self._apply()
    def enterEvent(self,e): self._h=True; self._apply(); super().enterEvent(e)
    def leaveEvent(self,e): self._h=False; self._p=False; self._apply(); super().leaveEvent(e)
    def mousePressEvent(self,e):
        self.on_click(self); self._p=True; self._apply()
        QTimer.singleShot(150,self._drop); super().mousePressEvent(e)

class FileBox(QFrame):
    def __init__(self,p,on_click): super().__init__(p); self._on_click=on_click
    def mousePressEvent(self,e): self._on_click(); super().mousePressEvent(e)

class XLabel(QLabel):
    def __init__(self,p,on):
        super().__init__("✕",p); self._on=on; self.setAlignment(Qt.AlignCenter)
        stl(self,f"color:#9a9a9a;background:transparent;border:none;"
                 f"font-size:{px(16)}px;font-weight:700;")
        self.setCursor(Qt.PointingHandCursor)
    def mousePressEvent(self,e): self._on(); e.accept()

class OverlayFrame(QFrame):
    def __init__(self,p,on_close):
        super().__init__(p); self._on_close=on_close; self.modal=None
    def mousePressEvent(self,e):
        for name in ("m_input","m_type_custom","search_input"):
            inp=getattr(self.window(),name,None)
            if inp is not None and inp.hasFocus():
                r=inp.geometry()
                r.moveTopLeft(inp.mapToGlobal(inp.rect().topLeft()))
                if not r.contains(e.globalPosition().toPoint()): inp.clearFocus()
        if self.modal is not None and self.modal.geometry().contains(
            e.position().toPoint()): e.accept(); return
        self._on_close()
        super().mousePressEvent(e)

class AnimatedScrollArea(QScrollArea):
    def __init__(self,parent=None):
        super().__init__(parent)
        self._anim=QVariantAnimation(self); self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_step)
    def _on_step(self,v):
        try: self.verticalScrollBar().setValue(int(v))
        except RuntimeError: pass
    def wheelEvent(self,event):
        sb=self.verticalScrollBar()
        if sb.maximum()<=0: super().wheelEvent(event); return
        d=event.angleDelta().y()
        if d==0: return
        start=sb.value(); target=max(0,min(sb.maximum(),start-d))
        self._anim.stop(); self._anim.setStartValue(start)
        self._anim.setEndValue(target); self._anim.start(); event.accept()

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dev_on=False; self.current_tab="Каталог"; self._modal_v=0.0
        self._catalog_data=[]; self._auto_timer=None
        self._auto_on=False
        self._blur=None; self._ov_opacity=None
        self._busy=False
        self._open_anim=QVariantAnimation(self); self._open_anim.setDuration(180)
        self._open_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._open_anim.valueChanged.connect(self._modal_frame)
        self._close_anim=QVariantAnimation(self); self._close_anim.setDuration(180)
        self._close_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._close_anim.valueChanged.connect(self._modal_frame)
        self._close_anim.finished.connect(self._finish_close)
        self._build()
        self._nav_clicked(self.nav_items[0])
        QTimer.singleShot(0,self.search_input.clearFocus)
        QTimer.singleShot(300,self._refresh_catalog)

    def _build(self):
        self.setWindowTitle("Claudy")
        self.setFixedSize(px(1280),px(720))
        self.setStyleSheet(f"background-color:{BG};")
        self.central=QFrame(self); self.central.setGeometry(0,0,px(1280),px(720))
        self.central.setStyleSheet(f"background-color:{BG};")
        self.nav_items=[]

        sbx=box(self.central,15,48,205,140)
        lay=QVBoxLayout(sbx); lay.setContentsMargins(px(7),px(10),px(7),px(10))
        for i,(t,emoji) in enumerate([("Каталог","📁"),("Библиотека","📚"),
                                      ("Загрузки","⬇️"),("Настройки","⚙️")]):
            item=NavItem(t,emoji,self._nav_clicked); item.setFixedWidth(px(190))
            item.set_active(i==0); self.nav_items.append(item)
            lay.addWidget(item,alignment=Qt.AlignHCenter)
        lay.addStretch(1)

        self.main_panel=box(self.central,235,48,1035,660)
        self.page_title=lbl(self.nav_items[0].tt,self.main_panel)
        geo(self.page_title,14,13,400,36)
        stl(self.page_title,f"color:{TEXT};font-size:{px(24)}px;font-weight:800;"
                            "background:transparent;border:none;")
        hline(self.main_panel,14,56,1004)

        self.search_input=qfield(self.main_panel,672,14,"Поиск",40,width=200)
        stl(self.search_input,"QLineEdit{color:#ffffff;background:#292929;border:1px solid "
             "#3a3a3a;border-radius:6px;font-size:13px;font-weight:700;padding-left:8px;"
             "padding-right:20px;}QLineEdit:focus{border:2px solid #0a6ec8;}"
             "QLineEdit::placeholder{color:#7a7a7a;font-weight:700;}")
        self.search_input.textEdited.connect(self._update_catalog_view)
        self.search_input.setFocusPolicy(Qt.ClickFocus)

        self.refresh_btn=AddButton(self.main_panel,"Обновить",self._refresh_catalog,
                                   bg="#3a3a3a",hover="#4a4a4a",dim="#2c2c2c")
        geo(self.refresh_btn,880,14,140,30)
        self.new_project_btn=AddButton(self.main_panel,"Новый проект",self._new_project)
        geo(self.new_project_btn,880,14,140,30); self.new_project_btn.hide()
        self.new_download_btn=AddButton(self.main_panel,"Новая загрузка",self._new_download)
        geo(self.new_download_btn,880,14,140,30); self.new_download_btn.hide()

        def empty_rect(title,desc):
            f=box(self.main_panel,17,70,1000,400)
            v=QVBoxLayout(f); v.setContentsMargins(0,0,0,0)
            v.setSpacing(px(10)); v.setAlignment(Qt.AlignCenter)
            t=lbl(title); stl(t,f"color:{TEXT};background:transparent;border:none;"
                                f"font-size:{px(25)}px;font-weight:700;")
            v.addWidget(t,alignment=Qt.AlignHCenter)
            d=lbl(desc); d.setWordWrap(True); d.setFixedWidth(px(560)); d.setAlignment(Qt.AlignCenter)
            stl(d,"color:#b4b4af;background:transparent;border:none;"
                  f"font-size:{px(13)}px;")
            v.addWidget(d,alignment=Qt.AlignHCenter); f.hide(); return f
        self.catalog_area=AnimatedScrollArea(self.main_panel)
        self.catalog_area.setWidgetResizable(True)
        self.catalog_area.setFrameShape(QFrame.NoFrame)
        self.catalog_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.catalog_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        stl(self.catalog_area,"QScrollArea{background:transparent;border:none;}"
              "QScrollBar:vertical{background:transparent;width:6px;margin:0;}"
              "QScrollBar::handle:vertical{background:#3c3c3c;border-radius:3px;"
              "min-height:24px;}QScrollBar::add-line:vertical,"
              "QScrollBar::sub-line:vertical{height:0px;}QScrollBar::add-page:vertical,"
              "QScrollBar::sub-page:vertical{background:transparent;}")
        self.catalog_view=QFrame(self.catalog_area)
        stl(self.catalog_view,"background:transparent;border:none;")
        self.catalog_area.setWidget(self.catalog_view)
        self.catalog_lay=QVBoxLayout(self.catalog_view)
        self.catalog_lay.setContentsMargins(0,px(10),0,0)
        self.catalog_lay.setSpacing(px(8)); self._project_cards=[]
        geo(self.catalog_area,14,70,1010,575)
        self.catalog_empty=empty_rect("Каталог пуст",
            "Все добавленные проекты, а также информация о них, появятся в этом разделе.")
        self.catalog_empty.hide()
        self.library_empty=empty_rect("Библиотека пуста",
            "Добавьте файл через каталог, чтобы он появился здесь. Все ваши файлы, а также "
            "информация о них и их текущем статусе, собраны в этом разделе.")
        self.downloads_empty=empty_rect("Загрузок пока нет",
            "Добавьте файл через библиотеку, чтобы он появился здесь. В этом разделе собрана "
            "информация о последних загрузках и их текущем статусе.")

        self.settings_box=AnimatedScrollArea(self.main_panel)
        self.settings_box.setWidgetResizable(True)
        self.settings_box.setFrameShape(QFrame.NoFrame)
        self.settings_box.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.settings_box.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        stl(self.settings_box,"QScrollArea{background:transparent;border:none;}"
             "QScrollBar:vertical{background:transparent;width:6px;margin:0;}"
             "QScrollBar::handle:vertical{background:#3c3c3c;border-radius:3px;"
             "min-height:24px;}QScrollBar::add-line:vertical,"
             "QScrollBar::sub-line:vertical{height:0px;}QScrollBar::add-page:vertical,"
             "QScrollBar::sub-page:vertical{background:transparent;}")
        self.settings_view=QFrame(self.settings_box)
        stl(self.settings_view,"background:transparent;border:none;")
        self.settings_box.setWidget(self.settings_view)
        sb_lay=QVBoxLayout(self.settings_view); sb_lay.setContentsMargins(0,px(14),0,0)
        sb_lay.setSpacing(px(10)); self.cards=[]

        def make_card(title,desc,row):
            f=box(self.settings_view,0,0,996,118); f.setFixedSize(px(996),px(118))
            f_lay=QHBoxLayout(f); f_lay.setContentsMargins(px(22),px(12),px(22),px(14))
            f_lay.setSpacing(px(8))
            tb=QVBoxLayout(); tb.setContentsMargins(0,0,0,0); tb.setSpacing(px(2))
            tl=lbl(title); stl(tl,f"color:{TEXT};background:transparent;border:none;"
                                  f"font-size:{px(17)}px;font-weight:600;")
            tb.addWidget(tl,alignment=Qt.AlignLeft)
            d=lbl(desc); d.setWordWrap(True)
            _f=QFont(); _f.setPixelSize(px(13)); d.setFont(_f)
            d.setFixedWidth(px(680)); d.setFixedHeight(d.heightForWidth(px(680)))
            stl(d,f"color:#9a9a9a;background:transparent;border:none;")
            tb.addWidget(d,alignment=Qt.AlignLeft); tb.addStretch(1)
            f_lay.addLayout(tb,1)
            rb=QHBoxLayout(); rb.setSpacing(px(6)); rb.addWidget(row,alignment=Qt.AlignVCenter)
            f_lay.addLayout(rb); self.cards.append(f); return f

        self.check_btn=ChoiceButton("Проверить",self._check_updates,w=168)
        make_card("Проверить обновления",
                  "Ручная проверка наличия новой версии приложения. Если обновление "
                  "доступно, вы сможете сразу его установить.",
                  self.check_btn)
        self.auto_switch=Switch(self._auto_toggled,initial=False)
        make_card("Автообновление каталога",
                  "Каталог будет обновляться автоматически. Все свежие данные, новые "
                  "записи и изменения подтягиваются сами, так что вручную ничего "
                  "обновлять не придётся.",
                  self.auto_switch)
        make_card("Очистить кэш и временные файлы",
                  "Удаление накопленных временных данных и кэша приложения. Это "
                  "помогает освободить место и устранить возможные сбои в работе.",
                  ResetButton("Очистить",self._clear_cache))
        make_card("Сбросить настройки",
                  "Возврат всех параметров к исходным значениям. При сбросе текущая "
                  "конфигурация будет удалена, а приложение вернётся к состоянию "
                  "по умолчанию.",
                  ResetButton("Сбросить",self._reset_settings))
        self.dev_switch=Switch(self._dev_toggled)
        make_card("Режим разработчика",
                  "Активация расширенного интерфейса для мониторинга системы. При "
                  "включении будет показана детализация версий, скрытые параметры и "
                  "инструменты управления проектами. Полный контроль над конфигурацией "
                  "и отладкой.",
                  self.dev_switch)
        for c in self.cards: sb_lay.addWidget(c,alignment=Qt.AlignLeft|Qt.AlignTop)
        geo(self.settings_box,16,65,1003,579); self.settings_box.hide()

        self.brand=lbl("Claudy",self.central); geo(self.brand,18,4,200,30)
        stl(self.brand,f"color:{TEXT};font-size:{px(24)}px;font-weight:800;"
                       "background:transparent;border:none;")
        self.version_label=lbl("v2.12",self.central); geo(self.version_label,18,690,200,24)
        stl(self.version_label,"color:#9a9a9a;font-size:15px;font-weight:600;"
                               "background:transparent;border:none;")
        self.version_label.hide()

        self.overlay=OverlayFrame(self,self._close_modal)
        self.overlay.setGeometry(0,0,px(1280),px(720))
        stl(self.overlay,"background-color: rgba(0, 0, 0, 120);")
        self.modal=box(self.overlay,320,150,640,440); self.overlay.modal=self.modal
        m_title=lbl("Новый проект",self.modal); geo(m_title,24,20,400,30)
        stl(m_title,f"color:{TEXT};background:transparent;border:none;"
                    f"font-size:{px(19)}px;font-weight:700;")
        hline(self.modal,24,55,592)
        self.selected_file=None; self._type=None
        m_rect=FileBox(self.modal,self._pick_file); self.m_rect=m_rect
        m_rect.setCursor(Qt.PointingHandCursor)
        geo(m_rect,24,72,592,136)
        stl(m_rect,"background-color:#191919;border:1px solid #2a2a2a;border-radius:8px;")
        m_lay=QVBoxLayout(m_rect); m_lay.setContentsMargins(px(16),px(8),px(16),px(8))
        m_lay.setSpacing(px(2)); m_lay.setAlignment(Qt.AlignCenter)
        self.rect_title=lbl("Загрузка файлов",m_rect); self.rect_title.setAlignment(Qt.AlignCenter)
        stl(self.rect_title,f"color:{TEXT};background:transparent;border:none;"
                            f"font-size:{px(25)}px;font-weight:700;")
        self.rect_desc=lbl(FILE_HINT,m_rect); self.rect_desc.setAlignment(Qt.AlignCenter)
        self.rect_desc.setWordWrap(True)
        stl(self.rect_desc,"color:#b4b4af;background:transparent;border:none;"
                           f"font-size:{px(13)}px;")
        m_lay.addWidget(self.rect_title); m_lay.addWidget(self.rect_desc)
        self.rect_close=XLabel(m_rect,self._clear_file)
        geo(self.rect_close,546,0,46,40); self.rect_close.hide()
        flbl(self.modal,24,214,"Название",13)
        self.m_input=qfield(self.modal,24,240,"Введите название",36,width=450)
        self.m_input.textEdited.connect(self._on_change)
        flbl(self.modal,24,282,"Тип запуска",15)
        self._chips=[]
        for i,txt in enumerate([".exe",".msi",".bat","Папка"]+["Другой"]):
            w=120 if txt=="Другой" else 92
            chip=ChoiceButton(txt,self._chip_toggled,w=w,bold=txt!="Другой")
            chip.setParent(self.modal); chip.setFixedSize(px(w),px(30))
            geo(chip,496 if txt=="Другой" else 24+i*102,310,w,30)
            self._chips.append(chip)
        self.m_type_custom=qfield(self.modal,496,282,"Пример: .txt",17,width=120)
        self.m_type_custom.textEdited.connect(self._on_change); self.m_type_custom.hide()
        self.add_btn=AddButton(self.modal,"Добавить",self._try_add)
        self.add_btn.setFixedSize(px(450),px(30)); geo(self.add_btn,24,366,450,30)
        m_cancel=ChoiceButton("Отмена",self._close_modal,w=120)
        m_cancel.setParent(self.modal); m_cancel.setFixedSize(px(120),px(30))
        geo(m_cancel,496,366,120,30); self.m_cancel=m_cancel
        self.m_error=lbl("",self.modal); geo(self.m_error,24,402,592,24)
        stl(self.m_error,"color:#ff5c5c;background:transparent;border:none;"
                         "font-size:13px;font-weight:600;")
        self.overlay.hide(); self.installEventFilter(self)

    # ---- поведение ----

    def _check_updates(self,btn=None): pass
    def _clear_cache(self):
        if os.path.isdir(CACHE_DIR): shutil.rmtree(CACHE_DIR,ignore_errors=True)
        os.makedirs(CACHE_DIR,exist_ok=True)
    def _reset_settings(self):
        self.auto_switch.set_state(False); self.dev_switch.set_state(False)
    def _dev_toggled(self,on):
        self.dev_on=on; self.version_label.setVisible(on); self._update_dynamic()
    def _update_version(self): return

    def _update_dynamic(self):
        self._layout_header()

    def _layout_header(self):
        if self.current_tab!="Каталог":
            self.search_input.hide(); self.refresh_btn.hide()
            self.new_project_btn.hide(); return
        self.search_input.show()
        auto=self._auto_on
        self.refresh_btn.setVisible(not auto)
        if self.dev_on:
            if auto:
                geo(self.search_input,544,14,332,30)
                self.new_project_btn.show(); geo(self.new_project_btn,880,14,140,30)
            else:
                geo(self.search_input,544,14,182,30)
                geo(self.refresh_btn,732,14,140,30)
                self.new_project_btn.show(); geo(self.new_project_btn,880,14,140,30)
        else:
            if auto:
                geo(self.search_input,640,14,232,30)
            else:
                geo(self.search_input,640,14,232,30)
                geo(self.refresh_btn,880,14,140,30)
            self.new_project_btn.hide()

    @staticmethod
    def _plural(n,one,few,many):
        n10,n100=n%10,n%100
        if n10==1 and n100!=11: return one
        if 2<=n10<=4 and not (12<=n100<=14): return few
        return many

    def _chip_toggled(self,chip):
        if self._busy: return
        self._type=chip.text()
        for c in self._chips: c.set_active(c is chip)
        self.m_type_custom.setVisible(chip.text()=="Другой"); self._on_change()

    def _pick_file(self):
        if self._busy: return
        path,_=QFileDialog.getOpenFileName(self,"Выберите файл","","Все файлы (*)")
        if not path: return
        self.selected_file=path; self.rect_title.setText(os.path.basename(path))
        self.rect_close.show()
        if path.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(path) as zf: count=len(zf.namelist())
                self.rect_desc.setText(f"{count} {self._plural(count,'файл','файла','файлов')}")
            except Exception: self.rect_desc.setText("Не удалось прочитать ZIP архив")
        else: self.rect_desc.hide()
        self._on_change()

    def _clear_file(self):
        if self._busy: return
        self.selected_file=None; self.rect_close.hide()
        self.rect_title.setText("Загрузка файлов")
        self.rect_desc.setText(FILE_HINT); self.rect_desc.show(); self._on_change()

    def _custom_ok(self):
        s=self.m_type_custom.text().strip()
        return (len(s)>=2 and s[0]=="."
                and all(ch.isalnum() for ch in s[1:]))

    def _type_ok(self):
        t=self._type
        if not t or not self.selected_file: return True
        if t=="Папка": return True
        ext=(self.m_type_custom.text().strip().lower() if t=="Другой"
             else t.lower())
        if not ext: return False
        f=self.selected_file.lower()
        if f.endswith(".zip"):
            try:
                with zipfile.ZipFile(self.selected_file) as zf:
                    names=[n.lower() for n in zf.namelist()]
                return not names or any(n.endswith(ext) for n in names)
            except Exception: return False
        return f.endswith(ext)

    def _check_error(self):
        if not self.m_input.text().strip(): return "Введите название проекту."
        if not self.selected_file: return "Добавьте файл в проект."
        if not self._type: return "Выберите тип запуска проекта."
        if self._type=="Другой":
            if not self._custom_ok(): return "Неверный тип запуска."
            if not self._type_ok(): return "Тип запуска не соответствует файлам."
        elif not self._type_ok(): return "Тип запуска не соответствует файлам."
        return ""

    def _on_change(self):
        if self._busy: return
        err=self._check_error()
        self.m_error.setText(err)
        self.add_btn.set_enabled(not bool(err))

    def _type_display(self):
        t=self._type
        if not t: return ""
        if t=="Другой": return self.m_type_custom.text().strip().lstrip(".")
        return t.lstrip(".")

    def _put_file(self,owner,path,b64,message):
        data={"message":message,"content":b64,"branch":"main"}
        url=GIT+f"repos/{owner}/ClaudyCloud/contents/{quote(path,safe='/')}"
        s,d=_gh("PUT",url,data,timeout=60)
        if s in (200,201): return True
        if s==422:
            gs,gd=_gh("GET",url,timeout=60)
            if gs==200 and gd.get("sha"):
                data["sha"]=gd["sha"]
                s,d=_gh("PUT",url,data,timeout=60)
                return s in (200,201)
        return False

    def _try_add(self):
        if self._busy: return
        err=self._check_error()
        if err: self.m_error.setText(err); return
        self._busy=True
        self.add_btn.set_enabled(False)
        for w in (self.m_input,self.m_type_custom): w.setEnabled(False)
        self.m_error.setText("Загрузка на GitHub...")
        stl(self.m_error,"color:#b4b4af;background:transparent;border:none;"
                         "font-size:13px;font-weight:600;")
        name=self.m_input.text().strip()
        fname=os.path.basename(self.selected_file)
        def work():
            try:
                owner=self._gh_owner()
                if not owner:
                    msg="Ошибка: не удалось авторизоваться."
                else:
                    with open(self.selected_file,"rb") as f: raw=f.read()
                    ok=self._put_file(owner,f"{name}/{fname}",
                                      base64.b64encode(raw).decode("utf-8"),
                                      f"Добавить {name}/{fname}")
                    if ok:
                        meta=json.dumps({"type":self._type_display()},
                                        ensure_ascii=False).encode("utf-8")
                        self._put_file(owner,f"{name}/.claudy.json",
                                       base64.b64encode(meta).decode("utf-8"),
                                       f"Метаданные {name}")
                        msg="Проект добавлен."
                    else: msg="Ошибка: не удалось загрузить файл."
            except Exception as e: msg="Ошибка: "+str(e)
            QTimer.singleShot(0,self,lambda: self._finish_add(msg))
        threading.Thread(target=work,daemon=True).start()

    def _finish_add(self,msg):
        self._busy=False
        for w in (self.m_input,self.m_type_custom): w.setEnabled(True)
        if msg.startswith("Ошибка"):
            self.m_error.setText(msg)
            stl(self.m_error,"color:#ff5c5c;background:transparent;border:none;"
                             "font-size:13px;font-weight:600;")
            self.add_btn.set_enabled(True)
        else:
            self._reset_modal()
            self._close_modal()
            QTimer.singleShot(600,self._refresh_catalog)
    def _auto_toggled(self,on):
        self._auto_on=on; self._layout_header()
        if on:
            if self._auto_timer is None:
                self._auto_timer=QTimer(self); self._auto_timer.setInterval(120000)
                self._auto_timer.timeout.connect(self._refresh_catalog)
            self._auto_timer.start()
            self._refresh_catalog()
        elif self._auto_timer is not None:
            self._auto_timer.stop()

    # ---- облако ----

    def _gh_owner(self):
        s,d=_gh("GET",GIT+"user")
        return d.get("login") if s==200 else None

    def _refresh_catalog(self):
        if self._busy: return
        self._busy=True
        self.refresh_btn.setText("Загрузка...")
        def work():
            try:
                owner=self._gh_owner()
                if not owner: projs=None
                else:
                    s,d=_gh("GET",GIT+f"repos/{owner}/ClaudyCloud/git/"
                                       f"trees/main?recursive=1")
                    if s==200: projs=self._collect_projects(owner,d.get("tree",[]))
                    elif s==409: projs=[]
                    else: projs=None
            except Exception: projs=None
            QTimer.singleShot(0,self,lambda: self._apply_catalog(projs))
        threading.Thread(target=work,daemon=True).start()

    def _collect_projects(self,owner,tree):
        groups={}
        for e in tree:
            if e.get("type")!="blob": continue
            p=e.get("path","")
            if p.count("/")<1: continue
            folder=p.split("/",1)[0]
            groups.setdefault(folder,[]).append(e)
        projects=[]
        for folder,entries in groups.items():
            real=[e for e in entries
                  if not e.get("path","").endswith("/.claudy.json")]
            if not real: continue
            largest=max(real,key=lambda e: e.get("size",0))
            size=sum(int(e.get("size",0)) for e in real)
            typ=""
            meta=[e for e in entries if e.get("path","").endswith("/.claudy.json")]
            if meta:
                sha=meta[0].get("sha")
                s2,m=_gh("GET",GIT+f"repos/{owner}/ClaudyCloud/git/blobs/{sha}")
                if s2==200 and m.get("encoding")=="base64":
                    try:
                        raw=base64.b64decode(m.get("content","")).decode("utf-8")
                        md=json.loads(raw); typ=md.get("type","")
                    except Exception: pass
            if not typ:
                ext=os.path.splitext(largest.get("path",""))[1].lstrip(".")
                typ=ext or "Файл"
            projects.append({"name":folder,
                             "type":typ,"size":_fmt_size(size)})
        projects.sort(key=lambda p:p["name"].lower())
        return projects

    def _apply_catalog(self,projs):
        self._busy=False
        self.refresh_btn.setText("Обновить")
        if projs is None: return
        self._catalog_data=projs
        self._render_cards()
        self._update_catalog_view()

    # ---- карточки/каталог (пустой) ----

    def _render_cards(self):
        while self.catalog_lay.count():
            item=self.catalog_lay.takeAt(0)
            w=item.widget()
            if w is not None:
                try: w.deleteLater()
                except RuntimeError: pass
        self._project_cards=[]
        for p in self._catalog_data:
            card=GameCard(self.catalog_view,name=p["name"],
                          size=p["size"],typ=p["type"])
            card.setFixedSize(px(1004),px(40))
            card.name=p["name"]
            self.catalog_lay.addWidget(card,alignment=Qt.AlignTop)
            self._project_cards.append(card)
        self.catalog_lay.addStretch(1)
        if self._catalog_data: self.catalog_area.show(); self.catalog_empty.hide()
        else: self.catalog_area.hide(); self.catalog_empty.show()
        self._update_catalog_view()

    def _update_catalog_view(self):
        q=self.search_input.text().strip().lower()
        if not self._project_cards: return
        prefix=[]; contains=[]
        for c in self._project_cards:
            nm=c.name.lower()
            if not q or nm==q or nm.startswith(q): prefix.append(c)
            elif q in nm: contains.append(c)
        for c in self._project_cards: c.setVisible(c in prefix or c in contains)
        order=prefix+contains
        for c in self._project_cards:
            if c in order:
                self.catalog_lay.removeWidget(c)
        for c in order:
            self.catalog_lay.insertWidget(self.catalog_lay.count()-1,c)

    def _new_project(self): self._open_modal()

    def _modal_frame(self,v):
        self._modal_v=v
        if self._blur is not None:
            try: self._blur.setBlurRadius(int(round(6*v)))
            except RuntimeError: pass
        if self._ov_opacity is not None:
            try: self._ov_opacity.setOpacity(v)
            except RuntimeError: pass

    def _reset_modal(self):
        self.selected_file=None; self._type=None
        self.m_input.clear(); self.m_type_custom.clear()
        self.m_type_custom.hide()
        for c in self._chips: c.set_active(False)
        self.rect_close.hide()
        self.rect_title.setText("Загрузка файлов")
        self.rect_desc.setText(FILE_HINT); self.rect_desc.show()
        self._on_change()

    def _open_modal(self):
        if self._busy or not self.overlay.isHidden(): return
        self._reset_modal()
        self.overlay.show(); self.overlay.raise_()
        if self._blur is None:
            self._blur=QGraphicsBlurEffect(self.central)
            self.central.setGraphicsEffect(self._blur)
        if self._ov_opacity is None:
            self._ov_opacity=QGraphicsOpacityEffect(self.overlay)
            self.overlay.setGraphicsEffect(self._ov_opacity)
        self._open_anim.stop()
        self._open_anim.setStartValue(0.0); self._open_anim.setEndValue(1.0)
        self._open_anim.start()

    def _close_modal(self,_btn=None):
        if self._busy or self.overlay.isHidden(): return
        self._open_anim.stop(); self._close_anim.stop()
        self._close_anim.setStartValue(self._modal_v)
        self._close_anim.setEndValue(0.0); self._close_anim.start()

    def _finish_close(self):
        self.overlay.hide(); self.central.setGraphicsEffect(None)
        self.overlay.setGraphicsEffect(None)
        for attr in ("_blur","_ov_opacity"):
            eff=getattr(self,attr,None)
            if eff is not None:
                try: eff.deleteLater()
                except RuntimeError: pass
                setattr(self,attr,None)

    def _new_download(self):
        for item in self.nav_items:
            if item.tt=="Библиотека":
                self._nav_clicked(item); return

    def _nav_clicked(self,item):
        self.current_tab=item.tt
        for other in self.nav_items: other.set_active(other is item)
        self.page_title.setText(item.tt)
        tab=item.tt
        if tab=="Каталог":
            self.catalog_area.setVisible(bool(self._project_cards))
            self.catalog_empty.setVisible(not self._project_cards)
            self._update_catalog_view()
        else:
            self.catalog_area.hide(); self.catalog_empty.hide()
        self.library_empty.setVisible(tab=="Библиотека")
        self.downloads_empty.setVisible(tab=="Загрузки")
        self.new_download_btn.setVisible(tab=="Загрузки")
        self.settings_box.setVisible(tab=="Настройки")
        self._update_dynamic()

    def eventFilter(self,obj,ev):
        if ev.type()==QEvent.MouseButtonPress:
            si=self.search_input
            if si is not None and si.hasFocus():
                r=si.geometry()
                r.moveTopLeft(si.mapToGlobal(si.rect().topLeft()))
                if not r.contains(ev.globalPosition().toPoint()): si.clearFocus()
        return super().eventFilter(obj,ev)

def main():
    app=QApplication(sys.argv); win=Window(); win.show(); sys.exit(app.exec())

if __name__=="__main__":
    main()