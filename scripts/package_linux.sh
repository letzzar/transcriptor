#!/usr/bin/env bash
# Genera los instaladores de Linux a partir de dist/Transcriptor (onedir de
# PyInstaller): AppImage, .deb y .rpm.
#
# Por qué los tres:
#   AppImage → un solo archivo, corre en cualquier distro sin instalar nada.
#              Es lo que menos fricción tiene para un perito que no administra
#              su equipo.
#   .deb/.rpm → integran la app en el menú del escritorio, se desinstalan con
#              el gestor de paquetes y, sobre todo, DECLARAN las libs de Qt como
#              dependencias. El tar.gz no puede hacerlo: arrancaba con errores
#              crípticos si faltaba libxcb-cursor0.
#
# Uso: scripts/package_linux.sh   (desde la raíz del repo, tras build_unix.sh)
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

BUNDLE="dist/Transcriptor"
[ -d "$BUNDLE" ] || { echo "ERROR: falta $BUNDLE (ejecuta antes build_unix.sh)"; exit 1; }

VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"
[ -n "$VERSION" ] || { echo "ERROR: no pude leer la version de pyproject.toml"; exit 1; }
echo "Empaquetando Transcriptor $VERSION para Linux"

# Dependencias de Qt. Los nombres difieren entre familias de distro, de ahí las
# dos listas. Son las que necesita PySide6 en un escritorio limpio.
# Cada una va como su propio `-d`: fpm no acepta una lista en un solo argumento.
DEPS_DEB=()
for d in libgl1 libegl1 libxkbcommon0 libxcb-cursor0 libfontconfig1 libdbus-1-3; do
  DEPS_DEB+=(-d "$d")
done
DEPS_RPM=()
for d in mesa-libGL mesa-libEGL libxkbcommon xcb-util-cursor fontconfig dbus-libs; do
  DEPS_RPM+=(-d "$d")
done

# ---------------------------------------------------------------- estructura
# Árbol común a .deb y .rpm: la app en /opt y los enganches del escritorio en
# sus rutas estándar.
ARBOL="$(mktemp -d)"
trap 'rm -rf "$ARBOL"' EXIT

install -d "$ARBOL/opt/transcriptor" "$ARBOL/usr/bin" \
           "$ARBOL/usr/share/applications" \
           "$ARBOL/usr/share/icons/hicolor/256x256/apps"
cp -a "$BUNDLE/." "$ARBOL/opt/transcriptor/"
cp logo_app.png "$ARBOL/usr/share/icons/hicolor/256x256/apps/transcriptor.png"
ln -s /opt/transcriptor/Transcriptor "$ARBOL/usr/bin/transcriptor"

cat > "$ARBOL/usr/share/applications/transcriptor.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Transcriptor
GenericName=Transcripción y auditoría de audio
Comment=Transcribe y audita audios con diarización de hablantes
Exec=transcriptor
Icon=transcriptor
Terminal=false
Categories=AudioVideo;Audio;Utility;
StartupWMClass=Transcriptor
DESKTOP

# ------------------------------------------------------------------ deb/rpm
# fpm construye ambos desde el mismo árbol; evita mantener un control y un spec
# por separado.
if ! command -v fpm >/dev/null; then
  echo "ERROR: falta fpm (gem install fpm)"; exit 1
fi

COMUN=(-s dir -C "$ARBOL"
       --name transcriptor
       --version "$VERSION"
       --license GPL-3.0
       --vendor letzzar
       --maintainer letzzar
       --url https://github.com/letzzar/transcriptor
       --description "Transcripcion y auditoria de audio con diarizacion (PySide6)"
       --force)

echo "→ .deb"
fpm "${COMUN[@]}" -t deb -a amd64 "${DEPS_DEB[@]}" \
    -p "dist/transcriptor_${VERSION}_amd64.deb" .

echo "→ .rpm"
command -v rpmbuild >/dev/null || { echo "ERROR: falta rpmbuild (paquete 'rpm')"; exit 1; }
fpm "${COMUN[@]}" -t rpm -a x86_64 "${DEPS_RPM[@]}" \
    -p "dist/transcriptor-${VERSION}-1.x86_64.rpm" .

# ----------------------------------------------------------------- AppImage
echo "→ AppImage"
APPDIR="$(mktemp -d)/Transcriptor.AppDir"
install -d "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
           "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$BUNDLE/." "$APPDIR/usr/bin/"
cp logo_app.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/transcriptor.png"
cp "$ARBOL/usr/share/applications/transcriptor.desktop" \
   "$APPDIR/usr/share/applications/transcriptor.desktop"
# appimagetool exige el .desktop y el icono también en la raíz del AppDir.
cp "$ARBOL/usr/share/applications/transcriptor.desktop" "$APPDIR/transcriptor.desktop"
cp logo_app.png "$APPDIR/transcriptor.png"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
# $APPDIR lo define el runtime del AppImage al montar la imagen.
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/Transcriptor" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

HERRAMIENTA="$(mktemp -d)/appimagetool"
curl -fsSL -o "$HERRAMIENTA" \
  "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
chmod +x "$HERRAMIENTA"
# --appimage-extract-and-run: los runners de CI no traen FUSE, así que la propia
# herramienta (que es un AppImage) no podría montarse.
ARCH=x86_64 "$HERRAMIENTA" --appimage-extract-and-run \
  "$APPDIR" "dist/Transcriptor-${VERSION}-x86_64.AppImage"

echo
echo "Listo:"
ls -lh dist/*.deb dist/*.rpm dist/*.AppImage
