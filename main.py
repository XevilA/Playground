import sys
import os
import json
import re
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextEdit, QPushButton, QLabel, QSplitter
)
from PyQt6.QtCore import Qt, QProcess, QTimer, QDir
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
import time

# Directory for temporary code storage
TEMP_DIR = "appstack_temp"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

language_cmds = {
    "Python": "python3",
    "Rust": "rustc",
    "Go": "go run",
    "C": "gcc",
    "C++": "g++",
}

class PythonHighlighter(QSyntaxHighlighter):
    """A simple syntax highlighter for Python code."""
    def __init__(self, parent=None):
        super(PythonHighlighter, self).__init__(parent)

        # Keyword formatting
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#ff79c6"))
        keywords = ["def", "class", "import", "from", "for", "while", "if", "else", "elif", "return", "try", "except"]
        self.rules = [(re.compile(r'\b' + keyword + r'\b'), keyword_format) for keyword in keywords]

        # String formatting
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#f1fa8c"))
        self.rules.append((re.compile(r'".*?"'), string_format))
        self.rules.append((re.compile(r"'.*?'"), string_format))

    def highlightBlock(self, text):
        for pattern, char_format in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, char_format)

class AppStack(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AppStack - Multi-language Code Runner with GUI Preview")
        self.setGeometry(100, 100, 1200, 800)

        # Main layout and splitter setup
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top splitter: code editor and GUI preview
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(top_splitter)

        # Left pane: Code editor tabs
        self.tabs = QTabWidget()
        self.code_editors = {}
        for lang in language_cmds.keys():
            editor = QTextEdit()
            editor.setPlaceholderText(f"Write your {lang} code here...")
            if lang == "Python":  # Add syntax highlighting to Python editor
                PythonHighlighter(editor.document())
            editor.textChanged.connect(self.on_code_change)
            self.code_editors[lang] = editor
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.addWidget(editor)
            self.tabs.addTab(tab, lang)
        top_splitter.addWidget(self.tabs)

        # Right pane: GUI preview
        self.gui_preview = QLabel("GUI Preview (for Tkinter and PyQt6 apps)")
        self.gui_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gui_preview.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        top_splitter.addWidget(self.gui_preview)

        # Bottom pane: Terminal output
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setPlaceholderText("Output will appear here...")
        splitter.addWidget(self.output_area)

        # Timer for real-time execution
        self.run_timer = QTimer()
        self.run_timer.setInterval(1500)  # 1.5 seconds delay
        self.run_timer.timeout.connect(self.run_code)

        # Control buttons
        button_layout = QHBoxLayout()
        self.clear_button = QPushButton("Clear Output")
        self.clear_button.clicked.connect(self.clear_output)
        button_layout.addWidget(self.clear_button)

        # Add elements to main layout
        main_layout.addLayout(button_layout)
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # For GUI preview processes
        self.gui_process = QProcess()

    def on_code_change(self):
        """Start a timer for real-time code execution."""
        self.run_timer.start()

    def run_code(self):
        """Run code in the selected language."""
        self.run_timer.stop()
        current_lang = self.tabs.tabText(self.tabs.currentIndex())
        code = self.code_editors[current_lang].toPlainText()

        # Save code to a temporary file
        code_file = self.save_code(current_lang, code)

        # Check if it's a GUI preview or terminal output
        if current_lang == "Python" and ("Tkinter" in code or "PyQt6" in code):
            self.run_gui_preview(code)
        else:
            output = self.execute_code(current_lang, code_file)
            self.output_area.setPlainText(output)

    def clear_output(self):
        """Clear the output area and stop any running GUI preview."""
        self.output_area.clear()
        if self.gui_process and self.gui_process.state() == QProcess.ProcessState.Running:
            self.gui_process.terminate()

    def save_code(self, language, code):
        """Save code snippet to a temporary file."""
        filename = os.path.join(TEMP_DIR, f"temp_code_{language}.json")
        with open(filename, "w") as file:
            json.dump({"language": language, "code": code}, file)
        return filename

    def execute_code(self, language, code_file):
        """Execute code and return output."""
        output = ""
        try:
            if language == "Python":
                with open(code_file, "r") as f:
                    code_data = json.load(f)
                process = subprocess.run(
                    [language_cmds[language], "-c", code_data["code"]],
                    capture_output=True, text=True
                )
                output = process.stdout if process.returncode == 0 else process.stderr

            elif language in ("C", "C++"):
                ext = "c" if language == "C" else "cpp"
                filename = os.path.join(TEMP_DIR, f"temp_code.{ext}")
                binary_name = os.path.join(TEMP_DIR, "temp_exec")

                with open(filename, "w") as file:
                    file.write(json.load(open(code_file))["code"])

                compile_cmd = f"{language_cmds[language]} {filename} -o {binary_name}"
                compile_process = subprocess.run(compile_cmd, shell=True, capture_output=True, text=True)
                if compile_process.returncode == 0:
                    run_process = subprocess.run(binary_name, shell=True, capture_output=True, text=True)
                    output = run_process.stdout if run_process.returncode == 0 else run_process.stderr
                else:
                    output = compile_process.stderr
                if os.path.exists(binary_name):
                    os.remove(binary_name)

            elif language == "Rust":
                filename = os.path.join(TEMP_DIR, "temp_code.rs")
                with open(filename, "w") as file:
                    file.write(json.load(open(code_file))["code"])
                compile_process = subprocess.run(["rustc", filename], capture_output=True, text=True)
                if compile_process.returncode == 0:
                    run_process = subprocess.run("./temp_code", capture_output=True, text=True)
                    output = run_process.stdout if run_process.returncode == 0 else run_process.stderr
                    os.remove("./temp_code")
                else:
                    output = compile_process.stderr

            elif language == "Go":
                filename = os.path.join(TEMP_DIR, "temp_code.go")
                with open(filename, "w") as file:
                    file.write(json.load(open(code_file))["code"])
                process = subprocess.run([language_cmds[language], filename], capture_output=True, text=True)
                output = process.stdout if process.returncode == 0 else process.stderr

        except Exception as e:
            output = str(e)
        return output

    def run_gui_preview(self, code):
        """Run Python GUI code and display preview."""
        if self.gui_process and self.gui_process.state() == QProcess.ProcessState.Running:
            self.gui_process.terminate()

        # Run GUI code in subprocess
        self.gui_process = QProcess(self)
        self.gui_process.setProgram("python3")
        self.gui_process.setArguments(["-c", code])
        self.gui_process.start()
        self.gui_process.finished.connect(self.on_gui_finished)

    def on_gui_finished(self):
        """Handle GUI process finish."""
        if self.gui_process.exitStatus() == QProcess.ExitStatus.NormalExit:
            self.gui_preview.setText("GUI Preview Finished")
        else:
            self.gui_preview.setText("Error in GUI code.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppStack()
    window.show()
    sys.exit(app.exec())
