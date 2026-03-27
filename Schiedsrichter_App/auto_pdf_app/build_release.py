from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
import zipfile


APP_EXE_NAME = "AutoPDF_Schiedsrichter"
PACKAGE_NAME = "AutoPDF_Schiedsrichter_Windows"
ASSETS = [
    "Schiedsrichter-Reisekostenabrechnung.pdf",
    "Km-Tabelle.xlsx",
]


def write_text(path: Path, content: str) -> None:
    path.write_text(content.replace("\n", "\r\n"), encoding="utf-8")


def build_release() -> tuple[Path, Path]:
    app_dir = Path(__file__).resolve().parent
    project_dir = app_dir.parent
    release_root = project_dir / "release"
    pyinstaller_build = release_root / "pyinstaller_build"
    pyinstaller_dist = release_root / "pyinstaller_dist"
    pyinstaller_spec = release_root / "pyinstaller_spec"
    staging_root = release_root / PACKAGE_NAME
    zip_path = release_root / f"{PACKAGE_NAME}.zip"

    for path in (pyinstaller_build, pyinstaller_dist, pyinstaller_spec, staging_root):
        if path.exists():
            shutil.rmtree(path)
    if zip_path.exists():
        zip_path.unlink()

    release_root.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        APP_EXE_NAME,
        "--distpath",
        str(pyinstaller_dist),
        "--workpath",
        str(pyinstaller_build),
        "--specpath",
        str(pyinstaller_spec),
    ]

    for asset in ASSETS:
        command.extend(
            [
                "--add-data",
                f"{project_dir / asset};assets",
            ]
        )

    command.append(str(app_dir / "app.py"))

    subprocess.run(command, check=True, cwd=app_dir)

    built_dir = pyinstaller_dist / APP_EXE_NAME
    shutil.copytree(built_dir, staging_root)

    (staging_root / "output").mkdir(exist_ok=True)
    (staging_root / "chrome_profile").mkdir(exist_ok=True)

    start_script = textwrap.dedent(
        f"""\
        @echo off
        cd /d "%~dp0"
        if exist "{APP_EXE_NAME}.exe" (
            start "" "%~dp0{APP_EXE_NAME}.exe"
            exit /b 0
        )
        echo Die Datei {APP_EXE_NAME}.exe wurde nicht gefunden.
        pause
        exit /b 1
        """
    )
    write_text(staging_root / "Start_AutoPDF_Schiedsrichter.bat", start_script)

    install_script = textwrap.dedent(
        f"""\
        @echo off
        setlocal
        set "SOURCE_DIR=%~dp0"
        set "TARGET_DIR=%LocalAppData%\\AutoPDF_Schiedsrichter"

        echo Installiere Auto PDF Schiedsrichter nach "%TARGET_DIR%" ...
        if exist "%TARGET_DIR%" rmdir /s /q "%TARGET_DIR%"
        mkdir "%TARGET_DIR%"
        xcopy "%SOURCE_DIR%*" "%TARGET_DIR%\\" /E /I /Y /Q >nul

        powershell -NoProfile -ExecutionPolicy Bypass -Command "$W = New-Object -ComObject WScript.Shell; $S = $W.CreateShortcut('%USERPROFILE%\\Desktop\\Auto PDF Schiedsrichter.lnk'); $S.TargetPath = '%TARGET_DIR%\\{APP_EXE_NAME}.exe'; $S.WorkingDirectory = '%TARGET_DIR%'; $S.IconLocation = '%TARGET_DIR%\\{APP_EXE_NAME}.exe,0'; $S.Save()"

        echo.
        echo Installation abgeschlossen.
        echo Desktop-Verknuepfung wurde erstellt.
        start "" "%TARGET_DIR%\\{APP_EXE_NAME}.exe"
        exit /b 0
        """
    )
    write_text(staging_root / "Install_AutoPDF_Schiedsrichter.bat", install_script)

    readme = textwrap.dedent(
        """\
        Auto PDF Schiedsrichter - Weitergabe-Version

        Diese ZIP enthaelt keine privaten Daten.
        Nicht enthalten sind insbesondere:
        - Zugangsdaten
        - gespeicherte Profile
        - Chrome-Sessiondaten
        - bereits erzeugte PDFs

        Enthalten sind:
        - die Windows-App als EXE
        - die PDF-Vorlage
        - die KM-Tabelle

        Nutzung:
        1. ZIP entpacken
        2. Entweder portable per Start_AutoPDF_Schiedsrichter.bat starten
        3. Oder per Install_AutoPDF_Schiedsrichter.bat nach AppData installieren

        Hinweise:
        - Google Chrome muss installiert sein, wenn Spielauftraege direkt von hw.it4sport.de geladen werden sollen.
        - Die App speichert persoenliche Daten erst nach der ersten Nutzung lokal im App-Ordner.
        """
    )
    write_text(staging_root / "README_PORTABEL.txt", readme)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in staging_root.rglob("*"):
            archive.write(file_path, file_path.relative_to(release_root))

    return staging_root, zip_path


if __name__ == "__main__":
    folder, archive = build_release()
    print(folder)
    print(archive)
