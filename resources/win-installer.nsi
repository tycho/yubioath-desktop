!include "MUI2.nsh"
!include "nsProcess.nsh"

!define MUI_ICON "yubioath-desktop.ico"

; The name of the installer
Name "Yubico Authenticator"

; The file to write
OutFile "../dist/yubioath-desktop-${VERSION}-win.exe"

; The default installation directory
InstallDir "$PROGRAMFILES\Yubico\Yubico Authenticator"

; Registry key to check for directory (so if you install again, it will 
; overwrite the old one automatically)
InstallDirRegKey HKLM "Software\Yubico\yubioath-desktop" "Install_Dir"

SetCompressor /SOLID lzma
ShowInstDetails show

Var MUI_TEMP
Var STARTMENU_FOLDER

;Interface Settings

  !define MUI_ABORTWARNING

;--------------------------------

; Pages
  !insertmacro MUI_PAGE_WELCOME
  !insertmacro MUI_PAGE_DIRECTORY
  ;Start Menu Folder Page Configuration
  !define MUI_STARTMENUPAGE_DEFAULTFOLDER "Yubico\Yubico Authenticator"
  !define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU"
  !define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\Yubico\Yubico Authenticator"
  !define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"
  !insertmacro MUI_PAGE_STARTMENU Application $STARTMENU_FOLDER
  !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_INSTFILES
  !insertmacro MUI_PAGE_FINISH

  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES

;Languages
  !insertmacro MUI_LANGUAGE "English"


Section "-Kill process" KillProcess
  ${nsProcess::FindProcess} "yubioath.exe" $R0
  ${If} $R0 == 0
    DetailPrint "Yubico Authenticator (CLI) is running. Closing..."
    ${nsProcess::CloseProcess} "yubioath.exe" $R0
    Sleep 2000
  ${EndIf}
  ${nsProcess::FindProcess} "yubioath-gui.exe" $R0
  ${If} $R0 == 0
    DetailPrint "Yubico Authenticator (GUI) is running. Closing..."
    ${nsProcess::CloseProcess} "yubioath-gui.exe" $R0
    Sleep 2000
  ${EndIf}
	${nsProcess::Unload}
SectionEnd


;--------------------------------

Section "Yubico Authenticator" Main
  SectionIn RO
  SetOutPath $INSTDIR
  File /r "..\dist\Yubico Authenticator\*"
SectionEnd

Section /o "Run at Windows startup" RunAtStartup
  CreateShortCut "$SMSTARTUP\Yubico Authenticator.lnk" "$INSTDIR\yubioath-gui.exe" "-t" "$INSTDIR\yubioath-gui.exe" 0
SectionEnd

Var MYTMP

# Last section is a hidden one.
Section
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Write the installation path into the registry
  WriteRegStr HKLM "Software\Yubico\yubioath-desktop" "Install_Dir" "$INSTDIR"

  # Windows Add/Remove Programs support
  StrCpy $MYTMP "Software\Microsoft\Windows\CurrentVersion\Uninstall\yubioath-desktop"
  WriteRegStr       HKLM $MYTMP "DisplayName"     "Yubico Authenticator"
  WriteRegExpandStr HKLM $MYTMP "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegExpandStr HKLM $MYTMP "InstallLocation" "$INSTDIR"
  WriteRegStr       HKLM $MYTMP "DisplayVersion"  "${VERSION}"
  WriteRegStr       HKLM $MYTMP "Publisher"       "Yubico AB"
  WriteRegStr       HKLM $MYTMP "URLInfoAbout"    "http://www.yubico.com"
  WriteRegDWORD     HKLM $MYTMP "NoModify"        "1"
  WriteRegDWORD     HKLM $MYTMP "NoRepair"        "1"

!insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    
;Create shortcuts
  SetShellVarContext all
  CreateDirectory "$SMPROGRAMS\$STARTMENU_FOLDER"
  SetOutPath "$SMPROGRAMS\$STARTMENU_FOLDER"
  CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\Yubico Authenticator.lnk" "$INSTDIR\yubioath-gui.exe" "" "$INSTDIR\yubioath-gui.exe" 0
  CreateShortCut "$SMPROGRAMS\$STARTMENU_FOLDER\Uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0
!insertmacro MUI_STARTMENU_WRITE_END

SectionEnd

; Uninstaller

Section "Uninstall"
  
  ; Remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\yubioath-desktop"
  DeleteRegKey HKLM "Software\Yubico\yubioath-desktop"

  ; Kill processes
  ${nsProcess::FindProcess} "yubioath.exe" $R0
  ${If} $R0 == 0
    DetailPrint "Yubico Authenticator (CLI) is running. Closing..."
    ${nsProcess::CloseProcess} "yubioath.exe" $R0
    Sleep 2000
  ${EndIf}
  ${nsProcess::FindProcess} "yubioath-gui.exe" $R0
  ${If} $R0 == 0
    DetailPrint "Yubico Authenticator (GUI) is running. Closing..."
    ${nsProcess::CloseProcess} "yubioath-gui.exe" $R0
    Sleep 2000
  ${EndIf}
  ${nsProcess::Unload}

  ; Remove all
  RMDir /R "$INSTDIR"

  ; Remove shortcuts, if any
  !insertmacro MUI_STARTMENU_GETFOLDER Application $MUI_TEMP
  SetShellVarContext all

  Delete "$SMPROGRAMS\$MUI_TEMP\Uninstall.lnk"
  Delete "$SMPROGRAMS\$MUI_TEMP\Yubico Authenticator.lnk"
  Delete "$SMSTARTUP\Yubico Authenticator.lnk"

  ;Delete empty start menu parent diretories
  StrCpy $MUI_TEMP "$SMPROGRAMS\$MUI_TEMP"

  startMenuDeleteLoop:
	ClearErrors
    RMDir $MUI_TEMP
    GetFullPathName $MUI_TEMP "$MUI_TEMP\.."

    IfErrors startMenuDeleteLoopDone

    StrCmp $MUI_TEMP $SMPROGRAMS startMenuDeleteLoopDone startMenuDeleteLoop
  startMenuDeleteLoopDone:

  DeleteRegKey /ifempty HKCU "Software\Yubico\yubioath-desktop"
SectionEnd
