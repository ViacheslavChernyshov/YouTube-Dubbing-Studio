"""
Built-in documentation dialog with guided sections for the app.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION
from app.gui.theme import COLORS
from app.i18n import language_manager, tr


PIPELINE_DOCS = [
    ("1. Скачивание видео", "Берёт ролик по ссылке YouTube и сохраняет локально через yt-dlp."),
    ("2. Извлечение аудио", "Достаёт звуковую дорожку из исходного видео, чтобы работать уже со звуком отдельно."),
    ("3. Подготовка аудио", "Проверяет исходную дорожку и готовит её к распознаванию и будущему миксу."),
    ("4. Распознавание речи", "Расшифровывает оригинальную речь в текст и разбивает её на сегменты с таймкодами."),
    ("5. Перевод текста", "Переводит сегменты на целевой язык, сохраняя структуру фраз для озвучивания."),
    ("6. Генерация речи (TTS)", "Озвучивает перевод выбранной моделью и голосом."),
    ("7. Выравнивание по времени", "Подгоняет длину и позицию TTS-фраз под оригинальные таймкоды."),
    ("8. Микширование аудио", "Либо оставляет только новую озвучку, либо смешивает её с оригинальной дорожкой."),
    ("9. Сборка финального видео", "Подменяет аудио в ролике и собирает итоговый файл output.mp4."),
]


class DocumentationDialog(QDialog):
    """Dialog with built-in user documentation."""

    SECTION_ORDER = [
        "overview",
        "quick_start",
        "menu_guide",
        "interface",
        "settings",
        "voices",
        "pipeline",
        "faq",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(980, 680)
        self.resize(1120, 760)
        self._sections = self._build_sections()
        self._setup_ui()
        self._populate_sections()
        self.open_section("overview")
        language_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self._title_label = QLabel("")
        self._title_label.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {COLORS['text_primary']};"
        )
        header.addWidget(self._title_label)
        header.addStretch()

        self._subtitle_label = QLabel("")
        self._subtitle_label.setStyleSheet(
            f"font-size: 12px; color: {COLORS['text_muted']};"
        )
        header.addWidget(self._subtitle_label)
        layout.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(12)

        self._section_list = QListWidget()
        self._section_list.setFixedWidth(260)
        self._section_list.currentItemChanged.connect(self._on_section_changed)
        self._section_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS['bg_input']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 6px;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 8px;
                color: {COLORS['text_secondary']};
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['accent_glow']};
                color: {COLORS['text_primary']};
            }}
            QListWidget::item:hover {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text_primary']};
            }}
        """)
        content.addWidget(self._section_list)

        browser_wrap = QWidget()
        browser_layout = QVBoxLayout(browser_wrap)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(8)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {COLORS['bg_input']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 14px;
                color: {COLORS['text_primary']};
                selection-background-color: {COLORS['accent']};
            }}
        """)
        browser_layout.addWidget(self._browser, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        self._close_btn = QPushButton("")
        self._close_btn.setFixedWidth(140)
        self._close_btn.clicked.connect(self.close)
        footer.addWidget(self._close_btn)
        browser_layout.addLayout(footer)

        content.addWidget(browser_wrap, 1)
        layout.addLayout(content, 1)

    def _populate_sections(self):
        self._section_list.clear()
        for section_id in self.SECTION_ORDER:
            item = QListWidgetItem(self._sections[section_id]["title"])
            item.setData(Qt.ItemDataRole.UserRole, section_id)
            self._section_list.addItem(item)

    def retranslate_ui(self):
        current_section_id = "overview"
        current_item = self._section_list.currentItem()
        if current_item is not None:
            current_section_id = current_item.data(Qt.ItemDataRole.UserRole)
        self.setWindowTitle(
            tr("docs.window_title", default="Documentation - {app_name}", app_name=APP_NAME)
        )
        self._title_label.setText(
            tr("docs.header_title", default="Help and documentation - {app_name}", app_name=APP_NAME)
        )
        self._subtitle_label.setText(
            tr("docs.version", default="Version {version}", version=APP_VERSION)
        )
        self._close_btn.setText(tr("common.close", default="Close"))
        self._close_btn.setToolTip(
            tr("docs.close_tip", default="Close the help window and return to the main screen.")
        )
        self._section_list.setToolTip(
            tr(
                "docs.section_list_tip",
                default="Choose a help section here. The article on the right updates immediately.",
            )
        )
        self._browser.setToolTip(
            tr(
                "docs.browser_tip",
                default="Built-in guide with explanations of interface elements, settings, and workflow.",
            )
        )
        self._sections = self._build_sections()
        self._populate_sections()
        self.open_section(current_section_id)

    def open_section(self, section_id: str):
        for index in range(self._section_list.count()):
            item = self._section_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == section_id:
                self._section_list.setCurrentRow(index)
                return
        if self._section_list.count():
            self._section_list.setCurrentRow(0)

    def _on_section_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None):
        if not current:
            return
        section_id = current.data(Qt.ItemDataRole.UserRole)
        section = self._sections.get(section_id)
        if not section:
            return
        self._browser.setHtml(self._wrap_page(section["title"], section["body"]))
        self._browser.verticalScrollBar().setValue(0)

    def _wrap_page(self, title: str, body: str) -> str:
        return f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', sans-serif;
                    color: {COLORS['text_primary']};
                    background: {COLORS['bg_input']};
                    line-height: 1.58;
                }}
                h1 {{
                    font-size: 24px;
                    margin: 0 0 10px 0;
                    color: {COLORS['text_primary']};
                }}
                h2 {{
                    font-size: 18px;
                    margin: 22px 0 8px 0;
                    color: {COLORS['text_primary']};
                }}
                p {{
                    margin: 0 0 10px 0;
                    color: {COLORS['text_secondary']};
                }}
                ul, ol {{
                    margin: 6px 0 12px 18px;
                    color: {COLORS['text_secondary']};
                }}
                li {{
                    margin: 0 0 7px 0;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 10px 0 18px 0;
                }}
                th, td {{
                    border: 1px solid {COLORS['border']};
                    padding: 8px 10px;
                    text-align: left;
                    vertical-align: top;
                }}
                th {{
                    background: {COLORS['bg_card']};
                    color: {COLORS['text_primary']};
                }}
                td {{
                    color: {COLORS['text_secondary']};
                }}
                code {{
                    background: {COLORS['bg_card']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 4px;
                    padding: 1px 5px;
                    color: {COLORS['text_primary']};
                }}
                .callout {{
                    margin: 12px 0;
                    padding: 10px 12px;
                    border-radius: 8px;
                    background: {COLORS['bg_card']};
                    border-left: 4px solid {COLORS['accent']};
                    color: {COLORS['text_secondary']};
                }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            {body}
        </body>
        </html>
        """

    def _build_sections(self) -> dict[str, dict[str, str]]:
        pipeline_rows = "".join(
            f"<tr><td>{title}</td><td>{desc}</td></tr>"
            for title, desc in PIPELINE_DOCS
        )

        settings_rows = """
            <tr><td>Модель озвучки</td><td>Выбирает движок синтеза. <code>Kokoro</code> — локальный и удобный для большинства задач, <code>Edge</code> — очень стабильный сетевой голос, <code>F5</code> — тяжёлое клонирование по образцу.</td></tr>
            <tr><td>Голос</td><td>Определяет тембр. Для Kokoro в названии теперь видны язык профиля и ориентировочная оценка качества.</td></tr>
            <tr><td>Авто-обрезка пауз</td><td>Удаляет лишнюю тишину вокруг сгенерированных фраз, чтобы речь была плотнее и короче.</td></tr>
            <tr><td>Мягкое отсечение концовок</td><td>Опция Kokoro. Сохраняет более естественное затухание фраз в конце предложений.</td></tr>
            <tr><td>Акцент en-US / en-GB</td><td>Опция Kokoro. Меняет английское произношение текста, не меняя сам тембр модели.</td></tr>
            <tr><td>Скорость Kokoro</td><td>Ускоряет или замедляет речь. Полезно, если фразы не помещаются в таймкоды или хочется спокойнее подачу.</td></tr>
            <tr><td>Скрывать слабые голоса</td><td>Прячет Kokoro-профили с низкой официальной оценкой качества, чтобы список был чище.</td></tr>
            <tr><td>Качество F5 (NFE)</td><td>Опция F5. Чем выше значение, тем дольше синтез, но потенциально лучше качество и плавность голоса.</td></tr>
            <tr><td>Ровная динамика звука</td><td>Накладывает сегменты мягче и помогает избежать грубых провалов на стыках.</td></tr>
            <tr><td>Оставить звук оригинала</td><td>Сохраняет фоновую музыку, шум помещения и атмосферу исходного ролика.</td></tr>
            <tr><td>Громкость</td><td>Задаёт, насколько слышен оригинальный звук под новой озвучкой.</td></tr>
            <tr><td>Динамичный монтаж</td><td>Вырезает пустоты между фразами и собирает более плотную версию ролика. Это заметно увеличивает время финальной сборки.</td></tr>
        """

        menu_rows = """
            <tr><td>Файл</td><td>Открытие папок с заданиями и логами, доступ к текущей папке задания и выход из программы.</td></tr>
            <tr><td>Действия</td><td>Быстрый старт обработки, остановка, вставка ссылки, открытие транскрипта, оригинала, результата и очистка журнала.</td></tr>
            <tr><td>Настройки</td><td>Дублирует самые важные переключатели правой панели: выбор модели, базовые аудио-опции, Kokoro- и F5-настройки.</td></tr>
            <tr><td>Документация</td><td>Открывает встроенные инструкции по работе с программой, по этапам пайплайна и по выбору настроек.</td></tr>
        """

        interface_rows = """
            <tr><td>Поле ссылки</td><td>Принимает ссылку YouTube. После ввода корректной ссылки кнопка старта становится активной.</td></tr>
            <tr><td>Панель этапов</td><td>Показывает, что именно происходит сейчас, общий прогресс, ETA и сообщения каждого этапа.</td></tr>
            <tr><td>Журнал</td><td>Показывает технические логи без скрытых усечений, чтобы проще ловить ошибки.</td></tr>
            <tr><td>Правая панель настроек</td><td>Главное место для выбора модели, голоса и поведения аудио.</td></tr>
            <tr><td>Нижние кнопки</td><td>Быстрый доступ к остановке, просмотру транскрипта, открытию оригинального видео и готового результата.</td></tr>
        """

        voice_rows = """
            <tr><td>Kokoro</td><td>Лучший баланс локальной скорости и качества. Хорошо подходит для тестов, массовых прогонов и обычного дубляжа.</td></tr>
            <tr><td>Edge-TTS</td><td>Очень понятная и чистая дикторская речь. Требует интернет, но обычно даёт предсказуемый результат.</td></tr>
            <tr><td>F5-TTS</td><td>Нужен, когда важнее сохранить характер конкретного голоса по образцу. Самый тяжёлый по ресурсам и времени.</td></tr>
        """

        return {
            "overview": {
                "title": tr("docs.section.overview", default="Program overview"),
                "body": f"""
                    <p><b>{APP_NAME}</b> — это локальное приложение для пошаговой озвучки YouTube-роликов. Оно скачивает видео, распознаёт речь, переводит её, генерирует новую озвучку и собирает финальный ролик обратно.</p>
                    <div class="callout">
                        Основная идея интерфейса: справа выбираются параметры, слева видно весь процесс и логи, а сверху в меню вынесены быстрые действия и инструкция.
                    </div>
                    <h2>Что умеет программа</h2>
                    <ul>
                        <li>работать с YouTube-ссылкой в один проход без ручной подготовки файлов;</li>
                        <li>показывать весь пайплайн по этапам, а не просто крутить общий спиннер;</li>
                        <li>давать выбор между несколькими движками синтеза речи;</li>
                        <li>смешивать новую озвучку с оригинальным звуком или полностью заменять аудио;</li>
                        <li>сохранять транскрипт и экспортировать его в <code>SRT</code> и <code>TXT</code>.</li>
                    </ul>
                    <h2>Когда что выбирать</h2>
                    <ul>
                        <li>Если нужен простой и быстрый рабочий результат, начни с <b>Kokoro</b>.</li>
                        <li>Если важна чёткость английского диктора, попробуй <b>Edge-TTS</b>.</li>
                        <li>Если нужен характер определённого голоса по образцу, используй <b>F5-TTS</b>.</li>
                    </ul>
                """,
            },
            "quick_start": {
                "title": tr("docs.section.quick_start", default="Quick start"),
                "body": """
                    <p>Это краткий сценарий для первого нормального запуска без лишних экспериментов.</p>
                    <ol>
                        <li>Вставь ссылку на YouTube в верхнее поле.</li>
                        <li>В правой панели выбери модель озвучки. Для первого запуска обычно удобно оставить <b>Kokoro-TTS</b>.</li>
                        <li>Выбери голос. Если нужен безопасный старт, начни с верхних голосов списка Kokoro — они уже отсортированы от сильных к слабым.</li>
                        <li>Для Kokoro при необходимости выбери акцент <code>en-US</code> или <code>en-GB</code>.</li>
                        <li>Реши, нужен ли оригинальный звук под озвучкой. Если да — оставь галочку и подстрой громкость.</li>
                        <li>Нажми <b>Старт</b> или выбери <b>Действия → Начать обработку</b>.</li>
                        <li>Следи за этапами слева. Если что-то пошло не так, сразу смотри журнал под ними.</li>
                        <li>После завершения открой <b>Результат</b> для готового видео или <b>Транскрипт</b> для проверки сегментов.</li>
                    </ol>
                    <div class="callout">
                        Если не знаешь, что менять: оставь Kokoro, верхний сильный голос, авто-обрезку пауз включённой и оригинальный звук на уровне 10–20%.
                    </div>
                """,
            },
            "menu_guide": {
                "title": tr("docs.section.menu_guide", default="Menu guide"),
                "body": f"""
                    <p>Верхнее меню теперь не просто декоративное. Оно дублирует самые полезные действия и позволяет быстрее ориентироваться в программе.</p>
                    <table>
                        <tr><th>Меню</th><th>Что внутри</th></tr>
                        {menu_rows}
                    </table>
                    <h2>Зачем дублировать действия в меню</h2>
                    <ul>
                        <li>чтобы не искать кнопку по интерфейсу, когда уже знаешь, что хочешь сделать;</li>
                        <li>чтобы основные функции были доступны даже при плотном рабочем процессе;</li>
                        <li>чтобы у программы была явная встроенная структура: запуск, настройки, документация, файлы.</li>
                    </ul>
                    <h2>Что важно помнить</h2>
                    <p>Во время обработки меню настроек блокируется так же, как и правая панель. Это сделано специально: активный запуск использует снимок настроек на момент старта и не должен меняться на ходу.</p>
                """,
            },
            "interface": {
                "title": tr("docs.section.interface", default="Interface and main sections"),
                "body": f"""
                    <p>Главный экран разделён на несколько рабочих зон, каждая отвечает за свой тип информации.</p>
                    <table>
                        <tr><th>Блок</th><th>Назначение</th></tr>
                        {interface_rows}
                    </table>
                    <h2>Как читать экран во время обработки</h2>
                    <ul>
                        <li>верх слева показывает общий прогресс и текущий сегмент;</li>
                        <li>карточки этапов ниже показывают, где именно находится пайплайн;</li>
                        <li>журнал нужен для детального разбора, если этап завис, завершился подозрительно быстро или упал с ошибкой;</li>
                        <li>правая панель нужна для подготовки следующего запуска, а не для анализа текущего лога.</li>
                    </ul>
                """,
            },
            "settings": {
                "title": tr("docs.section.settings", default="Settings and features"),
                "body": f"""
                    <p>Ниже собраны все основные настройки программы и их практический смысл.</p>
                    <table>
                        <tr><th>Параметр</th><th>Что означает на практике</th></tr>
                        {settings_rows}
                    </table>
                    <div class="callout">
                        Логика простая: сначала выбирается модель и голос, потом характер речи, затем решается, что делать с оригинальной дорожкой.
                    </div>
                """,
            },
            "voices": {
                "title": tr("docs.section.voices", default="How to choose a model and voice"),
                "body": f"""
                    <p>Ниже краткая шпаргалка по движкам и голосам.</p>
                    <table>
                        <tr><th>Движок</th><th>Когда выбирать</th></tr>
                        {voice_rows}
                    </table>
                    <h2>Как выбирать голос Kokoro</h2>
                    <ul>
                        <li>верх списка — это более сильные профили по официальным оценкам Kokoro;</li>
                        <li>если включена галочка <b>Скрывать слабые голоса</b>, из списка убираются самые спорные варианты;</li>
                        <li>обозначения <code>US</code> и <code>UK</code> помогают понять семейство голоса, а буквенная оценка даёт быстрый ориентир по качеству;</li>
                        <li>неанглийские профили тоже можно использовать, но чаще ради тембра, а не ради нейтрального английского дубляжа.</li>
                    </ul>
                    <h2>Практические рекомендации</h2>
                    <ul>
                        <li>для универсального старта: <b>af_heart</b>, <b>af_bella</b>, <b>af_nicole</b>, <b>bf_emma</b>;</li>
                        <li>если речь получается слишком торопливой, немного снизь скорость Kokoro;</li>
                        <li>если нужен максимально чистый англоязычный диктор без локального рендера, проверь Edge;</li>
                        <li>если важен характер конкретного человека, работай через F5 и образец голоса.</li>
                    </ul>
                """,
            },
            "pipeline": {
                "title": tr("docs.section.pipeline", default="How the program works"),
                "body": f"""
                    <p>Полный путь обработки состоит из девяти последовательных этапов.</p>
                    <table>
                        <tr><th>Этап</th><th>Что происходит</th></tr>
                        {pipeline_rows}
                    </table>
                    <h2>Почему это важно понимать</h2>
                    <ul>
                        <li>если ошибка произошла рано, проблема чаще в ссылке, ffmpeg, yt-dlp или входном видео;</li>
                        <li>если ошибка на TTS, смотрим модель, голос и параметры синтеза;</li>
                        <li>если финальный ролик собран, но звучит странно, чаще всего проблема уже на этапах выравнивания или микса, а не скачивания.</li>
                    </ul>
                """,
            },
            "faq": {
                "title": tr("docs.section.faq", default="Tips and FAQ"),
                "body": """
                    <h2>Что выбрать для первого запуска?</h2>
                    <p>Kokoro, один из верхних сильных голосов, акцент под задачу, оригинальный звук 10–20% и без jump-cut.</p>

                    <h2>Когда включать динамичный монтаж?</h2>
                    <p>Когда хочется более плотный ритм без длинных пауз. Но нужно помнить, что тогда финальный этап перекодирует видео и длится дольше.</p>

                    <h2>Зачем нужен журнал, если и так есть карточки этапов?</h2>
                    <p>Карточки показывают общий статус, а журнал показывает причины: модель, голос, точные тексты сегментов, ошибки ffmpeg, yt-dlp и TTS.</p>

                    <h2>Если перевод или голос звучат странно, куда смотреть первым делом?</h2>
                    <ul>
                        <li>открой транскрипт и проверь, правильно ли распознана исходная речь;</li>
                        <li>посмотри, не выбран ли экзотический голос вместо базового;</li>
                        <li>если фразы слишком длинные, попробуй другой голос или меньшую скорость;</li>
                        <li>если проблема в смешении дорожек, уменьши громкость оригинального звука.</li>
                    </ul>

                    <h2>Что делать, если не помню, где лежит результат?</h2>
                    <p>Используй кнопку <b>Результат</b> внизу или пункт меню <b>Действия → Открыть результат</b>. Все задания также лежат в папке jobs.</p>
                """,
            },
        }
