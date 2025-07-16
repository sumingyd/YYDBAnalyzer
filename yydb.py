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
        self.root.geometry("1200x800")
        self.theme = get_system_theme()
        self.setup_style()
        self.init_pygame()
        self.build_layout()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use('clam')
        self.bg = '#1e1e1e' if self.theme == 'dark' else '#ffffff'
        self.fg = '#eeeeee' if self.theme == 'dark' else '#222222'
        self.hl = '#3a91e0'
        self.root.configure(bg=self.bg)
        style.configure('TButton', font=('Segoe UI', 11), padding=6)
        style.configure('TNotebook', tabposition='n', font=('Segoe UI', 11))
        style.configure('TNotebook.Tab', padding=[10, 6], font=('Segoe UI', 10, 'bold'))

    def init_pygame(self):
        pygame.mixer.init()

    def build_layout(self):
        top = tk.Frame(self.root, bg=self.bg)
        top.pack(fill=tk.X, padx=10, pady=10)

        self.select_btn = ttk.Button(top, text="选择音频", command=self.choose_file)
        self.select_btn.pack(side=tk.LEFT)

        self.analyze_btn = ttk.Button(top, text="分析", command=self.start_analysis, state=tk.DISABLED)
        self.analyze_btn.pack(side=tk.RIGHT)

        self.path_label = tk.Label(top, text="未选择文件", bg=self.bg, fg=self.fg)
        self.path_label.pack(side=tk.LEFT, padx=10)

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill=tk.BOTH, expand=True)

        self.info_tab = tk.Frame(self.tabs, bg=self.bg)
        self.score_tab = tk.Frame(self.tabs, bg=self.bg)
        self.spectrum_tab = tk.Frame(self.tabs, bg=self.bg)
        self.play_tab = tk.Frame(self.tabs, bg=self.bg)

        self.tabs.add(self.info_tab, text="基本信息")
        self.tabs.add(self.score_tab, text="评分")
        self.tabs.add(self.spectrum_tab, text="频谱图")
        self.tabs.add(self.play_tab, text="播放")

        self.info_text = tk.Text(self.info_tab, bg=self.bg, fg=self.fg, font=("Consolas", 10))
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.score_text = tk.Text(self.score_tab, bg=self.bg, fg=self.fg, font=("Consolas", 11))
        self.score_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.export_btn = ttk.Button(self.info_tab, text="📤 导出分析报告", command=self.export_report)
        self.export_btn.pack(pady=10)

        # 播放控制
        control_frame = tk.Frame(self.play_tab, bg=self.bg)
        control_frame.pack(pady=20)

        self.play_btn = ttk.Button(control_frame, text="▶️ 播放", command=self.play_audio)
        self.pause_btn = ttk.Button(control_frame, text="⏸ 暂停", command=self.pause_audio)
        self.resume_btn = ttk.Button(control_frame, text="🔄 恢复", command=self.resume_audio)
        self.stop_btn = ttk.Button(control_frame, text="⏹ 停止", command=self.stop_audio)

        self.play_btn.grid(row=0, column=0, padx=10)
        self.pause_btn.grid(row=0, column=1, padx=10)
        self.resume_btn.grid(row=0, column=2, padx=10)
        self.stop_btn.grid(row=0, column=3, padx=10)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Scale(self.play_tab, from_=0, to=100, orient="horizontal", variable=self.progress_var, command=self.seek_audio)
        self.progress_bar.pack(fill=tk.X, padx=20)

        self.time_label = tk.Label(self.play_tab, text="00:00 / 00:00", bg=self.bg, fg=self.fg)
        self.time_label.pack(pady=5)
        
        self.analyze_progress = ttk.Progressbar(self.root, length=300, mode='determinate')
        self.analyze_progress.pack(pady=8)


    def choose_file(self):
        path = filedialog.askopenfilename(filetypes=[("音频文件", "*.mp3 *.flac *.wav *.m4a *.ape")])
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
        self.time_label.config(text="00:00 / 00:00")

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
        self.time_label.config(text="00:00 / 00:00")

    def seek_audio(self, val):
        if not self.y or not self.sr or self.duration <= 0:
            return
        try:
            pos = float(val)
            seek_time = (pos / 100.0) * self.duration
            start_sample = int(seek_time * self.sr)
            y_seek = self.y[start_sample:]
            temp_path = "_seek_temp.wav"
            librosa.output.write_wav(temp_path, y_seek, self.sr)
            pygame.mixer.music.stop()
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            self.playing = True
            self.paused = False
        except Exception as e:
            print("跳转播放出错：", e)

    def track_progress(self):
        while self.playing:
            if not self.paused:
                elapsed = pygame.mixer.music.get_pos() / 1000.0
                try:
                    percent = (elapsed / self.duration) * 100
                    self.progress_var.set(percent)
                    self.time_label.config(text=f"{self.format_time(elapsed)} / {self.format_time(self.duration)}")
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
        self.analyze_progress['value'] = 0
        self.analyze_progress.update()

        if not self.file_path:
            return

        self.info_text.delete(1.0, tk.END)
        self.score_text.delete(1.0, tk.END)

        self.info_text.insert(tk.END, f"文件: {self.file_path}\n")

        self.y, self.sr = librosa.load(self.file_path, sr=None, mono=True)
        self.duration = librosa.get_duration(y=self.y, sr=self.sr)

        rms = np.sqrt(np.mean(self.y ** 2))
        peak = np.max(np.abs(self.y))
        loudness_db = 20 * np.log10(rms + 1e-9)
        dynamic_range = 20 * np.log10((peak + 1e-9) / (rms + 1e-9))
        silent_ratio = np.mean(np.abs(self.y) < 1e-4)
        spec_centroid = librosa.feature.spectral_centroid(y=self.y, sr=self.sr).mean()
        spec_bw = librosa.feature.spectral_bandwidth(y=self.y, sr=self.sr).mean()
        tempo = float(librosa.beat.tempo(y=self.y, sr=self.sr)[0])
        zero_crossings = librosa.feature.zero_crossing_rate(y=self.y).mean()

        try:
            pitches, magnitudes = librosa.piptrack(y=self.y, sr=self.sr)
            pitch_values = pitches[magnitudes > np.median(magnitudes)]
            pitch_mean = pitch_values.mean() if len(pitch_values) > 0 else 0
        except:
            pitch_mean = 0

        size_bytes = os.path.getsize(self.file_path)
        bitrate = (size_bytes * 8) / self.duration / 1000
        compression_ratio = size_bytes / (self.duration * self.sr * 2)

        file_hash = hash_file(self.file_path)

        self.score_detail = {
            "比特率": 20 if bitrate > 256 else 10,
            "动态范围": 20 if dynamic_range > 12 else 10,
            "编码质量": 20 if bitrate > 256 else 10,
            "响度与动态": 20 if loudness_db > -18 and dynamic_range > 12 else 10,
            "结构完整性": 20 if spec_bw > 1000 else 10
        }
        self.score = sum(self.score_detail.values())

        from scipy.stats import kurtosis, skew

        symmetry = np.mean(self.y[self.y > 0]) - np.mean(self.y[self.y < 0])
        energy_std = np.std(librosa.feature.rms(y=self.y))
        kurt = kurtosis(self.y)
        skw = skew(self.y)

        self.info_text.insert(tk.END, f"时长: {self.format_time(self.duration)}\n")
        self.info_text.insert(tk.END, f"采样率: {self.sr} Hz\n")
        self.info_text.insert(tk.END, f"响度: {loudness_db:.2f} dB\n")
        self.info_text.insert(tk.END, f"动态范围: {dynamic_range:.2f} dB\n")
        self.info_text.insert(tk.END, f"静音比例: {silent_ratio:.2%}\n")
        self.info_text.insert(tk.END, f"频谱中心: {spec_centroid:.1f} Hz\n")
        self.info_text.insert(tk.END, f"频谱带宽: {spec_bw:.1f} Hz\n")
        self.info_text.insert(tk.END, f"节拍: {tempo:.1f} BPM\n")
        self.info_text.insert(tk.END, f"基频: {pitch_mean:.1f} Hz\n")
        self.info_text.insert(tk.END, f"过零率: {zero_crossings:.4f}\n")
        self.info_text.insert(tk.END, f"估算比特率: {bitrate:.1f} kbps\n")
        self.info_text.insert(tk.END, f"压缩率: {compression_ratio:.2f}\n")
        self.info_text.insert(tk.END, f"文件哈希: {file_hash}\n")
        self.info_text.insert(tk.END, f"能量变化率: {energy_std:.4f}\n")
        self.info_text.insert(tk.END, f"信号对称性: {symmetry:.4f}\n")
        self.info_text.insert(tk.END, f"峰度（kurtosis）: {kurt:.4f}\n")
        self.info_text.insert(tk.END, f"偏度（skew）: {skw:.4f}\n")

        self.score_text.insert(tk.END, f"综合评分：{self.score}/100\n\n")
        for k, v in self.score_detail.items():
            self.score_text.insert(tk.END, f"{k}: {v}/20\n")

        threading.Thread(target=self.draw_spectrum, daemon=True).start()

        self.analyze_progress['value'] = 100
        self.analyze_progress.update()
        
    def draw_spectrum(self):
        if self.y is None or self.sr is None:
            return
        D = librosa.amplitude_to_db(np.abs(librosa.stft(self.y, n_fft=2048, hop_length=512)), ref=np.max)
        fig = plt.figure(figsize=(10, 4), dpi=100)
        ax = fig.add_subplot(1, 1, 1)
        img = librosa.display.specshow(D, sr=self.sr, x_axis='time', y_axis='log', cmap='inferno', ax=ax)
        ax.set_title('频谱图（Spek 风格）')
        fig.colorbar(img, ax=ax, format='%+2.0f dB')
        for child in self.spectrum_tab.winfo_children():
            child.destroy()
        canvas = FigureCanvasTkAgg(fig, master=self.spectrum_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def export_report(self):
        if not self.file_path or self.y is None:
            messagebox.showwarning("提示", "请先分析音频。")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON 文件", "*.json")])
        if not save_path:
            return
        try:
            report = {
                "文件路径": self.file_path,
                "哈希": hash_file(self.file_path),
                "时长": self.duration,
                "采样率": self.sr,
                "评分": self.score,
                "评分明细": self.score_detail,
                "分析时间": datetime.now().isoformat()
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
