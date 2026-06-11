; FALCON Controller Server Setup Wizard Script
; Requires Inno Setup 6+ to compile.

[Setup]
AppId={{5E2B96D7-9092-4919-BA3C-56A2D40751A6}
AppName=FALCON Controller Server
AppVersion=1.0.0
AppPublisher=FALCON Team
AppPublisherURL=https://github.com/gitarju/Falcon-Controller
DefaultDirName={autopf}\FALCON Controller Server
DefaultGroupName=FALCON Controller Server
OutputDir=d:\AntiGravity\Controller app\files\output
OutputBaseFilename=FALCON_Controller_Server_Setup
SetupIconFile=d:\AntiGravity\Controller app\files\dist_bin\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"
Name: "installdriver"; Description: "Install ViGEmBus Virtual Gamepad Driver (Required for controller emulation)"; Check: IsDriverMissing

[Files]
Source: "d:\AntiGravity\Controller app\files\dist_bin\server.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "d:\AntiGravity\Controller app\files\dist_bin\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "d:\AntiGravity\Controller app\files\dist_bin\adb.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "d:\AntiGravity\Controller app\files\dist_bin\AdbWinApi.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "d:\AntiGravity\Controller app\files\dist_bin\AdbWinUsbApi.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "d:\AntiGravity\Controller app\files\dist_bin\ViGEmBusSetup_x64.msi"; DestDir: "{app}"; Flags: ignoreversion
Source: "d:\AntiGravity\Controller app\files\dist_bin\README.md"; DestDir: "{app}"; Flags: isreadme ignoreversion
Source: "d:\AntiGravity\Controller app\files\dist_bin\INSTRUCTION_MANUAL.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\FALCON Controller Server"; Filename: "{app}\server.exe"; IconFilename: "{app}\icon.ico"
Name: "{group}\Uninstall FALCON Controller Server"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FALCON Controller Server"; Filename: "{app}\server.exe"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
; Install the ViGEmBus gamepad driver if selected
Filename: "msiexec.exe"; Parameters: "/i ""{app}\ViGEmBusSetup_x64.msi"" /qb"; Tasks: installdriver; Description: "Installing ViGEmBus Gamepad Driver..."; Flags: runascurrentuser waituntilterminated

; Launch the server after installation
Filename: "{app}\server.exe"; Description: "{cm:LaunchProgram,FALCON Controller Server}"; Flags: postinstall nowait skipifsilent

[Code]
function IsDriverMissing(): Boolean;
begin
  // Check registry if ViGEmBus service is already installed
  Result := not RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\ViGEmBus');
end;
