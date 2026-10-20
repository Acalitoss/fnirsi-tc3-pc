"""Experimental raw ADC viewer. Displays only samples returned by hardware."""
import csv,queue,threading,time,math,json,os
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog
from .driver import TC3,SCALE_LABELS,SCALE_MV,TIME_LABELS

class Scope:
    def __init__(self,root):
        self.root=root;root.title('FNIRSI DSO-TC3 — PC Osiloskop');root.geometry('1060x770');root.minsize(760,590)
        root.configure(bg='#151b23')
        self.events=queue.Queue();self.stop=threading.Event();self.thread=None
        self.commands=queue.Queue();self.device_controls={}
        self.samples=[];self.metadata={}
        self.frame_count=0;self.last_saved=0
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
        self.port=tk.StringVar(value='COM7')
        ttk.Entry(toolbar,textvariable=self.port,width=12).pack(side='left',padx=8)
        self.start_button=ttk.Button(toolbar,text='Başlat',command=self.start);self.start_button.pack(side='left',padx=4)
        ttk.Button(toolbar,text='HOLD',command=self.hold).pack(side='left',padx=4)
        ttk.Button(toolbar,text='CSV kaydet',command=self.save).pack(side='right')
        self.canvas=tk.Canvas(root,bg='#101923',highlightthickness=2,highlightbackground='#536273');self.canvas.pack(fill='both',expand=True,padx=20,pady=(0,8))
        self.status=tk.StringVar(value='Cihazdan henüz örnek alınmadı.')
        ttk.Label(root,textvariable=self.status,padding=(20,5)).pack(fill='x')
        settings=ttk.Frame(root,padding=(20,6));settings.pack(fill='x')
        specs=[('scale_index','V/div',SCALE_LABELS),('probe_index','Prob',('X1','X10')),('timebase_index','Zaman/div',TIME_LABELS),('coupling_index','Bağlantı',('AC','DC')),('trigger_mode','Tetik',('Auto','Normal','Single'))]
        for name,label,values in specs:
            ttk.Label(settings,text=label).pack(side='left',padx=(0,4))
            combo=ttk.Combobox(settings,values=values,width=8,state='disabled');combo.pack(side='left',padx=(0,10))
            combo.bind('<<ComboboxSelected>>',lambda event,n=name,c=combo:self.request_control(n,c.current()))
            self.device_controls[name]=combo
        self.note=tk.StringVar(value='Firmware v2 bekleniyor · Voltaj ölçümleri ve cihaz kontrolü henüz etkin değil.')
        ttk.Label(root,textvariable=self.note,padding=(20,5),font=('Segoe UI',9)).pack(fill='x',pady=(0,8))
        self.canvas.bind('<Configure>',lambda event:self.draw())
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(50,self.poll)
    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stop.clear();self.mode='RUN';self.start_button.configure(state='disabled')
        port=self.port.get().strip();self.status.set('Deneysel firmware bağlantısı kontrol ediliyor…')
        def work():
            try:
                with TC3(port) as device:
                    device.read_metadata() # Must match signature before sample command 0x20.
                    while not self.stop.is_set():
                        try:
                            while True:
                                name,value=self.commands.get_nowait()
                                try:
                                    result=device.set_control(name,value)
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
                    if self.metadata.get('protocol_version')==2:
                        self.mode='HOLD' if self.metadata.get('device_hold') else 'RUN'
                        for name,combo in self.device_controls.items():
                            combo.configure(state='readonly')
                            index=self.metadata.get(name,-1)
                            if 0<=index<len(combo['values']):combo.current(index)
                        self.note.set('Cihazın hesapladığı voltajlar · Ayarlar cihazdan geri okunur · Güç kaynağını kontrol etmez.')
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
                elif kind=='setting':self.metadata=value;self.note.set('Ayar cihazdan geri okunarak doğrulandı.');self.draw()
                elif kind=='stopped':
                    self.start_button.configure(state='normal')
                    if self.mode=='RUN':self.mode='HOLD'
                    self.draw()
        except queue.Empty:pass
        self.root.after(50,self.poll)
    def hold(self):
        self.stop.set();self.mode='HOLD';self.status.set('HOLD · Son PC karesi donduruldu.');self.draw()
    def toggle_run(self):
        if self.metadata.get('protocol_version')==2:self.request_control('device_hold',not self.metadata.get('device_hold',False))
        elif self.mode=='RUN':self.hold()
        else:self.start()
    def request_control(self,name,value):
        if self.metadata.get('protocol_version')!=2:
            self.note.set('Bu kontrol için firmware v2 yüklenmeli.');return
        self.commands.put((name,value));self.note.set('Ayar cihaza gönderiliyor; geri okuma bekleniyor…')
    def draw(self):
        c=self.canvas;c.delete('all');w=max(c.winfo_width(),200);h=max(c.winfo_height(),200)
        yellow='#eeef35';white='#e6f1ff';muted='#91a7bd'
        font_size=max(12,min(21,int(w/47)));font=('Consolas',font_size,'bold')
        left,top,right,bottom=22,48,w-22,h-58
        c.create_rectangle(0,0,w,40,fill='#172433',outline='')
        c.create_rectangle(left,7,left+112,34,fill=yellow,outline='',tags='trigger_control')
        trigger=('Auto','Normal','Single')[self.metadata.get('trigger_mode',0)%3]
        c.create_text(left+56,20,text=trigger,fill='#283127',font=('Consolas',16,'bold'),tags='trigger_control')
        c.tag_bind('trigger_control','<Button-1>',lambda event:self.popup_control('trigger_mode',event))
        c.create_text(left+143,20,text='T',fill=yellow,font=('Consolas',20,'bold'))
        c.create_text(right,20,text='USB  '+self.mode,anchor='e',fill='#85ed95' if self.mode=='RUN' else muted,font=('Consolas',13,'bold'))
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
            coordinates=[]
            for index,value in enumerate(plotted):
                coordinates.append((left+(right-left)*index/max(1,len(plotted)-1),bottom-(value-minimum)*(bottom-top)/(maximum-minimum)))
            for (x1,y1),(x2,y2) in zip(coordinates,coordinates[1:]):
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
            c.create_text(w/2,top+(bottom-top)*0.6,text='Cihaz verisi bekleniyor',fill=muted,font=('Segoe UI',16))
        # Measurements overlay the grid, matching the handheld screen's two columns.
        for col,items in enumerate((first,second)):
            x=left+15+col*(right-left)*0.52
            for row,text in enumerate(items):
                c.create_text(x,top+17+row*(font_size+7),text=text,anchor='nw',fill=white,font=font)
        c.create_text(right-8,top+17+4*(font_size+7),text='CİHAZ ÖLÇÜMÜ' if device_values else 'HAM GÖRÜNÜM',anchor='ne',fill=muted,font=('Consolas',10))
        labels=[f'{division:g} ham/div','— X','60 örn/div','HAM',self.mode]
        if device_values:
            labels=[SCALE_LABELS[self.metadata['scale_index']],('X1','X10')[self.metadata['probe_index']],TIME_LABELS[self.metadata['timebase_index']],('AC','DC')[self.metadata['coupling_index']],self.mode]
        for index,label in enumerate(labels):
            x1=left+(right-left)*index/5;x2=left+(right-left)*(index+1)/5-4
            color='#2d58da' if index==3 else ('#8de78c' if index==4 and self.mode=='RUN' else yellow)
            tag='run' if index==4 else ('scale_index','probe_index','timebase_index','coupling_index')[index]
            c.create_rectangle(x1,bottom+9,x2,h-10,fill=color,outline='',tags=tag)
            c.create_text((x1+x2)/2,(bottom+9+h-10)/2,text=label,fill=white if index==3 else '#213024',font=('Consolas',max(10,font_size-3),'bold'),tags=tag)
            if index<4:c.tag_bind(tag,'<Button-1>',lambda event,n=tag:self.popup_control(n,event))
        c.tag_bind('run','<Button-1>',lambda event:self.toggle_run())
    def popup_control(self,name,event):
        if self.metadata.get('protocol_version')!=2:
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
    def close(self):self.stop.set();self.root.destroy()

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--connect',action='store_true');args=parser.parse_args()
    root=tk.Tk();scope=Scope(root)
    if args.connect:root.after(250,scope.start)
    root.mainloop()


if __name__ == "__main__":
    main()
