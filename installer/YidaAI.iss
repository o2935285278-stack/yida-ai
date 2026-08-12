#ifndef SourceRoot
  #error SourceRoot must be provided by scripts/build_installer.ps1
#endif
#ifndef LctExecutable
  #error LctExecutable must be provided by scripts/build_installer.ps1
#endif
#ifndef LctManifest
  #error LctManifest must be provided by scripts/build_installer.ps1
#endif

#define AppVersion "0.2.2-beta"
#define AppNumericVersion "0.2.2.0"

[Setup]
#ifdef QaBuild
AppId={{B1DC58AE-4DD4-4BD7-9A0B-2366516B48D9}
#else
AppId={{3C4D56F8-CB55-4C1B-A487-44D11BD60D2D}
#endif
AppName=Yida AI
AppVerName=Yida AI {#AppVersion}
AppVersion={#AppVersion}
AppPublisher=Yida AI contributors
VersionInfoVersion={#AppNumericVersion}
VersionInfoProductVersion={#AppNumericVersion}
VersionInfoCompany=Yida AI contributors
VersionInfoDescription=Yida AI multilingual real-time reply assistant installer
VersionInfoProductName=Yida AI
DefaultDirName={localappdata}\Programs\YidaAI
DefaultGroupName=Yida AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#SourceRoot}\dist\installer
#ifdef QaBuild
OutputBaseFilename=YidaAI-0.2.2-beta-win-x64-qa-setup
#else
OutputBaseFilename=YidaAI-0.2.2-beta-win-x64-setup
#endif
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile={#SourceRoot}\LICENSE
UninstallDisplayIcon={app}\YidaAI.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "{#SourceRoot}\installer\languages\ChineseSimplified.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "{#SourceRoot}\dist\YidaAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#LctExecutable}"; DestDir: "{app}\components\LiveCaptionsTranslator"; DestName: "LiveCaptions Translator.exe"; Flags: ignoreversion
Source: "{#SourceRoot}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\PRIVACY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\SECURITY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#LctManifest}"; DestDir: "{app}\components\LiveCaptionsTranslator"; DestName: "COMPONENT_MANIFEST.txt"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalShortcuts}"; Flags: unchecked

[Icons]
#ifdef QaBuild
Name: "{autoprograms}\译答 AI QA"; Filename: "{app}\YidaAI.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\译答 AI QA"; Filename: "{app}\YidaAI.exe"; WorkingDir: "{app}"; Tasks: desktopicon
#else
Name: "{autoprograms}\译答 AI"; Filename: "{app}\YidaAI.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\译答 AI"; Filename: "{app}\YidaAI.exe"; WorkingDir: "{app}"; Tasks: desktopicon
#endif

[Run]
Filename: "{app}\YidaAI.exe"; Description: "{cm:LaunchYidaAI}"; Flags: nowait postinstall skipifsilent

[CustomMessages]
english.CreateDesktopIcon=Create a desktop shortcut
english.AdditionalShortcuts=Additional shortcuts:
english.LaunchYidaAI=Launch Yida AI
chinesesimplified.CreateDesktopIcon=创建桌面快捷方式
chinesesimplified.AdditionalShortcuts=附加快捷方式：
chinesesimplified.LaunchYidaAI=启动译答 AI
brazilianportuguese.CreateDesktopIcon=Criar um atalho na área de trabalho
brazilianportuguese.AdditionalShortcuts=Atalhos adicionais:
brazilianportuguese.LaunchYidaAI=Iniciar o Yida AI
