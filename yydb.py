import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import platform
import hashlib
import json
import time
import pygame
import librosa
import librosa.display
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mutagen import File as MutagenFile
from datetime import datetime
from PIL import Image, ImageTk
import io
from scipy.stats import kurtosis, skew
import soundfile as sf
from concurrent.futures import ThreadPoolExecutor

def get_system_theme():
    try:
        if platform.system() == 'Windows':
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize") as key:
                value = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
                return 'light' if value == 1 else 'dark'
        elif platform.system() == 'Darwin':
            import subprocess
            out = subprocess.check_output(["defaults", "read", "-g", "AppleInterfaceStyle"])
            return 'dark' if b'Dark' in out else 'light'
    except:
        return 'light'

def hash_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

class AudioAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.file_path = None
        self.y = None
        self.sr = None
        self.duration = 0
        self.playing = False
        self.paused = False
        self.score = 0
        self.score_detail = {}
        self.root.title("🎵 YYDB 音频分析器")
        self.root.geometry("950x770")
        self.root.resizable(False, False)
        self.theme = get_system_theme()
        self.setup_style()
        self.init_pygame()
        self.build_layout()

    def setup_style(self):
        default_font = ("Microsoft YaHei", 10)
        style = ttk.Style()
        style.theme_use('vista' if platform.system() == 'Windows' else 'clam')
        style.configure('.', font=default_font)

        # 现代配色方案
        if self.theme == 'dark':
            self.bg = '#1e1e1e'
            self.fg = '#f0f0f0'
            self.hl = '#0e639c'
            self.secondary = '#2d2d30'
            self.text_bg = '#252526'
        else:
            self.bg = '#f9f9f9'
            self.fg = '#333333'
            self.hl = '#007acc'
            self.secondary = '#e5e5e5'
            self.text_bg = '#ffffff'

        self.root.configure(bg=self.bg)

        # 强制设置主题为clam，确保按钮样式一致
        style.theme_use('clam')
        
        # 按钮统一风格 - 使用固定颜色不受主题影响
        style.configure('TButton',
            font=('Microsoft YaHei', 10, 'bold'),
            padding=10,
            background='#007acc',
            foreground='white',
            relief='flat',
            borderwidth=0,
            bordercolor='#007acc',
            focuscolor='#007acc',
            lightcolor='#007acc',
            darkcolor='#007acc')
        style.map('TButton',
            background=[('active', '#005f9e'), ('!disabled', '#007acc')],
            foreground=[('active', 'white'), ('!disabled', 'white')])

        # 播放控制按钮风格
        style.configure('Modern.TButton',
            font=('Microsoft YaHei', 10, 'bold'),
            background='#007acc',
            foreground='white',
            padding=8,
            relief='flat',
            borderwidth=0,
            bordercolor='#007acc',
            focuscolor='#007acc',
            lightcolor='#007acc',
            darkcolor='#007acc')
        style.map('Modern.TButton',
            background=[('active', '#005f9e'), ('pressed', '#005f9e')],
            foreground=[('active', 'white'), ('pressed', 'white')])

        # 导出按钮
        style.configure('Accent.TButton',
            font=('Segoe UI', 11, 'bold'),
            background='#007acc',
            foreground='white',
            padding=10,
            bordercolor='#007acc',
            focuscolor='#007acc',
            lightcolor='#007acc',
            darkcolor='#007acc')
        style.map('Accent.TButton',
            background=[('active', '#007acc'), ('!disabled', '#007acc')],
            foreground=[('active', 'white'), ('!disabled', 'white')])

        # 分析和播放进度条（统一高度）
        style.configure('Horizontal.TProgressbar',
            thickness=10,
            troughcolor=self.secondary,
            background=self.hl,
            bordercolor=self.secondary,
            lightcolor=self.hl,
            darkcolor=self.hl)

        # 拖动条（播放进度条）
        style.configure('TScale',
            troughcolor=self.secondary,
            background=self.hl,
            sliderlength=14,
            sliderthickness=12)

    def init_pygame(self):
        pygame.mixer.init()

    def build_layout(self):
        # 先清除所有子组件
        for widget in self.root.winfo_children():
            widget.destroy()
            
        top = tk.Frame(self.root, bg=self.bg)
        top.pack(fill=tk.X, padx=10, pady=10)
        
        # 强制刷新布局
        self.root.update_idletasks()

        self.select_btn = ttk.Button(top, text="选择音频", command=self.choose_file)
        self.select_btn.pack(side=tk.LEFT)

        self.analyze_btn = ttk.Button(top, text="分析", command=self.start_analysis, state=tk.DISABLED)
        self.analyze_btn.pack(side=tk.RIGHT)

        self.path_label = tk.Label(top, text="未选择文件", bg=self.bg, fg=self.fg, font=("Segoe UI", 10))
        self.path_label.pack(side=tk.LEFT, padx=10)

        # 主内容区域
        main_frame = tk.Frame(self.root, bg=self.bg)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # 左侧信息面板 (固定宽度500px，高度由子元素决定)
        left_panel = tk.Frame(main_frame, bg=self.bg, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10), pady=0)

        # 右侧面板 (宽度500px，可扩展填充剩余空间)
        right_panel = tk.Frame(main_frame, bg=self.bg, width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=0)

        left_panel.pack_propagate(False)
        right_panel.pack_propagate(False)

        # 信息显示区域 (固定高度250px)
        info_frame = tk.LabelFrame(left_panel, text="音频信息", bg=self.bg, fg=self.fg, font=("Segoe UI", 10, "bold"), height=400)
        info_frame.pack_propagate(False)  # 禁止自动调整大小
        info_frame.pack(fill=tk.X, expand=False, pady=5)
        
        self.info_text = tk.Text(info_frame, 
                               bg=self.text_bg, 
                               fg=self.fg, 
                               font=("Segoe UI", 10),
                               relief='flat',
                               padx=10,
                               pady=10,
                               wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True)

        # 评分区域 (固定高度250px)
        score_frame = tk.LabelFrame(left_panel, text="音频评分", bg=self.bg, fg=self.fg, font=("Segoe UI", 10, "bold"), height=190)
        score_frame.pack_propagate(False)  # 禁止自动调整大小
        score_frame.pack(fill=tk.BOTH, expand=False, pady=5)
        
        self.score_text = tk.Text(score_frame, 
                                bg=self.text_bg, 
                                fg=self.fg, 
                                font=("Segoe UI", 10),
                                relief='flat',
                                padx=10,
                                pady=10,
                                wrap=tk.WORD)
        self.score_text.pack(fill=tk.BOTH, expand=True)

        # 频谱图区域
        spec_frame = tk.LabelFrame(right_panel, text="频谱分析", bg=self.bg, fg=self.fg, font=("Segoe UI", 10, "bold"))
        spec_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.spectrum_tab = tk.Frame(spec_frame, bg=self.bg)
        self.spectrum_tab.pack(fill=tk.BOTH, expand=True)

        # 播放控制区域
        play_frame = tk.LabelFrame(right_panel, text="播放控制", bg=self.bg, fg=self.fg, font=("Segoe UI", 10, "bold"))
        play_frame.pack(fill=tk.BOTH, expand=False)
        
        self.play_tab = tk.Frame(play_frame, bg=self.bg)
        self.play_tab.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 导出和关于按钮
        btn_frame = tk.Frame(left_panel, bg=self.bg)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.export_btn = ttk.Button(btn_frame, 
                                   text="📤 导出分析报告", 
                                   command=self.export_report,
                                   style='Accent.TButton')
        self.export_btn.pack(side=tk.LEFT, padx=5, pady=5, ipadx=20)
        
        self.about_btn = ttk.Button(btn_frame,
                                  text="ℹ️ 关于",
                                  command=self.show_about,
                                  style='Accent.TButton')
        self.about_btn.pack(side=tk.RIGHT, padx=5, pady=5, ipadx=20)
        
        # 添加样式
        style = ttk.Style()
        style.configure('Accent.TButton',
            font=('Segoe UI', 11, 'bold'),
            foreground='white',
            background=self.hl,
            padding=8)
        style.map('Accent.TButton',
            background=[('active', self.hl), ('!active', self.hl)],
            foreground=[('active', 'white'), ('!active', 'white')])

        # 播放控制区域
        control_frame = tk.Frame(self.play_tab, bg=self.bg)
        control_frame.pack(pady=(20, 10))

        # 进度条和时间显示
        progress_frame = tk.Frame(self.play_tab, bg=self.bg)
        progress_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        # 播放进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Scale(progress_frame,
            from_=0,
            to=100,
            orient='horizontal',
            variable=self.progress_var,
            command=self.seek_audio,
            style='TScale')
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        time_frame = tk.Frame(progress_frame, bg=self.bg)
        time_frame.pack(fill=tk.X)
        
        self.current_time = tk.Label(time_frame, 
                                   text="00:00", 
                                   bg=self.bg, 
                                   fg=self.fg,
                                   font=("Segoe UI", 9))
        self.current_time.pack(side=tk.LEFT)
        
        self.total_time = tk.Label(time_frame, 
                                 text="/ 00:00", 
                                 bg=self.bg, 
                                 fg=self.fg,
                                 font=("Segoe UI", 9))
        self.total_time.pack(side=tk.RIGHT)

        # 控制按钮
        btn_style = 'Modern.TButton'
        self.play_btn = ttk.Button(control_frame, text="▶ 播放", command=self.play_audio, style=btn_style)
        self.pause_btn = ttk.Button(control_frame, text="⏸ 暂停", command=self.pause_audio, style=btn_style)
        self.resume_btn = ttk.Button(control_frame, text="↻ 恢复", command=self.resume_audio, style=btn_style)
        self.stop_btn = ttk.Button(control_frame, text="⏹ 停止", command=self.stop_audio, style=btn_style)

        self.play_btn.grid(row=0, column=0, padx=6, ipadx=10)
        self.pause_btn.grid(row=0, column=1, padx=6, ipadx=10)
        self.resume_btn.grid(row=0, column=2, padx=6, ipadx=10)
        self.stop_btn.grid(row=0, column=3, padx=6, ipadx=10)

        
        # 调整控制区域宽度
        control_frame.config(width=600)
        
        # 调整控制区域大小
        control_frame.pack(pady=10, padx=10)
        
        # 底部状态栏
        status_frame = tk.Frame(self.root, bg=self.secondary, height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 5))

        # 整体分析进度条
        self.overall_progress = ttk.Progressbar(status_frame,
            length=300,
            mode='determinate',
            style='Horizontal.TProgressbar')
        self.overall_progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=5)

        # 用时标签
        self.time_label = tk.Label(status_frame,
            text="用时: 0.00秒",
            bg=self.secondary,
            fg=self.fg,
            font=("Segoe UI", 9))
        self.time_label.pack(side=tk.RIGHT, padx=10)

        # 状态文字
        self.status_label = tk.Label(status_frame,
            text="就绪",
            bg=self.secondary,
            fg=self.fg,
            font=("Segoe UI", 9))
        self.status_label.pack(side=tk.RIGHT, padx=10)

    def choose_file(self):
        path = filedialog.askopenfilename(filetypes=[("音频文件", "*.mp3 *.flac *.wav *.m4a *.ape *.dsf *.dsd *.dff *.aac *.ogg *.opus *.wma *.aiff *.aif *.au *.raw *.pcm *.caf *.tta *.wv")])
        if path:
            self.file_path = path
            self.path_label.config(text=os.path.basename(path))
            self.analyze_btn.config(state=tk.NORMAL)
            self.reset_player()

    def reset_player(self):
        pygame.mixer.music.stop()
        self.playing = False
        self.paused = False
        self.progress_var.set(0)
        self.current_time.config(text="00:00")
        self.total_time.config(text="/ 00:00")

    def play_audio(self):
        if not self.file_path:
            return
        pygame.mixer.music.load(self.file_path)
        pygame.mixer.music.play()
        self.playing = True
        self.paused = False
        threading.Thread(target=self.track_progress, daemon=True).start()

    def pause_audio(self):
        if self.playing:
            pygame.mixer.music.pause()
            self.paused = True

    def resume_audio(self):
        if self.paused:
            pygame.mixer.music.unpause()
            self.paused = False

    def stop_audio(self):
        pygame.mixer.music.stop()
        self.playing = False
        self.paused = False
        self.progress_var.set(0)
        self.current_time.config(text="00:00")
        self.total_time.config(text="/ 00:00")

    def seek_audio(self, val):
        if self.y is None or self.sr is None or self.duration <= 0:
            return
            
        try:
            # 确保值在0-100范围内
            pos = max(0, min(100, float(val)))
            seek_time = (pos / 100.0) * self.duration
            
            # 计算开始采样点
            start_sample = int(seek_time * self.sr)
            if start_sample >= len(self.y):
                return
                
            # 创建临时文件
            temp_dir = os.path.join(os.path.dirname(self.file_path), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"seek_temp_{time.time()}.wav")
            
            # 使用soundfile替代librosa.output.write_wav
            import soundfile as sf
            sf.write(temp_path, self.y[start_sample:], self.sr)
            
            # 停止当前播放并加载新位置
            pygame.mixer.music.stop()
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            
            # 更新播放状态
            self.playing = True
            self.paused = False
            
            # 删除旧临时文件
            for f in os.listdir(temp_dir):
                if f.startswith("seek_temp_") and f.endswith(".wav"):
                    try:
                        os.remove(os.path.join(temp_dir, f))
                    except:
                        pass
                        
        except Exception as e:
            print(f"跳转播放出错：{str(e)}")
            self.status_label.config(text=f"跳转出错：{str(e)}")

    def track_progress(self):
        while self.playing:
            if not self.paused:
                elapsed = pygame.mixer.music.get_pos() / 1000.0
                try:
                    percent = (elapsed / self.duration) * 100
                    self.progress_var.set(percent)
                    self.current_time.config(text=self.format_time(elapsed))
                    self.total_time.config(text=f"/ {self.format_time(self.duration)}")
                except:
                    pass
            time.sleep(0.5)

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02}:{seconds:02}"

    def start_analysis(self):
        threading.Thread(target=self.analyze_file, daemon=True).start()

    def analyze_file(self):
        self.analysis_start_time = time.time()
        self.analysis_running = True
        self.timer_thread = threading.Thread(target=self.update_timer, daemon=True)
        self.timer_thread.start()
        self.status_label.config(text="开始分析...")
        self.time_label.config(text="用时: 0.00秒")
        self.overall_progress['value'] = 0
        self.overall_progress.update()

        if not self.file_path:
            return

        self.info_text.delete(1.0, tk.END)
        self.score_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, f"文件: {self.file_path}\n")

        # 基本信息
        size_mb = round(os.path.getsize(self.file_path)/(1024*1024), 2)
        self.info_text.insert(tk.END, f"大小: {size_mb} MB\n")

        self.status_label.config(text="加载音频文件...")
        self.y, self.sr = librosa.load(self.file_path, sr=None, mono=True, duration=60.0)
        # 添加这一行，完整音频用于频谱图绘制
        self.y_full, _ = librosa.load(self.file_path, sr=None, mono=True)
        self.duration = sf.info(self.file_path).duration
        self.info_text.insert(tk.END, f"采样率: {self.sr} Hz\n")
        self.info_text.insert(tk.END, f"时长: {self.format_time(self.duration)}\n")
        self.overall_progress['value'] = 10
        self.overall_progress.update()

        self.status_label.config(text="提取音频特征...")
        with ThreadPoolExecutor() as executor:
            rms_future = executor.submit(librosa.feature.rms, y=self.y)
            zcr_future = executor.submit(librosa.feature.zero_crossing_rate, y=self.y)
            pitch_future = executor.submit(librosa.piptrack, y=self.y, sr=self.sr)
            spec_centroid_future = executor.submit(librosa.feature.spectral_centroid, y=self.y, sr=self.sr)
            spec_bw_future = executor.submit(librosa.feature.spectral_bandwidth, y=self.y, sr=self.sr)
            onset_env = librosa.onset.onset_strength(y=self.y, sr=self.sr)
            tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=self.sr)[0]

            rms_all = rms_future.result()[0]
            rms = np.mean(rms_all)
            peak = np.max(np.abs(self.y))
            loudness_db = 20 * np.log10(rms + 1e-9)
            dynamic_range = 20 * np.log10((peak + 1e-9) / (rms + 1e-9))
            self.info_text.insert(tk.END, f"响度: {loudness_db:.2f} dB\n")
            self.info_text.insert(tk.END, f"动态范围: {dynamic_range:.2f} dB\n")

            silent_ratio = np.mean(np.abs(self.y) < 1e-4)
            self.info_text.insert(tk.END, f"静音比例: {silent_ratio:.2%}\n")

            spec_centroid = spec_centroid_future.result().mean()
            self.info_text.insert(tk.END, f"频谱中心: {spec_centroid:.1f} Hz\n")
            spec_bw = spec_bw_future.result().mean()
            self.info_text.insert(tk.END, f"频谱带宽: {spec_bw:.1f} Hz\n")
            self.info_text.insert(tk.END, f"节拍: {tempo:.1f} BPM\n")

            zero_crossings = zcr_future.result()[0].mean()
            self.info_text.insert(tk.END, f"过零率: {zero_crossings:.4f}\n")

            pitches, magnitudes = pitch_future.result()
            pitch_values = pitches[magnitudes > np.median(magnitudes)]
            pitch_mean = pitch_values.mean() if len(pitch_values) > 0 else 0
            self.info_text.insert(tk.END, f"基频: {pitch_mean:.1f} Hz\n")

        self.overall_progress['value'] = 50
        self.overall_progress.update()

        self.status_label.config(text="计算码率与压缩率...")
        size_bytes = os.path.getsize(self.file_path)
        bitrate = (size_bytes * 8) / self.duration / 1000
        compression_ratio = size_bytes / (self.duration * self.sr * 2)
        file_hash = hashlib.md5(open(self.file_path, 'rb').read()).hexdigest()
        self.info_text.insert(tk.END, f"估算比特率: {bitrate:.1f} kbps\n")
        self.info_text.insert(tk.END, f"压缩率: {compression_ratio:.2f}\n")
        self.info_text.insert(tk.END, f"文件哈希: \n{file_hash}\n")
        self.overall_progress['value'] = 60
        self.overall_progress.update()

        self.status_label.config(text="评分分析...")
        self.score_detail = {
            "比特率": 20 if bitrate > 256 else 10,
            "动态范围": 20 if dynamic_range > 12 else 10,
            "编码质量": 20 if bitrate > 256 else 10,
            "响度与动态": 20 if loudness_db > -18 and dynamic_range > 12 else 10,
            "结构完整性": 20 if spec_bw > 1000 else 10
        }
        self.score = sum(self.score_detail.values())
        self.overall_progress['value'] = 70
        self.overall_progress.update()

        self.status_label.config(text="统计信号特征...")
        symmetry = np.mean(self.y[self.y > 0]) - np.mean(self.y[self.y < 0])
        energy_std = np.std(rms_all)
        kurt = kurtosis(self.y)
        skw = skew(self.y)
        self.info_text.insert(tk.END, f"能量变化率: {energy_std:.4f}\n")
        self.info_text.insert(tk.END, f"信号对称性: {symmetry:.4f}\n")
        self.info_text.insert(tk.END, f"峰度（kurtosis）: {kurt:.4f}\n")
        self.info_text.insert(tk.END, f"偏度（skew）: {skw:.4f}\n")
        self.overall_progress['value'] = 80
        self.overall_progress.update()

        self.score_text.insert(tk.END, f"综合评分：{self.score}/100\n\n")
        for k, v in self.score_detail.items():
            self.score_text.insert(tk.END, f"{k}: {v}/20\n")

        self.draw_spectrum()

    def draw_spectrum(self):
        if self.y is None or self.sr is None:
            return

        def _plot():
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import librosa.display
            D = librosa.amplitude_to_db(
                np.abs(librosa.stft(self.y_full, n_fft=1024, hop_length=1024)), ref=np.max)

            fig = plt.figure(facecolor=self.text_bg)
            ax = fig.add_subplot(111)
            librosa.display.specshow(D, sr=self.sr, x_axis='time', y_axis='log', cmap='magma', ax=ax)
            fig.tight_layout(pad=0.2)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, dpi='figure')
            plt.close(fig)
            buf.seek(0)
            pil_image = Image.open(buf)
            img_width = self.spectrum_tab.winfo_width() - 20
            if img_width > 0:
                pil_image = pil_image.resize((img_width, int(pil_image.height * img_width / pil_image.width)))
            img_tk = ImageTk.PhotoImage(pil_image)

            def _display():
                for child in self.spectrum_tab.winfo_children():
                    child.destroy()
                label = tk.Label(self.spectrum_tab, image=img_tk, bg=self.bg, anchor='center')
                label.image = img_tk
                label.pack(fill=tk.BOTH, expand=True)
                self.analysis_running = False
                self.timer_thread.join()
                self.overall_progress['value'] = 100
                self.status_label.config(text="分析完成")

            self.root.after(0, _display)

        threading.Thread(target=_plot, daemon=True).start()

        
    def show_about(self):
        about_win = tk.Toplevel(self.root)
        about_win.title("关于 YYDB 音频分析器")
        about_win.geometry("500x300")
        about_win.resizable(False, False)
        about_win.configure(bg=self.bg)
        
        # 标题
        title = tk.Label(about_win, 
                       text="YYDB 音频分析器", 
                       font=("Microsoft YaHei", 14, "bold"),
                       bg=self.bg,
                       fg=self.fg)
        title.pack(pady=10)
        
        # 版本信息
        version = tk.Label(about_win,
                          text="版本: 3.0.0",
                          font=("Microsoft YaHei", 10),
                          bg=self.bg,
                          fg=self.fg)
        version.pack()
        
        # 作者信息
        author = tk.Label(about_win,
                         text="作者: sumingyd & Deepseek",
                         font=("Microsoft YaHei", 10),
                         bg=self.bg,
                         fg=self.fg)
        author.pack(pady=5)
        
        # GitHub链接（可点击和复制）
        github_frame = tk.Frame(about_win, bg=self.bg)
        github_frame.pack()
        
        tk.Label(github_frame, 
                text="GitHub: ", 
                bg=self.bg,
                fg=self.fg).pack(side=tk.LEFT)
        
        github_link = tk.Text(github_frame,
                            height=1,
                            width=40,
                            font=("Microsoft YaHei", 10),
                            bg=self.text_bg,
                            fg="#0066cc",
                            relief="flat",
                            padx=2,
                            pady=2,
                            wrap=tk.NONE)
        github_link.insert("1.0", "https://github.com/sumingyd/YYDBAnalyzer")
        github_link.config(state="disabled")
        github_link.pack(side=tk.LEFT)
        
        # 添加点击事件
        def open_github(event):
            import webbrowser
            webbrowser.open("https://github.com/sumingyd/YYDBAnalyzer")
            
        github_link.tag_add("link", "1.0", "end")
        github_link.tag_config("link", foreground="#0066cc", underline=True)
        github_link.tag_bind("link", "<Button-1>", open_github)
        
        # 描述文本
        desc = tk.Label(about_win,
                       text="一个专业的音频分析工具，提供频谱分析、\n音频质量评分和详细报告导出功能。",
                       font=("Microsoft YaHei", 10),
                       bg=self.bg,
                       fg=self.fg)
        desc.pack(pady=15)
        
        # 关闭按钮
        close_btn = ttk.Button(about_win,
                             text="关闭",
                             command=about_win.destroy,
                             style='Accent.TButton')
        close_btn.pack(pady=10)

    def update_timer(self):
        """更新计时器显示"""
        while self.analysis_running:
            elapsed = time.time() - self.analysis_start_time
            self.time_label.config(text=f"用时: {elapsed:.2f}秒")
            time.sleep(0.1)

    def export_report(self):
        if not self.file_path or self.y is None:
            messagebox.showwarning("提示", "请先分析音频。")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON 文件", "*.json")])
        if not save_path:
            return
        try:
            # 收集所有分析数据
            report = {
                "文件信息": {
                    "路径": self.file_path,
                    "文件名": os.path.basename(self.file_path),
                    "大小(MB)": round(os.path.getsize(self.file_path)/(1024*1024), 2),
                    "哈希": hash_file(self.file_path),
                    "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "音频特征": {
                    "时长(秒)": round(self.duration, 2),
                    "采样率(Hz)": self.sr,
                    "比特率(kbps)": round((os.path.getsize(self.file_path)*8)/self.duration/1000, 1),
                    "响度(dB)": round(20*np.log10(np.sqrt(np.mean(self.y**2))+1e-9), 2),
                    "动态范围(dB)": round(20*np.log10((np.max(np.abs(self.y))+1e-9)/(np.sqrt(np.mean(self.y**2))+1e-9)), 2),
                    "频谱中心(Hz)": round(librosa.feature.spectral_centroid(y=self.y, sr=self.sr).mean(), 1),
                    "频谱带宽(Hz)": round(librosa.feature.spectral_bandwidth(y=self.y, sr=self.sr).mean(), 1),
                    "节拍(BPM)": round(float(librosa.beat.tempo(y=self.y, sr=self.sr)[0]), 1),
                    "静音比例": round(np.mean(np.abs(self.y) < 1e-4), 4)
                },
                "评分结果": {
                    "综合评分": self.score,
                    "评分明细": self.score_detail,
                    "评分标准": {
                        "比特率": ">256kbps得20分，否则10分",
                        "动态范围": ">12dB得20分，否则10分", 
                        "编码质量": "基于比特率评分",
                        "响度与动态": "响度>-18dB且动态>12dB得20分，否则10分",
                        "结构完整性": "频谱带宽>1000Hz得20分，否则10分"
                    }
                },
                "高级统计": {
                    "能量变化率": round(np.std(librosa.feature.rms(y=self.y)), 4),
                    "信号对称性": round(np.mean(self.y[self.y>0])-np.mean(self.y[self.y<0]), 4),
                    "峰度": round(float(kurtosis(self.y)), 4),
                    "偏度": round(float(skew(self.y)), 4)
                }
            }
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("导出成功", f"已保存到：{save_path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

if __name__ == '__main__':
    root = tk.Tk()
    app = AudioAnalyzerApp(root)
    root.mainloop()
