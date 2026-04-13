"""
Bootstrap Controller — handles startup checks and component downloads.

Extracted from MainWindow to reduce its responsibilities.
"""
from typing import Callable
from PySide6.QtWidgets import QMessageBox

from app.hardware import HardwareInfo
from app.runtime_assets import StartupBootstrapWorker, build_runtime_asset_plan
from app.gui.widgets.runtime_update_dialog import RuntimeUpdateDialog
from app.i18n import tr


class BootstrapController:
    """Manages the checking and downloading of required application components."""

    def __init__(
        self,
        parent,
        logger,
        hw_info: HardwareInfo,
        on_status_changed: Callable[[str], None],
        on_started: Callable[[], None],
        on_finished: Callable[[bool], None],
    ):
        self._parent = parent
        self._logger = logger
        self._hw_info = hw_info
        self._on_status_changed = on_status_changed
        self._on_started = on_started
        self._on_finished = on_finished

        self.is_active = False
        self._worker: StartupBootstrapWorker | None = None
        self._dialog: RuntimeUpdateDialog | None = None

    def trigger(self, *, initial: bool, pipeline_running: bool) -> None:
        """Start the bootstrap process."""
        if pipeline_running:
            self._logger.warning("Component preparation cannot run while processing is active")
            return
        if self._worker and self._worker.is_running():
            self._logger.info("Component preparation is already running")
            return

        missing_plan = [item for item in build_runtime_asset_plan(self._hw_info.device) if item.missing]
        if not missing_plan:
            if initial:
                self._on_status_changed(tr("status.ready", default="Ready to work"))
                self._logger.info("Startup check: all local components are already ready")
            else:
                QMessageBox.information(
                    self._parent,
                    "Components ready",
                    "All required local components are already prepared. Nothing else needs to be downloaded.",
                )
            return

        self.is_active = True
        self._on_started()
        self._on_status_changed(tr("status.preparing_components", default="Preparing components..."))

        if initial:
            self._logger.info("Startup preparation: missing components found, downloading them automatically")
        else:
            self._logger.info("Manual preparation started: missing components found, starting download")

        self._dialog = RuntimeUpdateDialog(missing_plan, self._parent, startup=initial)

        self._worker = StartupBootstrapWorker(
            device=self._hw_info.device,
            plan=missing_plan,
            logger_instance=self._logger,
            parent=self._parent,
        )
        self._worker.status_changed.connect(self._on_status_changed)
        self._worker.step_started.connect(self._on_step_started)
        self._worker.step_progress.connect(self._on_step_progress)
        self._worker.overall_progress.connect(self._on_overall_progress)
        self._worker.bootstrap_finished.connect(self._on_worker_finished)
        
        self._dialog.bind_worker(self._worker)
        self._dialog.show()
        self._worker.start()

    def confirm_close(self) -> bool:
        """Check if it's safe to close during an active bootstrap."""
        if not self.is_active:
            return True

        reply = QMessageBox.question(
            self._parent,
            tr("common.confirmation", default="Confirmation"),
            "Component download is in progress. If you close the app, the download will stop. Exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def retranslate(self):
        """Update any open dialog translations."""
        if self._dialog is not None:
            self._dialog.retranslate_ui()

    # ── Internal Worker Callbacks ──────────────────────────────────────

    def _on_step_started(self, payload):
        item = payload["item"]
        self._on_status_changed(f"Preparing: {item.name}...")

    def _on_step_progress(self, payload):
        message = payload.get("message") or ""
        if message:
            self._on_status_changed(message)

    def _on_overall_progress(self, payload):
        completed = payload["completed"]
        total = payload["total"]
        item = payload["item"]
        self._on_status_changed(f"Done {completed} of {total}: {item.name}")

    def _on_worker_finished(self, results):
        self.is_active = False

        required_failures = [item.name for item in results if not item.ok and not item.optional]
        optional_failures = [item.name for item in results if not item.ok and item.optional]

        if required_failures:
            self._on_status_changed("Done with warnings")
            self._logger.warning(
                "Preparation finished with warnings. Needs attention: "
                + ", ".join(required_failures)
            )
        elif optional_failures:
            self._on_status_changed(tr("status.ready", default="Ready to work"))
            self._logger.warning(
                "Base components are ready. Optional components missing: "
                + ", ".join(optional_failures)
            )
        else:
            self._on_status_changed(tr("status.ready", default="Ready to work"))
            self._logger.info("Preparation completed: all available components are ready")

        self._on_finished(success=not required_failures)
