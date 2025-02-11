import os
import re
import json
import html
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import textwrap

class RPGMMVTranslationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RPG Maker MV Çeviri Aracı")
        self.root.configure(bg='black')
        
        # Stil ayarları
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('.', background='black', foreground='cyan', fieldbackground='black')
        self.style.map('TButton', foreground=[('active', 'cyan')], background=[('active', 'black')])
        
        # Değişkenler
        self.directory = ""
        self.original_strings = []      # HTML'e aktarılacak placeholder uygulanmış metinler
        self.translation_entries = []   # Hangi metnin hangi dosyada, hangi alanda olduğunu tutan kayıtlar
        self.files_data = {}            # Dosya yolu -> JSON objesi (dosyanın yüklü hali)
        self.placeholder_mapping = []   # \\SE[1] gibi kodlar için mapping listesi
        
        self.create_widgets()
    
    def create_widgets(self):
        # Klasör seçim butonu
        self.dir_btn = ttk.Button(self.root, text="Klasör Seç", command=self.select_directory)
        self.dir_btn.pack(pady=10)
        
        # Bilgi label
        self.info_label = ttk.Label(self.root, text="Seçilen Klasör: Yok")
        self.info_label.pack()
        
        # Satır uzunluğu (harf) giriş alanı ekliyoruz (varsayılan 60)
        max_width_frame = ttk.Frame(self.root)
        max_width_frame.pack(pady=5)
        max_width_label = ttk.Label(max_width_frame, text="Satır uzunluğu (harf):", background='black', foreground='cyan')
        max_width_label.pack(side='left')
        self.max_width_entry = ttk.Entry(max_width_frame, width=5)
        self.max_width_entry.insert(0, "60")  # Varsayılan değer
        self.max_width_entry.pack(side='left')
        
        # HTML'e aktar butonu (ilk etapta devre dışı)
        self.export_btn = ttk.Button(self.root, text="HTML'e Aktar", command=self.export_html, state='disabled')
        self.export_btn.pack(pady=5)
        
        # Çeviri alanı
        self.translate_frame = ttk.Frame(self.root)
        self.translate_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Orijinal metinler (HTML aktarımında hangi metinlerin toplandığını gösterir)
        self.original_text = scrolledtext.ScrolledText(self.translate_frame, width=40, height=20,
                                                        bg='black', fg='cyan', insertbackground='cyan')
        self.original_text.pack(side='left', fill='both', expand=True)
        
        # Çevrilen metinler (kullanıcı çevirilerini girebilir)
        self.translated_text = scrolledtext.ScrolledText(self.translate_frame, width=40, height=20,
                                                          bg='black', fg='cyan', insertbackground='cyan')
        self.translated_text.pack(side='right', fill='both', expand=True)
        
        # Uygula butonu (çevrilen metinleri dosyaya uygular)
        self.apply_btn = ttk.Button(self.root, text="Çevirileri Uygula", command=self.apply_translations, state='disabled')
        self.apply_btn.pack(pady=10)
    
    def process_escapes(self, s):
        """
        Escape dizelerini placeholder ile değiştirir.
        \\SE[1] gibi diziler self.placeholder_mapping listesine eklenir.
        Diğer kaçış dizeleri ise yerel mapping listesine eklenir.
        """
        local_mapping = []
        def repl(match):
            code = match.group(0)
            if re.match(r'\\SE\[\d+\]', code):
                self.placeholder_mapping.append(code)
                index = len(self.placeholder_mapping) - 1
                return f'##PLACEHOLDER_SE{index}##'
            else:
                local_mapping.append(code)
                index = len(local_mapping) - 1
                return f'##ESC{index}##'
        pattern = r'(\\(?:[CVNI]|SE)\[\d+\])'
        processed = re.sub(pattern, repl, s)
        return s, processed, local_mapping
    
    def restore_escapes(self, s, mapping):
        """
        Placeholder (##ESC0##, ##PLACEHOLDER_SE0##, ...) içindeki numarayı tespit eder
        ve mapping içerisindeki orijinal değeri geri koyar.
        """
        def repl(match):
            idx = int(match.group(1))
            if idx < len(mapping):
                return mapping[idx]
            return match.group(0)
        s = re.sub(r'##ESC(\d+)##', repl, s)
        
        def repl_se(match):
            idx = int(match.group(1))
            if idx < len(self.placeholder_mapping):
                return self.placeholder_mapping[idx]
            return match.group(0)
        return re.sub(r'##PLACEHOLDER_SE(\d+)##', repl_se, s)
    
    def word_wrap(self, text, max_width):
        """
        textwrap.wrap kullanılarak metni verilen max_width genişliğinde,
        kelime bütünlüğünü bozmadan sarar. Eğer max_width sınırında kelime
        tamamlanmamışsa tamamı alt satıra aktarılır.
        """
        wrapped_lines = textwrap.wrap(text, width=max_width, break_long_words=False, break_on_hyphens=False)
        return wrapped_lines
    
    def parse_json_files(self):
        target_files = []
        for root_dir, dirs, files in os.walk(self.directory):
            for file in files:
                if file.endswith('.json'):
                    if any(file.startswith(prefix) for prefix in ["Map", "CommonEvents", "Actors", "Items", "Weapons", "Armors", "Skills", "Enemies", "Classes", "States", "MapInfos"]):
                        target_files.append(os.path.join(root_dir, file))
        for file_path in target_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.files_data[file_path] = data
                if os.path.basename(file_path).startswith("Map"):
                    self.extract_from_map(file_path, data)
                elif os.path.basename(file_path) == "CommonEvents.json":
                    self.extract_from_common_events(file_path, data)
                else:
                    self.extract_from_database(file_path, data)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
    
    def extract_from_map(self, file_path, data):
        if "events" not in data:
            return
        events = data["events"]
        # Eğer events bir liste değilse (örneğin boolean ise) işleme alma
        if not isinstance(events, list):
            return
        for event in events:
            if event is None or "pages" not in event:
                continue
            for page in event["pages"]:
                if "list" not in page:
                    continue
                i = 0
                while i < len(page["list"]):
                    cmd = page["list"][i]
                    if cmd.get("code") == 401:
                        raw, processed, mapping = self.process_escapes(cmd["parameters"][0])
                        merged_text = processed
                        merged_raw = [raw]
                        merged_mappings = [mapping]
                        start_index = i
                        i += 1
                        while i < len(page["list"]) and page["list"][i].get("code") == 401:
                            raw2, processed2, mapping2 = self.process_escapes(page["list"][i]["parameters"][0])
                            merged_text += " __DELIM__ " + processed2
                            merged_raw.append(raw2)
                            merged_mappings.append(mapping2)
                            i += 1
                        self.original_strings.append(merged_text)
                        entry = {
                            "file": file_path,
                            "page_list": page["list"],
                            "start_index": start_index,
                            "count": len(merged_raw),
                            "raws": merged_raw,
                            "merged": merged_text,
                            "mappings": merged_mappings
                        }
                        self.translation_entries.append(entry)
                    else:
                        if cmd.get("code") == 102:
                            choices = cmd.get("parameters", [None])[0]
                            if choices and isinstance(choices, list):
                                for j, choice in enumerate(choices):
                                    if choice:
                                        raw, processed, mapping = self.process_escapes(choice)
                                        self.original_strings.append(processed)
                                        entry = {
                                            "file": file_path,
                                            "container": cmd["parameters"][0],
                                            "index": j,
                                            "raw": raw,
                                            "processed": processed,
                                            "mapping": mapping
                                        }
                                        self.translation_entries.append(entry)
                        elif cmd.get("code") == 402:
                            params = cmd.get("parameters", [])
                            if len(params) >= 2:
                                text = params[1]
                                if text:
                                    raw, processed, mapping = self.process_escapes(text)
                                    self.original_strings.append(processed)
                                    entry = {
                                        "file": file_path,
                                        "container": cmd["parameters"],
                                        "index": 1,
                                        "raw": raw,
                                        "processed": processed,
                                        "mapping": mapping
                                    }
                                    self.translation_entries.append(entry)
                        i += 1
    
    def extract_from_common_events(self, file_path, data):
        for event in data:
            if event is None:
                continue
            if "list" in event:
                self.extract_from_event_list(file_path, event["list"])
    
    def extract_from_event_list(self, file_path, lst):
        for command in lst:
            code = command.get("code", None)
            if code == 401:
                text = command.get("parameters", [""])[0]
                if text:
                    raw, processed, mapping = self.process_escapes(text)
                    self.original_strings.append(processed)
                    entry = {
                        "file": file_path,
                        "container": command["parameters"],
                        "index": 0,
                        "raw": raw,
                        "processed": processed,
                        "mapping": mapping
                    }
                    self.translation_entries.append(entry)
            elif code == 102:
                choices = command.get("parameters", [None])[0]
                if choices and isinstance(choices, list):
                    for i, choice in enumerate(choices):
                        if choice:
                            raw, processed, mapping = self.process_escapes(choice)
                            self.original_strings.append(processed)
                            entry = {
                                "file": file_path,
                                "container": command["parameters"][0],
                                "index": i,
                                "raw": raw,
                                "processed": processed,
                                "mapping": mapping
                            }
                            self.translation_entries.append(entry)
            elif code == 402:
                params = command.get("parameters", [])
                if len(params) >= 2:
                    text = params[1]
                    if text:
                        raw, processed, mapping = self.process_escapes(text)
                        self.original_strings.append(processed)
                        entry = {
                            "file": file_path,
                            "container": command["parameters"],
                            "index": 1,
                            "raw": raw,
                            "processed": processed,
                            "mapping": mapping
                        }
                        self.translation_entries.append(entry)
    
    def extract_from_database(self, file_path, data):
        if not isinstance(data, list):
            return
        for obj in data:
            if obj is None:
                continue
            for key in ["name", "description"]:
                if key in obj and isinstance(obj[key], str) and obj[key]:
                    text = obj[key]
                    raw, processed, mapping = self.process_escapes(text)
                    self.original_strings.append(processed)
                    entry = {
                        "file": file_path,
                        "container_obj": obj,
                        "key": key,
                        "raw": raw,
                        "processed": processed,
                        "mapping": mapping
                    }
                    self.translation_entries.append(entry)
    
    def export_html(self):
        if not self.original_strings:
            messagebox.showwarning("Uyarı", "Çevrilecek metin bulunamadı!")
            return
        
        html_content = """<html>
<head>
    <style>
        body { background-color: black; color: cyan; font-family: monospace; }
        li { margin: 10px 0; white-space: pre-wrap; }
    </style>
</head>
<body>
    <ol>
"""
        for s in self.original_strings:
            s_clean = s.replace("\n", "").strip()
            html_content += f'        <li>{html.escape(s_clean)}</li>\n'
        html_content += """    </ol>
</body>
</html>"""
        
        with open('translations.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        webbrowser.open('translations.html')
        self.apply_btn.config(state='normal')
    
    def apply_translations(self):
        translated = self.translated_text.get(1.0, tk.END).splitlines()
        if len(translated) < len(self.translation_entries):
            translated.extend([""] * (len(self.translation_entries) - len(translated)))
        elif len(translated) > len(self.translation_entries):
            translated = translated[:len(self.translation_entries)]
        
        # Kullanıcının belirlediği maksimum satır genişliğini oku (harf cinsinden)
        try:
            max_width = int(self.max_width_entry.get())
        except ValueError:
            max_width = 60
        
        for i, entry in enumerate(self.translation_entries):
            new_text = translated[i]
            if "page_list" in entry:
                parts = new_text.split(" __DELIM__ ")
                # Parça sayısı, mapping listesindeki eleman sayısıyla aynı değilse, eşitleriz:
                if len(parts) < len(entry["mappings"]):
                    parts.extend([""] * (len(entry["mappings"]) - len(parts)))
                elif len(parts) > len(entry["mappings"]):
                    parts = parts[:len(entry["mappings"])]
    
                for idx, part in enumerate(parts):
                    fixed = self.restore_escapes(part, entry["mappings"][idx])
                    wrapped = self.word_wrap(fixed, max_width)
                    final_text = "\n".join(wrapped)
                    entry["page_list"][entry["start_index"] + idx]["parameters"][0] = final_text.replace('"', r'\"')
    
            else:
                fixed = self.restore_escapes(new_text, entry["mapping"])
                wrapped = self.word_wrap(fixed, max_width)
                final_text = "\n".join(wrapped)
                if "container" in entry:
                    entry["container"][entry["index"]] = final_text.replace('"', r'\"')
                elif "container_obj" in entry:
                    entry["container_obj"][entry["key"]] = final_text.replace('"', r'\"')
        
        updated_files = set(entry["file"] for entry in self.translation_entries)
        for file_path in updated_files:
            if file_path in self.files_data:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.files_data[file_path], f, indent=4, ensure_ascii=False)
                except Exception as e:
                    print(f"Error writing {file_path}: {e}")
        messagebox.showinfo("Başarılı", "Çeviriler başarıyla uygulandı!")
        
    def select_directory(self):
        self.directory = filedialog.askdirectory()
        if self.directory:
            self.info_label.config(text=f"Seçilen Klasör: {self.directory}")
            self.original_strings = []
            self.translation_entries = []
            self.files_data = {}
            self.placeholder_mapping = []  # Her seferinde sıfırlanır
            self.parse_json_files()
            self.original_text.delete(1.0, tk.END)
            self.original_text.insert(tk.END, "\n".join(self.original_strings))
            self.export_btn.config(state='normal')
    
if __name__ == "__main__":
    root = tk.Tk()
    app = RPGMMVTranslationApp(root)
    root.mainloop()
