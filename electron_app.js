const { app, BrowserWindow, globalShortcut } = require('electron');
const path = require('path');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: "JARVIS X OS",
    icon: path.join(__dirname, 'icon.png'),
    frame: false, // Frameless futuristic HUD window
    transparent: true,
    alwaysOnTop: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false
    }
  });

  // Load the React frontend from configured URL/port (fallback: http://localhost:5173)
  const hudPort = process.env.HUD_PORT || '5173';
  const targetUrl = process.env.HUD_URL || `http://localhost:${hudPort}`;
  mainWindow.loadURL(targetUrl);

  // Disallow arbitrary external web navigation within the trusted HUD window
  mainWindow.webContents.on('will-navigate', (event, navigationUrl) => {
    try {
      const parsedUrl = new URL(navigationUrl);
      const allowedTarget = new URL(targetUrl);
      if (parsedUrl.origin !== allowedTarget.origin && parsedUrl.origin !== `http://127.0.0.1:${hudPort}`) {
        event.preventDefault();
        console.warn(`[SECURITY] Blocked unauthorized Electron navigation to: ${navigationUrl}`);
      }
    } catch (e) {
      event.preventDefault();
    }
  });

  // Block opening unverified new windows or popups
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    console.warn(`[SECURITY] Blocked window.open popup to: ${url}`);
    return { action: 'deny' };
  });

  // Register global hotkey (Alt+Space) to toggle overlay / float mode
  globalShortcut.register('Alt+Space', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
