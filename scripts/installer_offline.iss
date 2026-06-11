; Instalador OFFLINE de Transcriptor para Windows (Inno Setup 6).
;
; A diferencia de installer.iss (thin, descarga el backend en el 1er arranque),
; este empaqueta TODO: bundle PyInstaller + wheelhouse (torch CPU+CUDA + motores)
; + modelos HF (Whisper turbo, diarizacion pyannote, genero) + ffmpeg.exe.
; En el 1er arranque crea el venv del backend desde los wheels locales (sin red)
; y la app usa los modelos empaquetados (HF_HUB_OFFLINE).
;
; Requisitos previos (los prepara scripts\build_offline.ps1):
;   - dist\Transcriptor\           (bundle PyInstaller, de build_windows.bat)
;   - dist\offline_payload\wheels\ (cpu\ + cu126\)
;   - dist\offline_payload\hf_cache\hub\models--...
;   - dist\offline_payload\ffmpeg.exe
;
; Compilar:  iscc scripts\installer_offline.iss
; Salida:    dist\Transcriptor-Setup-Offline.exe

#define AppName "Transcriptor"
#define AppVersion "0.2.0"
#define AppPublisher "letzzar"
#define DistDir "..\dist\Transcriptor"
#define PayloadDir "..\dist\offline_payload"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
; Instalacion por-usuario: la app guarda el backend/datos en %LOCALAPPDATA% y no
; necesita admin. {autopf} resuelve a una ruta de usuario con PrivilegesRequired=lowest.
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Transcriptor-Setup-Offline
SetupIconFile=..\src\transcriptor\resources\logo_app.ico
; El payload (wheels + modelos) ya esta comprimido; lzma2/fast comprime rapido
; sin solido (acota RAM/tiempo en ~7 GB).
Compression=lzma2/fast
SolidCompression=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
; Windows limita un Setup.exe unico a ~4.2 GB. El payload offline (wheels CPU+CUDA
; + modelos) lo supera, asi que se reparte en varios archivos: Setup.exe + .bin de
; ~2 GB cada uno. SE DISTRIBUYEN JUNTOS (misma carpeta); el usuario ejecuta el .exe.
DiskSpanning=yes
DiskSliceSize=2100000000
SlicesPerDisk=1

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; Bundle de la app (exe + _internal con el Python embebido).
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Payload offline: wheels\, hf_cache\, ffmpeg.exe -> junto al exe ({app}).
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[UninstallDelete]
; El venv del backend se crea en el 1er arranque en la carpeta del usuario.
Type: filesandordirs; Name: "{localappdata}\Transcriptor"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Transcriptor.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Transcriptor.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\Transcriptor.exe"; Description: "Iniciar Transcriptor"; Flags: nowait postinstall skipifsilent
