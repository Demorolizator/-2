"""Extension of attic GUI: zoom, hatch blocks, support post catalog and arrays."""
import json
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from construction_objects import (DEFAULT_HATCH_TYPES, DEFAULT_SUPPORT_TYPES, rect_corners,
                                  valid_placement, supports_on_line, count_by_type)

class ConstructionMixin:
    def __init__(self):
        self.hatch_types=[dict(t) for t in DEFAULT_HATCH_TYPES]
        self.support_types=[dict(t) for t in DEFAULT_SUPPORT_TYPES]
        self.hatches=[]
        self.supports=[]
        self.hatch_id='l1'
        self.support_id='s1'
        self.construction_mode='select'
        self.construction_selected=None
        self.construction_drag=None
        self.support_line_start=None
        self.attic_zoom=1.0
        self.zoom_focus=None
        super().__init__()
        self.title('RoofStudio v1.0 — Капитальный ремонт кровли')

    def _build_attic(self):
        super()._build_attic()
        controls=tk.Frame(self.workspace,bg='#FFFFFF')
        controls.pack(before=self.attic_canvas,fill='x',padx=12,pady=(0,5))
        tk.Label(controls,text='Люк:',bg='#FFFFFF',font=self.f_small).pack(side='left')
        self.hatch_choice=tk.StringVar(value=self.hatch_types[0]['code'] if self.hatch_types else '')
        hbox=ttk.Combobox(controls,textvariable=self.hatch_choice,values=[t['code'] for t in self.hatch_types],width=6,state='readonly')
        hbox.pack(side='left',padx=3)
        self.button(controls,'+ Люк',lambda:self._construction_mode('hatch'),padx=6)
        tk.Label(controls,text='Опора:',bg='#FFFFFF',font=self.f_small).pack(side='left',padx=(8,2))
        self.support_choice=tk.StringVar(value=self.support_types[0]['code'] if self.support_types else '')
        sbox=ttk.Combobox(controls,textvariable=self.support_choice,values=[t['code'] for t in self.support_types],width=6,state='readonly')
        sbox.pack(side='left',padx=3)
        self.button(controls,'+ Столб',lambda:self._construction_mode('support'),padx=6)
        self.button(controls,'Ряд по 2 точкам',lambda:self._construction_mode('line'),padx=6)
        self.button(controls,'Параметры блоков',self._edit_construction_catalog,padx=6)
        self.button(controls,'Удалить блок',self._delete_construction,padx=6)
        self.button(controls,'−',lambda:self._zoom_by(1/1.25),padx=9)
        self.button(controls,'+',lambda:self._zoom_by(1.25),padx=9)
        self.button(controls,'Вписать',self._zoom_fit,padx=5)
        self.attic_canvas.bind('<ButtonRelease-1>',lambda e:(setattr(self,'construction_drag',None),setattr(self,'attic_drag',None)))
        self.attic_canvas.bind('<MouseWheel>',self._zoom_wheel)
        self.attic_canvas.bind('<Button-4>',lambda e:self._zoom_by(1.25,e))
        self.attic_canvas.bind('<Button-5>',lambda e:self._zoom_by(1/1.25,e))
        self._render_attic()

    def _attic_transform(self):
        outline=super()._attic_transform()
        if self.attic_zoom!=1.0:
            c=self.attic_canvas
            w=max(c.winfo_width(),550);h=max(c.winfo_height(),220)
            # anchor zoom around canvas center; measured model remains unchanged
            focus=self.zoom_focus or (w/2,h/2)
            x0,y0=focus
            factor=self.attic_zoom
            self.attic_ox=x0-(x0-self.attic_ox)*factor
            self.attic_oy=y0-(y0-self.attic_oy)*factor
            self.attic_scale*=factor
        return outline

    def _zoom_by(self,factor,event=None):
        target=max(0.25,min(12.0,self.attic_zoom*factor))
        self.attic_zoom=target
        self.zoom_focus=None  # keep stable centered zoom when resizing
        if self.attic_canvas and self.attic_canvas.winfo_exists():self._render_attic()
        self.status.set(f'Масштаб плана чердака: {target*100:.0f}%')

    def _zoom_wheel(self,e):self._zoom_by(1.25 if e.delta>0 else 1/1.25,e)
    def _zoom_fit(self):self.attic_zoom=1.0;self.zoom_focus=None;self._render_attic()

    def _find_type(self,category):
        if category=='hatch':
            code=self.hatch_choice.get() if hasattr(self,'hatch_choice') else self.hatch_types[0]['code']
            return next((t for t in self.hatch_types if t['code']==code),None)
        code=self.support_choice.get() if hasattr(self,'support_choice') else self.support_types[0]['code']
        return next((t for t in self.support_types if t['code']==code),None)

    def _construction_mode(self,mode):
        self.construction_mode=mode
        self.attic_mode='select'
        self.support_line_start=None
        self.status.set('Укажите на плане 2 точки линии опор' if mode=='line' else 'Укажите место размещения блока на чердаке')

    def _attic_set_mode(self,mode):
        self.construction_mode='select'
        super()._attic_set_mode(mode)

    def _hit_construction(self,x,y):
        for category,arr,types in [('support',self.supports,self.support_types),('hatch',self.hatches,self.hatch_types)]:
            lookup={t['id']:t for t in types}
            for idx in range(len(arr)-1,-1,-1):
                obj=arr[idx];typ=lookup.get(obj.get('type_id'))
                if not typ:continue
                corners=rect_corners(obj,typ)
                xx=[p[0] for p in corners];yy=[p[1] for p in corners]
                if min(xx)<=x<=max(xx) and min(yy)<=y<=max(yy):return category,idx
        return None

    def _attic_click(self,event):
        x,y=self._attic_model(event.x,event.y)
        if self.construction_mode=='line':
            if self.support_line_start is None:
                self.support_line_start=(x,y)
                self.status.set('Теперь укажите вторую точку линии размещения опор')
                return
            typ=self._find_type('support')
            if not typ:return
            try:
                made,rejected=supports_on_line(self.support_line_start,(x,y),typ['spacing_mm'],typ,self._inner_outline(),self.supports)
            except ValueError as exc:
                messagebox.showwarning('Ряд столбов',str(exc));return
            self.supports.extend(made)
            self.support_line_start=None
            self.construction_mode='select'
            self.status.set(f'Создан ряд опор: {len(made)} шт.; не поместились в контур: {rejected} шт.')
            self._render_attic();return
        if self.construction_mode in ('hatch','support'):
            category=self.construction_mode
            typ=self._find_type(category)
            if not typ:return
            inst={'type_id':typ['id'],'x':round(x,4),'y':round(y,4),'rotation':0}
            if not valid_placement(inst,typ,self._inner_outline()):
                self.status.set('Блок целиком должен находиться внутри чердака');return
            arr=self.hatches if category=='hatch' else self.supports
            arr.append(inst)
            self.construction_selected=(category,len(arr)-1)
            self.construction_mode='select'
            self._render_attic();return
        hit=self._hit_construction(x,y)
        if hit:
            self.construction_selected=hit
            self.construction_drag=hit
            self.attic_selected=None
            self._render_attic();return
        self.construction_selected=None
        self.construction_drag=None
        super()._attic_click(event)

    def _attic_motion(self,event):
        if self.construction_drag:
            category,idx=self.construction_drag
            arr=self.hatches if category=='hatch' else self.supports
            types=self.hatch_types if category=='hatch' else self.support_types
            if idx>=len(arr):return
            old=arr[idx];typ=next((t for t in types if t['id']==old['type_id']),None)
            if not typ:return
            x,y=self._attic_model(event.x,event.y)
            candidate={**old,'x':round(x,4),'y':round(y,4)}
            if valid_placement(candidate,typ,self._inner_outline()):
                arr[idx]=candidate;self._render_attic()
            return
        super()._attic_motion(event)

    def _render_attic(self):
        super()._render_attic()
        c=self.attic_canvas
        if c is None or not c.winfo_exists():return
        for category,arr,types,color in [('hatch',self.hatches,self.hatch_types,'#D9EEF9'),('support',self.supports,self.support_types,'#DCEFD9')]:
            lookup={t['id']:t for t in types}
            for idx,o in enumerate(arr):
                typ=lookup.get(o.get('type_id'))
                if not typ:continue
                corners=rect_corners(o,typ)
                pts=[self._attic_screen(p) for p in corners]
                flat=[z for p in pts for z in p]
                selected=self.construction_selected==(category,idx)
                outline='#1D4FD0' if selected else ('#376A86' if category=='hatch' else '#4B6A3F')
                c.create_polygon(*flat,fill=color,outline=outline,width=3 if selected else 2)
                cx,cy=self._attic_screen((o['x'],o['y']))
                if category=='hatch':
                    c.create_line(*pts[0],*pts[2],fill=outline,width=1)
                    c.create_line(*pts[1],*pts[3],fill=outline,width=1)
                    c.create_line(cx-10,cy,cx+10,cy,fill=outline,width=1)
                else:
                    c.create_rectangle(cx-5,cy-5,cx+5,cy+5,fill=outline,outline=outline)
                    c.create_line(cx-12,cy,cx+12,cy,fill=outline,width=1)
                    c.create_line(cx,cy-12,cx,cy+12,fill=outline,width=1)
                c.create_text(cx,cy-12,text=typ['code'],fill='#173A60',font=self.f_tiny)
        if self.support_line_start:
            sx,sy=self._attic_screen(self.support_line_start)
            c.create_oval(sx-5,sy-5,sx+5,sy+5,fill='#D97706')
        if hasattr(self,'attic_status'):
            self.attic_status.set(self.attic_status.get()+f' • Люки: {len(self.hatches)} • Опоры: {len(self.supports)} • Zoom {self.attic_zoom*100:.0f}%')

    def _delete_construction(self):
        if not self.construction_selected:
            self.status.set('Выберите люк или столб на плане');return
        category,idx=self.construction_selected
        arr=self.hatches if category=='hatch' else self.supports
        if idx<len(arr):arr.pop(idx)
        self.construction_selected=None
        self._render_attic()

    def _edit_construction_catalog(self):
        win=tk.Toplevel(self)
        win.title('Каталог блоков: люки и опорные столбы')
        win.geometry('510x465');win.transient(self);win.grab_set()
        category=tk.StringVar(value='Люк')
        top=tk.Frame(win,padx=12,pady=8);top.pack(fill='x')
        ttk.Combobox(top,textvariable=category,values=['Люк','Опорный столб'],state='readonly',width=18).pack(side='left')
        code=tk.StringVar();width=tk.StringVar();length=tk.StringVar();height=tk.StringVar();material=tk.StringVar();step=tk.StringVar();note=tk.StringVar()
        mark=tk.StringVar()
        combo=ttk.Combobox(top,textvariable=mark,state='readonly',width=12);combo.pack(side='left',padx=7)
        rows=[('Марка',code),('Ширина, мм',width),('Длина, мм',length),('Высота, мм',height),('Материал',material),('Шаг опор, мм',step),('Примечание',note)]
        form=tk.Frame(win,padx=18,pady=8);form.pack(fill='both',expand=True)
        for lab,var in rows:
            row=tk.Frame(form);row.pack(fill='x',pady=5)
            tk.Label(row,text=lab,width=20,anchor='w').pack(side='left')
            ttk.Entry(row,textvariable=var,width=34).pack(side='left',fill='x',expand=True)
        def get_items():return self.hatch_types if category.get()=='Люк' else self.support_types
        def populate(_=None):
            items=get_items();combo.configure(values=[t['code'] for t in items]);mark.set(items[0]['code'] if items else '')
            select()
        def select(_=None):
            t=next((v for v in get_items() if v['code']==mark.get()),None)
            if not t:return
            code.set(t['code']);width.set(str(t['width_mm']));length.set(str(t['length_mm']))
            height.set(str(t.get('height_mm',0)));material.set(t.get('material',''))
            step.set(str(t.get('spacing_mm',3000)));note.set(t.get('note',''))
        def add_new():
            code.set('Л2' if category.get()=='Люк' else 'ОС2');width.set('1000' if category.get()=='Люк' else '380')
            length.set('1000' if category.get()=='Люк' else '380');height.set('0' if category.get()=='Люк' else '2400')
            material.set('Кирпичный');step.set('3000');note.set('')
            mark.set('')
        def save_type():
            try:
                w=float(width.get().replace(',','.'));l=float(length.get().replace(',','.'))
                ht=float(height.get().replace(',','.')) if height.get().strip() else 0
                sp=float(step.get().replace(',','.')) if step.get().strip() else 3000
                if not code.get().strip() or min(w,l)<50 or max(w,l)>10000 or ht<0 or not 100<=sp<=100000:raise ValueError()
            except ValueError:
                messagebox.showwarning('Размеры','Проверьте марку, габариты (50–10000 мм) и шаг (100–100000 мм)',parent=win);return
            items=get_items();matched=next((v for v in items if v['code']==mark.get()),None)
            if matched is None:matched={'id':('l' if category.get()=='Люк' else 's')+str(max([len(items)+1,2]))};items.append(matched)
            matched.update(code=code.get().strip(),width_mm=w,length_mm=l,note=note.get())
            if category.get()=='Опорный столб':matched.update(height_mm=ht,material=material.get(),spacing_mm=sp)
            populate()
            if hasattr(self,'hatch_choice'):self.hatch_choice.set(self.hatch_types[0]['code'])
            if hasattr(self,'support_choice'):self.support_choice.set(self.support_types[0]['code'])
            self._render_attic()
        category.trace_add('write',lambda *_:populate())
        combo.bind('<<ComboboxSelected>>',select)
        bar=tk.Frame(win,padx=12,pady=12);bar.pack(fill='x')
        ttk.Button(bar,text='Новая марка',command=add_new).pack(side='left',padx=4)
        ttk.Button(bar,text='Сохранить тип',command=save_type).pack(side='left',padx=4)
        ttk.Button(bar,text='Закрыть',command=win.destroy).pack(side='right',padx=4)
        populate()

    def _attic_data(self):
        d=super()._attic_data()
        d['hatch_types']=self.hatch_types;d['support_types']=self.support_types
        d['hatches']=self.hatches;d['supports']=self.supports
        return d

    def load(self):
        # Let existing loader preserve all old data; restore new collections afterwards.
        super().load()
        if self.path:
            try:
                d=json.loads(Path(self.path).read_text(encoding='utf-8')).get('attic',{})
                self.hatch_types=[dict(t) for t in d.get('hatch_types',DEFAULT_HATCH_TYPES)]
                self.support_types=[dict(t) for t in d.get('support_types',DEFAULT_SUPPORT_TYPES)]
                self.hatches=list(d.get('hatches',[]));self.supports=list(d.get('supports',[]))
                self.construction_selected=None
            except (OSError,ValueError,TypeError) as exc:
                messagebox.showwarning('Блоки чердака',str(exc))

    def new(self):
        super().new()
        if self.path is None:
            self.hatch_types=[dict(t) for t in DEFAULT_HATCH_TYPES];self.support_types=[dict(t) for t in DEFAULT_SUPPORT_TYPES]
            self.hatches=[];self.supports=[];self.construction_selected=None

    def fill_table(self):
        super().fill_table()
        table=getattr(self,'data_table',None)
        if table is None or not table.winfo_exists():return
        for kind,arr,types in [('Люки',self.hatches,self.hatch_types),('Опорные столбы',self.supports,self.support_types)]:
            codes=count_by_type(arr,types)
            for code,qty in codes.items():table.insert('','end',values=(kind,code,qty,'шт.'))
            lookup={t['id']:t for t in types}
            if kind=='Люки':
                area=sum(float(lookup[o['type_id']]['width_mm'])*float(lookup[o['type_id']]['length_mm'])/1e6 for o in arr if o['type_id'] in lookup)
                table.insert('','end',values=('Чердак','Площадь люков (для вычета)',f'{area:.3f}','м²'))
            else:
                volume=sum(float(lookup[o['type_id']]['width_mm'])*float(lookup[o['type_id']]['length_mm'])*float(lookup[o['type_id']].get('height_mm',0))/1e9 for o in arr if o['type_id'] in lookup)
                table.insert('','end',values=('Опоры','Геометрический объём столбов, без вычета полостей',f'{volume:.3f}','м³'))

    def export_attic_dxf(self):
        # Reuse existing DXF file generation with new blocks included.
        from attic_cad_export import write_attic_plan_dxf
        try:
            outer=self._attic_outline();inner=self._inner_outline();ridge,pitch=self._roof_height()
        except Exception as e:
            messagebox.showwarning('Экспорт чердака DXF',str(e));return
        path=filedialog.asksaveasfilename(title='DXF: план чердака',defaultextension='.dxf',filetypes=[('AutoCAD DXF','*.dxf')])
        if not path:return
        try:
            write_attic_plan_dxf(path,outer,inner,self.shaft_catalog,self.shaft_instances,
                                 self.wall_thickness_mm,self.wall_above_slag_mm,ridge,pitch,
                                 hatch_types=self.hatch_types,hatches=self.hatches,
                                 support_types=self.support_types,supports=self.supports)
            self.status.set('DXF чердака с люками и опорами: '+path)
        except Exception as e:messagebox.showerror('DXF чердака',str(e))
