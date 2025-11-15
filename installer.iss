; Inno Setup script para AutTranslate
; Instrucciones:
; - Coloca este archivo y los ficheros del proyecto en la misma carpeta y compila con Inno Setup.
; - Si quieres que el instalador ejecute el instalador de Tesseract automáticamente,
;   coloca el instalador de Tesseract renombrado como "tesseract-setup.exe" en la misma carpeta
;   antes de compilar (el instalador buscará y ejecutará ese fichero con modo silencioso si existe).
; - El script copia los archivos de la aplicación a "{pf}\AutTranslate" y opcionalmente copiará
;   los archivos de entrenamiento desde la carpeta "lenguajes" hacia el "tessdata" de Tesseract
;   si detecta una instalación en las rutas por defecto.

[Setup]
AppName=AutTranslate
AppVersion=1.0
DefaultDirName={pf}\AutTranslate
DefaultGroupName=AutTranslate
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=AutTranslate_Installer
Compression=lzma
SolidCompression=yes

[Files]
; Archivos de la aplicación
Source: "{#MySourcePath}\main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MySourcePath}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MySourcePath}\run_auttranslate.bat"; DestDir: "{app}"; Flags: ignoreversion

; Copiar todos los archivos de entrenamiento del subdirectorio 'lenguajes'
Source: "{#MySourcePath}\lenguajes\*"; DestDir: "{app}\lenguajes"; Flags: recursesubdirs createallsubdirs

; NOTA: Si deseas incluir el instalador de Tesseract dentro del paquete, añade aquí la línea
; Source: "{#MySourcePath}\tesseract-setup.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\AutTranslate"; Filename: "{cmd}"; Parameters: "/C start """""py -3 \"{app}\\main.py\"""""""; WorkingDir: "{app}"
Name: "{group}\AutTranslate (Lanzador)"; Filename: "{app}\run_auttranslate.bat"; WorkingDir: "{app}"
Name: "{group}\Desinstalar AutTranslate"; Filename: "{uninstallexe}"

[Run]
; Ejecutar el instalador de Tesseract si el fichero fue incluido en el paquete
Filename: "{app}\tesseract-setup.exe"; Parameters: "/S"; StatusMsg: "Instalando Tesseract OCR..."; Flags: runhidden waituntilterminated; Check: FileExists(ExpandConstant('{app}\tesseract-setup.exe'))

[Code]
function GetDefaultTessdataDir(): string;
begin
  if DirExists('C:\\Program Files\\Tesseract-OCR\\tessdata') then
    Result := 'C:\\Program Files\\Tesseract-OCR\\tessdata'
  else if DirExists('C:\\Program Files (x86)\\Tesseract-OCR\\tessdata') then
    Result := 'C:\\Program Files (x86)\\Tesseract-OCR\\tessdata'
  else
    Result := '';
end;

procedure CopyTrainedData(const SourceDir, DestDir: string);
var
  FindRec: TFindRec;
  SourceFile, DestFile: string;
begin
  if SourceDir = '' then Exit;
  if DestDir = '' then Exit;
  if not DirExists(SourceDir) then Exit;
  if not DirExists(DestDir) then Exit;

  if FindFirst(SourceDir + '\\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) = 0 then
        begin
          SourceFile := SourceDir + '\\' + FindRec.Name;
          DestFile := DestDir + '\\' + FindRec.Name;
          if FileCopy(SourceFile, DestFile, False) then
            Log('Copiado: ' + SourceFile + ' -> ' + DestFile)
          else
            Log('No copiado (ya existe u error): ' + SourceFile);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  TessdataDir, SourceDir: string;
begin
  if CurStep = ssPostInstall then
  begin
    TessdataDir := GetDefaultTessdataDir();
    SourceDir := ExpandConstant('{app}\lenguajes');
    if TessdataDir <> '' then
    begin
      if DirExists(SourceDir) then
      begin
        MsgBox('Se detectó una instalación de Tesseract. Copiando archivos de entrenamiento a: ' + TessdataDir, mbInformation, MB_OK);
        CopyTrainedData(SourceDir, TessdataDir);
        MsgBox('Copia de archivos de lenguaje finalizada.', mbInformation, MB_OK);
      end;
    end
    else
    begin
      MsgBox('No se detectó la carpeta de instalación de Tesseract en las rutas por defecto.'#13#10 +
        'Si quieres usar Tesseract, instala Tesseract-OCR y copia manualmente los archivos .traineddata desde la carpeta "lenguajes" dentro del directorio de instalación tessdata.', mbInformation, MB_OK);
    end;
  end;
end;

{ Helper para compilar cómodamente desde la carpeta del proyecto }
#define MySourcePath GetSourcePath()

function GetSourcePath(): String;
begin
  Result := ExpandConstant('{src}');
end;
