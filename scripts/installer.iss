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

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Transcriptor.exe"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\Transcriptor.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\Transcriptor.exe"; Description: "Iniciar Transcriptor"; Flags: nowait postinstall skipifsilent
