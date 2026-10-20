"""Experimental raw ADC viewer. Displays only samples returned by hardware."""
import csv,queue,threading,time,math,json,os
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from .driver import TC3,SCALE_LABELS,SCALE_MV,TIME_LABELS
from .updater import device_ports,install_firmware
from .i18n import translate
from .instrument import MODE_NAMES,MODES,WAVEFORMS,TOOLS

class LocalizedVar(tk.StringVar):
    def __init__(self,owner,value):
        self.owner=owner;self.original=value
        super().__init__(master=owner.root,value=owner.tr(value))
    def set(self,value):
        self.original=value;super().set(self.owner.tr(value))
    def refresh(self):super().set(self.owner.tr(self.original))

class Scope:
    def __init__(self,root):
        self.root=root;root.title('Retro Saver · FNIRSI DSO-TC3 PC v1.1-dev');root.geometry('1200x850');root.minsize(760,590)
        self.settings_path=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'FNIRSI-TC3-PC/settings.json'
        try:self.language=json.loads(self.settings_path.read_text(encoding='utf-8')).get('language','tr')
        except (OSError,ValueError):self.language='tr'
        self.static_texts=[]
        root.configure(bg='#151b23')
        self.events=queue.Queue();self.stop=threading.Event();self.thread=None
        self.commands=queue.Queue();self.device_controls={}
        self.samples=[];self.metadata={}
        self.zoom_x=1.;self.zoom_y=1.;self.pan_x=0.;self.pan_y=0.;self.drag_origin=None
        self.frame_count=0;self.last_saved=0
        self.updating=False;self.auto_connect=True;self.view_mode=None
        self.mode='BEKLE'
        style=ttk.Style(root);style.theme_use('clam')
        style.configure('TFrame',background='#151b23')
        style.configure('TLabel',background='#151b23',foreground='#bbc6d4',font=('Segoe UI',10))
        style.configure('TButton',background='#293341',foreground='#eef4fa',borderwidth=0,padding=(12,8))
        style.map('TButton',background=[('active','#3a485a')])
        masthead=tk.Frame(root,bg='#151b23');masthead.pack(fill='x',padx=22,pady=(16,0))
        tk.Label(masthead,text='FNIRSI',font=('Segoe UI',23,'bold'),fg='#f4f7fa',bg='#151b23').pack(side='left')
        tk.Label(masthead,text='DSO-TC3  /  PC OSCILLOSCOPE',font=('Segoe UI',12),fg='#9aaaba',bg='#151b23').pack(side='right')
        toolbar=ttk.Frame(root,padding=(20,12));toolbar.pack(fill='x')
        ttk.Label(toolbar,text='USB portu:').pack(side='left')
        self.port=tk.StringVar(value='Otomatik')
        ttk.Entry(toolbar,textvariable=self.port,width=12).pack(side='left',padx=8)
        self.start_button=ttk.Button(toolbar,text='Başlat',command=self.start);self.start_button.pack(side='left',padx=4)
        ttk.Button(toolbar,text='HOLD',command=self.hold).pack(side='left',padx=4)
        ttk.Button(toolbar,text='CSV kaydet',command=self.save).pack(side='right')
        self.firmware_button=ttk.Button(toolbar,text='Firmware kur',command=self.install);self.firmware_button.pack(side='right',padx=6)
        self.language_var=tk.StringVar(value='English' if self.language=='en' else 'Türkçe')
        language_picker=ttk.Combobox(toolbar,textvariable=self.language_var,values=('Türkçe','English'),width=8,state='readonly');language_picker.pack(side='right',padx=5)
        language_picker.bind('<<ComboboxSelected>>',lambda event:self.set_language('en' if self.language_var.get()=='English' else 'tr'))
        zoom_bar=ttk.Frame(root,padding=(20,0,20,8));zoom_bar.pack(fill='x');self.zoom_bar=zoom_bar
        for label,command in [('X +',lambda:self.zoom(1.5,1)),('X −',lambda:self.zoom(1/1.5,1)),('Y +',lambda:self.zoom(1,1.5)),('Y −',lambda:self.zoom(1,1/1.5)),('Sıfırla',self.reset_zoom),('Dalgalanmayı ortala',self.centre_ripple)]:
            ttk.Button(zoom_bar,text=label,command=command).pack(side='left',padx=2)
        ttk.Label(zoom_bar,text='Tekerlek: X zoom · Shift: Y zoom · Sürükle: kaydır').pack(side='left',padx=10)
        modebar=ttk.Frame(root,padding=(20,0,20,8));modebar.pack(fill='x');self.modebar=modebar
        self.mode_buttons={}
        for name,label in [('home','Ana menü'),('oscilloscope','Osiloskop'),('generator','Generator'),('tools','Tools'),('tester','M-Tester')]:
            button=ttk.Button(modebar,text=label,command=lambda n=name:self.instrument_command('mode',n));button.pack(side='left',padx=3);self.mode_buttons[name]=button
        ttk.Button(modebar,text='AUTO',command=lambda:self.request_control('auto',0)).pack(side='right')
        self.instrument_bar=ttk.Frame(root,padding=(20,0,20,8))
        self.item_picker=ttk.Combobox(self.instrument_bar,state='disabled',width=18);self.item_picker.pack(side='left',padx=5)
        self.item_picker.bind('<<ComboboxSelected>>',lambda event:self.instrument_command('item',self.item_picker.current()))
        for label,key in [('Geri',1),('◀',4),('▲',8),('OK / Test',2),('▼',32),('▶',16)]:
            ttk.Button(self.instrument_bar,text=label,command=lambda k=key:self.instrument_command('key',k)).pack(side='left',padx=3)
        self.canvas=tk.Canvas(root,bg='#101923',highlightthickness=2,highlightbackground='#536273');self.canvas.pack(fill='both',expand=True,padx=20,pady=(0,8))
        self.status=LocalizedVar(self,'Cihazdan henüz örnek alınmadı.')
        ttk.Label(root,textvariable=self.status,padding=(20,5)).pack(fill='x')
        settings=ttk.Frame(root,padding=(20,6));settings.pack(fill='x');self.scope_settings=settings
        specs=[('scale_index','V/div',SCALE_LABELS),('probe_index','Prob',('X1','X10')),('timebase_index','Zaman/div',TIME_LABELS),('coupling_index','Bağlantı',('AC','DC')),('trigger_mode','Tetik',('Auto','Normal','Single')),('trigger_edge','Kenar',('↑','↓'))]
        for name,label,values in specs:
            ttk.Label(settings,text=label).pack(side='left',padx=(0,4))
            combo=ttk.Combobox(settings,values=values,width=8,state='disabled');combo.pack(side='left',padx=(0,10))
            combo.bind('<<ComboboxSelected>>',lambda event,n=name,c=combo:self.request_control(n,c.current()))
            self.device_controls[name]=combo
        self.note=LocalizedVar(self,'Firmware v2 bekleniyor · Voltaj ölçümleri ve cihaz kontrolü henüz etkin değil.')
        self.note_label=ttk.Label(root,textvariable=self.note,padding=(20,5),font=('Segoe UI',9));self.note_label.pack(fill='x',pady=(0,8))
        self.canvas.bind('<Configure>',lambda event:self.draw())
        self.canvas.bind('<MouseWheel>',self.wheel_zoom)
        self.canvas.bind('<ButtonPress-1>',self.begin_pan)
        self.canvas.bind('<B1-Motion>',self.drag_pan)
        self.canvas.bind('<Double-Button-1>',lambda event:self.reset_zoom())
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(50,self.poll)
        root.after(1500,self.watch_usb)
        self._register_texts(root)
        self.refresh_language()
    def tr(self,text):return translate(text,self.language)
    def _register_texts(self,parent):
        for widget in parent.winfo_children():
            if 'text' in widget.keys() and not widget.cget('textvariable'):
                text=widget.cget('text')
                if text:self.static_texts.append((widget,text))
            self._register_texts(widget)
    def refresh_language(self):
        for widget,text in self.static_texts:widget.configure(text=self.tr(text))
        self.status.refresh();self.note.refresh();self.draw()
    def set_language(self,language):
        if language not in ('tr','en'):return
        self.language=language;self.language_var.set('English' if language=='en' else 'Türkçe')
        self.refresh_language()
        try:
            self.settings_path.parent.mkdir(parents=True,exist_ok=True)
            self.settings_path.write_text(json.dumps({'language':language}),encoding='utf-8')
        except OSError:self.note.set('Language preference could not be saved.')
    def start(self):
        if self.updating:return
        if self.thread and self.thread.is_alive():return
        port=self.port.get().strip()
        if port.lower() in ('otomatik','auto',''):
            ports=device_ports()
            if len(ports)!=1:
                self.status.set('USB bekleniyor · Tek bir DSO-TC3 bağlayın.');return
            port=ports[0]
        self.auto_connect=True
        self.stop.clear();self.mode='RUN';self.start_button.configure(state='disabled')
        self.status.set(f'{port} · Cihaz firmware bağlantısı kontrol ediliyor…')
        def work():
            try:
                with TC3(port) as device:
                    device.read_metadata() # Must match signature before sample command 0x20.
                    while not self.stop.is_set():
                        try:
                            while True:
                                name,value=self.commands.get_nowait()
                                try:
                                    if name=='mode':result=device.select_mode(value)
                                    elif name=='item':result=device.select_item(value)
                                    elif name=='key':device.press_key(value);result=device.read_metadata()
                                    else:result=device.set_control(name,value)
                                    self.events.put(('setting',result))
                                except Exception as error:self.events.put(('setting_error',str(error)))
                        except queue.Empty:pass
                        metadata,samples=device.read_waveform()
                        self.events.put(('frame',(metadata,samples)))
                        self.stop.wait(0.1)
            except Exception as error:self.events.put(('error',str(error)))
            finally:self.events.put(('stopped',None))
        self.thread=threading.Thread(target=work,daemon=True);self.thread.start()
    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='frame':
                    if self.stop.is_set():continue
                    self.metadata,self.samples=value
                    self.sync_instrument_view()
                    if self.metadata.get('protocol_version',0)>=2:
                        self.mode='HOLD' if self.metadata.get('device_hold') else 'RUN'
                        for name,combo in self.device_controls.items():
                            combo.configure(state='readonly')
                            index=self.metadata.get(name,-1)
                            if 0<=index<len(combo['values']):combo.current(index)
                        self.note.set('Cihazın hesapladığı voltajlar · Ayarlar cihazdan geri okunur · Güç kaynağını kontrol etmez.' if self.metadata.get('device_mode')==3 else 'Mod ve tuş işlemleri cihazdan geri okunur.')
                    self.frame_count+=1
                    if time.monotonic()-self.last_saved>=1:
                        self.last_saved=time.monotonic()
                        destination=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'FNIRSI-TC3-PC'/'viewer-live.json'
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        temporary=destination.with_suffix('.tmp')
                        temporary.write_text(json.dumps({'timestamp':time.time(),'process_id':os.getpid(),'state':'streaming','frame_count':self.frame_count,'port':self.port.get(),'metadata':self.metadata,'samples_raw':self.samples}),encoding='utf-8')
                        temporary.replace(destination)
                    self.status.set(f'USB bağlı  ·  {self.port.get()}  ·  {len(self.samples)} örnek / kare  ·  #{self.frame_count}')
                    self.draw()
                elif kind=='error':self.mode='HATA';self.status.set('Bağlantı/okuma hatası: '+value);self.draw()
                elif kind=='setting_error':self.note.set('Ayar uygulanamadı: '+value)
                elif kind=='setting':
                    self.metadata=value
                    if value.get('device_mode',3)!=3:self.samples=[]
                    self.sync_instrument_view();self.note.set('Ayar cihazdan geri okunarak doğrulandı.');self.draw()
                elif kind=='flash_progress':self.status.set(f'Firmware yükleniyor: %{value} · USB bağlantısını kesmeyin.')
                elif kind=='flash_done':
                    self.updating=False;self.auto_connect=True
                    self.firmware_button.configure(state='normal');self.start_button.configure(state='normal')
                    self.status.set('Yükleme tamamlandı. Cihazı güç tuşuyla açıp osiloskop ekranına geçin.')
                elif kind=='flash_error':
                    self.updating=False;self.auto_connect=False
                    self.firmware_button.configure(state='normal');self.start_button.configure(state='normal')
                    self.status.set('Yükleme durduruldu: '+value)
                elif kind=='stopped':
                    self.start_button.configure(state='normal')
                    if self.mode=='RUN':self.mode='HOLD'
                    self.draw()
        except queue.Empty:pass
        self.root.after(50,self.poll)
    def hold(self):
        self.auto_connect=False
        self.stop.set();self.mode='HOLD';self.status.set('HOLD · Son PC karesi donduruldu.');self.draw()
    def watch_usb(self):
        if self.auto_connect and not self.updating and not (self.thread and self.thread.is_alive()):self.start()
        self.root.after(2000,self.watch_usb)
    def install(self):
        if self.updating:return
        if not messagebox.askyesno(self.tr('DSO-TC3 V0.3 firmware kurulumu'),self.tr('Yalnızca desteklenen DSO-TC3 V0.3 içindir. Firmware değiştirmek cihazı çalışmaz hâle getirebilir.\n\nCihazı kapatıp ▼ + güç ile Bootloader OK ekranına geçin. Orijinal firmware yedeğinizi saklayın.\n\nBu cihaz için yüklemeyi başlatmak istiyor musunuz?')):return
        self.updating=True;self.auto_connect=False;self.stop.set()
        self.firmware_button.configure(state='disabled');self.start_button.configure(state='disabled')
        self._start_installer()
    def _start_installer(self):
        if self.thread and self.thread.is_alive():self.root.after(100,self._start_installer);return
        def work():
            try:
                install_firmware(lambda percent:self.events.put(('flash_progress',percent)))
                self.events.put(('flash_done',None))
            except Exception as error:self.events.put(('flash_error',str(error)))
        self.thread=threading.Thread(target=work,daemon=True);self.thread.start()
    def toggle_run(self):
        if self.metadata.get('protocol_version',0)>=2:self.request_control('device_hold',not self.metadata.get('device_hold',False))
        elif self.mode=='RUN':self.hold()
        else:self.start()
    def request_control(self,name,value):
        if self.metadata.get('protocol_version',0)<2:
            self.note.set('Bu kontrol için firmware v2 yüklenmeli.');return
        self.commands.put((name,value));self.note.set('Ayar cihaza gönderiliyor; geri okuma bekleniyor…')
    def instrument_command(self,name,value):
        if self.metadata.get('protocol_version',0)<3:
            self.note.set('Bu bölümler için çoklu mod firmware v3 gerekiyor.');return
        if not (self.thread and self.thread.is_alive()) or self.stop.is_set():
            self.note.set('Önce USB bağlantısını başlatın.');return
        self.commands.put((name,value));self.note.set('Ayar cihaza gönderiliyor; geri okuma bekleniyor…')
    def sync_instrument_view(self):
        mode=self.metadata.get('device_mode',3)
        if mode!=self.view_mode:
            self.view_mode=mode
            if mode==3:
                self.instrument_bar.pack(fill='x',before=self.canvas)
                self.zoom_bar.pack(fill='x',before=self.modebar)
                self.scope_settings.pack(fill='x',before=self.note_label)
            else:
                self.scope_settings.pack_forget()
                self.zoom_bar.pack_forget()
                self.instrument_bar.pack(fill='x',before=self.canvas)
        for name,button in self.mode_buttons.items():
            button.configure(state='disabled' if MODES[name]==mode else 'normal')
        choices=WAVEFORMS if mode==4 else TOOLS if mode==5 else ()
        self.item_picker.configure(values=choices,state='readonly' if choices else 'disabled')
        index=self.metadata.get('instrument_selection',-1)
        if choices and 0<=index<len(choices):self.item_picker.current(index)
        else:self.item_picker.set('')
    def draw_instrument(self):
        c=self.canvas;w=max(c.winfo_width(),200);h=max(c.winfo_height(),200)
        mode=self.metadata.get('device_mode',1)
        c.create_text(30,30,text=self.tr(MODE_NAMES.get(mode,'Ana menü')),anchor='nw',fill='#eeef35',font=('Segoe UI',28,'bold'))
        rows=[];hint=''
        if self.metadata.get('protocol_version',0)<3:
            rows=[self.tr('Bu bölümler için çoklu mod firmware v3 gerekiyor.')]
        elif mode==1:
            cards=[('tester','M-Tester'),('oscilloscope','Osiloskop'),('generator','Generator'),('tools','Tools')]
            for i,(name,label) in enumerate(cards):
                col,row=i%2,i//2;x1=32+col*(w-48)/2;y1=105+row*120;x2=x1+(w-80)/2;y2=y1+98
                tag='mode_'+name
                c.create_rectangle(x1,y1,x2,y2,fill='#233144',outline='#eeef35' if self.metadata.get('home_selection')==i else '#4c6077',width=2,tags=tag)
                c.create_text((x1+x2)/2,(y1+y2)/2,text=self.tr(label),fill='#e6f1ff',font=('Segoe UI',23,'bold'),tags=tag)
                c.tag_bind(tag,'<Button-1>',lambda event,n=name:self.instrument_command('mode',n))
            hint=self.tr('Seçili mod ve değerler USB üzerinden cihazdan okunur.')
        elif mode==4:
            g=self.metadata['generator'];idx=self.metadata['instrument_selection']
            rows=[WAVEFORMS[idx] if idx<len(WAVEFORMS) else '—',f"Freq: {g['frequency_hz']:,} Hz",f"Amp: {g['amplitude_v']} V",f"Duty: {g['duty_percent']} %"]
            hint=self.tr('▶ alan / basamak seçer · ◀ geri · ▲/▼ değeri değiştirir. Çıkış cihazdadır.')
        elif mode==5:
            t=self.metadata['tools'];idx=self.metadata['instrument_selection']
            rows=[TOOLS[idx] if idx<len(TOOLS) else '—']
            if idx==1:rows+=[f"{t['voltage_v']:.3f} V" if t['voltage_v'] is not None else '— V']
            elif idx==2:rows+=[f"{t['sensor_temperature']} °C" if self.metadata['tester']['type_code']==18 else self.tr('Sensör bekleniyor')]
            elif idx==3:rows+=[f"{t['sensor_temperature']} °C / {t['sensor_humidity']} %" if self.metadata['tester']['type_code']==19 else self.tr('Sensör bekleniyor')]
            elif idx==4:rows+=[f"IR: {t['ir_code']:08X}" if t['ir_received'] else self.tr('IR sinyali bekleniyor')]
            elif idx==0:rows+=[self.tr('Devamlılık sonucu cihazın sesinden izlenir.'),self.tr('Standart 1-2-3 girişi; 0–40 V girişine taşınmadı.')]
            elif idx==5:rows+=[self.tr('Kalibrasyon adımları için cihaz ekranını izleyin.')]
            hint=self.tr('▲/▼ araç seçer. Voltaj girişi: 0–40 V. Diğer testler cihazın standart girişlerini kullanır.')
        elif mode==2:
            t=self.metadata['tester'];code=t['type_code']
            rows=[t['type_name']]
            if code not in (0,1):
                pins=[t['pins'][0],t['pins'][2]] if code in (10,12,13,14,15) else t['pins']
                if code==16:rows+=['K / A']
                elif len(set(pins))==len(pins) and all(1<=pin<=3 for pin in pins):rows+=[f"Pins: {' / '.join(map(str,pins))}"]
                if code==14:rows+=[f"R: {t['primary_value']} Ω"]
                elif code==13:rows+=[f"C: {t['capacitance_pf']} pF",f"ESR: {t['esr_ohm']} Ω"]
                elif code==15:rows+=[f"L: {t['inductance_uh']} µH",f"R: {t['primary_value']} Ω"]
                elif code==12:rows+=[f"V: {t['cell_voltage_v']} V"]
                elif code==16:rows+=[f"Vz: {t['voltage_v']} V"]
                elif code==10:rows+=[f"Vf: {t['voltage_v']} V",f"C: {t['capacitance_pf']} pF",f"Ir: {t['diode_leakage_a']} A"]
                elif code in (4,5):rows+=[f"hFE: {t['gain']}",f"Vbe: {t['vbe_v']} V",f"Ic: {t['collector_ma']} mA"]
                else:rows+=[self.tr('Ayrıntılı eleman değerleri cihaz ekranında.')]
            hint=self.tr('Elemanı 1-2-3 soketine bağlayın. OK / Test ölçümü başlatır.')
        else:rows=[self.tr('Cihazın yön ve OK tuşlarını kullanın.')]
        for i,row in enumerate(rows):
            c.create_text(32,105+i*52,text=row,anchor='nw',fill='#e6f1ff',font=('Consolas',max(12,min(23,int(w/42))),'bold'))
        c.create_text(32,h-70,text=hint,anchor='nw',fill='#91a7bd',font=('Segoe UI',11),width=max(100,w-64))
    def zoom(self,x,y,anchor=None):
        old_x,old_y=self.zoom_x,self.zoom_y
        self.zoom_x=max(1.,min(100.,old_x*x));self.zoom_y=max(1.,min(100.,old_y*y))
        if anchor and hasattr(self,'view_bounds'):
            left,top,right,bottom=self.plot_bounds
            fx=max(0.,min(1.,(anchor[0]-left)/(right-left)))-.5
            fy=.5-max(0.,min(1.,(anchor[1]-top)/(bottom-top)))
            xmin,xmax,ymin,ymax=self.view_bounds
            self.pan_x+=fx*(xmax-xmin)*(1-old_x/self.zoom_x)
            self.pan_y+=fy*(ymax-ymin)*(1-old_y/self.zoom_y)
        self.draw()
    def wheel_zoom(self,event):
        if not self.in_plot(event):return
        factor=1.25 if event.delta>0 else 1/1.25
        self.zoom(1,factor,(event.x,event.y)) if event.state&1 else self.zoom(factor,1,(event.x,event.y))
        return 'break'
    def in_plot(self,event):
        if self.metadata.get('device_mode',3)!=3 or not hasattr(self,'plot_bounds'):return False
        l,t,r,b=self.plot_bounds
        return l<=event.x<=r and t<=event.y<=b
    def begin_pan(self,event):
        self.drag_origin=(event.x,event.y,self.pan_x,self.pan_y,self.view_bounds) if self.in_plot(event) and hasattr(self,'view_bounds') else None
    def drag_pan(self,event):
        if not self.drag_origin:return
        x,y,px,py,(xmin,xmax,ymin,ymax)=self.drag_origin
        l,t,r,b=self.plot_bounds
        self.pan_x=px-(event.x-x)*(xmax-xmin)/(r-l)
        self.pan_y=py+(event.y-y)*(ymax-ymin)/(b-t)
        self.draw()
    def reset_zoom(self):
        self.zoom_x=self.zoom_y=1.;self.pan_x=self.pan_y=0.;self.draw()
    def centre_ripple(self):
        if not self.samples:return
        start=max(0,min(300,self.metadata.get('trigger_sample',0))) if self.metadata.get('measurements') else 0
        values=self.samples[start:start+300] if self.metadata.get('measurements') else self.samples
        centre=sum(values)/len(values)
        if self.metadata.get('measurements'):base=self.metadata.get('offset_raw',0);span=198.
        else:
            target=max(1,(max(values)-min(values))*1.25/8);exponent=10**math.floor(math.log10(target))
            division=next(v*exponent for v in (1,2,5,10) if v*exponent>=target)
            base=round(centre/division)*division;span=division*8
        self.pan_y=centre-base;self.zoom_y=max(1.,min(100.,span/max(2.,(max(values)-min(values))*1.4)))
        self.draw()
    def draw(self):
        c=self.canvas;c.delete('all');w=max(c.winfo_width(),200);h=max(c.winfo_height(),200)
        if self.metadata.get('device_mode',1)!=3:
            self.draw_instrument();return
        yellow='#eeef35';white='#e6f1ff';muted='#91a7bd'
        font_size=max(12,min(21,int(w/47)));font=('Consolas',font_size,'bold')
        left,top,right,bottom=22,48,w-22,h-58
        self.plot_bounds=(left,top,right,bottom)
        c.create_rectangle(0,0,w,40,fill='#172433',outline='')
        c.create_rectangle(left,7,left+112,34,fill=yellow,outline='',tags='trigger_control')
        trigger=('Auto','Normal','Single')[self.metadata.get('trigger_mode',0)%3]
        c.create_text(left+56,20,text=trigger,fill='#283127',font=('Consolas',16,'bold'),tags='trigger_control')
        c.tag_bind('trigger_control','<Button-1>',lambda event:self.popup_control('trigger_mode',event))
        c.create_text(left+143,20,text='T',fill=yellow,font=('Consolas',20,'bold'))
        c.create_text(right,20,text='USB  '+self.tr(self.mode),anchor='e',fill='#85ed95' if self.mode=='RUN' else muted,font=('Consolas',13,'bold'))
        for i in range(11):
            x=left+(right-left)*i/10;c.create_line(x,top,x,bottom,fill='#8298b1' if i==5 else '#4c6077',dash=(1,6),width=1)
        for i in range(9):
            y=top+(bottom-top)*i/8;c.create_line(left,y,right,y,fill='#8298b1' if i==4 else '#4c6077',dash=(1,6),width=1)
        c.create_rectangle(left,top,right,bottom,outline='#8c9eb1')
        division=10
        device_values=self.metadata.get('measurements')
        if self.samples:
            low,high=min(self.samples),max(self.samples)
            mean=sum(self.samples)/len(self.samples);rms=math.sqrt(sum(x*x for x in self.samples)/len(self.samples))
            # Auto range in raw units, with the same eight vertical divisions as the device.
            target=max(1,(high-low)*1.25/8)
            exponent=10**math.floor(math.log10(target))
            division=next(v*exponent for v in (1,2,5,10) if v*exponent>=target)
            centre=round(mean/division)*division
            minimum=centre-division*4;maximum=centre+division*4
            plotted=self.samples
            if device_values:
                # Firmware renders 300 points from its trigger-selected window.
                # These words are already vertical display displacements, not ADC codes.
                start=max(0,min(300,self.metadata.get('trigger_sample',0)))
                plotted=self.samples[start:start+300]
                minimum=self.metadata.get('offset_raw',0)-99
                maximum=self.metadata.get('offset_raw',0)+99
            xcentre=(len(plotted)-1)/2+self.pan_x
            xspan=max(1,len(plotted)-1)/self.zoom_x
            xmin,xmax=xcentre-xspan/2,xcentre+xspan/2
            ycentre=(minimum+maximum)/2+self.pan_y
            yspan=(maximum-minimum)/self.zoom_y
            minimum,maximum=ycentre-yspan/2,ycentre+yspan/2
            self.view_bounds=(xmin,xmax,minimum,maximum)
            coordinates=[]
            for index,value in enumerate(plotted):
                if index<xmin-1 or index>xmax+1:continue
                coordinates.append((left+(right-left)*(index-xmin)/(xmax-xmin),bottom-(value-minimum)*(bottom-top)/(maximum-minimum)))
            for (x1,y1),(x2,y2) in zip(coordinates,coordinates[1:]):
                if max(x1,x2)<left or min(x1,x2)>right:continue
                if x1!=x2:
                    if x1<left:
                        y1+=(y2-y1)*(left-x1)/(x2-x1);x1=left
                    if x2>right:
                        y2=y1+(y2-y1)*(right-x1)/(x2-x1);x2=right
                if max(y1,y2)<top or min(y1,y2)>bottom:continue
                if y1!=y2:
                    if y1<top or y1>bottom:
                        edge=max(top,min(bottom,y1));x1=x1+(x2-x1)*(edge-y1)/(y2-y1);y1=edge
                    if y2<top or y2>bottom:
                        edge=max(top,min(bottom,y2));x2=x1+(x2-x1)*(edge-y1)/(y2-y1);y2=edge
                c.create_line(x1,y1,x2,y2,fill=yellow,width=2)
            zero_y=bottom-(0-minimum)*(bottom-top)/(maximum-minimum)
            if top<=zero_y<=bottom:
                c.create_polygon(left-13,zero_y-7,left-13,zero_y+7,left-2,zero_y,fill=yellow)
            c.create_polygon(right+12,(top+bottom)/2-6,right+12,(top+bottom)/2+6,right+2,(top+bottom)/2,fill=yellow)
            if device_values:
                m=device_values
                first=[f'Vmax: {m["vmax"]:.2f}V',f'Vmin: {m["vmin"]:.2f}V',f'Vavg: {m["vavg"]:.2f}V',f'Vrms: {m["vrms"]:.2f}V']
                second=[f'Vpp : {m["vpp"]:.2f}V',f'Fre : {m["frequency_khz"]:.3f}KHz',f'Dut : {m["duty_percent"]:.1f}%',f'Cyc : {m["cycle_ms"]:.3f}ms']
            else:
                first=[f'Max : {high:.0f}',f'Min : {low:.0f}',f'Avg : {mean:.2f}',f'RMS : {rms:.2f}']
                second=[f'P-P : {high-low:.0f}','Fre : — Hz','Dut : — %','Cyc : — ms']
        else:
            first=['Max : —','Min : —','Avg : —','RMS : —']
            second=['P-P : —','Fre : — Hz','Dut : — %','Cyc : — ms']
            c.create_text(w/2,top+(bottom-top)*0.6,text=self.tr('Cihaz verisi bekleniyor'),fill=muted,font=('Segoe UI',16))
        c.create_text(right-8,bottom-12,text=f'X ×{self.zoom_x:.2f}  Y ×{self.zoom_y:.2f}',anchor='se',fill=muted,font=('Consolas',10))
        # Measurements overlay the grid, matching the handheld screen's two columns.
        for col,items in enumerate((first,second)):
            x=left+15+col*(right-left)*0.52
            for row,text in enumerate(items):
                c.create_text(x,top+17+row*(font_size+7),text=text,anchor='nw',fill=white,font=font)
        c.create_text(right-8,top+17+4*(font_size+7),text=self.tr('CİHAZ ÖLÇÜMÜ' if device_values else 'HAM GÖRÜNÜM'),anchor='ne',fill=muted,font=('Consolas',10))
        labels=[f'{division:g} ham/div','— X','60 örn/div','HAM',self.mode]
        if device_values:
            labels=[SCALE_LABELS[self.metadata['scale_index']],('X1','X10')[self.metadata['probe_index']],TIME_LABELS[self.metadata['timebase_index']],('AC','DC')[self.metadata['coupling_index']],self.mode]
        for index,label in enumerate(labels):
            x1=left+(right-left)*index/5;x2=left+(right-left)*(index+1)/5-4
            color='#2d58da' if index==3 else ('#8de78c' if index==4 and self.mode=='RUN' else yellow)
            tag='run' if index==4 else ('scale_index','probe_index','timebase_index','coupling_index')[index]
            c.create_rectangle(x1,bottom+9,x2,h-10,fill=color,outline='',tags=tag)
            c.create_text((x1+x2)/2,(bottom+9+h-10)/2,text=label if label in ('RUN','HOLD') else self.tr(label),fill=white if index==3 else '#213024',font=('Consolas',max(10,font_size-3),'bold'),tags=tag)
            if index<4:c.tag_bind(tag,'<Button-1>',lambda event,n=tag:self.popup_control(n,event))
        c.tag_bind('run','<Button-1>',lambda event:self.toggle_run())
    def popup_control(self,name,event):
        if self.metadata.get('protocol_version',0)<2:
            self.note.set('Bu kontrol için cihazın firmware v2 ile açılması gerekiyor.');return
        menu=tk.Menu(self.root,tearoff=False,bg='#233144',fg='#edf5ff',activebackground='#eeef35',activeforeground='#142332')
        for index,label in enumerate(self.device_controls[name]['values']):
            mark='✓ ' if self.metadata.get(name)==index else '   '
            menu.add_command(label=mark+label,command=lambda value=index:self.request_control(name,value))
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()
    def save(self):
        if not self.samples:self.status.set('Kaydedilecek cihaz verisi yok.');return
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if not path:return
        with open(path,'w',newline='',encoding='utf-8') as output:
            writer=csv.writer(output);writer.writerow(['sample_index','display_displacement'])
            writer.writerows(enumerate(self.samples))
        self.status.set('Ham örnekler kaydedildi: '+path)
    def close(self):
        if self.updating:
            messagebox.showwarning(self.tr('Firmware yükleniyor'),self.tr('Yükleme tamamlanana kadar pencereyi ve USB bağlantısını açık bırakın.'));return
        self.stop.set();self.root.destroy()

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--connect',action='store_true')
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--self-test-report',type=Path,default=Path('self-test.json'));args=parser.parse_args()
    if args.self_test:
        import hashlib
        from .updater import bundled_firmware,PATCH_SHA
        report={}
        try:
            image=bundled_firmware()
            report['firmware_sha256']=hashlib.sha256(image.read_bytes()).hexdigest()
            if report['firmware_sha256']!=PATCH_SHA:raise ValueError('Firmware hash mismatch')
            root=tk.Tk();root.withdraw();scope=Scope(root);root.update();scope.draw();scope.close()
            report.update(ok=True,tkinter=True,version='1.1.0.dev1')
        except Exception as error:report.update(ok=False,error=str(error))
        args.self_test_report.write_text(json.dumps(report,indent=2),encoding='utf-8')
        if not report['ok']:raise SystemExit(1)
        return
    root=tk.Tk();scope=Scope(root)
    root.after(250,scope.start)
    root.mainloop()


if __name__ == "__main__":
    main()
