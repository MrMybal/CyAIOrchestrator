"""Windows notification-area lifetime, using pywebview's WinForms thread."""

class WindowsTray:
    def __init__(self, window, runtime):
        self.window, self.runtime = window, runtime
        self.icon = self.menu = None
        self.quitting = False

    def install(self):
        self.window.events.shown.wait()
        from System import Action
        self.window.native.Invoke(Action(self._install))

    def _install(self):
        from System import EventHandler
        from System.Drawing import Icon
        from pathlib import Path
        from System.Windows.Forms import NotifyIcon, ContextMenuStrip
        self.menu = ContextMenuStrip()
        self.menu.Items.Add('Ouvrir CyAI Orchestrator', None, EventHandler(self.open))
        self.menu.Items.Add('Quitter', None, EventHandler(self.quit))
        self.icon = NotifyIcon()
        self.brand_icon = Icon(str(Path(__file__).parent / 'web' / 'cyai-logo.ico'))
        self.icon.Icon = self.brand_icon
        self.window.native.Icon = self.brand_icon
        self.icon.Text = 'CyAI Orchestrator'
        self.icon.ContextMenuStrip = self.menu
        self.icon.DoubleClick += self.open
        self.window.native.FormClosing += self.on_closing
        self.window.native.FormClosed += self.dispose
        self.icon.Visible = True

    def on_closing(self, sender, args):
        # A Windows shutdown must never be cancelled by close-to-tray.
        if not self.quitting and self.icon is not None and str(args.CloseReason) == 'UserClosing':
            args.Cancel = True
            self.window.native.Hide()

    def open(self, *_):
        from System.Windows.Forms import FormWindowState
        form = self.window.native
        if form.WindowState == FormWindowState.Minimized:
            form.WindowState = FormWindowState.Normal
        form.Show()
        form.Activate()

    def quit(self, *_):
        from System.Windows.Forms import MessageBox, MessageBoxButtons, MessageBoxIcon, DialogResult
        engine = self.runtime.engine
        if engine:
            active = self.runtime.store.rows("SELECT id FROM missions WHERE status IN ('queued','running','awaiting_approval')")
            if active and MessageBox.Show(self.window.native,
                'Des missions sont en cours. Quitter les interrompra. Quitter quand même ?',
                'CyAI Orchestrator', MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes:
                return
        self.quitting = True
        import webview
        for window in list(webview.windows):
            if window is not self.window:
                window.destroy()
        self.window.native.Close()

    def dispose(self, *_):
        if self.icon is not None:
            self.icon.Visible = False
            self.icon.Dispose()
            self.icon = None
        if self.menu is not None:
            self.menu.Dispose()
            self.menu = None
        if getattr(self, 'brand_icon', None) is not None:
            self.brand_icon.Dispose()
            self.brand_icon = None
