"""
Runtime update dialog — shows missing components and download progress.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.theme import COLORS
from app.i18n import language_manager, tr
from app.runtime_assets import RuntimeAssetPlanItem


class RuntimeUpdateDialog(QDialog):
    """Modal dialog that informs the user about missing runtime assets."""

    def __init__(self, plan: list[RuntimeAssetPlanItem], parent=None, *, startup: bool = False):
        super().__init__(parent)
        self._plan = list(plan)
        self._startup = startup
        self._finished = False
        self._auto_close_seconds_left = 0
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setInterval(1000)
        self._auto_close_timer.timeout.connect(self._on_auto_close_tick)
        self._current_step_index = 0
        self._total_steps = len(self._plan)
        self.setMinimumWidth(760)
        self.resize(860, 560)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._setup_ui()
        self._render_plan()
        language_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self._title_label = QLabel("")
        self._title_label.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {COLORS['text_primary']};"
        )
        layout.addWidget(self._title_label)

        self._intro = QLabel("")
        self._intro.setWordWrap(True)
        self._intro.setObjectName("label_secondary")
        layout.addWidget(self._intro)

        self._plan_label = QLabel()
        self._plan_label.setWordWrap(True)
        self._plan_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._plan_label)

        bars_wrap = QWidget()
        bars_layout = QVBoxLayout(bars_wrap)
        bars_layout.setContentsMargins(0, 4, 0, 0)
        bars_layout.setSpacing(8)

        self._overall_title = QLabel("")
        self._overall_title.setStyleSheet(f"font-weight: 600; color: {COLORS['text_primary']};")
        bars_layout.addWidget(self._overall_title)

        self._overall_bar = QProgressBar()
        self._overall_bar.setRange(0, 100)
        self._overall_bar.setValue(0)
        self._overall_bar.setTextVisible(False)
        bars_layout.addWidget(self._overall_bar)

        self._overall_hint = QLabel("")
        self._overall_hint.setObjectName("label_muted")
        bars_layout.addWidget(self._overall_hint)

        self._current_title = QLabel("")
        self._current_title.setStyleSheet(f"font-weight: 600; color: {COLORS['text_primary']};")
        bars_layout.addWidget(self._current_title)

        self._current_bar = QProgressBar()
        self._current_bar.setRange(0, 0)
        self._current_bar.setTextVisible(False)
        bars_layout.addWidget(self._current_bar)

        self._current_hint = QLabel("")
        self._current_hint.setObjectName("label_muted")
        self._current_hint.setWordWrap(True)
        bars_layout.addWidget(self._current_hint)

        layout.addWidget(bars_wrap)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(220)
        layout.addWidget(self._log, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._close_btn = QPushButton("")
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.accept)
        buttons.addWidget(self._close_btn)
        layout.addLayout(buttons)

    def _update_close_button_text(self):
        if self._auto_close_seconds_left > 0:
            self._close_btn.setText(
                tr(
                    "runtime.close_countdown",
                    default="Open application ({seconds})",
                    seconds=self._auto_close_seconds_left,
                )
            )
        else:
            self._close_btn.setText(tr("common.close", default="Close"))

    def retranslate_ui(self):
        self.setWindowTitle(
            tr("runtime.window_title", default="Preparing components")
        )
        self._title_label.setText(
            tr("runtime.title", default="Preparing missing components")
        )
        self._intro.setText(
            tr(
                "runtime.intro_startup" if self._startup else "runtime.intro_manual",
                default=(
                    "The app is preparing required local components."
                ),
            )
        )
        self._overall_title.setText(
            tr("runtime.overall_progress", default="Overall progress")
        )
        if not self._overall_hint.text():
            self._overall_hint.setText(
                tr("runtime.waiting_start", default="Waiting to start...")
            )
        self._current_title.setText(
            tr("runtime.current_component", default="Current component")
        )
        if not self._current_hint.text():
            self._current_hint.setText(
                tr("runtime.queue_preparing", default="Preparing the download queue...")
            )
        self._update_close_button_text()
        self._render_plan()

    def _render_plan(self):
        if not self._plan:
            self._plan_label.setText(
                tr("runtime.all_ready", default="All local components are already ready.")
            )
            return

        lines = []
        for item in self._plan:
            suffix = tr("runtime.optional_suffix", default=" (optional)") if item.optional else ""
            detail = f"<br><span style='color:{COLORS['text_muted']};'>{item.detail}</span>" if item.detail else ""
            lines.append(
                f"<li><b>{item.name}{suffix}</b> — {item.description}{detail}</li>"
            )
        self._plan_label.setText("<ul>" + "".join(lines) + "</ul>")

    def bind_worker(self, worker):
        worker.status_changed.connect(self._on_status_changed)
        worker.step_started.connect(self._on_step_started)
        worker.step_progress.connect(self._on_step_progress)
        worker.overall_progress.connect(self._on_overall_progress)
        worker.bootstrap_finished.connect(self._on_finished)

    def append_log(self, message: str):
        self._log.appendPlainText(message)
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log.setTextCursor(cursor)

    def _on_status_changed(self, message: str):
        self._current_hint.setText(message)
        self.append_log(message)

    def _on_step_started(self, payload: dict):
        index = payload["index"]
        total = payload["total"]
        item = payload["item"]
        self._current_step_index = index
        self._total_steps = total
        self._current_bar.setRange(0, 0)
        self._current_title.setText(
            tr("runtime.current_component", default="Current component") + f": {item.name}"
        )
        self._overall_hint.setText(
            tr("runtime.step_of", default="Step {current} of {total}: {name}", current=index, total=total, name=item.name)
        )
        self.append_log(f"[{index}/{total}] {item.name} — {item.detail or item.description}")

    def _on_step_progress(self, payload: dict):
        percent = payload.get("percent")
        message = payload.get("message", "")
        current = payload.get("current")
        total = payload.get("total")
        item = payload.get("item")

        if percent is None:
            self._current_bar.setRange(0, 0)
            if message:
                self._current_hint.setText(message)
        else:
            self._current_bar.setRange(0, 100)
            self._current_bar.setValue(percent)
            self._overall_bar.setValue(
                self._calculate_overall_percent(
                    self._current_step_index,
                    self._total_steps,
                    percent,
                )
            )
            if item is not None and self._total_steps > 0 and self._current_step_index > 0:
                self._overall_hint.setText(
                    tr(
                        "runtime.step_of_percent",
                        default="Step {current} of {total}: {name} - {percent}%",
                        current=self._current_step_index,
                        total=self._total_steps,
                        name=item.name,
                        percent=percent,
                    )
                )
            if total:
                self._current_hint.setText(
                    f"{message} — {self._format_size(current or 0)} / {self._format_size(total)}"
                )
            else:
                self._current_hint.setText(f"{message} — {percent}%")

    def _on_overall_progress(self, payload: dict):
        completed = payload["completed"]
        total = payload["total"]
        percent = payload["percent"]
        item = payload["item"]
        self._overall_bar.setValue(percent)
        self._overall_hint.setText(
            tr(
                "runtime.done_of",
                default="Done {completed} of {total}: {name}",
                completed=completed,
                total=total,
                name=item.name,
            )
        )

    def _on_finished(self, results: list):
        self._finished = True
        self._close_btn.setEnabled(True)
        self._current_bar.setRange(0, 100)
        self._current_bar.setValue(100)
        self._overall_bar.setValue(100)
        self._auto_close_timer.stop()
        self._auto_close_seconds_left = 0

        failed_required = [result.name for result in results if not result.ok and not result.optional]
        failed_optional = [result.name for result in results if not result.ok and result.optional]

        if failed_required:
            self._current_hint.setText(
                tr(
                    "runtime.finished_required_warn",
                    default="Preparation finished with warnings. Some required components could not be downloaded.",
                )
            )
            self.append_log(
                tr("runtime.needs_attention", default="Needs attention: {items}", items=", ".join(failed_required))
            )
        elif failed_optional:
            self._current_hint.setText(
                tr(
                    "runtime.finished_optional_warn",
                    default="Base components are ready. Some optional components were not prepared.",
                )
            )
            self.append_log(
                tr("runtime.optional_missing", default="Optional components missing: {items}", items=", ".join(failed_optional))
            )
        else:
            self._current_hint.setText(
                tr("runtime.finished_success", default="All missing components were prepared successfully.")
            )
            self.append_log(
                tr("runtime.everything_done", default="Done: all missing components have been prepared.")
            )
            self._auto_close_seconds_left = 30
            self._update_close_button_text()
            self._auto_close_timer.start()
            return

        self._update_close_button_text()

    def _on_auto_close_tick(self):
        if self._auto_close_seconds_left <= 0:
            self._auto_close_timer.stop()
            self.accept()
            return

        self._auto_close_seconds_left -= 1
        if self._auto_close_seconds_left <= 0:
            self._auto_close_timer.stop()
            self.accept()
            return
        self._update_close_button_text()

    @staticmethod
    def _calculate_overall_percent(step_index: int, total_steps: int, step_percent: int | float) -> int:
        if total_steps <= 0:
            return 100
        completed_before = max(0, step_index - 1)
        bounded_step = max(0.0, min(float(step_percent), 100.0))
        overall = ((completed_before + bounded_step / 100.0) / total_steps) * 100.0
        return int(overall)

    @staticmethod
    def _format_size(value: int) -> str:
        units = ["B", "KB", "MB", "GB"]
        amount = float(value)
        unit = units[0]
        for unit in units:
            if amount < 1024 or unit == units[-1]:
                break
            amount /= 1024.0
        if unit == "B":
            return f"{int(amount)} {unit}"
        return f"{amount:.1f} {unit}"

    def reject(self):
        if self._finished:
            self._auto_close_timer.stop()
            super().reject()
