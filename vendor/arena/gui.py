"""Small launcher for the official game UI; no alternate board renderer."""
from pathlib import Path
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import native


def main():
    root=tk.Tk();root.title('Wesnoth Native Arena');root.geometry('700x270')
    frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
    exe=tk.StringVar(value=os.environ.get('WESNOTH_EXE',''))
    bot=tk.StringVar(value=str(native.ROOT/'sdk/template_bot'))
    players=tk.StringVar(value='2')
    def select_exe():
        path=filedialog.askopenfilename(title='选择 Wesnoth 1.18.8 程序')
        if path: exe.set(path)
    def select_bot():
        path=filedialog.askdirectory(title='选择选手附加组件目录')
        if path: bot.set(path)
    for row,label,value,command in [(0,'Wesnoth 程序',exe,select_exe),(1,'选手附加组件',bot,select_bot)]:
        ttk.Label(frame,text=label).grid(row=row,column=0,sticky='w',pady=7)
        ttk.Entry(frame,textvariable=value,width=62).grid(row=row,column=1,sticky='ew',padx=8)
        ttk.Button(frame,text='选择',command=command).grid(row=row,column=2)
    ttk.Label(frame,text='参战人数').grid(row=2,column=0,sticky='w',pady=7)
    ttk.Combobox(frame,textvariable=players,values=('2','4','8'),state='readonly',width=8).grid(row=2,column=1,sticky='w',padx=8)
    def launch(arguments):
        try:
            selected=native.find_wesnoth(exe.get() or None)
            logs=native.ROOT/'replays';logs.mkdir(exist_ok=True)
            with (logs/'launcher.log').open('a',encoding='utf-8') as log:
                subprocess.Popen([sys.executable,str(native.ROOT/'arena.py'),*arguments,'--wesnoth',selected],
                    cwd=native.ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=native.creationflags())
        except (OSError,ValueError) as exc: messagebox.showerror('启动失败',str(exc))
    def open_replay():
        path=filedialog.askopenfilename(title='选择原版回放',filetypes=[('Wesnoth replay','*.gz *.bz2 *.save'),('All files','*')])
        if path: launch(['replay',path])
    buttons=ttk.Frame(frame);buttons.grid(row=3,column=0,columnspan=3,sticky='w',pady=18)
    ttk.Button(buttons,text='我对战选手 AI',command=lambda:launch(['play',bot.get(),'--players',players.get()])).pack(side='left',padx=5)
    ttk.Button(buttons,text='打开原版回放',command=open_replay).pack(side='left',padx=5)
    ttk.Label(frame,text='人类默认第 1 方，选手第 2 方，其余为官方 AI。日志：replays/launcher.log').grid(row=4,column=0,columnspan=3,sticky='w')
    frame.columnconfigure(1,weight=1)
    root.mainloop()


if __name__=='__main__': main()
