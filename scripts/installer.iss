; Instalador de Transcriptor para Windows (Inno Setup 6).
;
; Requiere haber compilado antes con scripts\build_windows.bat (PyInstaller),
; que deja la carpeta onedir en dist\Transcriptor\.
;
; Compilar el instalador:  iscc scripts\installer.iss
; Salida:  dist\Transcriptor-Setup.exe

#define AppName "Transcriptor"
#define AppVersion "0.2.0"
#define AppPublisher "letzzar"
#define DistDir "..\dist\Transcriptor"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
; Instalacion por-usuario: la app guarda todo en %LOCALAPPDATA% (backend, datos)
; y no necesita admin. {autopf}/{autodesktop} resuelven a rutas de usuario.
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Transcriptor-Setup
SetupIconFile=..\src\transcriptor\resources\logo_app.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[UninstallDelete]
; El backend pesado (torch + motores) se descarga en el 1er arranque a la
; carpeta del usuario (Opcion C). Lo limpiamos al desinstalar; es re-descargable.
Type: filesandordirs; Name: "{localappdata}\Transcriptor"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Transcriptor.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Transcriptor.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\Transcriptor.exe"; Description: "Iniciar Transcriptor"; Flags: nowait postinstall skipifsilent
