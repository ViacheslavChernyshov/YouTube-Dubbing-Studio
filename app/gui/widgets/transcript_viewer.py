"""
Transcript viewer — shows transcription and translation side by side.
Opens as a dialog from the main window after STT/translation stages complete.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QAbstractItemView,
    QWidget, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from app.gui.theme import COLORS
from app.i18n import language_manager, tr


class TranscriptViewer(QDialog):
    """Dialog showing transcription + translation with timestamps."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(900, 600)
        self.resize(1000, 650)
        self._segments = []
        self._source_lang = ""
        self._setup_ui()
        language_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Header ──
        header = QHBoxLayout()

        self._title_label = QLabel("")
        self._title_label.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {COLORS['text_primary']};"
        )
        header.addWidget(self._title_label)

        header.addStretch()

        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 12px;"
        )
        header.addWidget(self._stats_label)

        layout.addLayout(header)

        # ── Table ──
        self._table = QTableWidget()
        self._table.setColumnCount(4)

        # Style the table
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setWordWrap(True)

        # Column widths
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 100)
        self._table.setColumnWidth(3, 80)

        # Table stylesheet for dark theme
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['bg_input']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                gridline-color: {COLORS['border']};
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 8px 6px;
                border-bottom: 1px solid {COLORS['border']};
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['accent_glow']};
                color: {COLORS['text_primary']};
            }}
            QTableWidget::item:alternate {{
                background-color: rgba(255,255,255,0.02);
            }}
            QHeaderView::section {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text_secondary']};
                border: none;
                border-bottom: 2px solid {COLORS['accent']};
                padding: 8px 6px;
                font-weight: 600;
                font-size: 12px;
            }}
        """)

        layout.addWidget(self._table, 1)

        # ── Bottom buttons ──
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self._export_srt_btn = QPushButton("")
        self._export_srt_btn.setObjectName("btn_secondary")
        self._export_srt_btn.setFixedWidth(160)
        self._export_srt_btn.clicked.connect(self._export_srt)
        bottom.addWidget(self._export_srt_btn)

        self._export_txt_btn = QPushButton("")
        self._export_txt_btn.setObjectName("btn_secondary")
        self._export_txt_btn.setFixedWidth(160)
        self._export_txt_btn.clicked.connect(self._export_txt)
        bottom.addWidget(self._export_txt_btn)

        bottom.addStretch()

        self._close_btn = QPushButton("")
        self._close_btn.setFixedWidth(120)
        self._close_btn.clicked.connect(self.close)
        bottom.addWidget(self._close_btn)

        layout.addLayout(bottom)

    def retranslate_ui(self):
        self.setWindowTitle(
            tr("transcript.window_title", default="📝 Transcript and translation")
        )
        self._title_label.setText(
            tr("transcript.window_title", default="📝 Transcript and translation")
        )
        self._table.setHorizontalHeaderLabels(
            [
                tr("transcript.header.time", default="⏱ Time"),
                tr("transcript.header.original", default="Original"),
                tr("transcript.header.translation", default="Translation"),
                tr("transcript.header.duration", default="Duration"),
            ]
        )
        self._export_srt_btn.setText(
            tr("transcript.export_srt", default="💾 Export to SRT")
        )
        self._export_srt_btn.setToolTip(
            tr(
                "transcript.export_srt_tip",
                default="Export the translated text as timed subtitles in .srt format.",
            )
        )
        self._export_txt_btn.setText(
            tr("transcript.export_txt", default="📄 Export to TXT")
        )
        self._export_txt_btn.setToolTip(
            tr(
                "transcript.export_txt_tip",
                default="Export the transcript and translation as a readable text file.",
            )
        )
        self._close_btn.setText(tr("common.close", default="Close"))
        self._close_btn.setToolTip(
            tr("transcript.close_tip", default="Close the transcript window and return to the main screen.")
        )
        self._table.setToolTip(
            tr(
                "transcript.table_tip",
                default="Review timestamps, original phrases, translation, and segment duration before export.",
            )
        )
        if self._segments:
            self._refresh_stats()

    def load_segments(self, segments: list, source_lang: str = ""):
        """Load segments into the table."""
        self._segments = segments
        self._source_lang = source_lang
        self._table.setRowCount(0)

        total_chars_orig = 0
        total_chars_trans = 0

        for i, seg in enumerate(segments):
            self._table.insertRow(i)

            # Timestamp
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            time_str = f"{self._fmt_time(start)} → {self._fmt_time(end)}"
            time_item = QTableWidgetItem(time_str)
            time_item.setForeground(QColor(COLORS['accent']))
            time_item.setFont(QFont("Cascadia Code", 11))
            self._table.setItem(i, 0, time_item)

            # Original text
            orig_text = seg.get("text", "")
            orig_item = QTableWidgetItem(orig_text)
            orig_item.setForeground(QColor(COLORS['text_primary']))
            self._table.setItem(i, 1, orig_item)
            total_chars_orig += len(orig_text)

            # Translated text
            trans_text = seg.get("translated_text", "")
            trans_item = QTableWidgetItem(trans_text)
            if trans_text == orig_text:
                # No translation happened
                trans_item.setForeground(QColor(COLORS['text_muted']))
            else:
                trans_item.setForeground(QColor(COLORS['success']))
            self._table.setItem(i, 2, trans_item)
            total_chars_trans += len(trans_text)

            # Duration
            dur = end - start
            dur_item = QTableWidgetItem(
                f"{dur:.1f}{tr('transcript.duration_suffix', default='s')}"
            )
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            dur_item.setForeground(QColor(COLORS['text_secondary']))
            self._table.setItem(i, 3, dur_item)

            # Auto row height
            self._table.setRowHeight(i, max(40, min(80, len(orig_text) // 2 + 30)))

        self._refresh_stats(total_chars_orig, total_chars_trans)

    def _refresh_stats(self, total_chars_orig: int | None = None, total_chars_trans: int | None = None):
        if total_chars_orig is None or total_chars_trans is None:
            total_chars_orig = sum(len(seg.get("text", "")) for seg in self._segments)
            total_chars_trans = sum(len(seg.get("translated_text", "")) for seg in self._segments)
        lang_label = self._source_lang.upper() if self._source_lang else "?"
        self._stats_label.setText(
            tr(
                "transcript.stats",
                default="Language: {lang} | Segments: {count} | Characters: {orig} -> {translated}",
                lang=lang_label,
                count=len(self._segments),
                orig=total_chars_orig,
                translated=total_chars_trans,
            )
        )

    def _fmt_time(self, seconds: float) -> str:
        """Format seconds as MM:SS.s"""
        m = int(seconds // 60)
        s = seconds % 60
        return f"{m:02d}:{s:04.1f}"

    def _fmt_srt_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS,mmm for SRT."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        ms = int((s - int(s)) * 1000)
        return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"

    def _export_srt(self):
        """Export translated text as SRT subtitle file."""
        if not self._segments:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("transcript.save_srt", default="Save SRT"),
            "",
            "Subtitles (*.srt)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                for i, seg in enumerate(self._segments):
                    text = seg.get("translated_text", seg.get("text", ""))
                    start = self._fmt_srt_time(seg.get("start", 0))
                    end = self._fmt_srt_time(seg.get("end", 0))
                    f.write(f"{i+1}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{text}\n\n")

            QMessageBox.information(
                self,
                tr("transcript.export_title", default="Export"),
                tr("transcript.saved_srt", default="SRT saved:\n{path}", path=path),
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("common.error", default="Error"),
                tr("transcript.export_failed", default="Unable to save:\n{error}", error=e),
            )

    def _export_txt(self):
        """Export as plain text with timestamps."""
        if not self._segments:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("transcript.save_txt", default="Save TXT"),
            "",
            "Text (*.txt)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("=" * 70 + "\n")
                f.write(tr("transcript.txt_heading", default="TRANSCRIPT AND TRANSLATION") + "\n")
                f.write("=" * 70 + "\n\n")

                for seg in self._segments:
                    start = self._fmt_time(seg.get("start", 0))
                    end = self._fmt_time(seg.get("end", 0))
                    orig = seg.get("text", "")
                    trans = seg.get("translated_text", "")

                    f.write(f"[{start} → {end}]\n")
                    f.write(f"  {tr('transcript.txt_original', default='ORIGINAL')}:  {orig}\n")
                    f.write(f"  {tr('transcript.txt_translation', default='TRANSLATION')}:   {trans}\n")
                    f.write("-" * 50 + "\n")

            QMessageBox.information(
                self,
                tr("transcript.export_title", default="Export"),
                tr("transcript.saved_txt", default="TXT saved:\n{path}", path=path),
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("common.error", default="Error"),
                tr("transcript.export_failed", default="Unable to save:\n{error}", error=e),
            )
