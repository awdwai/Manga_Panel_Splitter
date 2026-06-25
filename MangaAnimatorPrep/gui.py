"""Tkinter desktop GUI for MangaAnimatorPrep."""

from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from typing import Any

from MangaAnimatorPrep.config import AppConfig, load_config
from MangaAnimatorPrep.pipeline import MangaAnimatorPipeline
from MangaAnimatorPrep.utils.gpu import resolve_runtime, torch_cuda_available


def gui_smoke_test() -> dict[str, Any]:
    """Validate GUI imports and, when possible, create a root window."""

    try:
        import tkinter as tk
    except Exception as exc:  # pragma: no cover - platform dependent
        return {"status": "broken", "error": str(exc)}
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        return {"status": "headless", "tkinter": tk.TkVersion}
    root = tk.Tk()
    root.withdraw()
    root.update_idletasks()
    root.destroy()
    return {"status": "working", "tkinter": tk.TkVersion}


class MangaAnimatorPrepGUI:
    """Simple desktop front-end that runs the existing processing pipeline."""

    def __init__(self, config_path: Path | None = None) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, scrolledtext, ttk

        self.tk = tk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.ttk = ttk
        self.config_path = config_path
        self.root = tk.Tk()
        self.root.title("MangaAnimatorPrep")
        self.root.geometry("780x560")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar(value="output")
        self.debug_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._build_ui(scrolledtext)
        self.root.after(100, self._drain_log_queue)

    def _build_ui(self, scrolledtext: Any) -> None:
        frame = self.ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)

        self.ttk.Label(frame, text="Input image or folder").grid(row=0, column=0, sticky="w")
        self.ttk.Entry(frame, textvariable=self.input_var).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.ttk.Button(frame, text="Choose Image", command=self._choose_image).grid(row=1, column=3, padx=(8, 0), sticky="ew")
        self.ttk.Button(frame, text="Choose Folder", command=self._choose_folder).grid(row=1, column=4, padx=(8, 0), sticky="ew")

        self.ttk.Label(frame, text="Output folder").grid(row=2, column=0, sticky="w")
        self.ttk.Entry(frame, textvariable=self.output_var).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.ttk.Button(frame, text="Choose Output", command=self._choose_output).grid(row=3, column=3, columnspan=2, padx=(8, 0), sticky="ew")

        self.ttk.Checkbutton(frame, text="Write debug visualizations", variable=self.debug_var).grid(row=4, column=0, sticky="w")
        self.ttk.Button(frame, text="Process", command=lambda: self._start_run(False)).grid(row=5, column=0, sticky="ew", pady=8)
        self.ttk.Button(frame, text="Benchmark", command=lambda: self._start_run(True)).grid(row=5, column=1, sticky="ew", pady=8, padx=(8, 0))
        self.ttk.Button(frame, text="System Info", command=self._show_system_info).grid(row=5, column=2, sticky="ew", pady=8, padx=(8, 0))

        self.ttk.Label(frame, textvariable=self.status_var).grid(row=6, column=0, columnspan=5, sticky="w")
        self.log_text = scrolledtext.ScrolledText(frame, height=22, state="disabled")
        self.log_text.grid(row=7, column=0, columnspan=5, sticky="nsew", pady=(8, 0))

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.rowconfigure(7, weight=1)

    def run(self) -> None:
        self.root.mainloop()

    def _choose_image(self) -> None:
        path = self.filedialog.askopenfilename(
            title="Choose manga image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp"), ("All files", "*.*")],
        )
        if path:
            self.input_var.set(path)

    def _choose_folder(self) -> None:
        path = self.filedialog.askdirectory(title="Choose input folder")
        if path:
            self.input_var.set(path)

    def _choose_output(self) -> None:
        path = self.filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output_var.set(path)

    def _start_run(self, benchmark: bool) -> None:
        input_path = Path(self.input_var.get())
        output_path = Path(self.output_var.get())
        if not input_path.exists():
            self.messagebox.showerror("Input missing", f"Input path does not exist:\n{input_path}")
            return
        self.status_var.set("Running benchmark..." if benchmark else "Processing...")
        worker = threading.Thread(target=self._run_pipeline, args=(input_path, output_path, benchmark), daemon=True)
        worker.start()

    def _run_pipeline(self, input_path: Path, output_path: Path, benchmark: bool) -> None:
        try:
            config = load_config(self.config_path)
            config.output.debug = bool(self.debug_var.get())
            if benchmark:
                config.output.save_benchmark_markdown = True
                config.output.save_performance_json = True
            self._log(f"Input: {input_path}")
            self._log(f"Output: {output_path}")
            results = MangaAnimatorPipeline(config).process_path(input_path, output_path, debug=config.output.debug)
            self._log(f"Completed successfully: {len(results)} panel(s) processed.")
            self.root.after(0, lambda: self.status_var.set("Complete"))
        except Exception as exc:  # pragma: no cover - exercised manually
            self._log(f"ERROR: {exc}")
            self.root.after(0, lambda: self.status_var.set("Failed"))

    def _show_system_info(self) -> None:
        config = load_config(self.config_path)
        runtime = resolve_runtime(config.device)
        lines = [
            f"Device: {runtime.device}",
            f"torch.cuda.is_available(): {torch_cuda_available()}",
            f"Mixed precision: {runtime.mixed_precision}",
            f"PyTorch available: {runtime.torch_available}",
            f"GPU: {runtime.gpu_name or 'not detected'}",
            f"ONNX providers: {', '.join(runtime.onnx_providers) or 'none'}",
        ]
        self._log("\n".join(lines))

    def _log(self, message: str) -> None:
        self.log_queue.put(message)

    def _drain_log_queue(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(100, self._drain_log_queue)


def launch_gui(config_path: Path | None = None) -> None:
    MangaAnimatorPrepGUI(config_path).run()

