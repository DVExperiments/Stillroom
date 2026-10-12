"""Stillroom 3 — local-first rich text notebook, PySide6."""
import html
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSize, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPalette, QTextCharFormat, QTextCursor, QTextListFormat, QTextBlockFormat, QKeySequence, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QTextEdit, QListWidget, QListWidgetItem, QHBoxLayout, QVBoxLayout, QSplitter,
    QComboBox, QToolButton, QFileDialog, QMessageBox, QInputDialog, QMenu,
    QFontComboBox, QSpinBox, QStatusBar, QScrollArea, QSizePolicy
)

APP_DIR = Path(os.environ.get('APPDATA') or Path.home() / '.local' / 'share') / 'Stillroom'
STORE = APP_DIR / 'notes.json'
SNAPSHOT = APP_DIR / 'notes.pre-v3.json'
BACKUP = APP_DIR / 'notes.v3.backup.json'
PREFS = APP_DIR / 'settings.v3.json'

def now(): return datetime.now().isoformat(timespec='seconds')
def fresh(book='Personal'):
    return {'id':uuid.uuid4().hex,'title':'','body':'','notebook':book,'tags':[],
            'favorite':False,'pinned':False,'archived':False,'deleted':False,
            'created':now(),'updated':now()}

def plain_from_html(content):
    text = re.sub(r'(?i)<br\s*/?>|</(?:p|div|li|h[1-6])>', '\n',content)
    return html.unescape(re.sub('<[^>]*>', '', text)).strip()

def normalize(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get('notes'),list):
        raise ValueError('Invalid notes file')
    result = dict(payload)
    books = result.get('notebooks')
    result['notebooks'] = list(dict.fromkeys([str(x) for x in books if str(x).strip()])) if isinstance(books,list) else ['Personal','Work','Ideas']
    if not result['notebooks']: result['notebooks']=['Personal']
    cleaned=[]
    for original in result['notes']:
        if not isinstance(original,dict): continue
        note=fresh(); note.update(original)
        note['id']=str(note.get('id') or uuid.uuid4().hex)
        note['body']=str(note.get('body') or '')
        note['title']=str(note.get('title') or '')
        note['notebook']=str(note.get('notebook') or 'Personal')
        if not isinstance(note.get('tags'),list): note['tags']=[]
        for key in ('favorite','pinned','archived','deleted'): note[key]=bool(note.get(key,False))
        note['html']=note.get('html') if isinstance(note.get('html'),str) else None
        if note['notebook'] not in result['notebooks']:result['notebooks'].append(note['notebook'])
        cleaned.append(note)
    result['notes']=cleaned
    return result

def atomic_json(path, content):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf-8') as f:
        json.dump(content,f,ensure_ascii=False,indent=2)
        f.flush();os.fsync(f.fileno())
    os.replace(temp,path)

def load_store():
    if STORE.exists():
        with STORE.open(encoding='utf-8') as f: raw=json.load(f)
        return normalize(raw)
    return {'notes':[],'notebooks':['Personal','Work','Ideas']}

LIGHT={'bg':'#F5F3EE','rail':'#EBEEE8','panel':'#FFFFFF','paper':'#FFFDF9','ink':'#27352F',
       'muted':'#738077','accent':'#436951','accentText':'#FFFFFF','line':'#DDE3DB',
       'hover':'#E8EEE6','selected':'#DCEADD','input':'#F4F6F1'}
DARK={'bg':'#151D1A','rail':'#1B2721','panel':'#202C25','paper':'#243029','ink':'#ECF0E8',
      'muted':'#A4B4A9','accent':'#A8CCB1','accentText':'#17241B','line':'#39483D',
      'hover':'#2A3E31','selected':'#355640','input':'#27382E'}

def stylesheet(c):
    return f'''QMainWindow,QWidget#root {{background:{c['bg']};color:{c['ink']};}}
    QWidget {{font-family:"Segoe UI", "Arial";font-size:13px;color:{c['ink']};}}
    QFrame#rail {{background:{c['rail']};border:0;}}
    QFrame#collection {{background:{c['panel']};border:0;}}
    QFrame#sheet {{background:{c['paper']};border:1px solid {c['line']};border-radius:18px;}}
    QLabel#brand {{font-size:27px;font-weight:750;color:{c['ink']};}}
    QLabel#heading {{font-size:19px;font-weight:700;}}
    QLabel#eyebrow {{font-size:11px;font-weight:700;color:{c['muted']};}}
    QLabel#secondary {{color:{c['muted']};font-size:12px;}}
    QLineEdit,QComboBox,QSpinBox {{background:{c['input']};border:1px solid {c['line']};border-radius:9px;padding:9px 11px;selection-background-color:{c['selected']};}}
    QLineEdit:focus,QComboBox:focus {{border:1px solid {c['accent']};}}
    QLineEdit#title {{background:transparent;border:0;border-radius:0;padding:0;font-size:30px;font-weight:700;}}
    QLineEdit#tags {{background:transparent;border:0;border-bottom:1px solid {c['line']};border-radius:0;padding:5px 2px;}}
    QPushButton,QToolButton {{background:transparent;border:1px solid transparent;border-radius:10px;padding:9px 12px;}}
    QPushButton:hover,QToolButton:hover {{background:{c['hover']};}}
    QPushButton:pressed,QToolButton:pressed {{background:{c['selected']};}}
    QPushButton#primary {{background:{c['accent']};color:{c['accentText']};border-radius:11px;font-weight:700;padding:12px;}}
    QPushButton#primary:hover {{opacity:0.9;}}
    QPushButton#nav {{text-align:left;padding:12px 15px;border-radius:10px;}}
    QPushButton#nav[active="true"] {{background:{c['selected']};font-weight:700;}}
    QPushButton#tool,QToolButton#tool {{padding:5px 8px;border:1px solid {c['line']};border-radius:8px;min-width:22px;}}
    QPushButton#tool[active="true"] {{background:{c['selected']};}}
    QListWidget {{background:transparent;border:0;outline:0;padding:6px;}}
    QListWidget::item {{border-radius:11px;margin:3px 1px;padding:14px 12px;}}
    QListWidget::item:selected {{background:{c['selected']};color:{c['ink']};}}
    QListWidget::item:hover:!selected {{background:{c['hover']};}}
    QTextEdit {{background:transparent;border:0;selection-background-color:{c['selected']};color:{c['ink']};padding:4px 0;}}
    QSplitter::handle {{background:{c['line']};width:1px;}}
    QStatusBar {{background:{c['bg']};color:{c['muted']};border:0;}}
    QMenu {{background:{c['panel']};border:1px solid {c['line']};padding:5px;}}
    QMenu::item {{padding:8px 22px;border-radius:5px;}}
    QMenu::item:selected {{background:{c['selected']};}}
    QScrollBar:vertical {{border:0;background:transparent;width:9px;}}
    QScrollArea#sidebarScroll, QScrollArea#sidebarScroll > QWidget > QWidget {{background:transparent;border:0;}}
    QScrollBar::handle:vertical {{background:{c['line']};border-radius:4px;min-height:25px;}}
    '''

class Editor(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setAcceptRichText(True)
        self.setPlaceholderText('Start writing. Every thought has somewhere to begin…')
        self.setTabStopDistance(36)
        self.setFont(QFont('Georgia',13))
        self.setMinimumHeight(190)

class Stillroom(QMainWindow):
    def __init__(self):
        super().__init__()
        try:self.data=load_store()
        except Exception as e:
            QMessageBox.critical(None,'Stillroom — data could not be loaded',
                 f'Your notes file could not be read. Stillroom will not overwrite it.\n\n{e}\n\nFile: {STORE}')
            raise
        # Snapshot original v1/v2 data before any v3 modifications.
        if STORE.exists() and not SNAPSHOT.exists():
            APP_DIR.mkdir(parents=True,exist_ok=True)
            shutil.copy2(STORE,SNAPSHOT)
        try:
            self.prefs=json.loads(PREFS.read_text(encoding='utf-8')) if PREFS.exists() else {}
        except (ValueError,OSError):self.prefs={}
        self.theme=self.prefs.get('theme','light')
        if self.theme not in ('dark','light'):self.theme='light'
        self.active=None;self.view='All notes';self.loading=False;self.focus_mode=False
        self.save_timer=QTimer(self);self.save_timer.setSingleShot(True);self.save_timer.timeout.connect(self.save)
        self.setWindowTitle('Stillroom 3  ·  A space to write')
        self.resize(1350,850);self.setMinimumSize(830,570)
        self.build_ui();self.apply_theme();self.build_notebooks();self.refresh_list()
        candidates=[n for n in self.data['notes'] if not n['deleted'] and not n['archived']]
        if candidates:self.open_note(max(candidates,key=lambda x:x.get('updated',''))['id'])
        else:self.new_note()
        self.shortcuts()

    def lbl(self,txt,name=None):
        w=QLabel(txt)
        if name:w.setObjectName(name)
        return w
    def button(self,text,cb,name=None):
        b=QPushButton(text)
        if name:b.setObjectName(name)
        b.clicked.connect(cb);b.setCursor(Qt.PointingHandCursor)
        return b
    def build_ui(self):
        root=QWidget();root.setObjectName('root');self.setCentralWidget(root)
        layout=QHBoxLayout(root);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        self.split=QSplitter(Qt.Horizontal);self.split.setChildrenCollapsible(False);layout.addWidget(self.split)
        self.rail=QFrame();self.rail.setObjectName('rail');self.rail.setMinimumWidth(185)
        rail=QVBoxLayout(self.rail);rail.setContentsMargins(21,31,21,20);rail.setSpacing(9)
        rail.addWidget(self.lbl('✦  stillroom','brand'))
        rail.addWidget(self.lbl('A little room to think.','secondary'))
        rail.addSpacing(24)
        rail.addWidget(self.button('＋   New note',self.new_note,'primary'))
        rail.addSpacing(13)
        self.search=QLineEdit();self.search.setPlaceholderText('⌕   Search your notes');self.search.textChanged.connect(self.refresh_list)
        rail.addWidget(self.search)
        # Keep navigation readable on shorter windows: scroll the middle section,
        # instead of letting Qt shrink the notebook buttons below their text height.
        nav_scroll=QScrollArea()
        nav_scroll.setObjectName('sidebarScroll')
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        nav_content=QWidget()
        rail_body=QVBoxLayout(nav_content)
        rail_body.setContentsMargins(0,14,5,8)
        rail_body.setSpacing(9)
        nav_scroll.setWidget(nav_content)
        rail.addWidget(nav_scroll,1)

        rail_body.addWidget(self.lbl('LIBRARY','eyebrow'))
        self.nav={}
        for key,symbol in [('All notes','▤'),('Favorites','♡'),('Pinned','⌁'),('Archive','▣'),('Trash','♻')]:
            b=self.button(f'{symbol}    {key}',lambda _,k=key:self.change_view(k),'nav')
            b.setMinimumHeight(43)
            rail_body.addWidget(b);self.nav[key]=b
        rail_body.addSpacing(18)
        bar=QHBoxLayout();bar.addWidget(self.lbl('NOTEBOOKS','eyebrow'));bar.addStretch()
        bar.addWidget(self.button('＋',self.add_notebook))
        rail_body.addLayout(bar)
        self.books_container=QVBoxLayout();self.books_container.setSpacing(2);rail_body.addLayout(self.books_container)
        rail_body.addStretch()
        rail.addWidget(self.button('☼ / ☾   Appearance',self.toggle_theme,'nav'))
        rail.addWidget(self.button('↥   Backup / Export all',self.export_backup,'nav'))
        self.split.addWidget(self.rail)
        self.collection=QFrame();self.collection.setObjectName('collection');self.collection.setMinimumWidth(200)
        mid=QVBoxLayout(self.collection);mid.setContentsMargins(14,29,14,18);mid.setSpacing(10)
        self.list_title=self.lbl('All notes','heading');mid.addWidget(self.list_title)
        self.list_count=self.lbl('','secondary');mid.addWidget(self.list_count)
        self.note_list=QListWidget();self.note_list.setSpacing(4);self.note_list.currentItemChanged.connect(self.on_pick)
        self.note_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.note_list.customContextMenuRequested.connect(self.list_context)
        mid.addWidget(self.note_list)
        self.split.addWidget(self.collection)
        outer=QWidget();outer_layout=QVBoxLayout(outer);outer_layout.setContentsMargins(24,20,24,20)
        self.sheet=QFrame();self.sheet.setObjectName('sheet');outer_layout.addWidget(self.sheet)
        doc=QVBoxLayout(self.sheet);doc.setContentsMargins(40,26,40,23);doc.setSpacing(12)
        row=QHBoxLayout();self.breadcrumb=self.lbl('YOUR NOTE  /  PERSONAL','eyebrow');row.addWidget(self.breadcrumb);row.addStretch()
        self.focus_btn=self.button('⛶  Focus',self.toggle_focus);row.addWidget(self.focus_btn)
        self.more=self.button('•••',self.note_menu);row.addWidget(self.more)
        doc.addLayout(row);doc.addSpacing(12)
        self.title_edit=QLineEdit();self.title_edit.setObjectName('title');self.title_edit.setPlaceholderText('Untitled note')
        self.title_edit.textEdited.connect(self.schedule_save);doc.addWidget(self.title_edit)
        self.subtitle=self.lbl('Give your thoughts some space.','secondary');doc.addWidget(self.subtitle)
        doc.addSpacing(7)
        meta=QHBoxLayout();meta.addWidget(self.lbl('NOTEBOOK','eyebrow'))
        self.book_combo=QComboBox();self.book_combo.currentTextChanged.connect(self.schedule_save);meta.addWidget(self.book_combo)
        meta.addSpacing(14);meta.addWidget(self.lbl('TAGS','eyebrow'))
        self.tags_edit=QLineEdit();self.tags_edit.setObjectName('tags');self.tags_edit.setPlaceholderText('Add tags, separated by commas')
        self.tags_edit.textEdited.connect(self.schedule_save);meta.addWidget(self.tags_edit,1)
        doc.addLayout(meta);doc.addSpacing(8)
        line=QFrame();line.setFrameShape(QFrame.HLine);line.setStyleSheet('border-top:1px solid palette(mid);');doc.addWidget(line)
        toolbar=QHBoxLayout();toolbar.setSpacing(5)
        self.tools={}
        for label,tip,fn in [('B','Bold (Ctrl+B)',self.bold),('I','Italic (Ctrl+I)',self.italic),('U','Underline (Ctrl+U)',self.underline),('H1','Heading 1',lambda:self.heading(1)),('H2','Heading 2',lambda:self.heading(2)),('• List','Bulleted list',self.bullet),('1. List','Numbered list',self.numbered),('☐ Task','Insert checkbox',self.checkbox),('❝','Block quote',self.quote),('↶','Undo',lambda:self.editor.undo()),('↷','Redo',lambda:self.editor.redo())]:
            b=self.button(label,fn,'tool');b.setToolTip(tip);toolbar.addWidget(b);self.tools[label]=b
        toolbar.addStretch();doc.addLayout(toolbar)
        self.editor=Editor();self.editor.textChanged.connect(self.schedule_save)
        self.editor.cursorPositionChanged.connect(self.update_toolbar)
        doc.addWidget(self.editor,1)
        footer=QHBoxLayout();self.saved=self.lbl('Saved on this device','secondary');footer.addWidget(self.saved);footer.addStretch()
        self.counter=self.lbl('0 words','secondary');footer.addWidget(self.counter);doc.addLayout(footer)
        self.split.addWidget(outer);self.split.setSizes([232,295,823]);self.split.setStretchFactor(2,1)
        self.statusBar().showMessage('Private · Offline · Yours')

    def apply_theme(self):
        c=DARK if self.theme=='dark' else LIGHT
        QApplication.instance().setStyleSheet(stylesheet(c))
        palette=self.editor.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor(c['ink']))
        self.editor.setPalette(palette)
    def shortcuts(self):
        for seq,fn in [('Ctrl+N',self.new_note),('Ctrl+S',self.save),('Ctrl+F',self.focus_search),
                       ('Ctrl+Shift+E',self.export_html),('Ctrl+Shift+F',self.toggle_focus)]:
            action=QAction(self);action.setShortcut(QKeySequence(seq));action.triggered.connect(fn);self.addAction(action)
    def focus_search(self):self.search.setFocus();self.search.selectAll()
    def current(self):return next((n for n in self.data['notes'] if n['id']==self.active),None)
    def build_notebooks(self):
        while self.books_container.count():
            child=self.books_container.takeAt(0)
            if child.widget():child.widget().deleteLater()
        self.book_combo.blockSignals(True);self.book_combo.clear();self.book_combo.addItems(self.data['notebooks']);self.book_combo.blockSignals(False)
        self.book_nav={}
        for book in self.data['notebooks']:
            b=self.button('▫    '+book,lambda _,x=book:self.change_view('book:'+x),'nav')
            b.setMinimumHeight(43)
            b.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
            self.books_container.addWidget(b);self.book_nav[book]=b
        self.update_nav()
    def update_nav(self):
        for key,b in {**self.nav,**{'book:'+x:y for x,y in self.book_nav.items()}}.items():
            b.setProperty('active',str(key==self.view).lower());b.style().unpolish(b);b.style().polish(b)
    def change_view(self,key):
        self.save();self.view=key;self.update_nav();self.refresh_list()
        if self.note_list.count():self.note_list.setCurrentRow(0)
        else:self.blank_editor()
    def visible(self,n):
        if self.view=='Trash':return n['deleted']
        if n['deleted']:return False
        if self.view=='Archive':return n['archived']
        if n['archived']:return False
        if self.view=='Favorites':return n['favorite']
        if self.view=='Pinned':return n['pinned']
        if self.view.startswith('book:'):return n['notebook']==self.view[5:]
        return True
    def refresh_list(self):
        if not hasattr(self,'note_list'):return
        query=self.search.text().casefold().strip()
        entries=[n for n in self.data['notes'] if self.visible(n) and query in (' '.join([
            n['title'],n['body'],' '.join(map(str,n['tags'])),n['notebook']])).casefold()]
        entries.sort(key=lambda n:(bool(n['pinned']),n.get('updated','')),reverse=True)
        self.list_title.setText(self.view[5:] if self.view.startswith('book:') else self.view)
        self.list_count.setText(f'{len(entries)} note'+('s' if len(entries)!=1 else ''))
        self.note_list.blockSignals(True);self.note_list.clear()
        for n in entries:
            title=n['title'].strip() or 'Untitled note'
            snippet=re.sub(r'\s+',' ',n['body']).strip()[:62] or 'A blank page, ready for you…'
            emblem=('⌁ ' if n['pinned'] else '')+('♡ ' if n['favorite'] else '')
            item=QListWidgetItem(f'{emblem}{title}\n{snippet}\n{n["notebook"]}   ·   {str(n.get("updated",""))[:10]}')
            item.setData(Qt.ItemDataRole.UserRole,n['id']);item.setSizeHint(QSize(165,92))
            self.note_list.addItem(item)
            if n['id']==self.active:self.note_list.setCurrentItem(item)
        self.note_list.blockSignals(False)
    def on_pick(self,current,previous):
        if current:self.open_note(current.data(Qt.ItemDataRole.UserRole))
    def blank_editor(self):
        self.save();self.active=None;self.loading=True
        self.title_edit.clear();self.tags_edit.clear();self.editor.clear();self.breadcrumb.setText('YOUR SPACE')
        self.loading=False;self.saved.setText('Choose or create a note')
    def open_note(self,nid):
        if nid==self.active:return
        self.save();n=next((x for x in self.data['notes'] if x['id']==nid),None)
        if n is None:return
        self.loading=True;self.active=nid
        self.title_edit.setText(n['title']);self.tags_edit.setText(', '.join(map(str,n['tags'])))
        ix=self.book_combo.findText(n['notebook'])
        if ix>=0:self.book_combo.setCurrentIndex(ix)
        if n.get('html') is not None:self.editor.setHtml(n['html'])
        else:self.editor.setPlainText(n['body'])
        self.editor.document().setModified(False)
        self.breadcrumb.setText(n['notebook'].upper()+'  /  '+('TRASH' if n['deleted'] else 'YOUR NOTE'))
        self.loading=False;self.saved.setText('Saved on this device');self.update_counter();self.update_toolbar()
        self.refresh_list()
    def schedule_save(self,*args):
        if self.loading or not self.active:return
        self.saved.setText('Saving…');self.update_counter();self.save_timer.start(650)
    def update_counter(self):
        content=self.editor.toPlainText();self.counter.setText(f'{len(content.split())} words  ·  {len(content)} characters')
    def save(self):
        self.save_timer.stop()
        n=self.current()
        if n is None or self.loading:return
        title=self.title_edit.text();body=self.editor.toPlainText()
        rich=self.editor.toHtml();book=self.book_combo.currentText()
        tags=list(dict.fromkeys(x.strip() for x in self.tags_edit.text().split(',') if x.strip()))
        if (title,body,book,tags,rich)==(n['title'],n['body'],n['notebook'],n['tags'],n.get('html')):
            self.saved.setText('Saved on this device');return
        n.update(title=title,body=body,html=rich,notebook=book,tags=tags,updated=now())
        try:
            if STORE.exists():shutil.copy2(STORE,BACKUP)
            atomic_json(STORE,self.data)
        except OSError as e:
            self.saved.setText('Save failed — check disk space')
            QMessageBox.critical(self,'Save failed',str(e));return
        self.saved.setText('Saved on this device')
        self.breadcrumb.setText(book.upper()+'  /  YOUR NOTE')
        self.refresh_list()
    def persist(self):
        try:
            if STORE.exists():shutil.copy2(STORE,BACKUP)
            atomic_json(STORE,self.data)
        except OSError as e:QMessageBox.critical(self,'Save failed',str(e))
    def new_note(self):
        self.save()
        book=self.view[5:] if self.view.startswith('book:') else 'Personal'
        n=fresh(book);self.data['notes'].insert(0,n);self.persist()
        if self.view in ('Trash','Archive'):self.view='All notes'
        self.active=None;self.refresh_list();self.open_note(n['id']);self.title_edit.setFocus()
    def add_notebook(self):
        name,ok=QInputDialog.getText(self,'New notebook','Notebook name:')
        name=name.strip()
        if not ok or not name:return
        if name in self.data['notebooks']:
            QMessageBox.information(self,'Already exists','That notebook already exists.');return
        self.data['notebooks'].append(name);self.persist();self.build_notebooks();self.change_view('book:'+name)
    def toggle_theme(self):
        self.save();self.theme='dark' if self.theme=='light' else 'light'
        atomic_json(PREFS,{'theme':self.theme});self.apply_theme()
    def toggle_focus(self):
        self.focus_mode=not self.focus_mode
        self.rail.setVisible(not self.focus_mode);self.collection.setVisible(not self.focus_mode)
        self.focus_btn.setText('⛶  Exit focus' if self.focus_mode else '⛶  Focus')
        if self.focus_mode:self.editor.setFocus()
    def mutate(self,key,value=None):
        self.save();n=self.current()
        if n is None:return
        n[key]=not n[key] if value is None else value;n['updated']=now()
        self.persist();self.refresh_list()
        if key=='deleted' and n[key]:self.change_view('All notes')
        elif key=='archived' and n[key]:self.change_view('All notes')
    def permanent_delete(self):
        n=self.current()
        if n is None:return
        if QMessageBox.question(self,'Delete permanently',f'Delete “{n["title"] or "Untitled note"}” permanently?\nThis cannot be undone.')!=QMessageBox.StandardButton.Yes:return
        self.save();self.data['notes']=[x for x in self.data['notes'] if x['id']!=n['id']]
        self.active=None;self.persist();self.refresh_list()
        if self.note_list.count():self.note_list.setCurrentRow(0)
        else:self.blank_editor()
    def show_actions(self,point=None):
        n=self.current()
        if n is None:return
        menu=QMenu(self)
        menu.addAction(('☆ Remove favourite' if n['favorite'] else '♡ Favourite'),lambda:self.mutate('favorite'))
        menu.addAction(('Unpin' if n['pinned'] else 'Pin to top'),lambda:self.mutate('pinned'))
        menu.addSeparator()
        if n['deleted']:
            menu.addAction('Restore from trash',lambda:self.mutate('deleted',False))
            menu.addAction('Delete permanently…',self.permanent_delete)
        else:
            menu.addAction(('Unarchive' if n['archived'] else 'Archive'),lambda:self.mutate('archived'))
            menu.addAction('Move to trash',lambda:self.mutate('deleted',True))
        menu.addSeparator()
        menu.addAction('Export as HTML…',self.export_html)
        menu.addAction('Export as text…',self.export_text)
        menu.exec(point or self.more.mapToGlobal(self.more.rect().bottomLeft()))
    def note_menu(self):self.show_actions()
    def list_context(self,point):
        item=self.note_list.itemAt(point)
        if item:
            self.open_note(item.data(Qt.ItemDataRole.UserRole))
            self.show_actions(self.note_list.mapToGlobal(point))
    def export_backup(self):
        self.save()
        path,_=QFileDialog.getSaveFileName(self,'Export all notes','stillroom-backup.json','JSON (*.json)')
        if path:
            try:atomic_json(Path(path),self.data)
            except OSError as e:QMessageBox.critical(self,'Export failed',str(e))
    def export_html(self):
        self.save();n=self.current()
        if not n:return
        path,_=QFileDialog.getSaveFileName(self,'Export note',self.safe_name(n)+'.html','HTML (*.html)')
        if path:
            try:Path(path).write_text(n.get('html') or '<pre>'+html.escape(n['body'])+'</pre>',encoding='utf-8')
            except OSError as e:QMessageBox.critical(self,'Export failed',str(e))
    def export_text(self):
        self.save();n=self.current()
        if not n:return
        path,_=QFileDialog.getSaveFileName(self,'Export note',self.safe_name(n)+'.txt','Text (*.txt)')
        if path:
            try:Path(path).write_text(n['body'],encoding='utf-8')
            except OSError as e:QMessageBox.critical(self,'Export failed',str(e))
    def safe_name(self,n):return re.sub(r'[^\w .-]','_',n['title'] or 'Untitled note')[:80]
    def modify_char(self,kind):
        cursor=self.editor.textCursor();fmt=QTextCharFormat()
        existing=cursor.charFormat()
        if kind=='bold':fmt.setFontWeight(QFont.Weight.Normal if existing.fontWeight()>=QFont.Weight.Bold else QFont.Weight.Bold)
        if kind=='italic':fmt.setFontItalic(not existing.fontItalic())
        if kind=='underline':fmt.setFontUnderline(not existing.fontUnderline())
        cursor.mergeCharFormat(fmt);self.editor.mergeCurrentCharFormat(fmt);self.editor.setFocus()
        self.schedule_save();self.update_toolbar()
    def bold(self):self.modify_char('bold')
    def italic(self):self.modify_char('italic')
    def underline(self):self.modify_char('underline')
    def heading(self,level):
        cursor=self.editor.textCursor();cursor.beginEditBlock()
        fmt=QTextCharFormat();fmt.setFontPointSize(22 if level==1 else 17);fmt.setFontWeight(QFont.Weight.Bold)
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor);cursor.mergeCharFormat(fmt)
        cursor.endEditBlock();self.editor.setTextCursor(cursor);self.editor.setFocus()
    def make_list(self,style):
        cursor=self.editor.textCursor();fmt=QTextListFormat();fmt.setStyle(style)
        cursor.createList(fmt);self.editor.setFocus()
    def bullet(self):self.make_list(QTextListFormat.Style.ListDisc)
    def numbered(self):self.make_list(QTextListFormat.Style.ListDecimal)
    def checkbox(self):
        cursor=self.editor.textCursor();cursor.insertText('☐  ');self.editor.setFocus()
    def quote(self):
        cursor=self.editor.textCursor();block=cursor.blockFormat();block.setLeftMargin(28)
        cursor.setBlockFormat(block);cursor.insertText('❝  ');self.editor.setFocus()
    def update_toolbar(self):
        if not hasattr(self,'editor'):return
        fmt=self.editor.currentCharFormat()
        for key,state in [('B',fmt.fontWeight()>=QFont.Weight.Bold),('I',fmt.fontItalic()),('U',fmt.fontUnderline())]:
            if key in self.tools:
                b=self.tools[key];b.setProperty('active',str(state).lower());b.style().unpolish(b);b.style().polish(b)
    def closeEvent(self,event):
        self.save()
        if self.saved.text().startswith('Save failed'):
            event.ignore();return
        event.accept()

if __name__=='__main__':
    app=QApplication(sys.argv)
    app.setApplicationName('Stillroom')
    app.setStyle('Fusion')
    window=Stillroom();window.show()
    sys.exit(app.exec())
